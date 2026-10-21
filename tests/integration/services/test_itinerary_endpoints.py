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

"""Integration tests for AI Trip Planner and Itinerary Management endpoints (T010)."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.domain.entities import User
from vistarae_core.domain.itinerary import (
    Itinerary,
    ItineraryDay,
    ItineraryItem,
    ItineraryItemSource,
    ItineraryStatus,
)
from vistarae_core.ports.itinerary_repo import IItineraryRepository

from services.poi.dependencies import (
    get_current_user,
    get_itinerary_repo,
    get_planner_service,
)
from services.poi.main import app
from services.poi.services.planner import PlannerService


@pytest.fixture
def mock_user() -> User:
    """Fixture providing a mock authenticated user."""
    return User(
        id=uuid4(),
        cognito_sub="sub-test-12345",
        email="traveler@vistarae.com",
        full_name="Pacific Traveler",
    )


@pytest.fixture
def sample_itinerary(mock_user: User) -> Itinerary:
    """Fixture providing a mock domain itinerary."""
    it_id = uuid4()
    day_id = uuid4()
    item = ItineraryItem(
        id=uuid4(),
        itinerary_day_id=day_id,
        poi_id=uuid4(),
        title="Ruby Beach Sea Stacks",
        category="scenic",
        source_type=ItineraryItemSource.USER_SAVED,
        latitude=47.7099,
        longitude=-124.4137,
        order_index=0,
        start_time=time(9, 30),
        end_time=time(11, 30),
        duration_hours=Decimal("2.00"),
        cost_cents=0,
    )
    day = ItineraryDay(
        id=day_id,
        itinerary_id=it_id,
        day_number=1,
        calendar_date=date(2026, 7, 15),
        notes="Coastal exploration",
        items=[item],
    )
    return Itinerary(
        id=it_id,
        user_id=mock_user.id,
        title="Olympic Coast Adventure",
        destination="Olympic National Park",
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 16),
        budget_cents=25000,
        currency="USD",
        status=ItineraryStatus.DRAFT,
        days=[day],
    )


@pytest.fixture
def mock_repo(sample_itinerary: Itinerary) -> AsyncMock:
    """Fixture providing a mocked IItineraryRepository."""
    repo = AsyncMock(spec=IItineraryRepository)
    repo.list_itineraries_by_user.return_value = [sample_itinerary]
    repo.get_itinerary_by_id.return_value = sample_itinerary
    repo.create_itinerary.return_value = sample_itinerary
    repo.update_itinerary.return_value = sample_itinerary
    repo.delete_itinerary.return_value = True
    repo.reorder_items.return_value = sample_itinerary
    return repo


@pytest.fixture
def client(mock_user: User, mock_repo: AsyncMock):
    """Configures TestClient with overridden dependencies."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_itinerary_repo] = lambda: mock_repo

    c = TestClient(app, raise_server_exceptions=False)
    yield c

    app.dependency_overrides.clear()


class TestItineraryEndpoints:
    """Verifies all itinerary management and RAG endpoints."""

    def test_list_user_itineraries(self, client: TestClient, sample_itinerary: Itinerary) -> None:
        """GET /api/itineraries returns summary list of user's itineraries."""
        response = client.get("/api/itineraries")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == sample_itinerary.title
        assert data[0]["destination"] == sample_itinerary.destination

    def test_get_itinerary_by_id_success(
        self, client: TestClient, sample_itinerary: Itinerary
    ) -> None:
        """GET /api/itineraries/{id} returns complete details including days and items."""
        response = client.get(f"/api/itineraries/{sample_itinerary.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_itinerary.id)
        assert len(data["days"]) == 1
        assert data["days"][0]["items"][0]["title"] == "Ruby Beach Sea Stacks"

    def test_get_itinerary_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        """GET /api/itineraries/{id} returns 404 when itinerary does not exist."""
        mock_repo.get_itinerary_by_id.return_value = None
        response = client.get(f"/api/itineraries/{uuid4()}")
        assert response.status_code == 404
        assert "not found" in response.text.lower()

    def test_create_manual_itinerary(self, client: TestClient, sample_itinerary: Itinerary) -> None:
        """POST /api/itineraries creates manual draft itinerary."""
        payload = {
            "title": "Weekend in Portland",
            "destination": "Portland, OR",
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "budget_cents": 15000,
            "currency": "USD",
            "days": [
                {
                    "day_number": 1,
                    "calendar_date": "2026-08-01",
                    "items": [
                        {
                            "title": "Powell's City of Books",
                            "category": "shopping",
                            "latitude": 45.5231,
                            "longitude": -122.6816,
                            "order_index": 0,
                            "start_time": "10:00:00",
                            "end_time": "12:00:00",
                            "duration_hours": "2.00",
                            "cost_cents": 0,
                        }
                    ],
                }
            ],
        }
        response = client.post("/api/itineraries", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == sample_itinerary.title

    def test_generate_ai_itinerary_rag(
        self, client: TestClient, sample_itinerary: Itinerary, mock_user: User
    ) -> None:
        """POST /api/itineraries/generate synthesizes itinerary draft via PlannerService."""
        mock_planner = AsyncMock(spec=PlannerService)
        # Create ItineraryResponse-like return
        from vistarae_core.schemas.itinerary import (
            ItineraryResponse,
        )

        mock_planner.generate_itinerary.return_value = ItineraryResponse(
            id=sample_itinerary.id,
            user_id=mock_user.id,
            title="Generated Olympic Trip",
            destination="Olympic National Park",
            start_date=date(2026, 7, 15),
            end_date=date(2026, 7, 16),
            budget_cents=25000,
            currency="USD",
            status=ItineraryStatus.DRAFT,
            total_estimated_cost_cents=0,
            days=[],
            advisories=[],
            circuit_breaker_warnings=[],
            created_at=sample_itinerary.created_at,
            updated_at=sample_itinerary.updated_at,
        )
        app.dependency_overrides[get_planner_service] = lambda: mock_planner

        payload = {
            "prompt": "Show me dramatic coastal rocks and temperate rainforests",
            "destination": "Olympic Peninsula",
            "start_date": "2026-07-15",
            "end_date": "2026-07-16",
            "budget_cents": 25000,
            "currency": "USD",
        }
        response = client.post("/api/itineraries/generate", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["destination"] == "Olympic National Park"
        mock_planner.generate_itinerary.assert_called_once()

    def test_update_itinerary_metadata(
        self, client: TestClient, sample_itinerary: Itinerary, mock_repo: AsyncMock
    ) -> None:
        """PUT /api/itineraries/{id} updates title, dates, or budget."""
        payload = {
            "title": "Renamed Coastal Trek",
            "destination": "Olympic Wilderness",
            "start_date": "2026-07-16",
            "end_date": "2026-07-17",
            "budget_cents": 30000,
            "currency": "USD",
            "status": "confirmed",
        }
        response = client.put(f"/api/itineraries/{sample_itinerary.id}", json=payload)
        assert response.status_code == 200

    def test_update_itinerary_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        """PUT /api/itineraries/{id} returns 404 when itinerary missing."""
        mock_repo.get_itinerary_by_id.return_value = None
        response = client.put(f"/api/itineraries/{uuid4()}", json={"title": "Missing"})
        assert response.status_code == 404

    def test_delete_itinerary(self, client: TestClient, sample_itinerary: Itinerary) -> None:
        """DELETE /api/itineraries/{id} removes itinerary."""
        response = client.delete(f"/api/itineraries/{sample_itinerary.id}")
        assert response.status_code == 204

    def test_delete_itinerary_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        """DELETE /api/itineraries/{id} returns 404 when delete fails."""
        mock_repo.delete_itinerary.return_value = False
        response = client.delete(f"/api/itineraries/{uuid4()}")
        assert response.status_code == 404

    def test_reorder_itinerary_items(self, client: TestClient, sample_itinerary: Itinerary) -> None:
        """PUT /api/itineraries/{id}/items/reorder reorders drag-and-drop items."""
        payload = {
            "items": [
                {
                    "item_id": str(sample_itinerary.days[0].items[0].id),
                    "itinerary_day_id": str(sample_itinerary.days[0].id),
                    "order_index": 1,
                    "start_time": "14:00:00",
                    "end_time": "16:00:00",
                }
            ]
        }
        response = client.put(f"/api/itineraries/{sample_itinerary.id}/items/reorder", json=payload)
        assert response.status_code == 200

    def test_reorder_itinerary_items_invalid(
        self, client: TestClient, sample_itinerary: Itinerary, mock_repo: AsyncMock
    ) -> None:
        """PUT /api/itineraries/{id}/items/reorder returns 404 when reorder fails."""
        mock_repo.reorder_items.side_effect = ValueError("Invalid day ID")
        payload = {
            "items": [
                {
                    "item_id": str(sample_itinerary.days[0].items[0].id),
                    "itinerary_day_id": str(sample_itinerary.days[0].id),
                    "order_index": 1,
                }
            ]
        }
        response = client.put(f"/api/itineraries/{sample_itinerary.id}/items/reorder", json=payload)
        assert response.status_code == 404

    def test_spend_killswitch_middleware_halts_requests(self, client: TestClient) -> None:
        """Verifies check_spend_killswitch halts requests with 503 when killswitch active."""
        mock_repo = AsyncMock()
        mock_repo.get_system_setting.return_value = {
            "killswitch_active": True,
            "reason": "AWS Budget ceiling breached",
        }

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with (
            patch("services.poi.main.get_session_factory", return_value=lambda: mock_session_ctx),
            patch("services.poi.main.SqlAlchemyItineraryRepository", return_value=mock_repo),
        ):
            response = client.get("/api/itineraries")
            assert response.status_code == 503
            assert response.headers["content-type"] == "application/problem+json"
            data = response.json()
            assert data["status"] == 503
            assert "Emergency spend killswitch is active" in data["detail"]

            # Health checks bypass spend killswitch to allow readiness probes
            health_resp = client.get("/health/ready")
            assert health_resp.status_code == 200
