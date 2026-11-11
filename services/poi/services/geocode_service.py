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

"""Cached reverse geocoding service with PostGIS geocache & Nominatim rate limiter (T-017).

Enforces:
- PostGIS geocache table check with 5 decimal places coordinate rounding
- Strict 1 request per second sustained rate limiting
- Custom User-Agent: VistaraeTravelEngine/1.0
- Observability messaging tags (MSG   |-> and MSG   |<-)
- Standard English country and state normalization via AddressNormalizer
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from vistarae_core.adapters.geocoding.rate_limiter import TokenBucketRateLimiter
from vistarae_core.adapters.repositories.geocache_repo import hash_coordinate_pair
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.ports.repositories import IGeocodingCacheRepository
from vistarae_core.schemas.poi import ReverseGeocodeResponse
from vistarae_core.services.address_normalizer import AddressNormalizer

logger = logging.getLogger(__name__)

# Global singleton rate limiter across service invocations
_NOMINATIM_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=1.0, capacity=1.0)


class ReverseGeocodeService:
    """Service providing cached, rate-limited reverse geocoding."""

    def __init__(
        self,
        cache_repo: IGeocodingCacheRepository,
        rate_limiter: TokenBucketRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        """Initializes the reverse geocoding service.

        Args:
            cache_repo: Persistent geocache database repository.
            rate_limiter: Token bucket rate limiter (defaults to 1 req/sec).
            http_client: Optional httpx.AsyncClient for testing injection.
            timeout_seconds: Request timeout ceiling in seconds.
        """
        self._cache_repo = cache_repo
        self._rate_limiter = rate_limiter or _NOMINATIM_RATE_LIMITER
        self._client = http_client
        self._timeout_seconds = timeout_seconds

    async def reverse_geocode(
        self, lat: float, lng: float, force_refresh: bool = False
    ) -> ReverseGeocodeResponse:
        """Reverse geocodes a coordinate pair using geocache lookup and rate-limited Nominatim.

        Args:
            lat: Latitude (-90.0 to 90.0).
            lng: Longitude (-180.0 to 180.0).
            force_refresh: If True, bypasses cache and queries Nominatim.

        Returns:
            ReverseGeocodeResponse with normalized address fields and cache indicator.
        """
        norm_lat = round(lat, 5)
        norm_lng = round(lng, 5)
        coord_hash = hash_coordinate_pair(norm_lat, norm_lng)

        # 1. Check internal PostGIS geocache first
        if not force_refresh:
            cached_entry = await self._cache_repo.get(coord_hash)
            if cached_entry is not None:
                logger.info("MSG ->| Geocache hit for hash=%s", coord_hash)
                if cached_entry.status == "NOT_FOUND":
                    return ReverseGeocodeResponse(
                        street=None,
                        city=None,
                        state_province=None,
                        country="Unknown",
                        postal_code=None,
                        cached=True,
                    )
                try:
                    data = json.loads(cached_entry.formatted_address)
                    city_str = str(data.get("city") or "").lower()
                    is_district_city = (
                        "district" in city_str
                        or "subdistrict" in city_str
                        or city_str in ("pudong", "pudong new area")
                        or any(c in (data.get("city") or "") for c in ("区", "街道"))
                    )
                    # Re-parse if city or admin_level_1 is missing/outdated or city is a district but raw_geocoding is present
                    if (
                        not data.get("city")
                        or not data.get("admin_level_1")
                        or data.get("city") == data.get("admin_level_2")
                        or is_district_city
                    ) and data.get("raw_geocoding"):
                        re_parsed = AddressNormalizer.parse_nominatim_iso_address(data["raw_geocoding"])
                        for k in ("street", "city", "locality", "admin_level_1", "admin_level_2", "state_province", "country", "country_code"):
                            if re_parsed.get(k):
                                if not data.get(k) or (k in ("city", "locality", "admin_level_1", "admin_level_2") and data.get(k) != re_parsed.get(k)):
                                    data[k] = re_parsed[k]
                    return ReverseGeocodeResponse(
                        street=data.get("street"),
                        city=data.get("city"),
                        state_province=data.get("state_province"),
                        country=data.get("country", "Unknown"),
                        postal_code=data.get("postal_code"),
                        country_code=data.get("country_code", "US"),
                        admin_level_1=data.get("admin_level_1"),
                        admin_level_2=data.get("admin_level_2"),
                        locality=data.get("locality"),
                        raw_geocoding=data.get("raw_geocoding"),
                        cached=True,
                    )
                except (json.JSONDecodeError, TypeError):
                    # Fallback if legacy text address string was stored
                    norm_country = AddressNormalizer.normalize_country(cached_entry.formatted_address)
                    return ReverseGeocodeResponse(
                        street=None,
                        city=None,
                        state_province=None,
                        country=norm_country or "Unknown",
                        postal_code=None,
                        cached=True,
                    )

        # 2. Acquire token for 1 req/sec Nominatim compliance
        await self._rate_limiter.acquire()

        # 3. Perform outbound HTTP request to OpenStreetMap Nominatim
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "format": "jsonv2",
            "lat": norm_lat,
            "lon": norm_lng,
            "addressdetails": 1,
            "accept-language": "en",
        }
        headers = {
            "User-Agent": "VistaraeTravelEngine/1.0",
            "Accept": "application/json",
            "Accept-Language": "en",
        }

        logger.info("MSG   |-> Nominatim reverse geocode lat=%f lon=%f", norm_lat, norm_lng)

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
                body = resp.json()
                parsed = AddressNormalizer.parse_nominatim_iso_address(body)
                norm_country = parsed["country"]
                norm_state = (
                    AddressNormalizer.normalize_state_province(
                        parsed["admin_level_1"], country=norm_country
                    )
                    if parsed["admin_level_1"]
                    else None
                )

                payload = {
                    "street": parsed["street_address"],
                    "city": AddressNormalizer.normalize_city(
                        parsed["locality"], country=norm_country
                    )
                    if parsed["locality"]
                    else None,
                    "state_province": norm_state,
                    "country": norm_country,
                    "postal_code": parsed["postal_code"],
                    "country_code": parsed["country_code"],
                    "admin_level_1": parsed["admin_level_1"],
                    "admin_level_2": parsed["admin_level_2"],
                    "locality": parsed["locality"],
                    "raw_geocoding": body,
                }

                # Cache result with 90-day TTL
                now = datetime.now(UTC)
                cache_entry = GeocodingCacheEntry(
                    query_hash=coord_hash,
                    lat=norm_lat,
                    lon=norm_lng,
                    formatted_address=json.dumps(payload),
                    status="SUCCESS",
                    created_at=now,
                    expires_at=now + timedelta(days=90),
                )
                await self._cache_repo.set(cache_entry)

                return ReverseGeocodeResponse(**payload, cached=False)

            if resp.status_code == 429:
                logger.warning("MSG <-| Nominatim rate limit exceeded (HTTP 429)")

        except Exception as exc:
            logger.warning("MSG <-| Nominatim reverse geocode failed: %s", exc)

        # Fallback response on upstream timeout or failure
        return ReverseGeocodeResponse(
            street=None,
            city=None,
            state_province=None,
            country="Unknown",
            postal_code=None,
            cached=False,
        )
