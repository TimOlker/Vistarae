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

"""Add ingest_candidates staging table for two-phase interactive ingestion (T-001).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-28

Implements Phase 12 Requirements:
- REQ-ING-011: Isolated staging table ingest_candidates with multi-phase lifecycle
- REQ-ING-015: Strict user_id and job_id foreign key cascades
- REQ-ING-023: Tenant compound index and spatial GiST index
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates the ingest_candidates staging table and associated indices."""
    op.create_table(
        "ingest_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("poi_name", sa.String(length=255), nullable=False),
        sa.Column(
            "recommended_disposition",
            sa.String(length=32),
            server_default=sa.text("'accept'"),
            nullable=False,
        ),
        sa.Column("user_disposition", sa.String(length=32), nullable=True),
        sa.Column("matched_existing_poi_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_poi_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("street_address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state_province", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column(
            "addresses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "dates_visited",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("photo_directory", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reason_to_visit", sa.Text(), nullable=True),
        sa.Column(
            "update_coordinates",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_skipped",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "phase_state",
            sa.String(length=32),
            server_default=sa.text("'phase_1_triage'"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["ingest_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_existing_poi_id"], ["pois.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_poi_id"], ["pois.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "recommended_disposition IN ('accept', 'ignore', 'update_existing', 'sublocation')",
            name="ck_ingest_candidates_recommended_disp",
        ),
        sa.CheckConstraint(
            "phase_state IN ('phase_1_triage', 'phase_2_enriched', 'committed', 'aborted')",
            name="ck_ingest_candidates_phase_state",
        ),
    )

    # Compound tenant/job index
    op.create_index(
        "idx_ingest_candidates_user_job",
        "ingest_candidates",
        ["user_id", "job_id"],
    )

    # Spatial GiST index
    op.create_index(
        "idx_ingest_candidates_geom",
        "ingest_candidates",
        ["geom"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Drops the ingest_candidates staging table and indices."""
    op.drop_index("idx_ingest_candidates_geom", table_name="ingest_candidates")
    op.drop_index("idx_ingest_candidates_user_job", table_name="ingest_candidates")
    op.drop_table("ingest_candidates")
