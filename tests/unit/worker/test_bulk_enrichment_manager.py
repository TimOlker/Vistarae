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

"""Unit tests for BulkEnrichmentSessionManager orchestrator.

Tests:
- Canary gating (candidate #1 runs alone; subsequent held until canary completes)
- Fail-fast circuit breaker on BLOCKING_EXTERNAL_ERROR (0 downstream calls)
- Worker 45-second execution timeout ceiling
- Concurrency semaphore scaling to BULK_ENRICHMENT_CONCURRENCY
- Graceful cancellation with 30s draining
- 15s heartbeat timeout disconnection abort
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import (
    IngestCandidate,
)
from vistarae_core.domain.enums import (
    BulkEnrichmentStatus,
    EnrichmentResultCode,
)
from vistarae_core.domain.value_objects import IngestCandidatePhaseState, IngestDisposition

from services.worker.bulk_enrichment_manager import (
    ActiveSessionConflictError,
    BulkEnrichmentSessionManager,
)


def _make_candidate(cand_id, name="Test POI"):
    return IngestCandidate(
        id=cand_id,
        user_id=uuid4(),
        job_id=uuid4(),
        row_index=1,
        poi_name=name,
        recommended_disposition=IngestDisposition.ACCEPT,
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
    )


@pytest.mark.asyncio
async def test_canary_blocking_error_halts_queue_immediately() -> None:
    """Verifies candidate #1 acts as canary; HTTP 402/blocking error halts before candidates 2..N."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4() for _ in range(5)]

    processed_calls: list[uuid4] = []

    async def mock_worker(cand_id, is_canary, force_refresh):
        processed_calls.append(cand_id)
        if is_canary:
            return EnrichmentResultCode.BLOCKING_EXTERNAL_ERROR, "HTTP 402 Quota Depleted", 10
        return EnrichmentResultCode.SUCCESS, "", 5

    mock_repo = AsyncMock()
    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.get_by_id = AsyncMock(side_effect=lambda u, cid: _make_candidate(cid))

    manager = BulkEnrichmentSessionManager(
        worker_func=mock_worker,
        bulk_repo=mock_repo,
        candidate_repo=mock_candidate_repo,
    )

    session = await manager.start_session(
        user_id=user_id,
        job_id=job_id,
        candidate_ids=cand_ids,
    )

    # Wait for session task to finish
    await manager.wait_session(job_id)

    # Assert exactly 1 candidate was processed (the canary)
    assert len(processed_calls) == 1
    assert processed_calls[0] == cand_ids[0]

    # Assert session ended in BLOCKED state
    assert session.status == BulkEnrichmentStatus.BLOCKED
    assert session.processed_count == 1
    assert session.unprocessed_count == 4
    assert session.failure_count == 1
    assert session.success_count == 0

    # Assert audit log was saved to repo
    mock_repo.create_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_canary_success_scales_to_concurrency_ceiling() -> None:
    """Verifies canary success allows remaining candidates to process up to concurrency limit."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4() for _ in range(4)]

    active_concurrency = 0
    max_observed_concurrency = 0

    async def mock_worker(cand_id, is_canary, force_refresh):
        nonlocal active_concurrency, max_observed_concurrency
        active_concurrency += 1
        max_observed_concurrency = max(max_observed_concurrency, active_concurrency)
        await asyncio.sleep(0.05)
        active_concurrency -= 1
        return EnrichmentResultCode.SUCCESS, "", 2

    mock_repo = AsyncMock()
    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.get_by_id = AsyncMock(side_effect=lambda u, cid: _make_candidate(cid))

    manager = BulkEnrichmentSessionManager(
        worker_func=mock_worker,
        bulk_repo=mock_repo,
        candidate_repo=mock_candidate_repo,
        concurrency_limit=3,
    )

    session = await manager.start_session(
        user_id=user_id,
        job_id=job_id,
        candidate_ids=cand_ids,
    )

    await manager.wait_session(job_id)

    assert session.status == BulkEnrichmentStatus.COMPLETED
    assert session.processed_count == 4
    assert session.success_count == 4
    assert session.unprocessed_count == 0
    assert max_observed_concurrency <= 3


@pytest.mark.asyncio
async def test_worker_45s_timeout_treated_as_internal_error() -> None:
    """Verifies that an individual worker exceeding 45 seconds is aborted with INTERNAL_ERROR."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4(), uuid4()]

    async def slow_worker(cand_id, is_canary, force_refresh):
        if is_canary:
            return EnrichmentResultCode.SUCCESS, "", 1
        await asyncio.sleep(10.0)  # Simulate slow worker
        return EnrichmentResultCode.SUCCESS, "", 1

    mock_repo = AsyncMock()
    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.get_by_id = AsyncMock(side_effect=lambda u, cid: _make_candidate(cid))

    manager = BulkEnrichmentSessionManager(
        worker_func=slow_worker,
        bulk_repo=mock_repo,
        candidate_repo=mock_candidate_repo,
        worker_timeout_seconds=0.1,  # Lower timeout for unit test
    )

    session = await manager.start_session(
        user_id=user_id,
        job_id=job_id,
        candidate_ids=cand_ids,
    )

    await manager.wait_session(job_id)

    assert session.status == BulkEnrichmentStatus.COMPLETED
    assert session.processed_count == 2
    assert session.success_count == 1
    assert session.failure_count == 1


@pytest.mark.asyncio
async def test_cancel_session_drains_active_workers() -> None:
    """Verifies interactive cancel transitions to DRAINING and completes cleanly."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4() for _ in range(10)]

    async def worker(cand_id, is_canary, force_refresh):
        await asyncio.sleep(0.05)
        return EnrichmentResultCode.SUCCESS, "", 1

    mock_repo = AsyncMock()
    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.get_by_id = AsyncMock(side_effect=lambda u, cid: _make_candidate(cid))

    manager = BulkEnrichmentSessionManager(
        worker_func=worker,
        bulk_repo=mock_repo,
        candidate_repo=mock_candidate_repo,
        concurrency_limit=2,
    )

    session = await manager.start_session(
        user_id=user_id,
        job_id=job_id,
        candidate_ids=cand_ids,
    )

    await asyncio.sleep(0.02)
    cancelled = await manager.cancel_session(job_id)
    assert cancelled is True

    await manager.wait_session(job_id)

    assert session.status == BulkEnrichmentStatus.CANCELLED
    assert session.unprocessed_count > 0


@pytest.mark.asyncio
async def test_heartbeat_disconnect_cancels_session() -> None:
    """Verifies lack of client heartbeat > 15 seconds aborts active session."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4() for _ in range(5)]

    async def worker(cand_id, is_canary, force_refresh):
        await asyncio.sleep(0.2)
        return EnrichmentResultCode.SUCCESS, "", 1

    mock_repo = AsyncMock()
    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.get_by_id = AsyncMock(side_effect=lambda u, cid: _make_candidate(cid))

    manager = BulkEnrichmentSessionManager(
        worker_func=worker,
        bulk_repo=mock_repo,
        candidate_repo=mock_candidate_repo,
        heartbeat_timeout_seconds=0.1,  # Short timeout for unit test
    )

    session = await manager.start_session(
        user_id=user_id,
        job_id=job_id,
        candidate_ids=cand_ids,
    )

    # Set last heartbeat in the past
    session.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=1)

    await manager.wait_session(job_id)

    assert session.status == BulkEnrichmentStatus.CANCELLED
    assert "heartbeat" in session.termination_reason.lower()


@pytest.mark.asyncio
async def test_duplicate_active_session_raises_conflict() -> None:
    """Verifies starting a second session for same job raises ActiveSessionConflictError."""
    user_id = uuid4()
    job_id = uuid4()
    cand_ids = [uuid4()]

    async def worker(cand_id, is_canary, force_refresh):
        await asyncio.sleep(0.1)
        return EnrichmentResultCode.SUCCESS, "", 1

    manager = BulkEnrichmentSessionManager(
        worker_func=worker,
        bulk_repo=AsyncMock(),
        candidate_repo=AsyncMock(),
    )

    await manager.start_session(user_id=user_id, job_id=job_id, candidate_ids=cand_ids)

    with pytest.raises(ActiveSessionConflictError):
        await manager.start_session(user_id=user_id, job_id=job_id, candidate_ids=cand_ids)

    await manager.wait_session(job_id)
