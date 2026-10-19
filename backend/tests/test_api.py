"""Integration tests for FastAPI endpoints with authentication."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import app
from app.models import ListModel, User, UserTag
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
                    "X-Source": "extension",
                    "X-Destination": "backend",
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
async def test_extract_and_check_with_google_maps_direct_coordinates():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_candidate = POIExtractionCandidate(
        name="Glacier Point",
        name_aliases=["Glacier Point Overlook"],
        poi_type="photo location",
        personal_rating=5,
        description="Breathtaking panoramic overlook of Yosemite Valley.",
        category_tags=["viewpoint", "scenic"],
        physical_effort="paved walk",
        booking_lead_time="walk-in ok",
        indoor_outdoor="Outdoor",
        estimated_duration="1-2 hours",
        cost_tier="Free",
        search_address_query="Glacier Point, California",
        iptc_city="Yosemite Village",
        iptc_province_state="California",
        iptc_country_code="US",
    )

    with patch("app.main.extract_candidate_from_text", return_value=mock_candidate), \
         patch("app.main.check_spatial_collision", return_value=(CollisionStatus.UNIQUE_LOCATION, None, None)):

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/extract-and-check",
                json={
                    "selected_text": "",
                    "page_title": "Glacier Point - Google Maps",
                    "page_url": "https://www.google.com/maps/place/Glacier+Point/@37.730412,-119.573645,17z",
                    "latitude": 37.730412,
                    "longitude": -119.573645,
                    "place_name": "Glacier Point",
                },
                headers={
                    "traceparent": "00-33333333333333333333333333333333-4444444444444444-01",
                    "X-Source": "extension",
                    "X-Destination": "backend",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["candidate"]["name"] == "Glacier Point"
        assert data["latitude"] == 37.730412
        assert data["longitude"] == -119.573645
        assert data["collision_status"] == "UNIQUE_LOCATION"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_and_check_reverse_geocode_fallback_when_address_missing():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Candidate with missing address fields
    mock_candidate = POIExtractionCandidate(
        name="Horseshoe Bend",
        poi_type="photo location",
        search_address_query="Horseshoe Bend",
        iptc_city=None,
        iptc_province_state=None,
        iptc_country_code=None,
    )

    fake_reverse_json = {
        "address": {
            "city": "Page",
            "state": "Arizona",
            "country_code": "us",
            "postcode": "86040",
            "road": "Horseshoe Bend Trail",
        }
    }

    with patch("app.main.extract_candidate_from_text", return_value=mock_candidate), \
         patch("app.main.reverse_geocode", return_value=("Horseshoe Bend, Page, AZ", fake_reverse_json)), \
         patch("app.main.check_spatial_collision", return_value=(CollisionStatus.UNIQUE_LOCATION, None, None)):

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/extract-and-check",
                json={
                    "selected_text": "",
                    "page_title": "Horseshoe Bend Viewpoint",
                    "page_url": "https://www.google.com/maps/place/Horseshoe+Bend/@36.8791,-111.5104,15z",
                    "latitude": 36.8791,
                    "longitude": -111.5104,
                    "place_name": "Horseshoe Bend",
                },
                headers={
                    "traceparent": "00-55555555555555555555555555555555-6666666666666666-01",
                    "X-Source": "extension",
                    "X-Destination": "backend",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["candidate"]["iptc_city"] == "Page"
        assert data["candidate"]["iptc_province_state"] == "Arizona"
        assert data["candidate"]["iptc_country_code"] == "US"
        assert data["candidate"]["iptc_zip_code"] == "86040"
        assert data["candidate"]["iptc_sublocation"] == "Horseshoe Bend Trail"

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


@pytest.mark.asyncio
async def test_delete_user_list():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    test_list_id = uuid.uuid4()
    mock_list = ListModel(
        id=test_list_id,
        user_id=TEST_USER.id,
        title="Test List",
        is_trip=False,
    )
    mock_db.scalar.return_value = mock_list

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(f"/api/v1/lists/{test_list_id}")

    assert response.status_code == 204
    mock_db.delete.assert_called_once_with(mock_list)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tags_endpoints():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["climbing"]
    mock_db.scalars.return_value = mock_scalars

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List tags
        list_res = await client.get("/api/v1/tags")
        assert list_res.status_code == 200
        tags = list_res.json()
        assert "NPS" in tags
        assert "scenic" in tags

        # 2. Create custom tag
        mock_db.scalar.return_value = None  # no duplicate
        create_res = await client.post("/api/v1/tags", json={"name": "slot-canyon"})
        assert create_res.status_code == 201
        data = create_res.json()
        assert data["name"] == "slot-canyon"
        assert data["is_custom"] is True

        # 3. Delete custom tag
        mock_tag = UserTag(id=uuid.uuid4(), user_id=TEST_USER.id, name="slot-canyon")
        mock_db.scalar.return_value = mock_tag
        del_res = await client.delete("/api/v1/tags/slot-canyon")
        assert del_res.status_code == 204
        mock_db.delete.assert_called_once_with(mock_tag)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_poi_with_detailed_fields():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pois",
            json={
                "name": "Yosemite Falls",
                "poi_type": "site to see",
                "personal_rating": 5,
                "description": "Highest waterfall in Yosemite National Park.",
                "category_tags": ["NPS", "waterfall", "scenic"],
                "visited": True,
                "visit_date": "2026-06-15",
                "latitude": 37.7566,
                "longitude": -119.5969,
                "geofence_radius_ft": 500,
                "parent_poi_id": None,
                "physical_effort": "moderate hike",
                "booking_lead_time": "walk-in ok",
                "indoor_outdoor": "Outdoor",
                "estimated_duration": "2 hours",
                "cost_tier": "Free",
                "website_official": "https://www.nps.gov/yose",
                "phone_number": "(209) 372-0200",
                "primary_image_url": "https://example.com/yosemite-falls.jpg",
                "source_url": "https://www.nps.gov/yose/planyourvisit/falls.htm",
                "source_type": "Web Selection",
                "iptc_city": "Yosemite Village",
                "iptc_province_state": "California",
                "iptc_country_code": "US",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Yosemite Falls"
    assert data["visited"] is True
    assert data["visit_date"] == "2026-06-15"
    assert data["website_official"] == "https://www.nps.gov/yose"
    assert data["phone_number"] == "(209) 372-0200"
    assert data["primary_image_url"] == "https://example.com/yosemite-falls.jpg"
    assert "NPS" in data["category_tags"]
    assert data["visit_again"] is False

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_and_check_atlas_obscura_payload():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_db.scalars.return_value = mock_scalars

    with patch("app.main.check_spatial_collision", return_value=(CollisionStatus.UNIQUE_LOCATION, None, None)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/extract-and-check",
                json={
                    "selected_text": "The oldest family-run restaurant in the United States.",
                    "page_title": "Antoine's Restaurant in New Orleans - Atlas Obscura",
                    "page_url": "https://www.atlasobscura.com/places/antoines-restaurant",
                    "place_name": "Antoine's Restaurant",
                    "latitude": 29.956737,
                    "longitude": -90.066392,
                    "category": "food/drink",
                    "website": "https://antoines.com/",
                    "city": "New Orleans",
                    "state": "Louisiana",
                    "country": "US",
                    "postal_code": "70130",
                    "category_tags": ["Restaurants", "Wine", "History"],
                    "cost_tier": "$$$",
                    "indoor_outdoor": "Indoor",
                    "physical_effort": "paved walk",
                    "best_time_to_visit": "Lunch 11:30am-2:00pm",
                    "source_type": "Atlas Obscura",
                },
                headers={
                    "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
                    "X-Source": "extension",
                    "X-Destination": "backend",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["latitude"] == 29.956737
    assert data["longitude"] == -90.066392
    cand = data["candidate"]
    assert cand["name"] == "Antoine's Restaurant"
    assert cand["poi_type"] == "food/drink"
    assert cand["iptc_city"] == "New Orleans"
    assert cand["iptc_province_state"] == "Louisiana"
    assert cand["iptc_country_code"] == "US"
    assert cand["website_official"] == "https://antoines.com/"
    assert "food" in cand["category_tags"]
    assert cand["cost_tier"] == "$$$"
    assert cand["indoor_outdoor"] == "Indoor"
    assert cand["physical_effort"] == "paved walk"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_extract_and_check_location_not_detected():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Candidate with generic unresolvable name and no address or coordinates
    mock_candidate = POIExtractionCandidate(
        name="Scenic Point of Interest",
        poi_type="site to see",
        search_address_query="",
        iptc_city=None,
        iptc_province_state=None,
        iptc_country_code=None,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_db.scalars.return_value = mock_scalars

    with patch("app.main.extract_candidate_from_text", return_value=mock_candidate), \
         patch("app.main.geocode_query", return_value=(0.0, 0.0, "Unknown", {})), \
         patch("app.main.check_spatial_collision", return_value=(CollisionStatus.UNIQUE_LOCATION, None, None)):



        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/extract-and-check",
                json={
                    "selected_text": "",
                    "page_title": "Google Search",
                    "page_url": "https://www.google.com/search?q=something",
                },
                headers={
                    "traceparent": "00-22222222222222222222222222222222-3333333333333333-01",
                    "X-Source": "extension",
                    "X-Destination": "backend",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["location_detected"] is False
    assert data["latitude"] is None
    assert data["longitude"] is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_pois_with_filters():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    fake_poi_row = {
        "id": uuid.uuid4(),
        "name": "Glacier Point",
        "name_aliases": ["Glacier Point View"],
        "poi_type": "photo location",
        "personal_rating": 5,
        "description": "Overlook above Yosemite Valley",
        "category_tags": ["viewpoint", "yosemite"],
        "visited": False,
        "visit_date": None,
        "geofence_radius_ft": 500,
        "parent_poi_id": None,
        "physical_effort": "paved walk",
        "booking_lead_time": "walk-in ok",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "1-2 hours",
        "cost_tier": "Free",
        "hours_seasonality": "Summer/Fall",
        "best_time_to_visit": "Sunset",
        "website_official": "https://nps.gov/yose",
        "phone_number": "123-456-7890",
        "primary_image_url": "https://example.com/glacier.jpg",
        "source_url": "https://example.com/page",
        "source_type": "web",
        "iptc_city": "Yosemite Village",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
        "created_at": datetime.now(),
        "latitude": 37.728,
        "longitude": -119.573,
        "list_ids": [uuid.uuid4()],
    }

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [fake_poi_row]
    mock_exec_res = MagicMock()
    mock_exec_res.mappings.return_value = mock_mappings
    mock_db.execute.return_value = mock_exec_res

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test with multiple query filter combinations
        response = await client.get(
            "/api/v1/pois",
            params={
                "city": "Yosemite",
                "state": "California",
                "country": "US",
                "tag": "viewpoint",
                "lat": 37.728,
                "lng": -119.573,
                "radius_miles": 10,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Glacier Point"
    assert data[0]["iptc_city"] == "Yosemite Village"
    assert data[0]["latitude"] == 37.728
    assert "viewpoint" in data[0]["category_tags"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_pois_with_bounding_box_filter():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    fake_poi_row = {
        "id": uuid.uuid4(),
        "name": "Cloud Gate (The Bean)",
        "name_aliases": ["The Bean"],
        "poi_type": "site-to-see",
        "personal_rating": 5,
        "description": "Iconic reflective sculpture in Millennium Park, Chicago.",
        "category_tags": ["architecture", "scenic"],
        "visited": True,
        "visit_date": None,
        "geofence_radius_ft": 500,
        "parent_poi_id": None,
        "physical_effort": "easy walk",
        "booking_lead_time": "none",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "30 mins",
        "cost_tier": "Free",
        "hours_seasonality": "All Year",
        "best_time_to_visit": "Morning",
        "website_official": "https://chicago.gov",
        "phone_number": "",
        "primary_image_url": "https://example.com/bean.jpg",
        "source_url": "https://example.com/chicago",
        "source_type": "web",
        "iptc_city": "Chicago",
        "iptc_province_state": "Illinois",
        "iptc_country_code": "US",
        "created_at": datetime.now(),
        "latitude": 41.8827,
        "longitude": -87.6233,
        "list_ids": [],
    }

    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [fake_poi_row]
    mock_exec_res = MagicMock()
    mock_exec_res.mappings.return_value = mock_mappings
    mock_db.execute.return_value = mock_exec_res

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/pois",
            params={
                "min_lat": 41.80,
                "max_lat": 41.95,
                "min_lng": -87.70,
                "max_lng": -87.60,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Cloud Gate (The Bean)"
    assert data[0]["iptc_city"] == "Chicago"
    assert data[0]["latitude"] == 41.8827

    executed_call = mock_db.execute.call_args
    sql_text = str(executed_call[0][0])
    assert "ST_MakeEnvelope" in sql_text
    assert "min_lng" in executed_call[0][1]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_and_delete_poi():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi_id = uuid.uuid4()
    fake_poi_row = {
        "id": poi_id,
        "name": "Half Dome",
        "name_aliases": [],
        "poi_type": "experience",
        "personal_rating": 5,
        "description": "Iconic granite dome hike.",
        "category_tags": ["hiking", "summit"],
        "visited": False,
        "visit_date": None,
        "geofence_radius_ft": 500,
        "parent_poi_id": None,
        "physical_effort": "strenuous",
        "booking_lead_time": "permit lottery",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "full day",
        "cost_tier": "$$",
        "hours_seasonality": "Cables up May-Oct",
        "best_time_to_visit": "Early morning",
        "website_official": "https://nps.gov/yose",
        "phone_number": None,
        "primary_image_url": None,
        "source_url": "https://example.com/halfdome",
        "source_type": "web",
        "iptc_city": "Yosemite",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
        "created_at": datetime.now(),
        "latitude": 37.746,
        "longitude": -119.533,
        "list_ids": [],
    }

    mock_mappings = MagicMock()
    mock_mappings.first.return_value = fake_poi_row
    mock_exec_res = MagicMock()
    mock_exec_res.mappings.return_value = mock_mappings
    mock_db.execute.return_value = mock_exec_res

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get POI
        get_resp = await client.get(f"/api/v1/pois/{poi_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Half Dome"

        # 2. Delete POI
        mock_poi_obj = MagicMock()
        mock_db.scalar.return_value = mock_poi_obj
        del_resp = await client.delete(f"/api/v1/pois/{poi_id}")
        assert del_resp.status_code == 204
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_poi_source_type_default_and_update():
    """Verifies that creating a POI defaults source_type to 'web', and update_poi updates source_type."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create with default source_type
        create_res = await client.post(
            "/api/v1/pois",
            json={
                "name": "Bixby Creek Bridge",
                "poi_type": "site to see",
                "latitude": 36.3714,
                "longitude": -121.9018,
                "source_url": "https://en.wikipedia.org/wiki/Bixby_Creek_Bridge",
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        assert data["name"] == "Bixby Creek Bridge"
        assert data["source_type"] == "web"
        assert data["source_url"] == "https://en.wikipedia.org/wiki/Bixby_Creek_Bridge"

        # 2. Update source_type
        poi_id = data["id"]
        mock_poi_obj = MagicMock()
        mock_poi_obj.id = uuid.UUID(poi_id)
        mock_poi_obj.user_id = TEST_USER.id
        mock_poi_obj.source_type = "web"
        mock_db.scalar.return_value = mock_poi_obj

        fake_updated_row = {
            "id": uuid.UUID(poi_id),
            "name": "Bixby Creek Bridge",
            "name_aliases": [],
            "poi_type": "site to see",
            "personal_rating": None,
            "description": None,
            "category_tags": [],
            "visited": False,
            "visit_date": None,
            "visit_dates": [],
            "latitude": 36.3714,
            "longitude": -121.9018,
            "geofence_radius_ft": 500,
            "parent_poi_id": None,
            "physical_effort": None,
            "booking_lead_time": None,
            "indoor_outdoor": None,
            "estimated_duration": None,
            "cost_tier": None,
            "hours_seasonality": None,
            "best_time_to_visit": None,
            "website_official": None,
            "phone_number": None,
            "primary_image_url": None,
            "source_url": "https://en.wikipedia.org/wiki/Bixby_Creek_Bridge",
            "source_type": "photo",
            "iptc_city": None,
            "iptc_province_state": None,
            "iptc_country_code": None,
            "created_at": datetime.now(),
            "list_ids": [],
        }
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = fake_updated_row
        mock_exec_res = MagicMock()
        mock_exec_res.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_exec_res

        update_res = await client.put(
            f"/api/v1/pois/{poi_id}",
            json={"source_type": "photo"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["source_type"] == "photo"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_delete_pois():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1 = MagicMock(id=uuid.uuid4(), user_id=TEST_USER.id)
    poi2 = MagicMock(id=uuid.uuid4(), user_id=TEST_USER.id)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [poi1, poi2]
    mock_db.scalars.return_value = mock_scalars

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pois/bulk-delete",
            json={"poi_ids": [str(poi1.id), str(poi2.id)]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["affected_count"] == 2
    assert mock_db.delete.call_count == 2
    mock_db.commit.assert_awaited_once()

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_update_pois():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1 = MagicMock(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        category_tags=["old_tag", "keep_me"],
        iptc_city="Old City",
        iptc_province_state=None,
        iptc_country_code=None,
    )
    poi2 = MagicMock(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        category_tags=["old_tag"],
        iptc_city="Old City",
        iptc_province_state=None,
        iptc_country_code=None,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [poi1, poi2]
    mock_db.scalars.return_value = mock_scalars

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pois/bulk-update",
            json={
                "poi_ids": [str(poi1.id), str(poi2.id)],
                "add_tags": ["new_tag"],
                "remove_tags": ["old_tag"],
                "iptc_city": "San Francisco",
                "iptc_province_state": "California",
                "iptc_country_code": "US",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["affected_count"] == 2

    assert "new_tag" in poi1.category_tags
    assert "old_tag" not in poi1.category_tags
    assert "keep_me" in poi1.category_tags
    assert poi1.iptc_city == "San Francisco"
    assert poi1.iptc_province_state == "California"
    assert poi1.iptc_country_code == "US"

    mock_db.commit.assert_awaited_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_poi_without_location():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pois",
            json={
                "name": "Dream Overlook (Location Unknown)",
                "poi_type": "experience",
                "description": "Captured from an article without clear GPS or address.",
                "source_url": "https://example.com/dream-overlook",
                "source_type": "web",
                "latitude": None,
                "longitude": None,
            },
            headers={
                "traceparent": "00-33333333333333333333333333333333-4444444444444444-01",
                "X-Source": "extension",
                "X-Destination": "backend",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dream Overlook (Location Unknown)"
    assert data["latitude"] is None
    assert data["longitude"] is None

    # Verify POI was added to session with location=None
    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.location is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_manual_poi():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pois",
            json={
                "name": "Secret Vista Viewpoint",
                "poi_type": "viewpoint",
                "personal_rating": 5,
                "description": "Discovered on afternoon hike.",
                "source_type": "manual",
                "source_url": "",
                "latitude": 37.8199,
                "longitude": -122.4783,
                "category_tags": ["sunset", "scenic"],
            },
            headers={
                "traceparent": "00-44444444444444444444444444444444-5555555555555555-01",
                "X-Source": "extension",
                "X-Destination": "backend",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Secret Vista Viewpoint"
    assert data["source_type"] == "manual"
    assert data["personal_rating"] == 5

    added_obj = mock_db.add.call_args[0][0]
    assert added_obj.name == "Secret Vista Viewpoint"
    assert added_obj.source_type == "manual"
    assert added_obj.source_url == ""
    assert "SRID=4326;POINT(-122.4783 37.8199)" in added_obj.location

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_pois_has_location_filter():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test with has_location=true
        res_with = await client.get("/api/v1/pois?has_location=true")
        assert res_with.status_code == 200
        sql_with = str(mock_db.execute.call_args[0][0])
        assert "p.location IS NOT NULL" in sql_with

        # Test with has_location=false
        res_without = await client.get("/api/v1/pois?has_location=false")
        assert res_without.status_code == 200
        sql_without = str(mock_db.execute.call_args[0][0])
        assert "p.location IS NULL" in sql_without

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_pois_visited_status_filter():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Visited
        res_v = await client.get("/api/v1/pois?visited_status=visited")
        assert res_v.status_code == 200
        sql_v = str(mock_db.execute.call_args[0][0])
        assert "p.visit_date IS NOT NULL" in sql_v

        # 2. Not Visited
        res_nv = await client.get("/api/v1/pois?visited_status=not_visited")
        assert res_nv.status_code == 200
        sql_nv = str(mock_db.execute.call_args[0][0])
        assert "p.visit_date IS NULL" in sql_nv

        # 3. To See
        res_ts = await client.get("/api/v1/pois?visited_status=to_see")
        assert res_ts.status_code == 200
        sql_ts = str(mock_db.execute.call_args[0][0])
        assert "p.visit_again IS TRUE" in sql_ts

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_poi_clear_location():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    existing_poi = MagicMock()
    existing_poi.id = uuid.uuid4()
    existing_poi.user_id = TEST_USER.id
    existing_poi.location = "SRID=4326;POINT(-111.51 36.87)"
    mock_db.scalar.return_value = existing_poi

    # Mock get_poi return mapping
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = {
        "id": existing_poi.id,
        "name": "Updated POI",
        "name_aliases": [],
        "poi_type": "site to see",
        "personal_rating": 3,
        "description": "Cleared location",
        "category_tags": [],
        "visited": False,
        "visit_date": None,
        "visit_dates": [],
        "geofence_radius_ft": 500,
        "parent_poi_id": None,
        "physical_effort": None,
        "booking_lead_time": None,
        "indoor_outdoor": None,
        "estimated_duration": None,
        "cost_tier": None,
        "hours_seasonality": None,
        "best_time_to_visit": None,
        "website_official": None,
        "phone_number": None,
        "primary_image_url": None,
        "source_url": "https://example.com",
        "source_type": "web",
        "iptc_city": None,
        "iptc_province_state": None,
        "iptc_country_code": None,
        "created_at": datetime.now(),
        "latitude": None,
        "longitude": None,
        "list_ids": [],
    }
    mock_db.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            f"/api/v1/pois/{existing_poi.id}",
            json={
                "clear_location": True,
            },
        )

    assert response.status_code == 200
    assert existing_poi.location is None
    data = response.json()
    assert data["latitude"] is None
    assert data["longitude"] is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_update_pois_coordinates_and_clear():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1 = MagicMock(id=uuid.uuid4(), user_id=TEST_USER.id, location=None)
    poi2 = MagicMock(id=uuid.uuid4(), user_id=TEST_USER.id, location="SRID=4326;POINT(-122 37)")

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [poi1]
    mock_db.scalars.return_value = mock_scalars

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test adding coordinates to unlocated POI
        res_set = await client.post(
            "/api/v1/pois/bulk-update",
            json={
                "poi_ids": [str(poi1.id)],
                "latitude": 41.8781,
                "longitude": -87.6298,
            },
        )
        assert res_set.status_code == 200
        assert poi1.location == "SRID=4326;POINT(-87.6298 41.8781)"

        # Test clearing coordinates
        mock_scalars.all.return_value = [poi2]
        res_clear = await client.post(
            "/api/v1/pois/bulk-update",
            json={
                "poi_ids": [str(poi2.id)],
                "clear_location": True,
            },
        )
        assert res_clear.status_code == 200
        assert poi2.location is None

        # Test updating ONLY city on a POI that has location (location must be preserved)
        poi3 = MagicMock(
            id=uuid.uuid4(),
            user_id=TEST_USER.id,
            name="Golden Gate Bridge",
            location="SRID=4326;POINT(-122.4783 37.8199)",
            iptc_city="Old City",
        )
        mock_scalars.all.return_value = [poi3]
        res_city_only = await client.post(
            "/api/v1/pois/bulk-update",
            json={
                "poi_ids": [str(poi3.id)],
                "iptc_city": "San Francisco",
            },
        )
        assert res_city_only.status_code == 200
        assert poi3.iptc_city == "San Francisco"
        assert poi3.location == "SRID=4326;POINT(-122.4783 37.8199)"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_pois_country_mapping():
    """Verify that querying pois with country name (e.g. 'China' or 'china') maps to 'CN' in SQL parameters."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/pois?country=China")
        assert res.status_code == 200

        call_args = mock_db.execute.call_args
        sql_text = str(call_args[0][0])
        params = call_args[0][1]
        assert "p.iptc_country_code = :country_exact" in sql_text
        assert params["country_exact"] == "CN"
        assert params["country_val"] == "%CN%"

        # Test lowercase 'china'
        res2 = await client.get("/api/v1/pois?country=china")
        assert res2.status_code == 200
        call_args2 = mock_db.execute.call_args
        params2 = call_args2[0][1]
        assert params2["country_exact"] == "CN"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_reverse_geocode():
    """Verify reverse-geocode endpoint calls reverse_geocode service and returns parsed address components."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    fake_reverse_response = {
        "address": {
            "village": "Curry Village",
            "county": "Mariposa County",
            "state": "California",
            "country_code": "us",
            "country": "United States",
            "postcode": "95389",
            "road": "Glacier Point Road",
        }
    }

    with patch("app.main.reverse_geocode", new_callable=AsyncMock) as mock_rev:
        mock_rev.return_value = (
            "Glacier Point Road, Curry Village, Mariposa County, California, 95389, USA",
            fake_reverse_response,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/reverse-geocode?latitude=37.7304&longitude=-119.5736")
            assert res.status_code == 200
            data = res.json()
            assert data["city"] == "Curry Village"
            assert data["state"] == "California"
            assert data["country_code"] == "US"
            assert data["country_name"] == "United States"
            assert data["postcode"] == "95389"
            assert data["sublocation"] == "Glacier Point Road"
            assert data["display_name"] == "Glacier Point Road, Curry Village, Mariposa County, California, 95389, USA"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_geocode_forward():
    """Verify forward geocoding query endpoint returns coordinates and parsed address components."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    fake_geo_response = {
        "address": {
            "village": "Yosemite Village",
            "state": "California",
            "country_code": "us",
            "country": "United States",
        }
    }

    with patch("app.main.geocode_query", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = (
            37.7304,
            -119.5736,
            "Glacier Point, Yosemite, CA",
            fake_geo_response,
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/geocode?query=Glacier%20Point")
            assert res.status_code == 200
            data = res.json()
            assert data["latitude"] == 37.7304
            assert data["longitude"] == -119.5736
            assert data["city"] == "Yosemite Village"
            assert data["state"] == "California"
            assert data["country_code"] == "US"
            assert data["country_name"] == "United States"
            assert data["display_name"] == "Glacier Point, Yosemite, CA"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_poi_visit_again_create_and_update():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create POI with visit_again = True
        create_res = await client.post(
            "/api/v1/pois",
            json={
                "name": "Crater Lake Overlook",
                "poi_type": "site to see",
                "visited": True,
                "visit_date": "2025-08-10",
                "visit_again": True,
                "source_url": "https://example.com/crater-lake",
            },
        )
        assert create_res.status_code == 201
        created_data = create_res.json()
        assert created_data["visit_again"] is True

        poi_id = created_data["id"]

        # 2. Mock DB for update
        mock_poi_obj = MagicMock()
        mock_poi_obj.id = uuid.UUID(poi_id)
        mock_poi_obj.user_id = TEST_USER.id
        mock_poi_obj.visit_again = True
        mock_db.scalar.return_value = mock_poi_obj

        fake_updated_row = {
            "id": uuid.UUID(poi_id),
            "name": "Crater Lake Overlook",
            "name_aliases": [],
            "poi_type": "site to see",
            "personal_rating": None,
            "description": None,
            "category_tags": [],
            "visited": True,
            "visit_date": "2025-08-10",
            "visit_dates": [],
            "visit_again": False,
            "latitude": None,
            "longitude": None,
            "geofence_radius_ft": 500,
            "parent_poi_id": None,
            "physical_effort": None,
            "booking_lead_time": None,
            "indoor_outdoor": None,
            "estimated_duration": None,
            "cost_tier": None,
            "hours_seasonality": None,
            "best_time_to_visit": None,
            "website_official": None,
            "phone_number": None,
            "primary_image_url": None,
            "source_url": "https://example.com/crater-lake",
            "source_type": "web",
            "iptc_city": None,
            "iptc_province_state": None,
            "iptc_country_code": None,
            "created_at": datetime.now(),
            "list_ids": [],
        }
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = fake_updated_row
        mock_exec_res = MagicMock()
        mock_exec_res.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_exec_res

        # 3. Update POI setting visit_again = False
        update_res = await client.put(
            f"/api/v1/pois/{poi_id}",
            json={"visit_again": False},
        )
        assert update_res.status_code == 200
        assert mock_poi_obj.visit_again is False
        assert update_res.json()["visit_again"] is False

    app.dependency_overrides.clear()







