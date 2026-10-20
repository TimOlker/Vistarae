// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export interface CoordinatePoint {
  lng: number; // Longitude in degrees (-180.0 to 180.0)
  lat: number; // Latitude in degrees (-90.0 to 90.0)
}

export interface BoundingBox {
  minLng: number;
  minLat: number;
  maxLng: number;
  maxLat: number;
}

export type VisitState =
  "not_visited" | "visited_do_not_return" | "visited_return";

export type MapLayerId =
  | "osm"
  | "openfreemap"
  | "satellite"
  | "google-roadmap"
  | "google-hybrid"
  | "road"
  | "amap"
  | "baidu";

export interface LayerConfig {
  id: MapLayerId;
  name: string;
  isShifted: boolean; // True for Amap (GCJ-02) and Baidu (BD-09)
  type?: "raster" | "vector";
  styleUrl?: string;
  tiles: string[];
  maxZoom: number;
  attribution: string;
}

export interface POIMapFeature {
  id: string;
  name: string;
  canonical_lat: number; // Canonical WGS-84
  canonical_lng: number; // Canonical WGS-84
  render_lat: number; // Projected for rendering if shifted layer is active
  render_lng: number; // Projected for rendering if shifted layer is active
  visit_state: VisitState;
  rating: number | null;
  tags: string[];
  address?: string;
  city?: string;
  country?: string;
}
