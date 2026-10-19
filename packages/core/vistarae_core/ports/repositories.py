# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Abstract repository port interfaces.

Isolates external persistence dependencies behind typing.Protocol contracts per
Constitution Principle 2 (Ports & Adapters). No ORM or driver imports allowed.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from vistarae_core.domain.entities import (
    IdempotencyRecord,
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.value_objects import IdempotencyStatus, UserTier


class IUserRepository(Protocol):
    """Persistence contract for tenant identity management."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieves a user by primary key.

        Args:
            user_id: UUID of the target user.

        Returns:
            User entity or None if not found.
        """
        ...

    async def get_by_cognito_sub(self, sub: str) -> User | None:
        """Resolves a user entity from a Cognito JWT subject claim.

        Args:
            sub: Cognito unique subject identifier.

        Returns:
            Matched User entity or None.
        """
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Resolves a user entity by registered email address.

        Args:
            email: User's registered email address.

        Returns:
            Matched User entity or None.
        """
        ...

    async def create(
        self,
        user: User,
        preferences: UserPreferences,
        quotas: UserQuota,
        metrics: UserMetric,
    ) -> User:
        """Inserts a new tenant with all sub-tables atomically.

        Args:
            user: Core user aggregate.
            preferences: Partitioned tenant preferences.
            quotas: Initial quota allocation.
            metrics: Zero-initialized utilization metrics.

        Returns:
            Persisted User entity with database-assigned defaults.
        """
        ...

    async def update_profile(self, user_id: UUID, full_name: str) -> None:
        """Updates user display name.

        Args:
            user_id: UUID of the tenant.
            full_name: New display name value.
        """
        ...

    async def delete(self, user_id: UUID) -> None:
        """Permanently removes a tenant and all cascaded sub-records.

        Args:
            user_id: UUID of the tenant to delete.
        """
        ...

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        """Retrieves the preferences record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserPreferences entity or None if not found.
        """
        ...

    async def update_preferences(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies a partial update to tenant preferences.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        ...

    async def get_metrics(self, user_id: UUID) -> UserMetric | None:
        """Retrieves aggregate metrics for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserMetric entity or None.
        """
        ...

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves the quota record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        ...


class IQuotaRepository(Protocol):
    """Persistence contract for rolling rate limiting and token budgeting."""

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves current quota state for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        ...

    async def increment_request_count(
        self,
        user_id: UUID,
        tier: UserTier,
        window_seconds: int = 60,
    ) -> tuple[int, int, bool]:
        """Atomically increments rolling window request count.

        Args:
            user_id: UUID of the requesting tenant.
            tier: Current tenant governance tier.
            window_seconds: Rolling window duration in seconds.

        Returns:
            Tuple of (current_count, limit_for_tier, limit_exceeded).
        """
        ...

    async def check_token_budget(self, user_id: UUID, required_tokens: int) -> bool:
        """Verifies available token budget without mutating state.

        Args:
            user_id: UUID of the target tenant.
            required_tokens: Tokens required for the prospective operation.

        Returns:
            True if budget is available, False if exhausted.
        """
        ...

    async def increment_tokens(self, user_id: UUID, tokens: int) -> None:
        """Atomically adds consumed token count to quota and lifetime metrics.

        Args:
            user_id: UUID of the target tenant.
            tokens: Number of tokens consumed in the operation.
        """
        ...

    async def update_quota(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies administrative quota adjustments to a tenant.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        ...


class IIdempotencyRepository(Protocol):
    """Persistence contract for duplicate mutation prevention."""

    async def get_or_create(
        self,
        user_id: UUID,
        key: str,
    ) -> tuple[IdempotencyStatus, int | None, dict[str, Any] | None]:
        """Atomically retrieves or creates an idempotency record.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client-provided idempotency key string.

        Returns:
            Tuple of (status, cached_response_code, cached_payload).
        """
        ...

    async def complete(
        self,
        user_id: UUID,
        key: str,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        """Marks key as COMPLETED and stores cached response.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to finalize.
            status_code: HTTP status code of the successful response.
            payload: Serializable response body to cache.
        """
        ...

    async def fail(self, user_id: UUID, key: str) -> None:
        """Marks a key FAILED so subsequent retries can proceed.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to mark failed.
        """
        ...

    async def cleanup_older_than(self, hours: int = 24) -> int:
        """Purges idempotency records older than the given age.

        Args:
            hours: Age threshold in hours. Records older than this are deleted.

        Returns:
            Count of records deleted.
        """
        ...

    async def get_record(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        """Retrieves a single idempotency record by composite key.

        Args:
            user_id: UUID of the tenant.
            key: Client idempotency key string.

        Returns:
            IdempotencyRecord or None if not found.
        """
        ...
