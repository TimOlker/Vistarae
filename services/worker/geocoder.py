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

"""OpenStreetMap Nominatim geocoding client with cache-first resolution (T-025).

Enforces:
- Checking geocoding_cache table (SHA-256 of normalized address) before any HTTP request (REQ-WORKER-007)
- Sustained 1.0 req/sec pacing for cache misses via InMemoryRateLimiter (REQ-WORKER-006)
- Custom User-Agent: VistaraeTravelEngine/1.0 (REQ-WORKER-004)
- 90-day TTL persistence on cache entries (REQ-WORKER-008)
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.ports.repositories import IGeocodingCacheRepository

from services.worker.rate_limiter import InMemoryRateLimiter

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "VistaraeTravelEngine/1.0"


def normalize_address(address: str) -> str:
    """Normalizes address string for deterministic cache hashing.

    Args:
        address: Raw address text.

    Returns:
        Lowercased, trimmed, whitespace-normalized address.
    """
    return " ".join(address.lower().strip().split())


def compute_address_hash(normalized_address: str) -> str:
    """Computes SHA-256 hash of normalized address.

    Args:
        normalized_address: Normalized address string.

    Returns:
        64-character hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(normalized_address.encode("utf-8")).hexdigest()


class NominatimGeocoder:
    """OpenStreetMap Nominatim client adhering strictly to usage policies."""

    def __init__(
        self,
        cache_repo: IGeocodingCacheRepository,
        rate_limiter: InMemoryRateLimiter,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initializes geocoder.

        Args:
            cache_repo: Geocoding cache repository port.
            rate_limiter: Process-wide 1.0 req/sec rate limiter.
            http_client: Optional pre-configured HTTP client for tests.
        """
        self._cache_repo = cache_repo
        self._rate_limiter = rate_limiter
        self._http_client = http_client

    async def geocode(
        self,
        raw_address: str,
    ) -> tuple[float, float, str] | None:
        """Resolves raw address to coordinates and canonical address.

        Args:
            raw_address: Address or place string to resolve.

        Returns:
            Tuple of (latitude, longitude, formatted_address) or None if not found.
        """
        if not raw_address or not raw_address.strip():
            return None

        norm_addr = normalize_address(raw_address)
        query_hash = compute_address_hash(norm_addr)

        # 1. Cache-first lookup
        cached = await self._cache_repo.get(query_hash)
        if cached is not None and cached.status == "SUCCESS":
            logger.info("MSG <-|   Source=geocache Hash=%s", query_hash[:8])
            return cached.lat, cached.lon, cached.formatted_address

        # 2. Rate-limited outbound Nominatim request
        await self._rate_limiter.acquire()
        headers = {"User-Agent": USER_AGENT}
        params = {"q": raw_address, "format": "json", "limit": 1}

        logger.info("MSG   |-> Target=Nominatim Address='%s'", raw_address)
        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("Nominatim request failed for '%s': %s", raw_address, exc)
            return None
        finally:
            if self._http_client is None:
                await client.aclose()

        if not data:
            logger.info("MSG <-|   Source=Nominatim Status=NOT_FOUND Address='%s'", raw_address)
            return None

        result = data[0]
        lat = float(result["lat"])
        lon = float(result["lon"])
        formatted = str(result.get("display_name", raw_address))

        # 3. Store in cache with 90-day TTL
        entry = GeocodingCacheEntry(
            query_hash=query_hash,
            lat=lat,
            lon=lon,
            formatted_address=formatted,
            status="SUCCESS",
        )
        await self._cache_repo.set(entry)
        logger.info("MSG <-|   Source=Nominatim Status=SUCCESS Coords=(%f, %f)", lat, lon)
        return lat, lon, formatted
