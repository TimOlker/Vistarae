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

"""Unit tests for shared RFC 4180 CSV exporter (T-009).

Validates:
- 12 standardized columns (REQ-SCR-035)
- Formula injection sanitization for =, +, -, @, \\t, \\r (REQ-SCR-039)
- Semicolon-aligned multi-address lists (REQ-SCR-037)
- Tags empty reservation for photo scraper (REQ-SCR-036)
- Optional missing data empty column handling (REQ-SCR-038)
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.services.csv_exporter import (
    CSV_HEADERS,
    generate_standard_poi_csv,
    sanitize_csv_cell,
)


def test_sanitize_csv_cell() -> None:
    """Verifies formula injection characters are neutralized with a leading single quote."""
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+100") == "'+100"
    assert sanitize_csv_cell("-200") == "'-200"
    assert sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_csv_cell("\tTabbed") == "'\tTabbed"
    assert sanitize_csv_cell("\rReturn") == "'\rReturn"
    assert sanitize_csv_cell("Normal Text") == "Normal Text"
    assert sanitize_csv_cell("") == ""


def test_generate_standard_poi_csv_headers_and_empty() -> None:
    """Verifies empty records list outputs exactly the 12 standardized column headers."""
    csv_str = generate_standard_poi_csv([])
    reader = csv.reader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0] == CSV_HEADERS
    assert len(CSV_HEADERS) == 12


def test_generate_standard_poi_csv_single_record() -> None:
    """Verifies single record serialization with coordinates, dates, and directory."""
    rec = POIExportRecord(
        poi_name="Senso-ji",
        street_address=["2-3-1 Asakusa"],
        town_city=["Taito City"],
        state_province=["Tokyo"],
        zip_code=["111-0032"],
        country=["Japan"],
        tags=[],
        latitude=Decimal("35.7148000"),
        longitude=Decimal("139.7967000"),
        dates_visited=["2024-05-20"],
        photo_directory="/photos/Japan/Tokyo/Senso-ji",
        location_confidence_percent=95,
    )
    csv_str = generate_standard_poi_csv([rec])
    reader = list(csv.reader(io.StringIO(csv_str)))
    assert len(reader) == 2
    row = reader[1]
    assert row[0] == "Senso-ji"
    assert row[1] == "2-3-1 Asakusa"
    assert row[2] == "Taito City"
    assert row[3] == "Tokyo"
    assert row[4] == "111-0032"
    assert row[5] == "Japan"
    assert row[6] == ""  # Tags empty
    assert row[7] == "35.7148000"
    assert row[8] == "139.7967000"
    assert row[9] == "2024-05-20"
    assert row[10] == "/photos/Japan/Tokyo/Senso-ji"
    assert row[11] == "95"


def test_generate_standard_poi_csv_multi_address_alignment() -> None:
    """Verifies semicolon alignment across multi-address records (REQ-SCR-037)."""
    rec = POIExportRecord(
        poi_name="Iguazu Falls",
        street_address=["Ruta 101", "BR-469"],
        town_city=["Puerto Iguazu", "Foz do Iguacu"],
        state_province=["Misiones", "Parana"],
        zip_code=["N3370", "85855-750"],
        country=["Argentina", "Brazil"],
        tags=[],
        latitude=Decimal("-25.6953000"),
        longitude=Decimal("-54.4367000"),
        dates_visited=["2023-01-10", "2023-01-11"],
        photo_directory="/photos/SouthAmerica/Iguazu",
        location_confidence_percent=90,
    )
    csv_str = generate_standard_poi_csv([rec])
    reader = list(csv.reader(io.StringIO(csv_str)))
    row = reader[1]
    assert row[1] == "Ruta 101; BR-469"
    assert row[2] == "Puerto Iguazu; Foz do Iguacu"
    assert row[3] == "Misiones; Parana"
    assert row[4] == "N3370; 85855-750"
    assert row[5] == "Argentina; Brazil"
    assert row[9] == "2023-01-10; 2023-01-11"


def test_generate_standard_poi_csv_formula_injection() -> None:
    """Verifies formula injection characters are neutralized across all string columns."""
    rec = POIExportRecord(
        poi_name="=CMD|' /C calc'!A0",
        street_address=["+123 Main St"],
        town_city=["-Minus Town"],
        state_province=["@State"],
        zip_code=["+99999"],
        country=["=MaliciousCountry"],
        tags=[],
        latitude=None,
        longitude=None,
        dates_visited=[],
        photo_directory="/photos/attack",
        location_confidence_percent=10,
    )
    csv_str = generate_standard_poi_csv([rec])
    reader = list(csv.reader(io.StringIO(csv_str)))
    row = reader[1]
    assert row[0].startswith("'=")
    assert row[1].startswith("'+")
    assert row[2].startswith("'-")
    assert row[3].startswith("'@")
    assert row[4].startswith("'+")
    assert row[5].startswith("'=")
    assert row[7] == ""  # None latitude
    assert row[8] == ""  # None longitude
    assert row[9] == ""  # Empty dates
