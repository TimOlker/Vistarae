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

"""Geocoding service using OpenStreetMap Nominatim with strict rate limiting and persistent caching."""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from photo_scraper.core.cache import PersistentCache
from photo_scraper.core.config import settings

logger = logging.getLogger("vistarae.photo_scraper.geocoder")

# Global thread lock and timestamp for strict 1 req/sec rate limit enforcement
_rate_lock = threading.Lock()
_last_request_time: float = 0.0


@dataclass
class GeocodedLocation:
    """Standardized geocoded location result."""

    name: str
    display_name: str
    latitude: float
    longitude: float
    street: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    postal_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_nominatim_dict(self, query: str | None = None) -> dict[str, Any]:
        """Serializes geocoded result for cache storage."""
        data = {
            "query": query,
            "found": True,
            "name": self.name,
            "display_name": self.display_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "country_code": self.country_code,
            "postal_code": self.postal_code,
        }
        return data


def _enforce_rate_limit() -> None:
    """Enforces strict delay between outbound Nominatim requests."""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        required_delay = settings.NOMINATIM_RATE_LIMIT_SEC
        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            logger.debug(f"Nominatim rate limit pause: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        _last_request_time = time.monotonic()


def _normalize_query(query: str) -> str:
    """Normalizes address string for consistent hashing and caching."""
    return " ".join(query.strip().lower().split())


def _extract_address_components(raw_address: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """Extracts street, city, state, country, country_code, postal_code from OSM address dict."""
    street = (
        raw_address.get("road")
        or raw_address.get("pedestrian")
        or raw_address.get("street")
    )
    city = (
        raw_address.get("city")
        or raw_address.get("town")
        or raw_address.get("village")
        or raw_address.get("hamlet")
        or raw_address.get("municipality")
        or raw_address.get("suburb")
        or raw_address.get("county")
    )
    state = (
        raw_address.get("state")
        or raw_address.get("province")
        or raw_address.get("region")
        or raw_address.get("state_district")
    )
    country = raw_address.get("country")
    country_code = raw_address.get("country_code", "").upper() if raw_address.get("country_code") else None
    postal_code = raw_address.get("postcode")

    # If in UK and state is a constituent country (Scotland, Wales, England, Northern Ireland), map country to constituent country
    if country in ("United Kingdom", "Great Britain") and state in ("Scotland", "Wales", "England", "Northern Ireland"):
        country = state

    return street, city, state, country, country_code, postal_code


class ScraperGeocoder:
    """Handles reverse and forward geocoding with disk cache and Nominatim fallback."""

    def __init__(self, cache: PersistentCache | None = None):
        self.cache = cache or PersistentCache(settings.CACHE_FILE_PATH)
        self.headers = {
            "User-Agent": settings.NOMINATIM_USER_AGENT,
            "Accept-Language": "en",
        }

    def reverse_geocode(self, lat: float, lon: float, fallback_name: str = "") -> GeocodedLocation | None:
        """Resolves coordinates into an address and place details."""
        if lat == 0.0 and lon == 0.0:
            return None

        cache_key = f"rev:{lat:.5f},{lon:.5f}"
        cached = self.cache.get(cache_key)
        if cached:
            raw_addr = cached.get("address", {})
            street, city, state, country, cc, zip_code = _extract_address_components(raw_addr)
            return GeocodedLocation(
                name=cached.get("name") or fallback_name or cached.get("display_name", ""),
                display_name=cached.get("display_name", ""),
                latitude=lat,
                longitude=lon,
                street=street,
                city=city,
                state=state,
                country=country,
                country_code=cc,
                postal_code=zip_code,
                raw=cached,
            )

        # Enforce rate limit before calling Nominatim
        _enforce_rate_limit()

        url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/reverse"
        params = {
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "format": "jsonv2",
            "addressdetails": "1",
        }

        logger.info(f"MSG   |-> [Nominatim Reverse] lat={lat:.5f}, lon={lon:.5f}")
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params, headers=self.headers)
                logger.info(f"MSG   |<- [Nominatim Reverse] Status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data and "error" not in data:
                        self.cache.set(cache_key, data)
                        raw_addr = data.get("address", {})
                        street, city, state, country, cc, zip_code = _extract_address_components(raw_addr)

                        place_name = (
                            data.get("name")
                            or raw_addr.get("tourism")
                            or raw_addr.get("leisure")
                            or raw_addr.get("amenity")
                            or fallback_name
                            or data.get("display_name", "")
                        )

                        return GeocodedLocation(
                            name=place_name,
                            display_name=data.get("display_name", ""),
                            latitude=lat,
                            longitude=lon,
                            street=street,
                            city=city,
                            state=state,
                            country=country,
                            country_code=cc,
                            postal_code=zip_code,
                            raw=data,
                        )
                else:
                    logger.warning(f"Nominatim reverse error HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Nominatim reverse geocode exception for ({lat}, {lon}): {exc}")

        return None

    def forward_geocode(
        self,
        query: str,
        bias_near_batavia: bool = False,
    ) -> GeocodedLocation | None:
        """Forward geocodes query string using disk cache first, then Nominatim."""
        norm_query = _normalize_query(query)
        if not norm_query:
            return None

        cache_key = f"geo:{norm_query}"
        cached = self.cache.get(cache_key)
        if cached:
            raw_addr = cached.get("address", {})
            street, city, state, country, cc, zip_code = _extract_address_components(raw_addr)
            return GeocodedLocation(
                name=cached.get("name") or query,
                display_name=cached.get("display_name", query),
                latitude=float(cached.get("lat", 0.0)),
                longitude=float(cached.get("lon", 0.0)),
                street=street,
                city=city,
                state=state,
                country=country,
                country_code=cc,
                postal_code=zip_code,
                raw=cached,
            )

        # Enforce rate limit
        _enforce_rate_limit()

        url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search"
        params: dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": "1",
            "limit": "1",
        }

        result = self.forward_geocode_query(url, query, params, cache_key)
        return result

    def forward_geocode_query(self, url, query, params, cache_key) -> GeocodedLocation | None:
        if isinstance(cache_key, dict) and (
            cache_key.get('country', '').lower() == 'skip'
            or cache_key.get('state', '').lower() == 'skip'
            or cache_key.get('city', '').lower() == 'skip'
            or cache_key.get('site', '').lower() == 'skip'
            or cache_key.get('skip') is True
        ):
            logger.info(f"[Nominatim] skipping q='{query}'")
            return None

        logger.info(f"MSG   |-> [Nominatim Forward] q='{query}'")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params, headers=self.headers)

                if resp.status_code != 200:
                    logger.info(f"MSG   |<~ [Nominatim Forward] Status={resp.status_code}")
                    logger.warning(f"[Nominatim] search error HTTP {resp.status_code}: {resp.text}")
                    return None

                logger.info(f"MSG   |<- [Nominatim Forward] Status={resp.status_code}")
                results = resp.json()
                if not results or len(results) == 0:
                    logger.info(f"[Nominatim] returned no results for: '{query}'")
                    return None

                top = results[0]
                self.cache.set(cache_key, top)
                raw_addr = top.get("address", {})
                street, city, state, country, cc, zip_code = _extract_address_components(raw_addr)

                place_name = (
                    top.get("name")
                    or raw_addr.get("tourism")
                    or raw_addr.get("leisure")
                    or query
                )

                return GeocodedLocation(
                    name=place_name,
                    display_name=top.get("display_name", query),
                    latitude=float(top.get("lat", 0.0)),
                    longitude=float(top.get("lon", 0.0)),
                    street=street,
                    city=city,
                    state=state,
                    country=country,
                    country_code=cc,
                    postal_code=zip_code,
                    raw=top,
                )


        except Exception as exc:
            logger.error(f"[Nominatim] forward geocode exception for '{query}': {exc}")
            return None
