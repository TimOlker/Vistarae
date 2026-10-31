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

"""Add user_exclusion_zones table and update ingest disposition constraint.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates the user_exclusion_zones table and updates check constraint."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    uuid_type = postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36)
    server_uuid = sa.text("gen_random_uuid()") if is_postgres else None

    op.create_table(
        "user_exclusion_zones",
        sa.Column(
            "id",
            uuid_type,
            server_default=server_uuid,
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=False),
        sa.Column("radius_km", sa.Float(), server_default=sa.text("1.0"), nullable=False),
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
    )

    op.create_index(
        "idx_user_exclusion_zones_user",
        "user_exclusion_zones",
        ["user_id"],
    )

    # In PostgreSQL, update ck_ingest_candidates_recommended_disp to allow 'exclude'
    if is_postgres:
        op.drop_constraint(
            "ck_ingest_candidates_recommended_disp",
            "ingest_candidates",
            type_="check",
        )
        op.create_check_constraint(
            "ck_ingest_candidates_recommended_disp",
            "ingest_candidates",
            "recommended_disposition IN ('accept', 'ignore', 'update_existing', 'sublocation', 'exclude')",
        )


def downgrade() -> None:
    """Drops the user_exclusion_zones table and rolls back constraint."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.drop_constraint(
            "ck_ingest_candidates_recommended_disp",
            "ingest_candidates",
            type_="check",
        )
        op.create_check_constraint(
            "ck_ingest_candidates_recommended_disp",
            "ingest_candidates",
            "recommended_disposition IN ('accept', 'ignore', 'update_existing', 'sublocation')",
        )

    op.drop_index("idx_user_exclusion_zones_user", table_name="user_exclusion_zones")
    op.drop_table("user_exclusion_zones")

