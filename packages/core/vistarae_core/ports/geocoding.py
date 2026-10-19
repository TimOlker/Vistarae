# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Port protocol for external geocoding and reverse geocoding services.

Isolates HTTP client dependencies and rate-limiting from domain logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from vistarae_core.domain.value_objects import EnrichmentStatus


@dataclass(frozen=True)
class GeocodingResult:
    """Standardized geocoding resolution outcome."""

    lat: float
    lon: float
    formatted_address: str
    city: str | None = None
    states: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    status: EnrichmentStatus = EnrichmentStatus.SUCCESS


class IGeocodingPort(Protocol):
    """Port interface for forward and reverse geocoding providers."""

    async def forward_geocode(self, query: str) -> GeocodingResult:
        """Resolves freeform query or address string to canonical coordinates.

        Args:
            query: Freeform location or address text.

        Returns:
            GeocodingResult with coordinates, address, and administrative tags.

        Raises:
            GeocodingTimeoutError: If the external call exceeds timeout ceiling.
        """
        ...

    async def reverse_geocode(self, lat: float, lon: float) -> GeocodingResult:
        """Resolves geographic coordinates to standardized address and administrative tags.

        Args:
            lat: Latitude in EPSG:4326.
            lon: Longitude in EPSG:4326.

        Returns:
            GeocodingResult with standardized address and admin tags.

        Raises:
            GeocodingTimeoutError: If the external call exceeds timeout ceiling.
        """
        ...
