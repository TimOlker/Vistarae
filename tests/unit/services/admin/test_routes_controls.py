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

"""Unit tests for Admin platform control routes (T-042).

Tests:
- PUT /api/admin/quotas/defaults
- POST /api/admin/trace-injection/toggle
- POST /api/admin/users/{user_id}/messages
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
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
def client(admin_user: User) -> TestClient:
    app.dependency_overrides[require_admin] = lambda: admin_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestAdminControlsRoutes:
    """Tests for platform control endpoints."""

    def test_update_quota_defaults_success(self, client: TestClient) -> None:
        """Asserts PUT /api/admin/quotas/defaults updates default values."""
        resp = client.put(
            "/api/admin/quotas/defaults",
            json={"default_token_quota": 80000, "default_tier": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_token_quota"] == 80000
        assert data["default_tier"] == "high"

    def test_toggle_trace_injection_success(self, client: TestClient) -> None:
        """Asserts POST /api/admin/trace-injection/toggle flips boolean."""
        resp1 = client.post("/api/admin/trace-injection/toggle")
        assert resp1.status_code == 200
        state1 = resp1.json()["trace_injection_enabled"]

        resp2 = client.post("/api/admin/trace-injection/toggle")
        assert resp2.status_code == 200
        state2 = resp2.json()["trace_injection_enabled"]

        assert state1 != state2

    def test_send_admin_message_accepted(self, client: TestClient) -> None:
        """Asserts POST /api/admin/users/{id}/messages returns 202 Accepted."""
        target_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/admin/users/{target_id}/messages",
            json={"title": "Policy Update", "message": "Terms have changed."},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["user_id"] == target_id
