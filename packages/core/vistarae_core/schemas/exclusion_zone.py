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

"""Pydantic v2 schemas for User Privacy Exclusion Zones."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExclusionZoneCreateRequest(BaseModel):
    """Payload to create a new geographic privacy exclusion zone."""

    name: str = Field(..., min_length=1, max_length=100, description="Zone label, e.g. Home or Workplace")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Center latitude in WGS-84")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Center longitude in WGS-84")
    radius_km: float = Field(default=1.0, gt=0.0, le=100.0, description="Exclusion radius in kilometers")


class ExclusionZoneUpdateRequest(BaseModel):
    """Payload to update an existing exclusion zone."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    radius_km: float | None = Field(default=None, gt=0.0, le=100.0)


class ExclusionZoneResponse(BaseModel):
    """Representation of a persisted user privacy exclusion zone."""

    id: UUID
    name: str
    latitude: float
    longitude: float
    radius_km: float
    created_at: datetime
    updated_at: datetime


class ExclusionZoneListResponse(BaseModel):
    """Collection of user exclusion zones."""

    items: list[ExclusionZoneResponse] = Field(default_factory=list)


class ExclusionCheckRequest(BaseModel):
    """Payload to check whether coordinates fall within an exclusion zone."""

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class ExclusionCheckResponse(BaseModel):
    """Result of checking a geographic coordinate against user exclusion zones."""

    is_excluded: bool = False
    matched_zones: list[ExclusionZoneResponse] = Field(default_factory=list)
    matched_zone_names: list[str] = Field(default_factory=list)

