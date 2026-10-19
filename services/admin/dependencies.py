# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Admin RBAC dependency — enforces admin tier on all /api/admin/* routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import UserTier

from services.user.dependencies import get_current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to admin-tier tenants only.

    Resolves the authenticated user and asserts that the caller's tier is
    'admin'. Non-admin callers receive RFC 7807 403 Forbidden.

    Args:
        current_user: Authenticated user entity from the shared auth dependency.

    Returns:
        The same User entity, passed through unchanged.

    Raises:
        HTTPException: 403 Forbidden if the caller is not an admin.
    """
    # Tier is sourced from the user_quotas table via the auth dependency.
    # The actual quota row is not loaded in the dependency; admin status is
    # injected via the Cognito group claim in cloud, or the mock tier header locally.
    # For simplicity in this implementation we check a state attribute set by
    # the auth flow; callers may also inject via X-Mock-User-Tier in local stage.
    tier_str: str = getattr(current_user, "_tier", UserTier.LOW)

    if tier_str != UserTier.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Administrative access required. "
                "Your account does not have the 'admin' governance tier."
            ),
        )

    return current_user
