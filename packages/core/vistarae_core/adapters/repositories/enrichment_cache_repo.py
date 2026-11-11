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

"""SQLAlchemy 2.0 repository adapter for external enrichment cache.

Provides SHA-256 keyed caching for Wikipedia, Wikidata, LLM entity resolution,
and website metadata scraping with configurable TTL via ENRICHMENT_CACHE_TTL_DAYS.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import ExternalEnrichmentCacheTable
from vistarae_core.ports.repositories import IExternalEnrichmentCacheRepository

logger = logging.getLogger("vistarae.enrichment_cache")


def get_default_enrichment_cache_ttl_days() -> int:
    """Reads default cache TTL in days from environment variable ENRICHMENT_CACHE_TTL_DAYS."""
    val = os.getenv("ENRICHMENT_CACHE_TTL_DAYS", "60")
    try:
        return max(1, int(val))
    except ValueError:
        return 60


def hash_enrichment_cache_key(source: str, query: str) -> str:
    """Computes SHA-256 digest of normalized source and query string.

    Args:
        source: Source identifier (e.g. 'wikipedia', 'wikidata', 'enhanced_resolver', 'website_meta').
        query: Raw query or title string.

    Returns:
        64-character hexadecimal SHA-256 string.
    """
    clean_src = source.strip().lower()
    clean_query = " ".join(query.strip().lower().split())
    payload = f"{clean_src}:{clean_query}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SqlAlchemyExternalEnrichmentCacheRepository(IExternalEnrichmentCacheRepository):
    """PostgreSQL repository adapter for external enrichment cache."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes cache repository with active session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def get(self, source: str, query: str) -> dict[str, Any] | None:
        """Retrieves cached payload by source and query string if not expired.

        Args:
            source: Source identifier.
            query: Raw query or title string.

        Returns:
            Structured JSON response data, or None if missing or expired.
        """
        if not source or not query:
            return None

        cache_key = hash_enrichment_cache_key(source, query)
        stmt = select(ExternalEnrichmentCacheTable.response_data).where(
            ExternalEnrichmentCacheTable.cache_key == cache_key,
            ExternalEnrichmentCacheTable.expires_at > func.now(),
        )
        res = await self._session.execute(stmt)
        data = res.scalar_one_or_none()
        if data is not None and isinstance(data, dict):
            logger.debug("MSG <-|  Enrichment cache hit: [%s] '%s'", source, query)
            return dict(data)
        return None

    async def set(
        self,
        source: str,
        query: str,
        response_data: dict[str, Any],
        ttl_days: int | None = None,
    ) -> None:
        """Persists or refreshes an external enrichment cache entry.

        Args:
            source: Source identifier.
            query: Raw query or title string.
            response_data: Structured JSON payload to cache.
            ttl_days: Optional TTL in days override. Defaults to ENRICHMENT_CACHE_TTL_DAYS.
        """
        if not source or not query or not response_data:
            return

        cache_key = hash_enrichment_cache_key(source, query)
        effective_days = ttl_days if ttl_days is not None else get_default_enrichment_cache_ttl_days()
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=effective_days)

        stmt = (
            insert(ExternalEnrichmentCacheTable)
            .values(
                cache_key=cache_key,
                source=source.strip().lower(),
                query_text=query.strip(),
                response_data=response_data,
                created_at=now,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=[ExternalEnrichmentCacheTable.cache_key],
                set_={
                    "response_data": response_data,
                    "expires_at": expires_at,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.debug(
            "MSG |->  Enrichment cache stored: [%s] '%s' (TTL=%d days)",
            source,
            query,
            effective_days,
        )

    async def delete(self, source: str, query: str) -> bool:
        """Deletes a cached entry (used during force refresh/recalculation).

        Args:
            source: Source identifier.
            query: Raw query or title string.

        Returns:
            True if a record was removed, False otherwise.
        """
        if not source or not query:
            return False

        cache_key = hash_enrichment_cache_key(source, query)
        stmt = delete(ExternalEnrichmentCacheTable).where(
            ExternalEnrichmentCacheTable.cache_key == cache_key
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return (res.rowcount or 0) > 0

    async def cleanup_expired(self) -> int:
        """Evicts expired cache rows (expires_at <= NOW()).

        Returns:
            Number of evicted rows.
        """
        stmt = delete(ExternalEnrichmentCacheTable).where(
            ExternalEnrichmentCacheTable.expires_at <= func.now()
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount or 0
