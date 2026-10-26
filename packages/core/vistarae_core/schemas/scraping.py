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

"""Scraping sources preferences schemas enforcing Constitution Principle 5."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.value_objects import AddressRecord
from vistarae_core.schemas.base import StrictBaseModel


class ScrapingSourcesResponse(StrictBaseModel):
    """List of authorized secondary scraping domain suffixes for the user."""

    valid_scraping_domains: list[str] = Field(
        default_factory=list,
        description="List of domain suffixes authorized for secondary scraping",
    )


class ScrapingSourcesUpdateRequest(StrictBaseModel):
    """Payload to update the user's authorized secondary scraping domains."""

    valid_scraping_domains: list[str] = Field(
        min_length=1,
        description="List of domain suffixes authorized for secondary scraping",
    )


class ExtractAndCheckRequest(StrictBaseModel):
    """Request payload for multi-source web extraction and deduplication triage."""

    source_url: str = Field(..., description="Canonical URL of the captured page")
    page_title: str | None = Field(default=None, description="Raw HTML document title")
    selected_text: str | None = Field(
        default=None, description="User highlighted or selection snippet"
    )


class POICandidateSchema(StrictBaseModel):
    """Normalized POI extraction candidate schema maintaining 1:1 parity with POI Editor."""

    name: str = Field(..., description="Normalized standard English POI name")
    description: str = Field(..., description="Concise multi-line summary of the destination")
    addresses: list[AddressRecord] = Field(
        default_factory=list, description="Array of resolved address objects"
    )
    latitude: float | None = Field(
        default=None, description="Geographic latitude in decimal degrees"
    )
    longitude: float | None = Field(
        default=None, description="Geographic longitude in decimal degrees"
    )
    official_website_url: str | None = Field(
        default=None, description="Official attraction website URL"
    )
    wikipedia_url: str | None = Field(default=None, description="English Wikipedia article URL")
    hero_image_url: str | None = Field(
        default=None, description="High-resolution hero photo thumbnail"
    )
    estimated_duration_hours: float | None = Field(
        default=None, description="Estimated visit duration hours"
    )
    estimated_duration_days: int | None = Field(
        default=None, description="Estimated visit duration days"
    )
    rating: int | None = Field(
        default=None, ge=0, le=5, description="User manual rating (null on web capture)"
    )
    source_type: str = Field(default="Web", description="Origin source type")
    source_value: str = Field(..., description="Source page URL")
    extraction_sources: list[str] = Field(
        default_factory=list, description="List of source domains consulted"
    )


class DeduplicationVerdictSchema(StrictBaseModel):
    """Scale-aware duplicate and parent-child nesting triage verdict."""

    status: Literal["UNIQUE_LOCATION", "POTENTIAL_DUPLICATE", "NEARBY_PARENT"] = Field(
        ..., description="Spatial triage classification"
    )
    distance_meters: float | None = Field(
        default=None, description="Distance to closest POI in meters"
    )
    similarity_score: float | None = Field(
        default=None, description="Trigram name similarity score (0.0 to 1.0)"
    )
    existing_poi_id: UUID | None = Field(default=None, description="UUID of matched existing POI")
    existing_poi_name: str | None = Field(
        default=None, description="Display name of matched existing POI"
    )
    scale_classification: Literal["macro", "medium", "micro"] | None = Field(
        default=None, description="Inferred spatial footprint scale"
    )
    recommended_action: Literal["proceed", "make_child", "abort"] = Field(
        default="proceed", description="Recommended user triage workflow action"
    )


class ExtractAndCheckResponse(StrictBaseModel):
    """Comprehensive extraction candidate, tag recommendations, and duplicate verdict response."""

    candidate: POICandidateSchema = Field(
        ..., description="Structured POI candidate extracted from web"
    )
    recommended_tags: list[str] = Field(default_factory=list, description="Matched user tag slugs")
    deduplication: DeduplicationVerdictSchema = Field(
        ..., description="Deduplication and nesting verdict"
    )
