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

"""Standardized POI export record schema for RFC 4180 CSV export and import.

Adheres to:
- REQ-SCR-029: Standardized output schema
- REQ-SCR-034: 12 standardized CSV columns
- StrictBaseModel immutability and validation
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel
from vistarae_core.domain.value_objects import IngestDisposition


class POIExportRecord(StrictBaseModel):
    """Standardized representation of a POI row for RFC 4180 CSV export and import."""

    poi_name: str = Field(
        ...,
        max_length=255,
        description="Standardized name of the attraction",
    )
    street_address: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned street addresses",
    )
    town_city: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned city or locality names",
    )
    state_province: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned state or province names",
    )
    zip_code: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned postal or zip codes",
    )
    country: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned English country names",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Thematic or contextual tags (empty for photo scraper)",
    )
    latitude: Decimal | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="WGS-84 decimal latitude",
    )
    longitude: Decimal | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="WGS-84 decimal longitude",
    )
    dates_visited: list[str] = Field(
        default_factory=list,
        description="ISO-8601 visit dates (YYYY-MM-DD)",
    )
    photo_directory: str = Field(
        default="",
        description="Original filesystem directory path of the POI",
    )
    location_confidence_percent: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Location certainty score (0-100)",
    )
    confidence_source: str | None = Field(
        default=None,
        description="Signals and sources contributing to location confidence",
    )
    candidate_id: UUID | None = Field(
        default=None,
        description="Original candidate ID for intra-batch nesting and deduplication mapping",
    )
    row_index: int | None = Field(
        default=None,
        description="Original row index position",
    )
    locality: str | None = Field(
        default=None,
        description="Neighborhood, suburb, or sub-municipality locality",
    )
    admin_level_1: str | None = Field(
        default=None,
        description="Primary administrative subdivision (state/province/region)",
    )
    admin_level_2: str | None = Field(
        default=None,
        description="Secondary administrative subdivision (county/district)",
    )
    country_code: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 two-letter country code",
    )
    description: str | None = Field(
        default=None,
        description="Detailed description or overview",
    )
    reason_to_visit: str | None = Field(
        default=None,
        description="Traveler curation justification or highlight",
    )
    hero_image_url: str | None = Field(
        default=None,
        description="Hero/lead display photograph URL",
    )
    official_url: str | None = Field(
        default=None,
        description="Official website or authority URL",
    )
    wiki_url: str | None = Field(
        default=None,
        description="Wikipedia article reference URL",
    )
    related_websites: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured list of related website pairs (name, url)",
    )
    no_websites: bool = Field(
        default=False,
        description="Explicit flag confirming no relevant websites exist",
    )
    photo_directories: list[str] = Field(
        default_factory=list,
        description="List of originating photo filesystem directory paths",
    )
    recommended_duration_hours: Decimal | float | None = Field(
        default=None,
        description="Recommended time on site in hours",
    )
    recommended_visit_days: int | None = Field(
        default=None,
        description="Recommended days for itinerary scheduling",
    )
    estimated_visit_time_notes: str | None = Field(
        default=None,
        description="Temporal visit suggestions or scheduling tips",
    )
    recommended_disposition: IngestDisposition | str | None = Field(
        default=None,
        description="Initial automated recommendation verdict",
    )
    user_disposition: IngestDisposition | str | None = Field(
        default=None,
        description="Explicit traveler triage override disposition",
    )
    disposition_justification: str | None = Field(
        default=None,
        description="Explanation or rationale for disposition assignment",
    )
    is_user_overridden: bool = Field(
        default=False,
        description="Flag indicating manual override bypassing heuristic calculation",
    )
    parent_candidate_id: UUID | None = Field(
        default=None,
        description="Intra-batch parent candidate reference for macro-site nesting",
    )
    parent_poi_id: UUID | None = Field(
        default=None,
        description="Reference to existing database macro-site POI",
    )
    matched_existing_poi_id: UUID | None = Field(
        default=None,
        description="Reference to existing database POI matched for update/merge",
    )
    merge_target_id: UUID | None = Field(
        default=None,
        description="Intra-batch merge target reference for deduplication",
    )
    raw_geocoding: dict[str, Any] | None = Field(
        default=None,
        description="Raw geocoding payload or extension metadata dictionary",
    )
