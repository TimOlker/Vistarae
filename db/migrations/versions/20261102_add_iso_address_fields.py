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

"""Add ISO address fields and photo_directories to pois and ingest_candidates

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-02 19:15:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Alter pois table
    op.add_column(
        "pois",
        sa.Column("country_code", sa.String(2), server_default="US", nullable=False),
    )
    op.add_column("pois", sa.Column("admin_level_1", sa.String(100), nullable=True))
    op.add_column("pois", sa.Column("admin_level_2", sa.String(100), nullable=True))
    op.add_column("pois", sa.Column("locality", sa.String(150), nullable=True))
    op.add_column("pois", sa.Column("raw_geocoding", JSONB, nullable=True))
    op.add_column(
        "pois",
        sa.Column(
            "photo_directories",
            JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_pois_iso_location",
        "pois",
        ["country_code", "admin_level_1", "locality"],
    )

    # 2. Alter ingest_candidates table
    op.add_column(
        "ingest_candidates",
        sa.Column("country_code", sa.String(2), server_default="US", nullable=False),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column("admin_level_1", sa.String(100), nullable=True),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column("admin_level_2", sa.String(100), nullable=True),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column("locality", sa.String(150), nullable=True),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column("raw_geocoding", JSONB, nullable=True),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "photo_directories",
            JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_candidates_iso_location",
        "ingest_candidates",
        ["country_code", "admin_level_1", "locality"],
    )


def downgrade() -> None:
    op.drop_index("idx_candidates_iso_location", table_name="ingest_candidates")
    op.drop_column("ingest_candidates", "photo_directories")
    op.drop_column("ingest_candidates", "raw_geocoding")
    op.drop_column("ingest_candidates", "locality")
    op.drop_column("ingest_candidates", "admin_level_2")
    op.drop_column("ingest_candidates", "admin_level_1")
    op.drop_column("ingest_candidates", "country_code")

    op.drop_index("idx_pois_iso_location", table_name="pois")
    op.drop_column("pois", "photo_directories")
    op.drop_column("pois", "raw_geocoding")
    op.drop_column("pois", "locality")
    op.drop_column("pois", "admin_level_2")
    op.drop_column("pois", "admin_level_1")
    op.drop_column("pois", "country_code")
