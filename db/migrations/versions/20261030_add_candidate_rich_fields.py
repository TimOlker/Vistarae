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

"""Add rich fields to ingest_candidates table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adds official_url, wiki_url, hero_image_url, recommended_duration_hours, recommended_visit_days, and estimated_visit_time_notes columns."""
    op.add_column("ingest_candidates", sa.Column("official_url", sa.Text(), nullable=True))
    op.add_column("ingest_candidates", sa.Column("wiki_url", sa.Text(), nullable=True))
    op.add_column("ingest_candidates", sa.Column("hero_image_url", sa.Text(), nullable=True))
    op.add_column("ingest_candidates", sa.Column("recommended_duration_hours", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("ingest_candidates", sa.Column("recommended_visit_days", sa.Integer(), nullable=True))
    op.add_column("ingest_candidates", sa.Column("estimated_visit_time_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drops the added rich columns from ingest_candidates."""
    op.drop_column("ingest_candidates", "estimated_visit_time_notes")
    op.drop_column("ingest_candidates", "recommended_visit_days")
    op.drop_column("ingest_candidates", "recommended_duration_hours")
    op.drop_column("ingest_candidates", "hero_image_url")
    op.drop_column("ingest_candidates", "wiki_url")
    op.drop_column("ingest_candidates", "official_url")

