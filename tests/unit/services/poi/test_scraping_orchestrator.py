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

"""Unit tests for ScrapingOrchestrator, secondary adapters, and timeout fallback (T-023).

Validates:
- Secondary source augmentation (REQ-EXT-018, REQ-EXT-019)
- 3.0s timeout ceiling and graceful partial fallback (REQ-EXT-020)
- Vetted tag recommendation matching with overlapping aliases (REQ-EXT-029)
- 1:1 schema parity: unassigned star rating, null photo folders (REQ-EXT-015, REQ-EXT-016)
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.poi.scraping.orchestrator import ScrapingOrchestrator
from services.poi.scraping.secondary_sources import (
    SecondarySourceAdapter,
    WikipediaAdapter,
)
from services.poi.scraping.tag_matcher import TagMatcher


class SlowMockAdapter(SecondarySourceAdapter):
    """Adapter that sleeps longer than timeout to test graceful degradation."""

    @property
    def domain(self) -> str:
        return "slowsource.com"

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: Any = None,
    ) -> dict[str, Any]:
        await asyncio.sleep(1.0)
        return {"source_name": "slowsource.com", "description": "Too late"}


class FaultyMockAdapter(SecondarySourceAdapter):
    """Adapter that raises an HTTP exception to test error handling."""

    @property
    def domain(self) -> str:
        return "faultysource.com"

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: Any = None,
    ) -> dict[str, Any]:
        raise RuntimeError("Remote 503 Service Unavailable")


@pytest.mark.asyncio
class TestScrapingOrchestrator:
    """Test suite for ScrapingOrchestrator and secondary sources."""

    async def test_clean_page_title(self) -> None:
        """Verifies removal of branding suffixes from page titles."""
        clean = ScrapingOrchestrator.clean_page_title(
            "Bamburgh Castle - Wikipedia", "https://en.wikipedia.org/wiki/Bamburgh_Castle"
        )
        assert clean == "Bamburgh Castle"

        clean_ta = ScrapingOrchestrator.clean_page_title(
            "Eiffel Tower | TripAdvisor", "https://tripadvisor.com/eiffel"
        )
        assert clean_ta == "Eiffel Tower"

    async def test_wikipedia_adapter_mock_response(self) -> None:
        """Verifies WikipediaAdapter extracts coordinates, thumbnail, and summary."""
        adapter = WikipediaAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "extract": "Bamburgh Castle is a coastal castle in Northumberland.",
            "coordinates": {"lat": 55.6089, "lon": -1.7099},
            "thumbnail": {"source": "https://upload.wikimedia.org/bamburgh.jpg"},
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Bamburgh_Castle"}},
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        res = await adapter.augment("Bamburgh Castle", client=mock_client)
        assert res["source_name"] == "wikipedia.org"
        assert res["latitude"] == 55.6089
        assert res["longitude"] == -1.7099
        assert res["hero_image_url"] == "https://upload.wikimedia.org/bamburgh.jpg"
        assert "Northumberland" in res["description"]

    async def test_orchestrator_graceful_timeout_fallback(self) -> None:
        """Verifies orchestrator continues with primary data when secondary source times out (REQ-EXT-020)."""
        orchestrator = ScrapingOrchestrator(
            gemini_api_key=None,
            secondary_adapters=[SlowMockAdapter()],
            timeout_seconds=0.1,  # Short timeout for fast test
        )

        candidate, recommended_tags = await orchestrator.orchestrate(
            source_url="https://travelblog.example.com/castles",
            page_title="Awesome Scottish Castle",
            selected_text="A dramatic medieval fortress situated high above the ocean.",
            valid_scraping_domains=["slowsource.com"],
        )

        # Should not raise TimeoutError; should return candidate using primary data
        assert candidate.name == "Awesome Scottish Castle"
        assert "medieval fortress" in candidate.description
        assert candidate.rating is None  # REQ-EXT-016
        assert candidate.source_type == "Web"

    async def test_orchestrator_graceful_error_fallback(self) -> None:
        """Verifies orchestrator handles secondary adapter exceptions without aborting (REQ-EXT-020)."""
        orchestrator = ScrapingOrchestrator(
            gemini_api_key=None,
            secondary_adapters=[FaultyMockAdapter()],
            timeout_seconds=1.0,
        )

        candidate, _ = await orchestrator.orchestrate(
            source_url="https://travelblog.example.com/ruins",
            page_title="Ancient Roman Ruins",
            selected_text="Columns dating back to 200 AD.",
            valid_scraping_domains=["faultysource.com"],
        )

        assert candidate.name == "Ancient Roman Ruins"
        assert "200 AD" in candidate.description

    async def test_orchestrator_respects_valid_scraping_domains(self) -> None:
        """Verifies unapproved secondary sources are omitted (REQ-EXT-019)."""
        wiki_adapter = WikipediaAdapter()
        with patch.object(wiki_adapter, "augment", new_callable=AsyncMock) as mock_wiki:
            orchestrator = ScrapingOrchestrator(
                gemini_api_key=None,
                secondary_adapters=[wiki_adapter],
            )

            # user allows ONLY tripadvisor.com, NOT wikipedia.org
            await orchestrator.orchestrate(
                source_url="https://example.com/palace",
                page_title="Grand Palace",
                valid_scraping_domains=["tripadvisor.com"],
            )

            mock_wiki.assert_not_called()

    async def test_tag_matcher_with_overlapping_aliases(self) -> None:
        """Verifies overlapping aliases recommend all candidate tags (REQ-EXT-029)."""
        tags = [
            {
                "slug": "fortification",
                "name": "Fortification",
                "aliases": ["castle", "fort", "citadel"],
            },
            {
                "slug": "historic",
                "name": "Historic",
                "aliases": ["castle", "ancient", "heritage"],
            },
            {
                "slug": "nature_reserve",
                "name": "Nature Reserve",
                "aliases": ["wilderness", "wildlife"],
            },
        ]

        matcher = TagMatcher(tags)

        # "castle" alias overlaps across "fortification" and "historic"
        matched = matcher.match_tags("We visited an ancient castle near the coast.")
        assert "fortification" in matched
        assert "historic" in matched
        assert "nature_reserve" not in matched
