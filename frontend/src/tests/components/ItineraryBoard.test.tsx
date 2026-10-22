// Copyright (c) 2026 Tim Olker
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ItineraryBoard } from "../../components/planner/ItineraryBoard";
import type { ItineraryResponse } from "../../services/itineraryService";

const mockItinerary: ItineraryResponse = {
  id: "itin-123",
  user_id: "user-test",
  title: "Olympic & Seattle Road Trip",
  destination: "Olympic National Park, WA",
  start_date: "2026-07-01",
  end_date: "2026-07-03",
  budget_cents: 120000,
  total_estimated_cost_cents: 85000,
  currency: "USD",
  status: "draft",
  days: [
    {
      id: "day-1",
      itinerary_id: "itin-123",
      day_number: 1,
      calendar_date: "2026-07-01",
      total_cost_cents: 30000,
      items: [
        {
          id: "item-1",
          itinerary_day_id: "day-1",
          title: "Pike Place Market",
          order_index: 0,
          start_time: "09:00:00",
          end_time: "11:30:00",
          duration_hours: "2.50",
          source_type: "USER_SAVED",
          cost_cents: 2500,
          latitude: 47.6097,
          longitude: -122.3422,
          category: "market",
          poi_id: "poi-1",
        },
        {
          id: "item-2",
          itinerary_day_id: "day-1",
          title: "Seattle Waterfront Stroll",
          order_index: 1,
          start_time: "14:00:00",
          end_time: "17:00:00",
          duration_hours: "3.00",
          source_type: "AI_RECOMMENDED",
          cost_cents: 0,
          latitude: 47.6062,
          longitude: -122.3321,
          category: "walk",
          poi_id: null,
        },
      ],
    },
    {
      id: "day-2",
      itinerary_id: "itin-123",
      day_number: 2,
      calendar_date: "2026-07-02",
      total_cost_cents: 55000,
      items: [
        {
          id: "item-3",
          itinerary_day_id: "day-2",
          title: "Hurricane Ridge Trail",
          order_index: 0,
          start_time: "08:30:00",
          end_time: "13:30:00",
          duration_hours: "5.00",
          source_type: "USER_SAVED",
          cost_cents: 3000,
          latitude: 47.9691,
          longitude: -123.4983,
          category: "trail",
          poi_id: "poi-2",
        },
      ],
    },
  ],
  circuit_breaker_warnings: [],
  advisories: [
    {
      day_number: 1,
      meal_type: "LUNCH",
      gap_start: "11:30:00",
      gap_end: "14:00:00",
    },
  ],
};

describe("ItineraryBoard Component (REQ-PLAN-006, REQ-PLAN-007a, REQ-PLAN-012)", () => {
  it("renders day columns and itinerary items cleanly", () => {
    render(
      <ItineraryBoard itinerary={mockItinerary} onItineraryUpdated={vi.fn()} />,
    );

    // Columns
    expect(screen.getByText(/Day 1/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2/)).toBeInTheDocument();

    // Items
    expect(screen.getByText("Pike Place Market")).toBeInTheDocument();
    expect(screen.getByText("Seattle Waterfront Stroll")).toBeInTheDocument();
    expect(screen.getByText("Hurricane Ridge Trail")).toBeInTheDocument();
  });

  it("renders Missing Meal advisory card during lunch gap", () => {
    render(
      <ItineraryBoard itinerary={mockItinerary} onItineraryUpdated={vi.fn()} />,
    );

    expect(screen.getByText(/Missing LUNCH/i)).toBeInTheDocument();
  });

  it("displays over-planning amber warning banner when daily exploration exceeds 10 hours", () => {
    const overplannedItinerary: ItineraryResponse = {
      ...mockItinerary,
      days: [
        {
          ...mockItinerary.days[0],
          items: [
            {
              id: "item-long",
              itinerary_day_id: "day-1",
              title: "Daylong Epic Trek",
              order_index: 0,
              start_time: "07:00:00",
              end_time: "19:00:00",
              duration_hours: "12.00",
              source_type: "USER_SAVED",
              cost_cents: 0,
              latitude: 47.6,
              longitude: -122.3,
              category: "trek",
            },
          ],
        },
        mockItinerary.days[1],
      ],
      circuit_breaker_warnings: [
        {
          day_number: 1,
          total_active_hours: "12.00",
          threshold_hours: "10.00",
          message:
            "Day 1 scheduled for 12.0 hours, exceeding the 10.0 hour limit.",
        },
      ],
    };

    render(
      <ItineraryBoard
        itinerary={overplannedItinerary}
        onItineraryUpdated={vi.fn()}
      />,
    );

    const banner = screen.getByTestId("circuit-breaker-banner");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/Day 1 exceeds 10 hours/i);
  });

  it("renders DayShortageModal when circuit breaker warning indicates day shortage", () => {
    const onExtendTrip = vi.fn();
    const shortageItinerary: ItineraryResponse = {
      ...mockItinerary,
      circuit_breaker_warnings: [
        {
          day_number: 2,
          total_active_hours: "12.00",
          threshold_hours: "10.00",
          message:
            "Attraction requires 3 days, but only 2 days remain in trip. Please extend trip duration or remove activities.",
        },
      ],
    };

    render(
      <ItineraryBoard
        itinerary={shortageItinerary}
        onItineraryUpdated={vi.fn()}
        onExtendTrip={onExtendTrip}
      />,
    );

    expect(screen.getByText(/Insufficient Days/i)).toBeInTheDocument();
    const extendBtn = screen.getByRole("button", {
      name: /Extend Trip Duration/i,
    });
    expect(extendBtn).toBeInTheDocument();

    // Click extend trip button
    fireEvent.click(extendBtn);
    expect(onExtendTrip).toHaveBeenCalledTimes(1);
  });
});
