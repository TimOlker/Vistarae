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

"""Pydantic v2 schemas for POI selective merge operations (T-022)."""

from typing import Any
from uuid import UUID

from pydantic import Field

from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.poi import POIReadResponse


class POIMergeRequest(StrictBaseModel):
    """Payload for atomically merging two POIs or merging an in-memory draft."""

    source_poi_id: UUID | None = Field(
        default=None,
        description="Source POI ID to merge and delete, or None if merging in-memory draft.",
    )
    target_poi_id: UUID = Field(
        ...,
        description="Target POI ID that receives synthesized values and re-parented references.",
    )
    selected_scalars: dict[str, Any] = Field(
        default_factory=dict,
        description="Resolved scalar attribute values (name, description, rating, duration, etc.).",
    )
    selected_sets: dict[str, list[Any]] = Field(
        default_factory=dict,
        description="Resolved multi-value set attributes (addresses, tags, photo directories, etc.).",
    )
    use_source_for: list[str] = Field(
        default_factory=list,
        description="Attributes to copy from source to target (legacy compatibility).",
    )
    merge_tags: bool = Field(
        default=True,
        description="Whether to union tags from source into target (legacy compatibility).",
    )


class POIMergeResponse(StrictBaseModel):
    """Result of an atomic POI merge operation."""

    id: UUID | None = Field(
        default=None,
        description="Canonical target POI ID (legacy compatibility).",
    )
    target_poi: POIReadResponse = Field(
        ...,
        description="Updated target POI containing synthesized scalar and set attributes.",
    )
    deleted_source_poi_id: UUID | None = Field(
        default=None,
        description="Source POI ID that was deleted, or None if source was an in-memory draft.",
    )
    reparented_itinerary_items_count: int = Field(
        default=0,
        description="Number of itinerary_items records re-parented to the target POI.",
    )
    reparented_list_memberships_count: int = Field(
        default=0,
        description="Number of curated list memberships re-parented to the target POI.",
    )
    reparented_child_pois_count: int = Field(
        default=0,
        description="Number of child POIs whose parent_poi_id was updated to target POI.",
    )
