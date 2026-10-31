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

"""Unit tests for multi-standard metadata extraction (T-012).

Validates:
- Embedded EXIF GPS decoding and date extraction (REQ-SCR-018, REQ-SCR-022)
- Adobe/Darktable XMP RDF/XML sidecar parsing (REQ-SCR-019)
- Google Photos JSON sidecar parsing (REQ-SCR-020)
- Fallback coordinate precedence from sidecars (REQ-SCR-021)
- Earliest date selection across multi-date folder (REQ-SCR-024, REQ-SCR-025)
- Keyword and tag aggregation (REQ-SCR-026)
- Strict read-only preservation (REQ-SCR-027)
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import ExifTags, Image

from services.scraper.metadata_extractor import (
    DirectoryMetadata,
    _clean_date_str,
    _extract_exif_metadata,
    _find_sidecars,
    _parse_coordinate_string,
    _parse_json_sidecar,
    _to_float,
    convert_gps_to_decimal,
    extract_directory_metadata,
    parse_xmp_sidecar,
)


def _compute_dir_hash(directory: Path) -> str:
    """Computes SHA-256 tree hash to ensure read-only guarantee."""
    hasher = hashlib.sha256()
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            hasher.update(p.name.encode())
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def test_convert_gps_to_decimal() -> None:
    """Verifies DMS to decimal degree conversion and hemisphere negation."""
    dms = ((35, 1), (42, 1), (5328, 100))
    lat = convert_gps_to_decimal(dms, "N")
    assert lat is not None
    assert round(float(lat), 4) == 35.7148

    lat_s = convert_gps_to_decimal(dms, "S")
    assert lat_s is not None
    assert round(float(lat_s), 4) == -35.7148

    dms_lon = ((119, 1), (34, 1), (2496, 100))
    lon_w = convert_gps_to_decimal(dms_lon, "W")
    assert lon_w is not None
    assert round(float(lon_w), 4) == -119.5736


def test_parse_xmp_sidecar_red_fort() -> None:
    """Verifies XMP RDF/XML parsing of GPS, date, and title."""
    xmp_path = Path("tests/fixtures/sample_photos/Trip To India/01 Delhi/Red Fort/IMG_1001.xmp")
    gps, date_val, tags = parse_xmp_sidecar(xmp_path)
    assert gps is not None
    lat, lon = gps
    assert round(float(lat), 4) == 28.6562
    assert round(float(lon), 4) == 77.2410
    assert date_val == "2023-04-15"
    assert "Red Fort Historic Complex" in tags


def test_extract_directory_metadata_sensoji_gphotos_json() -> None:
    """Verifies Google Photos JSON sidecar parsing for Senso-ji."""
    folder = Path("tests/fixtures/sample_photos/Japan 4-03/1-Tokyo/Senso-ji (Asakusa Kannon)")
    meta: DirectoryMetadata = extract_directory_metadata(folder)
    assert meta.latitude is not None
    assert meta.longitude is not None
    assert round(float(meta.latitude), 4) == 35.7148
    assert round(float(meta.longitude), 4) == 139.7967
    assert meta.earliest_date == "2024-05-20"


def test_extract_directory_metadata_oaxaca_earliest_date() -> None:
    """Verifies lowest/earliest date selection across multi-photo folder."""
    folder = Path("tests/fixtures/sample_photos/03 Oaxaca/Monte Alban")
    meta = extract_directory_metadata(folder)
    assert meta.earliest_date == "2022-11-08"
    assert "2022-11-08" in meta.all_dates
    assert "2022-11-10" in meta.all_dates


def test_read_only_preservation() -> None:
    """Verifies zero filesystem modifications during metadata extraction (REQ-SCR-027)."""
    folder = Path("tests/fixtures/sample_photos/Trip To India/01 Delhi/Red Fort")
    hash_before = _compute_dir_hash(folder)
    _ = extract_directory_metadata(folder)
    hash_after = _compute_dir_hash(folder)
    assert hash_before == hash_after


def test_metadata_helpers_coverage(tmp_path: Path) -> None:
    """Tests helper edge cases in metadata extractor."""
    assert _to_float(42) == 42.0
    assert _to_float(Fraction(3, 4)) == 0.75
    assert _to_float((10, 2)) == 5.0
    assert _to_float((10, 0)) == 0.0

    assert convert_gps_to_decimal("invalid", "N") is None
    assert convert_gps_to_decimal((1, 2), "N") is None

    assert _parse_coordinate_string("50.12345") == Decimal("50.1234500")
    assert _parse_coordinate_string("invalid_coords") is None

    assert _clean_date_str("") is None
    assert _clean_date_str("Not a date") is None

    empty_meta = extract_directory_metadata(tmp_path / "non_existent_folder")
    assert empty_meta.latitude is None
    assert empty_meta.earliest_date is None


def test_metadata_extractor_direct(tmp_path: Path) -> None:
    """Tests direct extraction methods for high branch coverage."""
    json_path = tmp_path / "photo.json"
    json_path.write_text(
        '{"photoTakenTime": {"formatted": "2023-08-15 12:00:00"}, "geoData": {"latitude": 40.7128, "longitude": -74.0060}, "title": "NYC"}',
        encoding="utf-8",
    )
    gps, date_val, tags = _parse_json_sidecar(json_path)
    assert gps is not None
    assert date_val == "2023-08-15"
    assert "NYC" in tags

    assert _clean_date_str("2024:01:01 10:00:00") == "2024-01-01"
    assert _clean_date_str("2024-02-02T15:30:00Z") == "2024-02-02"

    bad_xmp = tmp_path / "bad.xmp"
    bad_xmp.write_text("NOT XML", encoding="utf-8")
    assert parse_xmp_sidecar(bad_xmp) == (None, None, [])


def test_embedded_exif_gps_and_keywords(tmp_path: Path) -> None:
    """Verifies embedded EXIF GPS tag decoding and XPKeywords extraction."""
    im = Image.new("RGB", (50, 50))
    exif = im.getexif()
    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps_ifd[1] = "N"
    gps_ifd[2] = (37.7749, 0.0, 0.0)
    gps_ifd[3] = "W"
    gps_ifd[4] = (122.4194, 0.0, 0.0)
    exif[40094] = "Castle; History; Vacation\x00".encode("utf-16le")
    img_path = tmp_path / "exif_gps.jpg"
    im.save(img_path, exif=exif)

    gps, date_val, tags = _extract_exif_metadata(img_path)
    assert gps is not None
    assert round(float(gps[0]), 3) == 37.775
    assert round(float(gps[1]), 3) == -122.419
    assert "Castle" in tags
    assert "History" in tags


def test_metadata_extractor_coords_edge() -> None:
    assert convert_gps_to_decimal(35.5, "N") == Decimal("35.5000000")
    assert _parse_coordinate_string("28.65N") == Decimal("28.6500000")


def test_extract_directory_metadata_smart_early_exit(tmp_path: Path) -> None:
    """Verifies smart early exit once GPS and date are anchored to minimize NAS reads."""
    dir_path = tmp_path / "early_exit_test"
    dir_path.mkdir()

    # Photo 1 has GPS and date
    im1 = Image.new("RGB", (10, 10))
    ex1 = im1.getexif()
    gps_ifd = ex1.get_ifd(ExifTags.IFD.GPSInfo)
    gps_ifd[1] = "N"
    gps_ifd[2] = (35.0, 0.0, 0.0)
    gps_ifd[3] = "E"
    gps_ifd[4] = (139.0, 0.0, 0.0)
    ex1[306] = "2024:05:01 10:00:00"
    im1.save(dir_path / "img_01.jpg", exif=ex1)

    # Photo 2 has only date
    im2 = Image.new("RGB", (10, 10))
    ex2 = im2.getexif()
    ex2[306] = "2024:05:02 10:00:00"
    im2.save(dir_path / "img_02.jpg", exif=ex2)

    # With early_exit=True (default), stops after img_01.jpg
    meta_fast = extract_directory_metadata(dir_path, early_exit=True)
    assert meta_fast.latitude == Decimal("35.0000000")
    assert meta_fast.longitude == Decimal("139.0000000")
    assert meta_fast.all_dates == ["2024-05-01"]

    # With early_exit=False, continues through all photos
    meta_full = extract_directory_metadata(dir_path, early_exit=False)
    assert len(meta_full.all_dates) == 2


def test_extract_directory_metadata_max_photos_per_dir(tmp_path: Path) -> None:
    """Verifies bounded scan stops after max_photos_per_dir on non-GPS folders."""
    dir_path = tmp_path / "no_gps_test"
    dir_path.mkdir()

    for i in range(5):
        im = Image.new("RGB", (10, 10))
        ex = im.getexif()
        ex[306] = f"2024:05:0{i + 1} 10:00:00"
        im.save(dir_path / f"img_{i:02d}.jpg", exif=ex)

    # Stop after 2 photos without GPS
    meta = extract_directory_metadata(dir_path, early_exit=True, max_photos_per_dir=2)
    assert len(meta.all_dates) == 2


def test_find_sidecars(tmp_path: Path) -> None:
    """Verifies companion sidecar pattern discovery."""
    img = tmp_path / "photo.jpg"
    img.touch()
    xmp1 = tmp_path / "photo.jpg.xmp"
    xmp1.touch()
    xmp2 = tmp_path / "photo.xmp"
    xmp2.touch()
    found = _find_sidecars(img)
    assert xmp1 in found
    assert xmp2 in found


def test_extract_directory_metadata_unreadable_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifies graceful handling when directory listing fails with OSError."""
    d = tmp_path / "locked"
    d.mkdir()

    def fake_iterdir(self):
        raise PermissionError("Access denied")

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    res = extract_directory_metadata(d)
    assert res.earliest_date is None


def test_sidecars_first_early_exit(tmp_path: Path) -> None:
    """Verifies sidecars are read first and trigger early exit before any image reads."""
    dir_path = tmp_path / "sidecar_first"
    dir_path.mkdir()
    xmp = dir_path / "meta.xmp"
    xmp.write_text(
        """<?xml version="1.0"?>
        <x:xmpmeta xmlns:x="adobe:ns:meta/">
          <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:exif="http://ns.adobe.com/exif/1.0/">
            <rdf:Description exif:GPSLatitude="35.6895N" exif:GPSLongitude="139.6917E" exif:DateTimeOriginal="2024-06-01"/>
          </rdf:RDF>
        </x:xmpmeta>""",
        encoding="utf-8",
    )
    # Even if an image exists, sidecar is processed first and satisfies early exit
    im = Image.new("RGB", (10, 10))
    im.save(dir_path / "img.jpg")

    meta = extract_directory_metadata(dir_path, early_exit=True)
    assert meta.latitude == Decimal("35.6895000")
    assert meta.longitude == Decimal("139.6917000")
    assert meta.earliest_date == "2024-06-01"
