"""Unit tests for PostGIS spatial deduplication and hierarchy algorithm."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.poi import CollisionStatus
from app.services.deduplication import check_spatial_collision


@pytest.mark.asyncio
async def test_collision_duplicate_detected():
    mock_db = AsyncMock()
    mock_result = MagicMock()

    dup_id = uuid.uuid4()
    mock_result.mappings.return_value.all.return_value = [
        {
            "id": dup_id,
            "name": "Glacier Point Overlook",
            "name_aliases": ["Glacier Point"],
            "poi_type": "photo location",
            "personal_rating": 5,
            "description": "Breathtaking overlook",
            "iptc_city": "Yosemite Village",
            "iptc_province_state": "California",
            "geofence_radius_ft": 500,
            "parent_poi_id": None,
            "distance_meters": 12.5,
            "name_similarity": 0.82,  # >= 0.60
        }
    ]
    mock_db.execute.return_value = mock_result

    status, dup, _ = await check_spatial_collision(
        cand_name="Glacier Point View",
        cand_lat=37.7304,
        cand_lng=-119.5736,
        radius_ft=500,
        db=mock_db,
    )

    assert status == CollisionStatus.POTENTIAL_DUPLICATE
    assert dup is not None
    assert dup.id == dup_id
    assert dup.distance_meters == 12.5


@pytest.mark.asyncio
async def test_collision_nearby_parent_detected():
    mock_db = AsyncMock()
    mock_result = MagicMock()

    park_id = uuid.uuid4()
    mock_result.mappings.return_value.all.return_value = [
        {
            "id": park_id,
            "name": "Yosemite National Park",
            "name_aliases": ["Yosemite"],
            "poi_type": "site to see",
            "personal_rating": 5,
            "description": "National park in California",
            "iptc_city": "Yosemite Village",
            "iptc_province_state": "California",
            "geofence_radius_ft": 52800,
            "parent_poi_id": None,
            "distance_meters": 120.0,
            "name_similarity": 0.15,  # < 0.60
        }
    ]
    mock_db.execute.return_value = mock_result

    status, dup, parent = await check_spatial_collision(
        cand_name="Glacier Point",
        cand_lat=37.7304,
        cand_lng=-119.5736,
        radius_ft=500,
        db=mock_db,
    )

    assert status == CollisionStatus.NEARBY_PARENT
    assert dup is None
    assert parent is not None
    assert parent.id == park_id
    assert parent.name == "Yosemite National Park"


@pytest.mark.asyncio
async def test_collision_unique_location():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    status, dup, parent = await check_spatial_collision(
        cand_name="Untouched Secret Peak",
        cand_lat=38.1234,
        cand_lng=-120.5678,
        radius_ft=500,
        db=mock_db,
    )

    assert status == CollisionStatus.UNIQUE_LOCATION
    assert dup is None
    assert parent is None


@pytest.mark.asyncio
async def test_check_duplicate_poi_endpoint():
    from httpx import ASGITransport, AsyncClient

    from app.db import get_db
    from app.main import app
    from app.models import User
    from app.services.auth import get_current_user

    test_user = User(
        id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        email="traveler@vistarae.com",
        hashed_password="pw",
        full_name="Traveler",
        is_active=True,
    )

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    dup_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {
            "id": dup_id,
            "name": "Glacier Point Overlook",
            "name_aliases": ["Glacier Point"],
            "poi_type": "photo location",
            "personal_rating": 5,
            "description": "Breathtaking overlook",
            "iptc_city": "Yosemite Village",
            "iptc_province_state": "California",
            "geofence_radius_ft": 500,
            "parent_poi_id": None,
            "distance_meters": 10.0,
            "name_similarity": 0.85,
        }
    ]
    mock_db.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/check-duplicate",
            json={
                "name": "Glacier Point View",
                "latitude": 37.7304,
                "longitude": -119.5736,
                "radius_ft": 500,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["collision_status"] == "POTENTIAL_DUPLICATE"
    assert data["matched_poi"] is not None
    assert data["matched_poi"]["id"] == str(dup_id)
    assert data["matched_poi"]["name"] == "Glacier Point Overlook"

    app.dependency_overrides.clear()
