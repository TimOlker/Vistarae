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

"""Unit tests for AI Trip Planner hybrid PostGIS + pgvector RAG synthesis (T009)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import POI
from vistarae_core.domain.itinerary import Itinerary
from vistarae_core.domain.value_objects import WGS84Point
from vistarae_core.schemas.itinerary import ItineraryGenerateRequest

from services.poi.services.planner import PlannerService


@pytest.fixture
def mock_embedding_port() -> AsyncMock:
    """Provides a mocked IEmbeddingPort returning a 768-dim float vector."""
    mock = AsyncMock()
    mock.generate_embedding.return_value = [0.05] * 768
    return mock


@pytest.fixture
def sample_pois() -> list[POI]:
    """Provides sample POIs for corridor retrieval."""
    u_id = uuid4()
    return [
        POI(
            id=uuid4(),
            user_id=u_id,
            name="Rialto Beach",
            geom=WGS84Point(lat=47.9208, lon=-124.6394),
            creation_metadata={"category": "scenic"},
            rating=5,
            estimated_cost=Decimal("10.00"),
            recommended_duration_hours=Decimal("2.00"),
            recommended_visit_days=1,
        ),
        POI(
            id=uuid4(),
            user_id=u_id,
            name="Hoh Rain Forest",
            geom=WGS84Point(lat=47.8601, lon=-123.9348),
            creation_metadata={"category": "nature"},
            rating=5,
            estimated_cost=Decimal("25.00"),
            recommended_duration_hours=Decimal("3.00"),
            recommended_visit_days=1,
        ),
        POI(
            id=uuid4(),
            user_id=u_id,
            name="Pike Place Chowder",
            geom=WGS84Point(lat=47.6097, lon=-122.3422),
            creation_metadata={"category": "food"},
            rating=5,
            estimated_cost=Decimal("18.00"),
            recommended_duration_hours=Decimal("1.00"),
            recommended_visit_days=1,
        ),
    ]


@pytest.fixture
def mock_itinerary_repo(sample_pois: list[POI]) -> AsyncMock:
    """Provides a mocked IItineraryRepository."""
    mock = AsyncMock()
    mock.find_pois_in_corridor_hybrid.return_value = sample_pois

    async def _mock_create(itinerary: Itinerary) -> Itinerary:
        return itinerary

    mock.create_itinerary.side_effect = _mock_create
    return mock


class TestPlannerServiceRAG:
    """Verifies hybrid RAG query synthesis and itinerary assembly."""

    @pytest.mark.asyncio
    async def test_generate_itinerary_hybrid_rag_flow(
        self,
        mock_itinerary_repo: AsyncMock,
        mock_embedding_port: AsyncMock,
    ) -> None:
        """Verifies full generation flow from prompt embedding to persisted itinerary."""
        service = PlannerService(
            itinerary_repo=mock_itinerary_repo,
            embedding_port=mock_embedding_port,
        )
        user_id = uuid4()
        req = ItineraryGenerateRequest(
            prompt="Scenic coastal hikes and local clam chowder",
            destination="Olympic National Park",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 3),
            budget_cents=50000,
            currency="USD",
        )

        response = await service.generate_itinerary(user_id=user_id, request=req)

        # 1. Verify embedding generation was requested
        mock_embedding_port.generate_embedding.assert_awaited_once()

        # 2. Verify hybrid corridor query was executed
        mock_itinerary_repo.find_pois_in_corridor_hybrid.assert_awaited_once()

        # 3. Verify itinerary structure
        assert response.destination == "Olympic National Park"
        assert len(response.days) == 3
        assert response.days[0].day_number == 1
        assert response.days[2].day_number == 3

        # 4. Verify activities assigned
        total_items = sum(len(d.items) for d in response.days)
        assert total_items > 0

        # 5. Verify transit metrics populated for consecutive items
        first_day_items = response.days[0].items
        if len(first_day_items) > 1:
            assert first_day_items[1].travel_time_prev_minutes is not None
            assert first_day_items[1].travel_distance_prev_meters is not None
