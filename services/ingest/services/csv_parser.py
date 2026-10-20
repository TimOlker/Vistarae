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

"""CSV file streaming parser and security sanitization module (T-015).

Enforces upload guardrails:
- File size <= 2MB (2,097,152 bytes) -> FileTooLargeError (RFC 7807 413)
- Data rows <= 2,000 -> RowLimitExceededError (RFC 7807 422)
- Allowed MIME types -> InvalidMimeTypeError (RFC 7807 415)
- Header validation -> InvalidCSVHeaderError (RFC 7807 422)
- Formula injection neutralization (prepending ' to =, +, -, @, \\t, \\r)
- Raw HTML tag stripping
- Description field truncation to 4,000 characters
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from vistarae_core.domain.exceptions import (
    DomainError,
    FileTooLargeError,
    InvalidCSVHeaderError,
    InvalidMimeTypeError,
    RowLimitExceededError,
)

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2,097,152 bytes
MAX_ROWS = 2000
ALLOWED_MIME_TYPES = {"text/csv", "text/plain", "application/vnd.ms-excel"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
HTML_TAG_REGEX = re.compile(r"<[^>]+>")


def sanitize_text_field(value: str) -> str:
    """Sanitizes a single text cell against formula injection and raw HTML.

    Args:
        value: Raw cell string.

    Returns:
        Sanitized string with HTML tags stripped and formula characters neutralized.
    """
    if not value:
        return ""

    # 1. Strip raw HTML tags
    cleaned = HTML_TAG_REGEX.sub("", value)

    # 2. Neutralize spreadsheet formula prefixes before stripping whitespace
    if cleaned and cleaned.startswith(FORMULA_PREFIXES):
        return f"'{cleaned}"

    return cleaned.strip()


def parse_and_sanitize_csv(  # noqa: C901
    file_bytes: bytes,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """Validates, parses, and sanitizes uploaded CSV content.

    Args:
        file_bytes: Raw binary content of the uploaded CSV.
        content_type: Optional MIME type from multipart header.

    Returns:
        List of dicts: [{'absolute_row_number': int, 'row_data': dict[str, str]}].

    Raises:
        FileTooLargeError: If size > 2MB.
        InvalidMimeTypeError: If content_type is provided and unsupported.
        DomainError: If file is empty or contains null bytes.
        InvalidCSVHeaderError: If mandatory column 'name' is missing.
        RowLimitExceededError: If data rows > 2,000.
    """
    # 1. Size guardrail
    size = len(file_bytes)
    if size > MAX_FILE_SIZE:
        raise FileTooLargeError(size=size, max_size=MAX_FILE_SIZE)

    # 2. MIME type verification
    if content_type:
        # Strip parameters like charset=utf-8
        base_mime = content_type.split(";")[0].strip().lower()
        if base_mime not in ALLOWED_MIME_TYPES:
            raise InvalidMimeTypeError(mime_type=base_mime, allowed=sorted(ALLOWED_MIME_TYPES))

    # 3. Empty file or binary null byte checks
    if size == 0:
        raise DomainError("CSV file is empty.")

    if b"\x00" in file_bytes:
        raise DomainError("CSV contains binary null bytes.")

    # 4. Decode text
    try:
        text_content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text_content = file_bytes.decode("latin-1")
        except Exception as exc:
            raise DomainError(f"Unable to decode CSV text: {exc}") from exc

    # 5. Parse CSV
    reader = csv.reader(io.StringIO(text_content))
    header_row: list[str] | None = None
    rows: list[dict[str, Any]] = []
    line_number = 0

    for raw_row in reader:
        line_number += 1
        if not raw_row or all(cell.strip() == "" for cell in raw_row):
            continue

        # Ignore comments
        if raw_row[0].strip().startswith("#"):
            continue

        if header_row is None:
            header_row = [h.strip().lower() for h in raw_row]
            if "name" not in header_row:
                raise InvalidCSVHeaderError(missing_headers=["name"])
            continue

        # Data row
        if len(rows) >= MAX_ROWS:
            raise RowLimitExceededError(count=len(rows) + 1, max_rows=MAX_ROWS)

        row_dict: dict[str, str] = {}
        for idx, col_name in enumerate(header_row):
            cell_val = raw_row[idx] if idx < len(raw_row) else ""
            sanitized = sanitize_text_field(cell_val)
            if col_name == "description" and len(sanitized) > 4000:
                sanitized = sanitized[:4000]
            row_dict[col_name] = sanitized

        rows.append(
            {
                "absolute_row_number": line_number,
                "row_data": row_dict,
            }
        )

    if header_row is None:
        raise DomainError("CSV file contains no headers.")

    return rows
