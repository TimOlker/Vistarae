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
