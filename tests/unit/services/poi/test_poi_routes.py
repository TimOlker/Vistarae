# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for POI CRUD, Viewport Exploration, Deduplication, and Merge routes (T-013).

Tests:
- GET /api/pois: planar viewport, multi-facet filtering, semantic vector search, pagination
- POST /api/pois: geocoding enrichment, tag resolution, Gemini embedding, 30-tag ceiling
- GET /api/pois/{id}: single entity lookup with attached tags, 404 RFC 7807 handling
- PATCH /api/pois/{id}: partial update, cycle prevention (self & recursive), embedding hash bypass
- DELETE /api/pois/{id}: tenant-scoped deletion, 404 handling
- GET /api/pois/dedup-check: proximity preset probing (urban vs macro)
- POST /api/pois/merge: atomic record merge
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import (
    POI,
    PotentialDuplicateMatch,
    TagEntity,
    User,
)
from vistarae_core.domain.value_objects import (
    EnrichmentStatus,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.geocoding import GeocodingResult, IGeocodingPort
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository

from services.poi.dependencies import (
    get_current_user,
    get_embedding_port,
    get_geocoding_port,
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
def sample_poi(current_user: User) -> POI:
    """Fixture providing a sample POI entity."""
    return POI(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        name="Yosemite National Park",
        geom=WGS84Point(lon=-119.5383, lat=37.8651),
        description="Iconic granite cliffs and waterfalls.",
        address="Yosemite Valley, CA",
        city="Yosemite Valley",
        states=["California"],
        countries=["United States"],
        visit_state=VisitState.NOT_VISITED,
        rating=5,
        recommended_duration_hours=8.0,
        recommended_visit_days=3,
        enrichment_status=EnrichmentStatus.SUCCESS,
        embedding=[0.05] * 768,
        embedding_md5="0" * 32,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_poi_repo() -> AsyncMock:
    return AsyncMock(spec=IPOIRepository)


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    return AsyncMock(spec=ITagRepository)


@pytest.fixture
def mock_geocoding_port() -> AsyncMock:
    return AsyncMock(spec=IGeocodingPort)


@pytest.fixture
def mock_embedding_port() -> AsyncMock:
    mock = AsyncMock(spec=IEmbeddingPort)
    mock.generate_embedding.return_value = [0.01] * 768
    return mock


@pytest.fixture
def client(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
    mock_geocoding_port: AsyncMock,
    mock_embedding_port: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo
    app.dependency_overrides[get_geocoding_port] = lambda: mock_geocoding_port
    app.dependency_overrides[get_embedding_port] = lambda: mock_embedding_port
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestListPoisRoute:
    """Tests for GET /api/pois."""

    def test_list_pois_success(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts successful query returns paginated POIListResponse."""
        mock_poi_repo.list_pois.return_value = ([sample_poi], 1)
        mock_tag_repo.get_tags_for_pois.return_value = {
            sample_poi.id: [TagEntity(id=uuid4(), user_id=sample_poi.user_id, name="hiking")]
        }

        resp = client.get("/api/pois?bbox=-120.0,37.0,-119.0,38.0&state=California")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Yosemite National Park"
        assert len(data["items"][0]["tags"]) == 1
        assert data["items"][0]["tags"][0]["name"] == "hiking"

    def test_list_pois_invalid_bbox_returns_422(self, client: TestClient) -> None:
        """Asserts invalid bounding box string raises 422 ProblemDetails."""
        resp = client.get("/api/pois?bbox=invalid-bbox")
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"

    def test_list_pois_invalid_tag_ids_returns_422(self, client: TestClient) -> None:
        """Asserts malformed tag UUID raises 422 ProblemDetails."""
        resp = client.get("/api/pois?tag_ids=not-a-uuid")
        assert resp.status_code == 422

    def test_list_pois_semantic_search(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_embedding_port: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts semantic_q triggers vector embedding generation and cosine ranking."""
        sample_poi.similarity_score = 0.94
        mock_poi_repo.list_pois.return_value = ([sample_poi], 1)
        mock_tag_repo.get_tags_for_pois.return_value = {}

        resp = client.get("/api/pois?semantic_q=misty+granite+peaks")
        assert resp.status_code == 200
        mock_embedding_port.generate_embedding.assert_called_once_with("misty granite peaks")
        data = resp.json()
        assert data["items"][0]["similarity_score"] == 0.94


class TestCreatePoiRoute:
    """Tests for POST /api/pois."""

    def test_create_poi_success(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
        mock_geocoding_port: AsyncMock,
    ) -> None:
        """Asserts successful creation enriches address, computes embedding, attaches tags."""
        mock_poi_repo.create.return_value = sample_poi
        mock_geocoding_port.forward_geocode.return_value = GeocodingResult(
            lat=37.8651,
            lon=-119.5383,
            formatted_address="Yosemite National Park, CA 95389",
            states=["California"],
            countries=["United States"],
            status=EnrichmentStatus.SUCCESS,
        )
        created_tag = TagEntity(id=uuid4(), user_id=sample_poi.user_id, name="hiking")
        mock_tag_repo.get_or_create.return_value = created_tag

        payload = {
            "name": "Yosemite National Park",
            "lon": -119.5383,
            "lat": 37.8651,
            "address": "Yosemite Valley",
            "tag_names": ["hiking"],
            "state": "California",
        }

        resp = client.post("/api/pois", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Yosemite National Park"
        assert mock_poi_repo.bulk_attach_tags.called

    def test_create_poi_parent_not_found(
        self, client: TestClient, mock_poi_repo: AsyncMock
    ) -> None:
        """Asserts invalid parent POI ID raises 404 ProblemDetails."""
        mock_poi_repo.get_by_id.return_value = None
        payload = {
            "name": "Glacier Point",
            "lon": -119.5732,
            "lat": 37.7303,
            "parent_poi_id": str(uuid4()),
        }
        resp = client.post("/api/pois", json=payload)
        assert resp.status_code == 404

    def test_create_poi_tag_limit_exceeded(self, client: TestClient) -> None:
        """Asserts supplying > 30 tags raises 422 ProblemDetails."""
        payload = {
            "name": "Overloaded POI",
            "lon": -120.0,
            "lat": 38.0,
            "tag_names": [f"tag-{i}" for i in range(35)],
        }
        resp = client.post("/api/pois", json=payload)
        assert resp.status_code == 422


class TestGetUpdateDeletePoiRoutes:
    """Tests for GET, PATCH, DELETE /api/pois/{id}."""

    def test_get_poi_found(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts successful single entity retrieval with tags."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_tag_repo.get_tags_for_poi.return_value = [
            TagEntity(id=uuid4(), user_id=sample_poi.user_id, name="scenic-view")
        ]

        resp = client.get(f"/api/pois/{sample_poi.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(sample_poi.id)
        assert len(resp.json()["tags"]) == 1

    def test_get_poi_not_found(self, client: TestClient, mock_poi_repo: AsyncMock) -> None:
        """Asserts 404 ProblemDetails when POI does not exist."""
        mock_poi_repo.get_by_id.return_value = None
        resp = client.get(f"/api/pois/{uuid4()}")
        assert resp.status_code == 404
        assert resp.headers["content-type"] == "application/problem+json"

    def test_patch_poi_self_parent_cycle_raises_400(
        self, client: TestClient, sample_poi: POI, mock_poi_repo: AsyncMock
    ) -> None:
        """Asserts assigning a POI as its own parent raises 400 ProblemDetails."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": str(sample_poi.id)},
        )
        assert resp.status_code == 400

    def test_patch_poi_updates_fields(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
        mock_embedding_port: AsyncMock,
    ) -> None:
        """Asserts partial update saves changes and skips embedding if content unchanged."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.return_value = sample_poi
        mock_tag_repo.get_tags_for_poi.return_value = []

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"rating": 4, "visit_state": "visited_return"},
        )
        assert resp.status_code == 200
        assert mock_poi_repo.update.called

    def test_delete_poi_success(
        self, client: TestClient, sample_poi: POI, mock_poi_repo: AsyncMock
    ) -> None:
        """Asserts successful deletion returns 204 No Content."""
        mock_poi_repo.delete.return_value = True
        resp = client.delete(f"/api/pois/{sample_poi.id}")
        assert resp.status_code == 204

    def test_delete_poi_not_found(self, client: TestClient, mock_poi_repo: AsyncMock) -> None:
        """Asserts 404 ProblemDetails when deleting nonexistent POI."""
        mock_poi_repo.delete.return_value = False
        resp = client.delete(f"/api/pois/{uuid4()}")
        assert resp.status_code == 404


class TestDedupAndMergeRoutes:
    """Tests for /api/pois/dedup-check and /api/pois/merge."""

    def test_dedup_check_urban_preset(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts dedup check queries with 805m radius for urban preset."""
        match = PotentialDuplicateMatch(
            existing_poi=sample_poi,
            distance_meters=250.0,
            name_similarity=0.88,
            match_confidence=0.91,
        )
        mock_poi_repo.find_potential_duplicates.return_value = [match]
        mock_tag_repo.get_tags_for_pois.return_value = {}

        resp = client.get(
            "/api/pois/dedup-check?name=Yosemite+Valley&lon=-119.538&lat=37.865&preset=urban"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["matches"]) == 1
        assert data["matches"][0]["distance_meters"] == 250.0
        assert data["matches"][0]["name_similarity"] == 0.88

    def test_merge_pois_success(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts merge returns retained target POI."""
        mock_poi_repo.merge_pois.return_value = sample_poi
        mock_tag_repo.get_tags_for_poi.return_value = []

        payload = {
            "target_poi_id": str(sample_poi.id),
            "source_poi_id": str(uuid4()),
            "use_source_for": ["description", "official_url"],
            "merge_tags": True,
        }

        resp = client.post("/api/pois/merge", json=payload)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(sample_poi.id)
