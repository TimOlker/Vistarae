"""Integration and API unit tests for POI bulk ingestion routes."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import app
from app.models import POI, ListModel, POIListMembership, User
from app.schemas.ingestion import ConflictAction, IngestCommitItem, IngestCommitRequest
from app.schemas.poi import CollisionStatus, POICollisionMatch
from app.services.auth import get_current_user

TEST_USER = User(
    id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
    email="traveler@vistarae.com",
    hashed_password="hashedpassword",
    full_name="Traveler",
    is_active=True,
)


@pytest.mark.asyncio
async def test_list_presets_endpoint():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/pois/ingest/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        preset_ids = [p["id"] for p in data]
        assert "nps_national_parks" in preset_ids
        assert "unesco_world_heritage" in preset_ids

        # Check NPS preset summary
        nps = next(p for p in data if p["id"] == "nps_national_parks")
        assert nps["count"] == 63
        assert "NPS" in nps["tags"]


@pytest.mark.asyncio
async def test_get_preset_content_endpoint():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/pois/ingest/presets/nps_national_parks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["preset_id"] == "nps_national_parks"
        assert len(data["data"]) == 63
        assert data["data"][0]["name"] == "Acadia National Park"


@pytest.mark.asyncio
async def test_parse_and_preview_valid_csv():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    csv_data = """name,latitude,longitude,city,state,website,visit_again
Acadia National Park,44.35,-68.21,Bar Harbor,Maine,https://nps.gov/acad,true
Arches National Park,38.68,-109.57,Moab,Utah,https://nps.gov/arch,false
"""
    # Mock collision detection to return unique location
    with patch(
        "app.services.ingestion.check_spatial_collision",
        return_value=(CollisionStatus.UNIQUE_LOCATION, None, None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pois/ingest/parse-and-preview",
                json={
                    "content": csv_data,
                    "filename": "parks.csv",
                    "default_tags": ["NPS"],
                    "perform_geocoding": False,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["detected_format"] == "csv"
            assert data["total_records"] == 2
            assert data["valid_records"] == 2
            assert len(data["items"]) == 2

            p1 = data["items"][0]
            assert p1["name"] == "Acadia National Park"
            assert p1["visit_again"] is True
            assert "NPS" in p1["category_tags"]
            assert p1["action"] == "CREATE"
            assert p1["source_url"] == "parks.csv"


@pytest.mark.asyncio
async def test_parse_and_preview_missing_required_name():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    invalid_csv = """latitude,longitude,city,state
44.35,-68.21,Bar Harbor,Maine
"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/parse-and-preview",
            json={
                "content": invalid_csv,
                "perform_geocoding": False,
            },
        )
        assert resp.status_code == 422
        assert "Missing required field" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_parse_and_preview_spatial_duplicate_detected():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    csv_data = """name,latitude,longitude
Acadia National Park,44.35,-68.21
"""
    matched = POICollisionMatch(
        id=uuid.uuid4(),
        name="Acadia NP",
        poi_type="site to see",
        distance_meters=15.0,
        name_similarity=0.92,
        description="Existing park record",
        iptc_city="Bar Harbor",
        iptc_province_state="Maine",
    )

    with patch(
        "app.services.ingestion.check_spatial_collision",
        return_value=(CollisionStatus.POTENTIAL_DUPLICATE, matched, None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pois/ingest/parse-and-preview",
                json={
                    "content": csv_data,
                    "perform_geocoding": False,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["conflict_count"] == 1
            item = data["items"][0]
            assert item["collision_status"] == "POTENTIAL_DUPLICATE"
            assert item["matched_poi"]["name"] == "Acadia NP"
            assert item["action"] == "SKIP"


@pytest.mark.asyncio
async def test_commit_ingested_pois():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="1",
                action=ConflictAction.CREATE,
                poi_data={
                    "temp_id": "1",
                    "name": "Zion National Park",
                    "latitude": 37.30,
                    "longitude": -113.05,
                    "iptc_city": "Springdale",
                    "iptc_province_state": "Utah",
                    "visit_again": True,
                    "category_tags": ["NPS"],
                    "quality": {"is_valid": True},
                },
            ),
            IngestCommitItem(
                temp_id="2",
                action=ConflictAction.SKIP,
                poi_data={
                    "temp_id": "2",
                    "name": "Already in DB",
                    "latitude": 37.0,
                    "longitude": -113.0,
                    "quality": {"is_valid": True},
                },
            ),
        ],
        default_tags=["imported"],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["created_count"] == 1
        assert res["skipped_count"] == 1
        assert res["merged_count"] == 0
        assert "imported" in res["applied_tags"]
        assert len(res["created_poi_ids"]) == 1


@pytest.mark.asyncio
async def test_parse_and_preview_duplicate_with_missing_tags():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    csv_data = 'name,latitude,longitude,Tags\nGrand Canyon,36.05,-112.14,"UNESCO, World Heritage"\n'
    matched = POICollisionMatch(
        id=uuid.uuid4(),
        name="Grand Canyon National Park",
        poi_type="site to see",
        distance_meters=20.0,
        name_similarity=0.85,
        description="Existing park record",
        category_tags=["NPS"],
    )

    with patch(
        "app.services.ingestion.check_spatial_collision",
        return_value=(CollisionStatus.POTENTIAL_DUPLICATE, matched, None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pois/ingest/parse-and-preview",
                json={
                    "content": csv_data,
                    "perform_geocoding": False,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["conflict_count"] == 1
            item = data["items"][0]
            assert item["collision_status"] == "POTENTIAL_DUPLICATE"
            assert "UNESCO" in item["missing_tags"]
            assert "World Heritage" in item["missing_tags"]
            assert item["action"] == "ADD_TAGS"


@pytest.mark.asyncio
async def test_commit_ingested_pois_add_tags():
    poi_id = uuid.uuid4()
    existing_poi = POI(
        id=poi_id,
        user_id=TEST_USER.id,
        name="Grand Canyon National Park",
        description="Preserved original description",
        category_tags=["NPS"],
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=existing_poi)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="1",
                action=ConflictAction.ADD_TAGS,
                matched_poi_id=poi_id,
                poi_data={
                    "temp_id": "1",
                    "name": "Grand Canyon",
                    "description": "This new description should NOT overwrite",
                    "category_tags": ["UNESCO", "NPS", "World Heritage"],
                    "quality": {"is_valid": True},
                },
            ),
        ],
        default_tags=[],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["merged_count"] == 1
        assert res["created_count"] == 0

        # Verify existing POI had tags appended and description preserved
        assert set(existing_poi.category_tags) == {"NPS", "UNESCO", "World Heritage"}
        assert existing_poi.description == "Preserved original description"


@pytest.mark.asyncio
async def test_commit_ingested_pois_with_new_list_and_scope_new_only():
    existing_id = uuid.uuid4()
    existing_poi = POI(
        id=existing_id,
        user_id=TEST_USER.id,
        name="Existing Site",
        category_tags=["tag1"],
    )

    added_objects = []
    mock_db = AsyncMock()
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_scalar(query):
        # If query for POI
        query_str = str(query)
        if "pois" in query_str.lower():
            return existing_poi
        # If query for ListModel or POIListMembership
        return None

    mock_db.scalar = AsyncMock(side_effect=mock_scalar)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="item-new",
                action=ConflictAction.CREATE,
                poi_data={
                    "temp_id": "item-new",
                    "name": "Brand New Park",
                    "latitude": 37.123,
                    "longitude": -119.456,
                    "quality": {"is_valid": True},
                },
            ),
            IngestCommitItem(
                temp_id="item-merge",
                action=ConflictAction.MERGE,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-merge",
                    "name": "Existing Site",
                    "category_tags": ["tag2"],
                    "quality": {"is_valid": True},
                },
            ),
        ],
        new_list_title="Roadtrip 2026",
        list_membership_scope="new_only",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["created_count"] == 1
        assert res["merged_count"] == 1
        assert res["target_list_id"] is not None
        assert res["target_list_title"] == "Roadtrip 2026"

        # Check added entities:
        # 1 ListModel created with title "Roadtrip 2026"
        created_lists = [obj for obj in added_objects if isinstance(obj, ListModel)]
        assert len(created_lists) == 1
        assert created_lists[0].title == "Roadtrip 2026"

        # Memberships: Because scope was "new_only", only the newly created POI gets membership!
        created_memberships = [obj for obj in added_objects if isinstance(obj, POIListMembership)]
        assert len(created_memberships) == 1
        assert created_memberships[0].poi_id == uuid.UUID(res["created_poi_ids"][0])


@pytest.mark.asyncio
async def test_commit_ingested_pois_with_scope_both():
    existing_id = uuid.uuid4()
    existing_poi = POI(
        id=existing_id,
        user_id=TEST_USER.id,
        name="Existing Landmark",
        category_tags=["tag1"],
    )

    added_objects = []
    mock_db = AsyncMock()
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_scalar(query):
        query_str = str(query)
        if "pois" in query_str.lower():
            return existing_poi
        return None

    mock_db.scalar = AsyncMock(side_effect=mock_scalar)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="item-new",
                action=ConflictAction.CREATE,
                poi_data={
                    "temp_id": "item-new",
                    "name": "New Vista",
                    "latitude": 38.123,
                    "longitude": -120.456,
                    "quality": {"is_valid": True},
                },
            ),
            IngestCommitItem(
                temp_id="item-merge",
                action=ConflictAction.MERGE,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-merge",
                    "name": "Existing Landmark",
                    "category_tags": ["tag2"],
                    "quality": {"is_valid": True},
                },
            ),
        ],
        new_list_title="All In One List",
        list_membership_scope="both",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["created_count"] == 1
        assert res["merged_count"] == 1
        assert res["target_list_title"] == "All In One List"

        # Memberships: Because scope was "both", BOTH newly created POI and merged existing POI get membership!
        created_memberships = [obj for obj in added_objects if isinstance(obj, POIListMembership)]
        assert len(created_memberships) == 2
        assigned_poi_ids = {m.poi_id for m in created_memberships}
        assert existing_id in assigned_poi_ids
        assert uuid.UUID(res["created_poi_ids"][0]) in assigned_poi_ids


@pytest.mark.asyncio
async def test_commit_ingested_pois_with_scope_both_and_skipped_duplicates():
    existing_id = uuid.uuid4()
    existing_poi = POI(
        id=existing_id,
        user_id=TEST_USER.id,
        name="UNESCO Site Alpha",
        category_tags=["UNESCO"],
    )

    added_objects = []
    mock_db = AsyncMock()
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_scalar(query):
        query_str = str(query)
        if "pois" in query_str.lower():
            return existing_poi
        return None

    mock_db.scalar = AsyncMock(side_effect=mock_scalar)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # A CSV where the place is an existing duplicate and action is SKIP
    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="item-skip",
                action=ConflictAction.SKIP,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-skip",
                    "name": "UNESCO Site Alpha",
                    "category_tags": ["UNESCO"],
                    "quality": {"is_valid": True},
                },
            ),
        ],
        new_list_title="World Heritage List",
        list_membership_scope="both",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["skipped_count"] == 1
        assert res["target_list_title"] == "World Heritage List"
        assert res["enrolled_count"] == 1

        # Membership: Existing skipped POI must still be enrolled when scope is "both"!
        created_memberships = [obj for obj in added_objects if isinstance(obj, POIListMembership)]
        assert len(created_memberships) == 1
        assert created_memberships[0].poi_id == existing_id


@pytest.mark.asyncio
async def test_commit_ingested_pois_deduplicates_same_poi_in_batch():
    """Verifies that multiple rows in the same CSV matching the same existing POI ID

    do not cause duplicate primary key insertions into poi_list_memberships.
    """
    existing_id = uuid.uuid4()
    existing_poi = POI(
        id=existing_id,
        user_id=TEST_USER.id,
        name="Vietnam Women's Memorial",
        category_tags=["NPS"],
    )

    added_objects = []
    mock_db = AsyncMock()
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_scalar(query):
        query_str = str(query)
        if "pois" in query_str.lower():
            return existing_poi
        return None

    mock_db.scalar = AsyncMock(side_effect=mock_scalar)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # 3 distinct CSV rows all resolving to the same existing POI
    payload = IngestCommitRequest(
        items=[
            IngestCommitItem(
                temp_id="item-1",
                action=ConflictAction.SKIP,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-1",
                    "name": "Vietnam Veterans Memorial",
                    "quality": {"is_valid": True},
                },
            ),
            IngestCommitItem(
                temp_id="item-2",
                action=ConflictAction.MERGE,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-2",
                    "name": "Constitution Gardens",
                    "quality": {"is_valid": True},
                },
            ),
            IngestCommitItem(
                temp_id="item-3",
                action=ConflictAction.ADD_TAGS,
                matched_poi_id=existing_id,
                poi_data={
                    "temp_id": "item-3",
                    "name": "Lincoln Memorial",
                    "quality": {"is_valid": True},
                },
            ),
        ],
        new_list_title="National Mall Sites",
        list_membership_scope="both",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/ingest/commit",
            json=payload.model_dump(mode="json"),
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["skipped_count"] == 1
        assert res["merged_count"] == 2
        assert res["enrolled_count"] == 1  # Exactly 1 enrollment, deduplicated!

        created_memberships = [obj for obj in added_objects if isinstance(obj, POIListMembership)]
        assert len(created_memberships) == 1
        assert created_memberships[0].poi_id == existing_id
