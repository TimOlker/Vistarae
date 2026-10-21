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

"""Pydantic schemas for multi-format POI bulk ingestion, data quality flags, and conflict resolution."""

import uuid
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.poi import CollisionStatus, POICollisionMatch


class ConflictAction(str, Enum):
    CREATE = "CREATE"
    MERGE = "MERGE"
    SKIP = "SKIP"
    LINK = "LINK"
    ADD_TAGS = "ADD_TAGS"


class IngestionDataQuality(BaseModel):
    is_valid: bool = True
    has_name: bool = True
    has_coordinates: bool = True
    has_address: bool = True
    geocoded_address: bool = False
    geocoded_coordinates: bool = False
    flags: list[str] = Field(default_factory=list)


class StandardizedCandidatePOI(BaseModel):
    temp_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    poi_type: str = "site to see"
    personal_rating: int | None = 3
    description: str | None = None
    category_tags: list[str] = Field(default_factory=list)
    visited: bool = False
    visit_date: date | None = None
    visit_again: bool = False

    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_ft: int = 500
    parent_poi_id: uuid.UUID | None = None

    website_official: str | None = None
    phone_number: str | None = None
    source_url: str | None = None
    source_type: str | None = "import"

    iptc_sublocation: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    iptc_world_region: str | None = None
    iptc_zip_code: str | None = None

    quality: IngestionDataQuality = Field(default_factory=IngestionDataQuality)
    collision_status: CollisionStatus = CollisionStatus.UNIQUE_LOCATION
    matched_poi: POICollisionMatch | None = None
    nearby_parent: POICollisionMatch | None = None
    action: ConflictAction = ConflictAction.CREATE
    missing_tags: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class IngestParseRequest(BaseModel):
    content: str
    filename: str | None = None
    format_hint: str | None = None
    default_tags: list[str] = Field(default_factory=list)
    target_list_id: uuid.UUID | None = None
    perform_geocoding: bool = True


class IngestPreviewResponse(BaseModel):
    detected_format: str
    total_records: int
    valid_records: int
    flagged_records: int
    conflict_count: int
    headers_found: list[str] = Field(default_factory=list)
    field_mappings: dict[str, str] = Field(default_factory=dict)
    items: list[StandardizedCandidatePOI] = Field(default_factory=list)
    preset_name: str | None = None


class IngestCommitItem(BaseModel):
    temp_id: str
    action: ConflictAction
    poi_data: StandardizedCandidatePOI
    matched_poi_id: uuid.UUID | None = None
    target_list_id: uuid.UUID | None = None


class IngestCommitRequest(BaseModel):
    items: list[IngestCommitItem]
    default_tags: list[str] = Field(default_factory=list)
    target_list_id: uuid.UUID | None = None
    new_list_title: str | None = None
    list_membership_scope: str = "both"  # "both" or "new_only"


class IngestCommitResponse(BaseModel):
    created_count: int
    merged_count: int
    skipped_count: int
    linked_count: int
    created_poi_ids: list[uuid.UUID] = Field(default_factory=list)
    applied_tags: list[str] = Field(default_factory=list)
    target_list_id: uuid.UUID | None = None
    target_list_title: str | None = None
    enrolled_count: int = 0


class PresetSummary(BaseModel):
    id: str
    title: str
    description: str
    count: int
    tags: list[str] = Field(default_factory=list)
