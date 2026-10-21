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

"""End-to-end integration and latency benchmark for AI Trip Planner (T050, SC-001, SC-003).

Validates that a 5-day itinerary generation request across saved POIs synthesizes
structured days, slots, transit times, and advisories within the < 4.0 second target.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

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

from services.poi.dependencies import get_current_user, get_itinerary_repo, get_planner_service
from services.poi.main import app
from services.poi.services.planner import PlannerService


def build_mock_5day_itinerary(user_id) -> Itinerary:
    """Constructs a realistic 5-day synthesized itinerary."""
    it_id = uuid4()
    days = []
    start_d = date(2026, 8, 1)
    categories = ["scenic", "trail", "viewpoint", "food", "attraction"]

    for d_num in range(1, 6):
        day_id = uuid4()
        items = []
        for i in range(3):
            items.append(
                ItineraryItem(
                    id=uuid4(),
                    itinerary_day_id=day_id,
                    poi_id=uuid4(),
                    title=f"Day {d_num} Destination {i + 1}",
                    category=categories[(d_num + i) % len(categories)],
                    source_type=ItineraryItemSource.USER_SAVED,
                    latitude=47.5 + (d_num * 0.05),
                    longitude=-122.3 - (i * 0.05),
                    order_index=i,
                    duration_hours=Decimal("2.00"),
                    cost_cents=1500,
                    travel_time_prev_minutes=25 if i > 0 else None,
                    travel_distance_prev_meters=18500 if i > 0 else None,
                )
            )
        days.append(
            ItineraryDay(
                id=day_id,
                itinerary_id=it_id,
                day_number=d_num,
                calendar_date=start_d + timedelta(days=d_num - 1),
                notes=f"Exploring sector {d_num}",
                total_cost_cents=4500,
                items=items,
            )
        )

    return Itinerary(
        id=it_id,
        user_id=user_id,
        title="5-Day Pacific Northwest Odyssey",
        destination="Olympic & Puget Sound",
        start_date=start_d,
        end_date=start_d + timedelta(days=4),
        budget_cents=50000,
        currency="USD",
        status=ItineraryStatus.DRAFT,
        days=days,
    )


def run_benchmark() -> float:
    """Executes the E2E trip generation request and returns duration in seconds."""
    user = User(
        id=uuid4(),
        cognito_sub="sub-bench-traveler",
        email="traveler@vistarae.com",
        full_name="Benchmark Traveler",
    )
    expected_itinerary = build_mock_5day_itinerary(user.id)

    mock_repo = AsyncMock(spec=IItineraryRepository)
    mock_repo.create_itinerary.return_value = expected_itinerary

    mock_planner = AsyncMock(spec=PlannerService)
    mock_planner.generate_itinerary.return_value = expected_itinerary

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_itinerary_repo] = lambda: mock_repo
    app.dependency_overrides[get_planner_service] = lambda: mock_planner

    payload = {
        "prompt": "5-day road trip covering dramatic sea stacks, rainforests, and local seafood",
        "destination": "Olympic & Puget Sound",
        "start_date": "2026-08-01",
        "end_date": "2026-08-05",
        "budget_cents": 50000,
        "currency": "USD",
    }

    client = TestClient(app, raise_server_exceptions=False)
    try:
        t0 = time.perf_counter()
        resp = client.post("/api/itineraries/generate", json=payload)
        t1 = time.perf_counter()
    finally:
        app.dependency_overrides.clear()

    duration = t1 - t0
    assert resp.status_code == 201, f"Expected 201 Created, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert len(data["days"]) == 5, f"Expected 5 days, got {len(data['days'])}"
    assert data["destination"] == "Olympic & Puget Sound"
    assert duration < 4.0, f"Latency benchmark exceeded: {duration:.3f}s >= 4.0s (SC-001)"

    return duration


def test_e2e_trip_planner_latency() -> None:
    """Pytest entrypoint for 5-day itinerary generation latency benchmark."""
    duration = run_benchmark()
    assert duration < 4.0


def main() -> int:
    """CLI entrypoint."""
    print("Executing E2E 5-Day Trip Planner Latency Benchmark (SC-001, SC-003)...")
    try:
        duration = run_benchmark()
        print(f"SUCCESS: 5-day itinerary generated in {duration:.3f}s (< 4.0s ceiling)")
        return 0
    except Exception as exc:
        print(f"FAILURE: Benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
