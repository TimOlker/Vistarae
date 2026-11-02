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

"""Unit tests for selective enrichment re-calculation overrides (T-030)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import IngestCandidate
from vistarae_core.domain.enums import SelectiveEnrichmentOverrides

from services.worker.candidate_enricher import CandidateEnricher


@pytest.fixture
def mock_candidate():
    return IngestCandidate(
        id=uuid4(),
        job_id=uuid4(),
        user_id=uuid4(),
        row_index=1,
        poi_name="Kiyomizu-dera",
        city="Kyoto",
        country="Japan",
        description="Preserved historical overview.",
        reason_to_visit="Preserved view from wooden stage.",
        recommended_duration_hours=Decimal("3.0"),
        recommended_visit_days=1,
        tags=["temple", "kyoto"],
        estimated_visit_time_notes="Preserved duration notes.",
        official_url="https://example.com/official",
        wiki_url="https://en.wikipedia.org/wiki/Kiyomizu-dera",
    )


@pytest.mark.asyncio
async def test_preserves_populated_fields_by_default(mock_candidate):
    """Asserts that populated attributes are untouched when overrides are False (REQ-REC-001)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(return_value="New AI Description")
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(return_value="New AI Reason")
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(return_value="New AI Notes")

    enricher = CandidateEnricher(orchestrator=mock_orchestrator)

    # Apply selective enrichment logic with default empty overrides
    cand = await enricher.apply_enrichment_to_candidate(
        candidate=mock_candidate,
        overrides=SelectiveEnrichmentOverrides(),
        valid_domains=[],
        directives={},
    )

    assert cand.description == "Preserved historical overview."
    assert cand.reason_to_visit == "Preserved view from wooden stage."
    assert cand.recommended_duration_hours == Decimal("3.0")
    assert cand.tags == ["temple", "kyoto"]
    mock_orchestrator.synthesize_summary.assert_not_called()
    mock_orchestrator.synthesize_reason_to_visit.assert_not_called()


@pytest.mark.asyncio
async def test_recalculates_fields_when_overrides_enabled(mock_candidate):
    """Asserts that flagged attributes are regenerated via AI when overrides are True (REQ-REC-002)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(return_value="Overridden Summary")
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(return_value="Overridden Reason")
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(return_value="Overridden Notes")

    enricher = CandidateEnricher(orchestrator=mock_orchestrator)

    overrides = SelectiveEnrichmentOverrides(
        recalculate_description=True,
        recalculate_reason_to_visit=True,
    )

    cand = await enricher.apply_enrichment_to_candidate(
        candidate=mock_candidate,
        overrides=overrides,
        valid_domains=[],
        directives={},
    )

    assert cand.description == "Overridden Summary"
    assert cand.reason_to_visit == "Overridden Reason"
    mock_orchestrator.synthesize_summary.assert_called_once()
    mock_orchestrator.synthesize_reason_to_visit.assert_called_once()
