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

"""Unit tests for single-candidate and batch enrichment endpoints (FR-006, FR-007, T-015, T-016, T-017)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import IngestCandidate, User
from vistarae_core.domain.exceptions import IngestCandidateNotFoundError
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
)

from services.ingest.dependencies import (
    get_current_user,
    get_poi_repo,
    get_staging_service,
)
from services.ingest.main import app


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-test-enricher",
        email="traveler@example.com",
    )


@pytest.fixture
def mock_staging_service() -> MagicMock:
    svc = MagicMock()
    svc.get_active_session = AsyncMock()
    svc.list_candidates = AsyncMock()
    svc.enrich_single_candidate = AsyncMock()
    svc.enrich_candidates_phase2 = AsyncMock()
    svc.batch_edit_candidates = AsyncMock()
    svc.commit_job = AsyncMock()
    svc.cancel_staging = AsyncMock()
    return svc


@pytest.fixture
def mock_poi_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def sample_candidate(mock_user: User) -> IngestCandidate:
    cand_id = uuid.uuid4()
    job_id = uuid.uuid4()
    return IngestCandidate(
        id=cand_id,
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Kiyomizu-dera",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        latitude=Decimal("34.994857"),
        longitude=Decimal("135.785046"),
        street_address="1 Chome-294 Kiyomizu, Higashiyama Ward",
        city="Kyoto",
        country="Japan",
        dates_visited=["2024-04-10"],
        photo_directory="Japan/Kyoto",
        confidence_score=95,
        tags=["Historic", "Temple"],
        description="Existing custom user description",
        reason_to_visit=None,
        hero_image_url="https://images.example.com/kiyomizu.jpg",
        wiki_url="https://en.wikipedia.org/wiki/Kiyomizu-dera",
        official_url=None,
        no_websites=False,
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_enrich_single_candidate_populates_missing_preserves_existing(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
    sample_candidate: IngestCandidate,
) -> None:
    """Verifies single enrichment preserves existing fields and populates blank fields (FR-006)."""
    # Enriched version has reason_to_visit and duration populated, keeping existing description
    enriched_cand = IngestCandidate(
        id=sample_candidate.id,
        user_id=sample_candidate.user_id,
        job_id=sample_candidate.job_id,
        row_index=sample_candidate.row_index,
        poi_name=sample_candidate.poi_name,
        recommended_disposition=sample_candidate.recommended_disposition,
        user_disposition=sample_candidate.user_disposition,
        latitude=sample_candidate.latitude,
        longitude=sample_candidate.longitude,
        street_address=sample_candidate.street_address,
        city=sample_candidate.city,
        country=sample_candidate.country,
        dates_visited=sample_candidate.dates_visited,
        photo_directory=sample_candidate.photo_directory,
        confidence_score=sample_candidate.confidence_score,
        tags=sample_candidate.tags,
        description=sample_candidate.description,  # preserved
        reason_to_visit="Ancient wooden stage overlooking cherry blossoms",  # populated
        hero_image_url=sample_candidate.hero_image_url,
        wiki_url=sample_candidate.wiki_url,
        official_url="https://www.kiyomizudera.or.jp",  # populated
        recommended_duration_hours=Decimal("2.5"),  # populated
        recommended_visit_days=1,
        no_websites=False,
        phase_state=sample_candidate.phase_state,
        created_at=sample_candidate.created_at,
        updated_at=datetime.now(UTC),
    )

    mock_staging_service.enrich_single_candidate.return_value = enriched_cand

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/ingest/jobs/{sample_candidate.job_id}/candidates/{sample_candidate.id}/enrich"
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_candidate.id)
    assert data["description"] == "Existing custom user description"
    assert data["reason_to_visit"] == "Ancient wooden stage overlooking cherry blossoms"
    assert data["official_url"] == "https://www.kiyomizudera.or.jp"
    assert data["recommended_duration_hours"] == 2.5
    mock_staging_service.enrich_single_candidate.assert_awaited_once_with(
        mock_user.id, sample_candidate.job_id, sample_candidate.id
    )


@pytest.mark.asyncio
async def test_enrich_all_candidates_enqueues_background_task(
    mock_user: User,
    mock_staging_service: MagicMock,
    sample_candidate: IngestCandidate,
) -> None:
    """Verifies batch enrichment returns 202 Accepted and enqueues tasks (FR-007)."""
    mock_staging_service.list_candidates.return_value = [sample_candidate]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/ingest/jobs/{sample_candidate.job_id}/enrich-all"
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "enriching"
    assert data["enqueued_candidates"] == 1
    mock_staging_service.enrich_candidates_phase2.assert_called_once()

