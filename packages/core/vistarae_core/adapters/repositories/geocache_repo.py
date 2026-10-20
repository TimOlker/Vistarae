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

"""SQLAlchemy 2.0 repository adapter for geocoding cache (T-022).

Implements 90-day SHA-256 caching and opportunistic eviction of expired entries.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import GeocodingCacheTable
from vistarae_core.domain.entities import GeocodingCacheEntry
from vistarae_core.ports.repositories import IGeocodingCacheRepository


def hash_query_string(query: str) -> str:
    """Computes SHA-256 digest of normalized query string.

    Args:
        query: Raw query or address string.

    Returns:
        64-character hexadecimal SHA-256 string.
    """
    normalized = " ".join(query.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_coordinate_pair(lat: float, lon: float) -> str:
    """Computes SHA-256 digest of normalized coordinate pair (5 decimal places).

    Args:
        lat: Latitude float.
        lon: Longitude float.

    Returns:
        64-character hexadecimal SHA-256 string.
    """
    normalized = f"{round(lat, 5):.5f},{round(lon, 5):.5f}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class SqlAlchemyGeocodingCacheRepository(IGeocodingCacheRepository):
    """PostgreSQL repository adapter for geocoding cache."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes cache repository with active session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def get(self, query_hash: str) -> GeocodingCacheEntry | None:
        """Retrieves a cached geocoding entry by SHA-256 hash if not expired.

        Args:
            query_hash: 64-char hex string SHA-256 digest.

        Returns:
            GeocodingCacheEntry or None if missing or expired.
        """
        stmt = select(GeocodingCacheTable).where(
            GeocodingCacheTable.query_hash == query_hash,
            GeocodingCacheTable.expires_at > func.now(),
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None

        return GeocodingCacheEntry(
            query_hash=row.query_hash,
            lat=row.lat,
            lon=row.lon,
            formatted_address=row.formatted_address,
            status=row.status,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    async def set(self, entry: GeocodingCacheEntry) -> None:
        """Persists or refreshes a geocoding cache entry with 90-day TTL.

        Args:
            entry: Cache entry to store.
        """
        stmt = (
            insert(GeocodingCacheTable)
            .values(
                query_hash=entry.query_hash,
                lat=entry.lat,
                lon=entry.lon,
                formatted_address=entry.formatted_address,
                status=entry.status,
                created_at=entry.created_at,
                expires_at=entry.expires_at,
            )
            .on_conflict_do_update(
                index_elements=[GeocodingCacheTable.query_hash],
                set_={
                    "lat": entry.lat,
                    "lon": entry.lon,
                    "formatted_address": entry.formatted_address,
                    "status": entry.status,
                    "expires_at": entry.expires_at,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def cleanup_expired(self) -> int:
        """Evicts expired geocoding cache rows (expires_at <= NOW()).

        Returns:
            Number of evicted rows.
        """
        stmt = delete(GeocodingCacheTable).where(GeocodingCacheTable.expires_at <= func.now())
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount or 0
