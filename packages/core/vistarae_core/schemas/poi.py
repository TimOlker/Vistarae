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

"""Pydantic v2 boundary schemas for Point of Interest Domain & Geospatial Engine.

Enforces OpenAPI 3.1 contract specifications defined in specs/002-poi-domain-spatial/contracts/poi-api.yaml.
Strict validation via StrictBaseModel (extra='forbid', str_strip_whitespace=True).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from vistarae_core.domain.value_objects import (
    AddressRecord,
    EnrichmentStatus,
    SourceType,
    VisitState,
)
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.tag import TagResponse


class ListResponse(StrictBaseModel):
    """Curated list response model."""

    id: UUID = Field(..., description="List unique identifier")
    user_id: UUID = Field(..., description="Owner user identifier")
    title: str = Field(..., description="List title")
    description: str | None = Field(default=None, description="List description")
    is_public: bool = Field(default=False, description="Public shareability flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ListCreateRequest(StrictBaseModel):
    """Request model for creating a curated list."""

    title: str = Field(..., min_length=1, max_length=200, description="List title")
    description: str | None = Field(default=None, description="List description")
    is_public: bool = Field(default=False, description="Public shareability flag")


class ListUpdateRequest(StrictBaseModel):
    """Request model for updating a curated list."""

    title: str | None = Field(default=None, min_length=1, max_length=200, description="List title")
    description: str | None = Field(default=None, description="List description")
    is_public: bool | None = Field(default=None, description="Public shareability flag")


class POIResponse(StrictBaseModel):
    """Point of Interest response schema."""

    id: UUID = Field(..., description="Unique POI identifier")
    user_id: UUID = Field(..., description="Owning tenant UUID")
    parent_poi_id: UUID | None = Field(default=None, description="Parent macro-site POI UUID")
    parent_poi_name: str | None = Field(
        default=None, description="Resolved parent macro-site POI canonical name"
    )
    name: str = Field(..., description="POI canonical name")
    description: str | None = Field(default=None, description="Rich description or markdown")
    address: str | None = Field(default=None, description="Geocoded street address")
    city: str | None = Field(default=None, description="City or municipality")
    states: list[str] = Field(
        default_factory=list,
        description="Administrative subdivisions or states spanned by POI",
    )
    countries: list[str] = Field(
        default_factory=list,
        description="Sovereign nations spanned by POI",
    )
    addresses: list[AddressRecord] = Field(
        default_factory=list, description="Array of structured international address records"
    )
    official_url: str | None = Field(default=None, description="Official entity website")
    wiki_url: str | None = Field(default=None, description="Wikipedia or Wikidata reference")
    image_urls: list[str] = Field(default_factory=list, description="Array of image URLs")
    directory_paths: list[str] = Field(
        default_factory=list, description="Associated local file directory paths"
    )
    creation_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata captured during creation"
    )
    visit_state: VisitState = Field(
        default=VisitState.NOT_VISITED, description="Visit tracking state"
    )
    visited_dates: list[date | str] = Field(
        default_factory=list, description="Dates on which the POI was visited"
    )
    want_to_visit_again: bool = Field(
        default=False, description="Flag indicating future travel intent"
    )
    already_visited: bool = Field(
        default=False, description="True if visited_dates contains one or more entries"
    )
    visit_pending: bool = Field(
        default=True, description="True if unvisited or want_to_visit_again is True"
    )
    source_type: str = Field(
        default="Manual", description="Origin provenance (Web, CSV, Manual, Photo)"
    )
    source_value: str | None = Field(default=None, description="Provenance origin details")
    rating: int | None = Field(default=None, ge=0, le=5, description="User rating (1-5)")
    estimated_cost: float | None = Field(default=None, description="Estimated activity cost")
    pricing_unit: str | None = Field(default=None, max_length=16, description="Currency or unit")
    recommended_duration_hours: float | None = Field(
        default=None, ge=0.1, le=24.0, description="Duration in hours"
    )
    recommended_visit_days: int = Field(default=1, description="Recommended days to spend at POI")
    enrichment_status: EnrichmentStatus = Field(
        default=EnrichmentStatus.PARTIAL, description="Address geocoding enrichment status"
    )
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees (WGS-84)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees (WGS-84)")
    longitude: float | None = Field(
        default=None, description="Longitude in degrees (alias for lon)"
    )
    latitude: float | None = Field(default=None, description="Latitude in degrees (alias for lat)")
    similarity_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Semantic vector cosine similarity score"
    )
    tags: list[TagResponse] = Field(default_factory=list, description="Attached tags")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last modification timestamp")

    @model_validator(mode="after")
    def sync_aliases_and_lifecycle(self) -> POIResponse:
        """Synchronizes latitude/longitude aliases and deterministic visit lifecycle."""
        lat = self.lat if self.latitude is None else self.latitude
        lon = self.lon if self.longitude is None else self.longitude
        has_visited = len(self.visited_dates) > 0
        already_visited = has_visited
        visit_pending = (not has_visited) or bool(self.want_to_visit_again)

        object.__setattr__(self, "latitude", lat)
        object.__setattr__(self, "longitude", lon)
        object.__setattr__(self, "already_visited", already_visited)
        object.__setattr__(self, "visit_pending", visit_pending)
        return self


class SharedListResponse(StrictBaseModel):
    """Public read-only curated list view containing member POIs."""

    pois: list[POIResponse] = Field(default_factory=list, description="Member POIs")
    list_: ListResponse = Field(..., alias="list", description="Curated list metadata")


class POICreateRequest(StrictBaseModel):
    """Request payload for creating a new Point of Interest."""

    name: str = Field(..., min_length=1, max_length=255, description="POI canonical name")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees (WGS-84)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees (WGS-84)")
    parent_poi_id: UUID | None = Field(default=None, description="Optional macro-site parent UUID")
    description: str | None = Field(default=None, description="Rich description or markdown")
    address: str | None = Field(default=None, max_length=500, description="Street address")
    city: str | None = Field(default=None, max_length=100, description="City or municipality")
    states: list[str] | None = Field(
        default=None,
        description="Array of states or provinces spanned by the POI",
    )
    countries: list[str] | None = Field(
        default=None,
        description="Array of countries spanned by the POI",
    )
    state: str | None = Field(
        default=None, description="Optional convenience alias for single-state POIs"
    )
    country: str | None = Field(
        default=None, description="Optional convenience alias for single-country POIs"
    )
    official_url: str | None = Field(default=None, description="Official website URL")
    wiki_url: str | None = Field(default=None, description="Wikipedia URL")
    image_urls: list[str] = Field(default_factory=list, description="Image URLs")
    tag_names: list[str] = Field(default_factory=list, description="Initial tag names to attach")
    visit_state: VisitState = Field(
        default=VisitState.NOT_VISITED, description="Visit tracking state"
    )
    rating: int | None = Field(default=None, ge=0, le=5, description="User rating (1-5)")
    estimated_cost: float | None = Field(default=None, description="Estimated activity cost")
    pricing_unit: str | None = Field(default=None, max_length=16, description="Pricing unit")
    recommended_duration_hours: float | None = Field(
        default=None, ge=0.25, le=12.0, description="Recommended duration in hours"
    )
    recommended_visit_days: int = Field(default=1, description="Recommended days to spend at POI")

    @model_validator(mode="after")
    def populate_state_and_country_arrays(self) -> POICreateRequest:
        """Coalesces convenience aliases 'state' and 'country' into plural arrays."""
        if self.states is None:
            self.states = [self.state] if self.state else []
        elif self.state and self.state not in self.states:
            self.states.append(self.state)

        if self.countries is None:
            self.countries = [self.country] if self.country else []
        elif self.country and self.country not in self.countries:
            self.countries.append(self.country)

        return self


class POIUpdateRequest(StrictBaseModel):
    """Request payload for updating an existing Point of Interest."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="POI canonical name"
    )
    parent_poi_id: UUID | None = Field(default=None, description="Optional macro-site parent UUID")
    description: str | None = Field(
        default=None, max_length=10000, description="Rich description or markdown"
    )
    addresses: list[AddressRecord] | None = Field(
        default=None, description="Structured international address records"
    )
    address: str | None = Field(default=None, max_length=500, description="Street address")
    city: str | None = Field(default=None, max_length=100, description="City or municipality")
    states: list[str] | None = Field(
        default=None, description="Array of states or provinces spanned by the POI"
    )
    countries: list[str] | None = Field(
        default=None, description="Array of countries spanned by the POI"
    )
    state: str | None = Field(
        default=None, description="Optional convenience alias for single-state updates"
    )
    country: str | None = Field(
        default=None, description="Optional convenience alias for single-country updates"
    )
    latitude: float | None = Field(
        default=None, ge=-90.0, le=90.0, description="Updated latitude in degrees"
    )
    longitude: float | None = Field(
        default=None, ge=-180.0, le=180.0, description="Updated longitude in degrees"
    )
    recommended_duration_hours: float | None = Field(
        default=None, ge=0.1, le=24.0, description="Recommended duration in hours"
    )
    recommended_visit_days: int | None = Field(
        default=None, ge=1, le=365, description="Recommended days to spend at POI"
    )
    source_type: SourceType | str | None = Field(
        default=None, description="Provenance source type (Web, CSV, Manual, Photo)"
    )
    source_value: str | None = Field(
        default=None, max_length=1000, description="Provenance source value"
    )
    official_url: str | None = Field(
        default=None, max_length=2000, description="Official website URL"
    )
    wiki_url: str | None = Field(default=None, max_length=2000, description="Wikipedia URL")
    directory_paths: list[str] | None = Field(
        default=None, description="Associated local file directory paths"
    )
    image_urls: list[str] | None = Field(default=None, description="Image URLs")
    visited_dates: list[date | str] | None = Field(
        default=None, description="Array of ISO-8601 visit dates"
    )
    want_to_visit_again: bool | None = Field(default=None, description="Future travel intent")
    visit_state: VisitState | None = Field(default=None, description="Visit tracking state")
    rating: int | None = Field(default=None, ge=0, le=5, description="User rating (1-5)")
    tags: list[str] | None = Field(default=None, description="Attached taxonomy tags")
    estimated_cost: float | None = Field(default=None, description="Estimated activity cost")
    pricing_unit: str | None = Field(default=None, max_length=16, description="Pricing unit")

    @model_validator(mode="after")
    def populate_state_and_country_arrays(self) -> POIUpdateRequest:
        """Coalesces convenience aliases 'state' and 'country' into plural arrays."""
        if self.state is not None and self.states is None:
            self.states = [self.state]
        if self.country is not None and self.countries is None:
            self.countries = [self.country]
        return self


POIReadResponse = POIResponse


class POIListResponse(StrictBaseModel):
    """Paginated collection of Point of Interest records."""

    items: list[POIResponse] = Field(..., description="Matching POI items")
    total: int = Field(..., description="Total count of matching records")
    limit: int = Field(..., description="Page size limit")
    offset: int = Field(..., description="Pagination offset")


class PotentialDuplicateItem(StrictBaseModel):
    """Individual candidate duplicate match."""

    existing_poi: POIResponse = Field(..., description="Existing collision POI")
    distance_meters: float = Field(..., description="Geodesic distance in meters")
    name_similarity: float = Field(..., description="Trigram similarity score (0.0 to 1.0)")
    match_confidence: float = Field(..., description="Composite match confidence (0.0 to 1.0)")


class DedupCheckResponse(StrictBaseModel):
    """Response payload for duplicate candidate probing."""

    matches: list[PotentialDuplicateItem] = Field(
        default_factory=list, description="Candidate duplicate POIs"
    )


class ParentPOICandidate(StrictBaseModel):
    """Candidate parent POI item for hierarchical typeahead."""

    id: UUID = Field(..., description="Unique POI identifier")
    name: str = Field(..., description="POI canonical name")
    location_summary: str | None = Field(
        default=None, description="Human-readable city/state/country summary"
    )


class ReverseGeocodeResponse(StrictBaseModel):
    """Response payload for reverse geocoding."""

    street: str | None = Field(default=None, max_length=255, description="Street address")
    city: str | None = Field(default=None, max_length=100, description="City or municipality")
    state_province: str | None = Field(
        default=None, max_length=100, description="State or province"
    )
    country: str = Field(
        ..., min_length=2, max_length=100, description="Normalized English country name"
    )
    postal_code: str | None = Field(default=None, max_length=32, description="Postal / ZIP code")
    cached: bool = Field(default=False, description="True if resolved from PostGIS geocache")


class POIMergeRequest(StrictBaseModel):
    """Specification for atomically merging two duplicate POIs."""

    target_poi_id: UUID = Field(..., description="POI record to retain as canonical")
    source_poi_id: UUID = Field(..., description="POI record to merge from and delete")
    use_source_for: list[str] = Field(
        default_factory=list,
        description="Attributes to copy from source to target (e.g. ['description', 'official_url'])",
    )
    merge_tags: bool = Field(
        default=True, description="Whether to union tags from source into target"
    )


class BulkTagsRequest(StrictBaseModel):
    """Request payload for bulk tag association or disassociation."""

    poi_ids: list[UUID] = Field(..., min_length=1, description="Target POI UUIDs")
    tag_ids: list[UUID] = Field(..., min_length=1, description="Tag UUIDs")
    action: Literal["attach", "detach"] = Field(
        ..., description="Action to perform: attach or detach"
    )


class BulkListsRequest(StrictBaseModel):
    """Request payload for bulk list membership association or disassociation."""

    poi_ids: list[UUID] = Field(..., min_length=1, description="Target POI UUIDs")
    list_ids: list[UUID] = Field(..., min_length=1, description="List UUIDs")
    action: Literal["attach", "detach"] = Field(
        ..., description="Action to perform: attach or detach"
    )


class BulkEditAction(StrEnum):
    """Enumeration of supported bulk POI mutation actions."""

    SET_RATING = "set_rating"
    ADD_VISIT_DATE = "add_visit_date"
    SET_VISIT_AGAIN = "set_visit_again"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    ADD_TO_LIST = "add_to_list"
    REMOVE_FROM_LIST = "remove_from_list"
    UPDATE_ADDRESS = "update_address"


class BulkAddressUpdatePayload(StrictBaseModel):
    """Address fields for bulk location updating."""

    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    clear_fields: list[str] = Field(
        default_factory=list, description="Fields explicitly cleared to null"
    )


class BulkEditPayload(StrictBaseModel):
    """Context-specific parameters for bulk POI mutations."""

    rating: int | None = Field(default=None, ge=0, le=5)
    visit_date: date | None = None
    want_to_visit_again: bool | None = None
    tag_name: str | None = Field(default=None, max_length=50)
    list_id: UUID | None = None
    address: BulkAddressUpdatePayload | None = None


class BulkEditRequest(StrictBaseModel):
    """Request payload for atomic bulk POI editing."""

    poi_ids: list[UUID] = Field(
        ..., min_length=1, max_length=500, description="Target POI UUIDs (max 500)"
    )
    action: BulkEditAction = Field(..., description="Action to execute")
    payload: BulkEditPayload = Field(..., description="Action parameters")


class BulkDeleteRequest(StrictBaseModel):
    """Request payload for bulk deletion of POIs."""

    poi_ids: list[UUID] = Field(
        ..., min_length=1, max_length=500, description="Target POI UUIDs to delete (max 500)"
    )


class POIQueryRequest(StrictBaseModel):
    """Request payload for evaluated query builder AST search."""

    query_tree: dict[str, Any] = Field(..., description="Structured query tree AST")
    bbox: str | None = Field(
        default=None, description="Comma-separated minLng,minLat,maxLng,maxLat"
    )


class BulkOperationResponse(StrictBaseModel):
    """Response payload for bulk mutations."""

    modified_count: int = Field(..., description="Count of modified associations")


class BulkDeleteResponse(StrictBaseModel):
    """Response payload for bulk deletion."""

    deleted_count: int = Field(..., description="Count of deleted POI records")
