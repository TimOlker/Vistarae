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

"""Unit tests for SqlAlchemyBulkEnrichmentRepository and concurrency resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.adapters.db.tables import BulkEnrichmentResultsTable
from vistarae_core.adapters.repositories.bulk_enrichment_repo import (
    SqlAlchemyBulkEnrichmentRepository,
    _row_to_entity,
)
from vistarae_core.domain.entities import (
    BulkEnrichmentResult,
    get_bulk_enrichment_concurrency,
)
from vistarae_core.domain.enums import BulkEnrichmentStatus


def test_get_bulk_enrichment_concurrency_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies default concurrency is 3 when environment variable is unset or invalid."""
    monkeypatch.delenv("BULK_ENRICHMENT_CONCURRENCY", raising=False)
    assert get_bulk_enrichment_concurrency() == 3

    monkeypatch.setenv("BULK_ENRICHMENT_CONCURRENCY", "invalid")
    assert get_bulk_enrichment_concurrency() == 3


def test_get_bulk_enrichment_concurrency_bounding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies concurrency is strictly bounded between 1 and 10."""
    monkeypatch.setenv("BULK_ENRICHMENT_CONCURRENCY", "-5")
    assert get_bulk_enrichment_concurrency() == 1

    monkeypatch.setenv("BULK_ENRICHMENT_CONCURRENCY", "0")
    assert get_bulk_enrichment_concurrency() == 1

    monkeypatch.setenv("BULK_ENRICHMENT_CONCURRENCY", "5")
    assert get_bulk_enrichment_concurrency() == 5

    monkeypatch.setenv("BULK_ENRICHMENT_CONCURRENCY", "100")
    assert get_bulk_enrichment_concurrency() == 10


def test_row_to_entity_mapping() -> None:
    """Verifies conversion from ORM table row to domain entity."""
    res_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)

    mock_row = MagicMock(spec=BulkEnrichmentResultsTable)
    mock_row.id = res_id
    mock_row.user_id = user_id
    mock_row.job_id = job_id
    mock_row.session_id = session_id
    mock_row.status = "COMPLETED"
    mock_row.processed_count = 10
    mock_row.unprocessed_count = 0
    mock_row.failure_count = 1
    mock_row.success_count = 9
    mock_row.total_resources_used = 150
    mock_row.total_duration_ms = 12000
    mock_row.average_duration_ms = 1200
    mock_row.termination_reason = "All records processed."
    mock_row.acknowledged_at = None
    mock_row.created_at = now
    mock_row.updated_at = now

    entity = _row_to_entity(mock_row)
    assert entity.id == res_id
    assert entity.user_id == user_id
    assert entity.status == BulkEnrichmentStatus.COMPLETED
    assert entity.success_count == 9
    assert entity.total_resources_used == 150


@pytest.mark.asyncio
async def test_create_result() -> None:
    """Verifies create_result adds to session and flushes."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)

    res_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    session_id = uuid4()

    result_entity = BulkEnrichmentResult(
        id=res_id,
        user_id=user_id,
        job_id=job_id,
        session_id=session_id,
        status=BulkEnrichmentStatus.COMPLETED,
        processed_count=5,
        unprocessed_count=0,
        failure_count=0,
        success_count=5,
        total_resources_used=50,
        total_duration_ms=4500,
        average_duration_ms=900,
        termination_reason="Finished successfully",
    )

    persisted = await repo.create_result(result_entity)
    assert persisted.id == res_id
    assert persisted.user_id == user_id
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_result_by_session_id_hit() -> None:
    """Verifies get_result_by_session_id retrieves matching record."""
    mock_session = AsyncMock()
    mock_exec = MagicMock()
    user_id = uuid4()
    session_id = uuid4()

    mock_row = MagicMock(spec=BulkEnrichmentResultsTable)
    mock_row.id = uuid4()
    mock_row.user_id = user_id
    mock_row.job_id = uuid4()
    mock_row.session_id = session_id
    mock_row.status = "BLOCKED"
    mock_row.processed_count = 1
    mock_row.unprocessed_count = 4
    mock_row.failure_count = 1
    mock_row.success_count = 0
    mock_row.total_resources_used = 12
    mock_row.total_duration_ms = 850
    mock_row.average_duration_ms = 850
    mock_row.termination_reason = "External quota exceeded"
    mock_row.acknowledged_at = None
    mock_row.created_at = datetime.now(UTC)
    mock_row.updated_at = datetime.now(UTC)

    mock_exec.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_exec

    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)
    result = await repo.get_result_by_session_id(user_id, session_id)

    assert result is not None
    assert result.status == BulkEnrichmentStatus.BLOCKED
    assert result.session_id == session_id


@pytest.mark.asyncio
async def test_get_result_by_session_id_miss() -> None:
    """Verifies get_result_by_session_id returns None on miss."""
    mock_session = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_exec

    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)
    result = await repo.get_result_by_session_id(uuid4(), uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_result_by_job_id() -> None:
    """Verifies get_latest_result_by_job_id retrieves most recent record."""
    mock_session = AsyncMock()
    mock_exec = MagicMock()
    user_id = uuid4()
    job_id = uuid4()

    mock_row = MagicMock(spec=BulkEnrichmentResultsTable)
    mock_row.id = uuid4()
    mock_row.user_id = user_id
    mock_row.job_id = job_id
    mock_row.session_id = uuid4()
    mock_row.status = "COMPLETED"
    mock_row.processed_count = 12
    mock_row.unprocessed_count = 0
    mock_row.failure_count = 0
    mock_row.success_count = 12
    mock_row.total_resources_used = 120
    mock_row.total_duration_ms = 9600
    mock_row.average_duration_ms = 800
    mock_row.termination_reason = "Complete"
    mock_row.acknowledged_at = None
    mock_row.created_at = datetime.now(UTC)
    mock_row.updated_at = datetime.now(UTC)

    mock_exec.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_exec

    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)
    result = await repo.get_latest_result_by_job_id(user_id, job_id)
    assert result is not None
    assert result.job_id == job_id


@pytest.mark.asyncio
async def test_get_unacknowledged_recovery_run() -> None:
    """Verifies get_unacknowledged_recovery_run returns unacknowledged BLOCKED run."""
    mock_session = AsyncMock()
    mock_exec = MagicMock()
    user_id = uuid4()

    mock_row = MagicMock(spec=BulkEnrichmentResultsTable)
    mock_row.id = uuid4()
    mock_row.user_id = user_id
    mock_row.job_id = uuid4()
    mock_row.session_id = uuid4()
    mock_row.status = "BLOCKED"
    mock_row.processed_count = 1
    mock_row.unprocessed_count = 9
    mock_row.failure_count = 1
    mock_row.success_count = 0
    mock_row.total_resources_used = 10
    mock_row.total_duration_ms = 500
    mock_row.average_duration_ms = 500
    mock_row.termination_reason = "Quota exhausted"
    mock_row.acknowledged_at = None
    mock_row.created_at = datetime.now(UTC)
    mock_row.updated_at = datetime.now(UTC)

    mock_exec.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_exec

    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)
    recovery = await repo.get_unacknowledged_recovery_run(user_id)

    assert recovery is not None
    assert recovery.status == BulkEnrichmentStatus.BLOCKED
    assert recovery.unprocessed_count == 9


@pytest.mark.asyncio
async def test_acknowledge_recovery_run() -> None:
    """Verifies acknowledge_recovery_run updates acknowledged_at timestamp."""
    mock_session = AsyncMock()
    mock_exec = MagicMock()
    user_id = uuid4()
    result_id = uuid4()
    ack_time = datetime.now(UTC)

    mock_row = MagicMock(spec=BulkEnrichmentResultsTable)
    mock_row.id = result_id
    mock_row.user_id = user_id
    mock_row.job_id = uuid4()
    mock_row.session_id = uuid4()
    mock_row.status = "BLOCKED"
    mock_row.processed_count = 2
    mock_row.unprocessed_count = 8
    mock_row.failure_count = 1
    mock_row.success_count = 1
    mock_row.total_resources_used = 25
    mock_row.total_duration_ms = 1500
    mock_row.average_duration_ms = 750
    mock_row.termination_reason = "Quota limit"
    mock_row.acknowledged_at = ack_time
    mock_row.created_at = datetime.now(UTC)
    mock_row.updated_at = ack_time

    mock_exec.scalar_one_or_none.return_value = mock_row
    mock_session.execute.return_value = mock_exec

    repo = SqlAlchemyBulkEnrichmentRepository(mock_session)
    updated = await repo.acknowledge_recovery_run(user_id, result_id, ack_time)

    assert updated is not None
    assert updated.acknowledged_at == ack_time
