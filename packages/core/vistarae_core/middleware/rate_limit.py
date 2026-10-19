# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rolling-window rate limiting middleware with in-memory tier cache.

Implements Constitution Principle 6 (User Story 3 — REQ-QUOTA-004/006):
- 60-second TTL in-memory cache storing (UserTier, is_disabled, expiry_ts)
- Checks is_disabled → returns RFC 7807 403 before any DB access
- Checks rolling 1-minute window via IQuotaRepository.increment_request_count
- Returns RFC 7807 429 Too Many Requests with Retry-After header on exhaustion

Execution order under Starlette LIFO:
  RateLimitMiddleware registered second → executes AFTER IdempotencyMiddleware
  Outer: Telemetry → RateLimit → Idempotency : Inner
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from vistarae_core.domain.value_objects import UserTier

logger = logging.getLogger(__name__)

# Tier → requests-per-minute limits per REQ-QUOTA-001/002.
_TIER_LIMITS: dict[str, int] = {
    UserTier.LOW: 60,
    UserTier.HIGH: 300,
    UserTier.ADMIN: 300,
}

# In-memory cache: user_id → (tier, is_disabled, expiry_epoch_seconds)
_tier_cache: dict[UUID, tuple[str, bool, float]] = {}
_CACHE_TTL_SECONDS: float = 60.0

_MEDIA_TYPE = "application/problem+json"


def _cache_get(user_id: UUID) -> tuple[str, bool] | None:
    """Retrieves a cached (tier, is_disabled) pair if not expired.

    Args:
        user_id: UUID of the tenant to look up.

    Returns:
        Tuple of (tier, is_disabled) or None if absent/expired.
    """
    entry = _tier_cache.get(user_id)
    if entry is None:
        return None
    tier, is_disabled, expiry = entry
    if time.monotonic() >= expiry:
        del _tier_cache[user_id]
        return None
    return tier, is_disabled


def _cache_set(user_id: UUID, tier: str, is_disabled: bool) -> None:
    """Writes (tier, is_disabled) into the in-memory cache with a 60s TTL.

    Args:
        user_id: UUID of the tenant.
        tier: Current governance tier string.
        is_disabled: Whether the account is administratively locked.
    """
    _tier_cache[user_id] = (tier, is_disabled, time.monotonic() + _CACHE_TTL_SECONDS)


def invalidate_cache(user_id: UUID) -> None:
    """Removes a tenant's tier cache entry to force a DB refresh.

    Called by admin disable/enable and quota-update routes.

    Args:
        user_id: UUID of the tenant whose cache entry should be purged.
    """
    _tier_cache.pop(user_id, None)


# Public aliases for external integration testing
set_cached_tier = _cache_set
get_cached_tier = _cache_get


def _problem_429(detail: str, retry_after: int) -> JSONResponse:
    """Constructs an RFC 7807 429 Too Many Requests response.

    Args:
        detail: Human-readable explanation of the rate limit exhaustion.
        retry_after: Seconds until the rolling window resets.

    Returns:
        JSONResponse with application/problem+json content type and Retry-After header.
    """
    body = {
        "type": "https://errors.vistarae.com/rate-limit-exceeded",
        "title": "Too Many Requests",
        "status": 429,
        "detail": detail,
    }
    return JSONResponse(
        status_code=429,
        content=body,
        media_type=_MEDIA_TYPE,
        headers={"Retry-After": str(retry_after)},
    )


def _problem_403(detail: str) -> JSONResponse:
    """Constructs an RFC 7807 403 Forbidden response for disabled accounts.

    Args:
        detail: Human-readable description of the account suspension.

    Returns:
        JSONResponse with application/problem+json content type.
    """
    body = {
        "type": "https://errors.vistarae.com/account-disabled",
        "title": "Account Disabled",
        "status": 403,
        "detail": detail,
    }
    return JSONResponse(status_code=403, content=body, media_type=_MEDIA_TYPE)


def _resolve_request_user_id(request: Request) -> UUID | None:
    """Extracts tenant UUID from request state or mock header in local stage."""
    user_id: UUID | None = getattr(request.state, "user_id", None)
    if user_id is not None:
        return user_id

    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local"))
    if stage == "local":
        mock_id = request.headers.get("X-Mock-User-Id")
        if mock_id:
            try:
                user_id = UUID(mock_id)
                request.state.user_id = user_id
                return user_id
            except (ValueError, AttributeError):
                pass
    return None


def _get_request_quota_repo(request: Request) -> Any:
    """Resolves quota repository from app.state or dependency overrides."""
    repo = getattr(request.app.state, "quota_repo", None)
    if repo is not None:
        return repo
    try:
        from vistarae_core.adapters.db.session import get_db_session
        from vistarae_core.adapters.repositories.quota_repo import SqlAlchemyQuotaRepository

        override = request.app.dependency_overrides.get(get_db_session)
        session = override() if override else None
        return SqlAlchemyQuotaRepository(session)
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces per-tenant rolling-window rate limits with an in-memory tier cache.

    Health check paths (/health/*) bypass rate limiting entirely to protect
    Neon's scale-to-zero quota from being consumed by monitoring probes.
    """

    # Paths that must never be subject to rate limiting.
    _BYPASS_PREFIXES: tuple[str, ...] = ("/health/",)

    def __init__(self, app: ASGIApp) -> None:
        """Initializes the middleware.

        Args:
            app: Inner ASGI application.
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Intercepts each request and enforces quota constraints.

        Skips rate limiting for unauthenticated paths and health probes.
        Checks the in-memory cache first; falls back to the DB repository on cache miss.

        Args:
            request: Incoming HTTP request.
            call_next: Next ASGI handler.

        Returns:
            Original response or an RFC 7807 error response.
        """
        path = request.url.path

        # Bypass rate limiting for health probes.
        for prefix in self._BYPASS_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Resolve authenticated user identity.
        user_id = _resolve_request_user_id(request)
        if user_id is None:
            # No user context yet — allow the request to proceed to auth.
            return await call_next(request)

        # ── 1. Try in-memory cache ──────────────────────────────────────────
        cached = get_cached_tier(user_id)
        if cached is not None:
            tier_str, is_disabled = cached
        else:
            # ── 2. DB fallback ──────────────────────────────────────────────
            repo = _get_request_quota_repo(request)
            if repo is None:
                # No repository mounted (e.g., during isolated unit tests).
                return await call_next(request)

            quota = await repo.get_quota(user_id)
            if quota is None:
                return await call_next(request)

            tier_str = str(quota.tier)
            is_disabled = quota.is_disabled
            set_cached_tier(user_id, tier_str, is_disabled)

        # ── 3. Disabled account short-circuit ──────────────────────────────
        if is_disabled:
            return _problem_403(f"Account {user_id} has been administratively disabled.")

        # ── 4. Rolling window increment ────────────────────────────────────
        repo = _get_request_quota_repo(request)
        if repo is None:
            return await call_next(request)

        tier = UserTier(tier_str)
        count, limit, exceeded = await repo.increment_request_count(user_id, tier)

        if exceeded:
            retry_after = 60  # Window length in seconds.
            return _problem_429(
                f"Rate limit of {limit} req/min exceeded for tier '{tier_str}'. "
                f"Please wait {retry_after} seconds before retrying.",
                retry_after=retry_after,
            )

        return await call_next(request)
