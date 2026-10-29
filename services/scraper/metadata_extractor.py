# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Multi-standard metadata and companion sidecar extraction engine (T-016).

Adheres to:
- REQ-SCR-017: Supported image formats (.jpg, .jpeg, .tiff, .heic, .png, .webp, .dng) and sidecars (.xmp, .json, .xml)
- REQ-SCR-018: Embedded EXIF (2.3+), IPTC, and XMP coordinate and date extraction
- REQ-SCR-019: Adobe/Darktable XMP RDF/XML sidecar parsing via defusedxml
- REQ-SCR-020: Google Photos Takeout JSON sidecar parsing
- REQ-SCR-021: Companion sidecar coordinate fallback when embedded GPS is absent
- REQ-SCR-022: Decimal WGS-84 coordinate normalization
- REQ-SCR-023: Empty coordinates when no source provides valid GPS
- REQ-SCR-024: Timestamp collection across embedded and sidecar sources
- REQ-SCR-025: Earliest (lowest) date selection for multi-date directory
- REQ-SCR-026: Keyword and category tag aggregation
- REQ-SCR-027: Strict read-only file access guarantee (open in 'rb' mode only)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import defusedxml.ElementTree as ET
from PIL import ExifTags, Image

logger = logging.getLogger("vistarae.scraper.metadata")

# Supported media extensions
SUPPORTED_IMAGE_EXTENSIONS: Final[set[str]] = {
    ".jpg",
    ".jpeg",
    ".tiff",
    ".heic",
    ".png",
    ".webp",
    ".dng",
}

# Supported sidecar extensions
SUPPORTED_SIDECAR_EXTENSIONS: Final[set[str]] = {".xmp", ".json", ".xml"}

# Regex for parsing DMS in strings (e.g., 28.6562N or 28,39.372N)
_DMS_STR_PATTERN: Final[re.Pattern] = re.compile(
    r"^([0-9.]+)[, ]*([0-9.]*)[, ]*([0-9.]*)\s*([NSEW])$", re.IGNORECASE
)


@dataclass
class DirectoryMetadata:
    """Aggregated metadata extracted from all media in a candidate folder."""

    latitude: Decimal | None = None
    longitude: Decimal | None = None
    earliest_date: str | None = None
    all_dates: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def _to_float(val: Any) -> float:
    """Converts int, float, Fraction, or (num, den) tuple to float."""
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        return float(val.numerator) / float(val.denominator) if val.denominator != 0 else 0.0
    if isinstance(val, (tuple, list)) and len(val) == 2:
        num, den = val
        return float(num) / float(den) if den != 0 else 0.0
    return float(val)


def convert_gps_to_decimal(coords: Any, ref: str) -> Decimal | None:
    """Converts GPS degrees/minutes/seconds coordinate to decimal degrees.

    Args:
        coords: Tuple of (degrees, minutes, seconds) components.
        ref: Direction reference ('N', 'S', 'E', 'W').

    Returns:
        Decimal representation rounded to 7 decimal places, or None if invalid.
    """
    try:
        if isinstance(coords, (tuple, list)) and len(coords) >= 3:
            deg = _to_float(coords[0])
            minute = _to_float(coords[1])
            sec = _to_float(coords[2])
            dec = deg + (minute / 60.0) + (sec / 3600.0)
        elif isinstance(coords, (int, float, Decimal)):
            dec = float(coords)
        else:
            return None

        clean_ref = ref.strip().upper()
        if clean_ref in ("S", "W"):
            dec = -dec

        return Decimal(f"{dec:.7f}")
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _parse_coordinate_string(coord_str: str) -> Decimal | None:
    """Parses coordinate string like '28.6562N' or '-25.6953'."""
    clean = coord_str.strip()
    match = _DMS_STR_PATTERN.match(clean)
    if match:
        deg_str, min_str, sec_str, ref = match.groups()
        deg = float(deg_str) if deg_str else 0.0
        minute = float(min_str) if min_str else 0.0
        sec = float(sec_str) if sec_str else 0.0
        return convert_gps_to_decimal((deg, minute, sec), ref)

    # Check trailing direction letter
    if clean and clean[-1].upper() in ("N", "S", "E", "W"):
        ref = clean[-1].upper()
        try:
            val = float(clean[:-1].strip())
            return convert_gps_to_decimal(val, ref)
        except ValueError:
            pass

    try:
        val = float(clean)
        return Decimal(f"{val:.7f}")
    except ValueError:
        return None


def _clean_date_str(raw: str) -> str | None:
    """Normalizes various timestamp formats to ISO YYYY-MM-DD."""
    if not raw:
        return None
    cleaned = raw.strip()
    # Check YYYY:MM:DD or YYYY-MM-DD
    match = re.match(r"^(\d{4})[:\-](\d{2})[:\-](\d{2})", cleaned)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    return None


def _extract_exif_metadata(
    image_path: Path,
) -> tuple[tuple[Decimal, Decimal] | None, str | None, list[str]]:
    """Extracts GPS, date, and tags from embedded image EXIF (read-only)."""
    gps: tuple[Decimal, Decimal] | None = None
    date_val: str | None = None
    tags: list[str] = []

    try:
        with open(image_path, "rb") as f:
            im = Image.open(f)
            exif = im.getexif()
            if not exif:
                return None, None, []

            # Date tags: DateTimeOriginal (36867), DateTimeDigitized (36868), DateTime (306)
            for tag_id in (36867, 36868, 306):
                if tag_id in exif:
                    dt = _clean_date_str(str(exif[tag_id]))
                    if dt:
                        date_val = dt
                        break

            # XPKeywords tag (40094)
            if 40094 in exif:
                val = exif[40094]
                if isinstance(val, bytes):
                    kw = val.decode("utf-16le", errors="ignore").rstrip("\x00")
                    tags.extend([k.strip() for k in kw.split(";") if k.strip()])

            # GPS Info (34853)
            gps_info = exif.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else exif.get(34853)
            if gps_info:
                lat_raw = gps_info.get(2)  # GPSLatitude
                lat_ref = gps_info.get(1, "N")  # GPSLatitudeRef
                lon_raw = gps_info.get(4)  # GPSLongitude
                lon_ref = gps_info.get(3, "E")  # GPSLongitudeRef

                if lat_raw and lon_raw:
                    lat_dec = convert_gps_to_decimal(lat_raw, str(lat_ref))
                    lon_dec = convert_gps_to_decimal(lon_raw, str(lon_ref))
                    if lat_dec is not None and lon_dec is not None:
                        gps = (lat_dec, lon_dec)
    except Exception as exc:
        logger.debug("Failed extracting EXIF from %s: %s", image_path, exc)

    return gps, date_val, tags


def parse_xmp_sidecar(
    xmp_path: Path,
) -> tuple[tuple[Decimal, Decimal] | None, str | None, list[str]]:
    """Parses an Adobe or Darktable XMP RDF/XML sidecar file strictly read-only."""
    gps: tuple[Decimal, Decimal] | None = None
    date_val: str | None = None
    tags: list[str] = []

    try:
        with open(xmp_path, "rb") as f:
            content = f.read()

        root = ET.fromstring(content)
        # Scan all elements and attributes for coordinates and date
        lat_dec: Decimal | None = None
        lon_dec: Decimal | None = None

        for elem in root.iter():
            # Check attributes
            for attr_name, attr_val in elem.attrib.items():
                attr_lower = attr_name.lower()
                if "gpslatitude" in attr_lower and lat_dec is None:
                    lat_dec = _parse_coordinate_string(attr_val)
                elif "gpslongitude" in attr_lower and lon_dec is None:
                    lon_dec = _parse_coordinate_string(attr_val)
                elif ("datecreated" in attr_lower or "createdate" in attr_lower or "datetimeoriginal" in attr_lower or "datetime" in attr_lower) and date_val is None:
                    date_val = _clean_date_str(attr_val)

            # Check text
            tag_lower = elem.tag.lower()
            if "gpslatitude" in tag_lower and elem.text and lat_dec is None:
                lat_dec = _parse_coordinate_string(elem.text)
            elif "gpslongitude" in tag_lower and elem.text and lon_dec is None:
                lon_dec = _parse_coordinate_string(elem.text)
            elif ("datecreated" in tag_lower or "createdate" in tag_lower or "datetimeoriginal" in tag_lower or "datetime" in tag_lower) and elem.text and date_val is None:
                date_val = _clean_date_str(elem.text)
            elif (tag_lower.endswith("title") or tag_lower.endswith("subject") or tag_lower.endswith("li")) and elem.text and elem.text.strip():
                tags.append(elem.text.strip())

        if lat_dec is not None and lon_dec is not None:
            gps = (lat_dec, lon_dec)
    except Exception as exc:
        logger.debug("Failed parsing XMP sidecar %s: %s", xmp_path, exc)

    return gps, date_val, tags


def _parse_json_sidecar(
    json_path: Path,
) -> tuple[tuple[Decimal, Decimal] | None, str | None, list[str]]:
    """Parses a Google Photos Takeout JSON sidecar strictly read-only."""
    gps: tuple[Decimal, Decimal] | None = None
    date_val: str | None = None
    tags: list[str] = []

    try:
        with open(json_path, "rb") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Coordinates
            geo = data.get("geoData") or data.get("geoDataExif")
            if isinstance(geo, dict):
                lat = geo.get("latitude")
                lon = geo.get("longitude")
                if lat is not None and lon is not None and (float(lat) != 0.0 or float(lon) != 0.0):
                    gps = (Decimal(f"{float(lat):.7f}"), Decimal(f"{float(lon):.7f}"))

            # Timestamp
            photo_time = data.get("photoTakenTime")
            if isinstance(photo_time, dict):
                ts = photo_time.get("timestamp")
                if ts:
                    try:
                        dt = datetime.fromtimestamp(int(ts), tz=UTC)
                        date_val = dt.strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass
                if not date_val:
                    date_val = _clean_date_str(photo_time.get("formatted", ""))

            # Tags / descriptions
            for key in ("title", "description"):
                val = data.get(key)
                if val and isinstance(val, str) and val.strip():
                    tags.append(val.strip())
    except Exception as exc:
        logger.debug("Failed parsing JSON sidecar %s: %s", json_path, exc)

    return gps, date_val, tags


def _find_sidecars(image_file: Path) -> list[Path]:
    """Finds companion sidecar files for an image file in the same folder."""
    sidecars: list[Path] = []
    parent = image_file.parent
    name = image_file.name
    stem = image_file.stem

    for ext in (".xmp", ".json", ".xml"):
        # Pattern 1: <image_name><ext> (e.g. photo.jpg.xmp)
        p1 = parent / f"{name}{ext}"
        if p1.is_file():
            sidecars.append(p1)
        # Pattern 2: <stem><ext> (e.g. photo.xmp)
        p2 = parent / f"{stem}{ext}"
        if p2.is_file() and p2 not in sidecars:
            sidecars.append(p2)

    return sidecars


def extract_directory_metadata(directory: Path | str) -> DirectoryMetadata:
    """Aggregates metadata across all media and companion sidecars in a directory.

    Strictly enforces read-only access per REQ-SCR-027.

    Args:
        directory: Filesystem path of the candidate POI directory.

    Returns:
        DirectoryMetadata with coordinates, earliest date, and aggregated tags.
    """
    folder = Path(directory)
    if not folder.is_dir():
        return DirectoryMetadata()

    primary_gps: tuple[Decimal, Decimal] | None = None
    all_dates: set[str] = set()
    all_tags: set[str] = set()

    for item in sorted(folder.iterdir()):
        if not item.is_file():
            continue

        ext_lower = item.suffix.lower()

        # Handle supported images
        if ext_lower in SUPPORTED_IMAGE_EXTENSIONS:
            exif_gps, exif_date, exif_tags = _extract_exif_metadata(item)
            if exif_date:
                all_dates.add(exif_date)
            all_tags.update(exif_tags)

            current_gps = exif_gps

            # Inspect companion sidecars
            for sidecar in _find_sidecars(item):
                sc_ext = sidecar.suffix.lower()
                sc_gps: tuple[Decimal, Decimal] | None = None
                sc_date: str | None = None
                sc_tags: list[str] = []

                if sc_ext in (".xmp", ".xml"):
                    sc_gps, sc_date, sc_tags = parse_xmp_sidecar(sidecar)
                elif sc_ext == ".json":
                    sc_gps, sc_date, sc_tags = _parse_json_sidecar(sidecar)

                if sc_date:
                    all_dates.add(sc_date)
                all_tags.update(sc_tags)

                # Sidecar fallback for GPS if embedded is absent (REQ-SCR-021)
                if current_gps is None and sc_gps is not None:
                    current_gps = sc_gps

            if primary_gps is None and current_gps is not None:
                primary_gps = current_gps

        # Handle standalone sidecars in folder
        elif ext_lower in SUPPORTED_SIDECAR_EXTENSIONS:
            sc_gps, sc_date, sc_tags = (
                parse_xmp_sidecar(item) if ext_lower in (".xmp", ".xml") else _parse_json_sidecar(item)
            )
            if sc_date:
                all_dates.add(sc_date)
            all_tags.update(sc_tags)
            if primary_gps is None and sc_gps is not None:
                primary_gps = sc_gps

    sorted_dates = sorted(all_dates)
    earliest = sorted_dates[0] if sorted_dates else None

    lat = primary_gps[0] if primary_gps else None
    lon = primary_gps[1] if primary_gps else None

    return DirectoryMetadata(
        latitude=lat,
        longitude=lon,
        earliest_date=earliest,
        all_dates=sorted_dates,
        tags=sorted(all_tags),
    )
