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

"""Unit tests for staging commit, batch edit, and sublocation validation (FR-012, FR-014, FR-018, FR-024, T-026)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from vistarae_core.domain.entities import POI, IngestCandidate
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
    WGS84Point,
)
from vistarae_core.schemas.ingest_staging import (
    BatchEditCandidatesRequest,
    CandidateUpdateRequest,
)

from services.ingest.services.staging_service import StagingService


@pytest.mark.asyncio
async def test_sublocation_update_rejected_without_parent() -> None:
    """Verifies that setting disposition to Sublocation without a parent POI raises HTTP 422 (FR-018)."""
    user_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    mock_candidate = IngestCandidate(
        id=candidate_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        row_index=0,
        poi_name="Gift Shop",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        photo_directory="dir",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_repo = MagicMock()
    mock_repo.get_candidate = AsyncMock(return_value=mock_candidate)

    service = StagingService(candidate_repo=mock_repo, poi_repo=None)

    # Attempt to set disposition to SUBLOCATION with neither parent_poi_id nor parent_candidate_id
    update_req = CandidateUpdateRequest(user_disposition=IngestDisposition.SUBLOCATION)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_candidate(user_id, candidate_id, update_req)

    assert exc_info.value.status_code == 422
    assert "Sublocation requires an assigned parent POI" in exc_info.value.detail


@pytest.mark.asyncio
async def test_batch_edit_candidates_updates_location_and_date() -> None:
    """Verifies batch_edit_candidates applies location and date updates across selected IDs (FR-014, FR-024)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand1 = uuid.uuid4()
    cand2 = uuid.uuid4()

    mock_repo = MagicMock()
    mock_repo.batch_edit = AsyncMock(return_value=2)

    service = StagingService(candidate_repo=mock_repo, poi_repo=None)

    req = BatchEditCandidatesRequest(
        candidate_ids=[cand1, cand2],
        country="Japan",
        state_province="Kyoto Prefecture",
        city="Kyoto",
        date_visited="2024-04-12",
    )

    count = await service.batch_edit_candidates(user_id, job_id, req)

    assert count == 2
    mock_repo.batch_edit.assert_awaited_once_with(
        user_id,
        [cand1, cand2],
        {
            "country": "Japan",
            "state_province": "Kyoto Prefecture",
            "city": "Kyoto",
            "dates_visited": ["2024-04-12"],
        },
    )


@pytest.mark.asyncio
async def test_commit_job_creates_pois_and_purges_staging() -> None:
    """Verifies commit_job persists accepted candidates to POIRepository and purges staging records (FR-012)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    candidate = IngestCandidate(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Fushimi Inari Shrine",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        latitude=Decimal("34.967140"),
        longitude=Decimal("135.772695"),
        street_address="68 Fukakusa Yabunouchicho",
        city="Kyoto",
        country="Japan",
        dates_visited=["2024-04-11"],
        photo_directory="Japan/Inari",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.list_by_job = AsyncMock(return_value=[candidate])
    mock_candidate_repo.purge_by_job = AsyncMock(return_value=1)

    mock_poi_repo = MagicMock()
    created_poi = POI(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Fushimi Inari Shrine",
        geom=WGS84Point(lat=34.967140, lon=135.772695),
        address="68 Fukakusa Yabunouchicho",
        city="Kyoto",
    )
    mock_poi_repo.create = AsyncMock(return_value=created_poi)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
    )

    total, created, merged = await service.commit_job(user_id, job_id)

    assert total == 1
    assert len(created) == 1
    assert len(merged) == 0
    mock_poi_repo.create.assert_awaited_once()
    mock_candidate_repo.purge_by_job.assert_awaited_once_with(user_id, job_id)

