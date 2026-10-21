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

"""Pydantic v2 boundary schemas for Trip Planner itineraries, days, items, and advisories.

Enforces Constitution Principle 5:
- Inherits from StrictBaseModel with extra='forbid'
- Verbatim field constraints for coordinate bounds, time slots, integer cents
- Validation for trip duration and date ordering
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from vistarae_core.schemas.base import StrictBaseModel


class ItineraryStatus(StrEnum):
    """Itinerary state transition status."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class ItineraryItemSource(StrEnum):
    """Source classification for scheduled itinerary items."""

    USER_SAVED = "USER_SAVED"
    AI_RECOMMENDED = "AI_RECOMMENDED"
    MANUAL = "MANUAL"


class ItineraryItemBase(StrictBaseModel):
    """Base fields for scheduled itinerary activity or POI item."""

    title: str = Field(..., max_length=255)
    category: str = Field(default="attraction", max_length=64)
    source_type: ItineraryItemSource = Field(default=ItineraryItemSource.USER_SAVED)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    order_index: int = Field(..., ge=0)
    start_time: time | None = None
    end_time: time | None = None
    duration_hours: Decimal = Field(
        default=Decimal("1.00"), ge=Decimal("0.25"), le=Decimal("12.00")
    )
    cost_cents: int = Field(default=0, ge=0)
    travel_time_prev_minutes: int | None = Field(default=None, ge=0)
    travel_distance_prev_meters: int | None = Field(default=None, ge=0)
    notes: str | None = None
    poi_id: UUID | None = None
    is_backup_for_id: UUID | None = None


class ItineraryItemCreate(ItineraryItemBase):
    """Payload to create an itinerary item."""

    pass


class ItineraryItemResponse(ItineraryItemBase):
    """Response payload for a persisted itinerary item."""

    id: UUID
    itinerary_day_id: UUID


class ItineraryDayBase(StrictBaseModel):
    """Base daily schedule breakdown within an itinerary."""

    day_number: int = Field(..., ge=1)
    calendar_date: date
    notes: str | None = None
    target_budget_cents: int | None = Field(default=None, ge=0)


class ItineraryDayCreate(ItineraryDayBase):
    """Payload to create an itinerary day with items."""

    items: list[ItineraryItemCreate] = Field(default_factory=list)


class ItineraryDayResponse(ItineraryDayBase):
    """Response payload for an itinerary day with populated items."""

    id: UUID
    itinerary_id: UUID
    total_cost_cents: int = 0
    items: list[ItineraryItemResponse] = Field(default_factory=list)


class ItineraryCreate(StrictBaseModel):
    """Manual itinerary creation payload."""

    title: str = Field(..., min_length=1, max_length=255)
    destination: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    budget_cents: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    days: list[ItineraryDayCreate] = Field(default_factory=list)

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date: date, info) -> date:
        """Validates that end_date is on or after start_date and <= 30 days duration."""
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        if start_date and (end_date - start_date).days > 30:
            raise ValueError("Trips cannot exceed 30 days in duration")
        return end_date


class ItineraryUpdate(StrictBaseModel):
    """Payload for updating itinerary metadata."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    destination: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    budget_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: ItineraryStatus | None = None


class ItineraryGenerateRequest(StrictBaseModel):
    """Request payload for AI natural language prompt + PostGIS pgvector RAG itinerary generation."""

    prompt: str = Field(..., min_length=3, max_length=1000)
    destination: str = Field(..., min_length=2, max_length=255)
    start_date: date
    end_date: date
    budget_cents: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date: date, info) -> date:
        """Validates date range and max duration <= 30 days."""
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        if start_date and (end_date - start_date).days > 30:
            raise ValueError("Trips cannot exceed 30 days in duration")
        return end_date


class ItineraryItemReorderItem(StrictBaseModel):
    """Single item position specification in batch reorder."""

    item_id: UUID
    itinerary_day_id: UUID
    order_index: int = Field(..., ge=0)
    start_time: time | None = None
    end_time: time | None = None


class ItineraryItemReorderRequest(StrictBaseModel):
    """Batch reorder request across days and time slots."""

    items: list[ItineraryItemReorderItem]


class MissingMealAdvisory(StrictBaseModel):
    """Advisory emitted when lunch or dinner window lacks a meal."""

    day_number: int
    meal_type: str  # "lunch" or "dinner"
    gap_start: time
    gap_end: time
    suggested_poi_id: UUID | None = None
    suggested_poi_title: str | None = None
    suggested_poi_address: str | None = None
    suggested_poi_lat: float | None = None
    suggested_poi_lng: float | None = None


class CircuitBreakerWarning(StrictBaseModel):
    """Warning emitted when active daily exploration exceeds circuit breaker threshold."""

    day_number: int
    total_active_hours: Decimal
    threshold_hours: Decimal = Decimal("10.00")
    message: str


class ItinerarySummary(StrictBaseModel):
    """High-level summary of an itinerary for listing views."""

    id: UUID
    user_id: UUID
    title: str
    destination: str
    start_date: date
    end_date: date
    budget_cents: int | None
    currency: str
    status: ItineraryStatus
    total_estimated_cost_cents: int
    total_days: int
    total_activities: int
    created_at: datetime
    updated_at: datetime


class ItineraryResponse(StrictBaseModel):
    """Complete detail response for an itinerary with days, items, and smart advisories."""

    id: UUID
    user_id: UUID
    title: str
    destination: str
    start_date: date
    end_date: date
    budget_cents: int | None
    currency: str
    status: ItineraryStatus
    total_estimated_cost_cents: int
    days: list[ItineraryDayResponse]
    advisories: list[MissingMealAdvisory] = Field(default_factory=list)
    circuit_breaker_warnings: list[CircuitBreakerWarning] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
