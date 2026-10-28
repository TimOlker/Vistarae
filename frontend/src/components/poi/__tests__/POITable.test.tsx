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
import { POITable } from "../POITable";
import type { POIMapFeature } from "../../../types/map";

describe("POITable Search & Column Toggle (T-029 / REQ-CTX-025, REQ-CTX-037)", () => {
  const pois: POIMapFeature[] = [
    {
      id: "poi-1",
      name: "Cascade Falls",
      canonical_lat: 44.1,
      canonical_lng: -71.5,
      render_lat: 44.1,
      render_lng: -71.5,
      visit_state: "not_visited",
      rating: 4,
      city: "Lincoln",
      state: "New Hampshire",
      country: "United States",
      tags: ["waterfall", "hiking"],
      description: "Cascading glacial brook tumbling over granite ledges.",
      reason_to_visit: "Hidden swimming hole with pristine mountain water.",
      addresses: [],
    },
    {
      id: "poi-2",
      name: "Old Pine Tavern",
      canonical_lat: 42.3,
      canonical_lng: -71.0,
      render_lat: 42.3,
      render_lng: -71.0,
      visit_state: "visited_return",
      rating: 5,
      city: "Boston",
      state: "Massachusetts",
      country: "United States",
      tags: ["historic", "dining"],
      description: "Colonial-era public house serving local ale and cider.",
      reason_to_visit: "Live traditional folk music and clam chowder served in sourdough.",
      addresses: [],
    },
  ];

  it("filters table results when search term matches exclusively in description", () => {
    render(
      <POITable
        pois={pois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
      />
    );

    expect(screen.getByText("Cascade Falls")).toBeDefined();
    expect(screen.getByText("Old Pine Tavern")).toBeDefined();

    const searchInput = screen.getByTestId("poi-table-search-input");
    // "glacial" is only in Cascade Falls description
    fireEvent.change(searchInput, { target: { value: "glacial" } });

    expect(screen.getByText("Cascade Falls")).toBeDefined();
    expect(screen.queryByText("Old Pine Tavern")).toBeNull();
  });

  it("filters table results when search term matches exclusively in reason_to_visit", () => {
    render(
      <POITable
        pois={pois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
      />
    );

    const searchInput = screen.getByTestId("poi-table-search-input");
    // "clam chowder" is only in Old Pine Tavern reason_to_visit
    fireEvent.change(searchInput, { target: { value: "clam chowder" } });

    expect(screen.getByText("Old Pine Tavern")).toBeDefined();
    expect(screen.queryByText("Cascade Falls")).toBeNull();
  });

  it("does not render obsolete checkbox toggles in header", () => {
    render(
      <POITable
        pois={pois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
      />,
    );

    expect(screen.queryByTestId("toggle-desc-column")).toBeNull();
    expect(screen.queryByTestId("toggle-reason-column")).toBeNull();
  });

  it("renders Reason to Visit and Description columns when configured in tableConfig", () => {
    render(
      <POITable
        pois={pois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
        tableConfig={{
          visible_columns: ["name", "description", "reason_to_visit"],
          column_order: ["name", "description", "reason_to_visit"],
          sort: { column: "name", direction: "asc" },
        }}
      />,
    );

    expect(
      screen.getByRole("columnheader", { name: "Reason to Visit" }),
    ).toBeDefined();
    expect(
      screen.getByRole("columnheader", { name: "Description" }),
    ).toBeDefined();

    const reasonCell = screen.getByTestId("poi-reason-cell-poi-1");
    expect(reasonCell).toBeDefined();
    expect(reasonCell.getAttribute("title")).toBe(
      "Hidden swimming hole with pristine mountain water.",
    );
    expect(reasonCell.textContent).toBe(
      "Hidden swimming hole with pristine mountain water.",
    );

    const descCell = screen.getByTestId("poi-desc-cell-poi-1");
    expect(descCell).toBeDefined();
    expect(descCell.textContent).toBe(
      "Cascading glacial brook tumbling over granite ledges.",
    );
  });

  it("renders duration hours, itinerary days, visit pending, and first visited date", () => {
    const richPois: POIMapFeature[] = [
      {
        ...pois[0],
        recommended_duration_hours: 3.5,
        recommended_visit_days: 1,
        visit_pending: true,
        visited_dates: ["2023-08-15", "2024-06-20"],
      },
    ];

    render(
      <POITable
        pois={richPois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
        tableConfig={{
          visible_columns: [
            "name",
            "recommended_duration_hours",
            "recommended_visit_days",
            "visit_pending",
            "visited_date",
          ],
          column_order: [
            "name",
            "recommended_duration_hours",
            "recommended_visit_days",
            "visit_pending",
            "visited_date",
          ],
          sort: { column: "name", direction: "asc" },
        }}
      />,
    );

    expect(
      screen.getByRole("columnheader", { name: "Duration (Hours)" }),
    ).toBeDefined();
    expect(
      screen.getByRole("columnheader", { name: "Itinerary Days" }),
    ).toBeDefined();
    expect(
      screen.getByRole("columnheader", { name: "Visit Pending" }),
    ).toBeDefined();
    expect(
      screen.getByRole("columnheader", { name: "Visited Date" }),
    ).toBeDefined();

    expect(screen.getByTestId("poi-duration-cell-poi-1").textContent).toBe(
      "3.5 hrs",
    );
    expect(screen.getByTestId("poi-days-cell-poi-1").textContent).toBe("1 days");
    expect(
      screen.getByTestId("poi-visit-pending-cell-poi-1").textContent,
    ).toBe("Pending");
    // Verifies that for multiple visited dates, the first entry is selected/rendered
    expect(screen.getByTestId("poi-visited-date-cell-poi-1").textContent).toBe(
      "2023-08-15",
    );
  });

  it("sorts rows by first visited date when visited_date sort is active", () => {
    const datedPois: POIMapFeature[] = [
      {
        ...pois[0],
        id: "poi-newer",
        name: "Newer Visit",
        visited_dates: ["2024-05-01", "2024-01-01"],
      },
      {
        ...pois[1],
        id: "poi-older",
        name: "Older Visit",
        visited_dates: ["2022-09-10"],
      },
    ];

    const { rerender } = render(
      <POITable
        pois={datedPois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
        tableConfig={{
          visible_columns: ["name", "visited_date"],
          column_order: ["name", "visited_date"],
          sort: { column: "visited_date", direction: "asc" },
        }}
      />,
    );

    const rows = screen.getAllByRole("row");
    // Row 0 is header. Row 1 should be Older Visit (2022), Row 2 should be Newer Visit (2024)
    expect(rows[1].textContent).toContain("Older Visit");
    expect(rows[2].textContent).toContain("Newer Visit");

    // Descending sort
    rerender(
      <POITable
        pois={datedPois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
        tableConfig={{
          visible_columns: ["name", "visited_date"],
          column_order: ["name", "visited_date"],
          sort: { column: "visited_date", direction: "desc" },
        }}
      />,
    );

    const descRows = screen.getAllByRole("row");
    expect(descRows[1].textContent).toContain("Newer Visit");
    expect(descRows[2].textContent).toContain("Older Visit");
  });
});
