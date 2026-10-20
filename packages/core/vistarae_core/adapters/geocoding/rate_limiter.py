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

"""Token bucket rate limiter for external geocoding providers (T-021).

Enforces strict 1 request per second sustained rate limiting adhering to
external provider and OSM/Nominatim usage policies.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Thread-safe asynchronous token bucket rate limiter."""

    def __init__(self, rate_per_second: float = 1.0, capacity: float = 1.0) -> None:
        """Initializes rate limiter.

        Args:
            rate_per_second: Number of tokens replenished per second.
            capacity: Maximum bucket burst capacity.
        """
        self._rate = rate_per_second
        self._capacity = capacity
        self._tokens = capacity
        self._last_updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquires a token, asynchronously sleeping if the bucket is exhausted."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_updated
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_updated = now

            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
                self._last_updated = time.monotonic()
            else:
                self._tokens -= 1.0
