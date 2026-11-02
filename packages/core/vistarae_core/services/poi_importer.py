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

"""Multi-format POI ingestion parser, canonical header alias resolution, and type pre-validation (T-017)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel, Field

from vistarae_core.schemas.poi_exchange import POIExchangeRecord

ALIAS_DICTIONARY: dict[str, str] = {
    # Coordinates
    "lat": "latitude",
    "y": "latitude",
    "latitude": "latitude",
    "lat_wgs84": "latitude",
    "lon": "longitude",
    "lng": "longitude",
    "long": "longitude",
    "x": "longitude",
    "longitude": "longitude",
    "lon_wgs84": "longitude",
    # Name & Identifiers
    "name": "poi_name",
    "title": "poi_name",
    "place": "poi_name",
    "poi": "poi_name",
    "poi_name": "poi_name",
    "waypoint": "poi_name",
    "id": "poi_id",
    "poi_id": "poi_id",
    # Address & Administrative
    "address": "street_address",
    "street": "street_address",
    "addr": "street_address",
    "street_address": "street_address",
    "town": "city",
    "locality": "city",
    "city": "city",
    "municipality": "city",
    "state": "state_province",
    "province": "state_province",
    "region": "state_province",
    "state_province": "state_province",
    "zip": "postal_code",
    "zipcode": "postal_code",
    "postal_code": "postal_code",
    "postcode": "postal_code",
    "nation": "country",
    "country": "country",
    # Tags & Categories
    "tag": "tags",
    "categories": "tags",
    "keywords": "tags",
    "labels": "tags",
    "tags": "tags",
    # AI Enrichment & Descriptions
    "description": "ai_description",
    "desc": "ai_description",
    "notes": "ai_description",
    "summary": "ai_description",
    "ai_description": "ai_description",
    "why_visit": "reason_to_visit",
    "reason_to_visit": "reason_to_visit",
    # Dates & Metadata
    "visit_date": "dates_visited",
    "date_visited": "dates_visited",
    "dates_visited": "dates_visited",
    "dates": "dates_visited",
    "photo_directory": "photo_directory",
    "created_at": "created_at",
    "official_website": "official_website",
    "website": "official_website",
    "url": "official_website",
    "wikipedia_url": "wikipedia_url",
    "wiki_url": "wikipedia_url",
    "hero_image_url": "hero_image_url",
    "image_url": "hero_image_url",
    "recommended_duration_hours": "recommended_duration_hours",
    "duration_hours": "recommended_duration_hours",
    "itinerary_days": "itinerary_days",
    "user_disposition": "user_disposition",
    "rejection_reason": "rejection_reason",
    "location_confidence_percent": "location_confidence_percent",
}


class ValidationIssue(BaseModel):
    """Represents a discrete row-level type or boundary validation failure."""

    row_number: int = Field(description="1-indexed row number in the uploaded dataset.")
    column: str = Field(description="Target or source column name failing validation.")
    raw_value: str = Field(description="Raw string value detected in the cell.")
    expected: str = Field(description="Human-readable description of expected type or range.")


class POIImporter:
    """Flexible multi-format parser with alias resolution, column mapping, and type pre-validation."""

    @classmethod
    def sniff_format(cls, filename: str, content: bytes) -> str:
        """Determines file format based on extension and byte signature."""
        lower_name = filename.lower()
        if lower_name.endswith(".json"):
            return "json"
        if lower_name.endswith((".yaml", ".yml")):
            return "yaml"
        # Content sniffing fallback
        stripped = content.lstrip(b"\xef\xbb\xbf \t\r\n")
        if stripped.startswith(b"[") or stripped.startswith(b"{"):
            return "json"
        return "csv"

    @classmethod
    def load_raw_rows(cls, content: bytes, filename: str) -> list[dict[str, Any]]:
        """Parses raw byte content into a uniform list of dictionary rows."""
        fmt = cls.sniff_format(filename, content)

        if fmt == "json":
            text = content.decode("utf-8-sig")
            data = json.loads(text)
            if isinstance(data, list):
                return [dict(item) for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                # Wrapped list or single item
                items = data.get("pois") or data.get("records") or [data]
                return [dict(item) for item in items if isinstance(item, dict)]
            return []

        if fmt == "yaml":
            text = content.decode("utf-8-sig")
            data = yaml.safe_load(text)
            if isinstance(data, list):
                return [dict(item) for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                items = data.get("pois") or data.get("records") or [data]
                return [dict(item) for item in items if isinstance(item, dict)]
            return []

        # Default CSV with utf-8-sig (automatically strips BOM if present)
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict[str, Any]] = []
        for r in reader:
            # Strip whitespace and quotes from keys and string values
            cleaned_row = {
                (k.strip() if k else ""): (v.strip() if isinstance(v, str) else v)
                for k, v in r.items()
                if k is not None
            }
            rows.append(cleaned_row)
        return rows

    @classmethod
    def inspect_headers_and_samples(
        cls,
        content: bytes,
        filename: str,
        column_mappings: dict[str, str] | None = None,
    ) -> tuple[list[str], list[str], dict[str, list[str]]]:
        """Inspects uploaded file headers, finds unmapped columns, and extracts 3 sample row values."""
        raw_rows = cls.load_raw_rows(content, filename)
        if not raw_rows:
            return [], [], {}

        raw_headers = list(raw_rows[0].keys())
        mappings = column_mappings or {}
        unmapped: list[str] = []
        samples: dict[str, list[str]] = {}

        for h in raw_headers:
            if not h:
                continue
            norm = h.strip().lower()
            # If user explicitly provided mapping or set to ignore, not unmapped
            if h in mappings or norm in mappings:
                continue
            # If recognized in ALIAS_DICTIONARY, not unmapped
            if norm in ALIAS_DICTIONARY:
                continue

            unmapped.append(h)
            # Collect up to 3 non-empty sample values
            h_samples: list[str] = []
            for row in raw_rows:
                val = row.get(h)
                if val is not None and str(val).strip():
                    h_samples.append(str(val).strip())
                if len(h_samples) >= 3:
                    break
            samples[h] = h_samples

        return raw_headers, unmapped, samples

    @classmethod
    def _validate_and_convert_row(  # noqa: C901
        cls,
        row_idx: int,
        canonical_row: dict[str, Any],
    ) -> tuple[POIExchangeRecord | None, list[ValidationIssue]]:
        """Validates canonical row values and constructs a POIExchangeRecord or returns issues."""
        issues: list[ValidationIssue] = []

        # 1. POI Name (required)
        poi_name = str(canonical_row.get("poi_name") or "").strip()
        if not poi_name:
            issues.append(
                ValidationIssue(
                    row_number=row_idx,
                    column="poi_name",
                    raw_value="",
                    expected="Non-empty POI name string",
                )
            )

        # 2. Latitude validation (-90 to 90)
        raw_lat = canonical_row.get("latitude")
        lat: float | None = None
        if raw_lat is not None and str(raw_lat).strip() != "":
            try:
                lat_val = float(str(raw_lat).strip())
                if -90.0 <= lat_val <= 90.0:
                    lat = lat_val
                else:
                    issues.append(
                        ValidationIssue(
                            row_number=row_idx,
                            column="latitude",
                            raw_value=str(raw_lat),
                            expected="Expected numeric latitude between -90 and 90",
                        )
                    )
            except (ValueError, TypeError):
                issues.append(
                    ValidationIssue(
                        row_number=row_idx,
                        column="latitude",
                        raw_value=str(raw_lat),
                        expected="Expected numeric latitude between -90 and 90",
                    )
                )

        # 3. Longitude validation (-180 to 180)
        raw_lon = canonical_row.get("longitude")
        lon: float | None = None
        if raw_lon is not None and str(raw_lon).strip() != "":
            try:
                lon_val = float(str(raw_lon).strip())
                if -180.0 <= lon_val <= 180.0:
                    lon = lon_val
                else:
                    issues.append(
                        ValidationIssue(
                            row_number=row_idx,
                            column="longitude",
                            raw_value=str(raw_lon),
                            expected="Expected numeric longitude between -180 and 180",
                        )
                    )
            except (ValueError, TypeError):
                issues.append(
                    ValidationIssue(
                        row_number=row_idx,
                        column="longitude",
                        raw_value=str(raw_lon),
                        expected="Expected numeric longitude between -180 and 180",
                    )
                )

        # 4. Dates Visited (ISO 8601 YYYY-MM-DD)
        raw_dates = canonical_row.get("dates_visited")
        dates_list: list[str] = []
        if raw_dates is not None:
            if isinstance(raw_dates, list):
                dates_list = [str(d).strip() for d in raw_dates if str(d).strip()]
            elif isinstance(raw_dates, str) and raw_dates.strip():
                # Split on semicolon or comma
                delimiter = ";" if ";" in raw_dates else ","
                dates_list = [d.strip() for d in raw_dates.split(delimiter) if d.strip()]

        # 5. Tags (array or semicolon/comma-delimited)
        raw_tags = canonical_row.get("tags")
        tags_list: list[str] = []
        if raw_tags is not None:
            if isinstance(raw_tags, list):
                tags_list = [str(t).strip() for t in raw_tags if str(t).strip()]
            elif isinstance(raw_tags, str) and raw_tags.strip():
                delimiter = ";" if ";" in raw_tags else ","
                tags_list = [t.strip() for t in raw_tags.split(delimiter) if t.strip()]

        # 6. POI ID if present
        raw_poi_id = canonical_row.get("poi_id")
        poi_uuid: UUID | None = None
        if raw_poi_id is not None and str(raw_poi_id).strip():
            try:
                poi_uuid = UUID(str(raw_poi_id).strip())
            except (ValueError, TypeError):
                poi_uuid = None  # Disregard non-UUID foreign IDs gracefully

        # 7. Created At
        raw_created_at = canonical_row.get("created_at")
        created_at_dt: datetime | None = None
        if raw_created_at is not None and str(raw_created_at).strip():
            try:
                created_at_dt = datetime.fromisoformat(str(raw_created_at).strip())
                if created_at_dt.tzinfo is None:
                    created_at_dt = created_at_dt.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                created_at_dt = None

        if issues:
            return None, issues

        record = POIExchangeRecord(
            poi_id=poi_uuid,
            poi_name=poi_name,
            latitude=lat,
            longitude=lon,
            street_address=str(canonical_row.get("street_address") or ""),
            city=str(canonical_row.get("city") or ""),
            state_province=str(canonical_row.get("state_province") or ""),
            postal_code=str(canonical_row.get("postal_code") or ""),
            country=str(canonical_row.get("country") or ""),
            tags=tags_list,
            dates_visited=dates_list,
            photo_directory=str(canonical_row.get("photo_directory") or ""),
            location_confidence_percent=int(
                canonical_row.get("location_confidence_percent") or 100
            ),
            user_disposition=canonical_row.get("user_disposition"),
            rejection_reason=str(canonical_row.get("rejection_reason") or ""),
            ai_description=str(canonical_row.get("ai_description") or ""),
            reason_to_visit=str(canonical_row.get("reason_to_visit") or ""),
            recommended_duration_hours=float(
                canonical_row.get("recommended_duration_hours") or 2.0
            ),
            itinerary_days=int(canonical_row.get("itinerary_days") or 1),
            hero_image_url=str(canonical_row.get("hero_image_url") or ""),
            official_website=str(canonical_row.get("official_website") or ""),
            wikipedia_url=str(canonical_row.get("wikipedia_url") or ""),
            created_at=created_at_dt,
        )
        return record, []

    @classmethod
    def parse_file_bytes(
        cls,
        content: bytes,
        filename: str,
        column_mappings: dict[str, str] | None = None,
        skip_invalid_rows: bool = False,
    ) -> tuple[list[POIExchangeRecord], list[str], list[ValidationIssue]]:
        """Parses file content, applies canonical aliases/mappings, validates types, and returns records."""
        raw_rows = cls.load_raw_rows(content, filename)
        if not raw_rows:
            return [], [], []

        raw_headers, unmapped, _ = cls.inspect_headers_and_samples(
            content=content, filename=filename, column_mappings=column_mappings
        )

        mappings = column_mappings or {}
        # Precompute mapping from raw header to canonical field name
        header_to_field: dict[str, str] = {}
        for h in raw_headers:
            norm = h.strip().lower()
            if h in mappings:
                target = mappings[h]
                if target and target.upper() not in ("IGNORE", "[IGNORE]"):
                    header_to_field[h] = target
            elif norm in mappings:
                target = mappings[norm]
                if target and target.upper() not in ("IGNORE", "[IGNORE]"):
                    header_to_field[h] = target
            elif norm in ALIAS_DICTIONARY:
                header_to_field[h] = ALIAS_DICTIONARY[norm]

        records: list[POIExchangeRecord] = []
        all_issues: list[ValidationIssue] = []

        # In CSV with header, data rows start at row 2 (row 1 is header)
        is_csv = cls.sniff_format(filename, content) == "csv"
        row_offset = 2 if is_csv else 1

        for i, row in enumerate(raw_rows):
            row_num = i + row_offset
            canonical_row: dict[str, Any] = {}
            for raw_h, raw_val in row.items():
                field_name = header_to_field.get(raw_h)
                if field_name:
                    canonical_row[field_name] = raw_val

            record, row_issues = cls._validate_and_convert_row(row_num, canonical_row)
            if row_issues:
                all_issues.extend(row_issues)
                if not skip_invalid_rows:
                    continue
            elif record is not None:
                records.append(record)

        return records, unmapped, all_issues
