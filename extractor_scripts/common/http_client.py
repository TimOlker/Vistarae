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

"""Resilient HTTP client with rate-limiting, disk caching, and exponential backoff retry."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "VistaraeDataExtractor/1.0 (Travel POI Research Engine; contact: dev@vistarae.local)"
)
DEFAULT_CACHE_DIR = Path(".cache/extractors")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ResilientHttpClient:
    """HTTP client enforcing domain rate-limiting, response caching, and retries."""

    def __init__(
        self,
        delay_seconds: float = 1.0,
        cache_enabled: bool = True,
        cache_dir: Path | None = None,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initializes the HTTP client.

        Args:
            delay_seconds: Minimum delay in seconds between calls to the same hostname.
            cache_enabled: Whether to read and write responses to local filesystem cache.
            cache_dir: Directory where cached HTML responses are stored.
            transport: Optional custom HTTPX transport (for mocking in unit tests).
            user_agent: User-Agent header value transmitted with requests.
            timeout_seconds: Network request timeout in seconds.
        """
        self.delay_seconds = max(0.0, delay_seconds)
        self.cache_enabled = cache_enabled
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

        self._last_request_times: dict[str, float] = {}
        self._client = httpx.Client(
            transport=transport,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def __enter__(self) -> ResilientHttpClient:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit, closing underlying HTTP transport."""
        self.close()

    def close(self) -> None:
        """Closes the underlying HTTP transport."""
        self._client.close()

    def _get_cache_path(self, url: str) -> Path:
        """Computes the cached file path for a URL.

        Args:
            url: Target URL.

        Returns:
            Path object pointing to the cached file on disk.
        """
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / domain / f"{url_hash}.html"

    def _read_cache(self, url: str) -> str | None:
        """Reads a cached response from disk if present.

        Args:
            url: Target URL.

        Returns:
            Cached HTML content string if found, otherwise None.
        """
        if not self.cache_enabled:
            return None
        cache_path = self._get_cache_path(url)
        if cache_path.is_file():
            try:
                return cache_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read cache file %s: %s", cache_path, exc)
        return None

    def _write_cache(self, url: str, content: str) -> None:
        """Writes response content to disk cache.

        Args:
            url: Target URL.
            content: Raw response text to store.
        """
        if not self.cache_enabled:
            return
        cache_path = self._get_cache_path(url)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write cache file %s: %s", cache_path, exc)

    def _enforce_rate_limit(self, domain: str) -> None:
        """Enforces politeness delay before querying the specified domain.

        Args:
            domain: Network hostname of the target server.
        """
        last_time = self._last_request_times.get(domain)
        if last_time is not None:
            elapsed = time.monotonic() - last_time
            if elapsed < self.delay_seconds:
                sleep_time = self.delay_seconds - elapsed
                time.sleep(sleep_time)
        self._last_request_times[domain] = time.monotonic()

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_retries: int = 3,
    ) -> str:
        """Fetches a URL with caching, rate-limiting, and exponential backoff retry.

        Args:
            url: Fully qualified target URL.
            params: Optional query parameters.
            headers: Optional additional request headers.
            max_retries: Maximum number of retry attempts for transient errors.

        Returns:
            Response body decoded as a string.

        Raises:
            httpx.HTTPStatusError: If a non-retryable 4xx error occurs.
            httpx.RequestError: If all retries are exhausted.
        """
        cached = self._read_cache(url)
        if cached is not None:
            return cached

        domain = urlparse(url).netloc
        attempt = 0
        backoff = 1.0

        while attempt <= max_retries:
            self._enforce_rate_limit(domain)
            try:
                response = self._client.get(url, params=params, headers=headers)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    attempt += 1
                    if attempt > max_retries:
                        response.raise_for_status()
                    logger.warning(
                        "HTTP %d from %s, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        url,
                        backoff,
                        attempt,
                        max_retries,
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue

                response.raise_for_status()
                text = response.text
                self._write_cache(url, text)
                return text

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > max_retries:
                    raise exc
                logger.warning(
                    "Network error %s from %s, retrying in %.1fs (attempt %d/%d)",
                    exc,
                    url,
                    backoff,
                    attempt,
                    max_retries,
                )
                time.sleep(backoff)
                backoff *= 2.0

        raise httpx.RequestError(f"Failed to fetch {url} after {max_retries} retries")
