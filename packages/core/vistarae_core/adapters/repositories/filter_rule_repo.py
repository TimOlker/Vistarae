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

"""SQLAlchemy 2.0 repository adapter for Filter Rules (T-009).

Implements IFilterRuleRepository:
- User-scoped filter rule CRUD operations
- Strict tenant isolation: WHERE user_id = :current_user_id on all operations
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import FilterRuleTable
from vistarae_core.domain.entities import FilterRuleEntity
from vistarae_core.ports.repositories import IFilterRuleRepository


def _row_to_entity(row: FilterRuleTable) -> FilterRuleEntity:
    """Maps FilterRuleTable ORM row to FilterRuleEntity domain model."""
    return FilterRuleEntity(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        query_tree=row.query_tree or {},
        table_config=row.table_config or {},
        pin_color_scheme=row.pin_color_scheme or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyFilterRuleRepository(IFilterRuleRepository):
    """PostgreSQL adapter for user-persisted filter rules."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes filter rule repository with database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def list_by_user(self, user_id: UUID) -> list[FilterRuleEntity]:
        """Lists all filter rules owned by tenant.

        Args:
            user_id: Tenant UUID.

        Returns:
            List of FilterRuleEntity instances ordered by name.
        """
        stmt = (
            select(FilterRuleTable)
            .where(FilterRuleTable.user_id == user_id)
            .order_by(FilterRuleTable.name.asc())
        )
        res = await self._session.execute(stmt)
        return [_row_to_entity(r) for r in res.scalars().all()]

    async def get_by_id(self, rule_id: UUID, user_id: UUID) -> FilterRuleEntity | None:
        """Retrieves a single filter rule by ID scoped to tenant.

        Args:
            rule_id: Rule UUID.
            user_id: Tenant UUID.

        Returns:
            FilterRuleEntity or None if not found.
        """
        stmt = select(FilterRuleTable).where(
            FilterRuleTable.id == rule_id,
            FilterRuleTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def get_by_name(self, name: str, user_id: UUID) -> FilterRuleEntity | None:
        """Retrieves a filter rule by name scoped to tenant.

        Args:
            name: Rule name string.
            user_id: Tenant UUID.

        Returns:
            FilterRuleEntity or None if not found.
        """
        stmt = select(FilterRuleTable).where(
            FilterRuleTable.name == name,
            FilterRuleTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        return _row_to_entity(row) if row else None

    async def create(self, rule: FilterRuleEntity) -> FilterRuleEntity:
        """Inserts a new filter rule record.

        Args:
            rule: FilterRuleEntity to persist.

        Returns:
            Persisted FilterRuleEntity with timestamps.
        """
        row = FilterRuleTable(
            id=rule.id,
            user_id=rule.user_id,
            name=rule.name,
            query_tree=rule.query_tree,
            table_config=rule.table_config,
            pin_color_scheme=rule.pin_color_scheme,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_entity(row)

    async def update(self, rule: FilterRuleEntity) -> FilterRuleEntity:
        """Updates/overwrites an existing filter rule record.

        Args:
            rule: FilterRuleEntity with updated properties.

        Returns:
            Updated FilterRuleEntity.
        """
        stmt = select(FilterRuleTable).where(
            FilterRuleTable.id == rule.id,
            FilterRuleTable.user_id == rule.user_id,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if not row:
            raise ValueError(f"FilterRule {rule.id} not found for user {rule.user_id}")

        row.name = rule.name
        row.query_tree = rule.query_tree
        row.table_config = rule.table_config
        row.pin_color_scheme = rule.pin_color_scheme
        row.updated_at = datetime.now(UTC)

        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_entity(row)

    async def delete(self, rule_id: UUID, user_id: UUID) -> bool:
        """Deletes a filter rule record scoped to tenant.

        Args:
            rule_id: Rule UUID.
            user_id: Tenant UUID.

        Returns:
            True if deleted, False if not found.
        """
        stmt = delete(FilterRuleTable).where(
            FilterRuleTable.id == rule_id,
            FilterRuleTable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        await self._session.flush()
        return (res.rowcount or 0) > 0
