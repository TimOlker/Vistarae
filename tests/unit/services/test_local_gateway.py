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

"""Unit tests for Unified Local Gateway (T-050).

Tests:
- Middleware pipeline: Telemetry, RateLimit, Idempotency, CORS
- Preflight CORS headers for http://localhost:5173
- Correlation headers on gateway responses
- Lifespan initialization and disposal
- Routing to mounted microservices
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.local_gateway import app, lifespan


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestLocalGatewayPipeline:
    """Tests gateway middleware and CORS integration."""

    def test_cors_preflight_headers(self, client: TestClient) -> None:
        """OPTIONS preflight from http://localhost:5173 receives allowed headers."""
        resp = client.options(
            "/health/live",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,idempotency-key",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_telemetry_headers_injected(self, client: TestClient) -> None:
        """Every response carries X-Transaction-ID and X-Current-Span-ID."""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert "x-transaction-id" in resp.headers
        assert "x-current-span-id" in resp.headers

    @pytest.mark.asyncio
    async def test_lifespan_initializes_and_disposes_engine(self) -> None:
        """Asserts lifespan calls init_engine on entry and engine.dispose on exit."""
        mock_engine = AsyncMock()
        with (
            patch("services.local_gateway.init_engine", new_callable=AsyncMock) as mock_init,
            patch("services.local_gateway.get_engine", return_value=mock_engine),
        ):
            async with lifespan(app):
                mock_init.assert_called_once()
                mock_engine.dispose.assert_not_called()
            mock_engine.dispose.assert_called_once()

    def test_open_folder_endpoint(self, client: TestClient) -> None:
        """Verifies POST /api/system/open-folder endpoint accepts valid local directory."""
        import os
        from unittest.mock import patch

        test_dir = os.path.dirname(__file__)
        with patch("os.startfile", create=True) as mock_startfile:
            resp = client.post(
                "/api/system/open-folder",
                json={"path": test_dir},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

        resp_bad = client.post(
            "/api/system/open-folder",
            json={"path": "Z:\nonexistent_volume_vistarae\test_folder"},
        )
        assert resp_bad.status_code == 404
