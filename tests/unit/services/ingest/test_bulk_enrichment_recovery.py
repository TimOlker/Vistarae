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

"""Unit tests for session audit persistence and login recovery workflows (REQ-ENR-026, REQ-ENR-033, REQ-ENR-034, SC-007, SC-008).

Tests:
- Final session state persistence to bulk_enrichment_results with unacknowledged flag
- Querying unacknowledged failed or blocked runs upon login
- Traveler prompt actions: RESUME (filter incomplete), DISMISS (ack only), CANCEL (unacknowledged)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import BulkEnrichmentResult, EnrichmentSession, User
from vistarae_core.domain.enums import BulkEnrichmentStatus
from vistarae_core.ports.repositories import IBulkEnrichmentRepository

from services.ingest.dependencies import get_bulk_enrichment_repo, get_current_user
from services.ingest.main import app
from services.worker.bulk_enrichment_manager import BulkEnrichmentSessionManager


@pytest.fixture
def mock_user() -> User:
    u = User(
        id=uuid.uuid4(),
        cognito_sub="sub-traveler-recovery",
        email="traveler@example.com",
    )
    u.tier = "PREMIUM"  # type: ignore[attr-defined]
    return u


@pytest.fixture
def mock_bulk_repo() -> MagicMock:
    repo = MagicMock(spec=IBulkEnrichmentRepository)
    repo.create_result = AsyncMock()
    repo.get_result_by_session_id = AsyncMock(return_value=None)
    repo.get_latest_result_by_job_id = AsyncMock(return_value=None)
    repo.get_unacknowledged_recovery_run = AsyncMock(return_value=None)
    repo.acknowledge_recovery_run = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_session_audit_persisted_on_finalize(
    mock_bulk_repo: MagicMock, mock_user: User
) -> None:
    """Audit record is created in bulk_enrichment_results with correct unacknowledged state (REQ-ENR-033, SC-007)."""
    manager = BulkEnrichmentSessionManager(bulk_repo=mock_bulk_repo)
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    session = EnrichmentSession(
        session_id=session_id,
        user_id=mock_user.id,
        job_id=job_id,
        status=BulkEnrichmentStatus.BLOCKED,
        total_count=10,
        concurrency_limit=3,
        canary_candidate_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        processed_count=1,
        success_count=0,
        failure_count=1,
        unprocessed_count=9,
        total_resources_used=1,
        total_duration_ms=800,
        termination_reason="HTTP 402 Resource Exhausted",
    )

    await manager._finalize_and_audit(session, temp_errors=0, blocking_errors=1, internal_errors=0)

    mock_bulk_repo.create_result.assert_awaited_once()
    saved_result: BulkEnrichmentResult = mock_bulk_repo.create_result.call_args[0][0]
    assert saved_result.session_id == session_id
    assert saved_result.status == BulkEnrichmentStatus.BLOCKED
    assert saved_result.processed_count == 1
    assert saved_result.unprocessed_count == 9
    assert saved_result.acknowledged_at is None  # Must be null for BLOCKED to prompt on login


@pytest.mark.asyncio
async def test_login_recovery_returns_204_when_no_unacknowledged(
    mock_user: User,
    mock_bulk_repo: MagicMock,
) -> None:
    """When no unacknowledged run exists, recovery endpoint returns 204 No Content (REQ-ENR-034)."""
    mock_bulk_repo.get_unacknowledged_recovery_run.return_value = None
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/ingest/bulk-enrichment/recovery")
            assert resp.status_code == 204
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_recovery_returns_200_and_details_when_unacknowledged(
    mock_user: User,
    mock_bulk_repo: MagicMock,
) -> None:
    """When an unacknowledged failed/blocked run exists, returns 200 with details (REQ-ENR-034, SC-008)."""
    result_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    run = BulkEnrichmentResult(
        id=result_id,
        user_id=mock_user.id,
        job_id=job_id,
        session_id=session_id,
        status=BulkEnrichmentStatus.BLOCKED,
        processed_count=1,
        unprocessed_count=15,
        failure_count=1,
        success_count=0,
        total_resources_used=1,
        total_duration_ms=1200,
        average_duration_ms=1200,
        termination_reason="HTTP 402 Payment Required",
        created_at=datetime.now(UTC),
    )
    mock_bulk_repo.get_unacknowledged_recovery_run.return_value = run

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/ingest/bulk-enrichment/recovery")
            assert resp.status_code == 200
            data = resp.json()
            assert data["result_id"] == str(result_id)
            assert data["job_id"] == str(job_id)
            assert data["status"] == "BLOCKED"
            assert data["unprocessed_count"] == 15
            assert "402" in data["termination_reason"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_recovery_actions_resume_and_dismiss(
    mock_user: User,
    mock_bulk_repo: MagicMock,
) -> None:
    """Action 'resume' sets acknowledged_at and routes with initial_filter='incomplete' (REQ-ENR-036, REQ-ENR-037)."""
    result_id = uuid.uuid4()
    job_id = uuid.uuid4()

    run = BulkEnrichmentResult(
        id=result_id,
        user_id=mock_user.id,
        job_id=job_id,
        session_id=uuid.uuid4(),
        status=BulkEnrichmentStatus.BLOCKED,
        processed_count=2,
        unprocessed_count=8,
        failure_count=1,
        success_count=1,
        total_resources_used=2,
        total_duration_ms=2000,
        average_duration_ms=1000,
        termination_reason="Quota reached",
        created_at=datetime.now(UTC),
    )
    mock_bulk_repo.acknowledge_recovery_run.return_value = run

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_bulk_enrichment_repo] = lambda: mock_bulk_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Action: resume
            resp = await client.post(
                "/api/ingest/bulk-enrichment/recovery/respond",
                json={"result_id": str(result_id), "action": "resume"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["acknowledged"] is True
            assert data["job_id"] == str(job_id)
            assert data["initial_filter"] == "incomplete"
            mock_bulk_repo.acknowledge_recovery_run.assert_awaited()

            # Action: dismiss
            resp_dismiss = await client.post(
                "/api/ingest/bulk-enrichment/recovery/respond",
                json={"result_id": str(result_id), "action": "dismiss"},
            )
            assert resp_dismiss.status_code == 200
            data_dismiss = resp_dismiss.json()
            assert data_dismiss["acknowledged"] is True
            assert data_dismiss["initial_filter"] is None
    finally:
        app.dependency_overrides.clear()
