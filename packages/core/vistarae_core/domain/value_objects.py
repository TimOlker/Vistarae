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

"""Domain value objects and enumeration types.

Strictly modeled as Python StrEnum backed by VARCHAR columns per Constitution
Principle 4 (prohibiting PostgreSQL native ENUM types).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class UserTier(StrEnum):
    """Governance tier for user quotas and rate limiting."""

    LOW = "low"
    HIGH = "high"
    ADMIN = "admin"


class ThemeMode(StrEnum):
    """User interface display theme setting."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class PacingMode(StrEnum):
    """Itinerary generation speed pacing."""

    RELAXED = "relaxed"
    MODERATE = "moderate"
    FAST_PACED = "fast_paced"


class TransitSpeedMode(StrEnum):
    """Travel transit method for distance calculations."""

    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"
    DRIVING = "driving"


class IdempotencyStatus(StrEnum):
    """Lifecycle state of an idempotency key."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VisitState(StrEnum):
    """User visit status of a POI."""

    NOT_VISITED = "not_visited"
    VISITED_DO_NOT_RETURN = "visited_do_not_return"
    VISITED_RETURN = "visited_return"


class EnrichmentStatus(StrEnum):
    """Enrichment and geocoding resolution status."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DeduplicationPreset(StrEnum):
    """Proximity search preset for duplicate detection."""

    URBAN = "urban"
    MACRO = "macro"

    @property
    def radius_meters(self) -> float:
        """Returns the search radius in meters for the preset.

        Returns:
            805.0 meters (~0.5 miles) for urban, 80467.0 meters (~50 miles) for macro.
        """
        if self == DeduplicationPreset.URBAN:
            return 805.0
        return 80467.0


@dataclass(frozen=True)
class WGS84Point:
    """Canonical geographic coordinate in EPSG:4326."""

    lon: float
    lat: float

    def __post_init__(self) -> None:
        """Validates coordinate ranges in EPSG:4326.

        Raises:
            ValueError: If lon not in [-180, 180] or lat not in [-90, 90].
        """
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"Longitude {self.lon} out of range [-180, 180]")
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"Latitude {self.lat} out of range [-90, 90]")

    @property
    def is_in_china_bbox(self) -> bool:
        """Determines if coordinate requires client-side GCJ-02 offset for Chinese tile providers.

        Territory bounds: 73.66°E <= lon <= 135.05°E, 18.16°N <= lat <= 53.55°N.

        Returns:
            True if point lies within mainland China bounds.
        """
        return 73.66 <= self.lon <= 135.05 and 18.16 <= self.lat <= 53.55


@dataclass(frozen=True)
class BoundingBox:
    """2D planar geographic envelope for map viewports."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        """Validates bounding box coordinates.

        Raises:
            ValueError: If coordinates are out of bounds or min_lat > max_lat.
        """
        if not (-180.0 <= self.min_lon <= 180.0 and -180.0 <= self.max_lon <= 180.0):
            raise ValueError("Longitude must be within [-180, 180]")
        if not (-90.0 <= self.min_lat <= 90.0 and -90.0 <= self.max_lat <= 90.0):
            raise ValueError("Latitude must be within [-90, 90]")
        if self.min_lat > self.max_lat:
            raise ValueError(f"min_lat ({self.min_lat}) cannot exceed max_lat ({self.max_lat})")

    @property
    def crosses_antimeridian(self) -> bool:
        """True when viewport spans across the 180th meridian (min_lon > max_lon).

        Returns:
            True if bounding box crosses antimeridian.
        """
        return self.min_lon > self.max_lon


@dataclass(frozen=True)
class MergeResolutionRule:
    """Rules specifying attribute migration during an interactive POI merge."""

    target_poi_id: UUID
    source_poi_id: UUID
    use_source_for: list[str] = field(default_factory=list)
    merge_tags: bool = True


class IngestJobStatus(StrEnum):
    """Lifecycle state of an asynchronous bulk ingestion job."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class DuplicateTriageStatus(StrEnum):
    """Review status for suspected duplicate POIs discovered during ingestion."""

    PENDING_REVIEW = "PENDING_REVIEW"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
