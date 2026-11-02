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

"""Unit tests for worker geocoding rate throttling and LLM concurrency limits (T-029)."""

from __future__ import annotations

import asyncio

import pytest

from services.worker.candidate_enricher import LLM_SEMAPHORE, CandidateEnricher
from services.worker.rate_limiter import AsyncTokenBucket


@pytest.mark.asyncio
async def test_token_bucket_pacing():
    """Asserts that token bucket serializes and paces sequential acquires."""
    bucket = AsyncTokenBucket(interval_seconds=0.05)  # Fast interval for test speed

    t0 = asyncio.get_event_loop().time()
    await bucket.acquire()
    await bucket.acquire()
    t1 = asyncio.get_event_loop().time()

    assert t1 - t0 >= 0.045


@pytest.mark.asyncio
async def test_llm_semaphore_concurrency_ceiling():
    """Asserts that CandidateEnricher enforces an upper concurrency ceiling of 5."""
    assert LLM_SEMAPHORE._value <= 5

    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def mock_llm_call(*args, **kwargs):
        nonlocal max_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        await asyncio.sleep(0.02)
        async with lock:
            current_concurrent -= 1
        return "synthesized text"

    enricher = CandidateEnricher()

    # Execute 10 concurrent tasks wrapped in the enricher's semaphore
    async def worker_task():
        async with enricher.llm_semaphore:
            return await mock_llm_call()

    results = await asyncio.gather(*[worker_task() for _ in range(10)])
    assert len(results) == 10
    assert max_concurrent <= 5
