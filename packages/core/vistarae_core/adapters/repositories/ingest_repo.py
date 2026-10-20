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

"""SQLAlchemy 2.0 repository adapter for asynchronous ingestion jobs (T-014, T-031).

Implements IIngestJobRepository:
- Strict tenant scoping (WHERE user_id = :current_user_id) per Constitution Principle 3
- Atomic progress tracking and JSONB duplicate/error appending
- Duplicate triage decision updates and job lifecycle transitions
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import IngestJobTable
from vistarae_core.domain.entities import IngestJob
from vistarae_core.domain.value_objects import DuplicateTriageStatus, IngestJobStatus
from vistarae_core.ports.repositories import IIngestJobRepository


def _row_to_ingest_job(row: IngestJobTable) -> IngestJob:
    """Maps IngestJobTable ORM instance to IngestJob domain entity."""
    return IngestJob(
        id=row.id,
        user_id=row.user_id,
        job_status=IngestJobStatus(row.job_status),
        total_rows=row.total_rows,
        processed_rows=row.processed_rows,
        duplicate_payloads=list(row.duplicate_payloads or []),
        target_list_id=row.target_list_id,
        error_summary=list(row.error_summary or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class IngestJobRepository(IIngestJobRepository):
    """PostgreSQL adapter for IngestJob aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes repository with database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create_job(self, job: IngestJob) -> IngestJob:
        """Persists a new ingestion job record.

        Args:
            job: Domain entity to persist.

        Returns:
            Created IngestJob entity.
        """
        row = IngestJobTable(
            id=job.id,
            user_id=job.user_id,
            job_status=job.job_status.value,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            duplicate_payloads=job.duplicate_payloads,
            target_list_id=job.target_list_id,
            error_summary=job.error_summary,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_ingest_job(row)

    async def get_job_by_id(self, job_id: UUID, user_id: UUID) -> IngestJob | None:
        """Retrieves an ingestion job strictly scoped by tenant user_id.

        Args:
            job_id: Primary key of the ingestion job.
            user_id: Tenant UUID.

        Returns:
            IngestJob or None if not found or unauthorized.
        """
        stmt = select(IngestJobTable).where(
            IngestJobTable.id == job_id,
            IngestJobTable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_ingest_job(row)

    async def increment_processed_rows(
        self,
        job_id: UUID,
        user_id: UUID,
        count: int = 1,
    ) -> IngestJob | None:
        """Atomically increments processed_rows and updates lifecycle state.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.
            count: Number of rows processed to add.

        Returns:
            Updated IngestJob entity or None.
        """
        stmt = (
            update(IngestJobTable)
            .where(
                IngestJobTable.id == job_id,
                IngestJobTable.user_id == user_id,
            )
            .values(
                processed_rows=IngestJobTable.processed_rows + count,
                updated_at=datetime.now(UTC),
            )
            .returning(IngestJobTable)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        # Check for status transition if all rows processed
        job = _row_to_ingest_job(row)
        if job.processed_rows >= job.total_rows and job.job_status in (
            IngestJobStatus.PENDING,
            IngestJobStatus.PROCESSING,
        ):
            return await self.recalculate_job_status(job_id, user_id)
        return job

    async def append_duplicate_payload(
        self,
        job_id: UUID,
        user_id: UUID,
        duplicate: dict[str, Any],
    ) -> IngestJob | None:
        """Appends a candidate duplicate record to duplicate_payloads JSONB.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.
            duplicate: Suspected duplicate payload dictionary.

        Returns:
            Updated IngestJob entity or None.
        """
        job = await self.get_job_by_id(job_id, user_id)
        if job is None:
            return None

        updated_duplicates = list(job.duplicate_payloads)
        updated_duplicates.append(duplicate)

        stmt = (
            update(IngestJobTable)
            .where(
                IngestJobTable.id == job_id,
                IngestJobTable.user_id == user_id,
            )
            .values(
                duplicate_payloads=updated_duplicates,
                updated_at=datetime.now(UTC),
            )
            .returning(IngestJobTable)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_ingest_job(row) if row else None

    async def append_error_summary(
        self,
        job_id: UUID,
        user_id: UUID,
        error: dict[str, Any],
    ) -> IngestJob | None:
        """Appends a row failure error object to error_summary JSONB.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.
            error: Row failure details dict.

        Returns:
            Updated IngestJob entity or None.
        """
        job = await self.get_job_by_id(job_id, user_id)
        if job is None:
            return None

        updated_errors = list(job.error_summary)
        updated_errors.append(error)

        stmt = (
            update(IngestJobTable)
            .where(
                IngestJobTable.id == job_id,
                IngestJobTable.user_id == user_id,
            )
            .values(
                error_summary=updated_errors,
                updated_at=datetime.now(UTC),
            )
            .returning(IngestJobTable)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_ingest_job(row) if row else None

    async def update_job_status(
        self,
        job_id: UUID,
        user_id: UUID,
        status: IngestJobStatus,
    ) -> IngestJob | None:
        """Updates the status of an ingestion job.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.
            status: New IngestJobStatus.

        Returns:
            Updated IngestJob entity or None.
        """
        stmt = (
            update(IngestJobTable)
            .where(
                IngestJobTable.id == job_id,
                IngestJobTable.user_id == user_id,
            )
            .values(
                job_status=status.value,
                updated_at=datetime.now(UTC),
            )
            .returning(IngestJobTable)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_ingest_job(row) if row else None

    async def get_pending_duplicates(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Retrieves duplicates currently marked PENDING_REVIEW.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.

        Returns:
            List of pending duplicate item dicts.
        """
        job = await self.get_job_by_id(job_id, user_id)
        if job is None:
            return []
        return [
            item
            for item in job.duplicate_payloads
            if item.get("triage_status") == DuplicateTriageStatus.PENDING_REVIEW.value
        ]

    async def update_duplicate_triage_decisions(
        self,
        job_id: UUID,
        user_id: UUID,
        decisions: list[dict[str, Any]],
    ) -> IngestJob | None:
        """Applies triage decisions (COMMITTED or REJECTED) to staged duplicates.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.
            decisions: List of dicts with 'row_number' and 'decision'.

        Returns:
            Updated IngestJob entity or None.
        """
        job = await self.get_job_by_id(job_id, user_id)
        if job is None:
            return None

        decision_map = {d["row_number"]: d["decision"] for d in decisions}
        updated_duplicates = []

        for item in job.duplicate_payloads:
            row_num = item.get("row_number")
            if row_num in decision_map:
                item_copy = dict(item)
                dec = decision_map[row_num]
                dec_val = dec.value if hasattr(dec, "value") else str(dec)
                item_copy["triage_status"] = dec_val
                updated_duplicates.append(item_copy)
            else:
                updated_duplicates.append(item)

        stmt = (
            update(IngestJobTable)
            .where(
                IngestJobTable.id == job_id,
                IngestJobTable.user_id == user_id,
            )
            .values(
                duplicate_payloads=updated_duplicates,
                updated_at=datetime.now(UTC),
            )
            .returning(IngestJobTable)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        # Re-evaluate overall job status
        return await self.recalculate_job_status(job_id, user_id)

    async def recalculate_job_status(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> IngestJob | None:
        """Transitions job status based on processed row counts and remaining triage items.

        Args:
            job_id: Ingest job UUID.
            user_id: Tenant UUID.

        Returns:
            Updated IngestJob entity or None.
        """
        stmt = select(IngestJobTable).where(
            IngestJobTable.id == job_id,
            IngestJobTable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        has_pending_duplicates = any(
            item.get("triage_status") == DuplicateTriageStatus.PENDING_REVIEW.value
            for item in (row.duplicate_payloads or [])
        )

        new_status = row.job_status
        if row.processed_rows >= row.total_rows and row.total_rows > 0:
            if has_pending_duplicates:
                new_status = IngestJobStatus.PARTIAL_SUCCESS.value
            else:
                new_status = IngestJobStatus.COMPLETED.value
        elif row.processed_rows > 0:
            new_status = IngestJobStatus.PROCESSING.value

        if new_status != row.job_status:
            upd_stmt = (
                update(IngestJobTable)
                .where(
                    IngestJobTable.id == job_id,
                    IngestJobTable.user_id == user_id,
                )
                .values(
                    job_status=new_status,
                    updated_at=datetime.now(UTC),
                )
                .returning(IngestJobTable)
            )
            upd_res = await self._session.execute(upd_stmt)
            row = upd_res.scalar_one()

        return _row_to_ingest_job(row)
