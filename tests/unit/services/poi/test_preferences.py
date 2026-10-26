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

"""Unit and contract tests for Scraping Sources preferences endpoints (T-011).

Validates:
- GET /api/user/preferences/scraping-sources (REQ-EXT-019)
- PUT /api/user/preferences/scraping-sources (REQ-EXT-019)
- Pydantic v2 boundary validation & RFC 7807 error formatting (REQ-EXT-034)
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import IScrapingPreferencesRepository

from services.poi.dependencies import get_current_user
from services.poi.main import app
from services.poi.routes.preferences import get_scraping_preferences_repo


@pytest.fixture
def mock_user() -> User:
    """Fixture providing an authenticated mock tenant."""
    return User(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        email="traveler@example.com",
        cognito_sub="sub-12345",
    )


@pytest.fixture
def mock_scraping_repo() -> AsyncMock:
    """Fixture providing a mock scraping preferences repository."""
    repo = AsyncMock(spec=IScrapingPreferencesRepository)
    return repo


@pytest.fixture
def client(mock_user: User, mock_scraping_repo: AsyncMock) -> TestClient:
    """TestClient with dependency overrides."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_scraping_preferences_repo] = lambda: mock_scraping_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestScrapingPreferencesEndpoints:
    """Tests for GET and PUT /api/user/preferences/scraping-sources."""

    def test_get_scraping_sources(self, client: TestClient, mock_scraping_repo: AsyncMock) -> None:
        """Asserts authorized scraping sources are returned."""
        domains = ["wikipedia.org", "tripadvisor.com", "atlasobscura.com"]
        mock_scraping_repo.get_scraping_domains.return_value = domains

        resp = client.get("/api/user/preferences/scraping-sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid_scraping_domains"] == domains

    def test_update_scraping_sources(
        self, client: TestClient, mock_scraping_repo: AsyncMock
    ) -> None:
        """Asserts valid scraping domains can be updated."""
        new_domains = ["wikipedia.org", "roadtrippers.com"]
        mock_scraping_repo.update_scraping_domains.return_value = new_domains

        resp = client.put(
            "/api/user/preferences/scraping-sources",
            json={"valid_scraping_domains": new_domains},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid_scraping_domains"] == new_domains

    def test_update_scraping_sources_empty_list_rejected(
        self, client: TestClient, mock_scraping_repo: AsyncMock
    ) -> None:
        """Asserts empty domain list fails Pydantic v2 min_length=1 validation."""
        resp = client.put(
            "/api/user/preferences/scraping-sources",
            json={"valid_scraping_domains": []},
        )
        assert resp.status_code == 422
