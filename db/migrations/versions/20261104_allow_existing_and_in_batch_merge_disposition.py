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

"""Allow 'existing' and 'in_batch_merge' dispositions in ingest_candidates check constraint

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-04 04:35:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Updates ck_ingest_candidates_recommended_disp to allow existing and in_batch_merge."""
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
            "recommended_disposition IN ('accept', 'ignore', 'update_existing', 'sublocation', 'exclude', 'existing', 'in_batch_merge')",
        )


def downgrade() -> None:
    """Reverts ck_ingest_candidates_recommended_disp to exclude existing and in_batch_merge."""
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
            "recommended_disposition IN ('accept', 'ignore', 'update_existing', 'sublocation', 'exclude')",
        )

