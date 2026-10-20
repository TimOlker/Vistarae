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

"""In-memory mock geocoding adapter for tests and local development."""

from __future__ import annotations

from vistarae_core.domain.exceptions import GeocodingTimeoutError
from vistarae_core.domain.value_objects import EnrichmentStatus
from vistarae_core.ports.geocoding import GeocodingResult, IGeocodingPort


class MockGeocodingAdapter(IGeocodingPort):
    """In-memory mock geocoding adapter."""

    def __init__(
        self,
        should_timeout: bool = False,
        should_fail: bool = False,
    ) -> None:
        """Initializes mock geocoding adapter.

        Args:
            should_timeout: If True, simulates 3.0s timeout error.
            should_fail: If True, returns FAILED status.
        """
        self._should_timeout = should_timeout
        self._should_fail = should_fail
        self.forward_call_count = 0
        self.reverse_call_count = 0

    async def forward_geocode(self, query: str) -> GeocodingResult:
        """Simulates forward geocoding."""
        self.forward_call_count += 1
        if self._should_timeout:
            raise GeocodingTimeoutError(query, 3.0)
        if self._should_fail:
            return GeocodingResult(
                lat=0.0,
                lon=0.0,
                formatted_address=query,
                status=EnrichmentStatus.FAILED,
            )

        return GeocodingResult(
            lat=37.8651,
            lon=-119.5383,
            formatted_address=f"{query}, California, USA",
            city="Yosemite",
            states=["California"],
            countries=["United States"],
            status=EnrichmentStatus.SUCCESS,
        )

    async def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Simulates reverse geocoding."""
        self.reverse_call_count += 1
        if self._should_timeout or self._should_fail:
            return GeocodingResult(
                lat=lat,
                lon=lon,
                formatted_address=f"Location ({lat:.4f}, {lon:.4f})",
                status=EnrichmentStatus.PARTIAL,
            )

        return GeocodingResult(
            lat=lat,
            lon=lon,
            formatted_address="Yosemite Village, CA 95389, USA",
            city="Yosemite",
            states=["California"],
            countries=["United States"],
            status=EnrichmentStatus.SUCCESS,
        )
