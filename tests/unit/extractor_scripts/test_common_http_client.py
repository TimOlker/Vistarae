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

"""Unit tests for ResilientHttpClient verifying caching, rate limiting, and retries."""

import time
from pathlib import Path

import httpx
import pytest

from extractor_scripts.common.http_client import ResilientHttpClient


def test_http_client_cache_hit(tmp_path: Path) -> None:
    """Verifies that a cached response is returned on subsequent calls without hitting network."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text="<html><body>Hello World</body></html>")

    transport = httpx.MockTransport(mock_handler)
    client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=True,
        cache_dir=tmp_path / "cache",
        transport=transport,
    )

    url = "https://example.com/test_page"

    # First fetch: should trigger transport
    text1 = client.get(url)
    assert "Hello World" in text1
    assert call_count == 1

    # Second fetch: should hit cache
    text2 = client.get(url)
    assert text2 == text1
    assert call_count == 1

    client.close()


def test_http_client_cache_disabled(tmp_path: Path) -> None:
    """Verifies that when caching is disabled, every call hits the transport."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=f"Call {call_count}")

    transport = httpx.MockTransport(mock_handler)
    with ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        cache_dir=tmp_path / "cache",
        transport=transport,
    ) as client:
        t1 = client.get("https://example.com/nocache")
        t2 = client.get("https://example.com/nocache")
        assert t1 == "Call 1"
        assert t2 == "Call 2"
        assert call_count == 2


def test_http_client_retry_logic(tmp_path: Path) -> None:
    """Verifies exponential retry logic on 503 and 429 status codes."""
    attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, text="Success after retry")

    transport = httpx.MockTransport(mock_handler)
    with ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        cache_dir=tmp_path / "cache",
        transport=transport,
    ) as client:
        # Patch sleep to speed up test execution
        orig_sleep = time.sleep
        sleep_calls = []
        time.sleep = lambda s: sleep_calls.append(s)
        try:
            content = client.get("https://example.com/retry_endpoint")
            assert content == "Success after retry"
            assert attempts == 3
            assert len(sleep_calls) >= 2
        finally:
            time.sleep = orig_sleep


def test_http_client_non_retryable_error(tmp_path: Path) -> None:
    """Verifies that 404 Not Found is not retried and raises HTTPStatusError."""
    attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(mock_handler)
    with ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=False,
        cache_dir=tmp_path / "cache",
        transport=transport,
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get("https://example.com/missing")
        assert attempts == 1


def test_http_client_rate_limiting(tmp_path: Path) -> None:
    """Verifies that politeness delay sleeps when queries are too close."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(mock_handler)
    with ResilientHttpClient(
        delay_seconds=1.0,
        cache_enabled=False,
        cache_dir=tmp_path / "cache",
        transport=transport,
    ) as client:
        sleep_durations = []
        orig_sleep = time.sleep
        time.sleep = lambda s: sleep_durations.append(s)
        try:
            client.get("https://example.com/p1")
            client.get("https://example.com/p2")
            assert len(sleep_durations) == 1
            assert sleep_durations[0] > 0
        finally:
            time.sleep = orig_sleep


def test_http_client_cache_io_errors(tmp_path: Path, monkeypatch) -> None:
    """Verifies graceful handling of OSError during cache read and write."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    transport = httpx.MockTransport(mock_handler)
    client = ResilientHttpClient(
        delay_seconds=0.0,
        cache_enabled=True,
        cache_dir=tmp_path / "cache",
        transport=transport,
    )

    # Monkeypatch write_text to simulate disk full / permission error
    def failing_write(*args, **kwargs):
        raise OSError("Disk full")

    monkeypatch.setattr(Path, "write_text", failing_write)
    # Should not raise exception
    res = client.get("https://example.com/cache_fail")
    assert res == "OK"
    client.close()
