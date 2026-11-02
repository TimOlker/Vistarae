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

"""Unit tests for hierarchy safety, cycle detection, orphan prevention, and merge aggregation (FR-023, FR-027, FR-028, FR-029, T-031)."""

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
from vistarae_core.schemas.ingest_staging import CandidateUpdateRequest

from services.ingest.services.staging_service import StagingService


@pytest.mark.asyncio
async def test_cyclic_hierarchy_assignment_rejected_with_422() -> None:
    """Verifies that circular sublocation assignments are detected and rejected with HTTP 422 (FR-029)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    cand_a_id = uuid.uuid4()
    cand_b_id = uuid.uuid4()

    # Cand A is already parent of Cand B
    cand_a = IngestCandidate(
        id=cand_a_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Castle Grounds",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        photo_directory="dirA",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        parent_candidate_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    cand_b = IngestCandidate(
        id=cand_b_id,
        user_id=user_id,
        job_id=job_id,
        row_index=1,
        poi_name="Castle Keep",
        recommended_disposition=IngestDisposition.SUBLOCATION,
        user_disposition=IngestDisposition.SUBLOCATION,
        photo_directory="dirB",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        parent_candidate_id=cand_a_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_repo = MagicMock()

    async def get_cand(c_id: uuid.UUID, u_id: uuid.UUID) -> IngestCandidate | None:
        if c_id == cand_a_id:
            return cand_a
        if c_id == cand_b_id:
            return cand_b
        return None

    mock_repo.get_candidate = AsyncMock(side_effect=get_cand)

    service = StagingService(candidate_repo=mock_repo, poi_repo=None)

    # Attempting to assign Cand A's parent to Cand B creates cycle A -> B -> A
    update_req = CandidateUpdateRequest(
        user_disposition=IngestDisposition.SUBLOCATION,
        parent_candidate_id=cand_b_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_candidate(user_id, cand_a_id, update_req)

    assert exc_info.value.status_code == 422
    assert "Circular hierarchy detected" in exc_info.value.detail


@pytest.mark.asyncio
async def test_orphan_prevention_blocks_ignoring_parent_candidate() -> None:
    """Verifies that setting a parent candidate to IGNORE is blocked if a child depends on it (FR-027)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    parent_cand = IngestCandidate(
        id=parent_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="National Park",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        photo_directory="dirP",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    child_cand = IngestCandidate(
        id=child_id,
        user_id=user_id,
        job_id=job_id,
        row_index=1,
        poi_name="Park Visitor Center",
        recommended_disposition=IngestDisposition.SUBLOCATION,
        user_disposition=IngestDisposition.SUBLOCATION,
        parent_candidate_id=parent_id,
        photo_directory="dirC",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_repo = MagicMock()
    mock_repo.get_candidate = AsyncMock(return_value=parent_cand)
    mock_repo.list_by_job = AsyncMock(return_value=[parent_cand, child_cand])

    service = StagingService(candidate_repo=mock_repo, poi_repo=None)

    # Try setting parent to IGNORE
    update_req = CandidateUpdateRequest(user_disposition=IngestDisposition.IGNORE)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_candidate(user_id, parent_id, update_req)

    assert exc_info.value.status_code == 422
    assert "Cannot ignore or exclude candidate" in exc_info.value.detail
    assert "Park Visitor Center" in exc_info.value.detail


@pytest.mark.asyncio
async def test_commit_aggregates_in_batch_merge_attributes_into_primary() -> None:
    """Verifies that IN_BATCH_MERGE candidates aggregate unique dates, tags, and notes into primary (FR-028)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    primary_id = uuid.uuid4()
    dup_id = uuid.uuid4()

    primary_cand = IngestCandidate(
        id=primary_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Mount Mitchell Summit",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        latitude=Decimal("35.7649"),
        longitude=Decimal("-82.2651"),
        dates_visited=["2023-06-01"],
        tags=["Hiking", "Scenic"],
        photo_directory="dir1",
        official_url=None,
        wiki_url="https://en.wikipedia.org/wiki/Mount_Mitchell",
        hero_image_url="https://images.example.com/mitchell1.jpg",
        estimated_visit_time_notes="Allow 2 hours for summit trail",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    dup_cand = IngestCandidate(
        id=dup_id,
        user_id=user_id,
        job_id=job_id,
        row_index=1,
        poi_name="Mount Mitchell Summit",
        recommended_disposition=IngestDisposition.IN_BATCH_MERGE,
        user_disposition=None,
        merge_target_id=primary_id,
        latitude=Decimal("35.7649"),
        longitude=Decimal("-82.2651"),
        dates_visited=["2024-05-15"],  # unique additional date
        tags=["Mountain", "Hiking"],  # unique additional tag
        photo_directory="dir2",
        official_url="https://www.ncparks.gov/mount-mitchell",  # missing on primary
        wiki_url=None,
        hero_image_url=None,
        estimated_visit_time_notes="Brisk winds at observation deck",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.list_by_job = AsyncMock(return_value=[primary_cand, dup_cand])
    mock_candidate_repo.purge_by_job = AsyncMock(return_value=2)

    created_pois = []
    mock_poi_repo = MagicMock()

    async def mock_create(p: POI) -> POI:
        created_pois.append(p)
        return p

    mock_poi_repo.create = AsyncMock(side_effect=mock_create)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
    )

    total, created, merged = await service.commit_job(user_id, job_id)

    # 1 POI created from primary (dup was aggregated and skipped)
    assert total == 1
    assert len(created_pois) == 1
    committed = created_pois[0]

    assert sorted(committed.visited_dates) == ["2023-06-01", "2024-05-15"]
    assert sorted(primary_cand.tags) == ["Hiking", "Mountain", "Scenic"]
    assert committed.official_url == "https://www.ncparks.gov/mount-mitchell"
    assert "Allow 2 hours for summit trail" in committed.estimated_visit_time_notes
    assert "Brisk winds at observation deck" in committed.estimated_visit_time_notes


@pytest.mark.asyncio
async def test_commit_sublocation_resolves_batch_parent_id() -> None:
    """Verifies that child sublocation resolves parent POI ID from parent candidate during commit (FR-023)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    parent_cand = IngestCandidate(
        id=parent_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Grand Canyon South Rim",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
        latitude=Decimal("36.0544"),
        longitude=Decimal("-112.1401"),
        photo_directory="GC/Rim",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    child_cand = IngestCandidate(
        id=child_id,
        user_id=user_id,
        job_id=job_id,
        row_index=1,
        poi_name="Mather Point",
        recommended_disposition=IngestDisposition.SUBLOCATION,
        user_disposition=IngestDisposition.SUBLOCATION,
        parent_candidate_id=parent_id,
        latitude=Decimal("36.0560"),
        longitude=Decimal("-112.1086"),
        photo_directory="GC/Mather",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.list_by_job = AsyncMock(return_value=[child_cand, parent_cand])
    mock_candidate_repo.purge_by_job = AsyncMock(return_value=2)

    created_pois = []
    mock_poi_repo = MagicMock()

    async def mock_create(p: POI) -> POI:
        created_pois.append(p)
        return p

    mock_poi_repo.create = AsyncMock(side_effect=mock_create)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
    )

    total, created, merged = await service.commit_job(user_id, job_id)

    assert total == 2
    assert len(created_pois) == 2

    # Find created parent and child
    parent_poi = next(p for p in created_pois if p.name == "Grand Canyon South Rim")
    child_poi = next(p for p in created_pois if p.name == "Mather Point")

    assert child_poi.parent_poi_id == parent_poi.id

