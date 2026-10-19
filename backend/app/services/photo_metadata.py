"""Photo metadata extraction service (EXIF, GPS, Dates, IPTC & XMP Tags)."""

import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, IptcImagePlugin

logger = logging.getLogger("vistarae.photo_metadata")

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".tif",
    ".tiff",
    ".webp",
    ".dng",
    ".cr2",
    ".nef",
    ".arw",
}


@dataclass
class ExtractedPhotoMetadata:
    """Extracted EXIF/IPTC/XMP photo metadata."""

    date_taken: date | None = None
    latitude: float | None = None
    longitude: float | None = None
    tags: list[str] = field(default_factory=list)
    file_name: str | None = None
    folder_path: str | None = None


def convert_gps_to_degrees(value: Any) -> float | None:
    """Converts EXIF GPS coordinate (deg, min, sec) tuple to decimal degrees."""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def parse_exif_date(date_str: str) -> date | None:
    """Parses various EXIF date string formats into a standard date object."""
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip().replace("\x00", "")
    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y:%m:%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:19], fmt)
            if 1970 <= dt.year <= 2100:
                return dt.date()
        except ValueError:
            continue
    return None


def extract_tags_from_image(img: Image.Image) -> list[str]:
    """Extracts keywords and tags from IPTC, XMP, and EXIF XPKeywords."""
    found_tags: set[str] = set()

    # 1. IPTC Keywords (tag (2, 25))
    try:
        iptc = IptcImagePlugin.getiptcinfo(img)
        if iptc and (2, 25) in iptc:
            raw_keywords = iptc[(2, 25)]
            if isinstance(raw_keywords, list):
                for kw in raw_keywords:
                    if isinstance(kw, bytes):
                        val = kw.decode("utf-8", errors="ignore").strip()
                        if val:
                            found_tags.add(val)
                    elif isinstance(kw, str) and kw.strip():
                        found_tags.add(kw.strip())
            elif isinstance(raw_keywords, (bytes, str)):
                val = (
                    raw_keywords.decode("utf-8", errors="ignore")
                    if isinstance(raw_keywords, bytes)
                    else raw_keywords
                )
                if val.strip():
                    found_tags.add(val.strip())
    except Exception:
        pass

    # 2. EXIF XPKeywords (Tag 40094, UTF-16LE encoded bytes)
    try:
        exif = img.getexif()
        if exif:
            xp_keywords = exif.get(40094)
            if xp_keywords:
                if isinstance(xp_keywords, bytes):
                    decoded = xp_keywords.decode("utf-16le", errors="ignore").rstrip("\x00")
                    for kw in decoded.split(";"):
                        if kw.strip():
                            found_tags.add(kw.strip())
                elif isinstance(xp_keywords, str):
                    for kw in xp_keywords.split(";"):
                        if kw.strip():
                            found_tags.add(kw.strip())
    except Exception:
        pass

    # 3. XMP dc:subject keywords
    try:
        xmp = img.getxmp()
        if xmp and isinstance(xmp, dict):
            def search_subjects(d: Any):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k.lower().endswith("subject") or k.lower() == "subject":
                            if isinstance(v, list):
                                for s in v:
                                    if isinstance(s, str) and s.strip():
                                        found_tags.add(s.strip())
                            elif isinstance(v, dict):
                                bag = v.get("Bag") or v.get("Seq")
                                if isinstance(bag, list):
                                    for s in bag:
                                        if isinstance(s, str) and s.strip():
                                            found_tags.add(s.strip())
                                elif isinstance(bag, dict) and "li" in bag:
                                    li = bag["li"]
                                    if isinstance(li, list):
                                        for s in li:
                                            if isinstance(s, str) and s.strip():
                                                found_tags.add(s.strip())
                                    elif isinstance(li, str) and li.strip():
                                        found_tags.add(li.strip())
                        search_subjects(v)
                elif isinstance(d, list):
                    for item in d:
                        search_subjects(item)

            search_subjects(xmp)
    except Exception:
        pass

    return sorted(list(found_tags))


def extract_metadata_from_pil(img: Image.Image) -> ExtractedPhotoMetadata:
    """Extracts date taken, coordinates, and tags from an opened PIL Image."""
    meta = ExtractedPhotoMetadata()

    try:
        # Extract tags
        meta.tags = extract_tags_from_image(img)

        exif = img.getexif()
        if not exif:
            return meta

        # 1. Date Taken
        date_val = None
        for tag_id in (36867, 36868, 306):
            raw = exif.get(tag_id)
            if raw:
                date_val = parse_exif_date(str(raw))
                if date_val:
                    break

        if not date_val:
            try:
                exif_ifd = exif.get_ifd(0x8769)
                for tag_id in (36867, 36868, 306):
                    raw = exif_ifd.get(tag_id)
                    if raw:
                        date_val = parse_exif_date(str(raw))
                        if date_val:
                            break
            except Exception:
                pass

        meta.date_taken = date_val

        # 2. GPS Coordinates
        gps_ifd = {}
        try:
            gps_ifd = exif.get_ifd(0x8825)
        except Exception:
            gps_ifd = {}

        if not gps_ifd:
            gps_raw = exif.get(34853)
            if isinstance(gps_raw, dict):
                gps_ifd = gps_raw

        if gps_ifd:
            lat_raw = gps_ifd.get(2)
            lat_ref = gps_ifd.get(1)
            lon_raw = gps_ifd.get(4)
            lon_ref = gps_ifd.get(3)

            if lat_raw and lon_raw:
                lat = convert_gps_to_degrees(lat_raw)
                lon = convert_gps_to_degrees(lon_raw)

                if lat is not None and lon is not None:
                    if lat_ref and str(lat_ref).upper().startswith("S"):
                        lat = -lat
                    if lon_ref and str(lon_ref).upper().startswith("W"):
                        lon = -lon

                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and not (lat == 0.0 and lon == 0.0):
                        meta.latitude = round(lat, 7)
                        meta.longitude = round(lon, 7)

    except Exception as e:
        logger.debug(f"Error parsing EXIF metadata: {e}")

    return meta


def extract_photo_metadata_from_bytes(file_bytes: bytes, filename: str | None = None) -> ExtractedPhotoMetadata:
    """Extracts photo metadata from an in-memory byte stream."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            meta = extract_metadata_from_pil(img)
            meta.file_name = filename
            return meta
    except Exception as e:
        logger.debug(f"Could not open image bytes: {e}")
        return ExtractedPhotoMetadata(file_name=filename)


def extract_photo_metadata_from_path(file_path: Path) -> ExtractedPhotoMetadata:
    """Extracts photo metadata from a file on the local filesystem."""
    if not file_path.exists() or file_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return ExtractedPhotoMetadata(file_name=file_path.name)

    try:
        with Image.open(file_path) as img:
            meta = extract_metadata_from_pil(img)
            meta.file_name = file_path.name
            meta.folder_path = str(file_path.parent)
            return meta
    except Exception as e:
        logger.debug(f"Could not open image file {file_path}: {e}")
        return ExtractedPhotoMetadata(file_name=file_path.name, folder_path=str(file_path.parent))
