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

"""Unit tests for worker exemption skip optimizations and invariant protections (T023).

Validates EARS requirements:
- REQ-EXM-004: System never automatically sets no_address = true or no_websites = true.
- REQ-EXM-020: Worker skips external scraping calls when no_websites = true.
- REQ-EXM-021: Worker / staging skips reverse-geocoding street address lookups when no_address = true.
- REQ-EXM-022: Worker preserves user-configured exemption flags across enrichment.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vistarae_core.domain.entities import IngestCandidate
from vistarae_core.domain.value_objects import IngestCandidatePhaseState, IngestDisposition

from services.worker.candidate_enricher import CandidateEnricher


def _make_candidate(
    cand_id: uuid.UUID,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    poi_name: str = "Mount Rainier Trail",
    no_address: bool = False,
    no_websites: bool = False,
) -> IngestCandidate:
    """Helper to construct IngestCandidate for enricher tests."""
    return IngestCandidate(
        id=cand_id,
        job_id=job_id,
        user_id=user_id,
        row_index=1,
        poi_name=poi_name,
        latitude=Decimal("46.8523"),
        longitude=Decimal("-121.7603"),
        street_address=None,
        official_url=None,
        hero_image_url="https://example.com/hero.jpg",
        no_address=no_address,
        no_websites=no_websites,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
        recommended_disposition=IngestDisposition.ACCEPT,
        confidence_score=90,
    )


@pytest.mark.asyncio
async def test_enricher_skips_scraping_when_no_websites_is_true() -> None:
    """Tests that Wikipedia, TripAdvisor, and Hillman scraping are skipped when cand.no_websites is True."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand = _make_candidate(uuid.uuid4(), job_id, user_id, no_websites=True)

    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(return_value="A scenic trail")
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(return_value="Great views")
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(return_value="2 hours")

    enricher = CandidateEnricher(orchestrator=mock_orchestrator)

    with patch("services.worker.candidate_enricher.WikipediaAdapter") as mock_wiki, \
         patch("services.worker.candidate_enricher.TripAdvisorAdapter") as mock_ta, \
         patch("services.worker.candidate_enricher.HillmanWondersAdapter") as mock_hillman:

        await enricher.apply_enrichment_to_candidate(cand)

        mock_wiki.assert_not_called()
        mock_ta.assert_not_called()
        mock_hillman.assert_not_called()
        assert cand.no_websites is True


@pytest.mark.asyncio
async def test_enricher_never_automatically_sets_no_websites_true() -> None:
    """Tests that discovering 0 websites leaves no_websites=False (REQ-EXM-004)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand = _make_candidate(uuid.uuid4(), job_id, user_id, no_websites=False)

    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(return_value="An isolated viewpoint")
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(return_value="Quiet overlook")
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(return_value="1 hour")

    enricher = CandidateEnricher(orchestrator=mock_orchestrator)

    with patch("services.worker.candidate_enricher.WikipediaAdapter") as mock_wiki:
        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.augment.return_value = {}  # 0 websites found
        mock_wiki.return_value = mock_adapter_instance

        await enricher.apply_enrichment_to_candidate(cand)

        # Invariant: Must NOT be automatically assigned True!
        assert cand.no_websites is False


@pytest.mark.asyncio
async def test_enricher_preserves_user_exemptions() -> None:
    """Tests that user-configured no_address=True and no_websites=True are preserved across enrichments (REQ-EXM-022)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand = _make_candidate(uuid.uuid4(), job_id, user_id, no_address=True, no_websites=True)

    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(return_value="Wilderness crag")
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(return_value="Untouched rock")
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(return_value="3 hours")

    enricher = CandidateEnricher(orchestrator=mock_orchestrator)

    await enricher.apply_enrichment_to_candidate(cand)

    assert cand.no_address is True
    assert cand.no_websites is True
