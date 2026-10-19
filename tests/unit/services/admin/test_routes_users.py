# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Admin tenant governance routes (T-042).

Tests:
- GET /api/admin/users/{user_id} found and 404
- PATCH /api/admin/users/{user_id}/quota and cache invalidation
- POST /api/admin/users/{user_id}/disable and cache invalidation
- POST /api/admin/users/{user_id}/enable and cache invalidation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserQuotasTable,
    UserTable,
)
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


class TestAdminUsersRoutes:
    """Tests for /api/admin/users/* endpoints."""

    def test_get_user_detail_found(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts user detail returned when tenant exists."""
        target_id = uuid.uuid4()
        now = datetime.now(UTC)
        fake_user = UserTable(
            id=target_id,
            cognito_sub="sub-target",
            email="target@example.com",
            full_name="Target User",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        fake_quota = UserQuotasTable(
            user_id=target_id,
            monthly_token_quota=60000,
            current_token_usage=5000,
            tier="low",
            is_disabled=False,
            updated_at=now,
        )
        fake_metrics = UserMetricsTable(
            user_id=target_id,
            poi_count=8,
            total_tokens_consumed=12000,
            updated_at=now,
        )
        mock_session.scalar.side_effect = [fake_user, fake_quota, fake_metrics]

        resp = client.get(f"/api/admin/users/{target_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["profile"]["id"] == str(target_id)
        assert data["quotas"]["monthly_token_quota"] == 60000
        assert data["metrics"]["poi_count"] == 8

    def test_get_user_detail_not_found(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts 404 when target tenant does not exist."""
        target_id = uuid.uuid4()
        mock_session.scalar.return_value = None

        resp = client.get(f"/api/admin/users/{target_id}")
        assert resp.status_code == 404

    def test_update_user_quota_success(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts PATCH updates quota and invalidates cache."""
        target_id = uuid.uuid4()
        now = datetime.now(UTC)
        fake_quota = UserQuotasTable(
            user_id=target_id,
            monthly_token_quota=150000,
            current_token_usage=10000,
            tier="high",
            is_disabled=False,
            updated_at=now,
        )
        mock_session.scalar.return_value = fake_quota

        with patch("services.admin.routes.users.invalidate_cache") as mock_inv:
            resp = client.patch(
                f"/api/admin/users/{target_id}/quota",
                json={"monthly_token_quota": 150000, "tier": "high"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["monthly_token_quota"] == 150000
            assert data["tier"] == "high"
            mock_session.execute.assert_called_once()
            mock_inv.assert_called_once_with(target_id)

    def test_disable_user_success(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts POST disable sets is_disabled=True and invalidates cache."""
        target_id = uuid.uuid4()
        with patch("services.admin.routes.users.invalidate_cache") as mock_inv:
            resp = client.post(f"/api/admin/users/{target_id}/disable")
            assert resp.status_code == 204
            mock_session.execute.assert_called_once()
            mock_inv.assert_called_once_with(target_id)

    def test_enable_user_success(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts POST enable sets is_disabled=False and invalidates cache."""
        target_id = uuid.uuid4()
        with patch("services.admin.routes.users.invalidate_cache") as mock_inv:
            resp = client.post(f"/api/admin/users/{target_id}/enable")
            assert resp.status_code == 204
            mock_session.execute.assert_called_once()
            mock_inv.assert_called_once_with(target_id)
