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

"""FastAPI router for canary-gated bulk AI enrichment and recovery workflows.

Implements REQ-ENR-001 through REQ-ENR-038:
- Premium subscription tier enforcement (HTTP 403 Forbidden with ProblemDetails)
- Selection scoping & confirmation prompts
- Session initiation, live progress polling, and cancellation
- Client heartbeat tracking for abandoned session detection
- Post-run audit summary retrieval
- Login recovery check and traveler response endpoints
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from vistarae_core.domain.entities import User
from vistarae_core.domain.enums import BulkEnrichmentStatus, IngestDisposition, RecoveryPromptAction
from vistarae_core.ports.repositories import IBulkEnrichmentRepository, IIngestCandidateRepository
from vistarae_core.schemas.bulk_enrichment import (
    BulkEnrichmentCancelResponse,
    BulkEnrichmentHeartbeatResponse,
    BulkEnrichmentInitiateRequest,
    BulkEnrichmentInitiateResponse,
    BulkEnrichmentProgressResponse,
    BulkEnrichmentRecoveryActionRequest,
    BulkEnrichmentRecoveryResponse,
    BulkEnrichmentSummaryResponse,
)

from services.ingest.dependencies import (
    get_bulk_enrichment_manager,
    get_bulk_enrichment_repo,
    get_candidate_repo,
    get_current_user,
)
from services.worker.bulk_enrichment_manager import (
    ActiveSessionConflictError,
    BulkEnrichmentSessionManager,
)

logger = logging.getLogger("vistarae.ingest.bulk_enrichment")

router = APIRouter(tags=["bulk-enrichment"])


def _assert_premium_user(user: User, request: Request) -> None:
    """Verifies that the authenticated user possesses a PREMIUM subscription tier.

    Raises:
        HTTPException: 403 Forbidden with RFC 7807 ProblemDetails payload if non-premium.
    """
    tier_val = getattr(user, "tier", None)
    if tier_val is None and hasattr(user, "subscription_tier"):
        tier_val = user.subscription_tier

    is_premium = False
    if tier_val is not None:
        is_premium = str(getattr(tier_val, "value", tier_val)).upper() in ("PREMIUM", "ADMIN")

    if not is_premium:
        logger.warning(
            "User %s attempted bulk AI enrichment without active PREMIUM subscription", user.id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://errors.vistarae.com/forbidden/premium-required",
                "title": "Premium Subscription Required",
                "status": 403,
                "detail": "Bulk AI enrichment is restricted exclusively to travelers with an active Premium subscription.",
                "instance": str(request.url.path),
            },
        )


@router.post(
    "/jobs/{job_id}/bulk-enrichment/start",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BulkEnrichmentInitiateResponse,
    summary="Initiate canary-gated bulk AI enrichment session",
)
@router.post(
    "/api/ingest/jobs/{job_id}/bulk-enrichment/start",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BulkEnrichmentInitiateResponse,
    include_in_schema=False,
)
async def start_bulk_enrichment(
    job_id: UUID,
    body: BulkEnrichmentInitiateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    manager: BulkEnrichmentSessionManager = Depends(get_bulk_enrichment_manager),
    candidate_repo: IIngestCandidateRepository = Depends(get_candidate_repo),
    bulk_repo: IBulkEnrichmentRepository = Depends(get_bulk_enrichment_repo),
) -> BulkEnrichmentInitiateResponse:
    """Launches a canary-gated bulk AI enrichment session."""
    _assert_premium_user(user, request)

    target_candidate_ids: list[UUID] = []

    if body.candidate_ids:
        target_candidate_ids = body.candidate_ids
    elif body.all_eligible:
        candidates = await candidate_repo.list_by_job(user.id, job_id)
        target_candidate_ids = [
            c.id
            for c in candidates
            if c.recommended_disposition != IngestDisposition.IGNORE
            and c.user_disposition != IngestDisposition.IGNORE
        ]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://errors.vistarae.com/bad-request/selection-required",
                "title": "Candidate Selection Required",
                "status": 400,
                "detail": "Either explicit candidate_ids or all_eligible=True confirmation must be provided.",
                "instance": str(request.url.path),
            },
        )

    if not target_candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://errors.vistarae.com/bad-request/empty-candidates",
                "title": "No Eligible Candidates",
                "status": 400,
                "detail": "No eligible non-ignored candidates were found to enrich for this import job.",
                "instance": str(request.url.path),
            },
        )

    # In unit tests without session_factory, bind test mock repositories
    if getattr(manager, "_session_factory", None) is None and getattr(manager, "_bulk_repo", None) is None:
        manager._bulk_repo = bulk_repo
    if getattr(manager, "_candidate_repo", None) is None:
        manager._candidate_repo = candidate_repo

    try:
        session = await manager.start_session(
            user_id=user.id,
            job_id=job_id,
            candidate_ids=target_candidate_ids,
            force_refresh=body.force_refresh,
        )
    except ActiveSessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://errors.vistarae.com/conflict/session-active",
                "title": "Enrichment Session Already Active",
                "status": 409,
                "detail": f"An enrichment session is already actively running for job {job_id}.",
                "instance": str(request.url.path),
            },
        ) from exc

    return BulkEnrichmentInitiateResponse(
        session_id=session.session_id,
        job_id=session.job_id,
        total_enqueued=session.total_count,
        status=session.status,
        message=f"Enqueued {session.total_count} candidate(s); canary dispatched.",
    )


@router.get(
    "/jobs/{job_id}/bulk-enrichment/progress",
    response_model=BulkEnrichmentProgressResponse,
    summary="Poll real-time metrics and progress of active enrichment session",
)
@router.get(
    "/api/ingest/jobs/{job_id}/bulk-enrichment/progress",
    response_model=BulkEnrichmentProgressResponse,
    include_in_schema=False,
)
async def get_bulk_enrichment_progress(
    job_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    manager: BulkEnrichmentSessionManager = Depends(get_bulk_enrichment_manager),
) -> BulkEnrichmentProgressResponse:
    """Retrieves live telemetry progress metrics for the active session."""
    progress = manager.get_progress(job_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://errors.vistarae.com/not-found/session-not-found",
                "title": "Session Not Found",
                "status": 404,
                "detail": f"No active or recent bulk enrichment session was found for job {job_id}.",
                "instance": str(request.url.path),
            },
        )
    return progress


@router.post(
    "/jobs/{job_id}/bulk-enrichment/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BulkEnrichmentCancelResponse,
    summary="Request graceful cancellation and worker draining",
)
@router.post(
    "/api/ingest/jobs/{job_id}/bulk-enrichment/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BulkEnrichmentCancelResponse,
    include_in_schema=False,
)
async def cancel_bulk_enrichment(
    job_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    manager: BulkEnrichmentSessionManager = Depends(get_bulk_enrichment_manager),
) -> BulkEnrichmentCancelResponse:
    """Requests graceful cancellation and worker draining."""
    session = manager.get_session(job_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://errors.vistarae.com/not-found/session-not-found",
                "title": "Session Not Found",
                "status": 404,
                "detail": f"No active enrichment session to cancel for job {job_id}.",
                "instance": str(request.url.path),
            },
        )

    await manager.cancel_session(job_id)
    return BulkEnrichmentCancelResponse(
        session_id=session.session_id,
        status=BulkEnrichmentStatus.DRAINING,
        message="Cancellation accepted; session transitioning to draining state.",
    )


@router.post(
    "/jobs/{job_id}/bulk-enrichment/heartbeat",
    response_model=BulkEnrichmentHeartbeatResponse,
    summary="Record client heartbeat to prevent disconnection cancellation",
)
@router.post(
    "/api/ingest/jobs/{job_id}/bulk-enrichment/heartbeat",
    response_model=BulkEnrichmentHeartbeatResponse,
    include_in_schema=False,
)
async def record_bulk_enrichment_heartbeat(
    job_id: UUID,
    user: User = Depends(get_current_user),
    manager: BulkEnrichmentSessionManager = Depends(get_bulk_enrichment_manager),
) -> BulkEnrichmentHeartbeatResponse:
    """Records client heartbeat signal."""
    recorded = manager.record_heartbeat(job_id)
    session = manager.get_session(job_id)
    sid = session.session_id if session else uuid4()
    return BulkEnrichmentHeartbeatResponse(
        session_id=sid,
        acknowledged=recorded,
        is_active=bool(
            session
            and session.status
            in (BulkEnrichmentStatus.ACTIVE, BulkEnrichmentStatus.CANARY_DISPATCH)
        ),
    )


@router.get(
    "/jobs/{job_id}/bulk-enrichment/summary",
    response_model=BulkEnrichmentSummaryResponse,
    summary="Retrieve post-processing audit summary for the latest completed session",
)
@router.get(
    "/api/ingest/jobs/{job_id}/bulk-enrichment/summary",
    response_model=BulkEnrichmentSummaryResponse,
    include_in_schema=False,
)
async def get_bulk_enrichment_summary(
    job_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    manager: BulkEnrichmentSessionManager = Depends(get_bulk_enrichment_manager),
    bulk_repo: IBulkEnrichmentRepository = Depends(get_bulk_enrichment_repo),
) -> BulkEnrichmentSummaryResponse:
    """Retrieves post-run summary window statistics."""
    summary = manager.get_summary(job_id)
    if summary:
        return summary

    result = await bulk_repo.get_latest_result_by_job_id(user.id, job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://errors.vistarae.com/not-found/summary-not-found",
                "title": "Summary Not Found",
                "status": 404,
                "detail": f"No completed enrichment summary found for job {job_id}.",
                "instance": str(request.url.path),
            },
        )

    return BulkEnrichmentSummaryResponse(
        session_id=result.session_id,
        job_id=result.job_id,
        status=result.status,
        total_candidates=result.processed_count + result.unprocessed_count,
        succeeded_count=result.success_count,
        temporary_error_count=0,
        blocking_error_count=1 if result.status == BulkEnrichmentStatus.BLOCKED else 0,
        internal_error_count=1 if result.status == BulkEnrichmentStatus.FAILED else 0,
        unprocessed_count=result.unprocessed_count,
        total_duration_ms=result.total_duration_ms,
        average_duration_ms=result.average_duration_ms,
        total_resources_used=result.total_resources_used,
        termination_reason=result.termination_reason,
        created_at=result.created_at,
    )


@router.get(
    "/bulk-enrichment/recovery",
    response_model=BulkEnrichmentRecoveryResponse,
    responses={204: {"description": "No unacknowledged recovery run found"}},
    summary="Check for unacknowledged failed or blocked enrichment runs upon login",
)
@router.get(
    "/api/ingest/bulk-enrichment/recovery",
    response_model=BulkEnrichmentRecoveryResponse,
    responses={204: {"description": "No unacknowledged recovery run found"}},
    include_in_schema=False,
)
async def check_bulk_enrichment_recovery(
    response: Response,
    user: User = Depends(get_current_user),
    bulk_repo: IBulkEnrichmentRepository = Depends(get_bulk_enrichment_repo),
) -> BulkEnrichmentRecoveryResponse | Response:
    """Checks for unacknowledged failed or blocked enrichment runs requiring traveler response."""
    run = await bulk_repo.get_unacknowledged_recovery_run(user.id)
    if not run:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return BulkEnrichmentRecoveryResponse(
        result_id=run.id,
        job_id=run.job_id,
        session_id=run.session_id,
        status=run.status,
        failed_at=run.created_at,
        unprocessed_count=run.unprocessed_count,
        failure_count=run.failure_count,
        total_candidates=run.processed_count + run.unprocessed_count,
        termination_reason=run.termination_reason,
    )


@router.post(
    "/bulk-enrichment/recovery/respond",
    summary="Submit user response to the login recovery prompt",
)
@router.post(
    "/api/ingest/bulk-enrichment/recovery/respond",
    include_in_schema=False,
)
async def respond_bulk_enrichment_recovery(
    body: BulkEnrichmentRecoveryActionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    bulk_repo: IBulkEnrichmentRepository = Depends(get_bulk_enrichment_repo),
) -> dict[str, Any]:
    """Submits traveler action in response to login recovery prompt."""
    now = datetime.now(UTC)
    acknowledged = False
    initial_filter = None

    if body.action in (RecoveryPromptAction.RESUME, RecoveryPromptAction.DISMISS):
        updated = await bulk_repo.acknowledge_recovery_run(user.id, body.result_id, now)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "https://errors.vistarae.com/not-found/recovery-run-not-found",
                    "title": "Recovery Run Not Found",
                    "status": 404,
                    "detail": f"Recovery run {body.result_id} was not found for this user.",
                    "instance": str(request.url.path),
                },
            )
        acknowledged = True
        job_id = updated.job_id
        if body.action == RecoveryPromptAction.RESUME:
            initial_filter = "incomplete"
    else:
        # Cancel / dismiss temporarily: do not update acknowledged_at
        run = await bulk_repo.get_unacknowledged_recovery_run(user.id)
        job_id = run.job_id if run else uuid4()

    return {
        "acknowledged": acknowledged,
        "job_id": str(job_id),
        "initial_filter": initial_filter,
    }
