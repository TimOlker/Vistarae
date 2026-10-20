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

"""Unit tests for RateLimitMiddleware (T-030).

Tests cover:
- Health probe bypass (/health/* paths skip rate limiting)
- Requests without user_id pass through without error
- Requests with cached tier skip DB lookup
- Disabled account returns RFC 7807 403 before quota increment
- Limit exhaustion returns RFC 7807 429 with Retry-After header
- Successful requests under limit pass through
- Cache TTL expiry forces DB re-fetch
- invalidate_cache removes entry
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient
from vistarae_core.domain.value_objects import UserTier
from vistarae_core.middleware.rate_limit import (
    RateLimitMiddleware,
    _cache_get,
    _cache_set,
    _tier_cache,
    invalidate_cache,
)


def _clear_cache() -> None:
    """Empties the module-level tier cache between tests."""
    _tier_cache.clear()


class TestCacheOperations:
    """Unit tests for the in-memory tier cache helpers."""

    def setup_method(self) -> None:
        _clear_cache()

    def test_cache_miss_on_empty(self) -> None:
        """A fresh cache should return None for any user_id."""
        assert _cache_get(uuid4()) is None

    def test_cache_hit_within_ttl(self) -> None:
        """A recently set entry should be returned by _cache_get."""
        uid = uuid4()
        _cache_set(uid, UserTier.LOW, False)
        result = _cache_get(uid)
        assert result == (UserTier.LOW, False)

    def test_cache_miss_after_ttl_expiry(self) -> None:
        """Expired entries should be evicted and return None."""
        uid = uuid4()
        # Write an entry that expired 1 second ago.
        _tier_cache[uid] = (UserTier.LOW, False, time.monotonic() - 1.0)
        assert _cache_get(uid) is None

    def test_invalidate_removes_entry(self) -> None:
        """invalidate_cache should purge the entry for the given user."""
        uid = uuid4()
        _cache_set(uid, UserTier.HIGH, False)
        invalidate_cache(uid)
        assert _cache_get(uid) is None

    def test_invalidate_nonexistent_is_noop(self) -> None:
        """invalidate_cache on a non-cached user_id should not raise."""
        invalidate_cache(uuid4())  # Must not raise.


class TestRateLimitMiddlewareBypass:
    """Tests paths that should bypass rate limiting entirely."""

    def _make_app(self, user_id: UUID | None = None) -> Starlette:
        async def handler(request: Request) -> Response:
            return JSONResponse({"ok": True})

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Any) -> Response:
                if user_id:
                    request.state.user_id = user_id
                return await call_next(request)

        app = Starlette(routes=[Route("/health/live", handler), Route("/api/test", handler)])
        app.add_middleware(RateLimitMiddleware)
        app.add_middleware(InjectUserMiddleware)
        return app

    def test_health_probe_bypasses_rate_limiting(self) -> None:
        """Requests to /health/* must pass through with 200, no quota checks."""
        app = self._make_app(uuid4())
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health/live")
        assert resp.status_code == 200

    def test_no_user_id_passes_through(self) -> None:
        """Request without user_id in state should pass through as 200."""
        app = self._make_app(None)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")
        assert resp.status_code == 200


class TestRateLimitMiddlewareEnforcement:
    """Tests quota enforcement paths using mocked quota repository."""

    def setup_method(self) -> None:
        _clear_cache()

    def teardown_method(self) -> None:
        _clear_cache()

    def _make_app_with_repo(
        self, mock_repo: MagicMock, user_id: UUID, tier: str = "low", is_disabled: bool = False
    ) -> Starlette:
        async def handler(request: Request) -> Response:
            return JSONResponse({"ok": True})

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Any) -> Response:
                request.state.user_id = user_id
                request.app.state.quota_repo = mock_repo
                return await call_next(request)

        app = Starlette(routes=[Route("/api/test", handler)])
        app.add_middleware(RateLimitMiddleware)
        app.add_middleware(InjectUserMiddleware)
        return app

    def test_disabled_account_returns_403(self) -> None:
        """A user with is_disabled=True in cache should receive 403 immediately."""
        uid = uuid4()
        _cache_set(uid, UserTier.LOW, True)  # Pre-populate cache as disabled.

        mock_repo = AsyncMock()
        app = self._make_app_with_repo(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")

        assert resp.status_code == 403
        data = resp.json()
        assert data["type"] == "https://errors.vistarae.com/account-disabled"
        # DB increment must NOT be called for disabled accounts.
        mock_repo.increment_request_count.assert_not_called()

    def test_rate_limit_exceeded_returns_429(self) -> None:
        """When increment_request_count returns exceeded=True, must return 429."""
        uid = uuid4()
        _cache_set(uid, UserTier.LOW, False)

        mock_repo = AsyncMock()
        mock_repo.increment_request_count.return_value = (61, 60, True)

        app = self._make_app_with_repo(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        data = resp.json()
        assert data["type"] == "https://errors.vistarae.com/rate-limit-exceeded"

    def test_within_limit_passes_through(self) -> None:
        """When increment_request_count returns exceeded=False, request passes through."""
        uid = uuid4()
        _cache_set(uid, UserTier.HIGH, False)

        mock_repo = AsyncMock()
        mock_repo.increment_request_count.return_value = (5, 300, False)

        app = self._make_app_with_repo(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")

        assert resp.status_code == 200

    def test_cache_miss_falls_back_to_db(self) -> None:
        """On cache miss, quota_repo.get_quota must be called to load tier."""
        uid = uuid4()
        # Do not pre-populate cache.

        mock_quota = MagicMock()
        mock_quota.tier = UserTier.LOW
        mock_quota.is_disabled = False

        mock_repo = AsyncMock()
        mock_repo.get_quota.return_value = mock_quota
        mock_repo.increment_request_count.return_value = (1, 60, False)

        app = self._make_app_with_repo(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")

        assert resp.status_code == 200
        mock_repo.get_quota.assert_called_once_with(uid)

    def test_admin_tier_limit_is_300(self) -> None:
        """Admin tier should use the 300 req/min limit bucket."""
        uid = uuid4()
        _cache_set(uid, UserTier.ADMIN, False)

        mock_repo = AsyncMock()
        # Simulates count=300 at the exact limit — not exceeded.
        mock_repo.increment_request_count.return_value = (300, 300, False)

        app = self._make_app_with_repo(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")

        assert resp.status_code == 200
        call_args = mock_repo.increment_request_count.call_args
        assert call_args[0][1] == UserTier.ADMIN
