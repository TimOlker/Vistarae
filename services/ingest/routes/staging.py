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

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from vistarae_core.domain.entities import IngestCandidate, User
from vistarae_core.domain.value_objects import IngestCandidatePhaseState, IngestDisposition
from vistarae_core.ports.repositories import IPOIRepository
from vistarae_core.schemas.ingest_staging import (
    ActiveSessionResponse,
    BatchEditCandidatesRequest,
    BatchEditResponse,
    CandidateItemResponse,
    CandidateListResponse,
    CandidateUpdateRequest,
    CommitSummaryResponse,
    JobCancellationResponse,
    Phase2ProgressResponse,
    PhaseTransitionResponse,
)
from vistarae_core.services.address_normalizer import AddressNormalizer

from services.ingest.dependencies import (
    get_current_user,
    get_poi_repo,
    get_staging_service,
)
from services.ingest.services.staging_service import StagingService
from services.poi.scraping.orchestrator import ScrapingOrchestrator

router = APIRouter(tags=["ingest-staging"])


def _to_candidate_response(
    candidate: IngestCandidate,
    poi_name_map: dict[UUID, str] | None = None,
    cand_name_map: dict[UUID, str] | None = None,
) -> CandidateItemResponse:
    """Transforms IngestCandidate domain entity to CandidateItemResponse."""
    matched_name = None
    parent_name = None
    if poi_name_map:
        if candidate.matched_existing_poi_id:
            matched_name = poi_name_map.get(candidate.matched_existing_poi_id)
        if candidate.parent_poi_id:
            parent_name = poi_name_map.get(candidate.parent_poi_id)

    parent_cand_name = None
    merge_cand_name = None
    if cand_name_map:
        if candidate.parent_candidate_id:
            parent_cand_name = cand_name_map.get(candidate.parent_candidate_id)
        if candidate.merge_target_id:
            merge_cand_name = cand_name_map.get(candidate.merge_target_id)

    recommended_name = None
    if candidate.raw_geocoding and isinstance(candidate.raw_geocoding, dict):
        res_n = candidate.raw_geocoding.get('resolved_name')
        if res_n and res_n.strip() and res_n.strip().lower() != candidate.poi_name.strip().lower():
            recommended_name = res_n.strip()

    disp = candidate.user_disposition or candidate.recommended_disposition
    is_dup = bool(
        candidate.merge_target_id
        or candidate.matched_existing_poi_id
        or disp in (IngestDisposition.IN_BATCH_MERGE, IngestDisposition.UPDATE_EXISTING, IngestDisposition.EXISTING)
    )

    return CandidateItemResponse(
        id=candidate.id,
        job_id=candidate.job_id,
        row_index=candidate.row_index,
        poi_name=candidate.poi_name,
        recommended_poi_name=recommended_name,
        recommended_disposition=candidate.recommended_disposition,
        user_disposition=candidate.user_disposition,
        matched_existing_poi_id=candidate.matched_existing_poi_id,
        matched_existing_poi_name=matched_name,
        parent_poi_id=candidate.parent_poi_id,
        parent_poi_name=parent_name,
        parent_candidate_id=candidate.parent_candidate_id,
        parent_candidate_name=parent_cand_name,
        merge_target_id=candidate.merge_target_id,
        merge_target_name=merge_cand_name,
        latitude=float(candidate.latitude) if candidate.latitude is not None else None,
        longitude=float(candidate.longitude) if candidate.longitude is not None else None,
        street_address=candidate.street_address,
        city=candidate.city,
        state_province=candidate.state_province,
        postal_code=candidate.postal_code,
        country=candidate.country,
        country_code=(
            candidate.country_code
            if candidate.country_code and candidate.country_code != "XX" and not (candidate.country_code == "US" and candidate.country and candidate.country.strip().lower() not in ("united states", "usa", "us"))
            else (AddressNormalizer.country_to_iso_code(candidate.country) if candidate.country and AddressNormalizer.country_to_iso_code(candidate.country) != "XX" else "US")
        ),
        admin_level_1=candidate.admin_level_1,
        admin_level_2=candidate.admin_level_2,
        locality=candidate.locality,
        raw_geocoding=candidate.raw_geocoding,
        photo_directories=candidate.photo_directories
        or ([candidate.photo_directory] if candidate.photo_directory else []),
        dates_visited=candidate.dates_visited,
        photo_directory=candidate.photo_directory,
        confidence_score=candidate.confidence_score,
        tags=candidate.tags,
        description=candidate.description,
        reason_to_visit=(
            ScrapingOrchestrator._clean_reason_to_visit_plain_text(candidate.reason_to_visit)
            if (
                candidate.reason_to_visit
                and ("•" in candidate.reason_to_visit or "**" in candidate.reason_to_visit or "__" in candidate.reason_to_visit)
            )
            else candidate.reason_to_visit
        ),
        official_url=candidate.official_url,
        wiki_url=candidate.wiki_url,
        related_websites=candidate.related_websites or [],
        hero_image_url=candidate.hero_image_url,
        hero_image_urls=(
            candidate.raw_geocoding.get("hero_image_urls")
            if isinstance(candidate.raw_geocoding, dict) and candidate.raw_geocoding.get("hero_image_urls")
            else ([candidate.hero_image_url] if candidate.hero_image_url else [])
        ),
        recommended_duration_hours=float(candidate.recommended_duration_hours)
        if candidate.recommended_duration_hours is not None
        else None,
        recommended_visit_days=candidate.recommended_visit_days,
        estimated_visit_time_notes=candidate.estimated_visit_time_notes,
        update_coordinates=candidate.update_coordinates,
        is_skipped=candidate.is_skipped,
        phase_state=candidate.phase_state,
        no_websites=candidate.no_websites,
        disposition_justification=candidate.disposition_justification,
        is_user_overridden=candidate.is_user_overridden,
        is_duplicate=is_dup,
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
    "/active-session",
    response_model=ActiveSessionResponse,
    summary="Check if tenant has an in-progress uncommitted ingest session",
)
@router.get(
    "/api/ingest/active-session",
    response_model=ActiveSessionResponse,
    include_in_schema=False,
)
async def get_active_session(
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> ActiveSessionResponse:
    """Returns details of any in-progress uncommitted staging session."""
    return await staging_service.get_active_session(user.id)


@router.delete(
    "/active-session",
    response_model=JobCancellationResponse,
    summary="Wipe out active uncommitted ingest session progress",
)
@router.delete(
    "/api/ingest/active-session",
    response_model=JobCancellationResponse,
    include_in_schema=False,
)
@router.post(
    "/api/ingest/active-session/wipe",
    response_model=JobCancellationResponse,
    include_in_schema=False,
)
async def wipe_active_session(
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> JobCancellationResponse:
    """Purges all uncommitted staged candidate records for the tenant."""
    purged = await staging_service.wipe_active_session(user.id)
    return JobCancellationResponse(
        job_id=UUID("00000000-0000-0000-0000-000000000000"),
        purged_count=purged,
        message=f"Wiped {purged} staged candidate record(s).",
    )


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
    completeness: str | None = Query(default=None),
    disposition: str | None = Query(default=None),
    search: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> CandidateListResponse:
    """Returns staged candidate records for the specified job with unified filtering."""
    candidates = list(await staging_service.list_candidates(user.id, job_id, phase))

    # Apply search filter
    if search and search.strip():
        q = search.strip().lower()
        candidates = [
            c
            for c in candidates
            if q in c.poi_name.lower()
            or (c.city and q in c.city.lower())
            or (c.state_province and q in c.state_province.lower())
            or (c.country and q in c.country.lower())
            or (c.description and q in c.description.lower())
        ]

    # Apply disposition filter (supports comma-separated list or single value)
    if disposition and disposition.strip():
        if disposition.strip().lower() == "none":
            candidates = []
        else:
            target_disps = {d.strip().lower() for d in disposition.split(",") if d.strip()}
            candidates = [
                c
                for c in candidates
                if (
                    c.user_disposition
                    and c.user_disposition.value.lower() in target_disps
                )
                or (
                    not c.user_disposition
                    and c.recommended_disposition
                    and c.recommended_disposition.value.lower() in target_disps
                )
            ]

    # Apply completeness filter (FR-002)
    if completeness and completeness.strip():
        comp = completeness.strip().lower()
        if comp in ("complete", "completed"):
            candidates = [
                c
                for c in candidates
                if bool(c.hero_image_url and str(c.hero_image_url).strip())
                and c.latitude is not None
                and c.longitude is not None
                and bool(c.street_address and str(c.street_address).strip())
                and (
                    bool(c.official_url and str(c.official_url).strip())
                    or bool(c.related_websites)
                    or bool(c.no_websites)
                )
            ]
        elif comp == "incomplete":
            candidates = [
                c
                for c in candidates
                if not (c.hero_image_url and str(c.hero_image_url).strip())
                or c.latitude is None
                or c.longitude is None
                or not (c.street_address and str(c.street_address).strip())
                or (
                    not (c.official_url and str(c.official_url).strip())
                    and not bool(c.related_websites)
                    and not bool(c.no_websites)
                )
            ]
        elif comp == "missing_photo":
            candidates = [c for c in candidates if not c.hero_image_url]
        elif comp == "missing_location":
            candidates = [
                c
                for c in candidates
                if c.latitude is None or c.longitude is None or not c.street_address
            ]
        elif comp == "missing_websites":
            candidates = [
                c
                for c in candidates
                if not (c.official_url and str(c.official_url).strip())
                and not bool(c.related_websites)
                and not bool(c.no_websites)
            ]

    cand_name_map = {c.id: c.poi_name for c in candidates}
    name_map = await _resolve_poi_names(candidates, user.id, poi_repo)

    return CandidateListResponse(
        job_id=job_id,
        total_candidates=len(candidates),
        candidates=[_to_candidate_response(c, name_map, cand_name_map) for c in candidates],
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
@router.put(
    "/jobs/{job_id}/candidates/{candidate_id}",
    response_model=CandidateItemResponse,
    summary="Update details, disposition, or coordinates for a candidate",
)
@router.put(
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
    """Transitions active candidates to Phase 2 and launches background parallel AI/web enrichment."""
    adv, ign = await staging_service.advance_to_phase2(user.id, job_id)
    import asyncio

    asyncio.create_task(staging_service.enrich_candidates_phase2(user.id, job_id))
    return PhaseTransitionResponse(
        job_id=job_id,
        message=f"Advanced {adv} candidate(s) to Phase 2; background enrichment queued.",
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


@router.post(
    "/jobs/{job_id}/phase2/enrich",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PhaseTransitionResponse,
    summary="Queue background AI and web enrichment for active Phase 2 candidates",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase2/enrich",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PhaseTransitionResponse,
    include_in_schema=False,
)
async def enrich_phase2(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> PhaseTransitionResponse:
    """Launches parallel background enrichment for Phase 2 candidates across 5 concurrent workers."""
    import asyncio

    from vistarae_core.domain.entities import IngestDisposition

    from services.worker.candidate_enricher import (
        CandidateEnrichmentQueueManager,
        _global_enrichment_progress,
    )

    # 1. Fetch staged candidates while the HTTP request session is active
    candidates = await staging_service.list_candidates(user.id, job_id)
    active_candidates = [
        cand
        for cand in candidates
        if not cand.is_skipped
        and (cand.user_disposition or cand.recommended_disposition)
        not in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE, IngestDisposition.EXISTING)
    ]

    # Filter to candidates missing any data (hero image, wiki url, official url, description, reason, duration, tags)
    candidates_to_enrich = [
        cand
        for cand in active_candidates
        if not cand.description
        or not cand.reason_to_visit
        or not cand.hero_image_url
        or not cand.wiki_url
        or not cand.official_url
        or cand.recommended_duration_hours is None
        or not cand.tags
    ]

    # If all candidates have complete data, fallback to active candidates; otherwise only process missing
    target_candidates = candidates_to_enrich if candidates_to_enrich else active_candidates
    candidate_ids = [cand.id for cand in target_candidates]
    total = len(candidate_ids)

    # 2. Register initial progress synchronously before returning HTTP 202
    _global_enrichment_progress[job_id] = {
        "total_count": total,
        "enriched_count": 0,
        "is_complete": total == 0,
        "percent_complete": 100 if total == 0 else 0,
        "status_message": (
            "All POIs are already complete."
            if total == 0
            else f"Queued {total} POI(s) for parallel AI and web enrichment..."
        ),
    }

    # 3. Dispatch parallel worker pool decoupled from the request session
    if total > 0:
        queue_mgr = CandidateEnrichmentQueueManager(max_concurrency=5)
        asyncio.create_task(queue_mgr.enqueue_and_process_job(user.id, job_id, candidate_ids))

    return PhaseTransitionResponse(
        job_id=job_id,
        message=f"Queued {total} POIs for parallel AI and web enrichment.",
        advanced_count=total,
        ignored_count=0,
    )


@router.get(
    "/jobs/{job_id}/phase2/progress",
    response_model=Phase2ProgressResponse,
    summary="Poll real-time progress of Phase 2 AI and web enrichment",
)
@router.get(
    "/api/ingest/jobs/{job_id}/phase2/progress",
    response_model=Phase2ProgressResponse,
    include_in_schema=False,
)
async def get_phase2_progress(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> Phase2ProgressResponse:
    """Retrieves real-time progress percentage and status of Phase 2 enrichment."""
    return staging_service.get_phase2_progress(user.id, job_id)


@router.post(
    "/jobs/{job_id}/phase2/back-to-phase1",
    response_model=PhaseTransitionResponse,
    summary="Revert candidate records from Phase 2 back to Phase 1 triage",
)
@router.post(
    "/api/ingest/jobs/{job_id}/phase2/back-to-phase1",
    response_model=PhaseTransitionResponse,
    include_in_schema=False,
)
async def back_to_phase1(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> PhaseTransitionResponse:
    """Reverts candidates from Phase 2 to Phase 1."""
    reverted = await staging_service.revert_to_phase1(user.id, job_id)
    return PhaseTransitionResponse(
        job_id=job_id,
        message=f"Reverted {reverted} candidate(s) back to Phase 1.",
        advanced_count=reverted,
        ignored_count=0,
    )


@router.post(
    "/jobs/{job_id}/candidates/{candidate_id}/enrich",
    response_model=CandidateItemResponse,
    summary="Trigger targeted single-POI AI enrichment",
)
@router.post(
    "/api/ingest/jobs/{job_id}/candidates/{candidate_id}/enrich",
    response_model=CandidateItemResponse,
    include_in_schema=False,
)
async def enrich_single_candidate(
    job_id: UUID,
    candidate_id: UUID,
    force_refresh: bool = Query(
        default=False, description="Bypass search cache and force recalculate/refresh"
    ),
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> CandidateItemResponse:
    """Enriches a single candidate on demand."""
    enriched = await staging_service.enrich_single_candidate(
        user.id, job_id, candidate_id, force_refresh=force_refresh
    )
    name_map = await _resolve_poi_names([enriched], user.id, poi_repo)
    return _to_candidate_response(enriched, name_map)


@router.post(
    "/jobs/{job_id}/enrich-all",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger asynchronous bulk AI enrichment for all eligible candidates",
)
@router.post(
    "/api/ingest/jobs/{job_id}/enrich-all",
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def enrich_all_candidates(
    job_id: UUID,
    force_refresh: bool = Query(
        default=False, description="Bypass search cache and force recalculate/refresh"
    ),
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> dict[str, Any]:
    """Launches parallel background enrichment for eligible candidates."""
    import asyncio

    candidates = await staging_service.list_candidates(user.id, job_id)
    eligible = [
        c
        for c in candidates
        if not c.is_skipped
        and (c.user_disposition or c.recommended_disposition)
        not in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE, IngestDisposition.EXISTING)
    ]
    asyncio.create_task(
        staging_service.enrich_candidates_phase2(
            user.id, job_id, force_refresh=force_refresh
        )
    )
    return {
        "job_id": str(job_id),
        "status": "enriching",
        "enqueued_candidates": len(eligible),
        "message": f"Enqueued {len(eligible)} candidate(s) for background AI enrichment.",
    }


@router.post(
    "/jobs/{job_id}/batch-edit",
    response_model=BatchEditResponse,
    summary="Batch update administrative location fields across selected candidates",
)
@router.post(
    "/api/ingest/jobs/{job_id}/batch-edit",
    response_model=BatchEditResponse,
    include_in_schema=False,
)
@router.post(
    "/jobs/{job_id}/candidates/batch-edit",
    response_model=BatchEditResponse,
    include_in_schema=False,
)
@router.post(
    "/api/ingest/jobs/{job_id}/candidates/batch-edit",
    response_model=BatchEditResponse,
    include_in_schema=False,
)
async def batch_edit_candidates(
    job_id: UUID,
    body: BatchEditCandidatesRequest,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> BatchEditResponse:
    """Updates location/date fields across multiple candidate rows."""
    count = await staging_service.batch_edit_candidates(user.id, job_id, body)
    return BatchEditResponse(updated_count=count)


@router.post(
    "/jobs/{job_id}/commit",
    response_model=CommitSummaryResponse,
    summary="Commit confirmed candidates to database pois table",
)
@router.post(
    "/api/ingest/jobs/{job_id}/commit",
    response_model=CommitSummaryResponse,
    include_in_schema=False,
)
async def commit_workbench_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> CommitSummaryResponse:
    """Commits accepted/sublocation/merged candidates to permanent PostGIS database."""
    total, created, merged = await staging_service.commit_job(user.id, job_id)
    return CommitSummaryResponse(
        job_id=job_id,
        committed_count=total,
        created_pois=created,
        merged_pois=merged,
        message=f"Successfully committed {total} POIs ({len(created)} created, {len(merged)} merged).",
    )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard staging job and delete all staging records",
)
@router.delete(
    "/api/ingest/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def discard_staging_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> None:
    """Purges all staged candidate records for the specified job."""
    await staging_service.cancel_staging(user.id, job_id)
