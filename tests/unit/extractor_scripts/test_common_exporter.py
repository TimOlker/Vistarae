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

"""Unit tests for the RFC 4180 CSV exporter and formula injection defense."""

import csv
import json
from pathlib import Path

from vistarae_core.schemas.extractor import (
    CSV_HEADERS,
    AdditionalAddressRecord,
    ExtractorRecord,
    WebsiteRecord,
    neutralize_formula_injection,
)

from extractor_scripts.common.exporter import CSVExporter


def test_neutralize_formula_injection() -> None:
    """Verifies that formulas and control characters are prefixed with a single quote."""
    assert neutralize_formula_injection("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert neutralize_formula_injection("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert neutralize_formula_injection("-123.45") == "'-123.45"
    assert neutralize_formula_injection("@special") == "'@special"
    assert neutralize_formula_injection("\talert") == "'\talert"
    assert neutralize_formula_injection("\ralert") == "'\ralert"
    assert neutralize_formula_injection("Grand Canyon") == "Grand Canyon"
    assert neutralize_formula_injection("") == ""


def test_serialize_record_json_columns_and_neutralization() -> None:
    """Verifies JSON column serialization and formula protection on fields."""
    rec = ExtractorRecord(
        poi_name="=Dangerous POI",
        street_address="100 Main St",
        town_city="Anytown",
        state_province="CA",
        zip_code="90210",
        country="United States",
        country_code="US",
        latitude=34.0522,
        longitude=-118.2437,
        tags=["NPS", "National Park"],
        websites=[
            WebsiteRecord(name="Official", url="https://example.gov/park"),
            WebsiteRecord(name="Wikipedia", url="https://en.wikipedia.org/wiki/Park"),
        ],
        additional_addresses=[
            AdditionalAddressRecord(
                street_address="200 North Outpost",
                town_city="Anytown",
                state_province="CA",
                latitude=34.1000,
                longitude=-118.2000,
            )
        ],
        description="A spectacular view of the mountains.",
        reason_to_visit="Scenic hiking trails.",
    )

    serialized = CSVExporter.serialize_record(rec)

    # Formula neutralization check
    assert serialized["POI Name"] == "'=Dangerous POI"
    assert serialized["Country Code"] == "US"
    assert serialized["latitude"] == "34.0522"
    assert serialized["longitude"] == "-118.2437"
    assert serialized["Tags"] == "NPS; National Park"

    # Websites JSON column check
    assert serialized["Websites"].startswith("[")
    websites_data = json.loads(serialized["Websites"])
    assert len(websites_data) == 2
    assert websites_data[0]["name"] == "Official"
    assert websites_data[0]["url"] == "https://example.gov/park"

    # Additional Address JSON column check
    assert serialized["Additional Address"].startswith("[")
    addrs_data = json.loads(serialized["Additional Address"])
    assert len(addrs_data) == 1
    assert addrs_data[0]["street_address"] == "200 North Outpost"
    assert addrs_data[0]["latitude"] == "34.1"


def test_export_empty_and_single_file(tmp_path: Path) -> None:
    """Verifies export when records are empty or below split threshold."""
    out_file = tmp_path / "test_output.csv"

    # Empty export creates header only
    generated = CSVExporter.export([], out_file, split_size=2000)
    assert len(generated) == 1
    assert generated[0] == out_file

    with out_file.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == CSV_HEADERS
        # No rows
        assert list(reader) == []

    # Single batch export
    rec = ExtractorRecord(poi_name="Lone Star Peak", country="United States")
    generated = CSVExporter.export([rec], out_file, split_size=2000)
    assert len(generated) == 1
    with out_file.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["POI Name"] == "Lone Star Peak"


def test_export_partitioning(tmp_path: Path) -> None:
    """Verifies automatic 2000-row (or custom split) partitioning."""
    out_file = tmp_path / "batch.csv"
    records = [ExtractorRecord(poi_name=f"Site #{i}", country="United States") for i in range(5)]

    # Split with split_size=2 should yield 3 files: part1 (2), part2 (2), part3 (1)
    files = CSVExporter.export(records, out_file, split_size=2)
    assert len(files) == 3
    assert files[0].name == "batch_part1.csv"
    assert files[1].name == "batch_part2.csv"
    assert files[2].name == "batch_part3.csv"

    # Verify content in each part
    for idx, expected_count in enumerate([2, 2, 1], start=1):
        p = tmp_path / f"batch_part{idx}.csv"
        assert p.exists()
        with p.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert len(list(reader)) == expected_count
