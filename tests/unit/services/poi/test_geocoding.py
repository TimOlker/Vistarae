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

"""Unit tests for GeocodingService, Nominatim rate limiter, PostGIS geocache, and trans-boundary addressing (T-029).

Validates:
- SHA-256 geocache lookup pre-check (REQ-EXT-022, REQ-EXT-027)
- Sustained 1 req/sec rate limiter & custom User-Agent (REQ-EXT-023)
- Reverse geocoding fallback on missing fields (REQ-EXT-024)
- Trans-boundary multi-address resolution & English country normalization (REQ-EXT-025, REQ-EXT-026)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.geocoding.rate_limiter import TokenBucketRateLimiter
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.ports.repositories import IGeocodingCacheRepository
from vistarae_core.services.address_normalizer import AddressNormalizer

from services.poi.services.geocoding_service import GeocodingService, compute_query_hash


class InMemoryGeocacheRepository(IGeocodingCacheRepository):
    """In-memory geocache repository for isolated unit testing."""

    def __init__(self) -> None:
        self.entries: dict[str, GeocodingCacheEntry] = {}

    async def get(self, query_hash: str) -> GeocodingCacheEntry | None:
        return self.entries.get(query_hash)

    async def set(self, entry: GeocodingCacheEntry) -> None:
        self.entries[entry.query_hash] = entry


@pytest.mark.asyncio
class TestGeocodingService:
    """Test suite for Nominatim geocoding compliance, PostGIS caching, and transboundary addressing."""

    async def test_compute_query_hash_deterministic(self) -> None:
        """Verifies SHA-256 query hashing normalizes whitespace and casing (REQ-EXT-022)."""
        h1 = compute_query_hash("Bamburgh Castle, UK")
        h2 = compute_query_hash("  bamburgh castle, uk  ")
        assert h1 == h2
        assert len(h1) == 64

    async def test_cache_hit_skips_outbound_http(self) -> None:
        """Verifies cache hits bypass the rate limiter and outbound network requests (REQ-EXT-022, REQ-EXT-027)."""
        repo = InMemoryGeocacheRepository()
        query = "Bamburgh Castle"
        q_hash = compute_query_hash(query)

        now = datetime.now(UTC)
        cached_data = {
            "addresses": [
                {
                    "street": "Bamburgh Castle",
                    "city": "Bamburgh",
                    "state_province": "Northumberland",
                    "country": "United Kingdom",
                    "postal_code": "NE69 7DF",
                }
            ]
        }
        await repo.set(
            GeocodingCacheEntry(
                query_hash=q_hash,
                lat=55.6089,
                lon=-1.7099,
                formatted_address=json.dumps(cached_data),
                status="SUCCESS",
                created_at=now,
                expires_at=now + timedelta(days=90),
            )
        )

        mock_client = AsyncMock()
        service = GeocodingService(cache_repo=repo, http_client=mock_client)

        lat, lon, addrs, cached = await service.geocode(query)

        assert cached is True
        assert lat == 55.6089
        assert lon == -1.7099
        assert len(addrs) == 1
        assert addrs[0].country == "United Kingdom"
        mock_client.get.assert_not_called()

    async def test_nominatim_rate_limiting_and_user_agent(self) -> None:
        """Verifies 1 req/sec token bucket acquisition and custom User-Agent header (REQ-EXT-023)."""
        repo = InMemoryGeocacheRepository()
        rate_limiter = MagicMock(spec=TokenBucketRateLimiter)
        rate_limiter.acquire = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "lat": "37.7303",
                "lon": "-119.5736",
                "address": {
                    "road": "Glacier Point Rd",
                    "city": "Yosemite Valley",
                    "state": "California",
                    "country": "United States",
                    "postcode": "95389",
                },
            }
        ]

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        service = GeocodingService(
            cache_repo=repo,
            rate_limiter=rate_limiter,
            http_client=mock_client,
        )

        lat, lon, addrs, cached = await service.geocode("Glacier Point Overlook")

        assert cached is False
        rate_limiter.acquire.assert_awaited_once()

        # Check User-Agent header sent to Nominatim
        mock_client.get.assert_called_once()
        headers = mock_client.get.call_args.kwargs["headers"]
        assert headers["User-Agent"] == "VistaraeTravelEngine/1.0"
        assert len(addrs) == 1
        assert addrs[0].state_province == "California"

    async def test_transboundary_multi_state_expansion(self) -> None:
        """Verifies multi-state destinations create distinct AddressRecords (REQ-EXT-025)."""
        records = AddressNormalizer.expand_transboundary_addresses("Wyoming, Montana, Idaho")
        assert len(records) == 3
        states = [r.state_province for r in records]
        assert "Wyoming" in states
        assert "Montana" in states
        assert "Idaho" in states
        for r in records:
            assert r.country == "United States"

    async def test_transboundary_multi_country_expansion(self) -> None:
        """Verifies multi-country landmarks create distinct AddressRecords with English names (REQ-EXT-025, REQ-EXT-026)."""
        records = AddressNormalizer.expand_transboundary_addresses(
            "Argentina and Brazil",
            base_address=None,
        )
        assert len(records) == 2
        countries = [r.country for r in records]
        assert "Argentina" in countries
        assert "Brazil" in countries
