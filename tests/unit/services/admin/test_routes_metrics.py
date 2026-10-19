# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Admin platform metrics route (T-042).

Tests GET /api/admin/metrics aggregation:
- total_users, active_users, disabled_users, total_pois, total_tokens_consumed, tier_distribution
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import UserTier

from services.admin.dependencies import require_admin
from services.admin.main import app


@pytest.fixture
def admin_user() -> User:
    u = User(
        id=uuid.uuid4(),
        cognito_sub="sub-admin",
        email="admin@example.com",
    )
    u._tier = UserTier.ADMIN
    return u


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(admin_user: User, mock_session: AsyncMock) -> TestClient:
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestAdminMetricsRoute:
    """Tests for GET /api/admin/metrics."""

    def test_get_metrics_success(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Asserts metrics aggregation produces expected values."""
        # Scalars: total_users=10, active_users=8, disabled_users=2, total_pois=120, total_tokens=45000
        mock_session.scalar.side_effect = [10, 8, 2, 120, 45000]

        row1 = MagicMock()
        row1.tier = "low"
        row1.count = 7
        row2 = MagicMock()
        row2.tier = "high"
        row2.count = 3
        mock_execute = MagicMock()
        mock_execute.side_effect = None
        mock_execute.__iter__.return_value = [row1, row2]
        mock_session.execute.return_value = [row1, row2]

        resp = client.get("/api/admin/metrics")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_users"] == 10
        assert data["active_users"] == 8
        assert data["disabled_users"] == 2
        assert data["total_pois"] == 120
        assert data["total_tokens_consumed"] == 45000
        assert data["tier_distribution"] == {"low": 7, "high": 3}

    @pytest.mark.asyncio
    async def test_admin_lifespan(self) -> None:
        """Asserts lifespan initializes and disposes engine."""
        from services.admin.main import app as a_app
        from services.admin.main import lifespan as a_lifespan

        mock_engine = AsyncMock()
        with (
            patch("services.admin.main.init_engine", new_callable=AsyncMock) as mock_init,
            patch("services.admin.main.get_engine", return_value=mock_engine),
        ):
            async with a_lifespan(a_app):
                mock_init.assert_called_once()
                mock_engine.dispose.assert_not_called()
            mock_engine.dispose.assert_called_once()

