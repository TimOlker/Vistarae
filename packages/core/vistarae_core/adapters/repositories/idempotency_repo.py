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

"""SQLAlchemy 2.0 idempotency repository (T-036).

Implements IIdempotencyRepository interface with atomic key insertion,
status transitions (PENDING, COMPLETED, FAILED), response caching, and 24h cleanup.
Enforces Constitution Principle 3: Explicit WHERE user_id predicates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import IdempotencyKeysTable
from vistarae_core.domain.entities import IdempotencyRecord
from vistarae_core.domain.value_objects import IdempotencyStatus


class SqlAlchemyIdempotencyRepository:
    """SQLAlchemy 2.0 implementation of IIdempotencyRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an active AsyncSession.

        Args:
            session: AsyncSession database handle.
        """
        self._session = session

    async def get_or_create(
        self,
        user_id: UUID,
        key: str,
    ) -> tuple[IdempotencyStatus, int | None, dict[str, Any] | None]:
        """Atomically retrieves or creates an idempotency record.

        - If existing and COMPLETED: returns (COMPLETED, code, payload).
        - If existing and PENDING: returns (PENDING, None, None).
        - If existing and FAILED: transitions to PENDING to allow retry, returns (PENDING, None, None).
        - If new: creates PENDING record, flushes, and returns (PENDING, None, None).

        Args:
            user_id: UUID of the requesting tenant.
            key: Client-provided idempotency key string.

        Returns:
            Tuple of (status, cached_response_code, cached_payload).
        """
        stmt = (
            select(IdempotencyKeysTable)
            .where(
                IdempotencyKeysTable.user_id == user_id,
                IdempotencyKeysTable.idempotency_key == key,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is not None:
            status = IdempotencyStatus(row.status)
            if status == IdempotencyStatus.COMPLETED:
                return status, row.response_code, row.response_payload
            if status == IdempotencyStatus.FAILED:
                # Reset failed record to PENDING to permit retry
                row.status = IdempotencyStatus.PENDING.value
                row.response_code = None
                row.response_payload = None
                await self._session.flush()
                return IdempotencyStatus.PENDING, None, None
            # PENDING
            return IdempotencyStatus.PENDING, None, None

        # Insert new PENDING key
        new_row = IdempotencyKeysTable(
            user_id=user_id,
            idempotency_key=key,
            status=IdempotencyStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )
        self._session.add(new_row)
        await self._session.flush()
        return IdempotencyStatus.PENDING, None, None

    async def complete(
        self,
        user_id: UUID,
        key: str,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        """Marks key as COMPLETED and stores cached response.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to finalize.
            status_code: HTTP status code of the successful response.
            payload: Serializable response body to cache.
        """
        stmt = (
            update(IdempotencyKeysTable)
            .where(
                IdempotencyKeysTable.user_id == user_id,
                IdempotencyKeysTable.idempotency_key == key,
            )
            .values(
                status=IdempotencyStatus.COMPLETED.value,
                response_code=status_code,
                response_payload=payload,
            )
        )
        await self._session.execute(stmt)

    async def fail(self, user_id: UUID, key: str) -> None:
        """Marks a key FAILED so subsequent retries can proceed.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to mark failed.
        """
        stmt = (
            update(IdempotencyKeysTable)
            .where(
                IdempotencyKeysTable.user_id == user_id,
                IdempotencyKeysTable.idempotency_key == key,
            )
            .values(status=IdempotencyStatus.FAILED.value)
        )
        await self._session.execute(stmt)

    async def cleanup_older_than(self, hours: int = 24) -> int:
        """Purges idempotency records older than the given age threshold.

        Args:
            hours: Age threshold in hours.

        Returns:
            Count of purged records.
        """
        threshold = datetime.now(UTC) - timedelta(hours=hours)
        stmt = delete(IdempotencyKeysTable).where(IdempotencyKeysTable.created_at < threshold)
        result = await self._session.execute(stmt)
        return int(result.rowcount) if result.rowcount is not None else 0

    async def get_record(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        """Retrieves a single idempotency record by composite key.

        Args:
            user_id: UUID of the tenant.
            key: Client idempotency key string.

        Returns:
            IdempotencyRecord or None if not found.
        """
        stmt = select(IdempotencyKeysTable).where(
            IdempotencyKeysTable.user_id == user_id,
            IdempotencyKeysTable.idempotency_key == key,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return IdempotencyRecord(
            id=row.id,
            user_id=row.user_id,
            idempotency_key=row.idempotency_key,
            status=IdempotencyStatus(row.status),
            response_code=row.response_code,
            response_payload=row.response_payload,
            created_at=row.created_at,
        )
