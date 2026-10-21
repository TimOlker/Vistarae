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

"""Unit tests for POIFunction dependency injection providers."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.itinerary_repo import IItineraryRepository

from services.poi.dependencies import (
    get_embedding_port,
    get_geocache_repo,
    get_geocoding_port,
    get_itinerary_repo,
    get_list_repo,
    get_planner_service,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.services.planner import PlannerService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def test_get_poi_repo(mock_session: AsyncMock) -> None:
    repo = get_poi_repo(mock_session)
    assert repo is not None


def test_get_list_repo(mock_session: AsyncMock) -> None:
    repo = get_list_repo(mock_session)
    assert repo is not None


def test_get_tag_repo(mock_session: AsyncMock) -> None:
    repo = get_tag_repo(mock_session)
    assert repo is not None


def test_get_geocache_repo(mock_session: AsyncMock) -> None:
    repo = get_geocache_repo(mock_session)
    assert repo is not None


def test_get_itinerary_repo(mock_session: AsyncMock) -> None:
    repo = get_itinerary_repo(mock_session)
    assert repo is not None


def test_get_geocoding_port_mock(mock_session: AsyncMock) -> None:
    cache_repo = get_geocache_repo(mock_session)
    with patch.dict(os.environ, {"MAPBOX_API_KEY": "", "MOCK_GEOCODING": "1"}):
        adapter = get_geocoding_port(cache_repo)
        assert adapter is not None


def test_get_geocoding_port_real(mock_session: AsyncMock) -> None:
    cache_repo = get_geocache_repo(mock_session)
    with patch.dict(os.environ, {"MAPBOX_API_KEY": "pk.test.123", "MOCK_GEOCODING": "0"}):
        adapter = get_geocoding_port(cache_repo)
        assert adapter is not None


def test_get_embedding_port_mock() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "MOCK_EMBEDDING": "1"}):
        adapter = get_embedding_port()
        assert adapter is not None


def test_get_embedding_port_real() -> None:
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-xyz", "MOCK_EMBEDDING": "0"}):
        adapter = get_embedding_port()
        assert adapter is not None


def test_get_planner_service() -> None:
    mock_itinerary_repo = MagicMock(spec=IItineraryRepository)
    mock_embedding = MagicMock(spec=IEmbeddingPort)
    planner = get_planner_service(
        itinerary_repo=mock_itinerary_repo,
        embedding_port=mock_embedding,
    )
    assert isinstance(planner, PlannerService)


@pytest.mark.asyncio
async def test_poi_lifespan() -> None:
    from services.poi.main import app, lifespan

    with (
        patch("services.poi.main.init_engine", new_callable=AsyncMock) as mock_init,
        patch("services.poi.main.get_engine") as mock_get_engine,
    ):
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        async with lifespan(app):
            mock_init.assert_awaited_once()
        mock_engine.dispose.assert_awaited_once()


def test_categorize_poi_food_keywords() -> None:
    from services.poi.services.planner import _categorize_poi

    class MockPOI:
        def __init__(self, name=None, description=None, creation_metadata=None):
            self.name = name
            self.description = description
            self.creation_metadata = creation_metadata

    assert _categorize_poi(MockPOI(name="Pike Place Chowder")) == "food"
    assert (
        _categorize_poi(MockPOI(name="Quiet Viewpoint", description="A cozy bakery nearby"))
        == "food"
    )
    assert _categorize_poi(MockPOI(creation_metadata={"category": "dining"})) == "dining"
    assert (
        _categorize_poi(MockPOI(name="Ruby Beach", description="Scenic sea stacks")) == "attraction"
    )
