# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Core domain exceptions.

Independent domain error definitions decoupled from HTTP and transport layers.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain logic violations."""

    def __init__(self, message: str) -> None:
        """Initializes a domain error.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)
        self.message = message


class AccountDisabledError(DomainError):
    """Raised when an operation targets an administratively disabled tenant."""

    def __init__(self, user_id: str) -> None:
        """Initializes an account disabled error.

        Args:
            user_id: UUID string of the disabled user.
        """
        super().__init__(f"Account {user_id} is disabled.")
        self.user_id = user_id


class QuotaExceededError(DomainError):
    """Raised when an operation exceeds monthly token quota or rate limit."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Initializes a quota exceeded error.

        Args:
            message: Explanation of the quota boundary exceeded.
            retry_after: Optional seconds remaining before quota reset.
        """
        super().__init__(message)
        self.retry_after = retry_after


class IdempotencyConflictError(DomainError):
    """Raised when a concurrent mutating operation with the same key is in progress."""

    def __init__(self, idempotency_key: str) -> None:
        """Initializes an idempotency conflict error.

        Args:
            idempotency_key: The client key currently marked PENDING.
        """
        super().__init__(f"Concurrent mutation in progress for key: {idempotency_key}")
        self.idempotency_key = idempotency_key


class TenantNotFoundError(DomainError):
    """Raised when a tenant user account does not exist."""

    def __init__(self, identifier: str) -> None:
        """Initializes a tenant not found error.

        Args:
            identifier: User ID or Cognito sub that was not found.
        """
        super().__init__(f"Tenant account {identifier} not found.")
        self.identifier = identifier
