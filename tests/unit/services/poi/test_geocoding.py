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

"""Unit tests for GeocodingPort adapters, rate limiting, and SHA-256 caching (T-020).

Tests:
- TokenBucketRateLimiter: 1 rps sustained rate limiting, token replenishment
- SqlAlchemyGeocodingCacheRepository: query/coord hashing, cache get/set, cleanup_expired
- MapboxGeocodingAdapter: cache hit short-circuiting, timeout fallback, graceful reverse geocoding
- MockGeocodingAdapter: simulated success, timeout, and failure states
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from vistarae_core.adapters.db.tables import GeocodingCacheTable
from vistarae_core.adapters.geocoding.mapbox import MapboxGeocodingAdapter
from vistarae_core.adapters.geocoding.mock import MockGeocodingAdapter
from vistarae_core.adapters.geocoding.rate_limiter import TokenBucketRateLimiter
from vistarae_core.adapters.repositories.geocache_repo import (
    SqlAlchemyGeocodingCacheRepository,
    hash_coordinate_pair,
    hash_query_string,
)
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.domain.exceptions import GeocodingTimeoutError
from vistarae_core.domain.value_objects import EnrichmentStatus


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    @pytest.mark.asyncio
    async def test_initial_acquire_immediate(self) -> None:
        """First acquire completes without delay when bucket is full."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, capacity=1.0)
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_burst_throttling(self) -> None:
        """Subsequent acquire within interval sleeps appropriately."""
        limiter = TokenBucketRateLimiter(rate_per_second=20.0, capacity=1.0)
        await limiter.acquire()
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04


class TestGeocodingCacheRepository:
    """Tests for SqlAlchemyGeocodingCacheRepository."""

    def test_hashing_functions(self) -> None:
        """Asserts deterministic SHA-256 digests for queries and coordinates."""
        h1 = hash_query_string("  Yosemite   Valley ")
        h2 = hash_query_string("yosemite valley")
        assert h1 == h2
        assert len(h1) == 64

        c1 = hash_coordinate_pair(37.774929, -122.419416)
        c2 = hash_coordinate_pair(37.774931, -122.419424)
        assert c1 == c2  # Rounds to 5 decimal places

    @pytest.mark.asyncio
    async def test_cache_get_hit(self) -> None:
        """Asserts get returns entry on valid cache hit."""
        session = AsyncMock()
        row = MagicMock(spec=GeocodingCacheTable)
        row.query_hash = "abc" * 21 + "a"
        row.lat = 37.7749
        row.lon = -122.4194
        row.formatted_address = "San Francisco, CA"
        row.status = "SUCCESS"
        row.created_at = datetime.now(UTC)
        row.expires_at = datetime.now(UTC) + timedelta(days=90)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyGeocodingCacheRepository(session)
        entry = await repo.get(row.query_hash)

        assert entry is not None
        assert entry.formatted_address == "San Francisco, CA"

    @pytest.mark.asyncio
    async def test_cache_get_miss(self) -> None:
        """Asserts get returns None on miss or expired entry."""
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res

        repo = SqlAlchemyGeocodingCacheRepository(session)
        entry = await repo.get("nonexistent")
        assert entry is None

    @pytest.mark.asyncio
    async def test_cache_set_and_cleanup(self) -> None:
        """Asserts set flushes and cleanup_expired returns deleted rowcount."""
        session = AsyncMock()
        mock_delete_res = MagicMock()
        mock_delete_res.rowcount = 5
        session.execute.return_value = mock_delete_res

        repo = SqlAlchemyGeocodingCacheRepository(session)
        entry = GeocodingCacheEntry(
            query_hash="123" * 21 + "1",
            lat=38.0,
            lon=-120.0,
            formatted_address="Test",
            status="SUCCESS",
        )
        await repo.set(entry)
        assert session.flush.called

        deleted = await repo.cleanup_expired()
        assert deleted == 5


class TestMapboxGeocodingAdapter:
    """Tests for MapboxGeocodingAdapter."""

    @pytest.mark.asyncio
    async def test_forward_geocode_cache_hit(self) -> None:
        """Asserts cache hit avoids outbound HTTP requests entirely."""
        cache_repo = AsyncMock()
        cached_entry = GeocodingCacheEntry(
            query_hash=hash_query_string("Lake Tahoe"),
            lat=39.0968,
            lon=-120.0324,
            formatted_address="Lake Tahoe, CA, USA",
            status="SUCCESS",
        )
        cache_repo.get.return_value = cached_entry

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)
        res = await adapter.forward_geocode("Lake Tahoe")

        assert res.lat == 39.0968
        assert res.formatted_address == "Lake Tahoe, CA, USA"
        assert res.status == EnrichmentStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_forward_geocode_timeout_raises(self) -> None:
        """Asserts httpx timeout raises GeocodingTimeoutError."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo, timeout_seconds=0.01)

        with (
            patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")),
            pytest.raises(GeocodingTimeoutError),
        ):
            await adapter.forward_geocode("Timeout Place")

    @pytest.mark.asyncio
    async def test_forward_geocode_http_success(self) -> None:
        """Asserts forward geocoding with 200 OK writes to cache and returns SUCCESS."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [
                {
                    "geometry": {"coordinates": [-119.5383, 37.8651]},
                    "place_name": "Yosemite National Park, California, United States",
                    "context": [
                        {"id": "region.123", "text": "California"},
                        {"id": "country.456", "text": "United States"},
                    ],
                }
            ]
        }

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            res = await adapter.forward_geocode("Yosemite National Park")
            assert res.status == EnrichmentStatus.SUCCESS
            assert res.lat == 37.8651
            assert res.lon == -119.5383
            assert res.states == ["California"]
            assert res.countries == ["United States"]
            assert cache_repo.set.called

    @pytest.mark.asyncio
    async def test_forward_geocode_non_200_returns_failed(self) -> None:
        """Asserts non-200 HTTP response returns FAILED status."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            res = await adapter.forward_geocode("Unknown Place")
            assert res.status == EnrichmentStatus.FAILED

    @pytest.mark.asyncio
    async def test_reverse_geocode_cache_hit(self) -> None:
        """Asserts reverse geocode returns immediately on cache hit."""
        cache_repo = AsyncMock()
        cached_entry = GeocodingCacheEntry(
            query_hash=hash_coordinate_pair(37.8651, -119.5383),
            lat=37.8651,
            lon=-119.5383,
            formatted_address="Cached Place",
            status="SUCCESS",
        )
        cache_repo.get.return_value = cached_entry

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)
        res = await adapter.reverse_geocode(37.8651, -119.5383)
        assert res.formatted_address == "Cached Place"
        assert res.status == EnrichmentStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_reverse_geocode_http_success(self) -> None:
        """Asserts reverse geocoding 200 OK writes to cache and returns SUCCESS."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "features": [
                {
                    "place_name": "Yosemite Valley, CA",
                    "context": [
                        {"id": "region.1", "text": "California"},
                        {"id": "country.1", "text": "United States"},
                    ],
                }
            ]
        }

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            res = await adapter.reverse_geocode(37.7456, -119.5936)
            assert res.status == EnrichmentStatus.SUCCESS
            assert res.formatted_address == "Yosemite Valley, CA"
            assert cache_repo.set.called

    @pytest.mark.asyncio
    async def test_reverse_geocode_fallback_partial(self) -> None:
        """Asserts reverse geocoding failure falls back to user coords with PARTIAL status."""
        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        adapter = MapboxGeocodingAdapter(cache_repo=cache_repo)

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("error")):
            res = await adapter.reverse_geocode(37.5, -119.5)
            assert res.lat == 37.5
            assert res.lon == -119.5
            assert res.status == EnrichmentStatus.PARTIAL


class TestMockGeocodingAdapter:
    """Tests for MockGeocodingAdapter."""

    @pytest.mark.asyncio
    async def test_mock_success(self) -> None:
        """Asserts mock adapter provides realistic results and tracks calls."""
        mock = MockGeocodingAdapter()
        fwd = await mock.forward_geocode("Yosemite")
        assert fwd.status == EnrichmentStatus.SUCCESS
        assert mock.forward_call_count == 1

        rev = await mock.reverse_geocode(37.8651, -119.5383)
        assert rev.status == EnrichmentStatus.SUCCESS
        assert mock.reverse_call_count == 1

    @pytest.mark.asyncio
    async def test_mock_timeout_and_fail(self) -> None:
        """Asserts mock flags trigger timeout error and failure status."""
        timeout_mock = MockGeocodingAdapter(should_timeout=True)
        with pytest.raises(GeocodingTimeoutError):
            await timeout_mock.forward_geocode("Zion")

        rev_timeout = await timeout_mock.reverse_geocode(37.0, -119.0)
        assert rev_timeout.status == EnrichmentStatus.PARTIAL

        fail_mock = MockGeocodingAdapter(should_fail=True)
        fail_res = await fail_mock.forward_geocode("Nowhere")
        assert fail_res.status == EnrichmentStatus.FAILED


class TestReverseGeocodeServiceAndRoute:
    """Tests for ReverseGeocodeService and GET /api/pois/geocode/reverse (T-016)."""

    @pytest.mark.asyncio
    async def test_reverse_geocode_service_cache_hit(self) -> None:
        """Asserts ReverseGeocodeService returns cached result when present."""
        import json

        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        payload = {
            "street": "9035 Village Dr",
            "city": "Yosemite Valley",
            "state_province": "California",
            "country": "United States",
            "postal_code": "95389",
        }
        cached_entry = GeocodingCacheEntry(
            query_hash="abc",
            lat=37.8651,
            lon=-119.5383,
            formatted_address=json.dumps(payload),
            status="SUCCESS",
        )
        cache_repo.get.return_value = cached_entry

        service = ReverseGeocodeService(cache_repo=cache_repo)
        resp = await service.reverse_geocode(37.8651, -119.5383)
        assert resp.cached is True
        assert resp.country == "United States"
        assert resp.state_province == "California"
        assert resp.city == "Yosemite Valley"

    @pytest.mark.asyncio
    async def test_reverse_geocode_service_http_success(self) -> None:
        """Asserts Nominatim call on cache miss normalizes English country and writes to cache."""
        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "address": {
                "road": "Hauptstrasse 10",
                "city": "Berlin",
                "state": "Berlin",
                "country": "Deutschland",  # German endonym
                "postcode": "10115",
            }
        }
        mock_client.get.return_value = mock_resp

        service = ReverseGeocodeService(cache_repo=cache_repo, http_client=mock_client)
        resp = await service.reverse_geocode(52.5200, 13.4050)
        assert resp.cached is False
        assert resp.country == "Germany"  # Normalized from Deutschland
        assert resp.city == "Berlin"
        assert resp.street == "Hauptstrasse 10"
        assert cache_repo.set.called

    def test_reverse_geocode_endpoint_success(self) -> None:
        """Asserts GET /api/pois/geocode/reverse returns 200 with ReverseGeocodeResponse."""
        import json
        from unittest.mock import MagicMock
        from uuid import UUID

        from fastapi.testclient import TestClient
        from vistarae_core.adapters.db.session import get_db_session
        from vistarae_core.domain.entities import User

        from services.poi.dependencies import get_current_user
        from services.poi.main import app

        current_user = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            cognito_sub="sub-traveler-1",
            email="traveler@example.com",
            full_name="Atlas Voyager",
            is_active=True,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        payload = {
            "street": "9035 Village Dr",
            "city": "Yosemite Valley",
            "state_province": "California",
            "country": "United States",
            "postal_code": "95389",
        }
        mock_cached_row = MagicMock()
        mock_cached_row.query_hash = "h1"
        mock_cached_row.lat = 37.8651
        mock_cached_row.lon = -119.5383
        mock_cached_row.formatted_address = json.dumps(payload)
        mock_cached_row.status = "SUCCESS"
        mock_cached_row.created_at = None
        mock_cached_row.expires_at = None
        mock_result.scalar_one_or_none.return_value = mock_cached_row
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_current_user] = lambda: current_user
        app.dependency_overrides[get_db_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.get("/api/pois/geocode/reverse?lat=37.8651&lng=-119.5383")
            assert resp.status_code == 200
            data = resp.json()
            assert data["cached"] is True
            assert data["country"] == "United States"
            assert data["city"] == "Yosemite Valley"
        finally:
            app.dependency_overrides.clear()

    def test_reverse_geocode_endpoint_invalid_lat_returns_422(self) -> None:
        """Asserts latitude > 90 returns 422 validation problem."""
        from uuid import UUID

        from fastapi.testclient import TestClient
        from vistarae_core.domain.entities import User

        from services.poi.dependencies import get_current_user
        from services.poi.main import app

        current_user = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            cognito_sub="sub-traveler-1",
            email="traveler@example.com",
            full_name="Atlas Voyager",
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: current_user

        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.get("/api/pois/geocode/reverse?lat=95.0&lng=-119.5383")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_reverse_geocode_legacy_text_cache(self) -> None:
        """Asserts legacy plain text formatted_address in cache is handled gracefully."""
        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        cached_entry = GeocodingCacheEntry(
            query_hash="def",
            lat=48.8584,
            lon=2.2945,
            formatted_address="France",
            status="SUCCESS",
        )
        cache_repo.get.return_value = cached_entry

        service = ReverseGeocodeService(cache_repo=cache_repo)
        resp = await service.reverse_geocode(48.8584, 2.2945)
        assert resp.cached is True
        assert resp.country == "France"

    @pytest.mark.asyncio
    async def test_reverse_geocode_fallback_on_exception(self) -> None:
        """Asserts upstream exception falls back to empty fields."""
        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectTimeout("Timeout")

        service = ReverseGeocodeService(cache_repo=cache_repo, http_client=mock_client)
        resp = await service.reverse_geocode(0.0, 0.0)
        assert resp.cached is False
        assert resp.country == "Unknown"

    @pytest.mark.asyncio
    async def test_reverse_geocode_rate_limited_429(self) -> None:
        """Asserts 429 status logs warning and returns fallback response."""
        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client.get.return_value = mock_resp

        service = ReverseGeocodeService(cache_repo=cache_repo, http_client=mock_client)
        resp = await service.reverse_geocode(10.0, 10.0)
        assert resp.cached is False
        assert resp.country == "Unknown"

    @pytest.mark.asyncio
    async def test_reverse_geocode_default_client_path(self) -> None:
        """Asserts client instantiation when client is None."""
        from unittest.mock import patch

        from services.poi.services.geocode_service import ReverseGeocodeService

        cache_repo = AsyncMock()
        cache_repo.get.return_value = None

        service = ReverseGeocodeService(cache_repo=cache_repo, http_client=None)
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            resp = await service.reverse_geocode(20.0, 20.0)
            assert resp.cached is False
            assert resp.country == "Unknown"
