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

"""Add external_enrichment_cache table for caching Wikipedia, Wikidata, and AI entity lookups.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-07 08:38:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Creates the external_enrichment_cache table with source and expires_at indexes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    op.create_table(
        "external_enrichment_cache",
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("response_data", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index(
        "idx_external_enrichment_cache_source",
        "external_enrichment_cache",
        ["source"],
    )
    op.create_index(
        "idx_external_enrichment_cache_expires_at",
        "external_enrichment_cache",
        ["expires_at"],
    )


def downgrade() -> None:
    """Drops the external_enrichment_cache table and its indexes."""
    op.drop_index("idx_external_enrichment_cache_expires_at", table_name="external_enrichment_cache")
    op.drop_index("idx_external_enrichment_cache_source", table_name="external_enrichment_cache")
    op.drop_table("external_enrichment_cache")

