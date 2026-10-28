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

"""SQLAlchemy 2.0 repository adapter for User Prompts (Phase 11).

Implements IUserPromptRepository:
- User-scoped personalized prompt directive persistence
- Strict tenant isolation: WHERE user_id = :current_user_id on all operations
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import UserPromptTable
from vistarae_core.domain.entities import UserPrompt
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.ports.repositories import IUserPromptRepository


def _row_to_entity(row: UserPromptTable) -> UserPrompt:
    """Maps UserPromptTable ORM row to UserPrompt domain entity."""
    return UserPrompt(
        id=row.id,
        user_id=row.user_id,
        prompt_type=PromptType(row.prompt_type),
        prompt_text=row.prompt_text,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyUserPromptRepository(IUserPromptRepository):
    """PostgreSQL adapter for tenant personalized prompt directives."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes user prompt repository with active database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def list_by_user(self, user_id: UUID) -> Sequence[UserPrompt]:
        """Retrieves all active prompt directives for a tenant.

        Args:
            user_id: Owning tenant UUID.

        Returns:
            Sequence of UserPrompt entities ordered by prompt_type.
        """
        stmt = (
            select(UserPromptTable)
            .where(UserPromptTable.user_id == user_id)
            .order_by(UserPromptTable.prompt_type.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_entity(r) for r in rows]

    async def upsert_prompts(
        self,
        user_id: UUID,
        prompts: dict[PromptType, str],
    ) -> Sequence[UserPrompt]:
        """Atomically replaces or updates prompt directives for a tenant.

        Args:
            user_id: Owning tenant UUID.
            prompts: Mapping of prompt types to directive text.

        Returns:
            Sequence of upserted UserPrompt entities.
        """
        now = datetime.now(UTC)
        for p_type, p_text in prompts.items():
            type_str = p_type.value if isinstance(p_type, PromptType) else str(p_type)
            stmt = pg_insert(UserPromptTable).values(
                id=uuid4(),
                user_id=user_id,
                prompt_type=type_str,
                prompt_text=p_text,
                created_at=now,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_user_prompts_user_type",
                set_={
                    "prompt_text": stmt.excluded.prompt_text,
                    "updated_at": now,
                },
            )
            await self._session.execute(stmt)

        await self._session.flush()
        return await self.list_by_user(user_id)

    async def delete_by_user(self, user_id: UUID) -> None:
        """Deletes all custom prompt directives for a tenant.

        Args:
            user_id: Owning tenant UUID.
        """
        stmt = delete(UserPromptTable).where(UserPromptTable.user_id == user_id)
        await self._session.execute(stmt)
        await self._session.flush()
