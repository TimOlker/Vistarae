# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""SQLAlchemy 2.0 repository adapter for Taxonomy Tags (T-032).

Implements ITagRepository:
- User-scoped unique tag management
- Tenant isolation
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import TagTable
from vistarae_core.domain.entities import TagEntity
from vistarae_core.ports.repositories import ITagRepository


def _row_to_tag(row: TagTable) -> TagEntity:
    """Maps TagTable ORM row to TagEntity domain model."""
    return TagEntity(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        created_at=row.created_at,
    )


class SqlAlchemyTagRepository(ITagRepository):
    """PostgreSQL adapter for user taxonomy tags."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes tag repository with database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create(self, tag: TagEntity) -> TagEntity:
        """Creates a new tag."""
        row = TagTable(
            id=tag.id,
            user_id=tag.user_id,
            name=tag.name.strip().lower(),
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_tag(row)

    async def get_by_id(self, tag_id: UUID, user_id: UUID) -> TagEntity | None:
        """Retrieves a tag by ID for tenant."""
        stmt = select(TagTable).where(
            TagTable.id == tag_id,
            TagTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_tag(row)

    async def get_by_name(self, name: str, user_id: UUID) -> TagEntity | None:
        """Retrieves a tag by name for tenant."""
        stmt = select(TagTable).where(
            TagTable.name == name.strip().lower(),
            TagTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_tag(row)

    async def list_by_user(self, user_id: UUID) -> list[TagEntity]:
        """Lists all tags for tenant."""
        stmt = select(TagTable).where(TagTable.user_id == user_id).order_by(TagTable.name.asc())
        res = await self._session.execute(stmt)
        return [_row_to_tag(r) for r in res.scalars().all()]

    async def delete(self, tag_id: UUID, user_id: UUID) -> bool:
        """Deletes a tag."""
        stmt = delete(TagTable).where(
            TagTable.id == tag_id,
            TagTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def get_tags_for_poi(self, poi_id: UUID) -> list[TagEntity]:
        """Retrieves all tags attached to a specific POI."""
        from vistarae_core.adapters.db.tables import POITagTable

        stmt = (
            select(TagTable)
            .join(POITagTable, POITagTable.tag_id == TagTable.id)
            .where(POITagTable.poi_id == poi_id)
            .order_by(TagTable.name.asc())
        )
        res = await self._session.execute(stmt)
        return [_row_to_tag(r) for r in res.scalars().all()]

    async def get_tags_for_pois(self, poi_ids: list[UUID]) -> dict[UUID, list[TagEntity]]:
        """Batch retrieves tags for multiple POIs."""
        if not poi_ids:
            return {}
        from vistarae_core.adapters.db.tables import POITagTable

        stmt = (
            select(POITagTable.poi_id, TagTable)
            .join(TagTable, POITagTable.tag_id == TagTable.id)
            .where(POITagTable.poi_id.in_(poi_ids))
            .order_by(TagTable.name.asc())
        )
        res = await self._session.execute(stmt)
        mapping: dict[UUID, list[TagEntity]] = {pid: [] for pid in poi_ids}
        for poi_id, tag_row in res.all():
            mapping[poi_id].append(_row_to_tag(tag_row))
        return mapping

    async def get_or_create(self, user_id: UUID, name: str) -> TagEntity:
        """Retrieves an existing tag or creates a new one."""
        from uuid import uuid4

        clean_name = name.strip().lower()
        existing = await self.get_by_name(clean_name, user_id)
        if existing:
            return existing
        new_tag = TagEntity(id=uuid4(), user_id=user_id, name=clean_name)
        return await self.create(new_tag)
