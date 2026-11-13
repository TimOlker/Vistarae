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

"""Authoritative canonical schema registry and serialization utilities for 017-export.

Defines the centralized specification for all POI candidate attributes, RFC 4180
serialization, formula injection neutralization, and dual-mode collection parsing.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel

UTF8_BOM = "\ufeff"
UTF8_BOM_BYTES = b"\xef\xbb\xbf"
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExportFieldType(StrEnum):
    """Data type categorization for candidate export and import fields."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING_LIST = "string_list"
    JSON_PAIRS = "json_pairs"
    UUID = "uuid"


def sanitize_formula_prefix(val: str) -> str:
    """Neutralizes spreadsheet formula injection by prepending a single quote.

    Args:
        val: Raw string to sanitize.

    Returns:
        String with leading single quote prepended if starting with formula triggers.
    """
    if not val:
        return ""
    if val.startswith(FORMULA_PREFIXES):
        return f"'{val}"
    return val


def desanitize_formula_prefix(val: str) -> str:
    """Strips formula-neutralizing leading single quote if followed by a formula prefix.

    Args:
        val: Input string potentially containing a neutralizing quote.

    Returns:
        Clean authentic string with neutralizing quote removed.
    """
    if not val:
        return ""
    if val.startswith("'") and len(val) > 1 and val[1:].startswith(FORMULA_PREFIXES):
        return val[1:]
    return val


def serialize_string_list(items: Sequence[str] | None) -> str:
    """Serializes a collection of strings into a semicolon-separated string.

    Args:
        items: List or sequence of string items.

    Returns:
        Semicolon-separated string, e.g. "Tag1; Tag2".
    """
    if not items:
        return ""
    return "; ".join(str(item).strip() for item in items if str(item).strip())


def deserialize_string_list(val: str) -> list[str]:
    """Deserializes a cell into a list of strings using tolerant dual-mode parsing.

    Accepts both JSON array strings (e.g. '["a", "b"]') and semicolon/comma-delimited
    text (e.g. "a; b").

    Args:
        val: Raw string value from CSV.

    Returns:
        List of non-empty stripped string items.
    """
    if not val:
        return []
    stripped = val.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    delimiter = ";" if ";" in stripped else ","
    return [item.strip() for item in stripped.split(delimiter) if item.strip()]


def serialize_json_pairs(items: Sequence[dict[str, Any]] | None) -> str:
    """Serializes structured object pairs (e.g. websites) to a compact JSON string.

    Args:
        items: List of dictionary pairs.

    Returns:
        JSON string representation.
    """
    if not items:
        return ""
    return json.dumps(list(items), ensure_ascii=False)


def deserialize_json_pairs(val: str) -> list[dict[str, Any]]:
    """Deserializes a cell containing structured object pairs.

    Accepts JSON array of objects, falling back to treating semicolon/comma-delimited
    URL strings as default URL objects if JSON parsing fails.

    Args:
        val: Raw cell value from CSV.

    Returns:
        List of dictionary objects containing at least name and url keys.
    """
    if not val:
        return []
    stripped = val.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                result: list[dict[str, Any]] = []
                for item in parsed:
                    if isinstance(item, dict):
                        result.append(item)
                    elif isinstance(item, str) and item.strip():
                        result.append({"name": item.strip(), "url": item.strip()})
                return result
        except Exception:
            pass

    # Fallback: treat delimited items as raw URLs
    delimiter = ";" if ";" in stripped else ","
    items = [item.strip() for item in stripped.split(delimiter) if item.strip()]
    return [{"name": u, "url": u} for u in items]


class ExportFieldDefinition(StrictBaseModel):
    """Metadata specification for a single candidate attribute in export and import."""

    attribute_key: str = Field(..., description="Canonical internal attribute key.")
    header_name: str = Field(..., description="Standardized CSV column header.")
    field_type: ExportFieldType = Field(default=ExportFieldType.STRING)
    aliases: list[str] = Field(
        default_factory=list, description="Accepted alternative header names."
    )
    is_formula_sanitized: bool = Field(
        default=False, description="Whether formula prefix protection applies."
    )
    default_value: Any = Field(default=None, description="Default fallback value if missing.")


CANONICAL_EXPORT_FIELDS: list[ExportFieldDefinition] = [
    ExportFieldDefinition(
        attribute_key="candidate_id",
        header_name="Candidate ID",
        field_type=ExportFieldType.UUID,
        aliases=["candidate_id", "candidate id", "id"],
    ),
    ExportFieldDefinition(
        attribute_key="row_index",
        header_name="Row Index",
        field_type=ExportFieldType.NUMBER,
        aliases=["row_index", "row index", "line_number"],
        default_value=0,
    ),
    ExportFieldDefinition(
        attribute_key="poi_name",
        header_name="POI Name",
        field_type=ExportFieldType.STRING,
        aliases=["poi_name", "poi name", "name", "title", "attraction"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="street_address",
        header_name="Street Address",
        field_type=ExportFieldType.STRING,
        aliases=["street_address", "street address", "address", "street"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="city",
        header_name="City / Town",
        field_type=ExportFieldType.STRING,
        aliases=["city", "town_city", "town/city", "town", "municipality"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="locality",
        header_name="Locality",
        field_type=ExportFieldType.STRING,
        aliases=["locality", "neighborhood", "suburb"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="admin_level_2",
        header_name="County / District (Admin Level 2)",
        field_type=ExportFieldType.STRING,
        aliases=["admin_level_2", "admin level 2", "county", "district"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="admin_level_1",
        header_name="State / Province (Admin Level 1)",
        field_type=ExportFieldType.STRING,
        aliases=["admin_level_1", "admin level 1", "state", "province", "region"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="state_province",
        header_name="State / Province",
        field_type=ExportFieldType.STRING,
        aliases=["state_province", "state/province"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="postal_code",
        header_name="Postal Code / Zip",
        field_type=ExportFieldType.STRING,
        aliases=["postal_code", "postal code", "zip_code", "zip code", "zip", "postcode"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="country",
        header_name="Country",
        field_type=ExportFieldType.STRING,
        aliases=["country", "nation"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="country_code",
        header_name="Country Code",
        field_type=ExportFieldType.STRING,
        aliases=["country_code", "country code", "iso_country"],
        is_formula_sanitized=False,
    ),
    ExportFieldDefinition(
        attribute_key="latitude",
        header_name="Latitude",
        field_type=ExportFieldType.NUMBER,
        aliases=["latitude", "lat"],
    ),
    ExportFieldDefinition(
        attribute_key="longitude",
        header_name="Longitude",
        field_type=ExportFieldType.NUMBER,
        aliases=["longitude", "lon", "lng"],
    ),
    ExportFieldDefinition(
        attribute_key="recommended_disposition",
        header_name="Recommended Disposition",
        field_type=ExportFieldType.STRING,
        aliases=["recommended_disposition", "recommended disposition"],
        default_value="accept",
    ),
    ExportFieldDefinition(
        attribute_key="user_disposition",
        header_name="User Disposition",
        field_type=ExportFieldType.STRING,
        aliases=["user_disposition", "user disposition", "disposition"],
    ),
    ExportFieldDefinition(
        attribute_key="confidence_score",
        header_name="Confidence Score",
        field_type=ExportFieldType.NUMBER,
        aliases=[
            "confidence_score",
            "confidence score",
            "location_confidence_percent",
            "confidence",
        ],
        default_value=0,
    ),
    ExportFieldDefinition(
        attribute_key="disposition_justification",
        header_name="Disposition Justification",
        field_type=ExportFieldType.STRING,
        aliases=[
            "disposition_justification",
            "disposition justification",
            "rejection_reason",
            "rationale",
        ],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="description",
        header_name="Description",
        field_type=ExportFieldType.STRING,
        aliases=["description", "ai_description", "overview"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="reason_to_visit",
        header_name="Reason to Visit",
        field_type=ExportFieldType.STRING,
        aliases=["reason_to_visit", "reason to visit", "why_visit"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="hero_image_url",
        header_name="Hero Image URL",
        field_type=ExportFieldType.STRING,
        aliases=["hero_image_url", "hero image url", "hero photo url", "image_url"],
    ),
    ExportFieldDefinition(
        attribute_key="official_url",
        header_name="Official URL",
        field_type=ExportFieldType.STRING,
        aliases=["official_url", "official url", "official website", "official_website"],
    ),
    ExportFieldDefinition(
        attribute_key="wiki_url",
        header_name="Wikipedia URL",
        field_type=ExportFieldType.STRING,
        aliases=["wiki_url", "wikipedia url", "wikipedia_url", "wiki url"],
    ),
    ExportFieldDefinition(
        attribute_key="related_websites",
        header_name="Related Websites",
        field_type=ExportFieldType.JSON_PAIRS,
        aliases=["related_websites", "related websites", "websites"],
    ),
    ExportFieldDefinition(
        attribute_key="no_websites",
        header_name="No Websites Flag",
        field_type=ExportFieldType.BOOLEAN,
        aliases=["no_websites", "no websites", "no_websites_flag"],
        default_value=False,
    ),
    ExportFieldDefinition(
        attribute_key="tags",
        header_name="Tags",
        field_type=ExportFieldType.STRING_LIST,
        aliases=["tags", "categories"],
    ),
    ExportFieldDefinition(
        attribute_key="photo_directory",
        header_name="Photo Directory",
        field_type=ExportFieldType.STRING,
        aliases=["photo_directory", "photo directory"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="photo_directories",
        header_name="Photo Directories",
        field_type=ExportFieldType.STRING_LIST,
        aliases=["photo_directories", "photo directories"],
    ),
    ExportFieldDefinition(
        attribute_key="dates_visited",
        header_name="Dates Visited",
        field_type=ExportFieldType.STRING_LIST,
        aliases=["dates_visited", "dates visited", "visited_dates"],
    ),
    ExportFieldDefinition(
        attribute_key="recommended_duration_hours",
        header_name="Recommended Duration Hours",
        field_type=ExportFieldType.NUMBER,
        aliases=["recommended_duration_hours", "estimated visit hours", "estimated_visit_hours"],
    ),
    ExportFieldDefinition(
        attribute_key="recommended_visit_days",
        header_name="Recommended Visit Days",
        field_type=ExportFieldType.NUMBER,
        aliases=["recommended_visit_days", "itinerary days", "itinerary_days"],
    ),
    ExportFieldDefinition(
        attribute_key="estimated_visit_time_notes",
        header_name="Estimated Visit Time Notes",
        field_type=ExportFieldType.STRING,
        aliases=["estimated_visit_time_notes", "visit_time_notes"],
        is_formula_sanitized=True,
    ),
    ExportFieldDefinition(
        attribute_key="parent_candidate_id",
        header_name="Parent Candidate ID",
        field_type=ExportFieldType.UUID,
        aliases=["parent_candidate_id", "parent candidate id"],
    ),
    ExportFieldDefinition(
        attribute_key="parent_poi_id",
        header_name="Parent POI ID",
        field_type=ExportFieldType.UUID,
        aliases=["parent_poi_id", "parent poi id"],
    ),
    ExportFieldDefinition(
        attribute_key="matched_existing_poi_id",
        header_name="Matched Existing POI ID",
        field_type=ExportFieldType.UUID,
        aliases=["matched_existing_poi_id", "matched existing poi id"],
    ),
    ExportFieldDefinition(
        attribute_key="merge_target_id",
        header_name="Merge Target ID",
        field_type=ExportFieldType.UUID,
        aliases=["merge_target_id", "merge target id"],
    ),
    ExportFieldDefinition(
        attribute_key="is_user_overridden",
        header_name="Is User Overridden",
        field_type=ExportFieldType.BOOLEAN,
        aliases=["is_user_overridden", "is user overridden", "user_overridden"],
        default_value=False,
    ),
]


def get_canonical_headers() -> list[str]:
    """Returns the ordered list of canonical CSV column headers."""
    return [field.header_name for field in CANONICAL_EXPORT_FIELDS]


def get_attribute_to_header_map() -> dict[str, str]:
    """Returns a mapping of attribute_key to header_name."""
    return {field.attribute_key: field.header_name for field in CANONICAL_EXPORT_FIELDS}


def get_header_to_attribute_map() -> dict[str, str]:
    """Returns a case-insensitive mapping of all headers and aliases to attribute keys."""
    mapping: dict[str, str] = {}
    for field in CANONICAL_EXPORT_FIELDS:
        mapping[field.header_name.lower()] = field.attribute_key
        mapping[field.attribute_key.lower()] = field.attribute_key
        for alias in field.aliases:
            mapping[alias.lower()] = field.attribute_key
    return mapping


def serialize_candidate_value(field_def: ExportFieldDefinition, raw_val: Any) -> str:
    """Formats an attribute value for CSV output according to its field definition.

    Args:
        field_def: The field definition.
        raw_val: Raw candidate attribute value.

    Returns:
        Formatted string representation.
    """
    if raw_val is None:
        return ""

    if field_def.field_type == ExportFieldType.STRING_LIST:
        if isinstance(raw_val, (list, tuple, set)):
            return serialize_string_list(list(raw_val))
        return str(raw_val)

    if field_def.field_type == ExportFieldType.JSON_PAIRS:
        if isinstance(raw_val, (list, tuple)):
            return serialize_json_pairs(list(raw_val))
        return str(raw_val)

    if field_def.field_type == ExportFieldType.BOOLEAN:
        return "true" if raw_val else "false"

    if field_def.field_type == ExportFieldType.UUID:
        return str(raw_val)

    if field_def.field_type == ExportFieldType.NUMBER:
        return str(raw_val)

    val_str = str(raw_val)
    if field_def.is_formula_sanitized:
        val_str = sanitize_formula_prefix(val_str)
    return val_str


def format_csv_cell(val: str) -> str:
    """Escapes a single string cell according to RFC 4180 rules.

    Args:
        val: Input string cell.

    Returns:
        RFC 4180 compliant quoted or unquoted cell string.
    """
    if not val:
        return ""
    if any(c in val for c in (",", '"', "\n", "\r")):
        escaped = val.replace('"', '""')
        return f'"{escaped}"'
    return val
