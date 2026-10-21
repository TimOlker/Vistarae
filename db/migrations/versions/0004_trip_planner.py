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

"""Trip Planner itineraries, days, items, and system_settings tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20

Implements Phase 6 Requirements (REQ-PLAN-001, REQ-PLAN-010, REQ-PLAN-011, REQ-PLAN-018, REQ-SAM-017)
and Constitution Invariants:
- Creates table itineraries with user_id foreign key cascading on delete to users
- Creates table itinerary_days with itinerary_id foreign key cascading on delete
- Creates table itinerary_items with geography(Point, 4326) coordinates and self-referential backup FK
- Creates table system_settings for operational runtime flags (SpendKillSwitch)
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates itineraries, itinerary_days, itinerary_items, and system_settings tables."""
    # 1. itineraries table
    op.create_table(
        "itineraries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("budget_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_date >= start_date", name="ck_itineraries_dates"),
        sa.CheckConstraint(
            "budget_cents IS NULL OR budget_cents >= 0", name="ck_itineraries_budget"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'archived')", name="ck_itineraries_status"
        ),
    )
    op.create_index("idx_itineraries_user_id", "itineraries", ["user_id"])
    op.create_index("idx_itineraries_user_status", "itineraries", ["user_id", "status"])

    # 2. itinerary_days table
    op.create_table(
        "itinerary_days",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("itinerary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("target_budget_cents", sa.Integer(), nullable=True),
        sa.Column("total_cost_cents", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("itinerary_id", "day_number", name="uq_itinerary_days_day_num"),
        sa.CheckConstraint("day_number > 0", name="ck_itinerary_days_positive"),
    )
    op.create_index("idx_itinerary_days_itinerary_id", "itinerary_days", ["itinerary_id"])

    # 3. itinerary_items table
    op.create_table(
        "itinerary_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("itinerary_day_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poi_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_backup_for_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), server_default="attraction", nullable=False),
        sa.Column("source_type", sa.String(length=32), server_default="USER_SAVED", nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column(
            "duration_hours",
            sa.Numeric(precision=4, scale=2),
            server_default="1.00",
            nullable=False,
        ),
        sa.Column("cost_cents", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("travel_time_prev_minutes", sa.Integer(), nullable=True),
        sa.Column("travel_distance_prev_meters", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["itinerary_day_id"], ["itinerary_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["poi_id"], ["pois.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["is_backup_for_id"], ["itinerary_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "source_type IN ('USER_SAVED', 'AI_RECOMMENDED', 'MANUAL')",
            name="ck_itinerary_items_source",
        ),
        sa.CheckConstraint(
            "duration_hours >= 0.25 AND duration_hours <= 12.00",
            name="ck_itinerary_items_duration",
        ),
        sa.CheckConstraint("cost_cents >= 0", name="ck_itinerary_items_cost"),
    )
    op.create_index(
        "idx_itinerary_items_day_order", "itinerary_items", ["itinerary_day_id", "order_index"]
    )
    op.create_index("idx_itinerary_items_poi_id", "itinerary_items", ["poi_id"])
    op.create_index("idx_itinerary_items_backup", "itinerary_items", ["is_backup_for_id"])
    op.create_index(
        "idx_itinerary_items_geom",
        "itinerary_items",
        ["geom"],
        postgresql_using="gist",
    )

    # 4. system_settings table
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed spend_killswitch initial record
    op.execute(
        sa.text(
            "INSERT INTO system_settings (key, value) "
            'VALUES (\'spend_killswitch\', \'{"killswitch_active": false, "triggered_at": null, "reason": null}\'::jsonb) '
            "ON CONFLICT (key) DO NOTHING;"
        )
    )


def downgrade() -> None:
    """Reversibly drops created tables in reverse dependency order."""
    op.drop_table("system_settings")
    op.drop_index("idx_itinerary_items_geom", table_name="itinerary_items", postgresql_using="gist")
    op.drop_index("idx_itinerary_items_backup", table_name="itinerary_items")
    op.drop_index("idx_itinerary_items_poi_id", table_name="itinerary_items")
    op.drop_index("idx_itinerary_items_day_order", table_name="itinerary_items")
    op.drop_table("itinerary_items")
    op.drop_index("idx_itinerary_days_itinerary_id", table_name="itinerary_days")
    op.drop_table("itinerary_days")
    op.drop_index("idx_itineraries_user_status", table_name="itineraries")
    op.drop_index("idx_itineraries_user_id", table_name="itineraries")
    op.drop_table("itineraries")
