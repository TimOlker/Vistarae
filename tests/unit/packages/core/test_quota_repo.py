# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for SqlAlchemyQuotaRepository (T-029).

Tests:
- get_quota found and not found
- increment_request_count within window
- increment_request_count limit exceeded
- increment_request_count window rollover after expiry
- tier-specific limits (low=60, high/admin=300)
- check_token_budget available and exhausted
- increment_tokens atomic update
- update_quota administrative updates
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import UserQuotasTable
from vistarae_core.adapters.repositories.quota_repo import SqlAlchemyQuotaRepository
from vistarae_core.domain.value_objects import UserTier


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestQuotaRepositoryGet:
    """Tests for get_quota."""

    @pytest.mark.asyncio
    async def test_get_quota_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts UserQuota entity correctly built from row."""
        now = datetime.now(UTC)
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            monthly_token_quota=75000,
            current_token_usage=12000,
            tier="low",
            request_count=10,
            window_start_at=now,
            is_disabled=False,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        quota = await repo.get_quota(test_user_id)

        assert quota is not None
        assert quota.user_id == test_user_id
        assert quota.monthly_token_quota == 75000
        assert quota.tier == UserTier.LOW
        assert quota.request_count == 10

    @pytest.mark.asyncio
    async def test_get_quota_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts None returned when row does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        quota = await repo.get_quota(test_user_id)
        assert quota is None


class TestQuotaRepositoryRateLimit:
    """Tests for rolling window rate limit tracking."""

    @pytest.mark.asyncio
    async def test_increment_request_count_no_row(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts defaults when no row exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        count, limit, exceeded = await repo.increment_request_count(test_user_id, UserTier.LOW)

        assert count == 1
        assert limit == 60
        assert exceeded is False

    @pytest.mark.asyncio
    async def test_increment_request_count_within_window(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts count increments when within 60s window."""
        now = datetime.now(UTC)
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            request_count=5,
            window_start_at=now - timedelta(seconds=10),
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        count, limit, exceeded = await repo.increment_request_count(test_user_id, UserTier.LOW)

        assert count == 6
        assert limit == 60
        assert exceeded is False
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_request_count_exceeded(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts exceeded is True when request_count > limit."""
        now = datetime.now(UTC)
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            request_count=60,
            window_start_at=now - timedelta(seconds=15),
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        count, limit, exceeded = await repo.increment_request_count(test_user_id, UserTier.LOW)

        assert count == 61
        assert limit == 60
        assert exceeded is True

    @pytest.mark.asyncio
    async def test_increment_request_count_window_rollover(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts window rolls over to 1 after 60s."""
        now = datetime.now(UTC)
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            request_count=55,
            window_start_at=now - timedelta(seconds=65),  # expired
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        count, limit, exceeded = await repo.increment_request_count(test_user_id, UserTier.LOW)

        assert count == 1
        assert limit == 60
        assert exceeded is False
        assert fake_row.request_count == 1

    @pytest.mark.asyncio
    async def test_increment_request_count_admin_tier_limit(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts admin tier has limit 300."""
        now = datetime.now(UTC)
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            request_count=100,
            window_start_at=now - timedelta(seconds=20),
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        count, limit, exceeded = await repo.increment_request_count(test_user_id, UserTier.ADMIN)

        assert count == 101
        assert limit == 300
        assert exceeded is False


class TestQuotaRepositoryTokenBudget:
    """Tests for token checking and consumption."""

    @pytest.mark.asyncio
    async def test_check_token_budget_available(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts True when usage + required <= monthly_quota."""
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            monthly_token_quota=50000,
            current_token_usage=10000,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        available = await repo.check_token_budget(test_user_id, 5000)
        assert available is True

    @pytest.mark.asyncio
    async def test_check_token_budget_exhausted(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts False when usage + required > monthly_quota."""
        fake_row = UserQuotasTable(
            user_id=test_user_id,
            monthly_token_quota=50000,
            current_token_usage=48000,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        available = await repo.check_token_budget(test_user_id, 3000)
        assert available is False

    @pytest.mark.asyncio
    async def test_check_token_budget_no_row(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts False when user quota row does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyQuotaRepository(mock_session)
        available = await repo.check_token_budget(test_user_id, 100)
        assert available is False

    @pytest.mark.asyncio
    async def test_increment_tokens(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts update executed for both user_quotas and user_metrics."""
        repo = SqlAlchemyQuotaRepository(mock_session)
        await repo.increment_tokens(test_user_id, 1500)
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_update_quota(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts administrative update executes successfully."""
        repo = SqlAlchemyQuotaRepository(mock_session)
        await repo.update_quota(
            test_user_id,
            {"tier": UserTier.HIGH, "monthly_token_quota": 200000},
        )
        mock_session.execute.assert_called_once()
