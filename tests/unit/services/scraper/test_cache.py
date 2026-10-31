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

"""Unit tests for ScraperCacheManager (T-010)."""

from __future__ import annotations

from pathlib import Path

from services.scraper.cache import ScraperCacheManager, compute_cache_key


def test_compute_cache_key_deterministic() -> None:
    """Verifies that cache keys normalize tokens, coordinates, and tag ordering."""
    k1 = compute_cache_key(
        ["Japan", "Tokyo", "Senso-ji"], 35.714801, 139.796701, ["temple", "tokyo"]
    )
    k2 = compute_cache_key(
        ["japan", "tokyo", "senso-ji"], 35.714804, 139.796704, ["tokyo", "temple"]
    )
    assert k1 == k2
    assert len(k1) == 64


def test_scraper_cache_manager_crud(tmp_path: Path) -> None:
    """Verifies cache storage, retrieval, and replacement."""
    db_file = tmp_path / "test_cache.db"
    manager = ScraperCacheManager(db_path=db_file)

    key = "test_hash_123"
    assert manager.get(key) is None

    payload = {"poi_name": "Senso-ji", "country": "Japan", "confidence": 95}
    manager.set(key, payload)

    cached = manager.get(key)
    assert cached is not None
    assert cached["poi_name"] == "Senso-ji"
    assert cached["country"] == "Japan"

    # Replace
    payload["confidence"] = 99
    manager.set(key, payload)
    updated = manager.get(key)
    assert updated is not None
    assert updated["confidence"] == 99
