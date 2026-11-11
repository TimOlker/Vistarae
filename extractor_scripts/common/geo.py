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

"""OpenStreetMap Nominatim geocoding client for optional CLI extraction geocoding."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = (
    "VistaraeDataExtractor/1.0 (Travel POI Research Engine; contact: dev@vistarae.local)"
)


class NominatimGeoClient:
    """Client for querying OpenStreetMap Nominatim with strict 1 req/sec rate limiting."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay_seconds: float = 1.0,
    ) -> None:
        """Initializes the Nominatim geocoding client.

        Args:
            transport: Optional custom HTTPX transport for test mocking.
            user_agent: Custom User-Agent header required by Nominatim usage policy.
            min_delay_seconds: Minimum seconds between subsequent queries (default 1.0).
        """
        self.user_agent = user_agent
        self.min_delay_seconds = max(1.0, min_delay_seconds)
        self._last_call_time: float | None = None
        self._client = httpx.Client(
            transport=transport,
            timeout=10.0,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Language": "en",
            },
        )

    def close(self) -> None:
        """Closes the underlying HTTP transport."""
        self._client.close()

    def _wait_for_rate_limit(self) -> None:
        """Enforces the strict 1 request per second Nominatim policy."""
        if self._last_call_time is not None:
            elapsed = time.monotonic() - self._last_call_time
            if elapsed < self.min_delay_seconds:
                time.sleep(self.min_delay_seconds - elapsed)
        self._last_call_time = time.monotonic()

    def geocode(
        self, query: str, country_code: str | None = None
    ) -> tuple[Decimal | None, Decimal | None]:
        """Geocodes a text query into WGS-84 decimal latitude and longitude.

        Args:
            query: Location or landmark search text.
            country_code: Optional ISO 3166-1 alpha-2 country code to restrict search.

        Returns:
            Tuple of (Decimal latitude, Decimal longitude) or (None, None) if unresolved.
        """
        if not query or not query.strip():
            return None, None

        self._wait_for_rate_limit()
        params: dict[str, Any] = {
            "q": query.strip(),
            "format": "jsonv2",
            "limit": 1,
        }
        if country_code:
            params["countrycodes"] = country_code.lower()

        try:
            response = self._client.get(NOMINATIM_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                first = data[0]
                lat = Decimal(str(first["lat"])).quantize(Decimal("0.000001"))
                lon = Decimal(str(first["lon"])).quantize(Decimal("0.000001"))
                return lat, lon
        except Exception as exc:
            logger.warning("Nominatim geocoding error for query '%s': %s", query, exc)

        return None, None
