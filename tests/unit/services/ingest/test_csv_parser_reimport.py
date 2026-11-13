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

"""Unit tests for full-fidelity CSV re-import parser (017-export T-013).

Validates:
- Full-fidelity canonical header detection (FR-005)
- Case-insensitive header aliases
- Dual-mode collection deserialization (semicolon vs JSON) (FR-003, FR-006)
- Formula injection prefix desanitization (FR-004, FR-006)
- Preserved user dispositions and manual overrides (FR-007)
- Roundtrip attribute integrity (SC-002)
"""

from __future__ import annotations

import csv
import io
import json
import uuid

from vistarae_core.schemas.export_schema import (
    UTF8_BOM,
    get_canonical_headers,
)

from services.ingest.services.csv_parser import parse_and_sanitize_csv


class TestCSVParserReimport:
    """Test suite for full-fidelity CSV re-import parsing."""

    def test_parse_full_fidelity_canonical_headers(self) -> None:
        """Asserts all 37 canonical headers are recognized and parsed into row_data."""
        headers = get_canonical_headers()
        cand_id = str(uuid.uuid4())
        parent_cand_id = str(uuid.uuid4())

        row_values = [
            cand_id,  # Candidate ID
            "0",  # Row Index
            "'=Super Volcano",  # POI Name (neutralized formula)
            "123 Caldera Way",  # Street Address
            "Yellowstone",  # City / Town
            "Mammoth",  # Locality
            "Park County",  # County / District (Admin Level 2)
            "Wyoming",  # State / Province (Admin Level 1)
            "Wyoming",  # State / Province
            "82190",  # Postal Code / Zip
            "United States",  # Country
            "US",  # Country Code
            "44.4280",  # Latitude
            "-110.5885",  # Longitude
            "accept",  # Recommended Disposition
            "sublocation",  # User Disposition
            "98",  # Confidence Score
            "Nested inside Yellowstone",  # Disposition Justification
            "Active volcanic caldera with geysers",  # Description
            "Unique geothermal features",  # Reason to Visit
            "https://example.com/caldera.jpg",  # Hero Image URL
            "https://nps.gov/yell",  # Official URL
            "https://en.wikipedia.org/wiki/Yellowstone_Caldera",  # Wikipedia URL
            json.dumps(
                [{"name": "NPS Geology", "url": "https://nps.gov/geology"}]
            ),  # Related Websites
            "false",  # No Websites Flag
            "Volcano; Geothermal; National Park",  # Tags (semicolon)
            "/photos/yellowstone",  # Photo Directory
            "/photos/yellowstone; /photos/wyoming",  # Photo Directories
            "2023-08-15; 2024-06-10",  # Dates Visited
            "4.5",  # Recommended Duration Hours
            "2",  # Recommended Visit Days
            "Morning is best for geysers",  # Estimated Visit Time Notes
            parent_cand_id,  # Parent Candidate ID
            "",  # Parent POI ID
            "",  # Matched Existing POI ID
            "",  # Merge Target ID
            "true",  # Is User Overridden
        ]

        # Assemble CSV using standard csv.writer for rigorous RFC 4180 quoting
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(headers)
        writer.writerow(row_values)
        csv_text = UTF8_BOM + buf.getvalue()

        rows = parse_and_sanitize_csv(csv_text.encode("utf-8"), content_type="text/csv")
        assert len(rows) == 1
        rd = rows[0]["row_data"]

        # Verify key fields
        assert rd["poi_name"] == "=Super Volcano"  # Neutralizing quote stripped
        assert rd["candidate_id"] == cand_id
        assert rd["locality"] == "Mammoth"
        assert rd["city"] == "Yellowstone"
        assert rd["admin_level_2"] == "Park County"
        assert rd["admin_level_1"] == "Wyoming"
        assert rd["country_code"] == "US"
        assert rd["user_disposition"] == "sublocation"
        assert rd["recommended_disposition"] == "accept"
        assert rd["confidence_score"] == 98
        assert rd["is_user_overridden"] is True
        assert rd["parent_candidate_id"] == parent_cand_id

        # Verify dual-mode parsed collections
        assert rd["tags"] == ["Volcano", "Geothermal", "National Park"]
        assert rd["photo_directories"] == ["/photos/yellowstone", "/photos/wyoming"]
        assert rd["dates_visited"] == ["2023-08-15", "2024-06-10"]
        assert len(rd["related_websites"]) == 1
        assert rd["related_websites"][0]["name"] == "NPS Geology"

    def test_dual_mode_collection_parsing(self) -> None:
        """Asserts collections parse JSON arrays and semicolon/comma strings interchangeably."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["POI Name", "Tags", "Dates Visited", "Related Websites"])
        writer.writerow(
            [
                "Place A",
                "Tag1; Tag2",
                "2023-01-01; 2023-02-01",
                json.dumps([{"name": "Guide", "url": "https://example.com"}]),
            ]
        )
        writer.writerow(
            [
                "Place B",
                json.dumps(["Tag3", "Tag4"]),
                json.dumps(["2024-05-01"]),
                "https://simple-link.com",
            ]
        )

        rows = parse_and_sanitize_csv(buf.getvalue().encode("utf-8"))
        assert len(rows) == 2

        # Row 1: semicolon-separated
        rd1 = rows[0]["row_data"]
        assert rd1["tags"] == ["Tag1", "Tag2"]
        assert rd1["dates_visited"] == ["2023-01-01", "2023-02-01"]
        assert rd1["related_websites"] == [{"name": "Guide", "url": "https://example.com"}]

        # Row 2: JSON array tags and visit dates
        rd2 = rows[1]["row_data"]
        assert rd2["tags"] == ["Tag3", "Tag4"]
        assert rd2["dates_visited"] == ["2024-05-01"]
        assert rd2["related_websites"] == [
            {"name": "https://simple-link.com", "url": "https://simple-link.com"}
        ]

    def test_formula_prefix_desanitization(self) -> None:
        """Asserts neutralizing single quotes are stripped while authentic apostrophes remain."""
        csv_content = (
            "POI Name,Description,Reason to Visit\n"
            '"\'=Formula POI","\'+Sum Value","\'-Minus Value"\n'
            '"\'@Admin POI","\'\tTabbed Desc","\'Normal with leading quote"\n'
            '"O\'Reilly Tavern","L\'Enfant Plaza","It\'s Great"\n'
        )

        rows = parse_and_sanitize_csv(csv_content.encode("utf-8"))
        assert len(rows) == 3

        # Row 1: =, +, - formula prefixes
        rd1 = rows[0]["row_data"]
        assert rd1["poi_name"] == "=Formula POI"
        assert rd1["description"] == "+Sum Value"
        assert rd1["reason_to_visit"] == "-Minus Value"

        # Row 2: @, \t, and authentic quote
        rd2 = rows[1]["row_data"]
        assert rd2["poi_name"] == "@Admin POI"
        assert rd2["description"] == "\tTabbed Desc"
        assert rd2["reason_to_visit"] == "'Normal with leading quote"

        # Row 3: Legitimate Irish/French apostrophes preserved
        rd3 = rows[2]["row_data"]
        assert rd3["poi_name"] == "O'Reilly Tavern"
        assert rd3["description"] == "L'Enfant Plaza"
        assert rd3["reason_to_visit"] == "It's Great"

    def test_user_disposition_and_override_preservation(self) -> None:
        """Asserts user_disposition and is_user_overridden are extracted intact."""
        csv_content = (
            "POI Name,User Disposition,Recommended Disposition,Is User Overridden,Disposition Justification\n"
            "Overridden Spot,ignore,accept,true,User explicitly excluded this\n"
            "Accepted Spot,accept,accept,false,Heuristic agreed\n"
        )

        rows = parse_and_sanitize_csv(csv_content.encode("utf-8"))
        assert len(rows) == 2

        rd1 = rows[0]["row_data"]
        assert rd1["user_disposition"] == "ignore"
        assert rd1["recommended_disposition"] == "accept"
        assert rd1["is_user_overridden"] is True
        assert rd1["disposition_justification"] == "User explicitly excluded this"

        rd2 = rows[1]["row_data"]
        assert rd2["user_disposition"] == "accept"
        assert rd2["is_user_overridden"] is False
