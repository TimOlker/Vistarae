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

"""Tag governance slugification, alias arrays, and scraping preferences.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22

Implements Phase 9 Requirements:
- REQ-EXT-004: Tag slug, display name, and search aliases
- REQ-EXT-005: Unique constraint uq_tags_user_slug on (user_id, slug)
- REQ-EXT-019: user_preferences.valid_scraping_domains JSONB column
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Applies schema changes for tag governance and scraping preferences."""
    # 1. Update tags table: add slug and aliases
    op.add_column("tags", sa.Column("slug", sa.String(length=64), nullable=True))
    op.add_column(
        "tags",
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # 2. Backfill existing tag slugs from name: slug = regexp_replace(lower(trim(name)), '[^a-z0-9]+', '_', 'g')
    op.execute(
        """
        UPDATE tags
        SET slug = regexp_replace(lower(trim(name)), '[^a-z0-9]+', '_', 'g')
        WHERE slug IS NULL;
        """
    )
    op.alter_column("tags", "slug", nullable=False)

    # 3. Create unique constraint on (user_id, slug) and index
    op.create_unique_constraint("uq_tags_user_slug", "tags", ["user_id", "slug"])
    op.create_index("idx_tags_user_slug", "tags", ["user_id", "slug"])

    # 4. Update user_preferences table: add valid_scraping_domains
    op.add_column(
        "user_preferences",
        sa.Column(
            "valid_scraping_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'["wikipedia.org", "tripadvisor.com", "atlasobscura.com", "google.com/maps", "roadtrippers.com"]\'::jsonb'
            ),
        ),
    )


def downgrade() -> None:
    """Reverts schema changes cleanly."""
    op.drop_column("user_preferences", "valid_scraping_domains")
    op.drop_index("idx_tags_user_slug", table_name="tags")
    op.drop_constraint("uq_tags_user_slug", "tags", type_="unique")
    op.drop_column("tags", "aliases")
    op.drop_column("tags", "slug")
