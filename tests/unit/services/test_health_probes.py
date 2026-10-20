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

"""Unit tests for dual-probe health endpoints (T-015).

Tests:
- GET /health/live returns 200 OK without DB query
- GET /health/ready returns 200 OK when DB connection succeeds
- GET /health/ready returns 503 Service Unavailable when DB connection fails
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session

from services.local_gateway import app


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(mock_session: AsyncMock) -> TestClient:
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestHealthProbes:
    """Tests for liveness and readiness health endpoints."""

    def test_health_live_probe(self, client: TestClient) -> None:
        """Asserts /health/live returns 200 OK with status alive."""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_health_ready_probe_success(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts /health/ready executes SELECT 1 and returns 200 ready."""
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}
        mock_session.execute.assert_called_once()

    def test_health_ready_probe_db_failure(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Asserts /health/ready returns RFC 7807 503 ProblemDetails when database execution raises."""
        mock_session.execute.side_effect = ConnectionRefusedError("DB offline")
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.headers["content-type"] == "application/problem+json"
        data = resp.json()
        assert data["type"] == "https://errors.vistarae.com/database-unreachable"
        assert data["title"] == "Database Unreachable"
        assert data["status"] == 503
        assert "DB offline" in data["detail"]
        assert data["instance"] == "/health/ready"
