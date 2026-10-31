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

"""Unit tests for modular candidate enricher, parallel queue worker, and Lambda handler."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vistarae_core.domain.entities import IngestCandidate, IngestDisposition, TagEntity
from vistarae_core.domain.value_objects import IngestCandidatePhaseState, PromptType

from services.worker.candidate_enricher import (
    CandidateEnricher,
    CandidateEnrichmentQueueManager,
)
from services.worker.main import candidate_enrichment_lambda_handler


def _build_mock_session():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__.return_value = None
    begin_ctx.__aexit__.return_value = None
    mock_session.begin = MagicMock(return_value=begin_ctx)
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = ["wikipedia.org"]
    mock_session.execute = AsyncMock(return_value=exec_res)
    return mock_session


@pytest.fixture
def mock_candidate() -> IngestCandidate:
    return IngestCandidate(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        row_index=1,
        poi_name="Eiffel Tower",
        recommended_disposition=IngestDisposition.ACCEPT,
        city="Paris",
        country="France",
        latitude=Decimal("48.8584"),
        longitude=Decimal("2.2945"),
        tags=[],
        description=None,
        reason_to_visit=None,
        official_url=None,
        wiki_url=None,
        hero_image_url=None,
        recommended_duration_hours=None,
        recommended_visit_days=None,
        estimated_visit_time_notes=None,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
    )


@pytest.mark.asyncio
async def test_candidate_enricher_populates_missing_fields(mock_candidate: IngestCandidate):
    """Enriches candidate using orchestrator, Wikipedia adapter, and prompt directives."""
    mock_session = _build_mock_session()
    mock_session_factory = MagicMock(return_value=mock_session)

    mock_orchestrator = MagicMock()
    mock_orchestrator.synthesize_summary = AsyncMock(
        return_value="Iconic iron lattice tower on the Champ de Mars in Paris."
    )
    mock_orchestrator.synthesize_reason_to_visit = AsyncMock(
        return_value="Travelers ascend the tower for breathtaking views and timeless Parisian atmosphere."
    )
    mock_orchestrator.synthesize_visit_duration_notes = AsyncMock(
        return_value="Allow 2.5 hours to clear security lines, ascend to the summit, and view exhibits."
    )

    enricher = CandidateEnricher(
        session_factory=mock_session_factory,
        orchestrator=mock_orchestrator,
    )

    with patch(
        "services.worker.candidate_enricher.SqlAlchemyIngestCandidateRepository"
    ) as MockCandidateRepo, patch(
        "services.worker.candidate_enricher.WikipediaAdapter"
    ) as MockWikiAdapter, patch(
        "services.worker.candidate_enricher.default_prompt_cache"
    ) as mock_cache, patch(
        "services.worker.candidate_enricher.SqlAlchemyTagRepository"
    ) as MockTagRepo:
        repo_instance = MagicMock()
        repo_instance.get_candidate = AsyncMock(return_value=mock_candidate)
        repo_instance.get_by_id = AsyncMock(return_value=mock_candidate)
        repo_instance.update_candidate = AsyncMock(side_effect=lambda u, c: c)
        MockCandidateRepo.return_value = repo_instance

        wiki_instance = MagicMock()
        wiki_instance.augment = AsyncMock(
            return_value={
                "wikipedia_url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
                "official_website_url": "https://www.toureiffel.paris",
                "hero_image_url": "https://upload.wikimedia.org/eiffel.jpg",
                "description": "The Eiffel Tower is a wrought-iron lattice tower.",
            }
        )
        MockWikiAdapter.return_value = wiki_instance

        mock_cache.get_or_load = AsyncMock(
            return_value={
                PromptType.DESCRIPTION: "Highlight architecture and viewpoints",
                PromptType.REASON_TO_VISIT: "Focus on scenic photography",
            }
        )

        tag_repo_instance = MagicMock()
        tag_repo_instance.list_by_user = AsyncMock(
            return_value=[
                TagEntity(id=uuid.uuid4(), user_id=mock_candidate.user_id, slug="architecture", name="Architecture"),
                TagEntity(id=uuid.uuid4(), user_id=mock_candidate.user_id, slug="landmark", name="Landmark"),
            ]
        )
        MockTagRepo.return_value = tag_repo_instance

        # Execute
        result = await enricher.enrich_candidate(
            user_id=mock_candidate.user_id,
            candidate_id=mock_candidate.id,
            job_id=mock_candidate.job_id,
        )

        assert result is not None
        assert result.description == "Iconic iron lattice tower on the Champ de Mars in Paris."
        assert "Parisian atmosphere" in result.reason_to_visit
        assert result.wiki_url == "https://en.wikipedia.org/wiki/Eiffel_Tower"
        assert result.official_url == "https://www.toureiffel.paris"
        assert result.hero_image_url == "https://upload.wikimedia.org/eiffel.jpg"
        assert result.recommended_duration_hours is not None
        assert "Allow 2.5 hours" in result.estimated_visit_time_notes
        assert len(result.tags) > 0


@pytest.mark.asyncio
async def test_candidate_enricher_preserves_existing_user_edits(mock_candidate: IngestCandidate):
    """Verifies that manual user values are not overwritten during enrichment."""
    mock_candidate.description = "My custom personal description of the tower."
    mock_candidate.reason_to_visit = "My personal why-visit notes."
    mock_candidate.recommended_duration_hours = Decimal("4.0")
    mock_candidate.official_url = "https://custom-site.example.com"
    mock_candidate.estimated_visit_time_notes = "Custom duration notes."

    mock_session = _build_mock_session()
    mock_session_factory = MagicMock(return_value=mock_session)
    mock_orchestrator = MagicMock()

    enricher = CandidateEnricher(
        session_factory=mock_session_factory,
        orchestrator=mock_orchestrator,
    )

    with patch(
        "services.worker.candidate_enricher.SqlAlchemyIngestCandidateRepository"
    ) as MockCandidateRepo:
        repo_instance = MagicMock()
        repo_instance.get_candidate = AsyncMock(return_value=mock_candidate)
        repo_instance.get_by_id = AsyncMock(return_value=mock_candidate)
        repo_instance.update_candidate = AsyncMock(side_effect=lambda u, c: c)
        MockCandidateRepo.return_value = repo_instance

        result = await enricher.enrich_candidate(
            user_id=mock_candidate.user_id,
            candidate_id=mock_candidate.id,
            job_id=mock_candidate.job_id,
        )

        assert result.description == "My custom personal description of the tower."
        assert result.reason_to_visit == "My personal why-visit notes."
        assert result.recommended_duration_hours == Decimal("4.0")
        assert result.official_url == "https://custom-site.example.com"
        mock_orchestrator.synthesize_summary.assert_not_called()
        mock_orchestrator.synthesize_reason_to_visit.assert_not_called()


@pytest.mark.asyncio
async def test_candidate_enrichment_queue_manager_progress_tracking():
    """Validates that CandidateEnrichmentQueueManager updates progress to 100%."""
    job_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    mock_enricher = MagicMock()
    mock_enricher.enrich_candidate = AsyncMock(
        return_value=IngestCandidate(
            id=cids[0],
            user_id=user_id,
            job_id=job_id,
            row_index=1,
            poi_name="Test POI",
            recommended_disposition=IngestDisposition.ACCEPT,
            phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
        )
    )

    queue_mgr = CandidateEnrichmentQueueManager(enricher=mock_enricher, max_concurrency=2)
    await queue_mgr.enqueue_and_process_job(user_id, job_id, cids)

    prog = CandidateEnrichmentQueueManager.get_progress(job_id)
    assert prog.is_complete is True
    assert prog.percent_complete == 100
    assert prog.enriched_count == 3
    assert prog.total_count == 3


def test_candidate_enrichment_lambda_handler():
    """Tests AWS Lambda event source mapping execution for candidate enrichment."""
    job_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    cid = str(uuid.uuid4())

    event = {
        "Records": [
            {
                "messageId": "msg-123",
                "body": f'{{"action": "enrich_candidate", "job_id": "{job_id}", "user_id": "{user_id}", "candidate_id": "{cid}"}}',
            }
        ]
    }

    with patch(
        "services.worker.candidate_enricher.CandidateEnricher.enrich_candidate",
        new_callable=AsyncMock,
    ) as mock_enrich:
        result = candidate_enrichment_lambda_handler(event, None)
        assert result == {"batchItemFailures": []}
        mock_enrich.assert_called_once()


@pytest.mark.asyncio
async def test_candidate_enricher_limits_tags_to_user_tags_library(mock_candidate: IngestCandidate):
    """Verifies that enrichment strictly discards unapproved tags and case duplicates, retaining only user's tags library."""
    mock_candidate.tags = ["water", "Water", "UnapprovedTag", "historic"]
    mock_candidate.description = "Already has description"
    mock_candidate.reason_to_visit = "Already has rationale"
    mock_candidate.estimated_visit_time_notes = "Already has duration notes"

    mock_session = _build_mock_session()
    mock_session_factory = MagicMock(return_value=mock_session)
    mock_orchestrator = MagicMock()

    enricher = CandidateEnricher(
        session_factory=mock_session_factory,
        orchestrator=mock_orchestrator,
    )

    with patch(
        "services.worker.candidate_enricher.SqlAlchemyIngestCandidateRepository"
    ) as MockCandidateRepo, patch(
        "services.worker.candidate_enricher.SqlAlchemyTagRepository"
    ) as MockTagRepo:
        repo_instance = MagicMock()
        repo_instance.get_candidate = AsyncMock(return_value=mock_candidate)
        repo_instance.get_by_id = AsyncMock(return_value=mock_candidate)
        repo_instance.update_candidate = AsyncMock(side_effect=lambda u, c: c)
        MockCandidateRepo.return_value = repo_instance

        tag_repo_instance = MagicMock()
        tag_repo_instance.list_by_user = AsyncMock(
            return_value=[
                TagEntity(id=uuid.uuid4(), user_id=mock_candidate.user_id, slug="water", name="Water"),
                TagEntity(id=uuid.uuid4(), user_id=mock_candidate.user_id, slug="historic", name="Historic"),
            ]
        )
        MockTagRepo.return_value = tag_repo_instance

        result = await enricher.enrich_candidate(
            user_id=mock_candidate.user_id,
            candidate_id=mock_candidate.id,
            job_id=mock_candidate.job_id,
        )

        assert result is not None
        # Only canonical display names from the user's tags library are retained
        assert result.tags == ["Historic", "Water"]
        assert "UnapprovedTag" not in result.tags
        assert "water" not in result.tags
