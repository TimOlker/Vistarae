# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for SQLAlchemy 2.0 ORM tables (T-010).

Verifies table schemas, relationships, constraints, and defaults:
- users, user_preferences, user_metrics, user_quotas, idempotency_keys
- Foreign keys with ON DELETE CASCADE
- Table constraints and indexes
- TimestampMixin
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from vistarae_core.adapters.db.base import Base, TimestampMixin
from vistarae_core.adapters.db.tables import (
    IdempotencyKeysTable,
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)


class TestTableMetadata:
    """Verifies table registration on DeclarativeBase metadata."""

    def test_all_tables_registered_in_metadata(self) -> None:
        """Asserts all five core domain tables exist in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "users",
            "user_preferences",
            "user_metrics",
            "user_quotas",
            "idempotency_keys",
        }
        assert expected.issubset(table_names)


class TestUserTableSchema:
    """Verifies UserTable schema, columns, and constraints."""

    def test_user_table_columns(self) -> None:
        """Asserts users table columns and types."""
        cols = UserTable.__table__.columns
        assert "id" in cols
        assert "cognito_sub" in cols
        assert "email" in cols
        assert "full_name" in cols
        assert "is_active" in cols
        assert "created_at" in cols
        assert "updated_at" in cols
        assert cols["id"].primary_key is True
        assert cols["cognito_sub"].nullable is False
        assert cols["email"].nullable is False
        assert cols["full_name"].nullable is True

    def test_user_table_indexes(self) -> None:
        """Asserts indexes on users table."""
        idx_names = {idx.name for idx in UserTable.__table__.indexes}
        assert "idx_users_cognito_sub" in idx_names
        assert "idx_users_email" in idx_names


class TestUserPreferencesTableSchema:
    """Verifies UserPreferencesTable schema and constraints."""

    def test_user_preferences_foreign_key(self) -> None:
        """Asserts user_preferences references users(id) with CASCADE."""
        fk_constraints = [
            c
            for c in UserPreferencesTable.__table__.constraints
            if isinstance(c, ForeignKeyConstraint)
        ]
        assert len(fk_constraints) >= 1
        fk = fk_constraints[0]
        assert fk.elements[0].column.table.name == "users"
        assert fk.ondelete == "CASCADE"

    def test_user_preferences_check_constraints(self) -> None:
        """Asserts check constraints for theme, pacing, transit, etc."""
        ck_names = {
            c.name
            for c in UserPreferencesTable.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "ck_user_prefs_theme" in ck_names
        assert "ck_user_prefs_pacing" in ck_names
        assert "ck_user_prefs_transit" in ck_names
        assert "ck_user_prefs_clustering_radius" in ck_names
        assert "ck_user_prefs_meal_intervals" in ck_names
        assert "ck_user_prefs_daily_cap" in ck_names


class TestUserMetricsAndQuotasTableSchema:
    """Verifies UserMetricsTable and UserQuotasTable constraints."""

    def test_metrics_foreign_key(self) -> None:
        """Asserts user_metrics references users(id) with CASCADE."""
        fk_constraints = [
            c for c in UserMetricsTable.__table__.constraints if isinstance(c, ForeignKeyConstraint)
        ]
        assert len(fk_constraints) >= 1
        assert fk_constraints[0].ondelete == "CASCADE"

    def test_quotas_foreign_key_and_tier_constraint(self) -> None:
        """Asserts user_quotas references users(id) and checks tier."""
        table = UserQuotasTable.__table__
        fks = [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]
        assert len(fks) >= 1
        assert fks[0].ondelete == "CASCADE"

        cks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        assert "ck_user_quotas_tier" in cks


class TestIdempotencyKeysTableSchema:
    """Verifies IdempotencyKeysTable schema and uniqueness constraints."""

    def test_idempotency_table_constraints(self) -> None:
        """Asserts unique constraint (user_id, idempotency_key) and status check."""
        table = IdempotencyKeysTable.__table__
        uqs = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
        uq_names = {c.name for c in uqs}
        assert "uq_idempotency_user_key" in uq_names

        cks = {c.name for c in table.constraints if isinstance(c, CheckConstraint)}
        assert "ck_idempotency_status" in cks


class TestTimestampMixin:
    """Verifies TimestampMixin attributes."""

    def test_timestamp_mixin_fields(self) -> None:
        """Asserts created_at and updated_at on a test class inheriting TimestampMixin."""

        class MockTimestamped(TimestampMixin):
            pass

        assert hasattr(MockTimestamped, "created_at")
        assert hasattr(MockTimestamped, "updated_at")
