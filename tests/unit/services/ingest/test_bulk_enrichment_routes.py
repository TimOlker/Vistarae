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

"""Unit tests for bulk AI enrichment API routes (REQ-ENR-001 through REQ-ENR-038).

Tests:
- Premium subscription tier gating (HTTP 403 Forbidden with RFC 7807 ProblemDetails)
- Candidate selection validation (explicit IDs, all_eligible flag, 400 Bad Request on empty)
- Concurrent session conflict prevention (HTTP 409 Conflict)
- Real-time progress polling (HTTP 200 with queue/worker telemetry)
- Interactive graceful cancellation (HTTP 200)
- 5s client heartbeat recording (HTTP 200)
- Post-run audit summary retrieval (HTTP 200, HTTP 404 fallback)
- Login recovery detection (HTTP 204 No Content, HTTP 200 with unacknowledged run)
- Traveler recovery responses (RESUME, DISMISS, CANCEL)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import BulkEnrichmentResult, EnrichmentSession, User
from vistarae_core.domain.enums import BulkEnrichmentStatus
from vistarae_core.schemas.bulk_enrichment import (
    BulkEnrichmentProgressResponse,
    BulkEnrichmentSummaryResponse,
)

from services.ingest.dependencies import (
    get_bulk_enrichment_manager,
    get_bulk_enrichment_repo,
    get_candidate_repo,
    get_current_user,
)
from services.ingest.main import app
from services.worker.bulk_enrichment_manager import (
    ActiveSessionConflictError,
    BulkEnrichmentSessionManager,
)


@pytest.fixture
def premium_user() -> User:
    u = User(
        id=uuid.uuid4(),
        cognito_sub="sub-premium-traveler",
        email="premium@example.com",
    )
    u.tier = "PREMIUM"  # type: ignore[attr-defined]
    return u


@pytest.fixture
def free_user() -> User:
    u = User(
        id=uuid.uuid4(),
        cognito_sub="sub-free-traveler",
        email="free@example.com",
    )
    u.tier = "FREE"  # type: ignore[attr-defined]
    return u


@pytest.fixture
def mock_candidate_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_by_job = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_bulk_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_result_by_session_id = AsyncMock(return_value=None)
    repo.get_latest_result_by_job_id = AsyncMock(return_value=None)
    repo.get_unacknowledged_recovery_run = AsyncMock(return_value=None)
    repo.acknowledge_recovery_run = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_manager() -> MagicMock:
    mgr = MagicMock(spec=BulkEnrichmentSessionManager)
    mgr._bulk_repo = None
    mgr._candidate_repo = None
    mgr.start_session = AsyncMock()
    mgr.get_session = MagicMock(return_value=None)
    mgr.get_progress = MagicMock(return_value=None)
    mgr.cancel_session = AsyncMock()
    mgr.record_heartbeat = MagicMock(return_value=True)
    mgr.get_summary = MagicMock(return_value=None)
    return mgr


@pytest.mark.asyncio
async def test_start_bulk_enrichment_requires_premium(free_user: User) -> None:
    """Non-premium travelers receive RFC 7807 403 Forbidden (REQ-ENR-003)."""
    job_id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: free_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/bulk-enrichment/start",
                json={"all_eligible": True},
            )
            assert resp.status_code == 403
            data = resp.json()
            assert data["status"] == 403
            assert data["type"] == "https://errors.vistarae.com/forbidden/premium-required"
            assert "Premium" in data["title"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_bulk_enrichment_selection_required(premium_user: User) -> None:
    """Empty payload without candidate_ids or all_eligible returns 400 Bad Request (REQ-ENR-005)."""
    job_id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: premium_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/bulk-enrichment/start",
                json={},
            )
            assert resp.status_code == 400
            data = resp.json()
            assert data["type"] == "https://errors.vistarae.com/bad-request/selection-required"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_bulk_enrichment_all_eligible_empty(
    premium_user: User,
    mock_candidate_repo: MagicMock,
    mock_manager: MagicMock,
    mock_bulk_repo: MagicMock,
) -> None:
    """all_eligible=True when no candidates are found returns 400 Bad Request (REQ-ENR-008)."""
    job_id = uuid.uuid4()
    mock_candidate_repo.list_by_job.return_value = []

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_candidate_repo] = lambda: mock_candidate_repo
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/bulk-enrichment/start",
                json={"all_eligible": True},
            )
            assert resp.status_code == 400
            data = resp.json()
            assert data["type"] == "https://errors.vistarae.com/bad-request/empty-candidates"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_bulk_enrichment_success_explicit_ids(
    premium_user: User,
    mock_manager: MagicMock,
    mock_bulk_repo: MagicMock,
    mock_candidate_repo: MagicMock,
) -> None:
    """Explicit candidate_ids launches session returning 202 Accepted (REQ-ENR-006)."""
    job_id = uuid.uuid4()
    cand1 = uuid.uuid4()
    cand2 = uuid.uuid4()
    session_id = uuid.uuid4()

    mock_session = EnrichmentSession(
        session_id=session_id,
        user_id=premium_user.id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=2,
        concurrency_limit=3,
        canary_candidate_id=cand1,
        started_at=datetime.now(UTC),
    )
    mock_manager.start_session.return_value = mock_session

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo
    app.dependency_overrides[get_candidate_repo] = lambda: mock_candidate_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/bulk-enrichment/start",
                json={"candidate_ids": [str(cand1), str(cand2)], "force_refresh": False},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["session_id"] == str(session_id)
            assert data["total_enqueued"] == 2
            mock_manager.start_session.assert_awaited_once_with(
                user_id=premium_user.id,
                job_id=job_id,
                candidate_ids=[cand1, cand2],
                force_refresh=False,
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_bulk_enrichment_active_conflict(
    premium_user: User,
    mock_manager: MagicMock,
    mock_bulk_repo: MagicMock,
    mock_candidate_repo: MagicMock,
) -> None:
    """Concurrent active session returns HTTP 409 Conflict (REQ-ENR-009)."""
    job_id = uuid.uuid4()
    mock_manager.start_session.side_effect = ActiveSessionConflictError("Active session running")

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo
    app.dependency_overrides[get_candidate_repo] = lambda: mock_candidate_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/bulk-enrichment/start",
                json={"candidate_ids": [str(uuid.uuid4())]},
            )
            assert resp.status_code == 409
            data = resp.json()
            assert data["type"] == "https://errors.vistarae.com/conflict/session-active"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_progress_success_and_not_found(
    premium_user: User,
    mock_manager: MagicMock,
) -> None:
    """Progress endpoint returns 200 with live metrics or 404 when absent (REQ-ENR-022)."""
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    progress = BulkEnrichmentProgressResponse(
        session_id=session_id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=10,
        completed_count=4,
        success_count=3,
        issue_count=1,
        remaining_count=6,
        in_flight_count=2,
        percent_complete=40,
        elapsed_seconds=5,
        average_duration_ms=1250,
        can_cancel=True,
        status_message="Enriching candidate 4/10",
    )
    mock_manager.get_progress.return_value = progress

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/ingest/jobs/{job_id}/bulk-enrichment/progress")
            assert resp.status_code == 200
            data = resp.json()
            assert data["completed_count"] == 4
            assert data["percent_complete"] == 40

            # Test 404 when session not active
            mock_manager.get_progress.return_value = None
            resp404 = await client.get(f"/api/ingest/jobs/{job_id}/bulk-enrichment/progress")
            assert resp404.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_endpoint(
    premium_user: User,
    mock_manager: MagicMock,
) -> None:
    """Cancel endpoint triggers graceful cancellation (REQ-ENR-021)."""
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    mock_session = EnrichmentSession(
        session_id=session_id,
        user_id=premium_user.id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=5,
        concurrency_limit=3,
        canary_candidate_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
    )
    mock_manager.get_session.return_value = mock_session

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/ingest/jobs/{job_id}/bulk-enrichment/cancel")
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "DRAINING"
            mock_manager.cancel_session.assert_awaited_once_with(job_id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_heartbeat_endpoint(
    premium_user: User,
    mock_manager: MagicMock,
) -> None:
    """Heartbeat endpoint refreshes session heartbeat timestamp (REQ-ENR-032)."""
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mock_manager.record_heartbeat.return_value = True
    mock_session = EnrichmentSession(
        session_id=session_id,
        user_id=premium_user.id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=5,
        concurrency_limit=3,
        canary_candidate_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
    )
    mock_manager.get_session.return_value = mock_session

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/ingest/jobs/{job_id}/bulk-enrichment/heartbeat")
            assert resp.status_code == 200
            data = resp.json()
            assert data["acknowledged"] is True
            assert data["is_active"] is True
            assert data["session_id"] == str(session_id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_summary_endpoint(
    premium_user: User,
    mock_manager: MagicMock,
    mock_bulk_repo: MagicMock,
) -> None:
    """Summary endpoint retrieves post-run statistics (REQ-ENR-026)."""
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    summary = BulkEnrichmentSummaryResponse(
        session_id=session_id,
        job_id=job_id,
        status=BulkEnrichmentStatus.COMPLETED,
        total_candidates=10,
        succeeded_count=9,
        temporary_error_count=1,
        blocking_error_count=0,
        internal_error_count=0,
        unprocessed_count=0,
        total_duration_ms=12000,
        average_duration_ms=1200,
        total_resources_used=10,
        termination_reason="All candidates processed successfully.",
        created_at=datetime.now(UTC),
    )
    mock_manager.get_summary.return_value = summary

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_manager] = lambda: mock_manager
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/ingest/jobs/{job_id}/bulk-enrichment/summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "COMPLETED"
            assert data["succeeded_count"] == 9
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_recovery_check_empty_and_present(
    premium_user: User,
    mock_bulk_repo: MagicMock,
) -> None:
    """Recovery check returns 204 when no unacknowledged run exists, 200 when present (REQ-ENR-034)."""
    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. No unacknowledged run -> 204 No Content
            mock_bulk_repo.get_unacknowledged_recovery_run.return_value = None
            resp204 = await client.get("/api/ingest/bulk-enrichment/recovery")
            assert resp204.status_code == 204

            # 2. Unacknowledged run present -> 200 OK
            run = BulkEnrichmentResult(
                id=uuid.uuid4(),
                user_id=premium_user.id,
                job_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                status=BulkEnrichmentStatus.BLOCKED,
                processed_count=1,
                unprocessed_count=9,
                failure_count=1,
                success_count=0,
                total_resources_used=1,
                total_duration_ms=1500,
                average_duration_ms=1500,
                termination_reason="HTTP 402 Resource Exhausted",
                created_at=datetime.now(UTC),
            )
            mock_bulk_repo.get_unacknowledged_recovery_run.return_value = run

            resp200 = await client.get("/api/ingest/bulk-enrichment/recovery")
            assert resp200.status_code == 200
            data = resp200.json()
            assert data["result_id"] == str(run.id)
            assert data["status"] == "BLOCKED"
            assert data["unprocessed_count"] == 9
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_recovery_respond_actions(
    premium_user: User,
    mock_bulk_repo: MagicMock,
) -> None:
    """Traveler actions (RESUME, DISMISS, CANCEL) update state correctly (REQ-ENR-036, REQ-ENR-037, REQ-ENR-038)."""
    result_id = uuid.uuid4()
    job_id = uuid.uuid4()
    run = BulkEnrichmentResult(
        id=result_id,
        user_id=premium_user.id,
        job_id=job_id,
        session_id=uuid.uuid4(),
        status=BulkEnrichmentStatus.BLOCKED,
        processed_count=1,
        unprocessed_count=5,
        failure_count=1,
        success_count=0,
        total_resources_used=1,
        total_duration_ms=1000,
        average_duration_ms=1000,
        termination_reason="Quota exceeded",
        created_at=datetime.now(UTC),
    )

    mock_bulk_repo.acknowledge_recovery_run.return_value = run

    app.dependency_overrides[get_current_user] = lambda: premium_user
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Action: RESUME -> acknowledged=True, initial_filter='incomplete'
            resp_resume = await client.post(
                "/api/ingest/bulk-enrichment/recovery/respond",
                json={"result_id": str(result_id), "action": "resume"},
            )
            assert resp_resume.status_code == 200
            data_resume = resp_resume.json()
            assert data_resume["acknowledged"] is True
            assert data_resume["initial_filter"] == "incomplete"
            mock_bulk_repo.acknowledge_recovery_run.assert_awaited()

            # Action: DISMISS -> acknowledged=True, initial_filter=None
            resp_dismiss = await client.post(
                "/api/ingest/bulk-enrichment/recovery/respond",
                json={"result_id": str(result_id), "action": "dismiss"},
            )
            assert resp_dismiss.status_code == 200
            data_dismiss = resp_dismiss.json()
            assert data_dismiss["acknowledged"] is True
            assert data_dismiss["initial_filter"] is None

            # Action: CANCEL -> acknowledged=False
            mock_bulk_repo.get_unacknowledged_recovery_run.return_value = run
            resp_cancel = await client.post(
                "/api/ingest/bulk-enrichment/recovery/respond",
                json={"result_id": str(result_id), "action": "cancel"},
            )
            assert resp_cancel.status_code == 200
            data_cancel = resp_cancel.json()
            assert data_cancel["acknowledged"] is False
    finally:
        app.dependency_overrides.clear()
