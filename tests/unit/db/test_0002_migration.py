# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Phase 2 Alembic migration 0002_poi_domain_spatial (T-003).

Verifies schema creation, check constraints, composite GiST indices,
foreign key cascade rules, and downgrade definition integrity.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from vistarae_core.adapters.db.base import Base
from vistarae_core.adapters.db.tables import (
    GeocodingCacheTable,
    ListTable,
    POITable,
    TagTable,
)


def _load_migration_module():
    """Dynamically loads the 0002 migration module."""
    migration_path = (
        Path(__file__).parents[3] / "db" / "migrations" / "versions" / "0002_poi_domain_spatial.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0002", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigration0002Metadata:
    """Verifies migration file revision identifiers and functions."""

    def test_migration_identifiers(self) -> None:
        """Asserts correct revision and parent revision pointers."""
        mod = _load_migration_module()
        assert mod.revision == "0002"
        assert mod.down_revision == "0001"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestPOITableSchema:
    """Verifies POITable schema, column types, and constraints."""

    def test_poi_columns_exist(self) -> None:
        """Asserts all POI columns exist in table metadata."""
        cols = POITable.__table__.columns
        expected_cols = {
            "id",
            "user_id",
            "parent_poi_id",
            "name",
            "description",
            "address",
            "city",
            "states",
            "countries",
            "official_url",
            "wiki_url",
            "image_urls",
            "directory_paths",
            "creation_metadata",
            "visit_state",
            "visited_dates",
            "rating",
            "estimated_cost",
            "pricing_unit",
            "recommended_duration_hours",
            "recommended_visit_days",
            "enrichment_status",
            "geom",
            "region_geom",
            "embedding",
            "embedding_md5",
            "created_at",
            "updated_at",
        }
        assert expected_cols.issubset(set(cols.keys()))

    def test_poi_constraints(self) -> None:
        """Asserts check constraints for visit_state, rating, duration, and enrichment."""
        constraints = {c.name: c for c in POITable.__table__.constraints if hasattr(c, "name")}
        assert "ck_pois_visit_state" in constraints
        assert "ck_pois_rating" in constraints
        assert "ck_pois_duration" in constraints
        assert "ck_pois_enrichment" in constraints

    def test_poi_foreign_keys(self) -> None:
        """Asserts foreign key cascades: user_id CASCADE and parent_poi_id SET NULL."""
        fks = {fk.column.table.name: fk for fk in POITable.__table__.foreign_keys}
        assert "users" in fks
        assert fks["users"].ondelete == "CASCADE"
        assert "pois" in fks
        assert fks["pois"].ondelete == "SET NULL"

    def test_poi_indexes(self) -> None:
        """Asserts composite GiST, GIN, HNSW, and parent indexes on POITable."""
        indexes = {idx.name for idx in POITable.__table__.indexes}
        assert "idx_pois_parent_poi_id" in indexes
        assert "idx_pois_states_gin" in indexes
        assert "idx_pois_countries_gin" in indexes
        assert "idx_pois_user_geom" in indexes
        assert "idx_pois_user_geom_geometry" in indexes
        assert "idx_pois_name_trgm" in indexes
        assert "idx_pois_embedding" in indexes


class TestAuxiliaryTablesSchema:
    """Verifies lists, tags, junction tables, and geocoding cache schemas."""

    def test_all_auxiliary_tables_registered(self) -> None:
        """Asserts auxiliary tables exist in Base.metadata."""
        tables = set(Base.metadata.tables.keys())
        expected = {"lists", "poi_lists", "tags", "poi_tags", "geocoding_cache"}
        assert expected.issubset(tables)

    def test_list_table_columns_and_fks(self) -> None:
        """Asserts list table structure and user CASCADE FK."""
        cols = ListTable.__table__.columns
        assert {
            "id",
            "user_id",
            "title",
            "description",
            "is_public",
            "created_at",
            "updated_at",
        }.issubset(set(cols.keys()))
        fk = next(iter(ListTable.__table__.foreign_keys))
        assert fk.column.table.name == "users"
        assert fk.ondelete == "CASCADE"

    def test_tag_table_uniqueness_and_fks(self) -> None:
        """Asserts tag table user_id + name unique constraint and CASCADE FK."""
        cols = TagTable.__table__.columns
        assert {"id", "user_id", "name", "created_at"}.issubset(set(cols.keys()))
        fk = next(iter(TagTable.__table__.foreign_keys))
        assert fk.column.table.name == "users"
        assert fk.ondelete == "CASCADE"

        constraints = {c.name for c in TagTable.__table__.constraints if hasattr(c, "name")}
        assert "uq_tags_user_name" in constraints

    def test_geocoding_cache_table(self) -> None:
        """Asserts geocoding cache primary key and columns."""
        cols = GeocodingCacheTable.__table__.columns
        assert cols["query_hash"].primary_key is True
        assert {"lat", "lon", "formatted_address", "status", "created_at", "expires_at"}.issubset(
            set(cols.keys())
        )
        indexes = {idx.name for idx in GeocodingCacheTable.__table__.indexes}
        assert "idx_geocoding_cache_expires_at" in indexes
