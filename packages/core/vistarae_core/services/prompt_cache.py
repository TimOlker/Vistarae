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

"""Process-level thread-safe in-memory cache for tenant prompt directives.

Implements Phase 11 Requirements (REQ-CTX-016, REQ-CTX-017, REQ-CTX-018, REQ-CTX-019)
and Constitution Operational Guardrails (Zero-Cost Architecture):
- Fast sub-2ms in-memory resolution of prompt directives
- Absolute TTL expiration (default: 300 seconds)
- Thread-safe synchronization via threading.Lock
- Immediate per-tenant invalidation upon travel style mutation or user deletion
- Graceful database fallback on miss or cache error
"""

from __future__ import annotations

import logging
import threading
import time
from uuid import UUID

from vistarae_core.domain.value_objects import PromptType
from vistarae_core.ports.repositories import IUserPromptRepository

logger = logging.getLogger(__name__)


class UserPromptCache:
    """Thread-safe process-level in-memory cache for user prompt directives."""

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        """Initializes prompt cache with a default TTL in seconds.

        Args:
            default_ttl_seconds: Duration in seconds before cache entries expire.
        """
        self._default_ttl_seconds = default_ttl_seconds
        self._cache: dict[UUID, tuple[float, dict[PromptType, str]]] = {}
        self._lock = threading.Lock()

    def get(self, user_id: UUID) -> dict[PromptType, str] | None:
        """Retrieves cached prompt directives if present and unexpired.

        Args:
            user_id: Owning tenant UUID.

        Returns:
            Dictionary of prompt directives or None if missing/expired.
        """
        with self._lock:
            entry = self._cache.get(user_id)
            if entry is None:
                return None
            expires_at, prompts = entry
            if time.monotonic() > expires_at:
                self._cache.pop(user_id, None)
                return None
            return dict(prompts)

    def set(
        self,
        user_id: UUID,
        prompts: dict[PromptType, str],
        ttl_seconds: float | None = None,
    ) -> None:
        """Stores prompt directives in cache with an expiration timestamp.

        Args:
            user_id: Owning tenant UUID.
            prompts: Dictionary of prompt directives.
            ttl_seconds: Optional custom TTL override.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        expires_at = time.monotonic() + ttl
        with self._lock:
            self._cache[user_id] = (expires_at, dict(prompts))

    def invalidate_user(self, user_id: UUID) -> None:
        """Immediately evicts cached prompt directives for a tenant.

        Args:
            user_id: Owning tenant UUID.
        """
        with self._lock:
            self._cache.pop(user_id, None)

    def clear(self) -> None:
        """Clears all cached entries across all tenants."""
        with self._lock:
            self._cache.clear()

    async def get_or_load(
        self,
        user_id: UUID,
        repo: IUserPromptRepository,
    ) -> dict[PromptType, str]:
        """Resolves prompt directives from cache, falling back to database repo on miss or error.

        Args:
            user_id: Owning tenant UUID.
            repo: IUserPromptRepository database implementation.

        Returns:
            Dictionary mapping PromptType to directive text.
        """
        try:
            cached = self.get(user_id)
            if cached is not None:
                return cached
        except Exception as exc:
            logger.warning("Cache read error for user %s: %s", user_id, exc)

        try:
            db_prompts = await repo.list_by_user(user_id)
            prompt_dict: dict[PromptType, str] = {p.prompt_type: p.prompt_text for p in db_prompts}
            try:
                self.set(user_id, prompt_dict)
            except Exception as exc:
                logger.warning("Cache write error for user %s: %s", user_id, exc)
            return prompt_dict
        except Exception as exc:
            logger.error(
                "Failed to load prompt directives from database for user %s: %s", user_id, exc
            )
            return {}


default_prompt_cache = UserPromptCache()
