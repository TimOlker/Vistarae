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

"""Integration tests for personalized Phase 2 enrichment (T-032).

Verifies REQ-ING-017 and REQ-ING-018:
- Traveler prompt directives from user_prompts are appended to Gemini prompts
- description and reason_to_visit incorporate personalized style directives
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import IngestCandidate
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
    PromptType,
)

from services.ingest.services.staging_service import StagingService
from services.poi.scraping.orchestrator import ScrapingOrchestrator


@pytest.mark.asyncio
async def test_phase2_enrichment_appends_travel_style_directives() -> None:
    """Verifies user travel style directives are injected into Gemini synthesis prompts."""
    user_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()

    candidate = IngestCandidate(
        id=cand_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Kiyomizu-dera",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        city="Kyoto",
        country="Japan",
        photo_directory="Japan 2023/Kiyomizu",
        confidence_score=95,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
    )

    mock_repo = MagicMock()
    mock_repo.list_by_job = AsyncMock(return_value=[candidate])
    mock_repo.update_candidate = AsyncMock(side_effect=lambda uid, c: c)

    directives = {
        PromptType.DESCRIPTION: "Focus on traditional Buddhist architecture and mountain views.",
        PromptType.REASON_TO_VISIT: "Highlight early morning visits to avoid crowds and photography spots.",
    }

    orchestrator = ScrapingOrchestrator(gemini_api_key="test-api-key")

    captured_prompts: list[str] = []

    def mock_generate_content(model: str, contents: str, config: object = None) -> object:
        captured_prompts.append(contents)
        resp = MagicMock()
        resp.text = "Personalized response from Gemini Flash-Lite."
        return resp

    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content.side_effect = mock_generate_content

    with patch("google.genai.Client", return_value=mock_genai_client):
        staging_service = StagingService(
            candidate_repo=mock_repo,
            orchestrator=orchestrator,
        )

        enriched = await staging_service.enrich_candidates_phase2(
            user_id=user_id,
            job_id=job_id,
            prompt_directives=directives,
        )

    assert len(enriched) == 1
    item = enriched[0]
    assert item.description is not None
    assert item.reason_to_visit is not None
    assert len(captured_prompts) >= 2

    # Verify directives were included in prompts
    assert any("traditional Buddhist architecture" in p for p in captured_prompts)
    assert any("early morning visits" in p for p in captured_prompts)
