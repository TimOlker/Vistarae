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

"""Unit tests for UserFunction sub-domain preferences routes (T-024).

Tests:
- GET /api/users/me/preferences
- PATCH /api/users/me/preferences/ui
- PATCH /api/users/me/preferences/poi
- PATCH /api/users/me/preferences/planner
- Strict validation enforcement (bounds, enums, extra fields forbidden)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.domain.entities import User

from services.user.dependencies import get_current_user
from services.user.main import app


@pytest.fixture
def test_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-pref-123",
        email="traveler@example.com",
        full_name="Pref Traveler",
        is_active=True,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(test_user: User, mock_session: AsyncMock) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db_session] = lambda: mock_session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_prefs_row(user_id: uuid.UUID) -> UserPreferencesTable:
    now = datetime.now(UTC)
    return UserPreferencesTable(
        user_id=user_id,
        theme="system",
        email_notifications_enabled=True,
        push_notifications_enabled=True,
        marketing_emails_enabled=False,
        clustering_enabled=True,
        clustering_radius_meters=50,
        default_map_layer="standard",
        geoproximity_scope_km=25.0,
        pin_color_presets={"favorite": "#E11D48"},
        pacing="moderate",
        meal_intervals_hours=4.0,
        lunch_packing_enabled=False,
        transit_speed_mode="walking",
        daily_activity_hour_cap=8.0,
        preferred_currency="USD",
        created_at=now,
        updated_at=now,
    )


class TestPreferencesRoutes:
    """Tests for preferences endpoints."""

    def test_get_preferences_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts GET /api/users/me/preferences returns UserPreferencesResponse."""
        fake_prefs = _make_prefs_row(test_user.id)
        mock_session.scalar.return_value = fake_prefs

        resp = client.get("/api/users/me/preferences")
        assert resp.status_code == 200
        data = resp.json()

        assert data["ui"]["theme"] == "system"
        assert data["poi"]["clustering_radius_meters"] == 50
        assert data["planner"]["pacing"] == "moderate"

    def test_patch_ui_preferences_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts PATCH /api/users/me/preferences/ui updates UI settings."""
        fake_prefs = _make_prefs_row(test_user.id)
        fake_prefs.theme = "dark"
        mock_session.scalar.return_value = fake_prefs

        resp = client.patch(
            "/api/users/me/preferences/ui",
            json={"theme": "dark", "marketing_emails_enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "dark"
        mock_session.execute.assert_called_once()

    def test_patch_poi_preferences_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts PATCH /api/users/me/preferences/poi updates POI settings."""
        fake_prefs = _make_prefs_row(test_user.id)
        fake_prefs.clustering_radius_meters = 150
        mock_session.scalar.return_value = fake_prefs

        resp = client.patch(
            "/api/users/me/preferences/poi",
            json={"clustering_radius_meters": 150, "default_map_layer": "satellite"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["clustering_radius_meters"] == 150

    def test_patch_planner_preferences_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts PATCH /api/users/me/preferences/planner updates Planner settings."""
        fake_prefs = _make_prefs_row(test_user.id)
        fake_prefs.pacing = "fast_paced"
        fake_prefs.preferred_currency = "JPY"
        mock_session.scalar.return_value = fake_prefs

        resp = client.patch(
            "/api/users/me/preferences/planner",
            json={"pacing": "fast_paced", "preferred_currency": "JPY"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pacing"] == "fast_paced"
        assert data["preferred_currency"] == "JPY"

    def test_patch_poi_validation_out_of_bounds(self, client: TestClient) -> None:
        """Asserts out-of-bounds clustering radius (< 10) returns 422 ProblemDetails."""
        resp = client.patch(
            "/api/users/me/preferences/poi",
            json={"clustering_radius_meters": 5},
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"

    def test_patch_planner_currency_length_validation(self, client: TestClient) -> None:
        """Asserts currency != 3 chars returns 422 ProblemDetails."""
        resp = client.patch(
            "/api/users/me/preferences/planner",
            json={"preferred_currency": "DOLLARS"},
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"
