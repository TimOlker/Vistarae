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

"""Asynchronous Ingestion Jobs table and indices.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19

Implements Phase 3 Requirements (REQ-INGEST-001, REQ-INGEST-002, REQ-INGEST-003)
and Constitution Invariants:
- Creates table ingest_jobs with user_id foreign key cascading on delete to users
- Enforces check constraint ck_ingest_jobs_status on job_status
- Creates composite index idx_ingest_jobs_user_created for tenant-scoped sorting
- Creates composite index idx_ingest_jobs_id_user for fast tenant-scoped job lookup
- Reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates ingest_jobs table, check constraints, and composite indices."""
    op.create_table(
        "ingest_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_status", sa.String(length=16), nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "duplicate_payloads",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("target_list_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "error_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["target_list_id"],
            ["lists.id"],
            name=op.f("fk_ingest_jobs_target_list_id_lists"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ingest_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingest_jobs")),
        sa.CheckConstraint(
            "job_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED')",
            name="ck_ingest_jobs_status",
        ),
    )

    op.create_index(
        "idx_ingest_jobs_user_created",
        "ingest_jobs",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_ingest_jobs_id_user",
        "ingest_jobs",
        ["id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drops ingest_jobs table, check constraints, and composite indices."""
    op.drop_index("idx_ingest_jobs_id_user", table_name="ingest_jobs")
    op.drop_index("idx_ingest_jobs_user_created", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
