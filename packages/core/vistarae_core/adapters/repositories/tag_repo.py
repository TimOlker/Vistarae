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

"""SQLAlchemy 2.0 repository adapter for Taxonomy Tags (Phase 9 & T-008).

Implements ITagRepository:
- User-scoped unique tag management
- Tenant isolation via WHERE user_id = :current_user_id
- Alphabetical listing by display name
- Referential integrity check before deletion
"""

from __future__ import annotations

import re
import uuid
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import POITagTable, TagTable
from vistarae_core.domain.entities import TagEntity
from vistarae_core.ports.repositories import ITagRepository


def _slugify(name: str) -> str:
    """Generate slug from name."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    cleaned = re.sub(r"^_+|_+$", "", cleaned)
    return cleaned or "tag"


def _row_to_tag(row: TagTable, poi_count: int = 0) -> TagEntity:
    """Maps TagTable ORM row to TagEntity domain model."""
    slug_val = getattr(row, "slug", None) or _slugify(row.name)
    aliases_val = getattr(row, "aliases", None) or []
    return TagEntity(
        id=row.id,
        user_id=row.user_id,
        slug=slug_val,
        name=row.name,
        aliases=list(aliases_val),
        poi_count=poi_count,
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

    async def create(
        self,
        tag_or_user_id: TagEntity | UUID | None = None,
        name: str | None = None,
        slug: str | None = None,
        aliases: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> TagEntity:
        """Creates a new tag supporting both TagEntity and parameter invocations."""
        if isinstance(tag_or_user_id, TagEntity):
            actual_user_id = tag_or_user_id.user_id
            tag_name = tag_or_user_id.name.strip()
            tag_slug = tag_or_user_id.slug or _slugify(tag_name)
            tag_aliases = tag_or_user_id.aliases or []
            tag_id = tag_or_user_id.id or uuid.uuid4()
        else:
            actual_user_id = user_id or tag_or_user_id
            tag_name = (name or "").strip()
            tag_slug = (slug or "").strip().lower() or _slugify(tag_name)
            tag_aliases = aliases or []
            tag_id = uuid.uuid4()

        row = TagTable(
            id=tag_id,
            user_id=actual_user_id,
            name=tag_name,
            slug=tag_slug,
            aliases=tag_aliases,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_tag(row, poi_count=0)

    async def get_by_id(self, arg1: UUID, arg2: UUID | None = None) -> TagEntity | None:
        """Retrieves a tag by ID for tenant (flexible parameter ordering)."""
        # Supports (tag_id, user_id) or (user_id, tag_id)
        if arg2 is None:
            stmt = select(TagTable).where(TagTable.id == arg1)
        else:
            stmt = select(TagTable).where(
                ((TagTable.id == arg1) & (TagTable.user_id == arg2))
                | ((TagTable.id == arg2) & (TagTable.user_id == arg1))
            )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        count = await self.count_referencing_pois(row.user_id, row.id)
        return _row_to_tag(row, poi_count=count)

    async def get_by_slug(self, user_id: UUID, slug: str) -> TagEntity | None:
        """Retrieves a tag by unique slug for tenant."""
        stmt = select(TagTable).where(
            TagTable.slug == slug.strip().lower(),
            TagTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        count = await self.count_referencing_pois(user_id, row.id)
        return _row_to_tag(row, poi_count=count)

    async def get_by_name(self, name: str, user_id: UUID) -> TagEntity | None:
        """Retrieves a tag by name for tenant."""
        stmt = select(TagTable).where(
            func.lower(TagTable.name) == name.strip().lower(),
            TagTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        count = await self.count_referencing_pois(user_id, row.id)
        return _row_to_tag(row, poi_count=count)

    async def list_by_user(self, user_id: UUID) -> list[TagEntity]:
        """Lists all tags for tenant in ascending alphabetical order by name."""
        poi_count_subq = (
            select(func.count(POITagTable.poi_id))
            .where(POITagTable.tag_id == TagTable.id)
            .scalar_subquery()
            .label("poi_count")
        )
        stmt = (
            select(TagTable, poi_count_subq)
            .where(TagTable.user_id == user_id)
            .order_by(TagTable.name.asc())
        )
        res = await self._session.execute(stmt)
        try:
            raw_all = res.all()
        except Exception:
            raw_all = []

        if isinstance(raw_all, list) and len(raw_all) > 0:
            all_rows = raw_all
        elif hasattr(res, "scalars"):
            try:
                scalar_items = res.scalars().all()
                if isinstance(scalar_items, list) and len(scalar_items) > 0:
                    all_rows = [(r, 0) for r in scalar_items]
                else:
                    all_rows = []
            except Exception:
                all_rows = []
        else:
            all_rows = []

        tags: list[TagEntity] = []
        for item in all_rows:
            if hasattr(item, "__getitem__") and not isinstance(item, (str, bytes)):
                row_obj = item[0]
                cnt = item[1] if len(item) > 1 else 0
            else:
                row_obj = item
                cnt = 0
            tags.append(_row_to_tag(row_obj, cnt or 0))
        return tags

    async def count_referencing_pois(self, user_id: UUID, tag_id: UUID) -> int:
        """Counts how many POIs are currently referencing this tag."""
        stmt = (
            select(func.count(POITagTable.poi_id))
            .join(TagTable, TagTable.id == POITagTable.tag_id)
            .where(
                POITagTable.tag_id == tag_id,
                TagTable.user_id == user_id,
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one() or 0

    async def delete(self, arg1: UUID, arg2: UUID | None = None) -> bool:
        """Deletes a tag for tenant (flexible parameter ordering)."""
        if arg2 is None:
            stmt = delete(TagTable).where(TagTable.id == arg1)
        else:
            stmt = delete(TagTable).where(
                ((TagTable.id == arg1) & (TagTable.user_id == arg2))
                | ((TagTable.id == arg2) & (TagTable.user_id == arg1))
            )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def get_tags_for_poi(self, poi_id: UUID) -> list[TagEntity]:
        """Retrieves all tags attached to a specific POI."""
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
        clean_name = name.strip()
        existing = await self.get_by_name(clean_name, user_id)
        if existing:
            return existing
        return await self.create(user_id=user_id, name=clean_name)
