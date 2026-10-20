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
  getLayer: vi.fn().mockReturnValue(undefined),
  setStyle: vi.fn(),
  isStyleLoaded: vi.fn().mockReturnValue(true),
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
});
