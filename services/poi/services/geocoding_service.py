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

"""Intelligent geocoding and boundary-aware addressing service (T-030, T-031).

Enforces:
- PostGIS geocoding_cache SHA-256 pre-check (REQ-EXT-022, REQ-EXT-027)
- 1 request per second rate limiting for OpenStreetMap Nominatim (REQ-EXT-023)
- Custom User-Agent: VistaraeTravelEngine/1.0
- Reverse geocoding fallback for missing street/administrative components (REQ-EXT-024)
- Trans-boundary multi-address generation (REQ-EXT-025)
- Standard English ISO 3166-1 country normalization (REQ-EXT-026)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from vistarae_core.adapters.geocoding.rate_limiter import TokenBucketRateLimiter
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.domain.value_objects import AddressRecord
from vistarae_core.ports.repositories import IGeocodingCacheRepository
from vistarae_core.services.address_normalizer import AddressNormalizer

from services.poi.services.geocode_service import ReverseGeocodeService

logger = logging.getLogger("vistarae.geocoding")

NOMINATIM_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=1.0, capacity=1.0)
CUSTOM_USER_AGENT = "VistaraeTravelEngine/1.0"


def compute_query_hash(query: str) -> str:
    """Computes normalized SHA-256 hash of address query string (REQ-EXT-022)."""
    norm = query.strip().lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class GeocodingService:
    """Provides cached, rate-limited forward and reverse geocoding."""

    def __init__(
        self,
        cache_repo: IGeocodingCacheRepository,
        rate_limiter: TokenBucketRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        """Initializes the geocoding service.

        Args:
            cache_repo: Persistent geocache database repository.
            rate_limiter: Token bucket rate limiter (defaults to 1 req/sec).
            http_client: Optional httpx.AsyncClient for testing.
            timeout_seconds: HTTP request timeout ceiling.
        """
        self._cache_repo = cache_repo
        self._rate_limiter = rate_limiter or NOMINATIM_RATE_LIMITER
        self._client = http_client
        self._timeout_seconds = timeout_seconds
        self._reverse_service = ReverseGeocodeService(
            cache_repo=cache_repo,
            rate_limiter=self._rate_limiter,
            http_client=http_client,
            timeout_seconds=timeout_seconds,
        )

    async def geocode(
        self,
        query: str,
        transboundary_hints: str | None = None,
    ) -> tuple[float | None, float | None, list[AddressRecord], bool]:
        """Geocodes a destination name or address query string.

        Args:
            query: Location query string.
            transboundary_hints: Optional text hints indicating multiple traversed divisions.

        Returns:
            Tuple of (latitude, longitude, list of AddressRecords, is_cached_bool).
        """
        if not query.strip():
            return None, None, [], False

        query_hash = compute_query_hash(query)

        # 1. Pre-check PostGIS geocoding_cache (REQ-EXT-022, REQ-EXT-027)
        cached_entry = await self._cache_repo.get(query_hash)
        if cached_entry is not None:
            logger.info("MSG ->| Geocache forward hit for hash=%s", query_hash)
            try:
                data = json.loads(cached_entry.formatted_address)
                lat = cached_entry.lat
                lon = cached_entry.lon
                raw_addrs = data.get("addresses", [])
                addresses = [AddressRecord(**a) for a in raw_addrs]
                return lat, lon, addresses, True
            except Exception as exc:
                logger.warning("Could not deserialize cached geocoding entry: %s", exc)

        # 2. Acquire token for 1 req/sec Nominatim rate limit (REQ-EXT-023)
        await self._rate_limiter.acquire()

        # 3. Perform outbound HTTP request to OpenStreetMap Nominatim search
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query.strip(),
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 1,
        }
        headers = {
            "User-Agent": CUSTOM_USER_AGENT,
            "Accept": "application/json",
        }

        logger.info("MSG   |-> Nominatim forward geocode query='%s'", query)

        lat: float | None = None
        lon: float | None = None
        base_address: AddressRecord | None = None

        try:
            if self._client is not None:
                resp = await self._client.get(
                    url, params=params, headers=headers, timeout=self._timeout_seconds
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url, params=params, headers=headers, timeout=self._timeout_seconds
                    )

            logger.info("MSG   |<- Nominatim response status=%d", resp.status_code)

            if resp.status_code == 200:
                results = resp.json()
                if results and len(results) > 0:
                    first = results[0]
                    lat = float(first["lat"])
                    lon = float(first["lon"])
                    addr = first.get("address", {})

                    street = addr.get("road") or addr.get("street") or addr.get("pedestrian")
                    city = (
                        addr.get("city")
                        or addr.get("town")
                        or addr.get("village")
                        or addr.get("municipality")
                    )
                    state = addr.get("state") or addr.get("province") or addr.get("region")
                    country = addr.get("country") or "Unknown"
                    postal = addr.get("postcode")

                    base_address = AddressNormalizer.normalize_address(
                        AddressRecord(
                            street=street.strip() if street else None,
                            city=city.strip() if city else None,
                            state_province=state.strip() if state else None,
                            country=country,
                            postal_code=postal.strip() if postal else None,
                        )
                    )
        except Exception as exc:
            logger.warning("MSG   |<- Nominatim search request failed: %s", exc)

        # 4. Reverse geocoding fallback for missing street/administrative components (REQ-EXT-024)
        if lat is not None and lon is not None and (not base_address or not base_address.country):
            try:
                rev = await self._reverse_service.reverse_geocode(lat, lon)
                base_address = AddressNormalizer.normalize_address(
                    AddressRecord(
                        street=rev.street,
                        city=rev.city,
                        state_province=rev.state_province,
                        country=rev.country,
                        postal_code=rev.postal_code,
                    )
                )
            except Exception as exc:
                logger.warning("Reverse geocode fallback failed: %s", exc)

        # 5. Trans-boundary multi-address expansion (REQ-EXT-025, REQ-EXT-026)
        division_source = transboundary_hints or query
        if base_address:
            addresses = AddressNormalizer.expand_transboundary_addresses(
                division_source, base_address=base_address
            )
        else:
            addresses = AddressNormalizer.expand_transboundary_addresses(division_source)

        # 6. Cache successful result with 90-day TTL (REQ-EXT-022, REQ-EXT-027)
        if lat is not None and lon is not None and addresses:
            now = datetime.now(UTC)
            cache_payload = {
                "addresses": [a.model_dump() for a in addresses],
            }
            entry = GeocodingCacheEntry(
                query_hash=query_hash,
                lat=round(lat, 5),
                lon=round(lon, 5),
                formatted_address=json.dumps(cache_payload),
                status="SUCCESS",
                created_at=now,
                expires_at=now + timedelta(days=90),
            )
            await self._cache_repo.set(entry)

        return lat, lon, addresses, False

    async def reverse_geocode(self, lat: float, lng: float) -> list[AddressRecord]:
        """Reverse geocodes coordinates into normalized AddressRecords."""
        resp = await self._reverse_service.reverse_geocode(lat, lng)
        rec = AddressNormalizer.normalize_address(
            AddressRecord(
                street=resp.street,
                city=resp.city,
                state_province=resp.state_province,
                country=resp.country,
                postal_code=resp.postal_code,
            )
        )
        return [rec]
