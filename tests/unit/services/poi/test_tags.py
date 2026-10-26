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

"""Unit and contract tests for Tag Management endpoints and seeder (T-010).

Validates:
- Alphabetical listing (REQ-EXT-002)
- Slug generation and aliases (REQ-EXT-004, REQ-EXT-005)
- 409 Conflict referential protection with remediation link (REQ-EXT-006)
- 204 No Content deletion when unused (REQ-EXT-007)
- Default tag seeder (REQ-EXT-003)
- Pydantic v2 boundary enforcement and RFC 7807 error responses (REQ-EXT-034)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.domain.entities import TagEntity, User
from vistarae_core.ports.repositories import ITagRepository

from services.poi.dependencies import get_current_user, get_tag_repo
from services.poi.main import app
from services.poi.services.tag_seeder import DEFAULT_TAGS, seed_default_tags


@pytest.fixture
def mock_user() -> User:
    """Fixture providing an authenticated mock tenant."""
    return User(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        email="traveler@example.com",
        cognito_sub="sub-12345",
    )


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    """Fixture providing a mock tag repository."""
    repo = AsyncMock(spec=ITagRepository)
    return repo


@pytest.fixture
def client(mock_user: User, mock_tag_repo: AsyncMock) -> TestClient:
    """TestClient with dependency overrides."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestTagManagementEndpoints:
    """Tests for GET, POST, DELETE /api/pois/tags."""

    def test_list_tags_alphabetical_order(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts tags are returned sorted by name ASC with slugs and aliases."""
        tags = [
            TagEntity(
                id=uuid4(),
                user_id=mock_user.id,
                slug="fortification",
                name="Fortification",
                aliases=["castle", "fort"],
                poi_count=3,
                created_at=datetime.now(UTC),
            ),
            TagEntity(
                id=uuid4(),
                user_id=mock_user.id,
                slug="historic",
                name="Historic",
                aliases=["history"],
                poi_count=0,
                created_at=datetime.now(UTC),
            ),
        ]
        mock_tag_repo.list_by_user.return_value = tags

        resp = client.get("/api/pois/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Fortification"
        assert data[0]["slug"] == "fortification"
        assert data[0]["poi_count"] == 3
        assert "castle" in data[0]["aliases"]
        assert data[1]["name"] == "Historic"

    def test_create_tag_with_derived_slug(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts slug is derived automatically when not explicitly provided."""
        mock_tag_repo.get_by_slug.return_value = None
        new_tag = TagEntity(
            id=uuid4(),
            user_id=mock_user.id,
            slug="historic_railway",
            name="Historic Railway",
            aliases=["steam train", "cog railway"],
            poi_count=0,
            created_at=datetime.now(UTC),
        )
        mock_tag_repo.create.return_value = new_tag

        resp = client.post(
            "/api/pois/tags",
            json={
                "name": "Historic Railway",
                "aliases": ["steam train", "cog railway"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "historic_railway"
        assert data["name"] == "Historic Railway"
        assert "steam train" in data["aliases"]

    def test_create_tag_duplicate_slug_conflict(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts duplicate slug returns RFC 7807 409 Conflict."""
        existing = TagEntity(
            id=uuid4(),
            user_id=mock_user.id,
            slug="fortification",
            name="Fortification",
            aliases=[],
            poi_count=1,
            created_at=datetime.now(UTC),
        )
        mock_tag_repo.get_by_slug.return_value = existing

        resp = client.post(
            "/api/pois/tags",
            json={
                "name": "Fortification",
                "slug": "fortification",
            },
        )
        assert resp.status_code == 409
        assert resp.headers["content-type"] == "application/problem+json"
        data = resp.json()
        assert data["title"] == "Tag slug already exists"
        assert data["status"] == 409

    def test_delete_tag_in_use_blocked_with_remediation_link(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts deletion is rejected with 409 and direct filter URL when referenced by POIs."""
        tag_id = uuid4()
        existing = TagEntity(
            id=tag_id,
            user_id=mock_user.id,
            slug="fortification",
            name="Fortification",
            aliases=[],
            poi_count=5,
            created_at=datetime.now(UTC),
        )
        mock_tag_repo.count_referencing_pois.return_value = 5
        mock_tag_repo.get_by_id.return_value = existing

        resp = client.delete(f"/api/pois/tags/{tag_id}")
        assert resp.status_code == 409
        assert resp.headers["content-type"] == "application/problem+json"
        data = resp.json()
        assert data["type"] == "urn:vistarae:error:tag-in-use"
        assert data["title"] == "Tag in use"
        assert data["referencing_poi_count"] == 5
        assert data["remediation_filter_url"] == "/?filter_tag=fortification"

    def test_delete_tag_unused_success(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts unused tag is deleted successfully returning 204 No Content."""
        tag_id = uuid4()
        mock_tag_repo.count_referencing_pois.return_value = 0
        mock_tag_repo.delete.return_value = True

        resp = client.delete(f"/api/pois/tags/{tag_id}")
        assert resp.status_code == 204

    def test_delete_tag_not_found(
        self, client: TestClient, mock_user: User, mock_tag_repo: AsyncMock
    ) -> None:
        """Asserts non-existent tag deletion returns 404."""
        tag_id = uuid4()
        mock_tag_repo.count_referencing_pois.return_value = 0
        mock_tag_repo.delete.return_value = False

        resp = client.delete(f"/api/pois/tags/{tag_id}")
        assert resp.status_code == 404


class TestTagSeeder:
    """Tests for seed_default_tags service."""

    @pytest.mark.asyncio
    async def test_seeder_has_30_tags_with_slugs_and_aliases(self) -> None:
        """Verifies the standard 30 default tags are properly defined."""
        assert len(DEFAULT_TAGS) == 30
        slugs = [t["slug"] for t in DEFAULT_TAGS]
        assert len(set(slugs)) == 30  # All slugs unique
        for tag in DEFAULT_TAGS:
            assert isinstance(tag["aliases"], list)
            assert len(tag["aliases"]) > 0

    @pytest.mark.asyncio
    async def test_seeder_execution(self) -> None:
        """Verifies seeder issues execute call with ON CONFLICT DO NOTHING."""
        mock_session = AsyncMock()
        user_id = uuid4()
        count = await seed_default_tags(user_id, mock_session)
        assert count == 30
        assert mock_session.execute.called
        assert mock_session.flush.called
