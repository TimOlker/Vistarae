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

"""Unit tests for pre-save duplicate collision detection (T-026).

Tests:
- POST /api/pois/check-duplicate: collision detection (distance <= 200m, similarity >= 0.60)
- POST /api/pois/check-duplicate: no collision scenario (clean save)
- POST /api/pois/check-duplicate: self-exclusion via exclude_poi_id
- POST /api/pois/check-duplicate: HTTP endpoint contract verification
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.domain.entities import (
    POI,
    PotentialDuplicateMatch,
    TagEntity,
    User,
)
from vistarae_core.domain.value_objects import (
    AddressRecord,
    EnrichmentStatus,
    SourceType,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi_duplicate import DuplicateCheckRequest

from services.poi.dependencies import get_current_user, get_poi_repo, get_tag_repo
from services.poi.main import app
from services.poi.routes.duplicate import check_duplicate_poi


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
def existing_poi(current_user: User) -> POI:
    """Fixture providing existing POI in database."""
    return POI(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        name="Yellowstone Grand Canyon",
        geom=WGS84Point(lon=-110.4965, lat=44.7188),
        description="Breathtaking canyon carved by the Yellowstone River.",
        addresses=[
            AddressRecord(
                street="Canyon Village",
                city="Yellowstone National Park",
                state_province="Wyoming",
                country="United States",
                postal_code="82190",
            )
        ],
        address="Canyon Village",
        city="Yellowstone National Park",
        states=["Wyoming"],
        countries=["United States"],
        visit_state=VisitState.NOT_VISITED,
        visited_dates=[],
        want_to_visit_again=False,
        source_type=SourceType.MANUAL,
        source_value=None,
        rating=5,
        recommended_duration_hours=3.0,
        recommended_visit_days=1,
        official_url=None,
        wiki_url=None,
        directory_paths=[],
        image_urls=[],
        enrichment_status=EnrichmentStatus.SUCCESS,
    )


@pytest.fixture
def mock_poi_repo(existing_poi: POI) -> AsyncMock:
    """Mock IPOIRepository configured for duplicate probing."""
    repo = AsyncMock(spec=IPOIRepository)
    match = PotentialDuplicateMatch(
        existing_poi=existing_poi,
        distance_meters=45.2,
        name_similarity=0.88,
        match_confidence=0.84,
    )
    repo.find_potential_duplicates.return_value = [match]
    return repo


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    """Mock ITagRepository."""
    repo = AsyncMock(spec=ITagRepository)
    repo.get_tags_for_poi.return_value = [
        TagEntity(id=uuid4(), user_id=UUID("00000000-0000-0000-0000-000000000001"), name="canyon")
    ]
    return repo


@pytest.mark.asyncio
async def test_duplicate_check_collision_detected(
    current_user: User,
    existing_poi: POI,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that close proximity (45m) and high similarity (0.88) returns is_duplicate=True."""
    req = DuplicateCheckRequest(
        name="Grand Canyon of Yellowstone",
        latitude=44.7189,
        longitude=-110.4966,
        exclude_poi_id=None,
    )
    response = await check_duplicate_poi(
        req=req,
        current_user=current_user,
        poi_repo=mock_poi_repo,
        tag_repo=mock_tag_repo,
    )

    assert response.is_duplicate is True
    assert response.candidate is not None
    assert response.candidate.poi_id == existing_poi.id
    assert response.candidate.name == existing_poi.name
    assert response.candidate.distance_meters == 45.2
    assert response.candidate.name_similarity == 0.88
    assert response.candidate.poi is not None
    assert response.candidate.poi.name == existing_poi.name


@pytest.mark.asyncio
async def test_duplicate_check_no_collision(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that when no candidates match, response returns is_duplicate=False."""
    mock_poi_repo.find_potential_duplicates.return_value = []
    req = DuplicateCheckRequest(
        name="Unique Faraway Trailhead",
        latitude=45.0,
        longitude=-111.0,
        exclude_poi_id=None,
    )
    response = await check_duplicate_poi(
        req=req,
        current_user=current_user,
        poi_repo=mock_poi_repo,
        tag_repo=mock_tag_repo,
    )

    assert response.is_duplicate is False
    assert response.candidate is None


@pytest.mark.asyncio
async def test_duplicate_check_self_exclusion(
    current_user: User,
    existing_poi: POI,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that when updating an existing POI, self-collision is excluded."""
    req = DuplicateCheckRequest(
        name="Yellowstone Grand Canyon",
        latitude=44.7188,
        longitude=-110.4965,
        exclude_poi_id=existing_poi.id,  # Exclude self
    )
    response = await check_duplicate_poi(
        req=req,
        current_user=current_user,
        poi_repo=mock_poi_repo,
        tag_repo=mock_tag_repo,
    )

    assert response.is_duplicate is False
    assert response.candidate is None


def test_duplicate_check_endpoint_http_match(
    current_user: User,
    existing_poi: POI,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/check-duplicate via TestClient when collision detected."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "name": "Grand Canyon of Yellowstone",
        "latitude": 44.7189,
        "longitude": -110.4966,
        "exclude_poi_id": None,
    }

    response = client.post("/api/pois/check-duplicate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_duplicate"] is True
    assert data["candidate"]["poi_id"] == str(existing_poi.id)
    assert data["candidate"]["distance_meters"] == 45.2

    app.dependency_overrides.clear()


def test_duplicate_check_endpoint_http_no_match(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/check-duplicate via TestClient when no collision detected."""
    mock_poi_repo.find_potential_duplicates.return_value = []
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "name": "Unique Overlook",
        "latitude": 44.0,
        "longitude": -110.0,
    }

    response = client.post("/api/pois/check-duplicate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_duplicate"] is False
    assert data["candidate"] is None

    app.dependency_overrides.clear()


def test_duplicate_check_invalid_coordinates_422(
    current_user: User,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/check-duplicate returns 422 on invalid latitude."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "name": "Invalid Lat POI",
        "latitude": 999.0,  # Invalid latitude
        "longitude": -110.0,
    }

    response = client.post("/api/pois/check-duplicate", json=payload)
    assert response.status_code == 422

    app.dependency_overrides.clear()
