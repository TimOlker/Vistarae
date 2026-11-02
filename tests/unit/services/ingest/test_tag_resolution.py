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

"""Unit tests for early tag resolution and pre-flight validation (T-023)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import TagEntity
from vistarae_core.domain.enums import TagResolutionAction
from vistarae_core.schemas.poi_exchange import POIExchangeRecord

from services.ingest.services.staging_service import StagingService


@pytest.fixture
def mock_tag_repo():
    repo = MagicMock()
    repo.list_by_user = AsyncMock(
        return_value=[
            TagEntity(
                id=uuid4(),
                user_id=uuid4(),
                name="Historical",
                slug="historical",
                aliases=["historic", "history"],
            ),
            TagEntity(
                id=uuid4(),
                user_id=uuid4(),
                name="Food",
                slug="food",
                aliases=["dining"],
            ),
        ]
    )
    repo.create = AsyncMock(
        side_effect=lambda tag: TagEntity(
            id=uuid4(),
            user_id=tag.user_id,
            name=tag.name,
            slug=tag.slug,
        )
    )
    return repo


@pytest.fixture
def staging_service(mock_tag_repo):
    service = StagingService(
        candidate_repo=MagicMock(),
        poi_repo=MagicMock(),
        geocoding_service=MagicMock(),
        duplicate_service=MagicMock(),
        orchestrator=MagicMock(),
        ingest_repo=MagicMock(),
        exclusion_zone_repo=MagicMock(),
        tag_repo=mock_tag_repo,
    )
    return service


@pytest.mark.asyncio
async def test_get_unapproved_tags_identifies_unvetted_tags(staging_service, mock_tag_repo):
    user_id = uuid4()
    records = [
        POIExchangeRecord(poi_name="Castle", tags=["Historical", "Ramen"]),
        POIExchangeRecord(poi_name="Bathhouse", tags=["onsen", "HISTORIC"]),
    ]

    unapproved = await staging_service.get_unapproved_tags(user_id, records)

    # "Historical" and "HISTORIC" match existing name/alias; "Ramen" and "onsen" are unvetted
    assert "Ramen" in unapproved or "ramen" in unapproved
    assert "onsen" in unapproved


@pytest.mark.asyncio
async def test_resolve_tags_approve_and_add(staging_service, mock_tag_repo):
    user_id = uuid4()
    records = [
        POIExchangeRecord(poi_name="Castle", tags=["Historical", "Ramen"]),
        POIExchangeRecord(poi_name="Bathhouse", tags=["Onsen"]),
    ]

    resolved_records = await staging_service.resolve_unapproved_tags(
        user_id=user_id,
        records=records,
        action=TagResolutionAction.APPROVE_AND_ADD,
        unapproved_tags=["Ramen", "Onsen"],
    )

    # All tags should remain preserved on records
    assert resolved_records[0].tags == ["Historical", "Ramen"]
    assert resolved_records[1].tags == ["Onsen"]
    # Tag repo create should have been called for Ramen and Onsen
    assert mock_tag_repo.create.call_count == 2


@pytest.mark.asyncio
async def test_resolve_tags_strip_unapproved(staging_service, mock_tag_repo):
    user_id = uuid4()
    records = [
        POIExchangeRecord(poi_name="Castle", tags=["Historical", "Ramen"]),
        POIExchangeRecord(poi_name="Bathhouse", tags=["Onsen"]),
    ]

    resolved_records = await staging_service.resolve_unapproved_tags(
        user_id=user_id,
        records=records,
        action=TagResolutionAction.STRIP_UNAPPROVED,
        unapproved_tags=["Ramen", "Onsen"],
    )

    # Only approved tag should remain
    assert resolved_records[0].tags == ["Historical"]
    assert resolved_records[1].tags == []
    # Tag repo create should NOT have been called
    assert mock_tag_repo.create.call_count == 0
