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

"""Unit tests for RFC 7807 problem details exception handlers (T-012).

Tests:
- RequestValidationError -> 422 with invalid_params
- StarletteHTTPException -> dynamic status code
- AccountDisabledError -> 403
- TenantNotFoundError -> 401
- QuotaExceededError -> 429 with Retry-After header
- IdempotencyConflictError -> 409
- Unhandled Exception -> 500
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from vistarae_core.domain.exceptions import (
    AccountDisabledError,
    IdempotencyConflictError,
    QuotaExceededError,
    TenantNotFoundError,
)
from vistarae_core.middleware.errors import add_problem_details_handlers


class DummyPayload(BaseModel):
    name: str = Field(min_length=3)
    count: int = Field(ge=1)


def create_error_test_app() -> FastAPI:
    """Creates a minimal FastAPI app configured with problem details handlers."""
    app = FastAPI()
    add_problem_details_handlers(app)

    @app.post("/test/validation")
    async def post_validation(payload: DummyPayload) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/test/http-error")
    async def get_http_error(code: int = 404) -> None:
        raise HTTPException(status_code=code, detail="Resource was not found")

    @app.get("/test/account-disabled")
    async def get_account_disabled() -> None:
        raise AccountDisabledError(user_id="11111111-1111-1111-1111-111111111111")

    @app.get("/test/tenant-not-found")
    async def get_tenant_not_found() -> None:
        raise TenantNotFoundError(identifier="user-123")

    @app.get("/test/quota-exceeded")
    async def get_quota_exceeded(retry_after: int | None = None) -> None:
        raise QuotaExceededError(message="Rate limit exceeded", retry_after=retry_after)

    @app.get("/test/idempotency-conflict")
    async def get_idempotency_conflict() -> None:
        raise IdempotencyConflictError(idempotency_key="test-key-123")

    @app.get("/test/unhandled")
    async def get_unhandled() -> None:
        raise RuntimeError("Something exploded")

    return app


@pytest.fixture
def error_client() -> TestClient:
    app = create_error_test_app()
    return TestClient(app, raise_server_exceptions=False)


class TestProblemDetailsHandlers:
    """Verifies exception handlers convert exceptions to application/problem+json."""

    def test_validation_error_handler(self, error_client: TestClient) -> None:
        """Pydantic validation error returns 422 with invalid_params list."""
        resp = error_client.post("/test/validation", json={"name": "x", "count": 0})
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/validation-error"
        assert body["status"] == 422
        assert len(body["invalid_params"]) >= 2

    def test_http_exception_handler(self, error_client: TestClient) -> None:
        """HTTPException returns ProblemDetails with given status."""
        resp = error_client.get("/test/http-error?code=403")
        assert resp.status_code == 403
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["status"] == 403
        assert "Resource was not found" in body["detail"]

    def test_account_disabled_handler(self, error_client: TestClient) -> None:
        """AccountDisabledError returns 403."""
        resp = error_client.get("/test/account-disabled")
        assert resp.status_code == 403
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/account-disabled"

    def test_tenant_not_found_handler(self, error_client: TestClient) -> None:
        """TenantNotFoundError returns 401."""
        resp = error_client.get("/test/tenant-not-found")
        assert resp.status_code == 401
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/user-not-found"

    def test_quota_exceeded_handler_with_retry_after(self, error_client: TestClient) -> None:
        """QuotaExceededError returns 429 and Retry-After header when provided."""
        resp = error_client.get("/test/quota-exceeded?retry_after=45")
        assert resp.status_code == 429
        assert resp.headers["content-type"] == "application/problem+json"
        assert resp.headers.get("retry-after") == "45"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/quota-exceeded"

    def test_quota_exceeded_handler_without_retry_after(self, error_client: TestClient) -> None:
        """QuotaExceededError returns 429 without Retry-After header when None."""
        resp = error_client.get("/test/quota-exceeded")
        assert resp.status_code == 429
        assert "retry-after" not in resp.headers

    def test_idempotency_conflict_handler(self, error_client: TestClient) -> None:
        """IdempotencyConflictError returns 409."""
        resp = error_client.get("/test/idempotency-conflict")
        assert resp.status_code == 409
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/idempotency-conflict"

    def test_unhandled_exception_handler(self, error_client: TestClient) -> None:
        """Unhandled exception returns 500 ProblemDetails."""
        resp = error_client.get("/test/unhandled")
        assert resp.status_code == 500
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.vistarae.com/internal-error"
        assert body["status"] == 500
