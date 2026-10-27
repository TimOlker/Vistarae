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

"""Unique user context: user_prompts table, travel_style_description, and reason_to_visit.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-27

Implements Phase 11 Requirements:
- REQ-CTX-014: Table user_prompts with foreign key users(id) ON DELETE CASCADE and unique (user_id, prompt_type)
- REQ-CTX-015: prompt_type VARCHAR(32) backed by StrEnum (no PostgreSQL ENUM)
- REQ-CTX-020: pois.reason_to_visit TEXT column
- REQ-CTX-004: user_preferences.travel_style_description TEXT column
- REQ-CTX-026: GIN trigram indices on pois.reason_to_visit and pois.description
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Applies schema changes for unique user context and POI reason_to_visit."""
    # 1. Add reason_to_visit column to pois table
    op.add_column("pois", sa.Column("reason_to_visit", sa.Text(), nullable=True))

    # 2. Add travel_style_description column to user_preferences table
    op.add_column("user_preferences", sa.Column("travel_style_description", sa.Text(), nullable=True))

    # 3. Create user_prompts table
    op.create_table(
        "user_prompts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_type", sa.String(length=32), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("user_id", "prompt_type", name="uq_user_prompts_user_type"),
        sa.CheckConstraint(
            "prompt_type IN ('description', 'reason_to_visit', 'time_spent')",
            name="ck_user_prompts_type",
        ),
    )
    op.create_index("idx_user_prompts_user_id", "user_prompts", ["user_id"])

    # 4. Create trigram indices for full-text search on description and reason_to_visit
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pois_reason_to_visit_trgm
            ON pois USING gin (reason_to_visit gin_trgm_ops);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pois_description_trgm
            ON pois USING gin (description gin_trgm_ops);
        """
    )


def downgrade() -> None:
    """Reverts schema changes cleanly."""
    op.execute("DROP INDEX IF EXISTS idx_pois_description_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_pois_reason_to_visit_trgm;")
    op.drop_index("idx_user_prompts_user_id", table_name="user_prompts")
    op.drop_table("user_prompts")
    op.drop_column("user_preferences", "travel_style_description")
    op.drop_column("pois", "reason_to_visit")
