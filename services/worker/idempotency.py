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

"""Record-level idempotency helper for SQS batch ingest worker (T-024).

Computes deterministic SHA-256 idempotency key:
    sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}".encode()).hexdigest()
and performs atomic INSERT ... ON CONFLICT (user_id, idempotency_key) DO NOTHING
per REQ-WORKER-002 and REQ-WORKER-003.
"""

from __future__ import annotations

import hashlib
import uuid
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.tables import IdempotencyKeysTable
from vistarae_core.domain.value_objects import IdempotencyStatus


def compute_synthetic_idempotency_key(
    user_id: UUID | str,
    job_id: UUID | str,
    absolute_row_number: int,
) -> str:
    """Computes a deterministic 64-character SHA-256 synthetic idempotency key.

    Args:
        user_id: Tenant user UUID.
        job_id: Ingest job UUID.
        absolute_row_number: 1-based spreadsheet row position.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    raw_str = f"{user_id}:{job_id}:{absolute_row_number}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


async def claim_row_idempotency(
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    absolute_row_number: int,
) -> bool:
    """Attempts to claim row execution in the database via atomic ON CONFLICT DO NOTHING.

    Args:
        session: Active SQLAlchemy AsyncSession.
        user_id: Tenant user UUID.
        job_id: Ingest job UUID.
        absolute_row_number: 1-based spreadsheet row position.

    Returns:
        True if the row was successfully claimed (first time seen),
        False if the row was previously processed (duplicate detected, skip).
    """
    key = compute_synthetic_idempotency_key(user_id, job_id, absolute_row_number)

    stmt = (
        insert(IdempotencyKeysTable)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            idempotency_key=key,
            status=IdempotencyStatus.COMPLETED.value,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "idempotency_key"]
        )
        .returning(IdempotencyKeysTable.id)
    )

    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    await session.flush()
    return inserted_id is not None
