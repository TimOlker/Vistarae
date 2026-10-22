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

"""Add filter_rules table with tenant isolation and JSONB configurations.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22

Implements Phase 8 Requirements (REQ-MAIN-012, REQ-MAIN-013)
and Constitution Invariants:
- Dedicated filter_rules table with UUID primary key
- Tenant isolation: foreign key to users.id ON DELETE CASCADE
- Per-tenant namespace isolation: unique constraint uq_filter_rules_user_name on (user_id, name)
- Composite index ix_filter_rules_user_id_name
- JSONB columns for query_tree, table_config, and pin_color_scheme
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates the filter_rules table with constraints and indexes."""
    op.create_table(
        "filter_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "query_tree",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "table_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "pin_color_scheme",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_filter_rules_user_name",
        "filter_rules",
        ["user_id", "name"],
    )
    op.create_index(
        "ix_filter_rules_user_id_name",
        "filter_rules",
        ["user_id", "name"],
    )


def downgrade() -> None:
    """Drops the filter_rules table and associated constraints and indexes."""
    op.drop_index("ix_filter_rules_user_id_name", table_name="filter_rules")
    op.drop_constraint("uq_filter_rules_user_name", "filter_rules", type_="unique")
    op.drop_table("filter_rules")
