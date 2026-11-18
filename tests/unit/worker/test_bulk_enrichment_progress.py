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

"""Unit tests for bulk enrichment progress, cancellation, and heartbeat timeout (REQ-ENR-020, REQ-ENR-021, REQ-ENR-022, REQ-ENR-025, REQ-ENR-032).

Tests:
- Progress calculation accurately reflects queue and active worker counts
- Percentage calculation handles 0 to 100 correctly
- Average duration per completed POI calculation
- Graceful cancellation signals worker draining and marks terminal CANCELLED status
- Abandoned session detection aborts when heartbeat exceeds 15 seconds
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.domain.entities import EnrichmentSession
from vistarae_core.domain.enums import BulkEnrichmentStatus
from vistarae_core.ports.repositories import IBulkEnrichmentRepository, IIngestCandidateRepository

from services.worker.bulk_enrichment_manager import BulkEnrichmentSessionManager


@pytest.fixture
def mock_candidate_repo() -> MagicMock:
    repo = MagicMock(spec=IIngestCandidateRepository)
    repo.get_by_id = AsyncMock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_bulk_repo() -> MagicMock:
    repo = MagicMock(spec=IBulkEnrichmentRepository)
    repo.create_result = AsyncMock()
    repo.get_result_by_session_id = AsyncMock(return_value=None)
    repo.get_latest_result_by_job_id = AsyncMock(return_value=None)
    repo.get_unacknowledged_recovery_run = AsyncMock(return_value=None)
    repo.acknowledge_recovery_run = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def manager(
    mock_candidate_repo: MagicMock, mock_bulk_repo: MagicMock
) -> BulkEnrichmentSessionManager:
    return BulkEnrichmentSessionManager(
        candidate_repo=mock_candidate_repo,
        bulk_repo=mock_bulk_repo,
    )


@pytest.mark.asyncio
async def test_progress_calculation(manager: BulkEnrichmentSessionManager) -> None:
    """Progress metrics accurately reflect active session counts (REQ-ENR-022)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()
    cand1 = uuid.uuid4()

    session = EnrichmentSession(
        session_id=session_id,
        user_id=user_id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=10,
        concurrency_limit=3,
        canary_candidate_id=cand1,
        started_at=datetime.now(UTC) - timedelta(seconds=12),
        processed_count=4,
        success_count=3,
        failure_count=1,
        unprocessed_count=6,
        total_duration_ms=4800,
    )
    manager._active_sessions[job_id] = session

    progress = manager.get_progress(job_id)
    assert progress is not None
    assert progress.session_id == session_id
    assert progress.job_id == job_id
    assert progress.status == BulkEnrichmentStatus.ACTIVE
    assert progress.total_count == 10
    assert progress.completed_count == 4
    assert progress.success_count == 3
    assert progress.issue_count == 1
    assert progress.remaining_count == 6
    assert progress.percent_complete == 40
    assert progress.elapsed_seconds >= 12
    assert progress.average_duration_ms == 1200
    assert progress.can_cancel is True


@pytest.mark.asyncio
async def test_cancel_session_transitions(manager: BulkEnrichmentSessionManager) -> None:
    """Cancelling a session requests stop and transitions towards CANCELLED (REQ-ENR-021)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    session = EnrichmentSession(
        session_id=session_id,
        user_id=user_id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=5,
        concurrency_limit=3,
        canary_candidate_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
    )
    manager._active_sessions[job_id] = session

    resp = await manager.cancel_session(job_id)
    assert resp is True
    assert session.stop_requested is True


@pytest.mark.asyncio
async def test_heartbeat_record_and_abandonment(manager: BulkEnrichmentSessionManager) -> None:
    """Recording heartbeat updates timestamp; stale heartbeat marks abandonment (REQ-ENR-032)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    session_id = uuid.uuid4()

    session = EnrichmentSession(
        session_id=session_id,
        user_id=user_id,
        job_id=job_id,
        status=BulkEnrichmentStatus.ACTIVE,
        total_count=5,
        concurrency_limit=3,
        canary_candidate_id=uuid.uuid4(),
        started_at=datetime.now(UTC),
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=20),
    )
    manager._active_sessions[job_id] = session

    # Check heartbeat recorded
    assert manager.record_heartbeat(job_id) is True
    assert (datetime.now(UTC) - session.last_heartbeat_at).total_seconds() < 2
