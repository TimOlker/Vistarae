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

"""Unit tests for SqlAlchemyUserPromptRepository (REQ-CTX-001, REQ-CTX-014, SC-007)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.adapters.db.tables import UserPromptTable
from vistarae_core.adapters.repositories.user_prompt_repo import SqlAlchemyUserPromptRepository
from vistarae_core.domain.value_objects import PromptType


@pytest.fixture
def mock_session() -> AsyncMock:
    """Fixture providing a mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def repo(mock_session: AsyncMock) -> SqlAlchemyUserPromptRepository:
    """Fixture providing SqlAlchemyUserPromptRepository with mock session."""
    return SqlAlchemyUserPromptRepository(mock_session)


@pytest.mark.asyncio
async def test_list_by_user_returns_entities(
    repo: SqlAlchemyUserPromptRepository, mock_session: AsyncMock
) -> None:
    """Verify list_by_user filters by tenant and converts ORM rows to domain entities."""
    user_id = uuid4()
    now = datetime.now(UTC)

    row1 = UserPromptTable(
        id=uuid4(),
        user_id=user_id,
        prompt_type="description",
        prompt_text="Focus on historical castles.",
        created_at=now,
        updated_at=now,
    )
    row2 = UserPromptTable(
        id=uuid4(),
        user_id=user_id,
        prompt_type="reason_to_visit",
        prompt_text="Experience medieval heritage.",
        created_at=now,
        updated_at=now,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [row1, row2]
    mock_session.execute.return_value = mock_result

    prompts = await repo.list_by_user(user_id)

    assert len(prompts) == 2
    assert prompts[0].prompt_type == PromptType.DESCRIPTION
    assert prompts[0].prompt_text == "Focus on historical castles."
    assert prompts[1].prompt_type == PromptType.REASON_TO_VISIT
    assert prompts[1].prompt_text == "Experience medieval heritage."
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_prompts_executes_inserts_and_flushes(
    repo: SqlAlchemyUserPromptRepository, mock_session: AsyncMock
) -> None:
    """Verify upsert_prompts executes on-conflict insert and flushes session."""
    user_id = uuid4()
    directives = {
        PromptType.DESCRIPTION: "Highlight scenic beauty.",
        PromptType.TIME_SPENT: "Pace for 2 hours.",
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    await repo.upsert_prompts(user_id, directives)

    # 2 inserts + 1 re-fetch list_by_user
    assert mock_session.execute.call_count == 3
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_by_user_executes_delete_statement(
    repo: SqlAlchemyUserPromptRepository, mock_session: AsyncMock
) -> None:
    """Verify delete_by_user executes delete filtered by tenant user_id."""
    user_id = uuid4()

    await repo.delete_by_user(user_id)

    assert mock_session.execute.call_count == 1
    mock_session.flush.assert_called_once()
