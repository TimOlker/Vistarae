"""Unit tests for EXIF metadata parsing."""

import tempfile
from datetime import date
from pathlib import Path

from PIL import Image

from photo_scraper.core.exif import (
    _convert_to_degrees,
    _parse_exif_date,
    extract_image_metadata,
)


def test_parse_exif_date():
    assert _parse_exif_date("2023:06:15 14:30:00") == date(2023, 6, 15)
    assert _parse_exif_date("2022-10-04 09:12:33") == date(2022, 10, 4)
    assert _parse_exif_date("2021/04/20") == date(2021, 4, 20)
    assert _parse_exif_date("invalid") is None
    assert _parse_exif_date("") is None


def test_convert_to_degrees():
    # 41 deg, 51 min, 0.0 sec = 41.85 degrees
    val = (41, 51, 0.0)
    deg = _convert_to_degrees(val)
    assert deg is not None
    assert round(deg, 2) == 41.85


def test_extract_image_metadata_with_synthetic_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_img_path = Path(tmpdir) / "test_photo.jpg"

        # Create a small RGB image
        img = Image.new("RGB", (50, 50), color=(100, 150, 200))
        exif = img.getexif()

        # Set DateTimeOriginal (36867)
        exif[36867] = "2024:07:04 12:00:00"

        # Set GPS IFD (0x8825)
        # GPSLatitude = 2, GPSLatitudeRef = 1, GPSLongitude = 4, GPSLongitudeRef = 3
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N"
        gps_ifd[2] = (41, 51, 0.0)  # 41.85 N
        gps_ifd[3] = "W"
        gps_ifd[4] = (88, 18, 45.36)  # ~88.3126 W

        img.save(test_img_path, exif=exif)

        meta = extract_image_metadata(test_img_path)
        assert meta.date_taken == date(2024, 7, 4)
        assert meta.latitude is not None
        assert round(meta.latitude, 2) == 41.85
        assert meta.longitude is not None
        assert round(meta.longitude, 2) == -88.31
