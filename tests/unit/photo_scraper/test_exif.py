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

"""Unit tests for photo EXIF metadata extraction (T-037).

Verifies:
- Parsing of various EXIF timestamp formats into Python dates
- Conversion of EXIF GPS coordinates (degrees, minutes, seconds) to decimal degrees
- Hemispheric sign adjustments (South -> negative, West -> negative)
- Graceful skipping of unsupported file extensions or corrupt/non-image files
- Extraction of coordinates and dates from synthetic JPEG/TIFF images
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from photo_scraper.core.exif import (
    _convert_to_degrees,
    _parse_exif_date,
    extract_image_metadata,
)


class TestExifExtraction:
    """Test suite for EXIF metadata parsing."""

    def test_parse_exif_date_formats(self) -> None:
        """Asserts diverse date formats are parsed correctly."""
        assert _parse_exif_date("2024:06:15 14:30:00") == date(2024, 6, 15)
        assert _parse_exif_date("2023-11-20 08:45:12") == date(2023, 11, 20)
        assert _parse_exif_date("2022/04/05 12:00:00") == date(2022, 4, 5)
        assert _parse_exif_date("2021:12:31") == date(2021, 12, 31)
        assert _parse_exif_date("2020-01-01") == date(2020, 1, 1)
        assert _parse_exif_date("invalid_date") is None
        assert _parse_exif_date("") is None

    def test_convert_to_degrees(self) -> None:
        """Asserts DMS coordinate conversion to decimal degrees."""
        # 37 deg, 44 min, 36 sec = 37.743333...
        val = (37, 44, 36.0)
        deg = _convert_to_degrees(val)
        assert deg is not None
        assert round(deg, 4) == 37.7433

        # Direct float / invalid value
        assert _convert_to_degrees(42.5) == 42.5
        assert _convert_to_degrees("invalid") is None

    def test_extract_metadata_synthetic_image(self) -> None:
        """Asserts EXIF metadata is parsed from an image with GPS and date tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "sample_gps.jpg"
            img = Image.new("RGB", (20, 20), color=(100, 150, 200))
            exif = img.getexif()

            # DateTimeOriginal (36867)
            exif[36867] = "2024:08:12 15:45:00"

            # GPS IFD (0x8825)
            # 1=LatRef, 2=Lat, 3=LonRef, 4=Lon
            gps_ifd = exif.get_ifd(0x8825)
            gps_ifd[1] = "S"  # South -> negative
            gps_ifd[2] = (33, 51, 0.0)  # -33.85
            gps_ifd[3] = "E"  # East -> positive
            gps_ifd[4] = (151, 12, 0.0)  # 151.20

            img.save(img_path, exif=exif)

            meta = extract_image_metadata(img_path)
            assert meta.date_taken == date(2024, 8, 12)
            assert meta.latitude is not None
            assert round(meta.latitude, 2) == -33.85
            assert meta.longitude is not None
            assert round(meta.longitude, 2) == 151.20

    def test_extract_metadata_unsupported_extension(self) -> None:
        """Asserts non-image files are gracefully skipped without errors."""
        txt_file = Path("dummy.txt")
        meta = extract_image_metadata(txt_file)
        assert meta.date_taken is None
        assert meta.latitude is None
        assert meta.longitude is None

    def test_extract_metadata_corrupt_file(self) -> None:
        """Asserts corrupt image file does not raise an exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_img = Path(tmpdir) / "corrupt.jpg"
            bad_img.write_text("not an image at all", encoding="utf-8")

            meta = extract_image_metadata(bad_img)
            assert meta.date_taken is None
            assert meta.latitude is None
