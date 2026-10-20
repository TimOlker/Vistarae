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

"""Unit tests for IngestFunction health probes (T-011).

Verifies:
- GET /health/live returns 200 OK without I/O
- GET /health/ready returns 200 OK when both DB and SQS are healthy
- GET /health/ready returns 503 ProblemDetails when DB is unreachable
- GET /health/ready returns 503 ProblemDetails when SQS is unreachable
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.adapters.db.session import get_db_session

from services.ingest.dependencies import get_queue_port
from services.ingest.main import app


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Verifies liveness and readiness probe behaviors."""

    async def test_health_live_endpoint(self) -> None:
        """Asserts zero-IO liveness probe returns 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health/live")
            assert response.status_code == 200
            assert response.json() == {"status": "alive"}

    async def test_health_ready_all_healthy(self) -> None:
        """Asserts readiness probe returns 200 OK when DB and SQS are available."""
        mock_session = AsyncMock()
        mock_queue = AsyncMock()
        mock_queue.receive_messages.return_value = []

        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_queue_port] = lambda: mock_queue

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health/ready")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ready"
                assert data["database"] == "healthy"
                assert data["queue"] == "healthy"
        finally:
            app.dependency_overrides.clear()

    async def test_health_ready_db_failure(self) -> None:
        """Asserts readiness probe returns 503 ProblemDetails on database error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionRefusedError("DB connection refused")
        mock_queue = AsyncMock()

        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_queue_port] = lambda: mock_queue

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health/ready")
                assert response.status_code == 503
                assert response.headers["content-type"] == "application/problem+json"
                data = response.json()
                assert data["title"] == "Database Unreachable"
                assert data["status"] == 503
        finally:
            app.dependency_overrides.clear()

    async def test_health_ready_queue_failure(self) -> None:
        """Asserts readiness probe returns 503 ProblemDetails on SQS error."""
        mock_session = AsyncMock()
        mock_queue = AsyncMock()
        mock_queue.receive_messages.side_effect = RuntimeError("SQS unreachable")

        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_queue_port] = lambda: mock_queue

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/health/ready")
                assert response.status_code == 503
                assert response.headers["content-type"] == "application/problem+json"
                data = response.json()
                assert data["title"] == "Queue Unreachable"
                assert data["status"] == 503
        finally:
            app.dependency_overrides.clear()

    async def test_ingest_lifespan(self) -> None:
        """Asserts IngestFunction lifespan properly initializes and disposes engine."""
        from unittest.mock import patch

        from services.ingest.main import lifespan

        with (
            patch("services.ingest.main.init_engine", new_callable=AsyncMock) as mock_init,
            patch("services.ingest.main.get_engine") as mock_get_engine,
        ):
            mock_engine = AsyncMock()
            mock_get_engine.return_value = mock_engine

            async with lifespan(app):
                mock_init.assert_called_once()

            mock_engine.dispose.assert_called_once()
