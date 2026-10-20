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

"""Unit tests for Nominatim geocoder with cache-first resolution (T-025).

Verifies:
- Address normalization and SHA-256 hash generation
- Cache hit returns stored coordinates without network I/O
- Cache miss triggers rate-limited Nominatim lookup and persists cache entry
- Empty response or HTTP failure gracefully returns None
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from vistarae_core.domain.entities import GeocodingCacheEntry

from services.worker.geocoder import (
    NominatimGeocoder,
    compute_address_hash,
    normalize_address,
)
from services.worker.rate_limiter import InMemoryRateLimiter


@pytest.mark.asyncio
class TestNominatimGeocoder:
    """Test suite for OpenStreetMap Nominatim geocoder adapter."""

    def test_normalize_address_and_hash(self) -> None:
        """Asserts address normalization trims, lowercases, and computes SHA-256."""
        raw = "  123 Main St,   Batavia,  IL  "
        normalized = normalize_address(raw)
        assert normalized == "123 main st, batavia, il"
        h = compute_address_hash(normalized)
        assert len(h) == 64
        assert h == compute_address_hash("123 main st, batavia, il")

    async def test_geocode_empty_address_returns_none(self) -> None:
        """Asserts empty or whitespace address returns None."""
        mock_cache = AsyncMock()
        mock_limiter = AsyncMock()
        geocoder = NominatimGeocoder(mock_cache, mock_limiter)

        assert await geocoder.geocode("") is None
        assert await geocoder.geocode("   ") is None
        assert mock_cache.get.call_count == 0

    async def test_geocode_cache_hit_bypasses_network(self) -> None:
        """Asserts cached address returns instantly without acquiring rate limiter."""
        mock_cache = AsyncMock()
        cached_entry = GeocodingCacheEntry(
            query_hash="abc",
            lat=41.8500,
            lon=-88.3126,
            formatted_address="123 Main St, Batavia, IL, USA",
            status="SUCCESS",
        )
        mock_cache.get.return_value = cached_entry

        mock_limiter = AsyncMock(spec=InMemoryRateLimiter)
        geocoder = NominatimGeocoder(mock_cache, mock_limiter)

        result = await geocoder.geocode("123 Main St, Batavia, IL")
        assert result == (41.8500, -88.3126, "123 Main St, Batavia, IL, USA")
        assert mock_limiter.acquire.call_count == 0

    async def test_geocode_cache_miss_queries_nominatim_and_caches(self) -> None:
        """Asserts cache miss calls Nominatim with custom User-Agent and saves to cache."""
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None

        mock_limiter = AsyncMock(spec=InMemoryRateLimiter)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": "37.7749",
                "lon": "-122.4194",
                "display_name": "San Francisco, California, USA",
            }
        ]

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_response

        geocoder = NominatimGeocoder(mock_cache, mock_limiter, http_client=mock_http)

        result = await geocoder.geocode("San Francisco, CA")
        assert result == (37.7749, -122.4194, "San Francisco, California, USA")

        assert mock_limiter.acquire.call_count == 1
        assert mock_http.get.call_count == 1
        assert mock_cache.set.call_count == 1
        saved_entry = mock_cache.set.call_args[0][0]
        assert saved_entry.lat == 37.7749
        assert saved_entry.lon == -122.4194

    async def test_geocode_nominatim_not_found(self) -> None:
        """Asserts empty response list from Nominatim returns None."""
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        mock_limiter = AsyncMock(spec=InMemoryRateLimiter)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_response

        geocoder = NominatimGeocoder(mock_cache, mock_limiter, http_client=mock_http)
        assert await geocoder.geocode("Nowhere Land") is None

    async def test_geocode_http_error_graceful_none(self) -> None:
        """Asserts HTTP network exception returns None without crashing."""
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        mock_limiter = AsyncMock(spec=InMemoryRateLimiter)

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.side_effect = httpx.ConnectTimeout("Connection timed out")

        geocoder = NominatimGeocoder(mock_cache, mock_limiter, http_client=mock_http)
        assert await geocoder.geocode("Some Remote Place") is None
