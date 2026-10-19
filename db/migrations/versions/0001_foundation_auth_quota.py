# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Initial foundation schema: tenant tables, extensions, indices, and constraints.

Revision ID: 0001
Revises: None
Create Date: 2026-10-19

Implements Constitution Principles 3 & 4:
- Enables uuid-ossp, postgis, btree_gist, vector extensions
- Creates users, user_preferences, user_metrics, user_quotas, idempotency_keys
- All VARCHAR enum columns protected by CHECK constraints (no PostgreSQL ENUM)
- All child tables reference users(id) ON DELETE CASCADE
- Fully reversible downgrade() — no-op downgrade strictly forbidden
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates all foundation tables, extensions, indices, and check constraints."""
    # ── 1. Extensions ──────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist"')
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
                CREATE EXTENSION IF NOT EXISTS "vector";
            END IF;
        END $$;
        """
    )

    # ── 2. users ───────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cognito_sub", sa.String(256), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cognito_sub", name="uq_users_cognito_sub"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_cognito_sub", "users", ["cognito_sub"])
    op.create_index("idx_users_email", "users", ["email"])

    # ── 3. user_preferences ────────────────────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "push_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "marketing_emails_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "clustering_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")
        ),
        sa.Column("clustering_radius_meters", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("default_map_layer", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("geoproximity_scope_km", sa.Float(), nullable=False, server_default="25.0"),
        sa.Column(
            "pin_color_presets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                """'{"favorite":"#E11D48","dream":"#8B5CF6","visited":"#10B981","default":"#3B82F6"}'::jsonb"""
            ),
        ),
        sa.Column("pacing", sa.String(16), nullable=False, server_default="moderate"),
        sa.Column("meal_intervals_hours", sa.Float(), nullable=False, server_default="4.0"),
        sa.Column(
            "lunch_packing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
        sa.Column("transit_speed_mode", sa.String(16), nullable=False, server_default="walking"),
        sa.Column("daily_activity_hour_cap", sa.Float(), nullable=False, server_default="8.0"),
        sa.Column("preferred_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_prefs_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("theme IN ('light', 'dark', 'system')", name="ck_user_prefs_theme"),
        sa.CheckConstraint(
            "pacing IN ('relaxed', 'moderate', 'fast_paced')", name="ck_user_prefs_pacing"
        ),
        sa.CheckConstraint(
            "transit_speed_mode IN ('walking', 'bicycling', 'transit', 'driving')",
            name="ck_user_prefs_transit",
        ),
        sa.CheckConstraint(
            "clustering_radius_meters BETWEEN 10 AND 500",
            name="ck_user_prefs_clustering_radius",
        ),
        sa.CheckConstraint(
            "meal_intervals_hours BETWEEN 1.0 AND 8.0",
            name="ck_user_prefs_meal_intervals",
        ),
        sa.CheckConstraint(
            "daily_activity_hour_cap BETWEEN 1.0 AND 18.0",
            name="ck_user_prefs_daily_cap",
        ),
    )

    # ── 4. user_metrics ────────────────────────────────────────────────────
    op.create_table(
        "user_metrics",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poi_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_metrics_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # ── 5. user_quotas ─────────────────────────────────────────────────────
    op.create_table(
        "user_quotas",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monthly_token_quota", sa.Integer(), nullable=False, server_default="50000"),
        sa.Column("current_token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(16), nullable=False, server_default="low"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "window_start_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_quotas_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("tier IN ('low', 'high', 'admin')", name="ck_user_quotas_tier"),
    )
    op.create_index("idx_user_quotas_tier", "user_quotas", ["tier"])

    # ── 6. idempotency_keys ────────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_idempotency_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_idempotency_user_key"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')", name="ck_idempotency_status"
        ),
    )
    op.create_index("idx_idempotency_keys_created_at", "idempotency_keys", ["created_at"])


def downgrade() -> None:
    """Drops all foundation tables and indices in reverse dependency order.

    Fully reversible — no data-loss guard or partial downgrade patterns.
    Extensions are left in place as they may be shared across schemas.
    """
    # Drop in reverse dependency order (children before parent).
    op.drop_index("idx_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_index("idx_user_quotas_tier", table_name="user_quotas")
    op.drop_table("user_quotas")

    op.drop_table("user_metrics")
    op.drop_table("user_preferences")

    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_users_cognito_sub", table_name="users")
    op.drop_table("users")
