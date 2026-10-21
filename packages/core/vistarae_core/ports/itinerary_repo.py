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

"""Abstract repository port interface for Itineraries and System Settings.

Isolates external persistence dependencies behind typing.Protocol contracts per
Constitution Principle 2 (Ports & Adapters). No ORM or driver imports allowed.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from vistarae_core.domain.entities import POI
from vistarae_core.domain.itinerary import Itinerary


class IItineraryRepository(Protocol):
    """Persistence contract for travel itineraries, days, items, and platform settings."""

    async def create_itinerary(self, itinerary: Itinerary) -> Itinerary:
        """Persists a new itinerary with all associated days and items.

        Args:
            itinerary: Domain itinerary aggregate to persist.

        Returns:
            Persisted Itinerary with assigned IDs and timestamps.
        """
        ...

    async def get_itinerary_by_id(self, itinerary_id: UUID, user_id: UUID) -> Itinerary | None:
        """Retrieves an itinerary by ID enforcing tenant isolation.

        Args:
            itinerary_id: UUID of the target itinerary.
            user_id: Authenticated user ID for tenant scoping.

        Returns:
            Itinerary domain aggregate with days and items if found and owned by user, else None.
        """
        ...

    async def list_itineraries_by_user(self, user_id: UUID) -> list[Itinerary]:
        """Lists all itineraries belonging to a user.

        Args:
            user_id: Authenticated user ID for tenant scoping.

        Returns:
            List of Itinerary aggregates.
        """
        ...

    async def update_itinerary(self, itinerary: Itinerary) -> Itinerary:
        """Updates itinerary metadata.

        Args:
            itinerary: Updated Itinerary domain aggregate.

        Returns:
            Updated Itinerary.
        """
        ...

    async def delete_itinerary(self, itinerary_id: UUID, user_id: UUID) -> bool:
        """Deletes an itinerary and cascades to all child days and items.

        Args:
            itinerary_id: UUID of the itinerary to delete.
            user_id: Authenticated user ID for tenant scoping.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def find_pois_in_corridor_hybrid(
        self,
        user_id: UUID,
        center_lat: float,
        center_lng: float,
        radius_meters: float,
        query_embedding: list[float],
        limit: int = 15,
    ) -> list[POI]:
        """Executes hybrid spatial pre-filtering and vector cosine similarity ranking.

        Pre-filters POIs by tenant and spatial corridor using idx_pois_user_geom (ST_DWithin),
        then ranks candidates by cosine distance against query_embedding (ORDER BY embedding <=> :vec).
        Falls back to public/curated POIs if fewer than 3 user POIs are found.

        Args:
            user_id: Tenant user ID.
            center_lat: Central corridor latitude.
            center_lng: Central corridor longitude.
            radius_meters: Spatial bounding radius in meters.
            query_embedding: 768-dim float embedding vector from Gemini.
            limit: Maximum candidate POIs to return.

        Returns:
            Ranked list of POI entities.
        """
        ...

    async def reorder_items(
        self,
        user_id: UUID,
        itinerary_id: UUID,
        item_reorders: list[dict[str, Any]],
    ) -> Itinerary:
        """Applies batch reordering of items within and across day columns.

        Args:
            user_id: Tenant user ID.
            itinerary_id: Target itinerary ID.
            item_reorders: List of item reposition dictionaries containing item_id,
                itinerary_day_id, order_index, start_time, and end_time.

        Returns:
            Updated Itinerary aggregate.
        """
        ...

    async def get_system_setting(self, key: str) -> dict[str, Any] | None:
        """Retrieves a system configuration by key.

        Args:
            key: Setting key (e.g. 'spend_killswitch').

        Returns:
            Dict value if found, else None.
        """
        ...

    async def set_system_setting(self, key: str, value: dict[str, Any]) -> None:
        """Upserts a system configuration value.

        Args:
            key: Setting key.
            value: JSON-serializable dictionary value.
        """
        ...
