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

"""Add no_address and no_websites columns to pois and ingest_candidates

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-18 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pois table additions
    op.add_column(
        "pois",
        sa.Column(
            "no_address",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "pois",
        sa.Column(
            "no_websites",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # ingest_candidates table addition
    op.add_column(
        "ingest_candidates",
        sa.Column(
            "no_address",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    # Clean, symmetrical downgrade
    op.drop_column("ingest_candidates", "no_address")
    op.drop_column("pois", "no_websites")
    op.drop_column("pois", "no_address")
