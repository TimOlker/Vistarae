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

    async def test_clean_page_title_branding_suffixes(self) -> None:
        """Verifies stripping of Google Maps and platform branding while preserving hyphens (REQ: FR-001)."""
        assert (
            ScrapingOrchestrator.clean_page_title(
                "Eltz Castle - Google Maps", "https://maps.google.com/?cid=123"
            )
            == "Eltz Castle"
        )
        assert (
            ScrapingOrchestrator.clean_page_title(
                "Baden-Baden Thermal Baths - Google Maps", "https://maps.google.com"
            )
            == "Baden-Baden Thermal Baths"
        )
        assert (
            ScrapingOrchestrator.clean_page_title(
                "Stratford-upon-Avon | TripAdvisor", "https://tripadvisor.com"
            )
            == "Stratford-upon-Avon"
        )
        assert (
            ScrapingOrchestrator.clean_page_title(
                "Yosemite Falls • Yelp", "https://yelp.com/biz/yosemite"
            )
            == "Yosemite Falls"
        )

    async def test_wikipedia_adapter_opensearch_fallback(self) -> None:
        """Verifies Wikipedia 2-step OpenSearch fallback when direct summary returns 404 (REQ: FR-002, FR-003, T-007, T-009)."""
        adapter = WikipediaAdapter()

        # Step 1 response: 404 Not Found for raw query
        resp_404 = MagicMock()
        resp_404.status_code = 404

        # Step 2 response: OpenSearch returns canonical match
        resp_opensearch = MagicMock()
        resp_opensearch.status_code = 200
        resp_opensearch.json.return_value = [
            "Burg Eltz",
            ["Eltz Castle"],
            ["Medieval castle in Germany"],
            ["https://en.wikipedia.org/wiki/Eltz_Castle"],
        ]

        # Step 3 response: Summary for canonical title
        resp_summary = MagicMock()
        resp_summary.status_code = 200
        resp_summary.json.return_value = {
            "extract": "Eltz Castle is a medieval castle nestled in the hills above the Moselle River.",
            "coordinates": {"lat": 50.2052, "lon": 7.3366},
            "originalimage": {"source": "https://upload.wikimedia.org/eltz_full.jpg"},
            "thumbnail": {"source": "https://upload.wikimedia.org/eltz_thumb.jpg"},
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Eltz_Castle"}},
        }

        mock_client = AsyncMock()
        mock_client.get.side_effect = [resp_404, resp_opensearch, resp_summary]

        result = await adapter.augment("Burg Eltz", client=mock_client)
        assert result["source_name"] == "wikipedia.org"
        assert result["wikipedia_url"] == "https://en.wikipedia.org/wiki/Eltz_Castle"
        assert "Moselle River" in result["description"]
        assert result["hero_image_url"] == "https://upload.wikimedia.org/eltz_full.jpg"
        assert result["latitude"] == 50.2052
        assert result["longitude"] == 7.3366

    async def test_infer_duration_heuristics(self) -> None:
        """Verifies category and scale visit duration heuristics (REQ: FR-017, T-008, T-010)."""
        # Category heuristic
        h, d = ScrapingOrchestrator.infer_duration(category="Castle", name="Eltz")
        assert h == 2.5
        assert d == 0

        # Scale heuristic: National park
        h, d = ScrapingOrchestrator.infer_duration(name="Yellowstone National Park")
        assert h == 12.0
        assert d == 1

        # Theme park
        h, d = ScrapingOrchestrator.infer_duration(category="Theme Park")
        assert h == 6.0
        assert d == 0

        # Scenic overlook
        h, d = ScrapingOrchestrator.infer_duration(name="Glacier Point Scenic Overlook")
        assert h == 0.5
        assert d == 0

        # Description keyword fallback
        h, d = ScrapingOrchestrator.infer_duration(
            name="Random Place", description="A beautiful botanical garden."
        )
        assert h == 2.5
        assert d == 0

        # Unknown
        h, d = ScrapingOrchestrator.infer_duration(name="Abstract Art Piece")
        assert h is None
        assert d is None

    async def test_orchestrator_parses_client_raw_address(self) -> None:
        """Verifies client raw address is parsed into structured address without duplicate country."""
        orchestrator = ScrapingOrchestrator(gemini_api_key=None, secondary_adapters=[])
        candidate, _ = await orchestrator.orchestrate(
            source_url="https://example.com/eltz",
            page_title="Burg Eltz",
            client_raw_address="56294 Wierschem, Germany",
        )
        assert len(candidate.addresses) == 1
        addr = candidate.addresses[0]
        assert addr.country == "Germany"
        assert addr.postal_code == "56294"
        assert addr.city == "Wierschem"
        assert addr.street is None or "Germany" not in addr.street
