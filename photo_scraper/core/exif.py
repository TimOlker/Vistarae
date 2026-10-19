"""EXIF metadata extractor for image files (dates and GPS coordinates)."""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger("vistarae.photo_scraper.exif")

SUPPORTED_EXTENSIONS = {
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
class ImageMetadata:
    """Metadata extracted from a single image file."""

    file_path: Path
    date_taken: date | None = None
    latitude: float | None = None
    longitude: float | None = None


def _convert_to_degrees(value: Any) -> float | None:
    """Converts EXIF GPS coordinate (degrees, minutes, seconds) to decimal degrees."""
    try:
        # Handles tuples of (deg, min, sec) with IFDRational or float/int
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def _parse_exif_date(date_str: str) -> date | None:
    """Parses various EXIF date string formats into a standard date object."""
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    # Replace null terminators
    date_str = date_str.replace("\x00", "")

    # Expected formats: "YYYY:MM:DD HH:MM:SS", "YYYY-MM-DD HH:MM:SS", "YYYY:MM:DD"
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
            # Basic sanity check on year
            if 1970 <= dt.year <= 2100:
                return dt.date()
        except ValueError:
            continue
    return None


def extract_image_metadata(file_path: Path) -> ImageMetadata:
    """Reads EXIF data from an image file, returning dates and coordinates if present."""
    meta = ImageMetadata(file_path=file_path)

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return meta

    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if not exif:
                return meta

            # 1. Date extraction
            # Tag IDs: DateTimeOriginal=36867, DateTimeDigitized=36868, DateTime=306
            date_val = None
            for tag_id in (36867, 36868, 306):
                raw_val = exif.get(tag_id)
                if raw_val:
                    date_val = _parse_exif_date(str(raw_val))
                    if date_val:
                        break

            # If not in main exif, check Exif IFD (tag 34665)
            if not date_val:
                try:
                    exif_ifd = exif.get_ifd(0x8769)
                    for tag_id in (36867, 36868, 306):
                        raw_val = exif_ifd.get(tag_id)
                        if raw_val:
                            date_val = _parse_exif_date(str(raw_val))
                            if date_val:
                                break
                except Exception:
                    pass

            meta.date_taken = date_val

            # 2. GPS extraction (IFD 0x8825)
            try:
                gps_ifd = exif.get_ifd(0x8825)
            except Exception:
                gps_ifd = {}

            if not gps_ifd:
                # Fallback to direct tag 34853
                gps_raw = exif.get(34853)
                if isinstance(gps_raw, dict):
                    gps_ifd = gps_raw

            if gps_ifd:
                # GPSLatitude = 2, GPSLatitudeRef = 1
                # GPSLongitude = 4, GPSLongitudeRef = 3
                lat_raw = gps_ifd.get(2)
                lat_ref = gps_ifd.get(1)
                lon_raw = gps_ifd.get(4)
                lon_ref = gps_ifd.get(3)

                if lat_raw and lon_raw:
                    lat = _convert_to_degrees(lat_raw)
                    lon = _convert_to_degrees(lon_raw)

                    if lat is not None and lon is not None:
                        if lat_ref and str(lat_ref).upper().startswith("S"):
                            lat = -lat
                        if lon_ref and str(lon_ref).upper().startswith("W"):
                            lon = -lon
                        # Verify valid ranges
                        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and not (lat == 0.0 and lon == 0.0):
                            meta.latitude = round(lat, 7)
                            meta.longitude = round(lon, 7)

    except Exception as exc:
        logger.debug(f"Could not read EXIF from {file_path}: {exc}")

    return meta
