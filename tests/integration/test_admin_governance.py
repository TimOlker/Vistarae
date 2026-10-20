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

"""Integration tests for Administrative Governance and tenant disablement (T-043).

Verifies:
- Non-admin callers receive RFC 7807 403 Forbidden on admin endpoints
- Admin caller inspects metrics and disables target user
- Disabled user is blocked from making further requests (403 Forbidden)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import (
    UserTable,
)
from vistarae_core.domain.value_objects import UserTier
from vistarae_core.middleware.rate_limit import set_cached_tier

from services.admin.dependencies import require_admin
from services.admin.main import app as admin_app
from services.local_gateway import app
from services.user.main import app as user_app


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


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


class TestAdminGovernanceIntegration:
    """Verifies end-to-end admin inspection, RBAC, and disablement."""

    def test_non_admin_forbidden_on_admin_routes(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caller without admin tier receives 403 on /api/admin/*."""
        monkeypatch.setenv("STAGE", "local")
        user_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_user = UserTable(
            id=user_id,
            cognito_sub=str(user_id),
            email="regular@example.com",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        with (
            patch(
                "services.admin.dependencies.get_current_user",
                new_callable=AsyncMock,
                return_value=fake_user,
            ),
            patch(
                "vistarae_core.middleware.rate_limit.get_cached_tier",
                return_value=(UserTier.LOW, False),
            ),
        ):
            resp = client.get(
                "/api/admin/metrics",
                headers={"X-Mock-User-Id": str(user_id)},
            )
            assert resp.status_code == 403
            assert resp.headers["content-type"] == "application/problem+json"

    def test_admin_disable_blocks_target_tenant(
        self, client: TestClient, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Admin disables target tenant; subsequent target requests receive 403."""
        monkeypatch.setenv("STAGE", "local")
        admin_id = uuid.uuid4()
        target_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_admin = UserTable(
            id=admin_id,
            cognito_sub=str(admin_id),
            email="admin@example.com",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        fake_admin._tier = UserTier.ADMIN

        # 1. Admin disables target
        admin_app.dependency_overrides[require_admin] = lambda: fake_admin
        try:
            with patch(
                "vistarae_core.middleware.rate_limit.get_cached_tier",
                return_value=(UserTier.ADMIN, False),
            ):
                disable_resp = client.post(
                    f"/api/admin/users/{target_id}/disable",
                    headers={"X-Mock-User-Id": str(admin_id)},
                )
                assert disable_resp.status_code == 204
        finally:
            admin_app.dependency_overrides.pop(require_admin, None)

        # 2. Target user now blocked in rate-limiting middleware / auth dependency
        set_cached_tier(target_id, UserTier.LOW, is_disabled=True)
        resp = client.get(
            "/api/users/me",
            headers={"X-Mock-User-Id": str(target_id)},
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()
