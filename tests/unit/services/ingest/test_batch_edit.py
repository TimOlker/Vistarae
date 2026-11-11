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

"""Unit tests for batch editing candidates including adding and removing tags."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import IngestCandidateTable
from vistarae_core.adapters.repositories.ingest_candidate_repo import (
    SqlAlchemyIngestCandidateRepository,
)
from vistarae_core.schemas.ingest_staging import BatchEditCandidatesRequest

from services.ingest.services.staging_service import StagingService


@pytest.mark.asyncio
async def test_batch_edit_add_tag_appends_and_skips_duplicates():
    """Batch edit add_tag appends tag if missing, and skips candidate if tag already exists."""
    user_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    row1 = IngestCandidateTable(
        id=c1_id,
        user_id=user_id,
        tags=["Historic"],
    )
    row2 = IngestCandidateTable(
        id=c2_id,
        user_id=user_id,
        tags=["Historic", "World Wonder"],
    )

    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = [row1, row2]
    mock_session.execute = AsyncMock(return_value=exec_result)
    mock_session.flush = AsyncMock()

    repo = SqlAlchemyIngestCandidateRepository(mock_session)
    count = await repo.batch_edit(
        user_id=user_id,
        candidate_ids=[c1_id, c2_id],
        add_tag="World Wonder",
    )

    assert count == 2
    assert row1.tags == ["Historic", "World Wonder"]
    assert row2.tags == ["Historic", "World Wonder"]  # Not duplicated


@pytest.mark.asyncio
async def test_batch_edit_remove_tag_removes_and_skips_missing():
    """Batch edit remove_tag removes tag if present, and skips candidate if tag does not exist."""
    user_id = uuid.uuid4()
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    row1 = IngestCandidateTable(
        id=c1_id,
        user_id=user_id,
        tags=["Historic", "DraftTag"],
    )
    row2 = IngestCandidateTable(
        id=c2_id,
        user_id=user_id,
        tags=["Historic"],
    )

    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalars.return_value = [row1, row2]
    mock_session.execute = AsyncMock(return_value=exec_result)
    mock_session.flush = AsyncMock()

    repo = SqlAlchemyIngestCandidateRepository(mock_session)
    count = await repo.batch_edit(
        user_id=user_id,
        candidate_ids=[c1_id, c2_id],
        remove_tag="DraftTag",
    )

    assert count == 2
    assert row1.tags == ["Historic"]
    assert row2.tags == ["Historic"]  # Untouched


@pytest.mark.asyncio
async def test_staging_service_batch_edit_forwards_tags():
    """StagingService forwards add_tag and remove_tag to candidate repository."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    c_id = uuid.uuid4()

    mock_candidate_repo = AsyncMock()
    mock_candidate_repo.batch_edit.return_value = 1

    service = StagingService(
        candidate_repo=mock_candidate_repo,
    )

    req = BatchEditCandidatesRequest(
        candidate_ids=[c_id],
        add_tag="Scenic",
        remove_tag="OldTag",
    )

    result = await service.batch_edit_candidates(user_id, job_id, req)
    assert result == 1
    mock_candidate_repo.batch_edit.assert_awaited_once_with(
        user_id=user_id,
        candidate_ids=[c_id],
        country=None,
        state_province=None,
        city=None,
        date_visited=None,
        add_tag="Scenic",
        remove_tag="OldTag",
    )
