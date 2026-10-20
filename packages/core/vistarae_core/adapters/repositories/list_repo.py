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

"""SQLAlchemy 2.0 repository adapter for Curated Lists (T-031).

Implements IListRepository:
- User-scoped list CRUD operations
- Public shared list access (is_public = TRUE) without tenant credentials
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import ListTable
from vistarae_core.domain.entities import ListEntity
from vistarae_core.ports.repositories import IListRepository


def _row_to_list(row: ListTable) -> ListEntity:
    """Maps ListTable ORM row to ListEntity domain model."""
    return ListEntity(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        description=row.description,
        is_public=row.is_public,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyListRepository(IListRepository):
    """PostgreSQL adapter for curated POI lists."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes list repository with database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create(self, list_entity: ListEntity) -> ListEntity:
        """Creates a new list."""
        row = ListTable(
            id=list_entity.id,
            user_id=list_entity.user_id,
            title=list_entity.title,
            description=list_entity.description,
            is_public=list_entity.is_public,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_list(row)

    async def get_by_id(self, list_id: UUID, user_id: UUID | None = None) -> ListEntity | None:
        """Retrieves a list by ID. If user_id provided, checks ownership or is_public."""
        stmt = select(ListTable).where(ListTable.id == list_id)
        if user_id is not None:
            stmt = stmt.where(or_(ListTable.user_id == user_id, ListTable.is_public.is_(True)))
        else:
            stmt = stmt.where(ListTable.is_public.is_(True))

        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_list(row)

    async def list_by_user(self, user_id: UUID) -> list[ListEntity]:
        """Lists all lists owned by the user."""
        stmt = (
            select(ListTable)
            .where(ListTable.user_id == user_id)
            .order_by(ListTable.created_at.desc())
        )
        res = await self._session.execute(stmt)
        return [_row_to_list(r) for r in res.scalars().all()]

    async def update(self, list_entity: ListEntity) -> ListEntity:
        """Updates a list owned by the user."""
        stmt = select(ListTable).where(
            ListTable.id == list_entity.id,
            ListTable.user_id == list_entity.user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            raise ValueError(f"List {list_entity.id} not found for user")

        row.title = list_entity.title
        row.description = list_entity.description
        row.is_public = list_entity.is_public
        await self._session.flush()
        return _row_to_list(row)

    async def delete(self, list_id: UUID, user_id: UUID) -> bool:
        """Deletes a list owned by the user."""
        stmt = delete(ListTable).where(
            ListTable.id == list_id,
            ListTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0
