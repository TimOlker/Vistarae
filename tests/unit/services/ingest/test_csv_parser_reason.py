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

"""Unit tests for CSV parser mapping of reason_to_visit and why_visit headers (T-036 / REQ-CTX-033).

Verifies:
- Standard reason_to_visit column header is parsed and sanitized.
- Alias header why_visit is normalized and mapped to reason_to_visit key.
- Formula injection in reason_to_visit is neutralized with prepended single quote.
- Raw HTML tags in reason_to_visit are stripped.
- Values exceeding 4,000 characters are safely truncated.
"""

from __future__ import annotations

import pytest
from services.ingest.services.csv_parser import parse_and_sanitize_csv


class TestCSVParserReasonToVisit:
    """Tests mapping and sanitization of reason_to_visit column."""

    def test_parse_csv_with_reason_to_visit_column(self) -> None:
        """Asserts reason_to_visit column is parsed and sanitized into row_data."""
        csv_content = (
            "name,city,description,reason_to_visit\n"
            "Sunset Cliff,San Diego,Scenic ocean bluffs,Incredible sunset vantage point with ocean vistas.\n"
        ).encode("utf-8")

        rows = parse_and_sanitize_csv(csv_content, content_type="text/csv")
        assert len(rows) == 1
        row_data = rows[0]["row_data"]
        assert row_data["name"] == "Sunset Cliff"
        assert row_data["description"] == "Scenic ocean bluffs"
        assert row_data["reason_to_visit"] == "Incredible sunset vantage point with ocean vistas."

    def test_parse_csv_with_why_visit_alias_column(self) -> None:
        """Asserts why_visit alias header is normalized into reason_to_visit key."""
        csv_content = (
            "name,city,why_visit\n"
            "Old Town Bakery,Portland,Award-winning marionberry pastries and pour-over coffee.\n"
        ).encode("utf-8")

        rows = parse_and_sanitize_csv(csv_content, content_type="text/csv")
        assert len(rows) == 1
        row_data = rows[0]["row_data"]
        assert row_data["name"] == "Old Town Bakery"
        assert "why_visit" not in row_data
        assert row_data["reason_to_visit"] == "Award-winning marionberry pastries and pour-over coffee."

    def test_reason_to_visit_sanitization_and_truncation(self) -> None:
        """Asserts HTML stripping, formula neutralization, and 4,000 character truncation."""
        long_text = "Spectacular view! " * 300  # 5,400 chars
        csv_content = (
            "name,reason_to_visit\n"
            f'Lookout Peak,"<b>=HYPERLINK(evil)</b>{long_text}"\n'
        ).encode("utf-8")

        rows = parse_and_sanitize_csv(csv_content, content_type="text/csv")
        assert len(rows) == 1
        reason = rows[0]["row_data"]["reason_to_visit"]

        # HTML stripped
        assert "<b>" not in reason
        assert "</b>" not in reason

        # Formula neutralized
        assert reason.startswith("'=HYPERLINK")

        # Truncated to 4,000 chars
        assert len(reason) == 4000
