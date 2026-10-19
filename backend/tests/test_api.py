"""Integration tests for FastAPI endpoints with authentication."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import app
from app.models import User
from app.schemas.extraction import POIExtractionCandidate
from app.schemas.poi import CollisionStatus
from app.services.auth import get_current_user

# Reusable mock user
TEST_USER = User(
    id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
    email="testuser@vistarae.com",
    hashed_password="fakehashedpassword",
    full_name="Test Traveler",
    is_active=True,
)


@pytest.mark.asyncio
async def test_health_endpoint():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "vistarae-backend"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthenticated_request_fails_with_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/lists")

    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_extract_and_check_endpoint():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_candidate = POIExtractionCandidate(
        name="Horseshoe Bend",
        name_aliases=[],
        poi_type="photo location",
        personal_rating=5,
        description="Iconic incised meander of the Colorado River.",
        category_tags=["viewpoint", "canyon"],
        physical_effort="paved walk",
        booking_lead_time="walk-in ok",
        indoor_outdoor="Outdoor",
        estimated_duration="1 hour",
        cost_tier="$",
        search_address_query="Horseshoe Bend, Page, Arizona",
        iptc_city="Page",
        iptc_province_state="Arizona",
        iptc_country_code="US",
    )

    with patch("app.main.extract_candidate_from_text", return_value=mock_candidate), \
         patch("app.main.geocode_query", return_value=(36.8791, -111.5104, "Horseshoe Bend, AZ", {})), \
         patch("app.main.check_spatial_collision", return_value=(CollisionStatus.UNIQUE_LOCATION, None, None)):

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/extract-and-check",
                json={
                    "selected_text": "Horseshoe Bend is a horseshoe-shaped incised meander of the Colorado River.",
                    "page_title": "Horseshoe Bend Travel Guide",
                    "page_url": "https://example.com/horseshoe",
                },
                headers={
                    "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
                    "X-Source": "chrome-extension://vistarae",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["candidate"]["name"] == "Horseshoe Bend"
        assert data["latitude"] == 36.8791
        assert data["longitude"] == -111.5104
        assert data["collision_status"] == "UNIQUE_LOCATION"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user_list():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/lists",
            json={
                "title": "Southwest Desert Odyssey",
                "description": "Red rock canyons and vistas",
                "is_trip": True,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Southwest Desert Odyssey"
    assert data["is_trip"] is True
    assert "id" in data

    app.dependency_overrides.clear()
