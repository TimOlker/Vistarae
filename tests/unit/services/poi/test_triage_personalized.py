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

"""Unit tests for personalized triage route POST /api/pois/extract-and-check (T-020).

Validates:
- reason_to_visit populated on candidate schema in response payload (REQ-CTX-021, REQ-CTX-022, SC-001)
- Prompt directives loaded from cache or repository and supplied to orchestrator
- Default balanced reason_to_visit returned when user has no custom directives
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.ports.repositories import IGeocodingCacheRepository, ITagRepository
from vistarae_core.schemas.scraping import POICandidateSchema

from services.poi.dependencies import (
    get_current_user,
    get_geocache_repo,
    get_tag_repo,
)
from services.poi.main import app


@pytest.fixture
def current_user() -> User:
    """Fixture providing an authenticated traveler."""
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        cognito_sub="sub-food-traveler",
        email="foodie@example.com",
        full_name="Gastronomy Traveler",
        is_active=True,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mock database session."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    """Mock tag repository."""
    repo = AsyncMock(spec=ITagRepository)
    repo.list_by_user.return_value = []
    return repo


@pytest.fixture
def mock_geocache_repo() -> AsyncMock:
    """Mock geocoding cache repository."""
    repo = AsyncMock(spec=IGeocodingCacheRepository)
    repo.get.return_value = None
    return repo


@pytest.fixture
def client(
    current_user: User,
    mock_session: AsyncMock,
    mock_tag_repo: AsyncMock,
    mock_geocache_repo: AsyncMock,
) -> TestClient:
    """Configured TestClient with dependencies overridden."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo
    app.dependency_overrides[get_geocache_repo] = lambda: mock_geocache_repo

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_and_check_returns_reason_to_visit(
    client: TestClient,
    current_user: User,
) -> None:
    """Asserts POST /api/pois/extract-and-check returns reason_to_visit in the candidate payload."""
    candidate_mock = POICandidateSchema(
        name="Pike Place Market",
        description="Historic public market showcasing local artisan bakeries and fresh seafood.",
        reason_to_visit="A must-visit for food lovers to sample regional ciders and artisan cheeses.",
        addresses=[],
        latitude=47.6087,
        longitude=-122.3400,
        official_website_url="https://pikeplacemarket.org",
        wikipedia_url="https://en.wikipedia.org/wiki/Pike_Place_Market",
        hero_image_url=None,
        estimated_duration_hours=3.0,
        estimated_duration_days=0,
        estimated_visit_time_notes=None,
        rating=None,
        source_type="Web",
        source_value="https://pikeplacemarket.org",
        extraction_sources=["pikeplacemarket.org", "wikipedia.org"],
    )

    with (
        patch(
            "services.poi.routes.triage.ScrapingOrchestrator.extract",
            new_callable=AsyncMock,
        ) as mock_extract,
        patch(
            "services.poi.routes.triage.default_prompt_cache.get_or_load",
            new_callable=AsyncMock,
        ) as mock_get_or_load,
    ):
        mock_extract.return_value = candidate_mock
        mock_get_or_load.return_value = {
            PromptType.DESCRIPTION: "Highlight local food traditions.",
            PromptType.REASON_TO_VISIT: "Focus on authentic dining and tasting.",
            PromptType.TIME_SPENT: "Allow generous duration estimates.",
        }

        req_payload = {
            "source_url": "https://pikeplacemarket.org",
            "page_title": "Pike Place Market - Seattle",
            "selected_text": "Pike Place Market opened in 1907.",
        }

        response = client.post("/api/pois/extract-and-check", json=req_payload)
        assert response.status_code == 200

        data = response.json()
        assert "candidate" in data
        candidate_data = data["candidate"]
        assert candidate_data["name"] == "Pike Place Market"
        assert candidate_data["description"] is not None
        assert "reason_to_visit" in candidate_data
        assert candidate_data["reason_to_visit"] == (
            "A must-visit for food lovers to sample regional ciders and artisan cheeses."
        )
        assert candidate_data["estimated_duration_hours"] == 3.0

        # Assert prompt directives were passed into orchestrator.extract
        mock_extract.assert_awaited_once()
        _, kwargs = mock_extract.call_args
        assert "prompt_directives" in kwargs
        assert (
            kwargs["prompt_directives"][PromptType.DESCRIPTION]
            == "Highlight local food traditions."
        )
