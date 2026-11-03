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

"""Add workbench fields to ingest_candidates

Revision ID: 20261102_add_workbench_fields
Revises: 20261102_add_related_websites
Create Date: 2026-11-02 12:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "no_websites",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column("disposition_justification", sa.Text(), nullable=True),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "is_user_overridden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "parent_candidate_id",
            UUID(as_uuid=False),
            sa.ForeignKey("ingest_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "merge_target_id",
            UUID(as_uuid=False),
            sa.ForeignKey("ingest_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ingest_candidates", "merge_target_id")
    op.drop_column("ingest_candidates", "parent_candidate_id")
    op.drop_column("ingest_candidates", "is_user_overridden")
    op.drop_column("ingest_candidates", "disposition_justification")
    op.drop_column("ingest_candidates", "no_websites")

