# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for authentication lifecycle, local bypass, and GDPR deletion (T-018).

Verifies:
- User context resolution via X-Mock-User-Id when STAGE == 'local'
- Rejection of unauthenticated requests
- Profile update
- GDPR cascade deletion
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)

from services.admin.main import app as admin_app
from services.local_gateway import app as gateway
from services.user.main import app as user_app


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(mock_session: AsyncMock) -> TestClient:
    gateway.dependency_overrides[get_db_session] = lambda: mock_session
    user_app.dependency_overrides[get_db_session] = lambda: mock_session
    admin_app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(gateway, raise_server_exceptions=False)
    yield client
    gateway.dependency_overrides.clear()
    user_app.dependency_overrides.clear()
    admin_app.dependency_overrides.clear()


class TestAuthLifecycleIntegration:
    """Integration scenarios for authentication and GDPR deletion."""

    def test_unauthenticated_request_rejected(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Requests without Authorization or X-Mock-User-Id return 401."""
        monkeypatch.setenv("STAGE", "production")
        resp = client.get("/api/users/me")
        assert resp.status_code == 401

    def test_local_bypass_and_profile_flow(
        self, client: TestClient, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """STAGE == 'local' with X-Mock-User-Id resolves user and allows profile update."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_user = UserTable(
            id=test_id,
            cognito_sub=str(test_id),
            email="test@local.vistarae.dev",
            full_name="Test User",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        fake_prefs = UserPreferencesTable(user_id=test_id, created_at=now, updated_at=now)
        fake_metrics = UserMetricsTable(user_id=test_id, updated_at=now)
        fake_quota = UserQuotasTable(user_id=test_id, tier="low", window_start_at=now, updated_at=now)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_session.execute.return_value = mock_result
        mock_session.scalar.side_effect = [fake_prefs, fake_metrics, fake_quota]

        # GET /me
        resp = client.get("/api/users/me", headers={"X-Mock-User-Id": str(test_id)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["id"] == str(test_id)

        # PATCH /me
        mock_result_patch = MagicMock()
        mock_result_patch.scalar_one_or_none.return_value = fake_user
        mock_session.execute.return_value = mock_result_patch
        patch_resp = client.patch(
            "/api/users/me",
            headers={"X-Mock-User-Id": str(test_id)},
            json={"full_name": "Updated Name"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["full_name"] == "Updated Name"

    def test_gdpr_deletion_flow(
        self, client: TestClient, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DELETE /me executes Cognito deletion and deletes user row from DB."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_user = UserTable(
            id=test_id,
            cognito_sub=str(test_id),
            email="gdpr@local.vistarae.dev",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_session.execute.return_value = mock_result
        mock_session.scalar.return_value = fake_user

        with patch("services.user.routes.me._cognito.delete_user", new_callable=AsyncMock) as mock_cog:
            del_resp = client.delete("/api/users/me", headers={"X-Mock-User-Id": str(test_id)})
            assert del_resp.status_code == 204
            mock_cog.assert_called_once_with(str(test_id))
            mock_session.execute.assert_called()
