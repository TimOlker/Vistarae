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

"""Unit tests for POI repository created_at timestamp auditing and date range filtering (T-034)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.domain.entities import POI
from vistarae_core.domain.value_objects import WGS84Point


def test_poi_domain_entity_defaults_created_at():
    """Asserts that new POI entity defaults created_at to UTC timestamp (REQ-AUD-001)."""
    poi = POI(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Scenic Peak",
        geom=WGS84Point(lat=35.0, lon=139.0),
    )
    assert poi.created_at is not None
    now = datetime.now(UTC)
    assert abs((now - poi.created_at).total_seconds()) < 5.0


@pytest.mark.asyncio
async def test_poi_repository_list_pois_filters_by_created_after_and_before():
    """Asserts that list_pois query applies created_after and created_before filter clauses (REQ-AUD-002)."""
    user_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()

    # Mock count and list responses
    count_res = MagicMock()
    count_res.scalar.return_value = 0
    list_res = MagicMock()
    list_res.scalars.return_value.all.return_value = []
    mock_session.execute.side_effect = [count_res, list_res]

    repo = SqlAlchemyPOIRepository(mock_session)

    created_after = datetime.now(UTC) - timedelta(days=7)
    created_before = datetime.now(UTC)

    await repo.list_pois(
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
    )

    # Inspect the compiled SQL statements executed
    assert mock_session.execute.call_count == 2
    executed_count_stmt = str(mock_session.execute.call_args_list[0][0][0])
    executed_list_stmt = str(mock_session.execute.call_args_list[1][0][0])

    assert "pois.created_at >=" in executed_count_stmt
    assert "pois.created_at <=" in executed_count_stmt
    assert "pois.created_at >=" in executed_list_stmt
    assert "pois.created_at <=" in executed_list_stmt
