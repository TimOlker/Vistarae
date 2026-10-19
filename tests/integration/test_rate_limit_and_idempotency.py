# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for Rate-Limiting and Idempotency middleware under Starlette LIFO (T-035).

Verifies:
- Starlette LIFO middleware execution: RateLimitMiddleware executes before IdempotencyMiddleware
- Rate limit exhaustion returns 429 without allocating idempotency records
- Completed idempotent mutation replays with X-Cache-Lookup: HIT
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.value_objects import IdempotencyStatus, UserTier
from vistarae_core.middleware.rate_limit import invalidate_cache

from services.admin.main import app as admin_app
from services.local_gateway import app
from services.user.main import app as user_app


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(mock_session: AsyncMock) -> TestClient:
    app.dependency_overrides[get_db_session] = lambda: mock_session
    user_app.dependency_overrides[get_db_session] = lambda: mock_session
    admin_app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
    user_app.dependency_overrides.clear()
    admin_app.dependency_overrides.clear()


class TestRateLimitAndIdempotencyOrder:
    """Verifies middleware execution sequence and interaction."""

    def test_rate_limit_short_circuits_before_idempotency_allocation(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When rate limit is exceeded, 429 returns before idempotency repository is called."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()
        invalidate_cache(test_id)

        # Mock rate limit check to return limit exceeded
        with (
            patch(
                "vistarae_core.middleware.rate_limit.get_cached_tier",
                return_value=(UserTier.LOW, False),
            ),
            patch(
                "vistarae_core.adapters.repositories.quota_repo.SqlAlchemyQuotaRepository.increment_request_count",
                new_callable=AsyncMock,
            ) as mock_incr,
            patch(
                "vistarae_core.adapters.repositories.idempotency_repo.SqlAlchemyIdempotencyRepository.get_or_create",
                new_callable=AsyncMock,
            ) as mock_idemp,
        ):
            mock_incr.return_value = (61, 60, True)  # Exceeded!

            resp = client.patch(
                "/api/users/me",
                headers={
                    "X-Mock-User-Id": str(test_id),
                    "Idempotency-Key": "test-idem-key",
                },
                json={"full_name": "New Name"},
            )

            assert resp.status_code == 429
            assert resp.headers["content-type"] == "application/problem+json"
            # Crucial: Idempotency repo must NOT have been called
            mock_idemp.assert_not_called()

    def test_idempotent_mutation_replay(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Completed idempotent request replays cached payload with X-Cache-Lookup: HIT."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()

        with (
            patch(
                "vistarae_core.middleware.rate_limit.get_cached_tier",
                return_value=(UserTier.LOW, False),
            ),
            patch(
                "vistarae_core.adapters.repositories.quota_repo.SqlAlchemyQuotaRepository.increment_request_count",
                new_callable=AsyncMock,
            ) as mock_incr,
            patch(
                "vistarae_core.adapters.repositories.idempotency_repo.SqlAlchemyIdempotencyRepository.get_or_create",
                new_callable=AsyncMock,
            ) as mock_idemp,
        ):
            mock_incr.return_value = (1, 60, False)
            mock_idemp.return_value = (
                IdempotencyStatus.COMPLETED,
                200,
                {"id": str(test_id), "email": "cached@example.com", "full_name": "Cached"},
            )

            resp = client.patch(
                "/api/users/me",
                headers={
                    "X-Mock-User-Id": str(test_id),
                    "Idempotency-Key": "cached-key-1",
                },
                json={"full_name": "Ignored"},
            )

            assert resp.status_code == 200
            assert resp.headers.get("x-cache-lookup") == "HIT"
            assert resp.json()["full_name"] == "Cached"
