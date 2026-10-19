# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for SqlAlchemyUserRepository (T-020).

Tests:
- get_by_id found and not found
- get_by_cognito_sub found and not found
- create adding user, preferences, quota, metric
- update_profile
- delete
- get_preferences found and not found
- update_preferences
- get_metrics found and not found
- get_quota found and not found
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)
from vistarae_core.adapters.repositories.user_repo import SqlAlchemyUserRepository
from vistarae_core.domain.entities import (
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.value_objects import (
    PacingMode,
    ThemeMode,
    TransitSpeedMode,
    UserTier,
)


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    return session


class TestUserRepositoryQueries:
    """Tests for get_by_id and get_by_cognito_sub."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts User entity correctly mapped when row exists."""
        now = datetime.now(UTC)
        fake_row = UserTable(
            id=test_user_id,
            cognito_sub="sub-123",
            email="traveler@example.com",
            full_name="Alice Explorer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_id(test_user_id)

        assert user is not None
        assert user.id == test_user_id
        assert user.cognito_sub == "sub-123"
        assert user.full_name == "Alice Explorer"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts None returned when row does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_id(test_user_id)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_cognito_sub_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts lookup by Cognito sub claim succeeds."""
        now = datetime.now(UTC)
        fake_row = UserTable(
            id=test_user_id,
            cognito_sub="sub-abc",
            email="bob@example.com",
            full_name="Bob Traveler",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_cognito_sub("sub-abc")

        assert user is not None
        assert user.id == test_user_id
        assert user.email == "bob@example.com"

    @pytest.mark.asyncio
    async def test_get_by_cognito_sub_not_found(self, mock_session: AsyncMock) -> None:
        """Asserts None returned when sub does not match."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_cognito_sub("missing-sub")
        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_email_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts lookup by email succeeds."""
        now = datetime.now(UTC)
        fake_row = UserTable(
            id=test_user_id,
            cognito_sub="sub-email",
            email="charlie@example.com",
            full_name="Charlie Explorer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_email("charlie@example.com")

        assert user is not None
        assert user.id == test_user_id
        assert user.email == "charlie@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, mock_session: AsyncMock) -> None:
        """Asserts None returned when email does not match."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        user = await repo.get_by_email("unknown@example.com")
        assert user is None


class TestUserRepositoryMutations:
    """Tests for create, update_profile, and delete."""

    @pytest.mark.asyncio
    async def test_create_adds_all_tables(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts create adds UserTable, UserPreferencesTable, UserQuotasTable, UserMetricsTable."""
        user = User(
            id=test_user_id,
            cognito_sub="sub-create",
            email="create@example.com",
            full_name="New User",
        )
        pref = UserPreferences(user_id=test_user_id, theme=ThemeMode.DARK)
        quota = UserQuota(user_id=test_user_id, tier=UserTier.HIGH)
        metric = UserMetric(user_id=test_user_id)

        repo = SqlAlchemyUserRepository(mock_session)
        created = await repo.create(user, pref, quota, metric)

        assert created.id == test_user_id
        mock_session.add_all.assert_called_once()
        added_objs = mock_session.add_all.call_args[0][0]
        assert len(added_objs) == 4
        assert isinstance(added_objs[0], UserTable)
        assert isinstance(added_objs[1], UserPreferencesTable)
        assert isinstance(added_objs[2], UserQuotasTable)
        assert isinstance(added_objs[3], UserMetricsTable)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_profile(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts update_profile executes update statement."""
        repo = SqlAlchemyUserRepository(mock_session)
        await repo.update_profile(test_user_id, "Updated Name")
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, mock_session: AsyncMock, test_user_id: uuid.UUID) -> None:
        """Asserts delete executes delete statement."""
        repo = SqlAlchemyUserRepository(mock_session)
        await repo.delete(test_user_id)
        mock_session.execute.assert_called_once()


class TestUserSubRecords:
    """Tests for preferences, metrics, and quotas access."""

    @pytest.mark.asyncio
    async def test_get_preferences_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts preferences row converts to UserPreferences entity."""
        now = datetime.now(UTC)
        fake_pref = UserPreferencesTable(
            user_id=test_user_id,
            theme="dark",
            email_notifications_enabled=True,
            push_notifications_enabled=False,
            marketing_emails_enabled=False,
            clustering_enabled=True,
            clustering_radius_meters=100,
            default_map_layer="satellite",
            geoproximity_scope_km=30.0,
            pin_color_presets={"fav": "#ff0000"},
            pacing="relaxed",
            meal_intervals_hours=3.5,
            lunch_packing_enabled=True,
            transit_speed_mode="bicycling",
            daily_activity_hour_cap=6.0,
            preferred_currency="EUR",
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_pref
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        prefs = await repo.get_preferences(test_user_id)

        assert prefs is not None
        assert prefs.theme == ThemeMode.DARK
        assert prefs.pacing == PacingMode.RELAXED
        assert prefs.transit_speed_mode == TransitSpeedMode.BICYCLING
        assert prefs.preferred_currency == "EUR"
        assert prefs.clustering_radius_meters == 100

    @pytest.mark.asyncio
    async def test_get_preferences_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        prefs = await repo.get_preferences(test_user_id)
        assert prefs is None

    @pytest.mark.asyncio
    async def test_update_preferences(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        repo = SqlAlchemyUserRepository(mock_session)
        await repo.update_preferences(test_user_id, {"theme": ThemeMode.LIGHT, "preferred_currency": "GBP"})
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        now = datetime.now(UTC)
        fake_metrics = UserMetricsTable(
            user_id=test_user_id,
            poi_count=42,
            total_tokens_consumed=1500,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_metrics
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        metrics = await repo.get_metrics(test_user_id)

        assert metrics is not None
        assert metrics.poi_count == 42
        assert metrics.total_tokens_consumed == 1500

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        metrics = await repo.get_metrics(test_user_id)
        assert metrics is None

    @pytest.mark.asyncio
    async def test_get_quota_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        now = datetime.now(UTC)
        fake_quota = UserQuotasTable(
            user_id=test_user_id,
            monthly_token_quota=100000,
            current_token_usage=25000,
            tier="high",
            request_count=15,
            window_start_at=now,
            is_disabled=False,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_quota
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        quota = await repo.get_quota(test_user_id)

        assert quota is not None
        assert quota.monthly_token_quota == 100000
        assert quota.tier == UserTier.HIGH
        assert quota.is_disabled is False

    @pytest.mark.asyncio
    async def test_get_quota_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyUserRepository(mock_session)
        quota = await repo.get_quota(test_user_id)
        assert quota is None
