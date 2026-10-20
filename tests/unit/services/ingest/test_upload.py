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

"""Unit tests for CSV upload validation, sanitization, and error boundaries (T-010).

Verifies:
- File size limit (<= 2MB / 413 Payload Too Large)
- Data row limit (<= 2,000 / 422 Unprocessable Content)
- MIME type verification (415 Unsupported Media Type)
- Formula prefix neutralization (prepending ' to =, +, -, @, \\t, \\r)
- Raw HTML tag stripping
- Description field truncation to 4,000 characters
- Empty file, null byte, and missing header handling
"""

from __future__ import annotations

import pytest
from vistarae_core.domain.exceptions import (
    DomainError,
    FileTooLargeError,
    InvalidCSVHeaderError,
    InvalidMimeTypeError,
    RowLimitExceededError,
)

from services.ingest.services.csv_parser import (
    MAX_FILE_SIZE,
    MAX_ROWS,
    parse_and_sanitize_csv,
    sanitize_text_field,
)


class TestCSVSanitization:
    """Verifies cell-level text sanitization."""

    def test_formula_prefix_neutralization(self) -> None:
        """Asserts dangerous formula injection prefixes are neutralized with a prepended single quote."""
        assert sanitize_text_field("=1+1") == "'=1+1"
        assert sanitize_text_field("+1234567890") == "'+1234567890"
        assert sanitize_text_field("-5.00") == "'-5.00"
        assert sanitize_text_field("@SUM(A1:A10)") == "'@SUM(A1:A10)"
        assert sanitize_text_field("\tTabbedText") == "'\tTabbedText"
        assert sanitize_text_field("\rReturnText") == "'\rReturnText"

    def test_benign_text_unmodified(self) -> None:
        """Asserts benign text is left clean without unnecessary quotes."""
        assert sanitize_text_field("Yosemite National Park") == "Yosemite National Park"
        assert sanitize_text_field("Half Dome Trail, CA") == "Half Dome Trail, CA"

    def test_html_tag_stripping(self) -> None:
        """Asserts all raw HTML tags are stripped from user text."""
        raw = "<b>Grand Canyon</b> <script>alert(1)</script> <i>Overlook</i>"
        assert sanitize_text_field(raw) == "Grand Canyon alert(1) Overlook"


class TestCSVParserGuardrails:
    """Verifies file-level guardrails and error boundaries."""

    def test_valid_csv_parsing(self) -> None:
        """Parses a valid CSV with sanitization and preserves absolute row numbers."""
        csv_text = (
            "name,description,address,latitude,longitude\n"
            "Yosemite Valley,=Great view,Wawona Rd,37.715,-119.677\n"
            "Half Dome,<b>Granite peak</b>,Yosemite,37.746,-119.533\n"
        )
        rows = parse_and_sanitize_csv(csv_text.encode("utf-8"), content_type="text/csv")
        assert len(rows) == 2

        # Row 1 (line 2)
        assert rows[0]["absolute_row_number"] == 2
        assert rows[0]["row_data"]["name"] == "Yosemite Valley"
        assert rows[0]["row_data"]["description"] == "'=Great view"
        assert rows[0]["row_data"]["latitude"] == "37.715"

        # Row 2 (line 3)
        assert rows[1]["absolute_row_number"] == 3
        assert rows[1]["row_data"]["description"] == "Granite peak"

    def test_file_size_exceeded(self) -> None:
        """Asserts FileTooLargeError when payload exceeds 2MB limit."""
        huge_content = b"name\n" + b"A" * (MAX_FILE_SIZE + 10)
        with pytest.raises(FileTooLargeError) as exc_info:
            parse_and_sanitize_csv(huge_content, content_type="text/csv")
        assert exc_info.value.size > MAX_FILE_SIZE

    def test_row_limit_exceeded(self) -> None:
        """Asserts RowLimitExceededError when data rows exceed 2,000."""
        lines = ["name,description"]
        for i in range(MAX_ROWS + 5):
            lines.append(f"POI {i},Description {i}")
        csv_bytes = "\n".join(lines).encode("utf-8")

        with pytest.raises(RowLimitExceededError) as exc_info:
            parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
        assert exc_info.value.count > MAX_ROWS

    def test_invalid_mime_type(self) -> None:
        """Asserts InvalidMimeTypeError when content-type is unsupported."""
        with pytest.raises(InvalidMimeTypeError) as exc_info:
            parse_and_sanitize_csv(b"name\nTest", content_type="application/pdf")
        assert exc_info.value.mime_type == "application/pdf"

    def test_missing_mandatory_name_header(self) -> None:
        """Asserts InvalidCSVHeaderError when 'name' column is missing."""
        csv_bytes = b"title,description,latitude,longitude\nPlace,Desc,0.0,0.0"
        with pytest.raises(InvalidCSVHeaderError) as exc_info:
            parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
        assert "name" in exc_info.value.missing_headers

    def test_empty_file_rejected(self) -> None:
        """Asserts empty file raises DomainError."""
        with pytest.raises(DomainError, match="CSV file is empty"):
            parse_and_sanitize_csv(b"", content_type="text/csv")

    def test_null_bytes_rejected(self) -> None:
        """Asserts binary null byte in payload raises DomainError."""
        with pytest.raises(DomainError, match="binary null bytes"):
            parse_and_sanitize_csv(b"name,desc\x00\nTest", content_type="text/csv")

    def test_description_truncation(self) -> None:
        """Asserts descriptions longer than 4,000 characters are safely truncated."""
        long_desc = "X" * 5000
        csv_bytes = f"name,description\nTest Place,{long_desc}\n".encode()
        rows = parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
        assert len(rows) == 1
        assert len(rows[0]["row_data"]["description"]) == 4000

    def test_csv_empty_lines_and_whitespace(self) -> None:
        """Asserts empty lines and whitespace lines are cleanly ignored."""
        csv_bytes = b"name,description\n\n   \nTest Place,Clean desc\n\n"
        rows = parse_and_sanitize_csv(csv_bytes, content_type="text/csv")
        assert len(rows) == 1
        assert rows[0]["row_data"]["name"] == "Test Place"

    def test_trace_context_fallback_generation(self) -> None:
        """Asserts fallback traceparent and X-Amzn-Trace-Id are generated when headers missing."""
        from unittest.mock import MagicMock

        from services.ingest.routes.upload import _extract_or_generate_trace_context

        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        ctx = _extract_or_generate_trace_context(mock_request)
        assert "traceparent" in ctx
        assert ctx["traceparent"].startswith("00-")
        assert "X-Amzn-Trace-Id" in ctx
        assert ctx["X-Amzn-Trace-Id"].startswith("Root=1-")
