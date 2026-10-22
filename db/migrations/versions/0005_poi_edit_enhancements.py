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

"""POI Editor Enhancements, Location Finder & Merge Workflow.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21

Implements Phase 7 Requirements (REQ-EDIT-001 through REQ-EDIT-014, REQ-SAVE-004)
and Constitution Invariants:
- Multi-address structured JSONB storage (addresses) with GIN jsonb_path_ops index
- Hierarchical parenting constraint chk_pois_parent_not_self and composite index idx_pois_user_parent
- Visit lifecycle tracking (visited_dates, want_to_visit_again, already_visited, visit_pending)
- Source provenance (source_type, source_value)
- Data backfill migrating legacy states/countries or IPTC columns into addresses
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adds rich POI fields, hierarchy indices, addresses JSONB, and lifecycle columns."""
    # 1. Add columns to pois table
    op.execute(
        """
        ALTER TABLE pois
            ADD COLUMN IF NOT EXISTS description TEXT,
            ADD COLUMN IF NOT EXISTS parent_poi_id UUID REFERENCES pois(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS addresses JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS recommended_duration_hours NUMERIC(4, 2),
            ADD COLUMN IF NOT EXISTS recommended_visit_days INTEGER NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) NOT NULL DEFAULT 'Manual',
            ADD COLUMN IF NOT EXISTS source_value VARCHAR(1000),
            ADD COLUMN IF NOT EXISTS official_url VARCHAR(2000),
            ADD COLUMN IF NOT EXISTS wiki_url VARCHAR(2000),
            ADD COLUMN IF NOT EXISTS directory_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS image_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS visited_dates JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS want_to_visit_again BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS already_visited BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS visit_pending BOOLEAN NOT NULL DEFAULT TRUE;
        """
    )

    # 2. Create indexes
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pois_addresses_path 
            ON pois USING gin (addresses jsonb_path_ops);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pois_user_parent 
            ON pois (user_id, parent_poi_id);
        """
    )

    # 3. Create check constraint
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'chk_pois_parent_not_self'
            ) THEN
                ALTER TABLE pois
                    ADD CONSTRAINT chk_pois_parent_not_self
                    CHECK (parent_poi_id IS NULL OR parent_poi_id != id);
            END IF;
        END $$;
        """
    )

    # 4. Data Backfill: Migrate legacy states and countries arrays or IPTC columns into addresses JSONB
    op.execute(
        """
        DO $$
        BEGIN
            -- Backfill from 0002 states/countries arrays if they exist
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'pois' AND column_name = 'states'
            ) THEN
                UPDATE pois
                SET addresses = (
                    SELECT COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'street', NULL,
                                'city', NULL,
                                'state_province', s.elem,
                                'country', COALESCE(c.elem, 'Unknown'),
                                'postal_code', NULL
                            )
                        ),
                        '[]'::jsonb
                    )
                    FROM jsonb_array_elements_text(COALESCE(pois.states, '[]'::jsonb)) WITH ORDINALITY AS s(elem, ord)
                    FULL OUTER JOIN jsonb_array_elements_text(COALESCE(pois.countries, '[]'::jsonb)) WITH ORDINALITY AS c(elem, ord)
                        ON s.ord = c.ord
                )
                WHERE jsonb_array_length(addresses) = 0 
                  AND (jsonb_array_length(COALESCE(states, '[]'::jsonb)) > 0 OR jsonb_array_length(COALESCE(countries, '[]'::jsonb)) > 0);
            END IF;

            -- Backfill from IPTC columns if they exist
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'pois' AND column_name = 'iptc_country_code'
            ) THEN
                UPDATE pois
                SET addresses = jsonb_build_array(
                    jsonb_build_object(
                        'street', NULL,
                        'city', iptc_city,
                        'state_province', iptc_province_state,
                        'country', COALESCE(iptc_country_code, 'Unknown'),
                        'postal_code', iptc_zip_code
                    )
                )
                WHERE jsonb_array_length(addresses) = 0
                  AND (iptc_country_code IS NOT NULL OR iptc_province_state IS NOT NULL OR iptc_city IS NOT NULL);
            END IF;

            -- Backfill visit flags from legacy columns if they exist
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'pois' AND column_name = 'visited'
            ) THEN
                UPDATE pois
                SET already_visited = COALESCE(visited, FALSE),
                    visit_pending = NOT COALESCE(visited, FALSE)
                WHERE already_visited = FALSE AND visited IS TRUE;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'pois' AND column_name = 'visit_again'
            ) THEN
                UPDATE pois
                SET want_to_visit_again = COALESCE(visit_again, FALSE)
                WHERE want_to_visit_again = FALSE AND visit_again IS TRUE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Reverts 0005 migration cleanly per Constitution Principle 4."""
    op.execute("DROP INDEX IF EXISTS idx_pois_user_parent;")
    op.execute("DROP INDEX IF EXISTS idx_pois_addresses_path;")
    op.execute("ALTER TABLE pois DROP CONSTRAINT IF EXISTS chk_pois_parent_not_self;")
    op.execute(
        """
        ALTER TABLE pois
            DROP COLUMN IF EXISTS visit_pending,
            DROP COLUMN IF EXISTS already_visited,
            DROP COLUMN IF EXISTS want_to_visit_again,
            DROP COLUMN IF EXISTS source_value,
            DROP COLUMN IF EXISTS source_type,
            DROP COLUMN IF EXISTS addresses;
        """
    )
