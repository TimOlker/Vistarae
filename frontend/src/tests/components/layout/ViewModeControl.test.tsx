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

vi.mock("maplibre-gl", () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      addControl: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      getSource: vi.fn(),
      getBounds: vi.fn().mockReturnValue({
        getWest: () => 0,
        getSouth: () => 0,
        getEast: () => 0,
        getNorth: () => 0,
      }),
      getZoom: vi.fn().mockReturnValue(10),
      getCanvas: vi.fn().mockReturnValue({ style: {} }),
      on: vi.fn(),
      remove: vi.fn(),
      resize: vi.fn(),
      flyTo: vi.fn(),
      easeTo: vi.fn(),
      getLayer: vi.fn(),
      setStyle: vi.fn(),
      isStyleLoaded: vi.fn().mockReturnValue(true),
      queryRenderedFeatures: vi.fn().mockReturnValue([]),
    })),
    NavigationControl: vi.fn(),
  },
}));

vi.mock("../../../context/PreferencesContext", () => ({
  usePreferences: () => ({
    poi: {
      default_map_layer: "osm",
      map_language: "local",
    },
  }),
  PreferencesProvider: ({ children }: any) => <>{children}</>,
}));

import { ViewModeControl } from "../../../components/layout/ViewModeControl";
import { HomePage } from "../../../pages/HomePage";
import { PreferencesProvider } from "../../../context/PreferencesContext";

// Mock MapView to avoid WebGL context requirements in jsdom
vi.mock("../../../components/map/MapView", () => ({
  MapView: ({ layoutMode, onPOIClick, pois }: any) => (
    <div data-testid="mock-map-view" data-layout-mode={layoutMode}>
      <button
        type="button"
        data-testid="mock-select-poi-btn"
        onClick={() => pois && pois[0] && onPOIClick && onPOIClick(pois[0])}
      >
        Select First POI
      </button>
    </div>
  ),
}));

describe("ViewModeControl Component (T-014 / REQ-MAIN-001)", () => {
  it("renders segmented control with all three view mode options", () => {
    const handleChange = vi.fn();
    render(<ViewModeControl mode="split" onChange={handleChange} />);

    expect(
      screen.getByRole("group", { name: /layout view mode/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("view-mode-split")).toBeInTheDocument();
    expect(screen.getByTestId("view-mode-map_only")).toBeInTheDocument();
    expect(screen.getByTestId("view-mode-table_only")).toBeInTheDocument();
  });

  it("reflects the active mode via aria-pressed state", () => {
    const handleChange = vi.fn();
    const { rerender } = render(
      <ViewModeControl mode="split" onChange={handleChange} />,
    );

    expect(screen.getByTestId("view-mode-split")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("view-mode-map_only")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("view-mode-table_only")).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    rerender(<ViewModeControl mode="map_only" onChange={handleChange} />);
    expect(screen.getByTestId("view-mode-split")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("view-mode-map_only")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("view-mode-table_only")).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    rerender(<ViewModeControl mode="table_only" onChange={handleChange} />);
    expect(screen.getByTestId("view-mode-split")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("view-mode-map_only")).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByTestId("view-mode-table_only")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("calls onChange with 'map_only' when Map Only button is clicked", () => {
    const handleChange = vi.fn();
    render(<ViewModeControl mode="split" onChange={handleChange} />);

    fireEvent.click(screen.getByTestId("view-mode-map_only"));
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(handleChange).toHaveBeenCalledWith("map_only");
  });

  it("calls onChange with 'table_only' when Table Only button is clicked", () => {
    const handleChange = vi.fn();
    render(<ViewModeControl mode="split" onChange={handleChange} />);

    fireEvent.click(screen.getByTestId("view-mode-table_only"));
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(handleChange).toHaveBeenCalledWith("table_only");
  });

  it("calls onChange with 'split' when Split View button is clicked", () => {
    const handleChange = vi.fn();
    render(<ViewModeControl mode="table_only" onChange={handleChange} />);

    fireEvent.click(screen.getByTestId("view-mode-split"));
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(handleChange).toHaveBeenCalledWith("split");
  });
});

describe("HomePage Layout Mode Integration (T-013, T-014 / REQ-MAIN-001 to REQ-MAIN-005, SC-001)", () => {
  it("defaults to split view on mount with both map and table displayed", () => {
    render(
      <PreferencesProvider>
        <HomePage />
      </PreferencesProvider>,
    );

    const mapContainer = screen.getByTestId("map-container");
    const tableContainer = screen.getByTestId("table-container");

    expect(mapContainer).toHaveStyle({ display: "flex" });
    expect(tableContainer).toHaveStyle({ display: "flex" });
    expect(screen.getByTestId("view-mode-split")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("hides table and expands map when switching to Map Only mode", () => {
    render(
      <PreferencesProvider>
        <HomePage />
      </PreferencesProvider>,
    );

    fireEvent.click(screen.getByTestId("view-mode-map_only"));

    const mapContainer = screen.getByTestId("map-container");
    const tableContainer = screen.getByTestId("table-container");

    expect(mapContainer).toHaveStyle({ display: "flex", width: "100%" });
    expect(tableContainer).toHaveStyle({ display: "none" });
    expect(screen.getByTestId("view-mode-map_only")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("hides map and expands table when switching to Table Only mode", () => {
    render(
      <PreferencesProvider>
        <HomePage />
      </PreferencesProvider>,
    );

    fireEvent.click(screen.getByTestId("view-mode-table_only"));

    const mapContainer = screen.getByTestId("map-container");
    const tableContainer = screen.getByTestId("table-container");

    expect(mapContainer).toHaveStyle({ display: "none" });
    expect(tableContainer).toHaveStyle({ display: "flex", width: "100%" });
    expect(screen.getByTestId("view-mode-table_only")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("restores split view when switching back from Table Only", () => {
    render(
      <PreferencesProvider>
        <HomePage />
      </PreferencesProvider>,
    );

    fireEvent.click(screen.getByTestId("view-mode-table_only"));
    fireEvent.click(screen.getByTestId("view-mode-split"));

    const mapContainer = screen.getByTestId("map-container");
    const tableContainer = screen.getByTestId("table-container");

    expect(mapContainer).toHaveStyle({ display: "flex" });
    expect(tableContainer).toHaveStyle({ display: "flex" });
  });

  it("preserves active POI selection across layout mode transitions (REQ-MAIN-005)", () => {
    render(
      <PreferencesProvider>
        <HomePage />
      </PreferencesProvider>,
    );

    // Select POI via map click trigger
    fireEvent.click(screen.getByTestId("mock-select-poi-btn"));

    // Switch to Map Only
    fireEvent.click(screen.getByTestId("view-mode-map_only"));
    expect(screen.getByTestId("map-container")).toHaveStyle({
      display: "flex",
    });

    // Switch to Table Only
    fireEvent.click(screen.getByTestId("view-mode-table_only"));
    expect(screen.getByTestId("table-container")).toHaveStyle({
      display: "flex",
    });

    // Switch back to Split View
    fireEvent.click(screen.getByTestId("view-mode-split"));
    expect(screen.getByTestId("map-container")).toHaveStyle({
      display: "flex",
    });
    expect(screen.getByTestId("table-container")).toHaveStyle({
      display: "flex",
    });
  });
});
