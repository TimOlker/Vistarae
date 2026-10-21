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

"""Pure domain aggregates and business entities for Trip Planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4


class ItineraryStatus(StrEnum):
    """Itinerary lifecycle state."""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class ItineraryItemSource(StrEnum):
    """Source classification of scheduled activities."""

    USER_SAVED = "USER_SAVED"
    AI_RECOMMENDED = "AI_RECOMMENDED"
    MANUAL = "MANUAL"


@dataclass
class ItineraryItem:
    """Scheduled activity item or POI reference within a day."""

    id: UUID = field(default_factory=uuid4)
    itinerary_day_id: UUID | None = None
    poi_id: UUID | None = None
    is_backup_for_id: UUID | None = None
    title: str = ""
    category: str = "attraction"
    source_type: ItineraryItemSource = ItineraryItemSource.USER_SAVED
    latitude: float = 0.0
    longitude: float = 0.0
    order_index: int = 0
    start_time: time | None = None
    end_time: time | None = None
    duration_hours: Decimal = Decimal("1.00")
    cost_cents: int = 0
    travel_time_prev_minutes: int | None = None
    travel_distance_prev_meters: int | None = None
    notes: str | None = None


@dataclass
class ItineraryDay:
    """Daily schedule breakdown within an itinerary."""

    id: UUID = field(default_factory=uuid4)
    itinerary_id: UUID | None = None
    day_number: int = 1
    calendar_date: date = field(default_factory=date.today)
    notes: str | None = None
    target_budget_cents: int | None = None
    total_cost_cents: int = 0
    items: list[ItineraryItem] = field(default_factory=list)


@dataclass
class Itinerary:
    """Root aggregate for travel itineraries."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID | None = None
    title: str = ""
    destination: str = ""
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)
    budget_cents: int | None = None
    currency: str = "USD"
    status: ItineraryStatus = ItineraryStatus.DRAFT
    days: list[ItineraryDay] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_estimated_cost_cents(self) -> int:
        """Calculates total cost across all scheduled items."""
        return sum(item.cost_cents for day in self.days for item in day.items)
