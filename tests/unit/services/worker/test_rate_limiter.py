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

"""Unit tests for in-memory interval rate limiter (T-019).

Verifies:
- Sustained 1.0 request/second spacing between calls
- First call executes immediately without delay
- Subsequent immediate calls are delayed by the remaining interval
- Concurrent asynchronous callers are serialized safely
"""

from __future__ import annotations

import asyncio
import time

import pytest

from services.worker.rate_limiter import InMemoryRateLimiter


@pytest.mark.asyncio
class TestInMemoryRateLimiter:
    """Verifies interval rate limiter timing and locking."""

    async def test_first_acquire_immediate(self) -> None:
        """Asserts initial acquire does not sleep."""
        limiter = InMemoryRateLimiter(interval_seconds=0.1)
        start = time.monotonic()
        slept = await limiter.acquire()
        elapsed = time.monotonic() - start

        assert slept == 0.0
        assert elapsed < 0.05

    async def test_subsequent_acquire_delayed(self) -> None:
        """Asserts immediate second acquire sleeps for the remaining interval."""
        interval = 0.1
        limiter = InMemoryRateLimiter(interval_seconds=interval)

        await limiter.acquire()
        start = time.monotonic()
        slept = await limiter.acquire()
        elapsed = time.monotonic() - start

        assert slept > 0.0
        assert elapsed >= (interval * 0.8)

    async def test_concurrent_callers_serialized(self) -> None:
        """Asserts concurrent tasks are paced sequentially."""
        interval = 0.05
        limiter = InMemoryRateLimiter(interval_seconds=interval)
        timestamps: list[float] = []

        async def worker():
            await limiter.acquire()
            timestamps.append(time.monotonic())

        start = time.monotonic()
        await asyncio.gather(worker(), worker(), worker())
        total_time = time.monotonic() - start

        assert len(timestamps) == 3
        # 3 calls spaced by 0.05s should take at least 2 intervals (>= 0.09s)
        assert total_time >= 0.08
        # Differences between consecutive calls should be >= 0.04s
        diff1 = timestamps[1] - timestamps[0]
        diff2 = timestamps[2] - timestamps[1]
        assert diff1 >= (interval * 0.8)
        assert diff2 >= (interval * 0.8)

    async def test_context_manager_usage(self) -> None:
        """Asserts async context manager works seamlessly."""
        limiter = InMemoryRateLimiter(interval_seconds=0.05)
        async with limiter:
            pass
        assert limiter.interval == 0.05
