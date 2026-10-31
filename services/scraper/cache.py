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

"""Local SQLite cache manager for the Photo Scraper CLI (T-010).

Adheres to:
- REQ-SCR-033: Local SQLite persistent cache before dispatching LLM or geocoding requests.
- SHA-256 deterministic keying of path tokens, rounded coordinates, and tags.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def compute_cache_key(
    path_tokens: Sequence[str],
    latitude: Decimal | float | None = None,
    longitude: Decimal | float | None = None,
    tags: Sequence[str] | None = None,
) -> str:
    """Computes a deterministic SHA-256 cache key from input metadata.

    Args:
        path_tokens: Cleaned directory or path tokens.
        latitude: Optional latitude.
        longitude: Optional longitude.
        tags: Optional discovered keywords or tags.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    normalized_tokens = [t.strip().lower() for t in path_tokens if t.strip()]

    lat_str = f"{float(latitude):.5f}" if latitude is not None else ""
    lon_str = f"{float(longitude):.5f}" if longitude is not None else ""

    norm_tags = sorted(t.strip().lower() for t in (tags or []) if t.strip())

    key_payload = {
        "tokens": normalized_tokens,
        "lat": lat_str,
        "lon": lon_str,
        "tags": norm_tags,
    }
    raw_bytes = json.dumps(key_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class ScraperCacheManager:
    """Manages persistent SQLite storage of resolved POI locations."""

    def __init__(self, db_path: Path | str = ".scraper_cache.db") -> None:
        """Initializes the SQLite cache database.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection to the SQLite database.

        Returns:
            Configured sqlite3.Connection.
        """
        return sqlite3.connect(self.db_path, timeout=10.0)

    def _init_db(self) -> None:
        """Creates the cache table and indices if they do not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS location_cache (
                    query_hash TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, query_hash: str) -> dict[str, Any] | None:
        """Retrieves a cached location resolution dictionary.

        Args:
            query_hash: SHA-256 key of the query.

        Returns:
            Cached response dictionary if found, else None.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT response_json FROM location_cache WHERE query_hash = ?",
                (query_hash,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def set(self, query_hash: str, response: dict[str, Any]) -> None:
        """Stores a resolved location in the cache.

        Args:
            query_hash: SHA-256 key of the query.
            response: Serialized dictionary response to persist.
        """
        now_iso = datetime.now(UTC).isoformat()
        payload = json.dumps(response)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO location_cache (query_hash, response_json, created_at)
                VALUES (?, ?, ?)
                """,
                (query_hash, payload, now_iso),
            )
            conn.commit()
