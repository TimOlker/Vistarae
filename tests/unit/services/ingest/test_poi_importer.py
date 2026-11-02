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

"""Unit tests for POI multi-format ingestion, alias resolution, and type pre-validation."""

from __future__ import annotations

from vistarae_core.services.poi_importer import (
    ALIAS_DICTIONARY,
    POIImporter,
)


def test_alias_dictionary_contains_standard_aliases():
    """Verifies that canonical alias dictionary covers latitude, longitude, and POI name variants."""
    assert ALIAS_DICTIONARY["lat"] == "latitude"
    assert ALIAS_DICTIONARY["lng"] == "longitude"
    assert ALIAS_DICTIONARY["lon"] == "longitude"
    assert ALIAS_DICTIONARY["x"] == "longitude"
    assert ALIAS_DICTIONARY["y"] == "latitude"
    assert ALIAS_DICTIONARY["place"] == "poi_name"
    assert ALIAS_DICTIONARY["waypoint"] == "poi_name"
    assert ALIAS_DICTIONARY["categories"] == "tags"
    assert ALIAS_DICTIONARY["desc"] == "ai_description"


def test_sniff_and_parse_csv_with_utf8_bom():
    """Asserts that CSV with UTF-8 BOM parses cleanly without leaving BOM artifacts in headers."""
    csv_bytes = b"\xef\xbb\xbfplace,lat,lng\r\nKyoto Tower,34.9875,135.7594\r\n"
    records, unmapped, issues = POIImporter.parse_file_bytes(
        content=csv_bytes,
        filename="trip.csv",
    )
    assert len(unmapped) == 0
    assert len(issues) == 0
    assert len(records) == 1
    assert records[0].poi_name == "Kyoto Tower"
    assert records[0].latitude == 34.9875
    assert records[0].longitude == 135.7594


def test_sniff_and_parse_json():
    """Asserts that JSON content is parsed into POIExchangeRecord items."""
    json_bytes = b"""[
      {
        "name": "Eiffel Tower",
        "latitude": 48.8584,
        "longitude": 2.2945,
        "tags": ["Monument", "Historic"]
      }
    ]"""
    records, unmapped, issues = POIImporter.parse_file_bytes(
        content=json_bytes,
        filename="paris.json",
    )
    assert len(unmapped) == 0
    assert len(issues) == 0
    assert len(records) == 1
    assert records[0].poi_name == "Eiffel Tower"
    assert records[0].tags == ["Monument", "Historic"]


def test_sniff_and_parse_yaml():
    """Asserts that YAML content parses cleanly."""
    yaml_bytes = b"""
- title: Matterhorn
  lat: 45.9765
  lon: 7.6585
  country: Switzerland
"""
    records, unmapped, issues = POIImporter.parse_file_bytes(
        content=yaml_bytes,
        filename="alps.yaml",
    )
    assert len(unmapped) == 0
    assert len(issues) == 0
    assert len(records) == 1
    assert records[0].poi_name == "Matterhorn"
    assert records[0].latitude == 45.9765
    assert records[0].country == "Switzerland"


def test_unmapped_columns_detected_with_samples():
    """Asserts that non-standard unrecognized columns are detected and return 3-row samples."""
    csv_bytes = (
        b"Waypoint,CustomNote,lat,lng\r\n"
        b"Point A,Note 1,10.0,20.0\r\n"
        b"Point B,Note 2,11.0,21.0\r\n"
        b"Point C,Note 3,12.0,22.0\r\n"
        b"Point D,Note 4,13.0,23.0\r\n"
    )
    # CustomNote is not in ALIAS_DICTIONARY; Waypoint is in ALIAS_DICTIONARY (poi_name)
    raw_headers, unmapped, samples = POIImporter.inspect_headers_and_samples(
        content=csv_bytes,
        filename="test.csv",
    )
    assert "CustomNote" in unmapped
    assert len(samples["CustomNote"]) == 3
    assert samples["CustomNote"] == ["Note 1", "Note 2", "Note 3"]


def test_pre_import_validation_identifies_invalid_coordinates():
    """Asserts that non-numeric or out-of-range coordinates are flagged as validation issues."""
    csv_bytes = (
        b"name,lat,lng\r\n"
        b"Valid POI,35.0,139.0\r\n"
        b"Invalid Row,true,139.0\r\n"
        b"Out of range,150.0,139.0\r\n"
    )
    records, unmapped, issues = POIImporter.parse_file_bytes(
        content=csv_bytes,
        filename="test.csv",
        skip_invalid_rows=False,
    )
    assert len(issues) == 2
    assert issues[0].row_number == 3  # Header is row 1, Valid POI is row 2, Invalid Row is row 3
    assert issues[0].column == "latitude"
    assert issues[0].raw_value == "true"
    assert "expected numeric latitude between -90 and 90" in issues[0].expected.lower()

    assert issues[1].row_number == 4
    assert issues[1].column == "latitude"
    assert issues[1].raw_value == "150.0"


def test_pre_import_validation_skip_invalid_rows():
    """Asserts that with skip_invalid_rows=True, invalid rows are skipped and valid rows preserved."""
    csv_bytes = (
        b"name,lat,lng\r\nValid 1,35.0,139.0\r\nInvalid 1,abc,139.0\r\nValid 2,36.0,140.0\r\n"
    )
    records, unmapped, issues = POIImporter.parse_file_bytes(
        content=csv_bytes,
        filename="test.csv",
        skip_invalid_rows=True,
    )
    assert len(issues) == 1
    assert len(records) == 2
    assert records[0].poi_name == "Valid 1"
    assert records[1].poi_name == "Valid 2"
