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

"""SQLAlchemy 2.0 quota and rolling rate limit repository (T-031, T-040).

Implements IQuotaRepository interface with atomic rolling window rate limit
tracking and monthly token budget tracking.
Enforces Constitution Principle 3: Explicit WHERE user_id predicates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import UserMetricsTable, UserQuotasTable
from vistarae_core.domain.entities import UserQuota
from vistarae_core.domain.value_objects import UserTier

_TIER_LIMITS: dict[UserTier, int] = {
    UserTier.LOW: 60,
    UserTier.HIGH: 300,
    UserTier.ADMIN: 300,
}


class SqlAlchemyQuotaRepository:
    """SQLAlchemy 2.0 implementation of IQuotaRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an active AsyncSession.

        Args:
            session: AsyncSession database handle.
        """
        self._session = session

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves current quota state for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        stmt = select(UserQuotasTable).where(UserQuotasTable.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not isinstance(row, UserQuotasTable):
            return None
        return UserQuota(
            user_id=row.user_id,
            monthly_token_quota=row.monthly_token_quota,
            current_token_usage=row.current_token_usage,
            tier=UserTier(row.tier),
            request_count=row.request_count,
            window_start_at=row.window_start_at,
            is_disabled=row.is_disabled,
            updated_at=row.updated_at,
        )

    async def increment_request_count(
        self,
        user_id: UUID,
        tier: UserTier,
        window_seconds: int = 60,
    ) -> tuple[int, int, bool]:
        """Atomically increments rolling window request count.

        If the current timestamp exceeds the window boundary, resets count to 1
        and rolls the window forward.

        Args:
            user_id: UUID of the requesting tenant.
            tier: Current tenant governance tier.
            window_seconds: Rolling window duration in seconds.

        Returns:
            Tuple of (current_count, limit_for_tier, limit_exceeded).
        """
        now = datetime.now(UTC)
        limit = _TIER_LIMITS.get(tier, 60)

        stmt = select(UserQuotasTable).where(UserQuotasTable.user_id == user_id).with_for_update()
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if not isinstance(row, UserQuotasTable):
            # If no quota row exists yet, treat as within limit count 1
            return 1, limit, False

        window_start = row.window_start_at
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=UTC)

        if now - window_start >= timedelta(seconds=window_seconds):
            # Window expired — rollover
            row.request_count = 1
            row.window_start_at = now
            row.updated_at = now
            await self._session.flush()
            return 1, limit, False

        row.request_count += 1
        row.updated_at = now
        await self._session.flush()

        limit_exceeded = row.request_count > limit
        return row.request_count, limit, limit_exceeded

    async def check_token_budget(self, user_id: UUID, required_tokens: int) -> bool:
        """Verifies available token budget without mutating state.

        Args:
            user_id: UUID of the target tenant.
            required_tokens: Tokens required for prospective operation.

        Returns:
            True if budget is available, False if exhausted.
        """
        stmt = select(UserQuotasTable).where(UserQuotasTable.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not isinstance(row, UserQuotasTable):
            return False
        return (row.current_token_usage + required_tokens) <= row.monthly_token_quota

    async def increment_tokens(self, user_id: UUID, tokens: int) -> None:
        """Atomically adds consumed token count to quota and lifetime metrics.

        Args:
            user_id: UUID of the target tenant.
            tokens: Number of tokens consumed in the operation.
        """
        now = datetime.now(UTC)
        quota_stmt = (
            update(UserQuotasTable)
            .where(UserQuotasTable.user_id == user_id)
            .values(
                current_token_usage=UserQuotasTable.current_token_usage + tokens,
                updated_at=now,
            )
        )
        metric_stmt = (
            update(UserMetricsTable)
            .where(UserMetricsTable.user_id == user_id)
            .values(
                total_tokens_consumed=UserMetricsTable.total_tokens_consumed + tokens,
                updated_at=now,
            )
        )
        await self._session.execute(quota_stmt)
        await self._session.execute(metric_stmt)

    async def update_quota(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies administrative quota adjustments to a tenant.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        updates_clean = dict(updates)
        for k, v in list(updates_clean.items()):
            if hasattr(v, "value"):
                updates_clean[k] = v.value
        updates_clean["updated_at"] = datetime.now(UTC)
        stmt = (
            update(UserQuotasTable)
            .where(UserQuotasTable.user_id == user_id)
            .values(**updates_clean)
        )
        await self._session.execute(stmt)
