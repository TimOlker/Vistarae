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

"""Sub-domain user preferences boundary schemas.

Partitions preferences into Account/UI, POI Mode, and Planner Mode domains
with strict field validation bounds per REQ-FOUND-008 and data-model.md.
"""

from __future__ import annotations

from pydantic import Field

from vistarae_core.domain.value_objects import (
    PacingMode,
    ThemeMode,
    TransitSpeedMode,
)
from vistarae_core.schemas.base import StrictBaseModel


class UIPreferencesResponse(StrictBaseModel):
    """Account and user interface presentation preferences."""

    theme: ThemeMode
    email_notifications_enabled: bool
    push_notifications_enabled: bool
    marketing_emails_enabled: bool


class UpdateUIPreferencesRequest(StrictBaseModel):
    """Payload to update account and presentation preferences."""

    theme: ThemeMode | None = None
    email_notifications_enabled: bool | None = None
    push_notifications_enabled: bool | None = None
    marketing_emails_enabled: bool | None = None


class POIPreferencesResponse(StrictBaseModel):
    """POI capture and map rendering preferences."""

    clustering_enabled: bool
    clustering_radius_meters: int = Field(..., ge=10, le=500)
    default_map_layer: str = Field(..., max_length=32)
    geoproximity_scope_km: float = Field(..., ge=1.0, le=500.0)
    pin_color_presets: dict[str, str]


class UpdatePOIPreferencesRequest(StrictBaseModel):
    """Payload to update POI capture and map rendering preferences."""

    clustering_enabled: bool | None = None
    clustering_radius_meters: int | None = Field(None, ge=10, le=500)
    default_map_layer: str | None = Field(None, max_length=32)
    geoproximity_scope_km: float | None = Field(None, ge=1.0, le=500.0)
    pin_color_presets: dict[str, str] | None = None


class PlannerPreferencesResponse(StrictBaseModel):
    """Itinerary and trip planning pacing preferences."""

    pacing: PacingMode
    meal_intervals_hours: float = Field(..., ge=1.0, le=8.0)
    lunch_packing_enabled: bool
    transit_speed_mode: TransitSpeedMode
    daily_activity_hour_cap: float = Field(..., ge=1.0, le=18.0)
    preferred_currency: str = Field(..., min_length=3, max_length=3)


class UpdatePlannerPreferencesRequest(StrictBaseModel):
    """Payload to update itinerary planning pacing preferences."""

    pacing: PacingMode | None = None
    meal_intervals_hours: float | None = Field(None, ge=1.0, le=8.0)
    lunch_packing_enabled: bool | None = None
    transit_speed_mode: TransitSpeedMode | None = None
    daily_activity_hour_cap: float | None = Field(None, ge=1.0, le=18.0)
    preferred_currency: str | None = Field(None, min_length=3, max_length=3)


class UserPreferencesResponse(StrictBaseModel):
    """Aggregated representation of all tenant sub-domain preferences."""

    ui: UIPreferencesResponse
    poi: POIPreferencesResponse
    planner: PlannerPreferencesResponse
