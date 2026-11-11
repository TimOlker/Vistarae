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

"""Unit tests for External Enrichment Cache Repository and TTL configuration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.repositories.enrichment_cache_repo import (
    SqlAlchemyExternalEnrichmentCacheRepository,
    get_default_enrichment_cache_ttl_days,
    hash_enrichment_cache_key,
)


def test_hash_enrichment_cache_key_normalization() -> None:
    """Verifies that hashing normalizes whitespace, casing, and source prefixes."""
    h1 = hash_enrichment_cache_key("Wikipedia", "Hot Springs   National   Park  ")
    h2 = hash_enrichment_cache_key("wikipedia", "hot springs national park")
    h3 = hash_enrichment_cache_key("wikidata", "hot springs national park")

    assert h1 == h2
    assert len(h1) == 64
    assert h1 != h3


def test_get_default_enrichment_cache_ttl_days_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies TTL environment variable parsing and fallbacks."""
    monkeypatch.delenv("ENRICHMENT_CACHE_TTL_DAYS", raising=False)
    assert get_default_enrichment_cache_ttl_days() == 60

    monkeypatch.setenv("ENRICHMENT_CACHE_TTL_DAYS", "90")
    assert get_default_enrichment_cache_ttl_days() == 90

    monkeypatch.setenv("ENRICHMENT_CACHE_TTL_DAYS", "invalid_number")
    assert get_default_enrichment_cache_ttl_days() == 60

    monkeypatch.setenv("ENRICHMENT_CACHE_TTL_DAYS", "-5")
    assert get_default_enrichment_cache_ttl_days() == 1


@pytest.mark.asyncio
async def test_enrichment_cache_get_hit() -> None:
    """Verifies get retrieves unexpired cached payload."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = {
        "title": "Baraqish",
        "extract": "Ancient city in Yemen",
        "latitude": 16.03,
        "longitude": 44.81,
    }
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyExternalEnrichmentCacheRepository(mock_session)
    data = await repo.get("wikipedia", "Barakesh")

    assert data is not None
    assert data["title"] == "Baraqish"
    assert data["latitude"] == 16.03
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrichment_cache_get_miss() -> None:
    """Verifies get returns None when no valid cached entry exists."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyExternalEnrichmentCacheRepository(mock_session)
    data = await repo.get("wikipedia", "Nonexistent Place")

    assert data is None


@pytest.mark.asyncio
async def test_enrichment_cache_set() -> None:
    """Verifies set persists cache entry and flushes session."""
    mock_session = AsyncMock()
    repo = SqlAlchemyExternalEnrichmentCacheRepository(mock_session)

    await repo.set(
        "wikipedia",
        "Hot Springs",
        {"title": "Hot Springs National Park", "url": "https://en.wikipedia.org/wiki/Hot_Springs"},
        ttl_days=30,
    )

    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrichment_cache_delete() -> None:
    """Verifies delete executes statement and returns True if row removed."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyExternalEnrichmentCacheRepository(mock_session)
    deleted = await repo.delete("wikipedia", "Hot Springs")

    assert deleted is True
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrichment_cache_cleanup_expired() -> None:
    """Verifies cleanup_expired removes outdated records."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyExternalEnrichmentCacheRepository(mock_session)
    count = await repo.cleanup_expired()

    assert count == 5
    mock_session.execute.assert_awaited_once()
    mock_session.flush.assert_awaited_once()
