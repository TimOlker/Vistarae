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

"""Unit tests for personalized prompt extension injection in ScrapingOrchestrator (T-019).

Validates:
- Description augmentation with user prompt directives (REQ-CTX-027, REQ-CTX-028)
- Reason to visit generation with user prompt directives (REQ-CTX-029)
- Anti-hallucination guardrails for non-overlapping themes (REQ-CTX-030)
- Visit duration pacing adjustments from time_spent directives (REQ-CTX-031)
- Aggregation of secondary source text into personalized synthesis (REQ-CTX-032)
- Graceful default fallback when no directives are present
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from vistarae_core.domain.value_objects import PromptType

from services.poi.scraping.orchestrator import ScrapingOrchestrator
from services.poi.scraping.secondary_sources import SecondarySourceAdapter


class MockSecondaryAdapter(SecondarySourceAdapter):
    """Secondary adapter providing canned multi-source text extracts."""

    def __init__(self, domain_name: str, desc: str, duration: float | None = 1.5) -> None:
        self._domain = domain_name
        self._desc = desc
        self._duration = duration

    @property
    def domain(self) -> str:
        return self._domain

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: Any = None,
    ) -> dict[str, Any]:
        return {
            "source_name": self._domain,
            "description": self._desc,
            "estimated_duration_hours": self._duration,
        }


@pytest.mark.asyncio
class TestPersonalizedScraping:
    """Test suite for personalized scraping and Reason to Visit generation."""

    async def test_extract_without_directives_standard_defaults(self) -> None:
        """Verifies standard default description and reason_to_visit generated when no directives."""
        orchestrator = ScrapingOrchestrator(
            gemini_api_key=None,  # Deterministic mode
            secondary_adapters=[],
        )

        candidate = await orchestrator.extract(
            source_url="https://en.wikipedia.org/wiki/Edinburgh_Castle",
            page_title="Edinburgh Castle - Wikipedia",
            selected_text="Historic fortress dominating the skyline of Edinburgh, Scotland.",
        )

        assert candidate.name == "Edinburgh Castle"
        assert candidate.description is not None
        assert "Edinburgh" in candidate.description
        assert candidate.reason_to_visit is not None
        assert len(candidate.reason_to_visit) > 0

    async def test_extract_with_gemini_personalized_directives(self) -> None:
        """Verifies Gemini Flash-Lite is invoked with user directives for description and reason_to_visit."""
        orchestrator = ScrapingOrchestrator(
            gemini_api_key="test-api-key",
            secondary_adapters=[
                MockSecondaryAdapter(
                    "wikipedia.org",
                    "Pike Place Market is a public market in Seattle overlooking Elliott Bay.",
                    duration=1.5,
                )
            ],
        )

        directives = {
            PromptType.DESCRIPTION: "Highlight local food traditions, artisan bakeries, and culinary heritage.",
            PromptType.REASON_TO_VISIT: "Focus on authentic dining, food vendor stalls, and tasting experiences.",
            PromptType.TIME_SPENT: "Allow generous duration estimates for leisurely dining and sampling.",
        }

        with patch("google.genai.Client") as mock_genai_cls:
            mock_client = MagicMock()
            mock_genai_cls.return_value = mock_client

            # Return distinctive responses for name normalization, description, reason_to_visit, and duration notes
            mock_resp_name = MagicMock()
            mock_resp_name.text = "Pike Place Market"
            mock_resp_desc = MagicMock()
            mock_resp_desc.text = "Historic public market showcasing local artisan bakeries, fresh seafood stalls, and northwest food culture."
            mock_resp_reason = MagicMock()
            mock_resp_reason.text = "Food-loving travelers should visit to wander the bustling market alleys, sample artisan ciders, and taste local cheeses."
            mock_resp_duration = MagicMock()
            mock_resp_duration.text = "Estimated 3 hours allows leisurely exploration of artisan stalls, a 45-minute food tasting tour, and unhurried sampling."

            mock_client.models.generate_content.side_effect = [
                mock_resp_name,
                mock_resp_desc,
                mock_resp_reason,
                mock_resp_duration,
            ]

            candidate = await orchestrator.extract(
                source_url="https://example.com/pike-place",
                page_title="Pike Place Market Seattle",
                selected_text="Pike Place Market opened in 1907 and is one of the oldest public farmers markets.",
                prompt_directives=directives,
            )

            assert "artisan bakeries" in candidate.description
            assert candidate.reason_to_visit is not None
            assert "artisan ciders" in candidate.reason_to_visit
            assert candidate.estimated_visit_time_notes is not None
            assert "tasting tour" in candidate.estimated_visit_time_notes

            # Check pacing adjustment: Pike Place base duration 1.5 adjusted for leisurely pacing -> 3.0
            assert candidate.estimated_duration_hours == 3.0

            # Verify prompt contents passed to Gemini
            assert mock_client.models.generate_content.call_count == 4
            desc_call_prompt = mock_client.models.generate_content.call_args_list[1].kwargs[
                "contents"
            ]
            reason_call_prompt = mock_client.models.generate_content.call_args_list[2].kwargs[
                "contents"
            ]
            duration_call_prompt = mock_client.models.generate_content.call_args_list[3].kwargs[
                "contents"
            ]

            assert "Highlight local food traditions" in desc_call_prompt
            assert "Focus on authentic dining" in reason_call_prompt
            assert "Do NOT invent, hallucinate, or force irrelevant themes" in desc_call_prompt
            assert "Do not invent or force irrelevant themes" in reason_call_prompt
            assert (
                "CRITICAL REQUIREMENT: Do NOT include or mention the capture source"
                in desc_call_prompt
            )
            assert "Time to spend in line / ticket queues" in duration_call_prompt
            assert "guided tour" in duration_call_prompt
            assert "Shuttle bus" in duration_call_prompt

    async def test_description_excludes_capture_source(self) -> None:
        """Verifies capture source prefixes ('Captured from Google Maps:') are stripped and forbidden."""
        orchestrator = ScrapingOrchestrator(
            gemini_api_key="test-api-key",
            secondary_adapters=[],
        )

        with patch("google.genai.Client") as mock_genai_cls:
            mock_client = MagicMock()
            mock_genai_cls.return_value = mock_client

            mock_resp_desc = MagicMock()
            # Simulate an LLM that mistakenly repeated the capture source
            mock_resp_desc.text = "Captured from Google Maps: Eltz Castle is a medieval castle nestled in the hills above the Moselle."
            mock_client.models.generate_content.return_value = mock_resp_desc

            desc = await orchestrator.synthesize_summary(
                name="Eltz Castle",
                primary_snippet="Captured from Google Maps: Eltz Castle Eltz Castle is a medieval castle nestled in the hills.",
                secondary_extracts=[],
            )

            # Assert capture source prefix is completely stripped from description output
            assert "Captured from Google Maps" not in desc
            assert desc.startswith("Eltz Castle is a medieval castle")

            # Assert the prompt explicitly instructed Gemini not to include the capture source
            call_prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
            assert "Do NOT include or mention the capture source" in call_prompt
            assert "Start directly with the factual description" in call_prompt

    async def test_duration_pacing_heuristic_generous(self) -> None:
        """Verifies leisurely/generous time_spent directive scales visit duration appropriately."""
        orchestrator = ScrapingOrchestrator(gemini_api_key=None, secondary_adapters=[])

        dur_h, dur_d = orchestrator._resolve_durations(
            primary_dur=1.5,
            secondary_dur=None,
            category="market",
            name="Pike Place Market",
            desc="Market overview",
            time_spent_directive="Allow generous duration estimates for leisurely dining and sampling.",
        )

        assert dur_h == 3.0
        assert dur_d == 0

    async def test_duration_pacing_heuristic_standard_without_directive(self) -> None:
        """Verifies standard duration without directive remains unscaled."""
        orchestrator = ScrapingOrchestrator(gemini_api_key=None, secondary_adapters=[])

        dur_h, dur_d = orchestrator._resolve_durations(
            primary_dur=1.5,
            secondary_dur=None,
            category="market",
            name="Pike Place Market",
            desc="Market overview",
            time_spent_directive=None,
        )

        assert dur_h == 1.5
        assert dur_d == 0

    async def test_heuristic_duration_notes_includes_factors(self) -> None:
        """Verifies visit duration reasoning and notes include tours, lines, shuttles, demonstrations, and pacing."""
        notes = ScrapingOrchestrator._heuristic_duration_notes(
            name="Eltz Castle",
            category="castle",
            duration_hours=2.5,
            duration_days=0,
            time_spent_directive="We travel at a leisurely, relaxed pace with time for tours.",
        )

        assert "Eltz Castle" in notes
        assert "shuttle bus" in notes.lower() or "approach" in notes.lower()
        assert "ticket" in notes.lower() or "lines" in notes.lower()
        assert "tour" in notes.lower()
        assert "demonstrations" in notes.lower() or "viewpoints" in notes.lower()
        assert "leisurely" in notes.lower()
