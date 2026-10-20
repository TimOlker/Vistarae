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

"""Unit tests for UserFunction profile and GDPR deletion routes (T-022).

Tests:
- GET /api/users/me (profile, preferences, metrics, quotas combination)
- PATCH /api/users/me (updating full_name)
- DELETE /api/users/me (GDPR cascade deletion calling Cognito and DB)
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
    UserPreferencesTable,
    UserQuotasTable,
)
from vistarae_core.domain.entities import User

from services.user.dependencies import get_current_user
from services.user.main import app


@pytest.fixture
def test_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-me-123",
        email="traveler@example.com",
        full_name="Original Name",
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


class TestMeRoutes:
    """Tests for /api/users/me endpoints."""

    def test_get_me_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts GET /api/users/me returns full UserProfileResponse."""
        now = datetime.now(UTC)
        fake_prefs = UserPreferencesTable(
            user_id=test_user.id,
            theme="dark",
            email_notifications_enabled=True,
            push_notifications_enabled=True,
            marketing_emails_enabled=False,
            clustering_enabled=True,
            clustering_radius_meters=60,
            default_map_layer="satellite",
            geoproximity_scope_km=20.0,
            pin_color_presets={"fav": "#ff0000"},
            pacing="fast_paced",
            meal_intervals_hours=4.5,
            lunch_packing_enabled=False,
            transit_speed_mode="driving",
            daily_activity_hour_cap=10.0,
            preferred_currency="EUR",
            created_at=now,
            updated_at=now,
        )
        fake_metrics = UserMetricsTable(
            user_id=test_user.id,
            poi_count=15,
            total_tokens_consumed=3200,
            updated_at=now,
        )
        fake_quota = UserQuotasTable(
            user_id=test_user.id,
            monthly_token_quota=100000,
            current_token_usage=15000,
            tier="high",
            request_count=20,
            window_start_at=now,
            is_disabled=False,
            updated_at=now,
        )

        mock_session.scalar.side_effect = [fake_prefs, fake_metrics, fake_quota]

        resp = client.get("/api/users/me")
        assert resp.status_code == 200
        data = resp.json()

        assert data["user"]["id"] == str(test_user.id)
        assert data["user"]["email"] == "traveler@example.com"
        assert data["preferences"]["ui"]["theme"] == "dark"
        assert data["preferences"]["poi"]["clustering_radius_meters"] == 60
        assert data["preferences"]["planner"]["pacing"] == "fast_paced"
        assert data["metrics"]["poi_count"] == 15
        assert data["quotas"]["tier"] == "high"

    def test_patch_me_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts PATCH /api/users/me updates full_name and returns UserResponse."""
        resp = client.patch("/api/users/me", json={"full_name": "Updated Name"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == str(test_user.id)
        assert data["full_name"] == "Updated Name"
        mock_session.execute.assert_called_once()

    def test_patch_me_extra_forbidden(self, client: TestClient) -> None:
        """Asserts extra fields in body are rejected with 422 ProblemDetails."""
        resp = client.patch(
            "/api/users/me",
            json={"full_name": "Valid", "unrecognized_extra": "forbidden"},
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"

    def test_delete_me_gdpr_success(
        self, client: TestClient, test_user: User, mock_session: AsyncMock
    ) -> None:
        """Asserts DELETE /api/users/me triggers Cognito deletion and DB delete."""
        with patch(
            "services.user.routes.me._cognito.delete_user", new_callable=AsyncMock
        ) as mock_cog:
            resp = client.delete("/api/users/me")
            assert resp.status_code == 204
            mock_cog.assert_called_once_with(test_user.cognito_sub)
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_lifespan(self) -> None:
        """Asserts lifespan initializes and disposes engine."""
        from services.user.main import app as u_app
        from services.user.main import lifespan as u_lifespan

        mock_engine = AsyncMock()
        with (
            patch("services.user.main.init_engine", new_callable=AsyncMock) as mock_init,
            patch("services.user.main.get_engine", return_value=mock_engine),
        ):
            async with u_lifespan(u_app):
                mock_init.assert_called_once()
                mock_engine.dispose.assert_not_called()
            mock_engine.dispose.assert_called_once()
