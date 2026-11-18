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

"""Add bulk_enrichment_results table for session auditing and login recovery.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-13 11:15:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Creates bulk_enrichment_results table with recovery index."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    uuid_type = postgresql.UUID(as_uuid=True) if is_postgres else sa.String(36)

    op.create_table(
        "bulk_enrichment_results",
        sa.Column(
            "id",
            uuid_type,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_postgres else None,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            uuid_type,
            sa.ForeignKey("ingest_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            uuid_type,
            unique=True,
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unprocessed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_resources_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("termination_reason", sa.Text(), nullable=False),
        sa.Column(
            "candidate_issues",
            postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(),
            server_default=sa.text("'[]'::jsonb") if is_postgres else "[]",
            nullable=False,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    op.create_index(
        "idx_bulk_enrichment_user_recovery",
        "bulk_enrichment_results",
        ["user_id", "acknowledged_at", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_bulk_enrichment_job_id",
        "bulk_enrichment_results",
        ["job_id"],
    )


def downgrade() -> None:
    """Drops bulk_enrichment_results table and its indexes."""
    op.drop_index("idx_bulk_enrichment_job_id", table_name="bulk_enrichment_results")
    op.drop_index("idx_bulk_enrichment_user_recovery", table_name="bulk_enrichment_results")
    op.drop_table("bulk_enrichment_results")
