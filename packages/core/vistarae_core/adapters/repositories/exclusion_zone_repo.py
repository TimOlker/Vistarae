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

"""SQLAlchemy adapter for IUserExclusionZoneRepository."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.tables import UserExclusionZoneTable
from vistarae_core.domain.entities import UserExclusionZone
from vistarae_core.ports.repositories import IUserExclusionZoneRepository


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance in kilometers using the Haversine formula."""
    r = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _row_to_entity(row: UserExclusionZoneTable) -> UserExclusionZone:
    return UserExclusionZone(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        latitude=float(row.latitude),
        longitude=float(row.longitude),
        radius_km=float(row.radius_km),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyUserExclusionZoneRepository(IUserExclusionZoneRepository):
    """SQLAlchemy 2.0 implementation of user exclusion zones repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: UUID) -> Sequence[UserExclusionZone]:
        stmt = (
            select(UserExclusionZoneTable)
            .where(UserExclusionZoneTable.user_id == user_id)
            .order_by(UserExclusionZoneTable.created_at.asc())
        )
        res = await self._session.execute(stmt)
        return [_row_to_entity(r) for r in res.scalars().all()]

    async def get_by_id(self, zone_id: UUID, user_id: UUID) -> UserExclusionZone | None:
        stmt = select(UserExclusionZoneTable).where(
            UserExclusionZoneTable.id == zone_id,
            UserExclusionZoneTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def create(self, zone: UserExclusionZone) -> UserExclusionZone:
        row = UserExclusionZoneTable(
            id=zone.id,
            user_id=zone.user_id,
            name=zone.name,
            latitude=Decimal(str(round(zone.latitude, 7))),
            longitude=Decimal(str(round(zone.longitude, 7))),
            radius_km=zone.radius_km,
            created_at=zone.created_at,
            updated_at=zone.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_entity(row)

    async def update(
        self,
        zone_id: UUID,
        user_id: UUID,
        name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float | None = None,
    ) -> UserExclusionZone | None:
        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            values["name"] = name
        if latitude is not None:
            values["latitude"] = Decimal(str(round(latitude, 7)))
        if longitude is not None:
            values["longitude"] = Decimal(str(round(longitude, 7)))
        if radius_km is not None:
            values["radius_km"] = radius_km

        stmt = (
            update(UserExclusionZoneTable)
            .where(
                UserExclusionZoneTable.id == zone_id,
                UserExclusionZoneTable.user_id == user_id,
            )
            .values(**values)
            .returning(UserExclusionZoneTable)
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row:
            await self._session.flush()
            return _row_to_entity(row)
        return None

    async def delete(self, zone_id: UUID, user_id: UUID) -> bool:
        stmt = delete(UserExclusionZoneTable).where(
            UserExclusionZoneTable.id == zone_id,
            UserExclusionZoneTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return (res.rowcount or 0) > 0

    async def find_matching_zones(
        self, user_id: UUID, lat: float, lon: float
    ) -> list[UserExclusionZone]:
        """Finds any user exclusion zones covering the given (lat, lon) coordinates."""
        all_zones = await self.list_by_user(user_id)
        matched: list[UserExclusionZone] = []
        for zone in all_zones:
            dist = haversine_distance_km(lat, lon, zone.latitude, zone.longitude)
            if dist <= zone.radius_km:
                matched.append(zone)
        return matched

