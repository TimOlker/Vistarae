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

"""Pydantic schemas for POI entities, deduplication responses, and lists."""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.extraction import POIExtractionCandidate


class CollisionStatus(str, Enum):
    UNIQUE_LOCATION = "UNIQUE_LOCATION"
    POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"
    NEARBY_PARENT = "NEARBY_PARENT"


class POICollisionMatch(BaseModel):
    id: uuid.UUID
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    poi_type: str
    personal_rating: int | None = None
    distance_meters: float
    name_similarity: float
    description: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    parent_poi_id: uuid.UUID | None = None
    category_tags: list[str] = Field(default_factory=list)


class ListSummary(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    is_trip: bool = False


class ParentPOISummary(BaseModel):
    id: uuid.UUID
    name: str
    poi_type: str


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class TagResponse(BaseModel):
    name: str
    is_custom: bool = False


class ExtractAndCheckResponse(BaseModel):
    candidate: POIExtractionCandidate
    latitude: float | None = None
    longitude: float | None = None
    display_name: str | None = None
    collision_status: CollisionStatus
    matched_poi: POICollisionMatch | None = None
    nearby_parent: POICollisionMatch | None = None
    available_lists: list[ListSummary] = Field(default_factory=list)
    available_parents: list[ParentPOISummary] = Field(default_factory=list)
    available_tags: list[str] = Field(default_factory=list)
    source_url: str
    source_type: str | None = "web"
    og_image_url: str | None = None
    location_detected: bool = True


class POIAccessPointCreate(BaseModel):
    type: str = Field(..., description="e.g. parking lot, trail head, bus stop")
    description: str | None = None
    latitude: float
    longitude: float
    parking_logistics: str | None = Field(
        default=None, description="free parking, paid street parking, transit only"
    )


class POICreate(BaseModel):
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    poi_type: str = Field(
        default="site to see",
        description="photo location, site to see, experience, food/drink, lodging, transit",
    )
    personal_rating: int | None = Field(default=3, ge=1, le=5)
    description: str | None = None
    category_tags: list[str] = Field(default_factory=list)
    visited: bool = False
    visit_date: date | None = None
    visit_dates: list[date] = Field(default_factory=list)
    visit_again: bool = False

    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_ft: int = 500
    parent_poi_id: uuid.UUID | None = None

    physical_effort: str | None = None
    booking_lead_time: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    hours_seasonality: str | None = None
    best_time_to_visit: str | None = None
    website_official: str | None = None
    phone_number: str | None = None
    google_place_id: str | None = None

    primary_image_url: str | None = None
    alternate_image_urls: list[str] = Field(default_factory=list)
    source_url: str = Field(default="")
    source_type: str | None = "web"
    raw_selected_text: str | None = None

    iptc_sublocation: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    iptc_world_region: str | None = None
    iptc_zip_code: str | None = None

    list_ids: list[uuid.UUID] = Field(default_factory=list)
    access_points: list[POIAccessPointCreate] = Field(default_factory=list)


class POIUpdate(BaseModel):
    name: str | None = None
    name_aliases: list[str] | None = None
    poi_type: str | None = None
    personal_rating: int | None = Field(default=None, ge=1, le=5)
    description: str | None = None
    category_tags: list[str] | None = None
    visited: bool | None = None
    visit_date: date | None = None
    visit_dates: list[date] | None = None
    visit_again: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    clear_location: bool | None = False
    geofence_radius_ft: int | None = None
    parent_poi_id: uuid.UUID | None = None
    physical_effort: str | None = None
    booking_lead_time: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    hours_seasonality: str | None = None
    best_time_to_visit: str | None = None
    website_official: str | None = None
    phone_number: str | None = None
    primary_image_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    iptc_sublocation: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    iptc_zip_code: str | None = None
    list_ids: list[uuid.UUID] | None = None


class POIResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_aliases: list[str]
    poi_type: str
    personal_rating: int | None
    description: str | None
    category_tags: list[str]
    visited: bool
    visit_date: date | None
    visit_dates: list[date] = Field(default_factory=list)
    visit_again: bool = False
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_ft: int
    parent_poi_id: uuid.UUID | None
    physical_effort: str | None
    booking_lead_time: str | None
    indoor_outdoor: str | None
    estimated_duration: str | None
    cost_tier: str | None
    hours_seasonality: str | None
    best_time_to_visit: str | None
    website_official: str | None
    phone_number: str | None
    primary_image_url: str | None
    source_url: str
    source_type: str | None = None
    iptc_city: str | None
    iptc_province_state: str | None
    iptc_country_code: str | None
    created_at: datetime
    list_ids: list[uuid.UUID] = Field(default_factory=list)
    has_folder_conflict: bool = False

    model_config = ConfigDict(from_attributes=True)


class ListCreate(BaseModel):
    title: str
    description: str | None = None
    is_trip: bool = False


class POIBulkDeleteRequest(BaseModel):
    poi_ids: list[uuid.UUID] = Field(..., min_length=1)


class POIBulkUpdateRequest(BaseModel):
    poi_ids: list[uuid.UUID] = Field(..., min_length=1)
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    clear_location: bool | None = False
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None


class POIBulkActionResponse(BaseModel):
    success: bool = True
    affected_count: int


class ReverseGeocodeResponse(BaseModel):
    display_name: str | None = None
    city: str | None = None
    state: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    sublocation: str | None = None
    postcode: str | None = None
    raw_address: dict[str, Any] = Field(default_factory=dict)


class GeocodeQueryResponse(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    display_name: str | None = None
    city: str | None = None
    state: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    sublocation: str | None = None
    postcode: str | None = None
    raw_address: dict[str, Any] = Field(default_factory=dict)


class CheckDuplicateRequest(BaseModel):
    name: str = Field(..., description="Name of the point of interest to test")
    latitude: float | None = Field(None, description="Latitude of candidate POI")
    longitude: float | None = Field(None, description="Longitude of candidate POI")
    radius_ft: int = Field(500, description="Spatial search radius in feet")


class CheckDuplicateResponse(BaseModel):
    collision_status: CollisionStatus
    matched_poi: POICollisionMatch | None = None
    nearby_parent: POICollisionMatch | None = None
