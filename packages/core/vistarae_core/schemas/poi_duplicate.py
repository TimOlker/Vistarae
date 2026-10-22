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

"""Pydantic v2 schemas for pre-save duplicate collision checks (T-027)."""

from uuid import UUID

from pydantic import Field

from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.poi import POIReadResponse


class DuplicateCandidateItem(StrictBaseModel):
    """Details of a potential duplicate collision candidate."""

    poi_id: UUID = Field(..., description="UUID of collision candidate POI")
    name: str = Field(..., description="Canonical name of candidate POI")
    distance_meters: float = Field(
        ..., description="Geodesic distance in meters (threshold <= 200m)"
    )
    name_similarity: float = Field(
        ..., description="Trigram name similarity score (threshold >= 0.60)"
    )
    poi: POIReadResponse | None = Field(
        default=None, description="Full POI entity representation for visual preview"
    )


class DuplicateCheckRequest(StrictBaseModel):
    """Payload for probing duplicate collisions before saving a draft."""

    name: str = Field(..., min_length=1, max_length=255, description="Draft POI name")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees WGS-84")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees WGS-84")
    exclude_poi_id: UUID | None = Field(
        default=None,
        description="Active POI ID to exclude from collision detection (self-exclusion)",
    )


class DuplicateCheckResponse(StrictBaseModel):
    """Result of pre-save duplicate collision detection."""

    is_duplicate: bool = Field(
        ..., description="True if collision within <= 200m and similarity >= 0.60"
    )
    candidate: DuplicateCandidateItem | None = Field(
        default=None, description="Closest collision candidate details"
    )
