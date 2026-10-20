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

"""Point of Interest domain, geospatial indices, lists, tags, and geocoding cache.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19

Implements Phase 2 Requirements (REQ-POI-001 through REQ-POI-007, REQ-GEO-001 through
REQ-GEO-006, REQ-EMBED-001) and Constitution Invariants:
- Enables pg_trgm, btree_gist, postgis, and vector extensions
- Creates tables: pois, lists, tags, poi_lists, poi_tags, geocoding_cache
- All foreign keys cascade on delete to tenant anchor (users)
- Check constraints: ck_pois_visit_state, ck_pois_rating, ck_pois_duration, ck_pois_enrichment
- Dual-index spatial separation:
    * Composite GiST idx_pois_user_geom on (user_id, geom) for geodesic queries (ST_DWithin)
    * Composite functional GiST idx_pois_user_geom_geometry on (user_id, (geom::geometry)) for planar queries (ST_MakeEnvelope)
- GIN indexes for JSONB string arrays: idx_pois_states_gin, idx_pois_countries_gin
- GIN trigram index for fuzzy name matching: idx_pois_name_trgm
- HNSW cosine distance vector index: idx_pois_embedding
- TTL index on geocoding_cache: idx_geocoding_cache_expires_at
- Fully reversible downgrade()
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates POI tables, geospatial and trigram indices, and check constraints."""
    # ── 1. Extensions ──────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
                CREATE EXTENSION IF NOT EXISTS "vector";
            END IF;
        END $$;
        """
    )

    # ── 2. pois ────────────────────────────────────────────────────────────
    op.create_table(
        "pois",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "parent_poi_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column(
            "states",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "countries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("wiki_url", sa.Text(), nullable=True),
        sa.Column(
            "image_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "directory_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "creation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "visit_state",
            sa.String(32),
            server_default=sa.text("'not_visited'"),
            nullable=False,
        ),
        sa.Column(
            "visited_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("pricing_unit", sa.String(16), nullable=True),
        sa.Column("recommended_duration_hours", sa.Numeric(4, 2), nullable=True),
        sa.Column(
            "recommended_visit_days",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "enrichment_status",
            sa.String(16),
            server_default=sa.text("'SUCCESS'"),
            nullable=False,
        ),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "region_geom",
            geoalchemy2.types.Geometry(
                geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False
            ),
            nullable=True,
        ),
        sa.Column("embedding_md5", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_pois_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_poi_id"], ["pois.id"], name="fk_pois_parent_poi_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "visit_state IN ('not_visited', 'visited_do_not_return', 'visited_return')",
            name="ck_pois_visit_state",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_pois_rating",
        ),
        sa.CheckConstraint(
            "recommended_duration_hours IS NULL OR (recommended_duration_hours >= 0.25 AND recommended_duration_hours <= 12.00)",
            name="ck_pois_duration",
        ),
        sa.CheckConstraint(
            "enrichment_status IN ('SUCCESS', 'PARTIAL', 'FAILED')",
            name="ck_pois_enrichment",
        ),
    )

    # Conditionally add vector embedding column if vector extension is present
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector') THEN
                ALTER TABLE pois ADD COLUMN IF NOT EXISTS embedding vector(768);
                CREATE INDEX IF NOT EXISTS idx_pois_embedding ON pois USING hnsw (embedding vector_cosine_ops);
            END IF;
        END $$;
        """
    )

    # ── POI Indexes ─────────────────────────────────────────────────────────
    op.create_index("idx_pois_parent_poi_id", "pois", ["parent_poi_id"])
    op.create_index("idx_pois_states_gin", "pois", ["states"], postgresql_using="gin")
    op.create_index("idx_pois_countries_gin", "pois", ["countries"], postgresql_using="gin")

    # Composite GiST indexes (requires btree_gist)
    op.execute("CREATE INDEX idx_pois_user_geom ON pois USING gist (user_id, geom);")
    op.execute(
        "CREATE INDEX idx_pois_user_geom_geometry ON pois USING gist (user_id, (geom::geometry));"
    )

    # Trigram GIN index for fuzzy name matching (requires pg_trgm)
    op.execute("CREATE INDEX idx_pois_name_trgm ON pois USING gin (name gin_trgm_ops);")

    # ── 3. lists ───────────────────────────────────────────────────────────
    op.create_table(
        "lists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_lists_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lists_user_id", "lists", ["user_id"])

    # ── 4. poi_lists ───────────────────────────────────────────────────────
    op.create_table(
        "poi_lists",
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "list_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["poi_id"], ["pois.id"], name="fk_poi_lists_poi_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["list_id"], ["lists.id"], name="fk_poi_lists_list_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("poi_id", "list_id"),
    )

    # ── 5. tags ────────────────────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tags_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_tags_user_name"),
    )
    op.create_index("idx_tags_user_id", "tags", ["user_id"])

    # ── 6. poi_tags ────────────────────────────────────────────────────────
    op.create_table(
        "poi_tags",
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["poi_id"], ["pois.id"], name="fk_poi_tags_poi_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_poi_tags_tag_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("poi_id", "tag_id"),
    )

    # ── 7. geocoding_cache ─────────────────────────────────────────────────
    op.create_table(
        "geocoding_cache",
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
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
        sa.PrimaryKeyConstraint("query_hash"),
    )
    op.create_index("idx_geocoding_cache_expires_at", "geocoding_cache", ["expires_at"])


def downgrade() -> None:
    """Drops all POI tables, indices, and constraints in reverse dependency order."""
    # ── Drop geocoding_cache ──
    op.drop_index("idx_geocoding_cache_expires_at", table_name="geocoding_cache")
    op.drop_table("geocoding_cache")

    # ── Drop poi_tags and tags ──
    op.drop_table("poi_tags")
    op.drop_index("idx_tags_user_id", table_name="tags")
    op.drop_table("tags")

    # ── Drop poi_lists and lists ──
    op.drop_table("poi_lists")
    op.drop_index("idx_lists_user_id", table_name="lists")
    op.drop_table("lists")

    # ── Drop pois and its indexes ──
    op.execute("DROP INDEX IF EXISTS idx_pois_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_pois_name_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_pois_user_geom_geometry;")
    op.execute("DROP INDEX IF EXISTS idx_pois_user_geom;")
    op.drop_index("idx_pois_countries_gin", table_name="pois")
    op.drop_index("idx_pois_states_gin", table_name="pois")
    op.drop_index("idx_pois_parent_poi_id", table_name="pois")
    op.drop_table("pois")
