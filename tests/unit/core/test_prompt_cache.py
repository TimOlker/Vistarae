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

"""Unit tests for UserPromptCache (T-040 / REQ-CTX-016..019 / SC-003).

Verifies:
- Cache hits and misses
- TTL expiration
- Multi-threaded concurrent access safety
- Per-tenant eviction via invalidate_user
- Graceful database fallback on cache failure or DB error
"""

from __future__ import annotations

import concurrent.futures
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from vistarae_core.domain.entities import UserPrompt
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.ports.repositories import IUserPromptRepository
from vistarae_core.services.prompt_cache import UserPromptCache


@pytest.fixture
def cache() -> UserPromptCache:
    """Fixture providing a fresh UserPromptCache instance."""
    return UserPromptCache(default_ttl_seconds=60.0)


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Fixture providing a mock IUserPromptRepository."""
    return AsyncMock(spec=IUserPromptRepository)


def test_cache_set_and_get_hit(cache: UserPromptCache) -> None:
    """Verify storing and retrieving prompt directives from cache."""
    user_id = uuid4()
    prompts = {
        PromptType.DESCRIPTION: "Focus on architectural landmarks.",
        PromptType.REASON_TO_VISIT: "Why an architecture lover should visit.",
    }
    cache.set(user_id, prompts)

    result = cache.get(user_id)
    assert result == prompts
    # Verify defensive copy
    assert result is not prompts


def test_cache_get_miss(cache: UserPromptCache) -> None:
    """Verify cache miss returns None for unknown tenant."""
    user_id = uuid4()
    assert cache.get(user_id) is None


def test_cache_ttl_expiration() -> None:
    """Verify entry expires after TTL seconds."""
    cache = UserPromptCache(default_ttl_seconds=0.05)
    user_id = uuid4()
    prompts = {PromptType.DESCRIPTION: "Short-lived prompt"}

    cache.set(user_id, prompts, ttl_seconds=0.05)
    assert cache.get(user_id) == prompts

    # Wait past TTL
    time.sleep(0.08)
    assert cache.get(user_id) is None


def test_cache_invalidate_user(cache: UserPromptCache) -> None:
    """Verify per-tenant invalidation evicts only target tenant."""
    user_a = uuid4()
    user_b = uuid4()

    prompts_a = {PromptType.DESCRIPTION: "Traveler A"}
    prompts_b = {PromptType.DESCRIPTION: "Traveler B"}

    cache.set(user_a, prompts_a)
    cache.set(user_b, prompts_b)

    cache.invalidate_user(user_a)

    assert cache.get(user_a) is None
    assert cache.get(user_b) == prompts_b


def test_cache_clear(cache: UserPromptCache) -> None:
    """Verify clear empties all tenant entries."""
    user_a = uuid4()
    user_b = uuid4()

    cache.set(user_a, {PromptType.DESCRIPTION: "A"})
    cache.set(user_b, {PromptType.DESCRIPTION: "B"})

    cache.clear()

    assert cache.get(user_a) is None
    assert cache.get(user_b) == None


def test_cache_thread_safety() -> None:
    """Verify concurrent reads, writes, and invalidations across multiple threads."""
    cache = UserPromptCache(default_ttl_seconds=10.0)
    users = [uuid4() for _ in range(20)]

    def worker(idx: int) -> None:
        user = users[idx % len(users)]
        prompts = {PromptType.DESCRIPTION: f"Directive from thread {idx}"}
        cache.set(user, prompts)
        val = cache.get(user)
        if val is not None:
            assert PromptType.DESCRIPTION in val
        if idx % 5 == 0:
            cache.invalidate_user(user)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(200)]
        concurrent.futures.wait(futures)
        for f in futures:
            f.result()  # Will raise if any thread raised an exception


@pytest.mark.asyncio
async def test_get_or_load_hits_cache(cache: UserPromptCache, mock_repo: AsyncMock) -> None:
    """Verify get_or_load returns cached data without calling database."""
    user_id = uuid4()
    prompts = {PromptType.DESCRIPTION: "Cached directive"}
    cache.set(user_id, prompts)

    result = await cache.get_or_load(user_id, mock_repo)

    assert result == prompts
    mock_repo.list_by_user.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_load_loads_and_populates_cache(cache: UserPromptCache, mock_repo: AsyncMock) -> None:
    """Verify get_or_load loads from repo on miss and stores in cache."""
    user_id = uuid4()
    prompt_record = UserPrompt(
        id=uuid4(),
        user_id=user_id,
        prompt_type=PromptType.REASON_TO_VISIT,
        prompt_text="Highlight culinary history.",
    )
    mock_repo.list_by_user.return_value = [prompt_record]

    result = await cache.get_or_load(user_id, mock_repo)

    assert result == {PromptType.REASON_TO_VISIT: "Highlight culinary history."}
    mock_repo.list_by_user.assert_called_once_with(user_id)

    # Next call should hit cache directly
    mock_repo.list_by_user.reset_mock()
    second_result = await cache.get_or_load(user_id, mock_repo)
    assert second_result == result
    mock_repo.list_by_user.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_load_repo_failure_graceful_fallback(cache: UserPromptCache, mock_repo: AsyncMock) -> None:
    """Verify get_or_load returns empty dict gracefully when database raises error."""
    user_id = uuid4()
    mock_repo.list_by_user.side_effect = RuntimeError("Database connection timed out")

    result = await cache.get_or_load(user_id, mock_repo)

    assert result == {}
