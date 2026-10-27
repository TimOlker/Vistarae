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

"""Benchmark test for UserPromptCache retrieval latency (T-041 / SC-003).

Success Criterion SC-003:
In-memory prompt cache resolution executes in under 2 milliseconds for 99%
of capture requests (< 2ms p99 latency).
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from vistarae_core.domain.value_objects import PromptType
from vistarae_core.services.prompt_cache import UserPromptCache


def test_cache_retrieval_sub_2ms_p99() -> None:
    """Benchmark asserting 99% of in-memory prompt cache retrievals complete in < 2.0ms."""
    cache = UserPromptCache(default_ttl_seconds=300.0)
    user_id = uuid4()
    prompts = {
        PromptType.DESCRIPTION: "Focus on hidden architectural wonders, gothic cathedrals, and quiet cobblestone streets.",
        PromptType.REASON_TO_VISIT: "Highlight historical significance, preservation details, and peaceful ambiance.",
        PromptType.TIME_SPENT: "Allocate 2 to 3 hours for deep exploration.",
    }
    cache.set(user_id, prompts)

    # Warmup
    for _ in range(50):
        cache.get(user_id)

    # Benchmark 1000 iterations
    latencies_ms: list[float] = []
    iterations = 1000

    for _ in range(iterations):
        start = time.perf_counter()
        result = cache.get(user_id)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)
        assert result is not None

    latencies_ms.sort()
    # 99th percentile index
    p99_idx = int(0.99 * iterations)
    p99_latency_ms = latencies_ms[p99_idx]
    mean_latency_ms = sum(latencies_ms) / iterations

    print(f"\n[CACHE BENCHMARK] Mean: {mean_latency_ms:.4f}ms | p99: {p99_latency_ms:.4f}ms (threshold: 2.0ms)")

    assert p99_latency_ms < 2.0, f"p99 latency {p99_latency_ms:.4f}ms exceeded 2.0ms threshold"
