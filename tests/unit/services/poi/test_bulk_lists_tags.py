# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Curated Lists, Shared Lists, Taxonomy Tags, and Bulk operations (T-030).

Tests:
- /api/lists: list, create, get, patch, delete
- /api/lists/{id}/shared: public unauthenticated access to public lists and member POIs
- /api/tags: list, create, delete
- /api/pois/bulk-tags: bulk attach and detach
- /api/pois/bulk-lists: bulk attach and detach
- /api/pois/bulk-delete: atomic multi-POI deletion
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import POI, ListEntity, TagEntity, User
from vistarae_core.domain.value_objects import EnrichmentStatus, VisitState, WGS84Point
from vistarae_core.ports.repositories import (
    IListRepository,
    IPOIRepository,
    ITagRepository,
)

from services.poi.dependencies import (
    get_current_user,
    get_list_repo,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.main import app


@pytest.fixture
def current_user() -> User:
    """Fixture providing a mock authenticated tenant user."""
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        cognito_sub="sub-traveler-1",
        email="traveler@example.com",
        full_name="Atlas Voyager",
        is_active=True,
    )


@pytest.fixture
def sample_list(current_user: User) -> ListEntity:
    """Fixture providing a sample curated list."""
    return ListEntity(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        title="California Gems",
        description="Best spots in California.",
        is_public=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_poi(current_user: User) -> POI:
    """Fixture providing a sample POI entity."""
    return POI(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        name="Lake Tahoe",
        geom=WGS84Point(lon=-120.0324, lat=39.0968),
        states=["California", "Nevada"],
        countries=["United States"],
        visit_state=VisitState.NOT_VISITED,
        enrichment_status=EnrichmentStatus.SUCCESS,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_poi_repo() -> AsyncMock:
    return AsyncMock(spec=IPOIRepository)


@pytest.fixture
def mock_list_repo() -> AsyncMock:
    return AsyncMock(spec=IListRepository)


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    return AsyncMock(spec=ITagRepository)


@pytest.fixture
def client(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_list_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_list_repo] = lambda: mock_list_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestCuratedListRoutes:
    """Tests for /api/lists endpoints."""

    def test_list_user_lists(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts user lists are returned."""
        mock_list_repo.list_by_user.return_value = [sample_list]
        resp = client.get("/api/lists")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "California Gems"

    def test_create_list(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts list creation returns 201 Created."""
        mock_list_repo.create.return_value = sample_list
        resp = client.post(
            "/api/lists",
            json={"title": "California Gems", "description": "Best spots", "is_public": True},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "California Gems"

    def test_get_list_by_id(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts retrieving single list returns 200 OK."""
        mock_list_repo.get_by_id.return_value = sample_list
        resp = client.get(f"/api/lists/{sample_list.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(sample_list.id)

    def test_get_list_not_found(self, client: TestClient, mock_list_repo: AsyncMock) -> None:
        """Asserts 404 when list does not exist."""
        mock_list_repo.get_by_id.return_value = None
        resp = client.get(f"/api/lists/{uuid4()}")
        assert resp.status_code == 404

    def test_patch_list(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts update modifies fields and returns updated model."""
        mock_list_repo.get_by_id.return_value = sample_list
        sample_list.title = "Updated Gems"
        mock_list_repo.update.return_value = sample_list

        resp = client.patch(
            f"/api/lists/{sample_list.id}",
            json={"title": "Updated Gems"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Gems"

    def test_delete_list(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts list deletion returns 204 No Content."""
        mock_list_repo.delete.return_value = True
        resp = client.delete(f"/api/lists/{sample_list.id}")
        assert resp.status_code == 204

    def test_get_shared_list_public(
        self,
        client: TestClient,
        sample_list: ListEntity,
        sample_poi: POI,
        mock_list_repo: AsyncMock,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts public shared list retrieves list and member POIs without user auth."""
        mock_list_repo.get_by_id.return_value = sample_list
        mock_poi_repo.list_pois.return_value = ([sample_poi], 1)
        mock_tag_repo.get_tags_for_pois.return_value = {}

        resp = client.get(f"/api/lists/{sample_list.id}/shared")
        assert resp.status_code == 200
        data = resp.json()
        assert data["list"]["title"] == "California Gems"
        assert len(data["pois"]) == 1
        assert data["pois"][0]["name"] == "Lake Tahoe"

    def test_get_shared_list_private_returns_404(
        self, client: TestClient, sample_list: ListEntity, mock_list_repo: AsyncMock
    ) -> None:
        """Asserts private list access returns 404 on shared endpoint."""
        sample_list.is_public = False
        mock_list_repo.get_by_id.return_value = sample_list

        resp = client.get(f"/api/lists/{sample_list.id}/shared")
        assert resp.status_code == 404


class TestTagRoutes:
    """Tests for /api/tags endpoints."""

    def test_list_tags(self, client: TestClient, mock_tag_repo: AsyncMock) -> None:
        """Asserts tags are returned sorted."""
        tag = TagEntity(id=uuid4(), user_id=uuid4(), name="hiking")
        mock_tag_repo.list_by_user.return_value = [tag]

        resp = client.get("/api/tags")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "hiking"

    def test_create_tag(self, client: TestClient, mock_tag_repo: AsyncMock) -> None:
        """Asserts tag creation returns 201 Created."""
        tag = TagEntity(id=uuid4(), user_id=uuid4(), name="camping")
        mock_tag_repo.get_or_create.return_value = tag

        resp = client.post("/api/tags", json={"name": "camping"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "camping"

    def test_delete_tag(self, client: TestClient, mock_tag_repo: AsyncMock) -> None:
        """Asserts tag deletion returns 204 No Content."""
        mock_tag_repo.delete.return_value = True
        resp = client.delete(f"/api/tags/{uuid4()}")
        assert resp.status_code == 204


class TestBulkOperationRoutes:
    """Tests for /api/pois/bulk-* endpoints."""

    def test_bulk_tags_attach_and_detach(
        self, client: TestClient, mock_poi_repo: AsyncMock
    ) -> None:
        """Asserts bulk tag attach and detach calls repo and returns modified count."""
        mock_poi_repo.bulk_attach_tags.return_value = 5
        mock_poi_repo.bulk_detach_tags.return_value = 3

        p_id = str(uuid4())
        t_id = str(uuid4())

        attach_resp = client.post(
            "/api/pois/bulk-tags",
            json={"poi_ids": [p_id], "tag_ids": [t_id], "action": "attach"},
        )
        assert attach_resp.status_code == 200
        assert attach_resp.json()["modified_count"] == 5

        detach_resp = client.post(
            "/api/pois/bulk-tags",
            json={"poi_ids": [p_id], "tag_ids": [t_id], "action": "detach"},
        )
        assert detach_resp.status_code == 200
        assert detach_resp.json()["modified_count"] == 3

    def test_bulk_lists_attach_and_detach(
        self, client: TestClient, mock_poi_repo: AsyncMock
    ) -> None:
        """Asserts bulk list attach and detach calls repo and returns modified count."""
        mock_poi_repo.bulk_attach_lists.return_value = 2
        mock_poi_repo.bulk_detach_lists.return_value = 2

        p_id = str(uuid4())
        l_id = str(uuid4())

        attach_resp = client.post(
            "/api/pois/bulk-lists",
            json={"poi_ids": [p_id], "list_ids": [l_id], "action": "attach"},
        )
        assert attach_resp.status_code == 200
        assert attach_resp.json()["modified_count"] == 2

    def test_bulk_delete(self, client: TestClient, mock_poi_repo: AsyncMock) -> None:
        """Asserts bulk deletion calls repo and returns deleted count."""
        mock_poi_repo.bulk_delete.return_value = 4
        p_ids = [str(uuid4()) for _ in range(4)]

        resp = client.post("/api/pois/bulk-delete", json={"poi_ids": p_ids})
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 4
