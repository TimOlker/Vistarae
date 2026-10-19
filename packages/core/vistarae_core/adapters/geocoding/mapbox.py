# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Mapbox / Nominatim geocoding adapter implementing IGeocodingPort (T-023).

Adheres to:
- 1 rps token bucket rate limit
- 90-day SHA-256 caching via IGeocodingCacheRepository
- 3.0-second timeout ceiling with graceful degradation (enrichment_status = 'PARTIAL')
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from vistarae_core.adapters.geocoding.rate_limiter import TokenBucketRateLimiter
from vistarae_core.adapters.repositories.geocache_repo import (
    hash_coordinate_pair,
    hash_query_string,
)
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.domain.exceptions import GeocodingTimeoutError
from vistarae_core.domain.value_objects import EnrichmentStatus
from vistarae_core.ports.geocoding import GeocodingResult, IGeocodingPort
from vistarae_core.ports.repositories import IGeocodingCacheRepository


class MapboxGeocodingAdapter(IGeocodingPort):
    """External geocoding client with caching, token bucket, and 3.0s timeout fallback."""

    def __init__(
        self,
        cache_repo: IGeocodingCacheRepository | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        api_key: str | None = None,
        base_url: str = "https://api.mapbox.com/geocoding/v5/mapbox.places",
        timeout_seconds: float = 3.0,
    ) -> None:
        """Initializes the geocoding adapter.

        Args:
            cache_repo: Optional database cache repository.
            rate_limiter: Optional 1 rps token bucket limiter.
            api_key: Provider API key or token.
            base_url: Geocoding endpoint URL.
            timeout_seconds: Timeout ceiling in seconds.
        """
        self._cache_repo = cache_repo
        self._limiter = rate_limiter or TokenBucketRateLimiter(rate_per_second=1.0)
        self._api_key = api_key or "pk.test"
        self._base_url = base_url
        self._timeout = timeout_seconds

    async def forward_geocode(self, query: str) -> GeocodingResult:
        """Forward geocodes query to canonical coordinates with cache lookup.

        Args:
            query: Location or address text.

        Returns:
            GeocodingResult.
        """
        query_hash = hash_query_string(query)

        # Check internal cache first
        if self._cache_repo is not None:
            cached = await self._cache_repo.get(query_hash)
            if cached is not None:
                return GeocodingResult(
                    lat=cached.lat,
                    lon=cached.lon,
                    formatted_address=cached.formatted_address,
                    status=EnrichmentStatus(cached.status),
                )

        # Rate limit outbound request
        await self._limiter.acquire()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/{httpx.URL(query).raw_path}.json",
                    params={"access_token": self._api_key, "limit": 1},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    if features:
                        feature = features[0]
                        lon, lat = feature["geometry"]["coordinates"]
                        addr = feature.get("place_name", query)
                        states = [
                            c["text"]
                            for c in feature.get("context", [])
                            if c.get("id", "").startswith("region")
                        ]
                        countries = [
                            c["text"]
                            for c in feature.get("context", [])
                            if c.get("id", "").startswith("country")
                        ]
                        result = GeocodingResult(
                            lat=float(lat),
                            lon=float(lon),
                            formatted_address=addr,
                            states=states,
                            countries=countries,
                            status=EnrichmentStatus.SUCCESS,
                        )

                        # Write to cache
                        if self._cache_repo is not None:
                            await self._cache_repo.set(
                                GeocodingCacheEntry(
                                    query_hash=query_hash,
                                    lat=result.lat,
                                    lon=result.lon,
                                    formatted_address=result.formatted_address,
                                    status=result.status.value,
                                    created_at=datetime.now(UTC),
                                    expires_at=datetime.now(UTC) + timedelta(days=90),
                                )
                            )
                        return result
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise GeocodingTimeoutError(query, self._timeout) from exc
        except Exception:
            pass

        return GeocodingResult(
            lat=0.0,
            lon=0.0,
            formatted_address=query,
            status=EnrichmentStatus.FAILED,
        )

    async def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Reverse geocodes coordinates with cache lookup and fallback.

        Args:
            lat: Latitude.
            lon: Longitude.

        Returns:
            GeocodingResult. Falls back to user coordinates with status PARTIAL on failure.
        """
        coord_hash = hash_coordinate_pair(lat, lon)

        # Check internal cache first
        if self._cache_repo is not None:
            cached = await self._cache_repo.get(coord_hash)
            if cached is not None:
                return GeocodingResult(
                    lat=cached.lat,
                    lon=cached.lon,
                    formatted_address=cached.formatted_address,
                    status=EnrichmentStatus(cached.status),
                )

        # Rate limit outbound request
        await self._limiter.acquire()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/{lon},{lat}.json",
                    params={"access_token": self._api_key, "limit": 1},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    if features:
                        feature = features[0]
                        addr = feature.get("place_name", f"{lat}, {lon}")
                        states = [
                            c["text"]
                            for c in feature.get("context", [])
                            if c.get("id", "").startswith("region")
                        ]
                        countries = [
                            c["text"]
                            for c in feature.get("context", [])
                            if c.get("id", "").startswith("country")
                        ]
                        result = GeocodingResult(
                            lat=lat,
                            lon=lon,
                            formatted_address=addr,
                            states=states,
                            countries=countries,
                            status=EnrichmentStatus.SUCCESS,
                        )

                        if self._cache_repo is not None:
                            await self._cache_repo.set(
                                GeocodingCacheEntry(
                                    query_hash=coord_hash,
                                    lat=result.lat,
                                    lon=result.lon,
                                    formatted_address=result.formatted_address,
                                    status=result.status.value,
                                    created_at=datetime.now(UTC),
                                    expires_at=datetime.now(UTC) + timedelta(days=90),
                                )
                            )
                        return result
        except Exception:
            # Graceful fallback: retain user coordinates with PARTIAL enrichment
            pass

        return GeocodingResult(
            lat=lat,
            lon=lon,
            formatted_address=f"Location ({lat:.4f}, {lon:.4f})",
            status=EnrichmentStatus.PARTIAL,
        )
