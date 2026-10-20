// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import Supercluster from "supercluster";
import type { BoundingBox, MapLayerId, POIMapFeature } from "../types/map";
import {
  isInChinaBBox,
  wgs84_to_bd09,
  wgs84_to_gcj02,
} from "../utils/coordinates";

export type POIFeature = GeoJSON.Feature<GeoJSON.Point, POIMapFeature>;

/**
 * Transforms coordinates for rendering if a shifted Chinese map layer is active.
 *
 * Args:
 *   poi: The canonical POI feature.
 *   activeLayer: Active map tile provider ID.
 *
 * Returns:
 *   [render_lng, render_lat] in map coordinate space.
 */
export function getRenderCoordinates(
  poi: POIMapFeature,
  activeLayer?: MapLayerId,
): [number, number] {
  if (
    (activeLayer === "amap" || activeLayer === "baidu") &&
    isInChinaBBox(poi.canonical_lng, poi.canonical_lat)
  ) {
    if (activeLayer === "amap") {
      const gcj = wgs84_to_gcj02(poi.canonical_lng, poi.canonical_lat);
      return [gcj.lng, gcj.lat];
    }
    if (activeLayer === "baidu") {
      const bd = wgs84_to_bd09(poi.canonical_lng, poi.canonical_lat);
      return [bd.lng, bd.lat];
    }
  }
  return [poi.canonical_lng, poi.canonical_lat];
}

/**
 * Converts a list of POI entities into GeoJSON Point features.
 */
export function poisToGeoJSONFeatures(
  pois: POIMapFeature[],
  activeLayer?: MapLayerId,
): POIFeature[] {
  return pois.map((poi) => {
    const [lng, lat] = getRenderCoordinates(poi, activeLayer);
    return {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [lng, lat],
      },
      properties: {
        ...poi,
        render_lng: lng,
        render_lat: lat,
      },
    };
  });
}

/**
 * Initializes and populates an in-memory Supercluster spatial index.
 *
 * Args:
 *   pois: Array of POIMapFeature records.
 *   activeLayer: Currently selected tile layer.
 *   radius: Cluster radius in pixels (default: 50).
 *
 * Returns:
 *   Loaded Supercluster instance.
 */
export function createSuperclusterIndex(
  pois: POIMapFeature[],
  activeLayer?: MapLayerId,
  radius = 50,
): Supercluster<POIMapFeature, Supercluster.AnyProps> {
  const index = new Supercluster<POIMapFeature>({
    radius,
    maxZoom: 16,
    minPoints: 2,
  });

  const features = poisToGeoJSONFeatures(pois, activeLayer);
  index.load(features);
  return index;
}

/**
 * Retrieves clustered or individual GeoJSON features for the current map viewport.
 *
 * Args:
 *   index: Loaded Supercluster index.
 *   bbox: Viewport bounding box { minLng, minLat, maxLng, maxLat }.
 *   zoom: Current map zoom level.
 *
 * Returns:
 *   GeoJSON FeatureCollection.
 */
export function getClustersForViewport(
  index: Supercluster<POIMapFeature, Supercluster.AnyProps>,
  bbox: BoundingBox,
  zoom: number,
): GeoJSON.FeatureCollection<GeoJSON.Point> {
  // Handle antimeridian crossing (when minLng > maxLng)
  let features: Array<
    | Supercluster.ClusterFeature<Supercluster.AnyProps>
    | Supercluster.PointFeature<POIMapFeature>
  > = [];

  if (bbox.minLng > bbox.maxLng) {
    // Split into Western and Eastern hemisphere boxes across 180° meridian
    const west = index.getClusters(
      [bbox.minLng, bbox.minLat, 180.0, bbox.maxLat],
      Math.floor(zoom),
    );
    const east = index.getClusters(
      [-180.0, bbox.minLat, bbox.maxLng, bbox.maxLat],
      Math.floor(zoom),
    );
    features = [...west, ...east];
  } else {
    features = index.getClusters(
      [bbox.minLng, bbox.minLat, bbox.maxLng, bbox.maxLat],
      Math.floor(zoom),
    );
  }

  return {
    type: "FeatureCollection",
    features,
  };
}

/**
 * Filters a collection of POIs to those whose coordinates fall inside the viewport bounding box.
 * Supports antimeridian crossing logic without infinite recursion.
 *
 * Args:
 *   pois: Array of POI entities.
 *   bbox: Current map viewport bounding box.
 *
 * Returns:
 *   Filtered array of POIMapFeature entities.
 */
export function filterPOIsByViewport(
  pois: POIMapFeature[],
  bbox: BoundingBox,
): POIMapFeature[] {
  const { minLng, minLat, maxLng, maxLat } = bbox;

  return pois.filter((poi) => {
    // Coordinate latitude must always be within minLat and maxLat
    if (poi.canonical_lat < minLat || poi.canonical_lat > maxLat) {
      return false;
    }

    // Antimeridian crossing check
    if (minLng > maxLng) {
      return poi.canonical_lng >= minLng || poi.canonical_lng <= maxLng;
    }

    return poi.canonical_lng >= minLng && poi.canonical_lng <= maxLng;
  });
}
