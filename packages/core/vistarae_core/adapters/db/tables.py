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

"""SQLAlchemy 2.0 ORM table definitions for all Vistarae tenant entities.

Implements Constitution Principle 3 & 4:
- All enum fields use VARCHAR(n) backed by Python StrEnum (no PostgreSQL ENUM)
- All child tables reference users(id) ON DELETE CASCADE
- Idempotency uniqueness enforced at DB level via UniqueConstraint
- No Row-Level Security — enforced via explicit WHERE user_id predicates
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography, Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vistarae_core.adapters.db.base import Base


class UserTable(Base):
    """Tenant anchor record — core identity and profile."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    cognito_sub: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships (convenience — not required for repo queries)
    preferences: Mapped[UserPreferencesTable | None] = relationship(
        "UserPreferencesTable",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    metrics: Mapped[UserMetricsTable | None] = relationship(
        "UserMetricsTable",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    quotas: Mapped[UserQuotasTable | None] = relationship(
        "UserQuotasTable",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    idempotency_keys: Mapped[list[IdempotencyKeysTable]] = relationship(
        "IdempotencyKeysTable",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    prompts: Mapped[list[UserPromptTable]] = relationship(
        "UserPromptTable",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("cognito_sub", name="uq_users_cognito_sub"),
        Index("idx_users_cognito_sub", "cognito_sub"),
        Index("idx_users_email", "email"),
    )


class UserPreferencesTable(Base):
    """Partitioned tenant configuration — UI, POI, and Planner preferences."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    # ── Account / UI ────────────────────────────────────────────────────────
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    marketing_emails_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── POI Mode ────────────────────────────────────────────────────────────
    clustering_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    clustering_radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    default_map_layer: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    geoproximity_scope_km: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    pin_color_presets: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "favorite": "#E11D48",
            "dream": "#8B5CF6",
            "visited": "#10B981",
            "default": "#3B82F6",
        },
    )

    # ── Planner Mode ────────────────────────────────────────────────────────
    pacing: Mapped[str] = mapped_column(String(16), nullable=False, default="moderate")
    meal_intervals_hours: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    lunch_packing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    transit_speed_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="walking")
    daily_activity_hour_cap: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    preferred_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # ── Extension / Scraping ────────────────────────────────────────────────
    valid_scraping_domains: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: [
            "wikipedia.org",
            "tripadvisor.com",
            "atlasobscura.com",
            "google.com/maps",
            "roadtrippers.com",
        ],
        server_default=text(
            '\'["wikipedia.org", "tripadvisor.com", "atlasobscura.com", "google.com/maps", "roadtrippers.com"]\'::jsonb'
        ),
    )

    # ── Unique User Context ──────────────────────────────────────────────────
    travel_style_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="preferences")

    __table_args__ = (
        CheckConstraint("theme IN ('light', 'dark', 'system')", name="ck_user_prefs_theme"),
        CheckConstraint(
            "pacing IN ('relaxed', 'moderate', 'fast_paced')", name="ck_user_prefs_pacing"
        ),
        CheckConstraint(
            "transit_speed_mode IN ('walking', 'bicycling', 'transit', 'driving')",
            name="ck_user_prefs_transit",
        ),
        CheckConstraint(
            "clustering_radius_meters BETWEEN 10 AND 500",
            name="ck_user_prefs_clustering_radius",
        ),
        CheckConstraint(
            "meal_intervals_hours BETWEEN 1.0 AND 8.0",
            name="ck_user_prefs_meal_intervals",
        ),
        CheckConstraint(
            "daily_activity_hour_cap BETWEEN 1.0 AND 18.0",
            name="ck_user_prefs_daily_cap",
        ),
    )


class UserMetricsTable(Base):
    """Aggregate utilization and consumption counters."""

    __tablename__ = "user_metrics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    poi_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="metrics")


class UserQuotasTable(Base):
    """Governance allocation, rolling rate limiting state, and disablement flag."""

    __tablename__ = "user_quotas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    monthly_token_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=50000)
    current_token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="quotas")

    __table_args__ = (
        CheckConstraint("tier IN ('low', 'high', 'admin')", name="ck_user_quotas_tier"),
        Index("idx_user_quotas_tier", "tier"),
    )


class IdempotencyKeysTable(Base):
    """Duplicate mutation prevention via database-backed key locking."""

    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="idempotency_keys")

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_idempotency_user_key"),
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')", name="ck_idempotency_status"
        ),
        Index("idx_idempotency_keys_created_at", "created_at"),
    )


class UserPromptTable(Base):
    """Personalized prompt directives decomposed by LLM from user travel style."""

    __tablename__ = "user_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[UserTable] = relationship("UserTable", back_populates="prompts")

    __table_args__ = (
        UniqueConstraint("user_id", "prompt_type", name="uq_user_prompts_user_type"),
        CheckConstraint(
            "prompt_type IN ('description', 'reason_to_visit', 'time_spent')",
            name="ck_user_prompts_type",
        ),
        Index("idx_user_prompts_user_id", "user_id"),
    )


class POITable(Base):
    """Point of interest aggregate record with geospatial indices."""

    __tablename__ = "pois"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_to_visit: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    states: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    countries: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    addresses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Manual",
        server_default=text("'Manual'"),
    )
    source_value: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wiki_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    directory_paths: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    creation_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    visit_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_visited",
        server_default=text("'not_visited'"),
    )
    visited_dates: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    want_to_visit_again: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
    )
    already_visited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
    )
    visit_pending: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    pricing_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    recommended_duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    recommended_visit_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    estimated_visit_time_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="SUCCESS",
        server_default=text("'SUCCESS'"),
    )
    geom: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    region_geom: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    embedding_md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    parent: Mapped[POITable | None] = relationship(
        "POITable", remote_side=[id], back_populates="children"
    )
    children: Mapped[list[POITable]] = relationship("POITable", back_populates="parent")
    lists: Mapped[list[ListTable]] = relationship(
        "ListTable", secondary="poi_lists", back_populates="pois"
    )
    tags: Mapped[list[TagTable]] = relationship(
        "TagTable", secondary="poi_tags", back_populates="pois"
    )

    __table_args__ = (
        CheckConstraint(
            "visit_state IN ('not_visited', 'visited_do_not_return', 'visited_return')",
            name="ck_pois_visit_state",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_pois_rating",
        ),
        CheckConstraint(
            "recommended_duration_hours IS NULL OR (recommended_duration_hours >= 0.25 AND recommended_duration_hours <= 12.00)",
            name="ck_pois_duration",
        ),
        CheckConstraint(
            "enrichment_status IN ('SUCCESS', 'PARTIAL', 'FAILED')",
            name="ck_pois_enrichment",
        ),
        CheckConstraint(
            "parent_poi_id IS NULL OR parent_poi_id != id",
            name="chk_pois_parent_not_self",
        ),
        Index("idx_pois_parent_poi_id", "parent_poi_id"),
        Index("idx_pois_user_parent", "user_id", "parent_poi_id"),
        Index(
            "idx_pois_addresses_path",
            "addresses",
            postgresql_using="gin",
            postgresql_ops={"addresses": "jsonb_path_ops"},
        ),
        Index("idx_pois_states_gin", "states", postgresql_using="gin"),
        Index("idx_pois_countries_gin", "countries", postgresql_using="gin"),
        Index("idx_pois_user_geom", "user_id", "geom", postgresql_using="gist"),
        Index(
            "idx_pois_user_geom_geometry",
            "user_id",
            text("(geom::geometry)"),
            postgresql_using="gist",
        ),
        Index(
            "idx_pois_name_trgm",
            text("name gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "idx_pois_reason_to_visit_trgm",
            text("reason_to_visit gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "idx_pois_description_trgm",
            text("description gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "idx_pois_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ListTable(Base):
    """Curated collection of POIs."""

    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    pois: Mapped[list[POITable]] = relationship(
        "POITable", secondary="poi_lists", back_populates="lists"
    )

    __table_args__ = (Index("idx_lists_user_id", "user_id"),)


class POIListTable(Base):
    """Association table linking POIs and Lists."""

    __tablename__ = "poi_lists"

    poi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="CASCADE"),
        primary_key=True,
    )
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TagTable(Base):
    """User-scoped taxonomy marker."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pois: Mapped[list[POITable]] = relationship(
        "POITable", secondary="poi_tags", back_populates="tags"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_tags_user_slug"),
        UniqueConstraint("user_id", "name", name="uq_tags_user_name"),
        Index("idx_tags_user_id", "user_id"),
        Index("idx_tags_user_slug", "user_id", "slug"),
    )


class POITagTable(Base):
    """Association table linking POIs and Tags."""

    __tablename__ = "poi_tags"

    poi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )


class GeocodingCacheTable(Base):
    """Cached geocoding result keyed by SHA-256 query hash."""

    __tablename__ = "geocoding_cache"

    query_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    formatted_address: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_geocoding_cache_expires_at", "expires_at"),)


class IngestJobTable(Base):
    """Tracks asynchronous bulk CSV ingestion jobs and duplicate triage."""

    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_status: Mapped[str] = mapped_column(String(16), nullable=False)
    total_rows: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    processed_rows: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    duplicate_payloads: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    target_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lists.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_summary: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "job_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED')",
            name="ck_ingest_jobs_status",
        ),
        Index("idx_ingest_jobs_user_created", "user_id", text("created_at DESC")),
        Index("idx_ingest_jobs_id_user", "id", "user_id"),
    )


class ItineraryTable(Base):
    """Itinerary container table owned by tenant user."""

    __tablename__ = "itineraries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    budget_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), server_default="USD", default="USD", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), server_default="draft", default="draft", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    days: Mapped[list[ItineraryDayTable]] = relationship(
        "ItineraryDayTable",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryDayTable.day_number",
    )

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_itineraries_dates"),
        CheckConstraint("budget_cents IS NULL OR budget_cents >= 0", name="ck_itineraries_budget"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'archived')", name="ck_itineraries_status"
        ),
        Index("idx_itineraries_user_id", "user_id"),
        Index("idx_itineraries_user_status", "user_id", "status"),
    )


class ItineraryDayTable(Base):
    """Daily schedule breakdown within an itinerary."""

    __tablename__ = "itinerary_days"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_budget_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_cents: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )

    itinerary: Mapped[ItineraryTable] = relationship("ItineraryTable", back_populates="days")
    items: Mapped[list[ItineraryItemTable]] = relationship(
        "ItineraryItemTable",
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="ItineraryItemTable.order_index",
    )

    __table_args__ = (
        UniqueConstraint("itinerary_id", "day_number", name="uq_itinerary_days_day_num"),
        CheckConstraint("day_number > 0", name="ck_itinerary_days_positive"),
        Index("idx_itinerary_days_itinerary_id", "itinerary_id"),
    )


class ItineraryItemTable(Base):
    """Scheduled activity item or POI reference within an itinerary day."""

    __tablename__ = "itinerary_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    itinerary_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("itinerary_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_backup_for_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("itinerary_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), server_default="attraction", default="attraction", nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(32), server_default="USER_SAVED", default="USER_SAVED", nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geography(
            geometry_type="POINT",
            srid=4326,
            from_text="ST_GeogFromText",
            name="geography",
            spatial_index=False,
            nullable=False,
        ),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), server_default="1.00", default=Decimal("1.00"), nullable=False
    )
    cost_cents: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    travel_time_prev_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    travel_distance_prev_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped[ItineraryDayTable] = relationship("ItineraryDayTable", back_populates="items")
    poi: Mapped[POITable | None] = relationship("POITable")

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('USER_SAVED', 'AI_RECOMMENDED', 'MANUAL')",
            name="ck_itinerary_items_source",
        ),
        CheckConstraint(
            "duration_hours >= 0.25 AND duration_hours <= 12.00",
            name="ck_itinerary_items_duration",
        ),
        CheckConstraint("cost_cents >= 0", name="ck_itinerary_items_cost"),
        Index("idx_itinerary_items_day_order", "itinerary_day_id", "order_index"),
        Index("idx_itinerary_items_poi_id", "poi_id"),
        Index("idx_itinerary_items_backup", "is_backup_for_id"),
        Index("idx_itinerary_items_geom", "geom", postgresql_using="gist"),
    )


class SystemSettingsTable(Base):
    """Runtime system configurations and killswitch flags."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class FilterRuleTable(Base):
    """User-persisted POI search profile, table view configuration, and map pin coloring rules."""

    __tablename__ = "filter_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    query_tree: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    table_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    pin_color_scheme: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_filter_rules_user_name"),
        Index("ix_filter_rules_user_id_name", "user_id", "name"),
    )


class IngestCandidateTable(Base):
    """PostgreSQL staging table for two-phase interactive CSV/photo ingestion (T-006)."""

    __tablename__ = "ingest_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    poi_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recommended_disposition: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'accept'"),
        default="accept",
        nullable=False,
    )
    user_disposition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_existing_poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pois.id", ondelete="SET NULL"),
        nullable=True,
    )
    geom: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=True,
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    street_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    addresses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    dates_visited: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    photo_directory: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), default=0, nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_to_visit: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wiki_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    recommended_visit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_visit_time_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_coordinates: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False, nullable=False
    )
    is_skipped: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), default=False, nullable=False
    )
    phase_state: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'phase_1_triage'"),
        default="phase_1_triage",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_ingest_candidates_user_job", "user_id", "job_id"),
        Index("idx_ingest_candidates_geom", "geom", postgresql_using="gist"),
    )


ingest_candidates_table = IngestCandidateTable.__table__


class UserExclusionZoneTable(Base):
    """Geographic exclusion zones for user privacy (home, school, workplace, etc.)."""

    __tablename__ = "user_exclusion_zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_user_exclusion_zones_user", "user_id"),
    )


user_exclusion_zones_table = UserExclusionZoneTable.__table__
