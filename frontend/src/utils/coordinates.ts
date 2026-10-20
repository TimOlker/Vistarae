// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { CoordinatePoint } from "../types/map";

const A = 6378245.0; // Krasovsky 1940 semi-major axis (meters)
const EE = 0.00669342162296594323; // First eccentricity squared
const X_PI = (Math.PI * 3000.0) / 180.0;

/**
 * Geographic bounding box defining mainland China.
 * Min Longitude: 73.66° E, Max Longitude: 135.05° E
 * Min Latitude: 18.16° N, Max Latitude: 53.55° N
 */
export const CHINA_BBOX = {
  minLng: 73.66,
  maxLng: 135.05,
  minLat: 18.16,
  maxLat: 53.55,
} as const;

/**
 * Checks whether a given coordinate point falls strictly within the China bounding box.
 *
 * Args:
 *   lng: Longitude in degrees.
 *   lat: Latitude in degrees.
 *
 * Returns:
 *   true if the coordinate is within China bounds; false otherwise.
 */
export function isInChinaBBox(lng: number, lat: number): boolean {
  return (
    lng >= CHINA_BBOX.minLng &&
    lng <= CHINA_BBOX.maxLng &&
    lat >= CHINA_BBOX.minLat &&
    lat <= CHINA_BBOX.maxLat
  );
}

function transformLat(x: number, y: number): number {
  let ret =
    -100.0 +
    2.0 * x +
    3.0 * y +
    0.2 * y * y +
    0.1 * x * y +
    0.2 * Math.sqrt(Math.abs(x));
  ret +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin((y / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((160.0 * Math.sin((y / 12.0) * Math.PI) +
      320.0 * Math.sin((y * Math.PI) / 30.0)) *
      2.0) /
    3.0;
  return ret;
}

function transformLng(x: number, y: number): number {
  let ret =
    300.0 +
    x +
    2.0 * y +
    0.1 * x * x +
    0.1 * x * y +
    0.1 * Math.sqrt(Math.abs(x));
  ret +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin((x / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((150.0 * Math.sin((x / 12.0) * Math.PI) +
      300.0 * Math.sin((x / 30.0) * Math.PI)) *
      2.0) /
    3.0;
  return ret;
}

/**
 * Transforms canonical WGS-84 coordinates to GCJ-02 (Mars coordinate system).
 * If the coordinates lie outside the China bounding box, returns unaltered coordinates.
 *
 * Args:
 *   lng: Canonical WGS-84 longitude.
 *   lat: Canonical WGS-84 latitude.
 *
 * Returns:
 *   CoordinatePoint with transformed or unaltered { lng, lat }.
 */
export function wgs84_to_gcj02(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const dLatRaw = transformLat(lng - 105.0, lat - 35.0);
  const dLngRaw = transformLng(lng - 105.0, lat - 35.0);

  const radLat = (lat / 180.0) * Math.PI;
  let magic = Math.sin(radLat);
  magic = 1.0 - EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);

  const dLat =
    (dLatRaw * 180.0) / (((A * (1.0 - EE)) / (magic * sqrtMagic)) * Math.PI);
  const dLng =
    (dLngRaw * 180.0) / ((A / sqrtMagic) * Math.cos(radLat) * Math.PI);

  return {
    lng: lng + dLng,
    lat: lat + dLat,
  };
}

/**
 * Converts GCJ-02 coordinates back to canonical WGS-84 using Newton's numerical iteration method.
 * Iterates until the difference is below 0.000001° (< 0.1m ground resolution) or reaches 30 iterations.
 *
 * Args:
 *   lng: GCJ-02 longitude.
 *   lat: GCJ-02 latitude.
 *
 * Returns:
 *   CoordinatePoint with canonical WGS-84 { lng, lat }.
 */
export function gcj02_to_wgs84(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  let currWgsLng = lng;
  let currWgsLat = lat;
  const threshold = 1e-6; // 0.000001 degrees
  const maxIterations = 30;

  for (let i = 0; i < maxIterations; i++) {
    const projectedGcj = wgs84_to_gcj02(currWgsLng, currWgsLat);
    const dLng = projectedGcj.lng - lng;
    const dLat = projectedGcj.lat - lat;

    if (Math.abs(dLng) < threshold && Math.abs(dLat) < threshold) {
      break;
    }

    currWgsLng -= dLng;
    currWgsLat -= dLat;
  }

  return {
    lng: currWgsLng,
    lat: currWgsLat,
  };
}

/**
 * Converts GCJ-02 coordinates to Baidu BD-09 coordinates.
 */
export function gcj02_to_bd09(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * X_PI);
  const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * X_PI);

  return {
    lng: z * Math.cos(theta) + 0.0065,
    lat: z * Math.sin(theta) + 0.006,
  };
}

/**
 * Converts Baidu BD-09 coordinates to GCJ-02 coordinates.
 */
export function bd09_to_gcj02(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const x = lng - 0.0065;
  const y = lat - 0.006;
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI);
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI);

  return {
    lng: z * Math.cos(theta),
    lat: z * Math.sin(theta),
  };
}

/**
 * Converts canonical WGS-84 coordinates to Baidu BD-09 coordinates.
 */
export function wgs84_to_bd09(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }
  const gcj = wgs84_to_gcj02(lng, lat);
  return gcj02_to_bd09(gcj.lng, gcj.lat);
}

/**
 * Converts Baidu BD-09 coordinates back to canonical WGS-84 coordinates.
 */
export function bd09_to_wgs84(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }
  const gcj = bd09_to_gcj02(lng, lat);
  return gcj02_to_wgs84(gcj.lng, gcj.lat);
}
