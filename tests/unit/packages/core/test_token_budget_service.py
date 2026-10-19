# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for TokenBudgetService (T-038).

Tests:
- verify_budget succeeds when budget available
- verify_budget raises QuotaExceededError when budget exhausted
- record_usage increments tokens via repository
- record_usage skips non-positive token counts
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from vistarae_core.domain.exceptions import QuotaExceededError
from vistarae_core.services.token_budget import TokenBudgetService


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_quota_repo() -> AsyncMock:
    return AsyncMock()


class TestTokenBudgetService:
    """Unit tests for TokenBudgetService."""

    @pytest.mark.asyncio
    async def test_verify_budget_success(
        self, mock_quota_repo: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Pre-flight succeeds when repository confirms available budget."""
        mock_quota_repo.check_token_budget.return_value = True

        service = TokenBudgetService(mock_quota_repo)
        await service.verify_budget(test_user_id, required_tokens=500)

        mock_quota_repo.check_token_budget.assert_called_once_with(test_user_id, 500)

    @pytest.mark.asyncio
    async def test_verify_budget_exhausted_raises(
        self, mock_quota_repo: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Pre-flight raises QuotaExceededError when budget is exhausted."""
        mock_quota_repo.check_token_budget.return_value = False

        service = TokenBudgetService(mock_quota_repo)
        with pytest.raises(QuotaExceededError, match="Monthly token quota exceeded"):
            await service.verify_budget(test_user_id, required_tokens=100)

    @pytest.mark.asyncio
    async def test_record_usage_increments_tokens(
        self, mock_quota_repo: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Post-flight records consumed tokens via repository."""
        service = TokenBudgetService(mock_quota_repo)
        await service.record_usage(test_user_id, tokens=1250)

        mock_quota_repo.increment_tokens.assert_called_once_with(test_user_id, 1250)

    @pytest.mark.asyncio
    async def test_record_usage_zero_or_negative_tokens(
        self, mock_quota_repo: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Zero or negative tokens are ignored without calling repository."""
        service = TokenBudgetService(mock_quota_repo)
        await service.record_usage(test_user_id, tokens=0)
        await service.record_usage(test_user_id, tokens=-5)

        mock_quota_repo.increment_tokens.assert_not_called()
