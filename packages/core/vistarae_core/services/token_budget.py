# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Token budget domain service (T-039).

Implements REQ-QUOTA-013, REQ-QUOTA-014, and REQ-QUOTA-015:
- Pre-flight token quota verification
- Rejection with QuotaExceededError when monthly quota is exhausted
- Atomic post-flight token consumption recording
"""

from __future__ import annotations

import logging
from uuid import UUID

from vistarae_core.domain.exceptions import QuotaExceededError
from vistarae_core.ports.repositories import IQuotaRepository

logger = logging.getLogger(__name__)


class TokenBudgetService:
    """Domain service managing LLM token budgeting and consumption tracking."""

    def __init__(self, quota_repo: IQuotaRepository) -> None:
        """Initializes the service with a quota repository port.

        Args:
            quota_repo: IQuotaRepository port implementation.
        """
        self._quota_repo = quota_repo

    async def verify_budget(self, user_id: UUID, required_tokens: int = 1) -> None:
        """Pre-flight check verifying user has available monthly token budget.

        Args:
            user_id: UUID of the requesting tenant.
            required_tokens: Estimated or minimum tokens needed for the operation.

        Raises:
            QuotaExceededError: If current token usage has reached or exceeded quota.
        """
        has_budget = await self._quota_repo.check_token_budget(user_id, required_tokens)
        if not has_budget:
            logger.warning(
                "MSG <~~| [token_budget.py] Token quota exhausted for user_id=%s",
                user_id,
            )
            raise QuotaExceededError(
                message="Monthly token quota exceeded. Please upgrade your tier or wait for quota reset."
            )

    async def record_usage(self, user_id: UUID, tokens: int) -> None:
        """Atomically records consumed tokens to user_quotas and user_metrics.

        Args:
            user_id: UUID of the requesting tenant.
            tokens: Number of tokens consumed in the LLM operation.
        """
        if tokens <= 0:
            return

        await self._quota_repo.increment_tokens(user_id, tokens)
        logger.debug(
            "MSG |-> [token_budget.py] Recorded %d consumed tokens for user_id=%s",
            tokens,
            user_id,
        )
