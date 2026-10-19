# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for SqlAlchemyListRepository and SqlAlchemyTagRepository (T-031, T-032)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.adapters.db.tables import ListTable, TagTable
from vistarae_core.adapters.repositories.list_repo import SqlAlchemyListRepository
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.domain.entities import ListEntity, TagEntity


class TestSqlAlchemyListRepository:
    """Tests for SqlAlchemyListRepository adapter."""

    @pytest.mark.asyncio
    async def test_create_list(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyListRepository(session)
        u_id = uuid4()
        entity = ListEntity(
            id=uuid4(),
            user_id=u_id,
            title="My List",
            description="Desc",
            is_public=False,
        )
        created = await repo.create(entity)
        assert created.title == "My List"
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_get_by_id_owner(self) -> None:
        session = AsyncMock()
        l_id = uuid4()
        u_id = uuid4()
        row = MagicMock(spec=ListTable)
        row.id = l_id
        row.user_id = u_id
        row.title = "Found List"
        row.description = None
        row.is_public = False
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        res = await repo.get_by_id(l_id, user_id=u_id)
        assert res is not None
        assert res.title == "Found List"

    @pytest.mark.asyncio
    async def test_get_by_id_none(self) -> None:
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        res = await repo.get_by_id(uuid4(), user_id=uuid4())
        assert res is None

    @pytest.mark.asyncio
    async def test_list_by_user(self) -> None:
        session = AsyncMock()
        row = MagicMock(spec=ListTable)
        row.id = uuid4()
        row.user_id = uuid4()
        row.title = "User List"
        row.description = None
        row.is_public = False
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [row]
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        lists = await repo.list_by_user(row.user_id)
        assert len(lists) == 1

    @pytest.mark.asyncio
    async def test_update_list(self) -> None:
        session = AsyncMock()
        row = MagicMock(spec=ListTable)
        row.id = uuid4()
        row.user_id = uuid4()
        row.title = "Old Title"
        row.description = None
        row.is_public = False
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        updated_entity = ListEntity(
            id=row.id,
            user_id=row.user_id,
            title="New Title",
            description="New Desc",
            is_public=True,
        )
        res = await repo.update(updated_entity)
        assert res.title == "New Title"
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_update_list_not_found_raises(self) -> None:
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        entity = ListEntity(id=uuid4(), user_id=uuid4(), title="Lost")
        with pytest.raises(ValueError, match="not found"):
            await repo.update(entity)

    @pytest.mark.asyncio
    async def test_delete_list(self) -> None:
        session = AsyncMock()
        mock_res = MagicMock()
        mock_res.rowcount = 1
        session.execute.return_value = mock_res

        repo = SqlAlchemyListRepository(session)
        deleted = await repo.delete(uuid4(), uuid4())
        assert deleted is True


class TestSqlAlchemyTagRepository:
    """Tests for SqlAlchemyTagRepository adapter."""

    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self) -> None:
        session = AsyncMock()
        t_id = uuid4()
        u_id = uuid4()
        row = MagicMock(spec=TagTable)
        row.id = t_id
        row.user_id = u_id
        row.name = "hiking"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        created = await repo.create(TagEntity(id=t_id, user_id=u_id, name="hiking"))
        assert created.name == "hiking"

        fetched = await repo.get_by_id(t_id, u_id)
        assert fetched is not None
        assert fetched.name == "hiking"

    @pytest.mark.asyncio
    async def test_get_by_name(self) -> None:
        session = AsyncMock()
        t_id = uuid4()
        u_id = uuid4()
        row = MagicMock(spec=TagTable)
        row.id = t_id
        row.user_id = u_id
        row.name = "camping"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        tag = await repo.get_by_name("camping", u_id)
        assert tag is not None
        assert tag.name == "camping"

    @pytest.mark.asyncio
    async def test_list_by_user_and_delete(self) -> None:
        session = AsyncMock()
        row = MagicMock(spec=TagTable)
        row.id = uuid4()
        row.user_id = uuid4()
        row.name = "scenic"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [row]
        mock_res.rowcount = 1
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        tags = await repo.list_by_user(row.user_id)
        assert len(tags) == 1

        deleted = await repo.delete(row.id, row.user_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_get_tags_for_poi(self) -> None:
        session = AsyncMock()
        row = MagicMock(spec=TagTable)
        row.id = uuid4()
        row.user_id = uuid4()
        row.name = "waterfall"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [row]
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        tags = await repo.get_tags_for_poi(uuid4())
        assert len(tags) == 1
        assert tags[0].name == "waterfall"

    @pytest.mark.asyncio
    async def test_get_tags_for_pois_batch(self) -> None:
        session = AsyncMock()
        p_id = uuid4()
        row = MagicMock(spec=TagTable)
        row.id = uuid4()
        row.user_id = uuid4()
        row.name = "mountain"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.all.return_value = [(p_id, row)]
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        empty = await repo.get_tags_for_pois([])
        assert empty == {}

        mapping = await repo.get_tags_for_pois([p_id])
        assert p_id in mapping
        assert len(mapping[p_id]) == 1

    @pytest.mark.asyncio
    async def test_get_or_create(self) -> None:
        session = AsyncMock()
        u_id = uuid4()
        row = MagicMock(spec=TagTable)
        row.id = uuid4()
        row.user_id = u_id
        row.name = "existing"
        row.created_at = datetime.now(UTC)

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = row
        session.execute.return_value = mock_res

        repo = SqlAlchemyTagRepository(session)
        existing = await repo.get_or_create(u_id, "existing")
        assert existing.name == "existing"

        # Test brand new creation path
        mock_res.scalar_one_or_none.return_value = None
        new_tag = await repo.get_or_create(u_id, "brand-new")
        assert new_tag.name == "brand-new"
