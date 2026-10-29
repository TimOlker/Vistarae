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

"""Shared RFC 4180 CSV export service for standardized POI datasets (T-009).

Adheres to:
- REQ-SCR-035: 12 standardized CSV columns
- REQ-SCR-036: Tags column reserved / empty for photo scraper
- REQ-SCR-037: Semicolon alignment across multi-address lists
- REQ-SCR-038: Optional missing data represented as empty string
- REQ-SCR-039: Formula injection sanitization for =, +, -, @, \\t, \\r
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from vistarae_core.schemas.poi_export import POIExportRecord

CSV_HEADERS: list[str] = [
    "POI Name",
    "Street Address",
    "Town/City",
    "State/Province",
    "Zip Code",
    "Country",
    "Tags",
    "latitude",
    "longitude",
    "dates visited",
    "Photo directory",
    "location_confidence_percent",
]

_FORMULA_INJECTION_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str) -> str:
    """Neutralizes formula injection risk by prepending a single quote.

    Args:
        value: Raw text string to sanitize.

    Returns:
        Sanitized string with prepended single quote if matching injection prefixes.
    """
    if not value:
        return value
    if value.startswith(_FORMULA_INJECTION_PREFIXES):
        return f"'{value}"
    return value


def _join_and_sanitize(items: Sequence[str]) -> str:
    """Joins a sequence with semicolons and sanitizes the combined result.

    Args:
        items: List of string elements.

    Returns:
        Semicolon-joined and sanitized string.
    """
    if not items:
        return ""
    cleaned = [sanitize_csv_cell(item.strip(" ")) for item in items if item.strip(" ")]
    joined = "; ".join(cleaned)
    return sanitize_csv_cell(joined)


def generate_standard_poi_csv(records: Sequence[POIExportRecord]) -> str:
    """Generates an RFC 4180 compliant CSV string from POI export records.

    Args:
        records: Collection of POIExportRecord objects to format.

    Returns:
        Serialized CSV string containing the standardized 12-column header and rows.
    """
    output = io.StringIO()
    writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)

    for rec in records:
        lat_str = str(rec.latitude) if rec.latitude is not None else ""
        lon_str = str(rec.longitude) if rec.longitude is not None else ""
        conf_str = str(rec.location_confidence_percent)

        row = [
            sanitize_csv_cell(rec.poi_name),
            _join_and_sanitize(rec.street_address),
            _join_and_sanitize(rec.town_city),
            _join_and_sanitize(rec.state_province),
            _join_and_sanitize(rec.zip_code),
            _join_and_sanitize(rec.country),
            _join_and_sanitize(rec.tags),
            lat_str,
            lon_str,
            _join_and_sanitize(rec.dates_visited),
            sanitize_csv_cell(rec.photo_directory),
            conf_str,
        ]
        writer.writerow(row)

    return output.getvalue()
