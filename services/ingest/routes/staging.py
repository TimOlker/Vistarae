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

"""FastAPI router for two-phase interactive candidate staging, triage, and review (T-029, T-035).

Exposes:
- GET /api/ingest/jobs/{job_id}/candidates: Lists staged candidates
- PATCH /api/ingest/jobs/{job_id}/candidates/{candidate_id}: Updates candidate details or disposition
- POST /api/ingest/jobs/{job_id}/phase1/proceed: Advances non-ignored candidates to Phase 2
- POST /api/ingest/jobs/{job_id}/phase1/cancel: Purges staged candidates and aborts Phase 1
- POST /api/ingest/jobs/{job_id}/phase2/commit: Persists accepted/sublocation/update candidates to pois
- POST /api/ingest/jobs/{job_id}/phase2/cancel: Purges staged candidates and aborts Phase 2
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from vistarae_core.domain.entities import IngestCandidate, User
from vistarae_core.domain.value_objects import IngestCandidatePhaseState
from vistarae_core.ports.repositories import IPOIRepository
from vistarae_core.schemas.ingest_staging import (
    CandidateItemResponse,
    CandidateListResponse,
    CandidateUpdateRequest,
    CommitSummaryResponse,
    JobCancellationResponse,
    PhaseTransitionResponse,
)

from services.ingest.dependencies import (
    get_current_user,
    get_poi_repo,
    get_staging_service,
)
from services.ingest.services.staging_service import StagingService

router = APIRouter(tags=["ingest-staging"])


def _to_candidate_response(
    candidate: IngestCandidate,
    poi_name_map: dict[UUID, str] | None = None,
) -> CandidateItemResponse:
    """Transforms IngestCandidate domain entity to CandidateItemResponse."""
    matched_name = None
    parent_name = None
    if poi_name_map:
        if candidate.matched_existing_poi_id:
            matched_name = poi_name_map.get(candidate.matched_existing_poi_id)
        if candidate.parent_poi_id:
            parent_name = poi_name_map.get(candidate.parent_poi_id)

    return CandidateItemResponse(
        id=candidate.id,
        job_id=candidate.job_id,
        row_index=candidate.row_index,
        poi_name=candidate.poi_name,
        recommended_disposition=candidate.recommended_disposition,
        user_disposition=candidate.user_disposition,
        matched_existing_poi_id=candidate.matched_existing_poi_id,
        matched_existing_poi_name=matched_name,
        parent_poi_id=candidate.parent_poi_id,
        parent_poi_name=parent_name,
        latitude=float(candidate.latitude) if candidate.latitude is not None else None,
        longitude=float(candidate.longitude) if candidate.longitude is not None else None,
        street_address=candidate.street_address,
        city=candidate.city,
        state_province=candidate.state_province,
        postal_code=candidate.postal_code,
        country=candidate.country,
        dates_visited=candidate.dates_visited,
        photo_directory=candidate.photo_directory,
        confidence_score=candidate.confidence_score,
        tags=candidate.tags,
        description=candidate.description,
        reason_to_visit=candidate.reason_to_visit,
        update_coordinates=candidate.update_coordinates,
        is_skipped=candidate.is_skipped,
        phase_state=candidate.phase_state,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


async def _resolve_poi_names(
    candidates: list[IngestCandidate],
    user_id: UUID,
    poi_repo: IPOIRepository,
) -> dict[UUID, str]:
    """Resolves names for matched or parent POIs referenced in candidate rows."""
    needed_ids: set[UUID] = set()
    for c in candidates:
        if c.matched_existing_poi_id:
            needed_ids.add(c.matched_existing_poi_id)
        if c.parent_poi_id:
            needed_ids.add(c.parent_poi_id)

    name_map: dict[UUID, str] = {}
    for pid in needed_ids:
        poi = await poi_repo.get_by_id(pid, user_id)
        if poi:
            name_map[pid] = poi.name
    return name_map


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=CandidateListResponse,
    summary="Retrieve staged candidates for an ingest job",
)
@router.get(
    "/api/ingest/jobs/{job_id}/candidates",
    response_model=CandidateListResponse,
    include_in_schema=False,
)
async def get_job_candidates(
    job_id: UUID,
    phase: IngestCandidatePhaseState | None = Query(default=None),
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> CandidateListResponse:
    """Returns staged candidate records for the specified job."""
    candidates = list(await staging_service.list_candidates(user.id, job_id, phase))
    name_map = await _resolve_poi_names(candidates, user.id, poi_repo)

    return CandidateListResponse(
        job_id=job_id,
        total_candidates=len(candidates),
        candidates=[_to_candidate_response(c, name_map) for c in candidates],
    )


@router.patch(
    "/jobs/{job_id}/candidates/{candidate_id}",
    response_model=CandidateItemResponse,
    summary="Update details, disposition, or coordinates for a candidate",
)
@router.patch(
    "/api/ingest/jobs/{job_id}/candidates/{candidate_id}",
    response_model=CandidateItemResponse,
    include_in_schema=False,
)
async def update_candidate(
    job_id: UUID,
    candidate_id: UUID,
    body: CandidateUpdateRequest,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> CandidateItemResponse:
    """Updates fields or disposition on an individual candidate."""
    updated = await staging_service.update_candidate(user.id, candidate_id, body)
    name_map = await _resolve_poi_names([updated], user.id, poi_repo)
    return _to_candidate_response(updated, name_map)


@router.post(
    "/jobs/{job_id}/phase1/proceed",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PhaseTransitionResponse,
    summary="Advance confirmed Phase 1 triage records to Phase 2 enrichment",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase1/proceed",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PhaseTransitionResponse,
    include_in_schema=False,
)
async def proceed_phase1(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> PhaseTransitionResponse:
    """Transitions active candidates to Phase 2."""
    adv, ign = await staging_service.advance_to_phase2(user.id, job_id)
    return PhaseTransitionResponse(
        job_id=job_id,
        message=f"Advanced {adv} candidate(s) to Phase 2; ignored {ign} candidate(s).",
        advanced_count=adv,
        ignored_count=ign,
    )


@router.post(
    "/jobs/{job_id}/phase1/cancel",
    response_model=JobCancellationResponse,
    summary="Abort Phase 1 triage and purge staged candidate records",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase1/cancel",
    response_model=JobCancellationResponse,
    include_in_schema=False,
)
async def cancel_phase1(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> JobCancellationResponse:
    """Purges staging table for the job upon Phase 1 cancellation."""
    purged = await staging_service.cancel_staging(user.id, job_id)
    return JobCancellationResponse(
        job_id=job_id,
        purged_count=purged,
        message="Phase 1 triage cancelled; staged records purged.",
    )


@router.post(
    "/jobs/{job_id}/phase2/commit",
    response_model=CommitSummaryResponse,
    summary="Commit confirmed candidates to database pois table",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase2/commit",
    response_model=CommitSummaryResponse,
    include_in_schema=False,
)
async def commit_phase2(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> CommitSummaryResponse:
    """Executes final database transaction committing accepted, child, and merged POIs."""
    total, created, merged = await staging_service.commit_job(user.id, job_id)
    return CommitSummaryResponse(
        job_id=job_id,
        committed_count=total,
        created_pois=created,
        merged_pois=merged,
        message=f"Successfully committed {total} POIs ({len(created)} created, {len(merged)} merged).",
    )


@router.post(
    "/jobs/{job_id}/phase2/cancel",
    response_model=JobCancellationResponse,
    summary="Abort Phase 2 review and purge staged candidate records",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase2/cancel",
    response_model=JobCancellationResponse,
    include_in_schema=False,
)
async def cancel_phase2(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> JobCancellationResponse:
    """Purges staging table for the job upon Phase 2 cancellation."""
    purged = await staging_service.cancel_staging(user.id, job_id)
    return JobCancellationResponse(
        job_id=job_id,
        purged_count=purged,
        message="Phase 2 review cancelled; staged records purged.",
    )

