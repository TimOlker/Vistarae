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

"""Unit tests for atomic POI field-by-field merge and referential re-parenting (T-021).

Tests:
- POST /api/pois/merge: scalar resolution (name, description, duration, rating, coords)
- POST /api/pois/merge: set resolution & deduplication (addresses, directories, dates, tags)
- POST /api/pois/merge: visit lifecycle flag re-calculation
- POST /api/pois/merge: referential re-parenting (itinerary_items, poi_lists, scanned_paths, child POIs)
- POST /api/pois/merge: source POI deletion
- POST /api/pois/merge: in-memory draft merge (source_poi_id is None)
- POST /api/pois/merge: error handling (same POI 422, missing target 404, missing source 404, cross-tenant 404, cycle 422)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import POI, TagEntity, User
from vistarae_core.domain.exceptions import POINotFoundError
from vistarae_core.domain.value_objects import (
    AddressRecord,
    EnrichmentStatus,
    SourceType,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi_merge import POIMergeRequest

from services.poi.dependencies import get_current_user, get_poi_repo, get_tag_repo
from services.poi.main import app
from services.poi.services.merge_service import MergeService


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
def other_user() -> User:
    """Mock distinct user for cross-tenant rejection testing."""
    return User(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        cognito_sub="sub-traveler-99",
        email="stranger@example.com",
        full_name="Other User",
        is_active=True,
    )


@pytest.fixture
def target_poi(current_user: User) -> POI:
    """Fixture providing target POI."""
    return POI(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        user_id=current_user.id,
        name="Old Faithful Geyser",
        geom=WGS84Point(lon=-110.8281, lat=44.4605),
        description="Famous cone geyser in Yellowstone.",
        addresses=[
            AddressRecord(
                street="Old Faithful Inn Rd",
                city="Yellowstone National Park",
                state_province="Wyoming",
                country="United States",
                postal_code="82190",
            )
        ],
        address="Old Faithful Inn Rd",
        city="Yellowstone National Park",
        states=["Wyoming"],
        countries=["United States"],
        visit_state=VisitState.NOT_VISITED,
        visited_dates=[],
        want_to_visit_again=False,
        source_type=SourceType.MANUAL,
        source_value=None,
        rating=4,
        recommended_duration_hours=1.5,
        recommended_visit_days=1,
        official_url="https://www.nps.gov/yell/planyourvisit/exploreoldfaithful.htm",
        wiki_url="https://en.wikipedia.org/wiki/Old_Faithful",
        directory_paths=["/photos/yellowstone_2023"],
        image_urls=["https://images.example.com/old_faithful_1.jpg"],
        enrichment_status=EnrichmentStatus.SUCCESS,
    )


@pytest.fixture
def source_poi(current_user: User) -> POI:
    """Fixture providing source POI."""
    return POI(
        id=UUID("10000000-0000-0000-0000-000000000002"),
        user_id=current_user.id,
        name="Old Faithful (Upper Geyser Basin)",
        geom=WGS84Point(lon=-110.8285, lat=44.4608),
        description="Rich historical geothermal feature erupting every 90 minutes.",
        addresses=[
            AddressRecord(
                street="Upper Geyser Basin",
                city="Yellowstone National Park",
                state_province="Wyoming",
                country="United States",
                postal_code="82190",
            )
        ],
        address="Upper Geyser Basin",
        city="Yellowstone National Park",
        states=["Wyoming"],
        countries=["United States"],
        visit_state=VisitState.VISITED_RETURN,
        visited_dates=["2024-07-04"],
        want_to_visit_again=True,
        source_type=SourceType.WEB,
        source_value="https://travelblog.example.com/yellowstone",
        rating=5,
        recommended_duration_hours=2.0,
        recommended_visit_days=1,
        official_url=None,
        wiki_url="https://en.wikipedia.org/wiki/Old_Faithful",
        directory_paths=["/photos/yellowstone_2024", "/photos/yellowstone_2023"],
        image_urls=["https://images.example.com/old_faithful_2.jpg"],
        enrichment_status=EnrichmentStatus.SUCCESS,
    )


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock SQLAlchemy AsyncSession simulating rowcount on execute."""
    session = AsyncMock()
    # Mock result with rowcount
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 2
    session.execute.return_value = mock_cursor
    return session


@pytest.fixture
def mock_poi_repo(target_poi: POI, source_poi: POI) -> AsyncMock:
    """Mock IPOIRepository returning target and source."""
    repo = AsyncMock(spec=IPOIRepository)
    pois = {target_poi.id: target_poi, source_poi.id: source_poi}

    async def get_by_id(poi_id: UUID, user_id: UUID) -> POI | None:
        p = pois.get(poi_id)
        if p and p.user_id == user_id:
            return p
        return None

    repo.get_by_id.side_effect = get_by_id
    repo.update.side_effect = lambda p: p
    repo.delete.return_value = True
    repo.bulk_detach_tags.return_value = None
    repo.bulk_attach_tags.return_value = None
    return repo


@pytest.fixture
def mock_tag_repo() -> AsyncMock:
    """Mock ITagRepository."""
    repo = AsyncMock(spec=ITagRepository)
    repo.get_tags_for_poi.return_value = [
        TagEntity(
            id=uuid4(), user_id=UUID("00000000-0000-0000-0000-000000000001"), name="geothermal"
        )
    ]
    repo.get_or_create.side_effect = lambda uid, name: TagEntity(id=uuid4(), user_id=uid, name=name)
    return repo


@pytest.mark.asyncio
async def test_merge_same_poi_raises_value_error(
    current_user: User,
    target_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that attempting to merge a POI into itself raises ValueError."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    req = POIMergeRequest(
        source_poi_id=target_poi.id,
        target_poi_id=target_poi.id,
        selected_scalars={},
        selected_sets={},
    )
    with pytest.raises(ValueError, match="Source POI and Target POI cannot be the same"):
        await service.merge_pois(current_user.id, req)


@pytest.mark.asyncio
async def test_merge_nonexistent_target_raises_not_found(
    current_user: User,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that non-existent target POI raises POINotFoundError."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    missing_id = uuid4()
    req = POIMergeRequest(
        source_poi_id=source_poi.id,
        target_poi_id=missing_id,
        selected_scalars={},
        selected_sets={},
    )
    with pytest.raises(POINotFoundError):
        await service.merge_pois(current_user.id, req)


@pytest.mark.asyncio
async def test_merge_nonexistent_source_raises_not_found(
    current_user: User,
    target_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that non-existent source POI raises POINotFoundError."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    missing_id = uuid4()
    req = POIMergeRequest(
        source_poi_id=missing_id,
        target_poi_id=target_poi.id,
        selected_scalars={},
        selected_sets={},
    )
    with pytest.raises(POINotFoundError):
        await service.merge_pois(current_user.id, req)


@pytest.mark.asyncio
async def test_merge_cross_tenant_rejected(
    other_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Asserts that attempting to merge another user's POI is rejected with 404 (REQ-MERGE-006)."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    req = POIMergeRequest(
        source_poi_id=source_poi.id,
        target_poi_id=target_poi.id,
        selected_scalars={},
        selected_sets={},
    )
    # Using other_user who does not own target_poi
    with pytest.raises(POINotFoundError):
        await service.merge_pois(other_user.id, req)


@pytest.mark.asyncio
async def test_merge_scalar_and_set_synthesis(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests selective scalar resolution and set unioning with deduplication."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    req = POIMergeRequest(
        source_poi_id=source_poi.id,
        target_poi_id=target_poi.id,
        selected_scalars={
            "name": "Old Faithful Geyser (Unified)",
            "description": source_poi.description,
            "rating": 5,
            "recommended_duration_hours": 2.0,
            "source_type": "Web",
            "source_value": "https://travelblog.example.com/yellowstone",
            "want_to_visit_again": True,
            "latitude": 44.4608,
            "longitude": -110.8285,
        },
        selected_sets={
            "addresses": [
                {
                    "street": "Old Faithful Inn Rd",
                    "city": "Yellowstone National Park",
                    "state_province": "Wyoming",
                    "country": "United States",
                    "postal_code": "82190",
                },
                {
                    "street": "Upper Geyser Basin",
                    "city": "Yellowstone National Park",
                    "state_province": "Wyoming",
                    "country": "United States",
                    "postal_code": "82190",
                },
                # Duplicate address to test de-duplication
                {
                    "street": "Old Faithful Inn Rd",
                    "city": "Yellowstone National Park",
                    "state_province": "Wyoming",
                    "country": "United States",
                    "postal_code": "82190",
                },
            ],
            "directory_paths": [
                "/photos/yellowstone_2023",
                "/photos/yellowstone_2024",
                "/photos/yellowstone_2023",  # duplicate
            ],
            "visited_dates": ["2024-07-04", "2023-08-15"],
            "tags": ["geothermal", "national-park", "yellowstone"],
        },
    )

    response = await service.merge_pois(current_user.id, req)

    assert response.deleted_source_poi_id == source_poi.id
    assert response.target_poi.name == "Old Faithful Geyser (Unified)"
    assert response.target_poi.description == source_poi.description
    assert response.target_poi.rating == 5
    assert response.target_poi.recommended_duration_hours == 2.0
    assert response.target_poi.lat == 44.4608
    assert response.target_poi.lon == -110.8285

    # Addresses de-duplicated
    assert len(response.target_poi.addresses) == 2

    # Directory paths de-duplicated
    assert response.target_poi.directory_paths == [
        "/photos/yellowstone_2023",
        "/photos/yellowstone_2024",
    ]

    # Visited dates sorted chronologically
    assert response.target_poi.visited_dates == ["2023-08-15", "2024-07-04"]
    assert response.target_poi.already_visited is True
    assert response.target_poi.visit_pending is True

    # Source deleted
    mock_poi_repo.delete.assert_called_once_with(source_poi.id, current_user.id)


@pytest.mark.asyncio
async def test_merge_in_memory_draft_success(
    current_user: User,
    target_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests merging an in-memory draft (source_poi_id is None) into target POI."""
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    req = POIMergeRequest(
        source_poi_id=None,
        target_poi_id=target_poi.id,
        selected_scalars={
            "description": "Updated from in-memory draft before save.",
            "rating": 5,
        },
        selected_sets={
            "directory_paths": ["/photos/draft_folder"],
        },
    )

    response = await service.merge_pois(current_user.id, req)

    assert response.deleted_source_poi_id is None
    assert response.target_poi.description == "Updated from in-memory draft before save."
    assert response.target_poi.rating == 5
    assert response.target_poi.directory_paths == ["/photos/draft_folder"]
    # No source deletion executed
    mock_poi_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_merge_reparenting_executes_in_session(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Verifies that itinerary_items, poi_lists, scanned_paths, and child POIs are re-parented."""
    cursor = MagicMock()
    cursor.rowcount = 3
    mock_db_session.execute.return_value = cursor

    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)
    req = POIMergeRequest(
        source_poi_id=source_poi.id,
        target_poi_id=target_poi.id,
        selected_scalars={"name": target_poi.name},
        selected_sets={},
    )

    response = await service.merge_pois(current_user.id, req)

    assert response.reparented_itinerary_items_count == 3
    assert response.reparented_list_memberships_count == 3
    assert response.reparented_child_pois_count == 3
    assert mock_db_session.execute.call_count >= 5


def test_merge_endpoint_http_flow(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/merge endpoint via FastAPI TestClient."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "source_poi_id": str(source_poi.id),
        "target_poi_id": str(target_poi.id),
        "selected_scalars": {
            "name": "Synthesized Old Faithful",
            "rating": 5,
        },
        "selected_sets": {
            "tags": ["national-park", "geothermal"],
        },
    }

    response = client.post("/api/pois/merge", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["target_poi"]["name"] == "Synthesized Old Faithful"
    assert data["deleted_source_poi_id"] == str(source_poi.id)

    app.dependency_overrides.clear()


def test_merge_endpoint_missing_target_404(
    current_user: User,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/merge with non-existent target returns 404."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    missing_id = str(uuid4())
    payload = {
        "source_poi_id": str(source_poi.id),
        "target_poi_id": missing_id,
        "selected_scalars": {},
        "selected_sets": {},
    }

    response = client.post("/api/pois/merge", json=payload)
    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_merge_endpoint_same_source_target_422(
    current_user: User,
    target_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/merge with identical source and target returns 422."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "source_poi_id": str(target_poi.id),
        "target_poi_id": str(target_poi.id),
        "selected_scalars": {},
        "selected_sets": {},
    }

    response = client.post("/api/pois/merge", json=payload)
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_merge_endpoint_cyclic_hierarchy_422(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Tests POST /api/pois/merge with cycle returns 422."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

    client = TestClient(app)
    payload = {
        "source_poi_id": str(source_poi.id),
        "target_poi_id": str(target_poi.id),
        "selected_scalars": {
            "parent_poi_id": str(target_poi.id),
        },
        "selected_sets": {},
    }

    response = client.post("/api/pois/merge", json=payload)
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_merge_service_all_fields_and_branches(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Covers all scalar and set synthesis branches in MergeService."""
    cursor = MagicMock()
    cursor.rowcount = 1
    mock_db_session.execute.return_value = cursor

    cursor_hier = MagicMock()
    cursor_hier.first.return_value = None
    mock_db_session.execute.side_effect = [
        cursor_hier,  # validate_no_cycle query
        cursor,  # itin
        cursor,  # poi_lists delete
        cursor,  # poi_lists update
        cursor,  # scanned paths
        cursor,  # child pois
        cursor,  # detach tags
    ]

    parent_id = uuid4()
    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)

    req = POIMergeRequest(
        source_poi_id=source_poi.id,
        target_poi_id=target_poi.id,
        selected_scalars={
            "name": "Full Field Synthesized",
            "description": "New description",
            "recommended_duration_hours": 3.5,
            "recommended_visit_days": 2,
            "source_type": "Web",
            "source_value": "https://example.com",
            "official_url": "https://nps.gov",
            "wiki_url": "https://wikipedia.org",
            "want_to_visit_again": True,
            "rating": 5,
            "visit_state": VisitState.VISITED_RETURN,
            "latitude": 44.4600,
            "longitude": -110.8200,
            "parent_poi_id": str(parent_id),
        },
        selected_sets={
            "addresses": [
                AddressRecord(
                    street="100 Main St",
                    city="Cody",
                    state_province="WY",
                    country="United States",
                    postal_code="82414",
                )
            ],
            "directory_paths": ["  /photos/trip  ", "", None],
            "image_urls": ["  https://img.com/1.jpg  ", ""],
            "visited_dates": ["2023-01-01", "2022-01-01"],
            "tags": ["geothermal", "national-park"],
        },
    )

    response = await service.merge_pois(current_user.id, req)
    assert response.target_poi.name == "Full Field Synthesized"
    assert target_poi.recommended_duration_hours == 3.5
    assert target_poi.recommended_visit_days == 2
    assert target_poi.source_type == "Web"
    assert target_poi.source_value == "https://example.com"
    assert target_poi.official_url == "https://nps.gov"
    assert target_poi.wiki_url == "https://wikipedia.org"
    assert target_poi.want_to_visit_again is True
    assert target_poi.rating == 5
    assert target_poi.visit_state == VisitState.VISITED_RETURN
    assert target_poi.geom.lat == 44.4600
    assert target_poi.geom.lon == -110.8200
    assert target_poi.parent_poi_id == parent_id
    assert target_poi.directory_paths == ["/photos/trip"]
    assert target_poi.image_urls == ["https://img.com/1.jpg"]
    assert target_poi.visited_dates == ["2022-01-01", "2023-01-01"]
    assert target_poi.already_visited is True
    assert target_poi.visit_pending is True


@pytest.mark.asyncio
async def test_merge_service_partial_coords_and_reset_parent(
    current_user: User,
    target_poi: POI,
    source_poi: POI,
    mock_db_session: AsyncMock,
    mock_poi_repo: AsyncMock,
    mock_tag_repo: AsyncMock,
) -> None:
    """Covers lat-only, lng-only, and parent_poi_id=None branches."""
    cursor = MagicMock()
    cursor.rowcount = 0
    mock_db_session.execute.return_value = cursor

    service = MergeService(mock_db_session, mock_poi_repo, mock_tag_repo)

    # 1. Lat only
    req1 = POIMergeRequest(
        source_poi_id=None,
        target_poi_id=target_poi.id,
        selected_scalars={
            "lat": 45.0,
            "parent_poi_id": None,
        },
        selected_sets={},
    )
    await service.merge_pois(current_user.id, req1)
    assert target_poi.geom.lat == 45.0
    assert target_poi.parent_poi_id is None

    # 2. Lng only
    req2 = POIMergeRequest(
        source_poi_id=None,
        target_poi_id=target_poi.id,
        selected_scalars={
            "lng": -111.0,
        },
        selected_sets={},
    )
    await service.merge_pois(current_user.id, req2)
    assert target_poi.geom.lon == -111.0
