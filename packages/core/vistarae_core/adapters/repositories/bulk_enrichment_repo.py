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

"""SQLAlchemy 2.0 repository adapter for bulk enrichment results.

Implements IBulkEnrichmentRepository adhering to Constitution Principle 3:
- Pure async SQLAlchemy 2.0 operations
- Strict tenant filtering (WHERE user_id = :current_user_id)
- Statement caching disabled (statement_cache_size: 0 compatible with PgBouncer)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import BulkEnrichmentResultsTable
from vistarae_core.domain.entities import BulkEnrichmentResult
from vistarae_core.domain.enums import BulkEnrichmentStatus
from vistarae_core.ports.repositories import IBulkEnrichmentRepository

logger = logging.getLogger("vistarae.repository.bulk_enrichment")


def _row_to_entity(row: BulkEnrichmentResultsTable) -> BulkEnrichmentResult:
    """Maps a BulkEnrichmentResultsTable ORM row to domain entity."""
    return BulkEnrichmentResult(
        id=row.id,
        user_id=row.user_id,
        job_id=row.job_id,
        session_id=row.session_id,
        status=BulkEnrichmentStatus(row.status),
        processed_count=row.processed_count,
        unprocessed_count=row.unprocessed_count,
        failure_count=row.failure_count,
        success_count=row.success_count,
        total_resources_used=row.total_resources_used,
        total_duration_ms=row.total_duration_ms,
        average_duration_ms=row.average_duration_ms,
        termination_reason=row.termination_reason,
        candidate_issues=getattr(row, "candidate_issues", []) or [],
        acknowledged_at=row.acknowledged_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyBulkEnrichmentRepository(IBulkEnrichmentRepository):
    """SQLAlchemy 2.0 implementation of IBulkEnrichmentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an active AsyncSession.

        Args:
            session: AsyncSession bound to Neon PgBouncer transaction-mode pool.
        """
        self._session = session

    async def create_result(self, result: BulkEnrichmentResult) -> BulkEnrichmentResult:
        """Persists a new bulk enrichment audit record.

        Args:
            result: Domain entity to persist.

        Returns:
            The persisted BulkEnrichmentResult.
        """
        now = datetime.now(UTC)
        row = BulkEnrichmentResultsTable(
            id=result.id or uuid4(),
            user_id=result.user_id,
            job_id=result.job_id,
            session_id=result.session_id,
            status=result.status.value if hasattr(result.status, "value") else str(result.status),
            processed_count=result.processed_count,
            unprocessed_count=result.unprocessed_count,
            failure_count=result.failure_count,
            success_count=result.success_count,
            total_resources_used=result.total_resources_used,
            total_duration_ms=result.total_duration_ms,
            average_duration_ms=result.average_duration_ms,
            termination_reason=result.termination_reason,
            candidate_issues=result.candidate_issues or [],
            acknowledged_at=result.acknowledged_at,
            created_at=result.created_at or now,
            updated_at=result.updated_at or now,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_entity(row)

    async def get_result_by_session_id(
        self, user_id: UUID, session_id: UUID
    ) -> BulkEnrichmentResult | None:
        """Retrieves an audit result by session UUID with strict tenant isolation.

        Args:
            user_id: Owning tenant UUID.
            session_id: Target session UUID.

        Returns:
            Matching BulkEnrichmentResult or None if not found.
        """
        stmt = select(BulkEnrichmentResultsTable).where(
            BulkEnrichmentResultsTable.user_id == user_id,
            BulkEnrichmentResultsTable.session_id == session_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def get_latest_result_by_job_id(
        self, user_id: UUID, job_id: UUID
    ) -> BulkEnrichmentResult | None:
        """Retrieves the most recent audit result for a staging job.

        Args:
            user_id: Owning tenant UUID.
            job_id: Staging job UUID.

        Returns:
            Latest BulkEnrichmentResult or None if not found.
        """
        stmt = (
            select(BulkEnrichmentResultsTable)
            .where(
                BulkEnrichmentResultsTable.user_id == user_id,
                BulkEnrichmentResultsTable.job_id == job_id,
            )
            .order_by(BulkEnrichmentResultsTable.created_at.desc())
            .limit(1)
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def get_unacknowledged_recovery_run(self, user_id: UUID) -> BulkEnrichmentResult | None:
        """Finds the most recent unacknowledged failed or blocked enrichment run.

        Queries where status IN ('BLOCKED', 'FAILED') and acknowledged_at IS NULL,
        ordered by created_at DESC LIMIT 1.

        Args:
            user_id: Owning tenant UUID.

        Returns:
            Unacknowledged BulkEnrichmentResult or None.
        """
        stmt = (
            select(BulkEnrichmentResultsTable)
            .where(
                BulkEnrichmentResultsTable.user_id == user_id,
                BulkEnrichmentResultsTable.acknowledged_at.is_(None),
                BulkEnrichmentResultsTable.status.in_(
                    [BulkEnrichmentStatus.BLOCKED.value, BulkEnrichmentStatus.FAILED.value]
                ),
            )
            .order_by(BulkEnrichmentResultsTable.created_at.desc())
            .limit(1)
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def acknowledge_recovery_run(
        self, user_id: UUID, result_id: UUID, acknowledged_at: datetime
    ) -> BulkEnrichmentResult | None:
        """Updates acknowledged_at on a recovery run record with tenant isolation.

        Args:
            user_id: Owning tenant UUID.
            result_id: Audit record UUID.
            acknowledged_at: Acknowledgment timestamp.

        Returns:
            Updated BulkEnrichmentResult or None if not found.
        """
        now = datetime.now(UTC)
        stmt = (
            update(BulkEnrichmentResultsTable)
            .where(
                BulkEnrichmentResultsTable.user_id == user_id,
                BulkEnrichmentResultsTable.id == result_id,
            )
            .values(acknowledged_at=acknowledged_at, updated_at=now)
            .returning(BulkEnrichmentResultsTable)
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None
