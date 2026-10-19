# Copyright (c) 2026 Vistarae. All rights reserved.
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
    EnrichmentStatus,
    IdempotencyStatus,
    PacingMode,
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
    description: str | None = None
    address: str | None = None
    city: str | None = None
    states: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    official_url: str | None = None
    wiki_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    directory_paths: list[str] = field(default_factory=list)
    creation_metadata: dict[str, Any] = field(default_factory=dict)
    visit_state: VisitState = VisitState.NOT_VISITED
    visited_dates: list[str] = field(default_factory=list)
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
