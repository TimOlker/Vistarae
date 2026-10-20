// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect } from "vitest";
import {
  createSuperclusterIndex,
  getClustersForViewport,
  filterPOIsByViewport,
  getRenderCoordinates,
} from "../../src/services/clustering";
import type { POIMapFeature, BoundingBox } from "../../src/types/map";

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
    tags: ["historic", "landmark"],
  },
  {
    id: "poi-2",
    name: "Forbidden City",
    canonical_lng: 116.397027,
    canonical_lat: 39.917865,
    render_lng: 116.397027,
    render_lat: 39.917865,
    visit_state: "visited_return",
    rating: 5,
    tags: ["unesco", "palace"],
  },
  {
    id: "poi-3",
    name: "Eiffel Tower",
    canonical_lng: 2.2945,
    canonical_lat: 48.8584,
    render_lng: 2.2945,
    render_lat: 48.8584,
    visit_state: "not_visited",
    rating: null,
    tags: ["iconic"],
  },
];

describe("Supercluster Geospatial Service", () => {
  it("creates an index and generates clusters for nearby points", () => {
    const index = createSuperclusterIndex(samplePOIs, "osm", 50);
    const bbox: BoundingBox = {
      minLng: 115.0,
      minLat: 38.0,
      maxLng: 118.0,
      maxLat: 41.0,
    };

    // At low zoom level (e.g. zoom 5), Tiananmen and Forbidden City cluster together
    const clusters = getClustersForViewport(index, bbox, 5);
    expect(clusters.features.length).toBeGreaterThan(0);
    const cluster = clusters.features.find(
      (f) => f.properties && "cluster" in f.properties,
    );
    expect(cluster).toBeDefined();
  });

  it("transforms coordinates into GCJ-02 space when Amap layer is active inside China", () => {
    const beijingPOI = samplePOIs[0];
    const [renderLng, renderLat] = getRenderCoordinates(beijingPOI, "amap");

    // Expected to shift coordinates into GCJ-02 space
    expect(renderLng).not.toBe(beijingPOI.canonical_lng);
    expect(renderLat).not.toBe(beijingPOI.canonical_lat);
    expect(renderLng).toBeCloseTo(116.403694, 3);
  });

  it("keeps canonical coordinates for international points even when Amap layer is active", () => {
    const parisPOI = samplePOIs[2];
    const [renderLng, renderLat] = getRenderCoordinates(parisPOI, "amap");

    expect(renderLng).toBe(parisPOI.canonical_lng);
    expect(renderLat).toBe(parisPOI.canonical_lat);
  });

  describe("filterPOIsByViewport", () => {
    it("filters POIs inside standard viewport bounding box", () => {
      const beijingBbox: BoundingBox = {
        minLng: 116.0,
        minLat: 39.0,
        maxLng: 117.0,
        maxLat: 40.0,
      };

      const result = filterPOIsByViewport(samplePOIs, beijingBbox);
      expect(result.length).toBe(2);
      expect(result.map((p) => p.id)).toContain("poi-1");
      expect(result.map((p) => p.id)).toContain("poi-2");
      expect(result.map((p) => p.id)).not.toContain("poi-3");
    });

    it("handles antimeridian crossing when minLng > maxLng", () => {
      const pacificBbox: BoundingBox = {
        minLng: 170.0,
        minLat: -20.0,
        maxLng: -170.0,
        maxLat: 20.0,
      };

      const pacificPOI: POIMapFeature = {
        id: "poi-fiji",
        name: "Fiji Islands",
        canonical_lng: 178.0,
        canonical_lat: -17.7,
        render_lng: 178.0,
        render_lat: -17.7,
        visit_state: "not_visited",
        rating: null,
        tags: [],
      };

      const result = filterPOIsByViewport(
        [pacificPOI, ...samplePOIs],
        pacificBbox,
      );
      expect(result.length).toBe(1);
      expect(result[0].id).toBe("poi-fiji");
    });
  });
});
