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

"""Unit tests for Trip Planner business rules, circuit breakers, and meal advisories (T017)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import POI
from vistarae_core.domain.value_objects import WGS84Point
from vistarae_core.schemas.itinerary import ItineraryGenerateRequest

from services.poi.services.planner import PlannerService


class TestItineraryBusinessRules:
    """Verifies circuit breakers, multi-day shortage alerts, and meal gap detection."""

    @pytest.mark.asyncio
    async def test_multi_day_shortage_detection(self) -> None:
        """Asserts that a POI requiring more days than available triggers shortage warning."""
        mock_repo = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.generate_embedding.return_value = [0.0] * 768

        # Attraction requiring 4 days on a 2-day trip
        mock_repo.find_pois_in_corridor_hybrid.return_value = [
            POI(
                id=uuid4(),
                user_id=uuid4(),
                name="Yellowstone Grand Loop",
                geom=WGS84Point(lat=44.4280, lon=-110.5885),
                creation_metadata={"category": "scenic"},
                recommended_visit_days=4,
            )
        ]
        mock_repo.create_itinerary.side_effect = lambda it: it

        service = PlannerService(itinerary_repo=mock_repo, embedding_port=mock_embedder)
        req = ItineraryGenerateRequest(
            prompt="Quick 2 day weekend tour",
            destination="Yellowstone",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 2),
            budget_cents=20000,
        )

        response = await service.generate_itinerary(user_id=uuid4(), request=req)

        # Verify warning emitted about insufficient days
        assert len(response.circuit_breaker_warnings) >= 1
        shortage_warning = response.circuit_breaker_warnings[0]
        assert "Not enough days available" in shortage_warning.message
        assert "4 days" in shortage_warning.message

    @pytest.mark.asyncio
    async def test_missing_meal_advisories(self) -> None:
        """Asserts that days lacking meals emit lunch and dinner advisories."""
        mock_repo = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.generate_embedding.return_value = [0.0] * 768

        # Purely scenic / attraction POIs without food
        mock_repo.find_pois_in_corridor_hybrid.return_value = [
            POI(
                id=uuid4(),
                user_id=uuid4(),
                name="Mount Rainier Vista",
                geom=WGS84Point(lat=46.8523, lon=-121.7603),
                creation_metadata={"category": "scenic"},
                recommended_visit_days=1,
            )
        ]
        mock_repo.create_itinerary.side_effect = lambda it: it

        service = PlannerService(itinerary_repo=mock_repo, embedding_port=mock_embedder)
        req = ItineraryGenerateRequest(
            prompt="Scenic drive",
            destination="Mount Rainier",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            budget_cents=10000,
        )

        response = await service.generate_itinerary(user_id=uuid4(), request=req)

        # Assert missing meal advisories for lunch and dinner
        meal_types = {adv.meal_type for adv in response.advisories}
        assert "lunch" in meal_types
        assert "dinner" in meal_types

    @pytest.mark.asyncio
    async def test_active_hours_circuit_breaker(self) -> None:
        """Asserts that daily exploration exceeding 10.0 hours triggers warning (REQ-PLAN-006)."""
        mock_repo = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.generate_embedding.return_value = [0.0] * 768

        # 6 POIs to schedule 3 activities per day, each with duration
        pois = [
            POI(
                id=uuid4(),
                user_id=uuid4(),
                name=f"Hike {i}",
                geom=WGS84Point(lat=47.5 + (i * 0.01), lon=-122.0 - (i * 0.01)),
                creation_metadata={"category": "outdoors"},
                recommended_duration_hours=Decimal("4.00"),
                recommended_visit_days=1,
            )
            for i in range(5)
        ]
        mock_repo.find_pois_in_corridor_hybrid.return_value = pois
        mock_repo.create_itinerary.side_effect = lambda it: it

        service = PlannerService(itinerary_repo=mock_repo, embedding_port=mock_embedder)
        req = ItineraryGenerateRequest(
            prompt="Endurance hiking trail",
            destination="Cascades",
            start_date=date(2026, 7, 10),
            end_date=date(2026, 7, 10),
            budget_cents=50000,
        )

        response = await service.generate_itinerary(user_id=uuid4(), request=req)
        assert len(response.days) == 1
        day = response.days[0]
        assert len(day.items) >= 2
        # Check transit calculations on second item
        second_item = day.items[1]
        assert second_item.travel_distance_prev_meters is not None
        assert second_item.travel_time_prev_minutes is not None
        # Verify circuit breaker warning triggered
        assert len(response.circuit_breaker_warnings) >= 1
        assert any("exceeds 10 hours" in w.message for w in response.circuit_breaker_warnings)

    @pytest.mark.asyncio
    async def test_embedding_failure_fallback(self) -> None:
        """Asserts that failure in embedding service gracefully falls back to zero vector."""
        mock_repo = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.generate_embedding.side_effect = RuntimeError("API quota exceeded")

        mock_repo.find_pois_in_corridor_hybrid.return_value = []
        mock_repo.create_itinerary.side_effect = lambda it: it

        service = PlannerService(itinerary_repo=mock_repo, embedding_port=mock_embedder)
        req = ItineraryGenerateRequest(
            prompt="Spontaneous trip",
            destination="Olympic Peninsula",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 1),
        )

        response = await service.generate_itinerary(user_id=uuid4(), request=req)
        assert response.destination == "Olympic Peninsula"
        # Verified fallback called find_pois_in_corridor_hybrid with zeros
        mock_repo.find_pois_in_corridor_hybrid.assert_called_once()
        call_kwargs = mock_repo.find_pois_in_corridor_hybrid.call_args.kwargs
        assert call_kwargs["query_embedding"] == [0.0] * 768

    def test_schema_date_validations(self) -> None:
        """Verifies date ordering and 30-day max duration validations."""
        from vistarae_core.schemas.itinerary import ItineraryCreate

        # Test end_date < start_date
        with pytest.raises(ValueError, match="end_date must be on or after start_date"):
            ItineraryCreate(
                title="Invalid Date Trip",
                destination="Seattle",
                start_date=date(2026, 8, 10),
                end_date=date(2026, 8, 5),
            )

        with pytest.raises(ValueError, match="end_date must be on or after start_date"):
            ItineraryGenerateRequest(
                prompt="Explore Seattle",
                destination="Seattle",
                start_date=date(2026, 8, 10),
                end_date=date(2026, 8, 5),
            )

        # Test > 30 days
        with pytest.raises(ValueError, match="Trips cannot exceed 30 days"):
            ItineraryCreate(
                title="Too Long Trip",
                destination="Seattle",
                start_date=date(2026, 8, 1),
                end_date=date(2026, 9, 15),
            )

        with pytest.raises(ValueError, match="Trips cannot exceed 30 days"):
            ItineraryGenerateRequest(
                prompt="Too Long Trip",
                destination="Seattle",
                start_date=date(2026, 8, 1),
                end_date=date(2026, 9, 15),
            )
