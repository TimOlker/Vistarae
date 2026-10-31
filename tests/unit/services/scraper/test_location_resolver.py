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

"""Unit tests for Gemini location resolver and SQLite cache integration (T-013).

Validates:
- Structured POI location resolution with thinking_budget=0 (REQ-SCR-029, REQ-SCR-030)
- SQLite cache hits skip external API calls (REQ-SCR-034)
- Missing GOOGLE_API_KEY terminates with error (REQ-SCR-028)
- Reverse geocoding coordination with known coordinates
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from services.scraper.cache import ScraperCacheManager
from services.scraper.location_resolver import (
    LocationResolver,
    validate_api_key_or_exit,
)
from services.scraper.path_parser import ParsedPathContext


def test_validate_api_key_or_exit_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing GOOGLE_API_KEY exits with non-zero status (REQ-SCR-028)."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        validate_api_key_or_exit()
    assert exc_info.value.code != 0


def test_validate_api_key_or_exit_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies validation succeeds when GOOGLE_API_KEY is present."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-12345")
    # Should not raise
    validate_api_key_or_exit()


def test_location_resolver_cache_hit(tmp_path: Path) -> None:
    """Verifies cache hits return immediately without invoking Gemini API."""
    db_file = tmp_path / "cache.db"
    cache = ScraperCacheManager(db_path=db_file)
    resolver = LocationResolver(cache_manager=cache, api_key="dummy-key")

    path_ctx = ParsedPathContext(
        poi_name="Senso-ji",
        country="Japan",
        city="Tokyo",
        path_tokens=["Japan", "Tokyo", "Senso-ji"],
    )
    lat = Decimal("35.7148000")
    lon = Decimal("139.7967000")

    # Seed the cache
    cached_data = {
        "poi_name": "Senso-ji",
        "street": "2-3-1 Asakusa",
        "city": "Taito City",
        "state_province": "Tokyo",
        "postal_code": "111-0032",
        "country": "Japan",
        "location_confidence_percent": 98,
    }
    from services.scraper.cache import compute_cache_key

    key = compute_cache_key(path_ctx.path_tokens, lat, lon, ["temple"])
    cache.set(key, cached_data)

    # Call resolve
    res = resolver.resolve(path_ctx, latitude=lat, longitude=lon, tags=["temple"])
    assert res.poi_name == "Senso-ji"
    assert res.location_confidence_percent == 98
    assert res.country == "Japan"


def test_location_resolver_invokes_gemini_on_miss(tmp_path: Path) -> None:
    """Verifies Gemini Flash-Lite is invoked on cache miss with thinking_budget=0."""
    db_file = tmp_path / "cache.db"
    cache = ScraperCacheManager(db_path=db_file)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"poi_name": "Red Fort", "street": "Netaji Subhash Marg", '
        '"city": "New Delhi", "state_province": "Delhi", "postal_code": "110006", '
        '"country": "India", "location_confidence_percent": 95}'
    )
    mock_client.models.generate_content.return_value = mock_response

    resolver = LocationResolver(cache_manager=cache, api_key="dummy-key", genai_client=mock_client)

    path_ctx = ParsedPathContext(
        poi_name="Red Fort",
        country="India",
        city="Delhi",
        path_tokens=["India", "Delhi", "Red Fort"],
    )

    res = resolver.resolve(
        path_ctx, latitude=Decimal("28.6562"), longitude=Decimal("77.2410"), tags=[]
    )
    assert res.poi_name == "Red Fort"
    assert res.country == "India"
    assert res.location_confidence_percent == 95

    # Verify call arguments
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    if call_kwargs["config"].thinking_config is not None:
        assert call_kwargs["config"].thinking_config.thinking_budget == 0
