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

"""Unit tests for CSV parser exemption column parsing and defaulting (T022).

Validates EARS requirements:
- REQ-EXM-023: Exporting POIs includes no_address and no_websites attributes.
- REQ-EXM-024: Importing CSV/JSON files maps no_address and no_websites columns into candidate attributes.
- REQ-EXM-025: Files lacking no_address or no_websites columns default both to false.
"""

from __future__ import annotations

from vistarae_core.schemas.export_schema import CANONICAL_EXPORT_FIELDS

from services.ingest.services.csv_parser import parse_and_sanitize_csv


def test_csv_parser_with_exemption_columns() -> None:
    """Tests that CSV files with explicit no_address and no_websites columns parse booleans accurately."""
    csv_content = (
        "POI Name,Street Address,No Address Flag,No Websites Flag,Latitude,Longitude\n"
        "Mount Rainier Peak,,true,yes,46.8523,-121.7603\n"
        "Space Needle,400 Broad St,false,0,47.6205,-122.3493\n"
    )
    result = parse_and_sanitize_csv(csv_content.encode("utf-8"))
    assert len(result) == 2

    # Row 1: Mount Rainier Peak (exempted)
    r1 = result[0]["row_data"]
    assert r1["poi_name"] == "Mount Rainier Peak"
    assert r1["no_address"] is True
    assert r1["no_websites"] is True

    # Row 2: Space Needle (not exempted)
    r2 = result[1]["row_data"]
    assert r2["poi_name"] == "Space Needle"
    assert r2["no_address"] is False
    assert r2["no_websites"] is False


def test_csv_parser_defaults_exemptions_to_false() -> None:
    """Tests that CSV files missing no_address and no_websites columns default both to False."""
    csv_content = (
        "POI Name,Street Address,City,Country\n"
        "Crater Lake,,Klamath Falls,USA\n"
    )
    result = parse_and_sanitize_csv(csv_content.encode("utf-8"))
    assert len(result) == 1

    r = result[0]["row_data"]
    assert r["poi_name"] == "Crater Lake"
    assert r["no_address"] is False
    assert r["no_websites"] is False


def test_canonical_export_fields_include_exemptions() -> None:
    """Tests that CANONICAL_EXPORT_FIELDS schema includes definitions for no_address and no_websites."""
    attr_keys = {f.attribute_key for f in CANONICAL_EXPORT_FIELDS}
    assert "no_address" in attr_keys
    assert "no_websites" in attr_keys

    no_addr_def = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "no_address")
    assert no_addr_def.default_value is False
    assert "no_address" in no_addr_def.aliases

    no_web_def = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "no_websites")
    assert no_web_def.default_value is False
    assert "no_websites" in no_web_def.aliases
