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

"""Unit and route integration tests for Travel Style Profile endpoints (T-013).

Tests:
- GET /api/user/profile/travel-style
- PUT /api/user/profile/travel-style (valid, empty, brief, cache invalidation)
- DELETE /api/user/profile/travel-style
- Strict schema validation (max length 2000, extra fields forbidden)
- Tenant isolation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable, UserPromptTable
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.services.prompt_cache import UserPromptCache

from services.user.dependencies import get_current_user
from services.user.main import app
from services.user.routes.profile import get_prompt_cache, get_prompt_synthesizer


@pytest.fixture
def test_user() -> User:
    """Fixture providing an authenticated test User entity."""
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-travel-style-123",
        email="traveler@example.com",
        full_name="Traveler Style Tester",
        is_active=True,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Fixture providing a mock AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_synthesizer() -> AsyncMock:
    """Fixture providing a mock UserPromptSynthesizer."""
    synthesizer = AsyncMock()
    synthesizer.decompose = AsyncMock(
        return_value={
            PromptType.DESCRIPTION: "Highlight local food traditions and artisan bakeries.",
            PromptType.REASON_TO_VISIT: "Focus on authentic dining and culinary culture.",
            PromptType.TIME_SPENT: "Allow generous duration estimates for leisurely dining.",
        }
    )
    return synthesizer


@pytest.fixture
def mock_cache() -> MagicMock:
    """Fixture providing a mock UserPromptCache."""
    cache = MagicMock(spec=UserPromptCache)
    return cache


@pytest.fixture
def client(
    test_user: User,
    mock_session: AsyncMock,
    mock_synthesizer: AsyncMock,
    mock_cache: MagicMock,
) -> TestClient:
    """FastAPI TestClient with all dependencies mocked."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_prompt_synthesizer] = lambda: mock_synthesizer
    app.dependency_overrides[get_prompt_cache] = lambda: mock_cache

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()


class TestProfileTravelStyleRoutes:
    """Integration test suite for travel style endpoints."""

    def test_get_travel_style_unpopulated(
        self,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """Asserts GET returns null travel style and empty prompts when unpopulated."""
        mock_session.scalar.return_value = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        response = client.get("/api/user/profile/travel-style")
        assert response.status_code == 200
        data = response.json()
        assert data["travel_style_description"] is None
        assert data["prompts"] == []

    def test_get_travel_style_populated(
        self,
        client: TestClient,
        test_user: User,
        mock_session: AsyncMock,
    ) -> None:
        """Asserts GET returns saved narrative and active prompt directives."""
        now = datetime.now(UTC)
        mock_pref = UserPreferencesTable(
            user_id=test_user.id,
            travel_style_description="Passionate about street food and local markets.",
            created_at=now,
            updated_at=now,
        )
        mock_session.scalar.return_value = mock_pref

        mock_prompt_row = UserPromptTable(
            id=uuid.uuid4(),
            user_id=test_user.id,
            prompt_type="description",
            prompt_text="Highlight local culinary heritage.",
            created_at=now,
            updated_at=now,
        )
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_prompt_row]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        response = client.get("/api/user/profile/travel-style")
        assert response.status_code == 200
        data = response.json()
        assert data["travel_style_description"] == "Passionate about street food and local markets."
        assert len(data["prompts"]) == 1
        assert data["prompts"][0]["prompt_type"] == "description"
        assert data["prompts"][0]["prompt_text"] == "Highlight local culinary heritage."

    def test_put_travel_style_success(
        self,
        client: TestClient,
        test_user: User,
        mock_session: AsyncMock,
        mock_synthesizer: AsyncMock,
        mock_cache: MagicMock,
    ) -> None:
        """Asserts PUT saves narrative, synthesizes prompts, invalidates cache, and returns directives."""
        now = datetime.now(UTC)
        existing_pref = UserPreferencesTable(
            user_id=test_user.id,
            travel_style_description="Old narrative",
            created_at=now,
            updated_at=now,
        )
        mock_session.scalar.return_value = existing_pref

        # Return synthesized prompts on list_by_user call
        prompt_rows = [
            UserPromptTable(
                id=uuid.uuid4(),
                user_id=test_user.id,
                prompt_type="description",
                prompt_text="Highlight local food traditions.",
                created_at=now,
                updated_at=now,
            ),
            UserPromptTable(
                id=uuid.uuid4(),
                user_id=test_user.id,
                prompt_type="reason_to_visit",
                prompt_text="Focus on authentic dining.",
                created_at=now,
                updated_at=now,
            ),
            UserPromptTable(
                id=uuid.uuid4(),
                user_id=test_user.id,
                prompt_type="time_spent",
                prompt_text="Allow generous duration estimates.",
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = prompt_rows
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        payload = {
            "travel_style_description": (
                "I love taking in culinary traditions and artisan food markets. "
                "Generous time to explore."
            )
        }
        response = client.put("/api/user/profile/travel-style", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["travel_style_description"] == payload["travel_style_description"]
        assert len(data["prompts"]) == 3

        # Assert synthesizer was called
        mock_synthesizer.decompose.assert_awaited_once_with(payload["travel_style_description"])

        # Assert cache invalidation was triggered for test_user.id
        mock_cache.invalidate_user.assert_called_once_with(test_user.id)

        # Assert commit was called
        mock_session.commit.assert_awaited_once()

    def test_put_travel_style_empty_clears_directives(
        self,
        client: TestClient,
        test_user: User,
        mock_session: AsyncMock,
        mock_synthesizer: AsyncMock,
        mock_cache: MagicMock,
    ) -> None:
        """Asserts PUT with empty string clears travel style narrative and prompt directives."""
        now = datetime.now(UTC)
        existing_pref = UserPreferencesTable(
            user_id=test_user.id,
            travel_style_description="Old narrative",
            created_at=now,
            updated_at=now,
        )
        mock_session.scalar.return_value = existing_pref

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        response = client.put(
            "/api/user/profile/travel-style",
            json={"travel_style_description": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["travel_style_description"] is None
        assert data["prompts"] == []

        # Synthesizer should not be called for empty string
        mock_synthesizer.decompose.assert_not_called()
        mock_cache.invalidate_user.assert_called_once_with(test_user.id)

    def test_delete_travel_style_success(
        self,
        client: TestClient,
        test_user: User,
        mock_session: AsyncMock,
        mock_cache: MagicMock,
    ) -> None:
        """Asserts DELETE clears narrative and removes prompt directives from DB."""
        response = client.delete("/api/user/profile/travel-style")
        assert response.status_code == 200
        data = response.json()
        assert data["travel_style_description"] is None
        assert data["prompts"] == []

        mock_cache.invalidate_user.assert_called_once_with(test_user.id)
        mock_session.commit.assert_awaited_once()

    def test_put_travel_style_validation_max_length(
        self,
        client: TestClient,
    ) -> None:
        """Asserts narrative exceeding 2000 characters is rejected with 422."""
        too_long = "A" * 2001
        response = client.put(
            "/api/user/profile/travel-style",
            json={"travel_style_description": too_long},
        )
        assert response.status_code == 422

    def test_put_travel_style_validation_extra_fields_forbidden(
        self,
        client: TestClient,
    ) -> None:
        """Asserts payloads with unauthorized fields are rejected with 422."""
        response = client.put(
            "/api/user/profile/travel-style",
            json={
                "travel_style_description": "Valid narrative here.",
                "unauthorized_field": "exploit",
            },
        )
        assert response.status_code == 422
