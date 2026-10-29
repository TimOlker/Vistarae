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

"""CSV file streaming parser and security sanitization module (T-015, T-027).

Enforces upload guardrails:
- File size <= 2MB (2,097,152 bytes) -> FileTooLargeError (RFC 7807 413)
- Data rows <= 2,000 -> RowLimitExceededError (RFC 7807 422)
- Allowed MIME types -> InvalidMimeTypeError (RFC 7807 415)
- Standardized POIExportRecord column headers & aliases
- Semicolon-delimited multi-address alignment
- Formula injection neutralization (prepending ' to =, +, -, @, \\t, \\r)
- Raw HTML tag stripping
- Description and reason_to_visit truncation to 4,000 characters
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

_COLUMN_MAPPINGS: dict[str, str] = {
    "poi name": "poi_name",
    "name": "poi_name",
    "street address": "street_address",
    "street_address": "street_address",
    "street": "street_address",
    "town/city": "city",
    "town_city": "city",
    "town": "city",
    "city": "city",
    "state/province": "state_province",
    "state_province": "state_province",
    "state": "state_province",
    "province": "state_province",
    "zip code": "postal_code",
    "zip_code": "postal_code",
    "zip": "postal_code",
    "postal code": "postal_code",
    "postal_code": "postal_code",
    "country": "country",
    "tags": "tags",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
    "lng": "longitude",
    "dates visited": "dates_visited",
    "dates_visited": "dates_visited",
    "photo directory": "photo_directory",
    "photo_directory": "photo_directory",
    "location_confidence_percent": "confidence_score",
    "confidence_score": "confidence_score",
    "confidence": "confidence_score",
    "description": "description",
    "reason_to_visit": "reason_to_visit",
    "why_visit": "reason_to_visit",
}


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


def _split_semicolons(val: str) -> list[str]:
    """Splits a semicolon-delimited string into non-empty stripped tokens."""
    if not val:
        return []
    return [item.strip() for item in val.split(";") if item.strip()]


def _build_aligned_addresses(
    raw_street: str,
    raw_city: str,
    raw_state: str,
    raw_zip: str,
    raw_country: str,
) -> list[dict[str, str | None]]:
    """Aligns semicolon-separated multi-element address parts into structured dicts."""
    streets = _split_semicolons(raw_street)
    cities = _split_semicolons(raw_city)
    states = _split_semicolons(raw_state)
    zips = _split_semicolons(raw_zip)
    countries = _split_semicolons(raw_country)

    max_len = max(len(streets), len(cities), len(states), len(zips), len(countries), 1)
    if not any([streets, cities, states, zips, countries]):
        return []

    addresses: list[dict[str, str | None]] = []
    for i in range(max_len):
        street = streets[i] if i < len(streets) else (streets[0] if len(streets) == 1 else None)
        city = cities[i] if i < len(cities) else (cities[0] if len(cities) == 1 else None)
        state = states[i] if i < len(states) else (states[0] if len(states) == 1 else None)
        postal = zips[i] if i < len(zips) else (zips[0] if len(zips) == 1 else None)
        country = countries[i] if i < len(countries) else (countries[0] if len(countries) == 1 else "Unknown")

        addresses.append(
            {
                "street": street,
                "city": city,
                "state_province": state,
                "postal_code": postal,
                "country": country or "Unknown",
            }
        )
    return addresses


def parse_and_sanitize_csv(  # noqa: C901
    file_bytes: bytes,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """Validates, parses, and sanitizes uploaded CSV content.

    Args:
        file_bytes: Raw binary content of the uploaded CSV.
        content_type: Optional MIME type from multipart header.

    Returns:
        List of dicts: [{'absolute_row_number': int, 'row_data': dict[str, Any]}].

    Raises:
        FileTooLargeError: If size > 2MB.
        InvalidMimeTypeError: If content_type is provided and unsupported.
        DomainError: If file is empty or contains null bytes.
        InvalidCSVHeaderError: If mandatory name/POI Name column is missing.
        RowLimitExceededError: If data rows > 2,000.
    """
    # 1. Size guardrail
    size = len(file_bytes)
    if size > MAX_FILE_SIZE:
        raise FileTooLargeError(size=size, max_size=MAX_FILE_SIZE)

    # 2. MIME type verification
    if content_type:
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
            name_aliases = {"name", "poi name", "poi_name"}
            if not any(alias in header_row for alias in name_aliases):
                raise InvalidCSVHeaderError(missing_headers=["name"])
            continue

        # Data row
        if len(rows) >= MAX_ROWS:
            raise RowLimitExceededError(count=len(rows) + 1, max_rows=MAX_ROWS)

        raw_dict: dict[str, str] = {}
        for idx, col_name in enumerate(header_row):
            cell_val = raw_row[idx] if idx < len(raw_row) else ""
            sanitized = sanitize_text_field(cell_val)
            target_key = _COLUMN_MAPPINGS.get(col_name, col_name)
            if (
                target_key in ("description", "reason_to_visit")
                and len(sanitized) > 4000
            ):
                sanitized = sanitized[:4000]
            raw_dict[target_key] = sanitized

        # Extract normalized POI name
        poi_name = raw_dict.get("poi_name") or raw_dict.get("name", "")

        # Extract coordinates
        lat_val: float | None = None
        lon_val: float | None = None
        if raw_dict.get("latitude"):
            try:
                lat_val = float(raw_dict["latitude"])
            except ValueError:
                pass
        if raw_dict.get("longitude"):
            try:
                lon_val = float(raw_dict["longitude"])
            except ValueError:
                pass

        # Parse confidence score
        conf_val = 0
        if raw_dict.get("confidence_score"):
            try:
                conf_val = int(raw_dict["confidence_score"])
            except ValueError:
                pass

        # Build aligned addresses
        addrs = _build_aligned_addresses(
            raw_street=raw_dict.get("street_address", ""),
            raw_city=raw_dict.get("city", ""),
            raw_state=raw_dict.get("state_province", ""),
            raw_zip=raw_dict.get("postal_code", ""),
            raw_country=raw_dict.get("country", ""),
        )

        # Dates visited
        dates_list = _split_semicolons(raw_dict.get("dates_visited", ""))

        # Tags
        tags_list = _split_semicolons(raw_dict.get("tags", ""))

        # Assemble row_data maintaining backward compatibility with legacy consumers
        row_data: dict[str, Any] = {
            "name": poi_name,
            "poi_name": poi_name,
            "street_address": raw_dict.get("street_address", ""),
            "city": raw_dict.get("city", ""),
            "state_province": raw_dict.get("state_province", ""),
            "postal_code": raw_dict.get("postal_code", ""),
            "country": raw_dict.get("country", ""),
            "addresses": addrs,
            "dates_visited": dates_list,
            "photo_directory": raw_dict.get("photo_directory", ""),
            "confidence_score": conf_val,
            "latitude": raw_dict.get("latitude", ""),
            "longitude": raw_dict.get("longitude", ""),
            "tags": tags_list,
            "description": raw_dict.get("description", ""),
            "reason_to_visit": raw_dict.get("reason_to_visit", ""),
        }
        # Copy any extra columns
        for k, v in raw_dict.items():
            if k not in row_data:
                row_data[k] = v

        rows.append(
            {
                "absolute_row_number": line_number,
                "row_data": row_data,
            }
        )

    if header_row is None:
        raise DomainError("CSV file contains no headers.")

    return rows
