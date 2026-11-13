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

"""Unit tests for schema extensibility and unmapped column preservation (017-export T-020).

Validates:
- Unknown/extension columns captured under _unmapped_columns in raw_geocoding (FR-008)
- Zero data loss for non-schema attributes (SC-004)
- Preserving arbitrary external headers safely
"""

from __future__ import annotations

from services.ingest.services.csv_parser import parse_and_sanitize_csv


class TestSchemaExtensibility:
    """Test suite for extension columns and unmapped header preservation."""

    def test_unmapped_columns_captured_in_raw_geocoding(self) -> None:
        """Asserts columns not in schema registry are stored in raw_geocoding['_unmapped_columns']."""
        csv_content = (
            "POI Name,City,TicketPriceUSD,CustomTourGuideNotes,AccessibilityFlag\n"
            'Louvre Museum,Paris,22.00,"Requires timed entry ticket",WheelchairAccessible\n'
        )

        rows = parse_and_sanitize_csv(csv_content.encode("utf-8"))
        assert len(rows) == 1
        rd = rows[0]["row_data"]

        # Recognized canonical attributes
        assert rd["poi_name"] == "Louvre Museum"
        assert rd["city"] == "Paris"

        # Unmapped columns captured in raw_geocoding['_unmapped_columns']
        assert "raw_geocoding" in rd
        assert isinstance(rd["raw_geocoding"], dict)
        assert "_unmapped_columns" in rd["raw_geocoding"]
        unmapped = rd["raw_geocoding"]["_unmapped_columns"]

        assert unmapped["TicketPriceUSD"] == "22.00"
        assert unmapped["CustomTourGuideNotes"] == "Requires timed entry ticket"
        assert unmapped["AccessibilityFlag"] == "WheelchairAccessible"

    def test_empty_unmapped_columns_not_injected_when_all_headers_match(self) -> None:
        """Asserts pure canonical CSV does not create unwanted _unmapped_columns entries."""
        csv_content = (
            "POI Name,Street Address,City / Town,State / Province,Country\n"
            "Space Needle,400 Broad St,Seattle,Washington,United States\n"
        )

        rows = parse_and_sanitize_csv(csv_content.encode("utf-8"))
        assert len(rows) == 1
        rd = rows[0]["row_data"]
        assert rd["poi_name"] == "Space Needle"
        raw_geo = rd.get("raw_geocoding") or {}
        assert "_unmapped_columns" not in raw_geo
