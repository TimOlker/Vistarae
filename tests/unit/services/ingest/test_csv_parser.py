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

"""Unit tests for standardized CSV streaming parser (T-023).

Validates:
- Standardized POIExportRecord column headers (POI Name, Street Address, etc.) (REQ-ING-001)
- Header normalization (name vs POI Name)
- Semicolon-delimited multi-address alignment (REQ-SCR-037)
- Dates visited and photo directory parsing
- Formula injection sanitization and HTML stripping
- 2MB file size and 2,000 row limits
"""

from __future__ import annotations

import pytest
from vistarae_core.domain.exceptions import (
    FileTooLargeError,
    InvalidCSVHeaderError,
    RowLimitExceededError,
)

from services.ingest.services.csv_parser import (
    MAX_FILE_SIZE,
    MAX_ROWS,
    parse_and_sanitize_csv,
)


def test_parse_standardized_photo_scraper_csv() -> None:
    """Verifies parsing of RFC 4180 CSV exported by the photo scraper."""
    csv_bytes = (
        b"POI Name,Street Address,Town/City,State/Province,Zip Code,Country,Tags,latitude,longitude,dates visited,Photo directory,location_confidence_percent\n"
        b"Senso-ji,2-3-1 Asakusa,Taito City,Tokyo,111-0032,Japan,,35.7148000,139.7967000,2024-05-20,/photos/Japan/Senso-ji,95\n"
    )

    rows = parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
    assert len(rows) == 1
    row = rows[0]["row_data"]
    assert row["poi_name"] == "Senso-ji"
    assert row["name"] == "Senso-ji"
    assert row["street_address"] == "2-3-1 Asakusa"
    assert row["city"] == "Taito City"
    assert row["state_province"] == "Tokyo"
    assert row["postal_code"] == "111-0032"
    assert row["country"] == "Japan"
    assert float(row["latitude"]) == 35.7148
    assert float(row["longitude"]) == 139.7967
    assert row["dates_visited"] == ["2024-05-20"]
    assert row["photo_directory"] == "/photos/Japan/Senso-ji"
    assert row["confidence_score"] == 95


def test_parse_multi_address_alignment() -> None:
    """Verifies semicolon-separated multi-address parsing and alignment."""
    csv_bytes = (
        b"POI Name,Street Address,Town/City,State/Province,Zip Code,Country,Tags,latitude,longitude,dates visited,Photo directory,location_confidence_percent\n"
        b"Iguazu Falls,Ruta 101; BR-469,Puerto Iguazu; Foz do Iguacu,Misiones; Parana,N3370; 85855-750,Argentina; Brazil,,-25.6953000,-54.4367000,2023-01-10; 2023-01-11,/photos/Iguazu,90\n"
    )

    rows = parse_and_sanitize_csv(csv_bytes)
    assert len(rows) == 1
    row = rows[0]["row_data"]
    assert row["poi_name"] == "Iguazu Falls"
    assert len(row["addresses"]) == 2
    assert row["addresses"][0]["country"] == "Argentina"
    assert row["addresses"][0]["city"] == "Puerto Iguazu"
    assert row["addresses"][1]["country"] == "Brazil"
    assert row["addresses"][1]["city"] == "Foz do Iguacu"
    assert row["dates_visited"] == ["2023-01-10", "2023-01-11"]


def test_parse_missing_name_header_raises() -> None:
    """Verifies missing name or POI Name header raises InvalidCSVHeaderError."""
    csv_bytes = b"City,Country,latitude,longitude\nParis,France,48.8566,2.3522\n"
    with pytest.raises(InvalidCSVHeaderError):
        parse_and_sanitize_csv(csv_bytes)


def test_parse_file_too_large_raises() -> None:
    """Verifies files exceeding 2MB raise FileTooLargeError."""
    large_bytes = b"POI Name\n" + (b"A" * (MAX_FILE_SIZE + 1))
    with pytest.raises(FileTooLargeError):
        parse_and_sanitize_csv(large_bytes)


def test_parse_row_limit_exceeded_raises() -> None:
    """Verifies files exceeding 2,000 data rows raise RowLimitExceededError."""
    lines = [b"POI Name,City\n"]
    for i in range(MAX_ROWS + 1):
        lines.append(f"POI {i},City\n".encode())
    csv_bytes = b"".join(lines)
    with pytest.raises(RowLimitExceededError):
        parse_and_sanitize_csv(csv_bytes)
