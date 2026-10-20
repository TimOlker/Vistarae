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

"""In-memory rate limiter coordinating sustained 1.0 req/sec pacing (T-023).

Enforces OpenStreetMap Nominatim rate-limiting policy (strictly <= 1 req/sec)
within worker process memory under single-worker concurrency (ReservedConcurrentExecutions: 1).
Bypasses database lock contention on Neon PgBouncer transaction-mode connection pools.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any


class InMemoryRateLimiter:
    """Asynchronous interval rate limiter pacing external HTTP requests."""

    def __init__(self, interval_seconds: float = 1.0) -> None:
        """Initializes rate limiter with interval spacing.

        Args:
            interval_seconds: Minimum seconds between subsequent acquires (default: 1.0s).
        """
        self._interval = interval_seconds
        self._last_acquire_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def interval(self) -> float:
        """Returns the configured minimum interval in seconds."""
        return self._interval

    async def acquire(self) -> float:
        """Serializes concurrent callers and delays until the minimum interval elapses.

        Returns:
            Float seconds slept (0.0 if sufficient time had already elapsed).
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_acquire_time
            slept = 0.0
            if elapsed < self._interval:
                slept = self._interval - elapsed
                await asyncio.sleep(slept)
                self._last_acquire_time = time.monotonic()
            else:
                self._last_acquire_time = now
            return slept

    async def __aenter__(self) -> InMemoryRateLimiter:
        """Async context manager entry pacing execution."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        pass
