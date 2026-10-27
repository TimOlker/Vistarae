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

  it("toggles Reason to Visit column visibility and renders truncated cell with tooltip", () => {
    render(
      <POITable
        pois={pois}
        isViewportFilterActive={false}
        onToggleViewportFilter={vi.fn()}
        onSelectPOI={vi.fn()}
      />
    );

    // Initially, Reason to Visit column header is not displayed
    expect(screen.queryByRole("columnheader", { name: "Reason to Visit" })).toBeNull();

    // Toggle column on
    const toggleReason = screen.getByTestId("toggle-reason-column");
    fireEvent.click(toggleReason);

    // Column header should now be present
    expect(screen.getByRole("columnheader", { name: "Reason to Visit" })).toBeDefined();

    // Cell with tooltip title should be present
    const cell = screen.getByTestId("poi-reason-cell-poi-1");
    expect(cell).toBeDefined();
    expect(cell.getAttribute("title")).toBe("Hidden swimming hole with pristine mountain water.");
    expect(cell.textContent).toBe("Hidden swimming hole with pristine mountain water.");
  });
});
