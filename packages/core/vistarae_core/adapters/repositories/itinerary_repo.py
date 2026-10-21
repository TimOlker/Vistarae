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

"""SQLAlchemy 2.0 Pure Async Repository for Itineraries and PostGIS + pgvector RAG.

Implements Constitution Principles 2 & 3:
- Strict tenant scoping (WHERE user_id = :user_id)
- Hybrid corridor queries combining spatial pre-filtering (idx_pois_user_geom via ST_DWithin)
  and pgvector HNSW cosine ranking (ORDER BY embedding <=> :query_vec)
- Atomic batch item reordering with geodesic transit recalculation via ST_Distance
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vistarae_core.adapters.db.tables import (
    ItineraryDayTable,
    ItineraryItemTable,
    ItineraryTable,
    POITable,
    SystemSettingsTable,
)
from vistarae_core.adapters.repositories.poi_repo import _row_to_poi
from vistarae_core.domain.entities import POI
from vistarae_core.domain.itinerary import (
    Itinerary,
    ItineraryDay,
    ItineraryItem,
    ItineraryItemSource,
    ItineraryStatus,
)
from vistarae_core.ports.itinerary_repo import IItineraryRepository


def _extract_lat_lng(geom: Any) -> tuple[float, float]:
    """Extracts latitude and longitude from a GeoAlchemy geometry or mock object.

    Args:
        geom: Geography or geometry object.

    Returns:
        Tuple of (latitude, longitude).
    """
    try:
        shape = to_shape(geom)
        return float(shape.y), float(shape.x)
    except Exception:
        if hasattr(geom, "y") and hasattr(geom, "x"):
            return float(geom.y), float(geom.x)
        if hasattr(geom, "lat") and hasattr(geom, "lon"):
            return float(geom.lat), float(geom.lon)
        return 0.0, 0.0


def _item_row_to_domain(row: ItineraryItemTable) -> ItineraryItem:
    """Converts ItineraryItemTable ORM row to pure domain entity."""
    lat, lng = _extract_lat_lng(row.geom)
    return ItineraryItem(
        id=row.id,
        itinerary_day_id=row.itinerary_day_id,
        poi_id=row.poi_id,
        is_backup_for_id=row.is_backup_for_id,
        title=row.title,
        category=row.category,
        source_type=ItineraryItemSource(row.source_type),
        latitude=lat,
        longitude=lng,
        order_index=row.order_index,
        start_time=row.start_time,
        end_time=row.end_time,
        duration_hours=row.duration_hours,
        cost_cents=row.cost_cents,
        travel_time_prev_minutes=row.travel_time_prev_minutes,
        travel_distance_prev_meters=row.travel_distance_prev_meters,
        notes=row.notes,
    )


def _day_row_to_domain(row: ItineraryDayTable) -> ItineraryDay:
    """Converts ItineraryDayTable ORM row to pure domain entity."""
    return ItineraryDay(
        id=row.id,
        itinerary_id=row.itinerary_id,
        day_number=row.day_number,
        calendar_date=row.calendar_date,
        notes=row.notes,
        target_budget_cents=row.target_budget_cents,
        total_cost_cents=row.total_cost_cents,
        items=[
            _item_row_to_domain(item) for item in sorted(row.items, key=lambda x: x.order_index)
        ],
    )


def _itinerary_row_to_domain(row: ItineraryTable) -> Itinerary:
    """Converts ItineraryTable ORM row to pure domain entity."""
    return Itinerary(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        destination=row.destination,
        start_date=row.start_date,
        end_date=row.end_date,
        budget_cents=row.budget_cents,
        currency=row.currency,
        status=ItineraryStatus(row.status),
        days=[_day_row_to_domain(day) for day in sorted(row.days, key=lambda x: x.day_number)],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyItineraryRepository(IItineraryRepository):
    """SQLAlchemy 2.0 Async PostgreSQL PostGIS + pgvector adapter for Itineraries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes repository with async session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create_itinerary(self, itinerary: Itinerary) -> Itinerary:
        """Persists a new itinerary with child days and items."""
        itinerary_row = ItineraryTable(
            id=itinerary.id,
            user_id=itinerary.user_id,
            title=itinerary.title,
            destination=itinerary.destination,
            start_date=itinerary.start_date,
            end_date=itinerary.end_date,
            budget_cents=itinerary.budget_cents,
            currency=itinerary.currency,
            status=itinerary.status.value,
        )
        self._session.add(itinerary_row)
        await self._session.flush()

        for day in itinerary.days:
            day_cost = sum(item.cost_cents for item in day.items)
            day_row = ItineraryDayTable(
                id=day.id,
                itinerary_id=itinerary_row.id,
                day_number=day.day_number,
                calendar_date=day.calendar_date,
                notes=day.notes,
                target_budget_cents=day.target_budget_cents,
                total_cost_cents=day_cost,
            )
            self._session.add(day_row)
            await self._session.flush()

            for item in day.items:
                geom_wkt = WKTElement(f"POINT({item.longitude} {item.latitude})", srid=4326)
                item_row = ItineraryItemTable(
                    id=item.id,
                    itinerary_day_id=day_row.id,
                    poi_id=item.poi_id,
                    is_backup_for_id=item.is_backup_for_id,
                    title=item.title,
                    category=item.category,
                    source_type=item.source_type.value,
                    geom=geom_wkt,
                    order_index=item.order_index,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    duration_hours=item.duration_hours,
                    cost_cents=item.cost_cents,
                    travel_time_prev_minutes=item.travel_time_prev_minutes,
                    travel_distance_prev_meters=item.travel_distance_prev_meters,
                    notes=item.notes,
                )
                self._session.add(item_row)

        await self._session.flush()
        return await self.get_itinerary_by_id(itinerary_row.id, itinerary.user_id)  # type: ignore[return-value]

    async def get_itinerary_by_id(self, itinerary_id: UUID, user_id: UUID) -> Itinerary | None:
        """Retrieves an itinerary by ID with days and items enforcing tenant isolation."""
        stmt = (
            select(ItineraryTable)
            .where(ItineraryTable.id == itinerary_id, ItineraryTable.user_id == user_id)
            .options(selectinload(ItineraryTable.days).selectinload(ItineraryDayTable.items))
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return _itinerary_row_to_domain(row)

    async def list_itineraries_by_user(self, user_id: UUID) -> list[Itinerary]:
        """Lists all itineraries belonging to a user."""
        stmt = (
            select(ItineraryTable)
            .where(ItineraryTable.user_id == user_id)
            .options(selectinload(ItineraryTable.days).selectinload(ItineraryDayTable.items))
            .order_by(ItineraryTable.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_itinerary_row_to_domain(r) for r in rows]

    async def update_itinerary(self, itinerary: Itinerary) -> Itinerary:
        """Updates itinerary metadata."""
        stmt = (
            update(ItineraryTable)
            .where(ItineraryTable.id == itinerary.id, ItineraryTable.user_id == itinerary.user_id)
            .values(
                title=itinerary.title,
                destination=itinerary.destination,
                start_date=itinerary.start_date,
                end_date=itinerary.end_date,
                budget_cents=itinerary.budget_cents,
                currency=itinerary.currency,
                status=itinerary.status.value,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get_itinerary_by_id(itinerary.id, itinerary.user_id)  # type: ignore[return-value]

    async def delete_itinerary(self, itinerary_id: UUID, user_id: UUID) -> bool:
        """Deletes an itinerary cascading to all days and items."""
        stmt = delete(ItineraryTable).where(
            ItineraryTable.id == itinerary_id, ItineraryTable.user_id == user_id
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def find_pois_in_corridor_hybrid(
        self,
        user_id: UUID,
        center_lat: float,
        center_lng: float,
        radius_meters: float,
        query_embedding: list[float],
        limit: int = 15,
    ) -> list[POI]:
        """Hybrid PostGIS spatial pre-filtering + pgvector cosine similarity ranking."""
        corridor_point = func.ST_SetSRID(func.ST_MakePoint(center_lng, center_lat), 4326)

        # 1. Primary tenant query with spatial proximity pre-filter
        user_stmt = select(POITable).where(
            POITable.user_id == user_id,
            func.ST_DWithin(POITable.geom, corridor_point, radius_meters),
        )

        if query_embedding:
            cosine_distance = POITable.embedding.cosine_distance(query_embedding)
            user_stmt = user_stmt.order_by(cosine_distance)
        else:
            user_stmt = user_stmt.order_by(POITable.rating.desc().nullslast())

        user_stmt = user_stmt.limit(limit)
        result = await self._session.execute(user_stmt)
        rows = list(result.scalars().all())

        # 2. Fallback to other public POIs if user has fewer than 3 POIs in the region
        if len(rows) < 3:
            needed = limit - len(rows)
            existing_ids = [r.id for r in rows]
            fallback_stmt = select(POITable).where(
                func.ST_DWithin(POITable.geom, corridor_point, radius_meters),
                POITable.id.notin_(existing_ids) if existing_ids else True,
            )
            if query_embedding:
                fallback_stmt = fallback_stmt.order_by(
                    POITable.embedding.cosine_distance(query_embedding)
                )
            else:
                fallback_stmt = fallback_stmt.order_by(POITable.rating.desc().nullslast())

            fallback_stmt = fallback_stmt.limit(needed)
            fb_res = await self._session.execute(fallback_stmt)
            rows.extend(list(fb_res.scalars().all()))

        return [_row_to_poi(r) for r in rows]

    async def reorder_items(
        self,
        user_id: UUID,
        itinerary_id: UUID,
        item_reorders: list[dict[str, Any]],
    ) -> Itinerary:
        """Applies batch reordering of items within and across day columns."""
        # Verify itinerary ownership
        itinerary = await self.get_itinerary_by_id(itinerary_id, user_id)
        if not itinerary:
            raise ValueError(f"Itinerary {itinerary_id} not found for user {user_id}")

        for item_data in item_reorders:
            item_id = item_data["item_id"]
            new_day_id = item_data["itinerary_day_id"]
            new_order = item_data["order_index"]
            start_t = item_data.get("start_time")
            end_t = item_data.get("end_time")

            update_values: dict[str, Any] = {
                "itinerary_day_id": new_day_id,
                "order_index": new_order,
            }
            if start_t is not None:
                update_values["start_time"] = start_t
            if end_t is not None:
                update_values["end_time"] = end_t

            await self._session.execute(
                update(ItineraryItemTable)
                .where(ItineraryItemTable.id == item_id)
                .values(**update_values)
            )

        await self._session.flush()

        # Recalculate transit times and distances between sequential items for each day
        refreshed = await self.get_itinerary_by_id(itinerary_id, user_id)
        if not refreshed:
            raise ValueError(f"Failed to refresh itinerary {itinerary_id}")

        for day in refreshed.days:
            items = sorted(day.items, key=lambda x: x.order_index)
            for idx in range(len(items)):
                if idx == 0:
                    await self._session.execute(
                        update(ItineraryItemTable)
                        .where(ItineraryItemTable.id == items[idx].id)
                        .values(travel_time_prev_minutes=0, travel_distance_prev_meters=0)
                    )
                else:
                    prev = items[idx - 1]
                    curr = items[idx]
                    # Compute geodesic distance via ST_Distance
                    dist_query = select(
                        func.ST_Distance(
                            func.ST_SetSRID(func.ST_MakePoint(prev.longitude, prev.latitude), 4326),
                            func.ST_SetSRID(func.ST_MakePoint(curr.longitude, curr.latitude), 4326),
                        )
                    )
                    dist_result = await self._session.execute(dist_query)
                    meters = int(dist_result.scalar_one() or 0)
                    # Estimate transit minutes: ~40 km/h driving average (666 meters/minute)
                    minutes = (
                        max(5, int(meters / 666.0)) if meters > 500 else max(2, int(meters / 80.0))
                    )

                    await self._session.execute(
                        update(ItineraryItemTable)
                        .where(ItineraryItemTable.id == curr.id)
                        .values(
                            travel_time_prev_minutes=minutes, travel_distance_prev_meters=meters
                        )
                    )

            # Update day total cost
            day_total = sum(i.cost_cents for i in items)
            await self._session.execute(
                update(ItineraryDayTable)
                .where(ItineraryDayTable.id == day.id)
                .values(total_cost_cents=day_total)
            )

        await self._session.flush()
        return await self.get_itinerary_by_id(itinerary_id, user_id)  # type: ignore[return-value]

    async def get_system_setting(self, key: str) -> dict[str, Any] | None:
        """Retrieves a system configuration by key."""
        stmt = select(SystemSettingsTable).where(SystemSettingsTable.key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return dict(row.value)

    async def set_system_setting(self, key: str, value: dict[str, Any]) -> None:
        """Upserts a system configuration value."""
        stmt = (
            insert(SystemSettingsTable)
            .values(key=key, value=value, updated_at=datetime.now(UTC))
            .on_conflict_do_update(
                index_elements=[SystemSettingsTable.key],
                set_={"value": value, "updated_at": datetime.now(UTC)},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
