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

"""Unit tests for EnhancedLocationResolver and encyclopedic/AI geocoding fallbacks."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.poi.services.enhanced_location_resolver import (
    EnhancedLocationResolver,
)
from services.poi.services.geocoding_service import GeocodingService


def test_enhanced_resolver_wikipedia_coordinates() -> None:
    """Verifies that Wikipedia search returns canonical title and page coordinates."""
    mock_client = AsyncMock()

    def mock_get(url: str, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "list=search" in url:
            resp.json.return_value = {
                "query": {
                    "search": [
                        {"title": "Okapi Wildlife Reserve", "pageid": 565700}
                    ]
                }
            }
        elif "prop=coordinates" in url:
            resp.json.return_value = {
                "query": {
                    "pages": {
                        "565700": {
                            "title": "Okapi Wildlife Reserve",
                            "coordinates": [{"lat": 2.0, "lon": 28.5}],
                        }
                    }
                }
            }
        else:
            resp.json.return_value = {}
        return resp

    mock_client.get = AsyncMock(side_effect=mock_get)

    resolver = EnhancedLocationResolver(http_client=mock_client)
    candidates = asyncio.run(resolver.resolve_canonical_poi("Okapi Faunal Reserve"))

    assert len(candidates) >= 1
    top = candidates[0]
    assert top.canonical_name == "Okapi Wildlife Reserve"
    assert top.latitude == 2.0
    assert top.longitude == 28.5
    assert top.source == "wikipedia_coordinates"


def test_enhanced_resolver_suffix_stripping() -> None:
    """Verifies that common travel suffixes are stripped to canonical base landmarks."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"query": {"search": []}}
    mock_client.get = AsyncMock(return_value=mock_resp)

    resolver = EnhancedLocationResolver(http_client=mock_client)
    candidates = asyncio.run(resolver.resolve_canonical_poi("Bamburgh Castle - Visitor Center"))

    # Suffix stripping should produce "Bamburgh Castle"
    names = [c.canonical_name for c in candidates]
    assert "Bamburgh Castle" in names


def test_enhanced_resolver_gemini_fallback() -> None:
    """Verifies Gemini Flash-Lite fallback when encyclopedic sources return no results."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"query": {"search": []}}
    mock_client.get = AsyncMock(return_value=mock_resp)

    # Mock Google GenAI client
    mock_genai = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"canonical_name": "Ngorongoro Conservation Area", '
        '"country": "Tanzania", "state_province": "Arusha", "city": null, "is_known_poi": true}'
    )
    mock_genai.models.generate_content.return_value = mock_response

    resolver = EnhancedLocationResolver(http_client=mock_client, gemini_client=mock_genai)
    # Ensure env var is set for test
    import os
    os.environ["GEMINI_API_KEY"] = "mock_key_for_test"

    try:
        candidates = asyncio.run(
            resolver.resolve_canonical_poi("Ngorongoro Crater Conservation Area")
        )
        llm_match = next((c for c in candidates if c.source == "gemini_flash_lite"), None)
        assert llm_match is not None
        assert llm_match.canonical_name == "Ngorongoro Conservation Area"
        assert llm_match.country == "Tanzania"
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


def test_enhanced_resolver_gemini_transliteration_yemen() -> None:
    """Verifies that non-standard transliterations like 'Barakesh' resolve to 'Baraqish' via Gemini."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"query": {"search": []}}
    mock_client.get = AsyncMock(return_value=mock_resp)

    mock_genai = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '{"canonical_name": "Baraqish", "country": "Yemen", '
        '"state_province": "Al Jawf", "alternate_names": ["Barakesh", "Barakish", "Yathill"], '
        '"is_known_poi": true}'
    )
    mock_genai.models.generate_content.return_value = mock_response

    resolver = EnhancedLocationResolver(http_client=mock_client, gemini_client=mock_genai)
    import os
    os.environ["GEMINI_API_KEY"] = "mock_key_for_test"

    try:
        candidates = asyncio.run(
            resolver.resolve_canonical_poi("Barakesh", country_hint="Yemen")
        )
        canonical = next((c for c in candidates if c.canonical_name == "Baraqish"), None)
        assert canonical is not None
        assert canonical.country == "Yemen"

        # Alternate transliterations should also be included
        alt_names = [c.canonical_name for c in candidates]
        assert "Barakish" in alt_names or "Yathill" in alt_names
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


def test_geocoding_service_cascades_to_enhanced_resolver() -> None:
    """Verifies GeocodingService cascades to enhanced resolver when Nominatim returns 0 results."""
    from vistarae_core.ports.repositories import IGeocodingCacheRepository
    from vistarae_core.domain.entities import GeocodingCacheEntry

    class InMemoryGeocache(IGeocodingCacheRepository):
        def __init__(self):
            self.store = {}
        async def get(self, q_hash: str):
            return self.store.get(q_hash)
        async def set(self, entry: GeocodingCacheEntry):
            self.store[entry.query_hash] = entry

    cache = InMemoryGeocache()
    mock_client = AsyncMock()

    # Call sequence:
    # 1. Nominatim "Okapi Faunal Reserve" -> empty []
    # 2. Wikipedia search "Okapi Faunal Reserve" -> "Okapi Wildlife Reserve"
    # 3. Nominatim "Okapi Wildlife Reserve" -> found!
    def mock_http(url: str, params=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "nominatim.openstreetmap.org/search" in url:
            q = (params or {}).get("q", "")
            if "Faunal" in q:
                resp.json.return_value = []
            elif "Wildlife" in q:
                resp.json.return_value = [
                    {
                        "lat": "1.7209",
                        "lon": "28.5235",
                        "display_name": "Réserve de faune à okapis, Ituri, Democratic Republic of the Congo",
                        "name": "Réserve de faune à okapis",
                        "address": {
                            "nature_reserve": "Réserve de faune à okapis",
                            "state": "Ituri",
                            "country": "Democratic Republic of the Congo",
                            "country_code": "cd",
                        },
                    }
                ]
            else:
                resp.json.return_value = []
        elif "en.wikipedia.org" in url and "list=search" in url:
            resp.json.return_value = {
                "query": {
                    "search": [{"title": "Okapi Wildlife Reserve", "pageid": 565700}]
                }
            }
        elif "en.wikipedia.org" in url and "prop=coordinates" in url:
            resp.json.return_value = {"query": {"pages": {"565700": {"coordinates": []}}}}
        else:
            resp.json.return_value = {}
        return resp

    mock_client.get = AsyncMock(side_effect=mock_http)

    service = GeocodingService(cache_repo=cache, http_client=mock_client)
    lat, lon, addrs, cached = asyncio.run(service.geocode("Okapi Faunal Reserve"))

    assert lat is not None
    assert lon is not None
    assert pytest.approx(lat, abs=0.01) == 1.72
    assert pytest.approx(lon, abs=0.01) == 28.52
    assert len(addrs) > 0
    assert addrs[0].country == "Democratic Republic of the Congo"
    assert addrs[0].raw_geocoding.get("resolved_name") == "Okapi Wildlife Reserve"

    # Verify both the original query and canonical query were cached!
    from services.poi.services.geocoding_service import compute_query_hash
    orig_hash = compute_query_hash("Okapi Faunal Reserve")
    canon_hash = compute_query_hash("Okapi Wildlife Reserve")
    assert orig_hash in cache.store
    assert canon_hash in cache.store

