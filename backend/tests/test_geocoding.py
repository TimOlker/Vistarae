"""Unit tests for Nominatim geocoding and local PostGIS geocache."""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from app.models import Geocache
from app.services.geocoding import compute_query_hash, geocode_query


def test_compute_query_hash_normalization():
    raw_query_1 = "  Glacier Point,   Yosemite National Park, CA  "
    raw_query_2 = "glacier point, yosemite national park, ca"
    hash_1 = compute_query_hash(raw_query_1)
    hash_2 = compute_query_hash(raw_query_2)

    assert hash_1 == hash_2
    assert len(hash_1) == 64
    assert hash_1 == hashlib.sha256(b"glacier point, yosemite national park, ca").hexdigest()


@pytest.mark.asyncio
async def test_geocode_geocache_hit():
    mock_db = AsyncMock()
    cached_entry = Geocache(
        query_hash="dummyhash",
        latitude=37.7304,
        longitude=-119.5736,
        display_name="Glacier Point, Yosemite, CA",
        raw_json={"place_id": 12345},
    )
    mock_db.scalar.return_value = cached_entry

    lat, lng, display_name, _ = await geocode_query("Glacier Point", mock_db)

    assert lat == 37.7304
    assert lng == -119.5736
    assert display_name == "Glacier Point, Yosemite, CA"
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_geocode_geocache_miss_and_store():
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None  # Cache miss

    fake_osm_response = [
        {
            "lat": "37.7304000",
            "lon": "-119.5736000",
            "display_name": "Glacier Point Overlook, California",
            "address": {
                "village": "Yosemite Village",
                "state": "California",
                "country_code": "us",
                "postcode": "95389",
            },
        }
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_osm_response
        mock_get.return_value = mock_resp

        lat, lng, display_name, raw = await geocode_query("Glacier Point", mock_db)

        assert lat == 37.7304
        assert lng == -119.5736
        assert "Glacier Point Overlook" in display_name
        assert raw["address"]["state"] == "California"

        # Verify entry added to database cache
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_reverse_geocode_hit_and_miss():
    mock_db = AsyncMock()
    # 1. Test cache hit
    cached_entry = Geocache(
        query_hash="dummyhash",
        latitude=37.7304,
        longitude=-119.5736,
        display_name="Glacier Point Road, Yosemite, CA",
        raw_json={
            "address": {"village": "Yosemite Village", "state": "California", "country_code": "us"}
        },
    )
    mock_db.scalar.return_value = cached_entry

    from app.services.geocoding import enrich_candidate_from_address, reverse_geocode

    display_name, raw = await reverse_geocode(37.7304, -119.5736, mock_db)
    assert display_name == "Glacier Point Road, Yosemite, CA"
    assert raw["address"]["village"] == "Yosemite Village"

    # 2. Test cache miss
    mock_db.scalar.return_value = None
    fake_reverse_response = {
        "display_name": "Glacier Point Road, Curry Village, Mariposa County, California, 95389, USA",
        "address": {
            "road": "Glacier Point Road",
            "village": "Curry Village",
            "county": "Mariposa County",
            "state": "California",
            "country_code": "us",
            "postcode": "95389",
            "country": "United States",
        },
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_reverse_response
        mock_get.return_value = mock_resp

        disp, res = await reverse_geocode(37.730412, -119.573645, mock_db)
        assert disp == fake_reverse_response["display_name"]
        assert res["address"]["state"] == "California"

    # 3. Test enrich_candidate_from_address
    from app.schemas.extraction import POIExtractionCandidate

    candidate = POIExtractionCandidate(
        name="Wilderness Viewpoint",
        poi_type="photo location",
        search_address_query="Wilderness Viewpoint",
        iptc_city=None,
        iptc_province_state=None,
        iptc_country_code=None,
    )
    enrich_candidate_from_address(candidate, fake_reverse_response)
    assert candidate.iptc_city == "Curry Village"
    assert candidate.iptc_province_state == "California"
    assert candidate.iptc_country_code == "US"
    assert candidate.iptc_zip_code == "95389"
    assert candidate.iptc_sublocation == "Glacier Point Road"


@pytest.mark.asyncio
async def test_geocode_google_plus_code():
    """Tests resolution of Google Plus Codes (Open Location Codes)."""
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None

    # Test full Plus Code
    lat, lng, disp, raw = await geocode_query("7GQJ8H92+5M4", mock_db)
    assert round(lat, 3) == 25.318
    assert round(lng, 3) == 32.552


def test_enrich_multinational_candidate_country_code():
    from app.schemas.ingestion import StandardizedCandidatePOI
    from app.services.geocoding import enrich_candidate_from_address

    cand = StandardizedCandidatePOI(
        name="Qhapaq Ñan, Andean Road System",
        iptc_country_code="AR",
        raw_data={"_allowed_country_codes": ["AR", "BO", "CL", "CO", "EC", "PE"]},
    )
    ecuador_geo = {
        "address": {
            "road": "Qhapaq Ñan",
            "village": "Juncal",
            "county": "Cañar",
            "state": "Cañar",
            "country_code": "ec",
            "country": "Ecuador",
        }
    }
    enrich_candidate_from_address(cand, ecuador_geo)
    assert cand.iptc_country_code == "EC"
    assert cand.iptc_city == "Juncal"
    assert cand.iptc_province_state == "Cañar"
    assert cand.iptc_world_region == "Ecuador"
