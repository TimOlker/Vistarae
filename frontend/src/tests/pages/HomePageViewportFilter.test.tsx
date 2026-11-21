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

import { describe, it, expect, vi, beforeEach } from "vitest";
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

vi.mock("../../context/PreferencesContext", () => ({
  usePreferences: () => ({
    poi: {
      default_map_layer: "osm",
      map_language: "local",
    },
  }),
  PreferencesProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../components/map/MapView", () => ({
  MapView: () => <div data-testid="mock-map-view" />,
}));

import {
  HomePage,
  INITIAL_DEMO_POIS,
  SESSION_KEY_EXPLORER_VIEWPORT_FILTER,
} from "../../pages/HomePage";
import { PreferencesProvider } from "../../context/PreferencesContext";

describe("Explorer Page Viewport Filter Session Storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("initializes viewport filter to false by default when session data is empty", () => {
    render(
      <PreferencesProvider>
        <HomePage pois={INITIAL_DEMO_POIS} />
      </PreferencesProvider>,
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /filter to map viewport/i,
    }) as HTMLInputElement;

    expect(checkbox.checked).toBe(false);
    expect(
      sessionStorage.getItem(SESSION_KEY_EXPLORER_VIEWPORT_FILTER),
    ).toBe("false");
  });

  it("restores viewport filter as true when session data has true saved", () => {
    sessionStorage.setItem(SESSION_KEY_EXPLORER_VIEWPORT_FILTER, "true");

    render(
      <PreferencesProvider>
        <HomePage pois={INITIAL_DEMO_POIS} />
      </PreferencesProvider>,
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /filter to map viewport/i,
    }) as HTMLInputElement;

    expect(checkbox.checked).toBe(true);
  });

  it("restores viewport filter as false when session data has false saved", () => {
    sessionStorage.setItem(SESSION_KEY_EXPLORER_VIEWPORT_FILTER, "false");

    render(
      <PreferencesProvider>
        <HomePage pois={INITIAL_DEMO_POIS} />
      </PreferencesProvider>,
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /filter to map viewport/i,
    }) as HTMLInputElement;

    expect(checkbox.checked).toBe(false);
  });

  it("saves the toggled value to session data when user changes checkbox", () => {
    render(
      <PreferencesProvider>
        <HomePage pois={INITIAL_DEMO_POIS} />
      </PreferencesProvider>,
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /filter to map viewport/i,
    }) as HTMLInputElement;

    expect(checkbox.checked).toBe(false);

    // Toggle ON
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
    expect(
      sessionStorage.getItem(SESSION_KEY_EXPLORER_VIEWPORT_FILTER),
    ).toBe("true");

    // Toggle OFF
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
    expect(
      sessionStorage.getItem(SESSION_KEY_EXPLORER_VIEWPORT_FILTER),
    ).toBe("false");
  });
});
