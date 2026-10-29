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

"""SQLAlchemy 2.0 repository adapter for staged ingest candidates (T-008).

Implements IIngestCandidateRepository:
- Strict tenant filtering (WHERE user_id = :current_user_id) per Constitution Principle 3
- Atomic batch creation and status transitions
- Spatial Point geometry synchronization via ST_SetSRID and ST_MakePoint
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import IngestCandidateTable
from vistarae_core.domain.entities import IngestCandidate
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
)
from vistarae_core.ports.repositories import IIngestCandidateRepository


def _row_to_entity(row: IngestCandidateTable) -> IngestCandidate:
    """Maps IngestCandidateTable ORM row to IngestCandidate domain entity."""
    return IngestCandidate(
        id=row.id,
        user_id=row.user_id,
        job_id=row.job_id,
        row_index=row.row_index,
        poi_name=row.poi_name,
        recommended_disposition=IngestDisposition(row.recommended_disposition),
        user_disposition=IngestDisposition(row.user_disposition) if row.user_disposition else None,
        matched_existing_poi_id=row.matched_existing_poi_id,
        parent_poi_id=row.parent_poi_id,
        latitude=Decimal(str(row.latitude)) if row.latitude is not None else None,
        longitude=Decimal(str(row.longitude)) if row.longitude is not None else None,
        street_address=row.street_address,
        city=row.city,
        state_province=row.state_province,
        postal_code=row.postal_code,
        country=row.country,
        addresses=list(row.addresses or []),
        dates_visited=list(row.dates_visited or []),
        photo_directory=row.photo_directory,
        confidence_score=row.confidence_score,
        tags=list(row.tags or []),
        description=row.description,
        reason_to_visit=row.reason_to_visit,
        update_coordinates=row.update_coordinates,
        is_skipped=row.is_skipped,
        phase_state=IngestCandidatePhaseState(row.phase_state),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyIngestCandidateRepository(IIngestCandidateRepository):
    """PostgreSQL adapter for IngestCandidate staged entities."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an active session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create_batch(
        self,
        candidates: Sequence[IngestCandidate],
    ) -> Sequence[IngestCandidate]:
        """Persists a collection of candidate POI records for an ingest job.

        Args:
            candidates: Collection of IngestCandidate entities to persist.

        Returns:
            Collection of persisted IngestCandidate entities.
        """
        rows: list[IngestCandidateTable] = []
        for cand in candidates:
            geom = None
            if cand.latitude is not None and cand.longitude is not None:
                geom = ST_SetSRID(
                    ST_MakePoint(float(cand.longitude), float(cand.latitude)),
                    4326,
                )

            row = IngestCandidateTable(
                id=cand.id,
                user_id=cand.user_id,
                job_id=cand.job_id,
                row_index=cand.row_index,
                poi_name=cand.poi_name,
                recommended_disposition=cand.recommended_disposition.value,
                user_disposition=cand.user_disposition.value if cand.user_disposition else None,
                matched_existing_poi_id=cand.matched_existing_poi_id,
                parent_poi_id=cand.parent_poi_id,
                geom=geom,
                latitude=cand.latitude,
                longitude=cand.longitude,
                street_address=cand.street_address,
                city=cand.city,
                state_province=cand.state_province,
                postal_code=cand.postal_code,
                country=cand.country,
                addresses=cand.addresses,
                dates_visited=cand.dates_visited,
                photo_directory=cand.photo_directory,
                confidence_score=cand.confidence_score,
                tags=cand.tags,
                description=cand.description,
                reason_to_visit=cand.reason_to_visit,
                update_coordinates=cand.update_coordinates,
                is_skipped=cand.is_skipped,
                phase_state=cand.phase_state.value,
                created_at=cand.created_at,
                updated_at=cand.updated_at,
            )
            rows.append(row)

        self._session.add_all(rows)
        await self._session.flush()
        return [_row_to_entity(r) for r in rows]

    async def list_by_job(
        self,
        user_id: UUID,
        job_id: UUID,
        phase_state: IngestCandidatePhaseState | None = None,
    ) -> Sequence[IngestCandidate]:
        """Retrieves all candidates for an ingest job scoped to tenant user.

        Args:
            user_id: Tenant user UUID.
            job_id: Ingest job UUID.
            phase_state: Optional lifecycle state filter.

        Returns:
            Sequence of IngestCandidate entities.
        """
        stmt = (
            select(IngestCandidateTable)
            .where(
                IngestCandidateTable.user_id == user_id,
                IngestCandidateTable.job_id == job_id,
            )
            .order_by(IngestCandidateTable.row_index)
        )
        if phase_state is not None:
            stmt = stmt.where(IngestCandidateTable.phase_state == phase_state.value)

        res = await self._session.execute(stmt)
        return [_row_to_entity(row) for row in res.scalars()]

    async def get_candidate(
        self,
        candidate_id: UUID,
        user_id: UUID,
    ) -> IngestCandidate | None:
        """Retrieves a single candidate record by primary key and tenant.

        Args:
            candidate_id: Primary key UUID of candidate.
            user_id: Tenant user UUID.

        Returns:
            IngestCandidate entity or None if not found or tenant mismatch.
        """
        stmt = select(IngestCandidateTable).where(
            IngestCandidateTable.id == candidate_id,
            IngestCandidateTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def update_candidate(
        self,
        user_id: UUID,
        candidate: IngestCandidate,
    ) -> IngestCandidate:
        """Updates a candidate record enforcing tenant isolation.

        Args:
            user_id: Tenant user UUID.
            candidate: Updated IngestCandidate domain entity.

        Returns:
            Persisted updated IngestCandidate entity.
        """
        stmt = select(IngestCandidateTable).where(
            IngestCandidateTable.id == candidate.id,
            IngestCandidateTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one()

        row.poi_name = candidate.poi_name
        row.recommended_disposition = candidate.recommended_disposition.value
        row.user_disposition = (
            candidate.user_disposition.value if candidate.user_disposition else None
        )
        row.matched_existing_poi_id = candidate.matched_existing_poi_id
        row.parent_poi_id = candidate.parent_poi_id
        row.latitude = candidate.latitude
        row.longitude = candidate.longitude
        row.street_address = candidate.street_address
        row.city = candidate.city
        row.state_province = candidate.state_province
        row.postal_code = candidate.postal_code
        row.country = candidate.country
        row.addresses = candidate.addresses
        row.dates_visited = candidate.dates_visited
        row.photo_directory = candidate.photo_directory
        row.confidence_score = candidate.confidence_score
        row.tags = candidate.tags
        row.description = candidate.description
        row.reason_to_visit = candidate.reason_to_visit
        row.update_coordinates = candidate.update_coordinates
        row.is_skipped = candidate.is_skipped
        row.phase_state = candidate.phase_state.value
        row.updated_at = datetime.now(UTC)

        if candidate.latitude is not None and candidate.longitude is not None:
            row.geom = ST_SetSRID(
                ST_MakePoint(float(candidate.longitude), float(candidate.latitude)),
                4326,
            )
        else:
            row.geom = None

        await self._session.flush()
        return _row_to_entity(row)

    async def advance_to_phase2(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> int:
        """Transitions all active candidates for a job from Phase 1 to Phase 2.

        Args:
            user_id: Tenant user UUID.
            job_id: Ingest job UUID.

        Returns:
            Count of candidates transitioned.
        """
        stmt = (
            update(IngestCandidateTable)
            .where(
                IngestCandidateTable.user_id == user_id,
                IngestCandidateTable.job_id == job_id,
                IngestCandidateTable.phase_state == IngestCandidatePhaseState.PHASE_1_TRIAGE.value,
            )
            .values(
                phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED.value,
                updated_at=datetime.now(UTC),
            )
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount

    async def commit_job(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> Sequence[IngestCandidate]:
        """Marks all unskipped candidates for a job as committed.

        Args:
            user_id: Tenant user UUID.
            job_id: Ingest job UUID.

        Returns:
            Sequence of committed IngestCandidate entities.
        """
        stmt = (
            update(IngestCandidateTable)
            .where(
                IngestCandidateTable.user_id == user_id,
                IngestCandidateTable.job_id == job_id,
                IngestCandidateTable.is_skipped.is_(False),
            )
            .values(
                phase_state=IngestCandidatePhaseState.COMMITTED.value,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated records
        return await self.list_by_job(
            user_id=user_id,
            job_id=job_id,
            phase_state=IngestCandidatePhaseState.COMMITTED,
        )

    async def purge_by_job(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> int:
        """Deletes all staged candidate records for an ingest job.

        Args:
            user_id: Tenant user UUID.
            job_id: Ingest job UUID.

        Returns:
            Count of rows deleted.
        """
        stmt = delete(IngestCandidateTable).where(
            IngestCandidateTable.user_id == user_id,
            IngestCandidateTable.job_id == job_id,
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return res.rowcount

