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

"""Unit tests for POI update, parent candidate search, and cycle rejection (T-009).

Tests:
- GET /api/pois/parents: candidate parent lookup, descendant exclusion, typeahead search
- PATCH /api/pois/{id}: rich description, duration, URLs, directory paths, source provenance
- PATCH /api/pois/{id}: multi-address normalization (standard English country & state)
- PATCH /api/pois/{id}: visit lifecycle tracking (visited_dates, want_to_visit_again, computed flags)
- PATCH /api/pois/{id}: parent assignment, unassignment, 404 for missing parent
- PATCH /api/pois/{id}: cycle prevention (self-parent & recursive descendant loop 400)
- PATCH /api/pois/{id}: coordinate updates and tag reconciliation (30-tag ceiling)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import POI, TagEntity, User
from vistarae_core.domain.value_objects import (
    AddressRecord,
    EnrichmentStatus,
    SourceType,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository

from services.poi.dependencies import (
    get_current_user,
    get_embedding_port,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.main import app


@pytest.fixture
def current_user() -> User:
    """Mock authenticated tenant user."""
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        cognito_sub="sub-traveler-1",
        email="traveler@example.com",
        full_name="Atlas Voyager",
        is_active=True,
    )


@pytest.fixture
def sample_poi(current_user: User) -> POI:
    """Fixture providing a base POI entity."""
    return POI(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        name="Yosemite National Park",
        geom=WGS84Point(lon=-119.5383, lat=37.8651),
        parent_poi_id=None,
        description="Iconic granite cliffs and waterfalls.",
        addresses=[
            AddressRecord(
                street="9035 Village Dr",
                city="Yosemite Valley",
                state_province="California",
                country="United States",
                postal_code="95389",
            )
        ],
        address="9035 Village Dr, Yosemite Valley, CA",
        city="Yosemite Valley",
        states=["California"],
        countries=["United States"],
        visit_state=VisitState.NOT_VISITED,
        visited_dates=[],
        want_to_visit_again=False,
        source_type=SourceType.MANUAL,
        source_value="Field Notes",
        rating=5,
        recommended_duration_hours=8.0,
        recommended_visit_days=3,
        official_url="https://www.nps.gov/yose",
        wiki_url="https://en.wikipedia.org/wiki/Yosemite_National_Park",
        directory_paths=["/photos/yosemite"],
        image_urls=["https://images.example.com/yosemite1.jpg"],
        enrichment_status=EnrichmentStatus.SUCCESS,
        embedding=[0.05] * 768,
        embedding_md5="0" * 32,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def parent_poi(current_user: User) -> POI:
    """Fixture providing a macro-site parent POI."""
    return POI(
        id=UUID("20000000-0000-0000-0000-000000000002"),
        user_id=current_user.id,
        name="California State Parks System",
        geom=WGS84Point(lon=-121.4944, lat=38.5816),
        description="Statewide network of nature reserves.",
        states=["California"],
        countries=["United States"],
        enrichment_status=EnrichmentStatus.SUCCESS,
        embedding=[0.02] * 768,
        embedding_md5="1" * 32,
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
def mock_embedding_port() -> AsyncMock:
    mock = AsyncMock(spec=IEmbeddingPort)
    mock.generate_embedding.return_value = [0.01] * 768
    return mock


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    # Mock execute for CTE queries
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_result.all.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def client(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
    mock_embedding_port: AsyncMock,
    mock_session: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo
    app.dependency_overrides[get_embedding_port] = lambda: mock_embedding_port
    app.dependency_overrides[get_db_session] = lambda: mock_session

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestHierarchyParentCandidatesRoute:
    """Tests for GET /api/pois/parents (T-011)."""

    def test_get_parents_empty(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts candidate search returns empty array when no parent candidates match."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        resp = client.get("/api/pois/parents?query=NonExistent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_parents_with_candidates(self, client: TestClient, mock_session: AsyncMock) -> None:
        """Asserts candidate parent search returns mapped ParentPOICandidate records."""
        parent_id = uuid4()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (
                parent_id,
                "Sierra Nevada Range",
                "California",
                [
                    {
                        "city": "Mammoth Lakes",
                        "state_province": "California",
                        "country": "United States",
                    }
                ],
            )
        ]
        mock_session.execute.return_value = mock_result

        resp = client.get("/api/pois/parents?query=Sierra&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(parent_id)
        assert data[0]["name"] == "Sierra Nevada Range"
        assert "Mammoth Lakes, California, United States" in data[0]["location_summary"]

    def test_get_parents_excludes_active_poi_descendants(
        self, client: TestClient, mock_session: AsyncMock, sample_poi: POI
    ) -> None:
        """Asserts candidate search passes exclude_poi_id to recursive CTE exclusion."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        resp = client.get(f"/api/pois/parents?exclude_poi_id={sample_poi.id}")
        assert resp.status_code == 200
        # Check that session.execute was invoked with exclude_poi_id param
        args, kwargs = mock_session.execute.call_args
        params = args[1]
        assert params["exclude_poi_id"] == sample_poi.id


class TestPoiRichUpdateRoute:
    """Tests for PATCH /api/pois/{id} rich field updates (T-012)."""

    def test_patch_rich_fields(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts updating description, duration, URLs, directory paths, and source provenance."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []

        payload = {
            "description": "Expanded rich multi-line description.",
            "recommended_duration_hours": 6.5,
            "recommended_visit_days": 2,
            "official_url": "https://yosemite.org",
            "wiki_url": "https://en.wikipedia.org/wiki/Yosemite",
            "directory_paths": ["D:/Photos/Yosemite/2026", "D:/Photos/Yosemite/2024"],
            "image_urls": ["https://images.example.com/el-capitan.jpg"],
            "source_type": "Web",
            "source_value": "https://travelblog.example.com/guide",
        }

        resp = client.patch(f"/api/pois/{sample_poi.id}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Expanded rich multi-line description."
        assert data["recommended_duration_hours"] == 6.5
        assert data["recommended_visit_days"] == 2
        assert data["official_url"] == "https://yosemite.org"
        assert data["wiki_url"] == "https://en.wikipedia.org/wiki/Yosemite"
        assert len(data["directory_paths"]) == 2
        assert data["source_type"] == "Web"
        assert data["source_value"] == "https://travelblog.example.com/guide"

    def test_patch_addresses_with_english_normalization(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts addresses array normalizes international country aliases and state codes."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []

        payload = {
            "addresses": [
                {
                    "street": "Hauptstrasse 1",
                    "city": "berlin",
                    "state_province": "berlin",
                    "country": "Deutschland",  # German endonym -> should normalize to "Germany"
                    "postal_code": "10115",
                },
                {
                    "street": "1 Market St",
                    "city": "san francisco",
                    "state_province": "ca",  # US abbreviation -> should normalize to "California"
                    "country": "usa",  # Code -> should normalize to "United States"
                    "postal_code": "94105",
                },
            ]
        }

        resp = client.patch(f"/api/pois/{sample_poi.id}", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["addresses"]) == 2
        # Address 1 assertions
        assert data["addresses"][0]["country"] == "Germany"
        assert data["addresses"][0]["city"] == "Berlin"
        # Address 2 assertions
        assert data["addresses"][1]["country"] == "United States"
        assert data["addresses"][1]["state_province"] == "California"
        assert data["addresses"][1]["city"] == "San Francisco"

    def test_patch_visit_tracking_and_lifecycle_flags(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts visit dates and return intent deterministically compute already_visited and visit_pending."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []

        # Scenario 1: Visited in past, no intent to return -> already_visited=True, visit_pending=False
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={
                "visited_dates": ["2024-06-15"],
                "want_to_visit_again": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_visited"] is True
        assert data["visit_pending"] is False

        # Scenario 2: Visited in past, but want to visit again -> already_visited=True, visit_pending=True
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={
                "visited_dates": ["2024-06-15", "2025-08-20"],
                "want_to_visit_again": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_visited"] is True
        assert data["visit_pending"] is True

        # Scenario 3: Never visited -> already_visited=False, visit_pending=True
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={
                "visited_dates": [],
                "want_to_visit_again": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["already_visited"] is False
        assert data["visit_pending"] is True

    def test_patch_assign_and_unassign_parent(
        self,
        client: TestClient,
        sample_poi: POI,
        parent_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Asserts assigning a valid parent POI and unassigning back to root."""
        mock_poi_repo.get_by_id.side_effect = lambda pid, uid: (
            sample_poi if pid == sample_poi.id else (parent_poi if pid == parent_poi.id else None)
        )
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []

        # Step 1: Assign valid parent
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": str(parent_poi.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["parent_poi_id"] == str(parent_poi.id)

        # Step 2: Unassign parent (set to None)
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["parent_poi_id"] is None

    def test_patch_parent_not_found_returns_404(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts assigning a nonexistent parent returns 404 ProblemDetails."""
        mock_poi_repo.get_by_id.side_effect = lambda pid, uid: (
            sample_poi if pid == sample_poi.id else None
        )
        missing_parent_id = uuid4()
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": str(missing_parent_id)},
        )
        assert resp.status_code == 404
        assert resp.headers["content-type"] == "application/problem+json"

    def test_patch_self_parent_cycle_returns_400(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
    ) -> None:
        """Asserts assigning self as parent returns 400 ProblemDetails."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": str(sample_poi.id)},
        )
        assert resp.status_code == 400
        assert resp.headers["content-type"] == "application/problem+json"
        assert "circular" in resp.json()["detail"].lower()

    def test_patch_descendant_cycle_returns_400(
        self,
        client: TestClient,
        sample_poi: POI,
        parent_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Asserts assigning a descendant as parent fails with 400 ProblemDetails via CTE check."""
        mock_poi_repo.get_by_id.side_effect = lambda pid, uid: (
            sample_poi if pid == sample_poi.id else (parent_poi if pid == parent_poi.id else None)
        )
        # Mock CTE to simulate cycle detected (row returned)
        mock_result = MagicMock()
        mock_result.first.return_value = (sample_poi.id,)
        mock_session.execute.return_value = mock_result

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"parent_poi_id": str(parent_poi.id)},
        )
        assert resp.status_code == 400
        assert resp.headers["content-type"] == "application/problem+json"
        assert "circular" in resp.json()["detail"].lower()

    def test_patch_coordinates_updates_point(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts latitude and longitude updates update spatial geometry."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"latitude": 37.7749, "longitude": -122.4194},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["lat"] == pytest.approx(37.7749)
        assert data["lon"] == pytest.approx(-122.4194)

    def test_patch_tags_reconciliation(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts reconciling tags calls detach and attach and caps at 30."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p

        tag1 = TagEntity(id=uuid4(), user_id=sample_poi.user_id, name="mountains")
        mock_tag_repo.get_tags_for_poi.return_value = [tag1]
        mock_tag_repo.get_or_create.side_effect = lambda uid, name: TagEntity(
            id=uuid4(), user_id=uid, name=name
        )

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"tags": ["mountains", "national-park", "hiking"]},
        )
        assert resp.status_code == 200
        assert mock_poi_repo.bulk_detach_tags.called
        assert mock_poi_repo.bulk_attach_tags.called

    def test_patch_tags_empty_current_tags(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts attaching tags when POI currently has no tags (no detach needed)."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        mock_tag_repo.get_tags_for_poi.return_value = []
        mock_tag_repo.get_or_create.side_effect = lambda uid, name: TagEntity(
            id=uuid4(), user_id=uid, name=name
        )
        mock_poi_repo.bulk_detach_tags.reset_mock()
        mock_poi_repo.bulk_attach_tags.reset_mock()

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"tags": ["new-tag"]},
        )
        assert resp.status_code == 200
        assert not mock_poi_repo.bulk_detach_tags.called
        assert mock_poi_repo.bulk_attach_tags.called

    def test_patch_tags_detach_all(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts clearing all tags detaches existing tags without attaching new ones."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p
        existing_tag = TagEntity(id=uuid4(), user_id=sample_poi.user_id, name="old-tag")
        mock_tag_repo.get_tags_for_poi.return_value = [existing_tag]
        mock_poi_repo.bulk_detach_tags.reset_mock()
        mock_poi_repo.bulk_attach_tags.reset_mock()

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"tags": []},
        )
        assert resp.status_code == 200
        assert mock_poi_repo.bulk_detach_tags.called
        assert not mock_poi_repo.bulk_attach_tags.called

    def test_patch_tags_over_limit_raises_422(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
        mock_tag_repo: AsyncMock,
    ) -> None:
        """Asserts updating with > 30 tags raises 422 ProblemDetails."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_tag_repo.get_tags_for_poi.return_value = []

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={"tags": [f"tag-{i}" for i in range(35)]},
        )
        assert resp.status_code == 422
        assert resp.headers["content-type"] == "application/problem+json"

    def test_patch_poi_not_found(
        self,
        client: TestClient,
        mock_poi_repo: AsyncMock,
    ) -> None:
        """Asserts updating non-existent POI raises 404."""
        mock_poi_repo.get_by_id.return_value = None
        resp = client.patch(f"/api/pois/{uuid4()}", json={"name": "New Name"})
        assert resp.status_code == 404

    def test_patch_poi_coordinates_single(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
    ) -> None:
        """Asserts updating single latitude or longitude updates geometry properly."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p

        # latitude only
        resp_lat = client.patch(f"/api/pois/{sample_poi.id}", json={"latitude": 42.0})
        assert resp_lat.status_code == 200
        assert sample_poi.geom.lat == 42.0

        # longitude only
        resp_lon = client.patch(f"/api/pois/{sample_poi.id}", json={"longitude": -118.0})
        assert resp_lon.status_code == 200
        assert sample_poi.geom.lon == -118.0

    def test_patch_poi_addresses_extract_state_and_country(
        self,
        client: TestClient,
        sample_poi: POI,
        mock_poi_repo: AsyncMock,
    ) -> None:
        """Asserts updating addresses without passing states/countries populates them from addresses."""
        mock_poi_repo.get_by_id.return_value = sample_poi
        mock_poi_repo.update.side_effect = lambda p: p

        resp = client.patch(
            f"/api/pois/{sample_poi.id}",
            json={
                "addresses": [
                    {
                        "street": "123 Temple Way",
                        "city": "Kyoto",
                        "state_province": "Kyoto Prefecture",
                        "country": "Japan",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert "Kyoto Prefecture" in sample_poi.states
        assert "Japan" in sample_poi.countries
