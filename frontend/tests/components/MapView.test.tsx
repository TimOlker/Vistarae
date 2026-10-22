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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MapView } from "../../src/components/map/MapView";
import type { POIMapFeature } from "../../src/types/map";

// Mock MapLibre GL
const mockSetData = vi.fn();
const mockSetTiles = vi.fn();
const mockMapEvents: Record<string, ((...args: unknown[]) => void)[]> = {};

const mockSource = {
  setData: mockSetData,
  setTiles: mockSetTiles,
};

let mockExistingSources: Record<string, unknown> = {
  "raster-tiles": mockSource,
};

const mockMapInstance = {
  addControl: vi.fn(),
  resize: vi.fn(),
  addSource: vi.fn().mockImplementation((name: string) => {
    mockExistingSources[name] = mockSource;
  }),
  addLayer: vi.fn(),
  getSource: vi.fn().mockImplementation((name: string) => {
    return mockExistingSources[name];
  }),
  getBounds: vi.fn().mockReturnValue({
    getWest: () => 116.0,
    getSouth: () => 39.0,
    getEast: () => 117.0,
    getNorth: () => 40.0,
  }),
  getZoom: vi.fn().mockReturnValue(10),
  getCanvas: vi.fn().mockReturnValue({ style: {} }),
  on: vi.fn().mockImplementation((event: string, ...rest: unknown[]) => {
    const handler = rest[rest.length - 1] as (...args: unknown[]) => void;
    if (!mockMapEvents[event]) {
      mockMapEvents[event] = [];
    }
    mockMapEvents[event].push(handler);
  }),
  remove: vi.fn(),
  flyTo: vi.fn(),
  easeTo: vi.fn(),
  fitBounds: vi.fn(),
  project: vi.fn().mockReturnValue({ x: 100, y: 150 }),
  getLayer: vi.fn().mockReturnValue(undefined),
  setStyle: vi.fn(),
  isStyleLoaded: vi.fn().mockReturnValue(true),
  getStyle: vi.fn().mockReturnValue({ version: 8, sources: {}, layers: [] }),
  once: vi.fn().mockImplementation((event: string, ...rest: unknown[]) => {
    const handler = rest[rest.length - 1] as (...args: unknown[]) => void;
    if (!mockMapEvents[event]) {
      mockMapEvents[event] = [];
    }
    mockMapEvents[event].push(handler);
  }),
  queryRenderedFeatures: vi.fn().mockReturnValue([]),
};

vi.mock("maplibre-gl", () => {
  return {
    default: {
      Map: vi.fn().mockImplementation(() => mockMapInstance),
      NavigationControl: vi.fn(),
    },
  };
});

const samplePOIs: POIMapFeature[] = [
  {
    id: "poi-1",
    name: "Tiananmen Square",
    canonical_lng: 116.397458,
    canonical_lat: 39.909187,
    render_lng: 116.397458,
    render_lat: 39.909187,
    visit_state: "visited_return",
    rating: 5,
    tags: ["historic"],
  },
];

describe("MapView Component", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    Object.keys(mockMapEvents).forEach((key) => delete mockMapEvents[key]);
    mockExistingSources = { "raster-tiles": mockSource };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("initializes MapLibre map with container, sources, and cluster layers", () => {
    render(<MapView pois={samplePOIs} totalPoiCount={1} />);

    expect(mockMapInstance.addControl).toHaveBeenCalled();
    // Trigger map 'load' event
    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    expect(mockMapInstance.addSource).toHaveBeenCalledWith(
      "pois",
      expect.any(Object),
    );
    expect(mockMapInstance.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: "clusters" }),
    );
    expect(mockMapInstance.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: "unclustered-point" }),
    );
    expect(mockSetData).toHaveBeenCalled();
  });

  it("debounces map moveend by 300ms before querying server for datasets >= 1,000 POIs", () => {
    const onFetchServerViewport = vi.fn().mockResolvedValue(undefined);

    render(
      <MapView
        pois={samplePOIs}
        totalPoiCount={1500}
        onFetchServerViewport={onFetchServerViewport}
      />,
    );

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // Simulate user moving map
    act(() => {
      mockMapEvents["movestart"]?.forEach((cb) => cb());
      mockMapEvents["moveend"]?.forEach((cb) => cb());
    });

    // At 150ms, request should NOT have fired yet
    vi.advanceTimersByTime(150);
    expect(onFetchServerViewport).not.toHaveBeenCalled();

    // Another gesture before 300ms resets debounce
    act(() => {
      mockMapEvents["movestart"]?.forEach((cb) => cb());
      mockMapEvents["moveend"]?.forEach((cb) => cb());
    });

    vi.advanceTimersByTime(200);
    expect(onFetchServerViewport).not.toHaveBeenCalled();

    // After full 300ms elapses without interruption, request fires
    vi.advanceTimersByTime(100);
    expect(onFetchServerViewport).toHaveBeenCalledTimes(1);
    expect(onFetchServerViewport).toHaveBeenCalledWith(
      { minLng: 116.0, minLat: 39.0, maxLng: 117.0, maxLat: 40.0 },
      expect.any(AbortSignal),
    );
  });

  it("executes reverse Newton numerical iteration when dropping pin on shifted Amap layer in China", () => {
    const onPinDrop = vi.fn();

    render(
      <MapView
        pois={samplePOIs}
        totalPoiCount={1}
        activeLayer="amap"
        isPinDropMode={true}
        onPinDrop={onPinDrop}
      />,
    );

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // Simulate click on Amap layer in Beijing (e.g. Tiananmen shifted coordinates)
    const shiftedBeijing = { lng: 116.403694, lat: 39.910543 };
    act(() => {
      mockMapEvents["click"]?.forEach((cb) =>
        cb({ lngLat: shiftedBeijing, point: { x: 100, y: 100 } }),
      );
    });

    expect(onPinDrop).toHaveBeenCalledTimes(1);
    const passedCoords = onPinDrop.mock.calls[0][0];

    // Assert that the coordinates passed to callback were reversed to canonical WGS-84 (~116.397458, ~39.909187)
    expect(passedCoords.lng).toBeCloseTo(116.397458, 4);
    expect(passedCoords.lat).toBeCloseTo(39.909187, 4);
  });

  it("renders pin drop mode banner when isPinDropMode is true", () => {
    render(
      <MapView pois={samplePOIs} totalPoiCount={1} isPinDropMode={true} />,
    );

    expect(
      screen.getByText(/Click anywhere on the map to set location pin/i),
    ).toBeInTheDocument();
  });

  it("switches to vector style URL when OpenFreeMap layer is selected", () => {
    const onLayerChange = vi.fn();
    render(
      <MapView
        pois={samplePOIs}
        totalPoiCount={1}
        activeLayer="osm"
        onLayerChange={onLayerChange}
      />,
    );

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // Open layer switcher
    const switcherButton = screen.getByRole("button", { name: /layers/i });
    act(() => {
      switcherButton.click();
    });

    // Click on OpenFreeMap (English Vector)
    const ofmButton = screen.getByText(/OpenFreeMap \(English Vector\)/i);
    act(() => {
      ofmButton.click();
    });

    expect(onLayerChange).toHaveBeenCalledWith("openfreemap");
    expect(mockMapInstance.setStyle).toHaveBeenCalledWith(
      "https://tiles.openfreemap.org/styles/liberty",
    );
  });

  it("calculates cluster bounding box and eases camera via map.fitBounds with 300ms easing (T-033 / REQ-MAIN-036, SC-005)", () => {
    const clusterPOIs: POIMapFeature[] = [
      {
        id: "poi-c1",
        name: "Place A",
        canonical_lng: 116.38,
        canonical_lat: 39.9,
        render_lng: 116.38,
        render_lat: 39.9,
        visit_state: "not_visited",
        tags: [],
      },
      {
        id: "poi-c2",
        name: "Place B",
        canonical_lng: 116.39,
        canonical_lat: 39.91,
        render_lng: 116.39,
        render_lat: 39.91,
        visit_state: "not_visited",
        tags: [],
      },
    ];

    render(<MapView pois={clusterPOIs} totalPoiCount={2} />);

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // Extract the real cluster feature generated by Supercluster
    const lastGeoJSON =
      mockSetData.mock.calls[mockSetData.mock.calls.length - 1][0];
    const clusterFeat = lastGeoJSON.features.find(
      (f: any) => f.properties?.cluster,
    );

    mockMapInstance.getLayer.mockImplementation((id: string) =>
      id === "clusters" ? {} : undefined,
    );
    mockMapInstance.queryRenderedFeatures.mockReturnValue([clusterFeat]);

    // Click cluster
    act(() => {
      mockMapEvents["click"]?.forEach((cb) =>
        cb({ point: { x: 50, y: 50 }, lngLat: { lng: 116.385, lat: 39.905 } }),
      );
    });

    // Verify map.fitBounds called with exact bounding box and 300ms duration
    expect(mockMapInstance.fitBounds).toHaveBeenCalledTimes(1);
    expect(mockMapInstance.fitBounds).toHaveBeenCalledWith(
      [
        [116.38, 39.9],
        [116.39, 39.91],
      ],
      { padding: 60, maxZoom: 18, duration: 300 },
    );
  });

  it("renders co-located POI disambiguation list popup for overlapping markers at max zoom >= 19.5 (T-034 / REQ-MAIN-037)", () => {
    const colocatedPOIs: POIMapFeature[] = [
      {
        id: "poi-co1",
        name: "Museum Exhibit 1",
        canonical_lng: 116.39,
        canonical_lat: 39.91,
        render_lng: 116.39,
        render_lat: 39.91,
        visit_state: "visited_return",
        rating: 5,
        tags: [],
      },
      {
        id: "poi-co2",
        name: "Museum Exhibit 2",
        canonical_lng: 116.39,
        canonical_lat: 39.91,
        render_lng: 116.39,
        render_lat: 39.91,
        visit_state: "not_visited",
        rating: 4,
        tags: [],
      },
    ];

    render(<MapView pois={colocatedPOIs} totalPoiCount={2} />);

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // Set map zoom to 19.5 to trigger co-location disambiguation
    mockMapInstance.getZoom.mockReturnValue(19.5);

    const lastGeoJSON =
      mockSetData.mock.calls[mockSetData.mock.calls.length - 1][0];
    const clusterFeat = lastGeoJSON.features.find(
      (f: any) => f.properties?.cluster,
    );

    mockMapInstance.getLayer.mockImplementation((id: string) =>
      id === "clusters" ? {} : undefined,
    );
    mockMapInstance.queryRenderedFeatures.mockReturnValue([clusterFeat]);

    // Click cluster at max zoom
    act(() => {
      mockMapEvents["click"]?.forEach((cb) =>
        cb({ point: { x: 50, y: 50 }, lngLat: { lng: 116.39, lat: 39.91 } }),
      );
    });

    // Disambiguation list popup should render
    expect(screen.getByTestId("colocated-popup-list")).toBeInTheDocument();
    expect(screen.getByTestId("colocated-popup-title")).toHaveTextContent(
      "Co-located POIs (2)",
    );
    expect(screen.getByTestId("colocated-poi-item-poi-co1")).toBeInTheDocument();
    expect(screen.getByTestId("colocated-poi-item-poi-co2")).toBeInTheDocument();

    // Selecting an item from the disambiguation list transitions to that POI's popup card
    act(() => {
      screen.getByTestId("colocated-poi-item-poi-co1").click();
    });

    expect(screen.queryByTestId("colocated-popup-list")).not.toBeInTheDocument();
    expect(screen.getByTestId("poi-popup-card")).toBeInTheDocument();
    expect(screen.getByTestId("poi-popup-title")).toHaveTextContent("Museum Exhibit 1");
  });

  it("renders POIPopupCard upon unclustered pin click and opens drawer on Edit POI click (T-035, T-036 / REQ-MAIN-038, REQ-MAIN-039)", () => {
    const onPOIClick = vi.fn();
    const onEditPOI = vi.fn();

    render(
      <MapView
        pois={samplePOIs}
        totalPoiCount={1}
        onPOIClick={onPOIClick}
        onEditPOI={onEditPOI}
      />,
    );

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    mockMapInstance.getLayer.mockImplementation((id: string) =>
      id === "unclustered-point" ? {} : undefined,
    );
    mockMapInstance.queryRenderedFeatures.mockReturnValue([
      {
        properties: { id: "poi-1", name: "Tiananmen Square" },
        geometry: { type: "Point", coordinates: [116.397458, 39.909187] },
      },
    ]);

    // Click unclustered point
    act(() => {
      mockMapEvents["click"]?.forEach((cb) =>
        cb({ point: { x: 50, y: 50 }, lngLat: { lng: 116.397458, lat: 39.909187 } }),
      );
    });

    expect(onPOIClick).toHaveBeenCalledWith(samplePOIs[0]);
    expect(screen.getByTestId("poi-popup-card")).toBeInTheDocument();
    expect(screen.getByTestId("poi-popup-title")).toHaveTextContent("Tiananmen Square");

    // Click Edit POI button inside popup card
    const editBtn = screen.getByTestId("popup-edit-poi-btn");
    act(() => {
      editBtn.click();
    });

    // Should call onEditPOI and close popup
    expect(onEditPOI).toHaveBeenCalledWith(samplePOIs[0]);
    expect(screen.queryByTestId("poi-popup-card")).not.toBeInTheDocument();
  });

  it("continuously synchronizes visible POIs with viewport bounding box changes (T-037 / REQ-MAIN-040)", () => {
    const onViewportChange = vi.fn();

    render(
      <MapView
        pois={samplePOIs}
        totalPoiCount={1}
        onViewportChange={onViewportChange}
      />,
    );

    act(() => {
      mockMapEvents["load"]?.forEach((cb) => cb());
    });

    // onViewportChange should have fired on initial load
    expect(onViewportChange).toHaveBeenCalled();
    const [bbox, visible] = onViewportChange.mock.calls[0];
    expect(bbox).toEqual({
      minLng: 116.0,
      minLat: 39.0,
      maxLng: 117.0,
      maxLat: 40.0,
    });
    expect(visible).toHaveLength(1);
    expect(visible[0].id).toBe("poi-1");
  });
});

