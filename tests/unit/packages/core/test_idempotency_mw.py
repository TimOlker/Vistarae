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

"""Unit tests for IdempotencyMiddleware (T-034).

Tests cover:
- Non-mutating methods (GET, HEAD) pass through without key inspection
- Missing Idempotency-Key header passes through for mutating methods
- Missing user_id in request state passes through
- Missing idempotency_repo in app state passes through
- PENDING status with no cached response → 409 Conflict
- COMPLETED status → 200 replay with X-Cache-Lookup: HIT header
- Newly created PENDING → downstream executed and COMPLETED on 2XX
- Downstream failure marks FAILED
- FAILED status allows retry by re-executing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient
from vistarae_core.domain.value_objects import IdempotencyStatus
from vistarae_core.middleware.idempotency import IdempotencyMiddleware


def _make_app(
    mock_repo: Any | None,
    user_id: UUID | None,
    handler_status: int = 200,
    handler_body: dict | None = None,
) -> Starlette:
    """Constructs a test Starlette app with IdempotencyMiddleware.

    Args:
        mock_repo: Mock idempotency repository to inject into app.state.
        user_id: UUID to inject into request.state.
        handler_status: HTTP status code returned by the test handler.
        handler_body: JSON body returned by the test handler.

    Returns:
        Configured Starlette test application.
    """
    body = handler_body or {"result": "created"}

    async def handler(request: Request) -> Response:
        return JSONResponse(body, status_code=handler_status)

    class InjectStateMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            if user_id:
                request.state.user_id = user_id
            if mock_repo is not None:
                request.app.state.idempotency_repo = mock_repo
            return await call_next(request)

    app = Starlette(routes=[Route("/api/pois", handler, methods=["GET", "POST"])])
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(InjectStateMiddleware)
    return app


class TestIdempotencyMiddlewareBypass:
    """Tests requests that should bypass idempotency enforcement."""

    def test_get_request_bypasses_idempotency(self) -> None:
        """GET requests must not be subject to idempotency enforcement."""
        mock_repo = AsyncMock()
        app = _make_app(mock_repo, uuid4())
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/pois")
        assert resp.status_code == 200
        mock_repo.get_or_create.assert_not_called()

    def test_post_without_key_header_bypasses(self) -> None:
        """POST without Idempotency-Key header should pass through."""
        mock_repo = AsyncMock()
        app = _make_app(mock_repo, uuid4())
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois")
        assert resp.status_code == 200
        mock_repo.get_or_create.assert_not_called()

    def test_post_without_user_id_bypasses(self) -> None:
        """POST with Idempotency-Key but no user_id in state passes through."""
        mock_repo = AsyncMock()
        app = _make_app(mock_repo, None)  # No user_id injected.
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-abc"})
        assert resp.status_code == 200
        mock_repo.get_or_create.assert_not_called()

    def test_post_without_repo_bypasses(self) -> None:
        """POST with user_id but no repo in app.state passes through."""
        app = _make_app(None, uuid4())  # No repo injected.
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-abc"})
        assert resp.status_code == 200


class TestIdempotencyMiddlewareConflict:
    """Tests PENDING key behavior."""

    def test_pending_key_returns_409(self) -> None:
        """Existing PENDING record with response_code set should return 409."""
        uid = uuid4()
        mock_repo = AsyncMock()
        # status=PENDING with cached_code=201 means concurrent in-flight request.
        mock_repo.get_or_create.return_value = (IdempotencyStatus.PENDING, 201, None)

        app = _make_app(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-concurrent"})

        assert resp.status_code == 409
        data = resp.json()
        assert data["type"] == "https://errors.vistarae.com/idempotency-conflict"
        assert "key-concurrent" in data["detail"]


class TestIdempotencyMiddlewareReplay:
    """Tests COMPLETED key replay behavior."""

    def test_completed_key_replays_cached_response(self) -> None:
        """COMPLETED key should return the cached body with X-Cache-Lookup: HIT."""
        uid = uuid4()
        cached_payload = {"id": "poi-123", "name": "Eiffel Tower"}
        mock_repo = AsyncMock()
        mock_repo.get_or_create.return_value = (IdempotencyStatus.COMPLETED, 201, cached_payload)

        app = _make_app(mock_repo, uid)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-done"})

        assert resp.status_code == 201
        assert resp.headers.get("X-Cache-Lookup") == "HIT"
        assert resp.json() == cached_payload


class TestIdempotencyMiddlewareNewRequest:
    """Tests first-time (newly inserted PENDING) request lifecycle."""

    def test_new_pending_executes_and_caches_on_success(self) -> None:
        """Newly created PENDING record should execute handler and call repo.complete."""
        uid = uuid4()
        mock_repo = AsyncMock()
        # (PENDING, None, None) = newly inserted — not a concurrent conflict.
        mock_repo.get_or_create.return_value = (IdempotencyStatus.PENDING, None, None)

        app = _make_app(mock_repo, uid, handler_status=201, handler_body={"created": True})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-new"})

        assert resp.status_code == 201
        assert resp.json() == {"created": True}
        mock_repo.complete.assert_called_once_with(uid, "key-new", 201, {"created": True})
        mock_repo.fail.assert_not_called()

    def test_new_pending_marks_failed_on_4xx_response(self) -> None:
        """Non-2XX response from handler should mark the key as FAILED."""
        uid = uuid4()
        mock_repo = AsyncMock()
        mock_repo.get_or_create.return_value = (IdempotencyStatus.PENDING, None, None)

        app = _make_app(mock_repo, uid, handler_status=422, handler_body={"error": "bad"})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-fail"})

        assert resp.status_code == 422
        mock_repo.fail.assert_called_once_with(uid, "key-fail")
        mock_repo.complete.assert_not_called()


class TestIdempotencyMiddlewareFailedRetry:
    """Tests that FAILED keys allow retry by re-executing the downstream handler."""

    def test_failed_key_allows_retry(self) -> None:
        """FAILED status should re-execute the handler and attempt completion."""
        uid = uuid4()
        mock_repo = AsyncMock()
        # First call: FAILED → retry. _execute_and_cache will run again.
        mock_repo.get_or_create.return_value = (IdempotencyStatus.FAILED, None, None)
        # Retry succeeds:
        mock_repo.complete.return_value = None

        app = _make_app(mock_repo, uid, handler_status=200, handler_body={"retry": "ok"})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/pois", headers={"Idempotency-Key": "key-retry"})

        assert resp.status_code == 200
        mock_repo.complete.assert_called_once()
