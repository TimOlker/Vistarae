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

"""Pure domain aggregates and business entities.

Encapsulates state and business rules decoupled from external ORM frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from vistarae_core.domain.value_objects import (
    AddressRecord,
    DuplicateTriageStatus,
    EnrichmentStatus,
    IdempotencyStatus,
    IngestJobStatus,
    PacingMode,
    SourceType,
    ThemeMode,
    TransitSpeedMode,
    UserTier,
    VisitState,
    WGS84Point,
)


@dataclass
class User:
    """Core tenant anchor entity."""

    id: UUID
    cognito_sub: str
    email: str
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class UserPreferences:
    """Partitioned tenant configuration across Account/UI, POI, and Planner modes."""

    user_id: UUID
    theme: ThemeMode = ThemeMode.SYSTEM
    email_notifications_enabled: bool = True
    push_notifications_enabled: bool = True
    marketing_emails_enabled: bool = False

    clustering_enabled: bool = True
    clustering_radius_meters: int = 50
    default_map_layer: str = "standard"
    geoproximity_scope_km: float = 25.0
    pin_color_presets: dict[str, str] = field(
        default_factory=lambda: {
            "favorite": "#E11D48",
            "dream": "#8B5CF6",
            "visited": "#10B981",
            "default": "#3B82F6",
        }
    )

    pacing: PacingMode = PacingMode.MODERATE
    meal_intervals_hours: float = 4.0
    lunch_packing_enabled: bool = False
    transit_speed_mode: TransitSpeedMode = TransitSpeedMode.WALKING
    daily_activity_hour_cap: float = 8.0
    preferred_currency: str = "USD"

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class UserMetric:
    """Aggregate utilization and consumption telemetry."""

    user_id: UUID
    poi_count: int = 0
    total_tokens_consumed: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class UserQuota:
    """Tenant governance and rolling rate limiting state."""

    user_id: UUID
    monthly_token_quota: int = 50000
    current_token_usage: int = 0
    tier: UserTier = UserTier.LOW
    request_count: int = 0
    window_start_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_disabled: bool = False
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_available_tokens(self) -> bool:
        """Checks if current token usage remains below monthly quota.

        Returns:
            True if tokens remain available, False otherwise.
        """
        return self.current_token_usage < self.monthly_token_quota


@dataclass
class IdempotencyRecord:
    """Tracking entity for duplicate mutation prevention."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    idempotency_key: str = ""
    status: IdempotencyStatus = IdempotencyStatus.PENDING
    response_code: int | None = None
    response_payload: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class POI:
    """Point of Interest root aggregate."""

    id: UUID
    user_id: UUID
    name: str
    geom: WGS84Point
    parent_poi_id: UUID | None = None
    parent_poi_name: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    states: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    addresses: list[AddressRecord] = field(default_factory=list)
    official_url: str | None = None
    wiki_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    directory_paths: list[str] = field(default_factory=list)
    creation_metadata: dict[str, Any] = field(default_factory=dict)
    visit_state: VisitState = VisitState.NOT_VISITED
    visited_dates: list[str] = field(default_factory=list)
    want_to_visit_again: bool = False
    already_visited: bool = False
    visit_pending: bool = True
    source_type: SourceType | str = SourceType.MANUAL
    source_value: str | None = None
    rating: int | None = None
    estimated_cost: Decimal | None = None
    pricing_unit: str | None = None
    recommended_duration_hours: Decimal | None = None
    recommended_visit_days: int = 1
    enrichment_status: EnrichmentStatus = EnrichmentStatus.SUCCESS
    region_geom: str | None = None
    embedding: list[float] | None = None
    embedding_md5: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Enforces deterministic visit lifecycle calculation per REQ-EDIT-011."""
        has_visited = len(self.visited_dates) > 0
        self.already_visited = has_visited
        self.visit_pending = (not has_visited) or bool(self.want_to_visit_again)
        if isinstance(self.source_type, str):
            try:
                self.source_type = SourceType(self.source_type)
            except ValueError:
                self.source_type = SourceType.MANUAL


@dataclass
class ListEntity:
    """Curated collection of POIs."""

    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    is_public: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TagEntity:
    """User-scoped taxonomy marker."""

    id: UUID
    user_id: UUID
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class GeocodingCacheEntry:
    """Cached geocoding result keyed by SHA-256 query hash."""

    query_hash: str
    lat: float
    lon: float
    formatted_address: str
    status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(days=90))


@dataclass
class PotentialDuplicateMatch:
    """Represents a flagged collision during deduplication checks."""

    existing_poi: POI
    distance_meters: float
    name_similarity: float
    match_confidence: float


@dataclass
class IngestJob:
    """Asynchronous ingestion job aggregate."""

    id: UUID
    user_id: UUID
    job_status: IngestJobStatus
    total_rows: int = 0
    processed_rows: int = 0
    duplicate_payloads: list[dict[str, Any]] = field(default_factory=list)
    target_list_id: UUID | None = None
    error_summary: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def percent_complete(self) -> float:
        """Calculates job completion percentage."""
        if self.total_rows <= 0:
            if self.job_status in (IngestJobStatus.COMPLETED, IngestJobStatus.PARTIAL_SUCCESS):
                return 100.0
            return 0.0
        return round((self.processed_rows / self.total_rows) * 100.0, 2)


@dataclass
class DuplicatePayloadItem:
    """Suspected duplicate record discovered during batch ingestion."""

    row_number: int
    raw_name: str
    candidate_poi_id: UUID
    match_type: str
    similarity_score: float
    distance_meters: float
    triage_status: DuplicateTriageStatus
    staged_poi_data: dict[str, Any]


@dataclass
class IngestRowMessage:
    """Individual CSV row payload dispatched to SQS queue."""

    job_id: UUID
    user_id: UUID
    absolute_row_number: int
    row_data: dict[str, str]
    target_list_id: UUID | None = None
