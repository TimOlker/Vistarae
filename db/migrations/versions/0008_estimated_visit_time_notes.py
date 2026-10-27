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

"""Add estimated_visit_time_notes column to pois table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26

Adds:
- estimated_visit_time_notes TEXT column to pois table for explaining visit duration reasoning
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adds estimated_visit_time_notes column to pois table."""
    op.execute(
        """
        ALTER TABLE pois
            ADD COLUMN IF NOT EXISTS estimated_visit_time_notes TEXT;
        """
    )


def downgrade() -> None:
    """Removes estimated_visit_time_notes column from pois table."""
    op.execute(
        """
        ALTER TABLE pois
            DROP COLUMN IF EXISTS estimated_visit_time_notes;
        """
    )
