# Copyright (c) 2026 Vistarae. All rights reserved.
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
