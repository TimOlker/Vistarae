// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect } from "vitest";
import {
  isInChinaBBox,
  wgs84_to_gcj02,
  gcj02_to_wgs84,
  wgs84_to_bd09,
  bd09_to_wgs84,
  CHINA_BBOX,
} from "../../src/utils/coordinates";

describe("Two-Way Coordinate Transformation Module", () => {
  describe("isInChinaBBox", () => {
    it("returns true for points well inside China (Beijing, Shanghai, Chengdu)", () => {
      expect(isInChinaBBox(116.397458, 39.909187)).toBe(true); // Beijing
      expect(isInChinaBBox(121.505676, 31.233519)).toBe(true); // Shanghai
      expect(isInChinaBBox(104.066541, 30.572269)).toBe(true); // Chengdu
    });

    it("returns true for exact boundary values (inclusive bounds)", () => {
      expect(isInChinaBBox(CHINA_BBOX.minLng, CHINA_BBOX.minLat)).toBe(true);
      expect(isInChinaBBox(CHINA_BBOX.maxLng, CHINA_BBOX.maxLat)).toBe(true);
      expect(isInChinaBBox(CHINA_BBOX.minLng, CHINA_BBOX.maxLat)).toBe(true);
      expect(isInChinaBBox(CHINA_BBOX.maxLng, CHINA_BBOX.minLat)).toBe(true);
    });

    it("returns false for international locations outside China", () => {
      expect(isInChinaBBox(2.2945, 48.8584)).toBe(false); // Paris Eiffel Tower
      expect(isInChinaBBox(-74.006, 40.7128)).toBe(false); // New York
      expect(isInChinaBBox(139.6917, 35.6895)).toBe(false); // Tokyo
      expect(isInChinaBBox(0.0, 0.0)).toBe(false); // Null Island
    });
  });

  describe("wgs84_to_gcj02 and gcj02_to_wgs84 (Newton Numerical Iteration)", () => {
    it("accurately converts Beijing Tiananmen Square and inverts back within 1e-6 degrees", () => {
      const wgs = { lng: 116.397458, lat: 39.909187 };
      const gcj = wgs84_to_gcj02(wgs.lng, wgs.lat);

      // Verify non-zero offset (~500m shift in mainland China)
      expect(gcj.lng).not.toBe(wgs.lng);
      expect(gcj.lat).not.toBe(wgs.lat);
      expect(gcj.lng).toBeCloseTo(116.403694, 4);
      expect(gcj.lat).toBeCloseTo(39.910543, 4);

      // Verify Newton numerical iteration reverse calculation
      const invertedWgs = gcj02_to_wgs84(gcj.lng, gcj.lat);
      expect(Math.abs(invertedWgs.lng - wgs.lng)).toBeLessThan(1e-6);
      expect(Math.abs(invertedWgs.lat - wgs.lat)).toBeLessThan(1e-6);
    });

    it("accurately converts Shanghai Tower and inverts back within 1e-6 degrees", () => {
      const wgs = { lng: 121.505676, lat: 31.233519 };
      const gcj = wgs84_to_gcj02(wgs.lng, wgs.lat);

      expect(gcj.lng).toBeCloseTo(121.5101, 3);
      expect(gcj.lat).toBeCloseTo(31.2315, 3);

      const invertedWgs = gcj02_to_wgs84(gcj.lng, gcj.lat);
      expect(Math.abs(invertedWgs.lng - wgs.lng)).toBeLessThan(1e-6);
      expect(Math.abs(invertedWgs.lat - wgs.lat)).toBeLessThan(1e-6);
    });

    it("passes international points through unaltered", () => {
      const paris = { lng: 2.2945, lat: 48.8584 };
      const forward = wgs84_to_gcj02(paris.lng, paris.lat);
      expect(forward.lng).toBe(paris.lng);
      expect(forward.lat).toBe(paris.lat);

      const reverse = gcj02_to_wgs84(paris.lng, paris.lat);
      expect(reverse.lng).toBe(paris.lng);
      expect(reverse.lat).toBe(paris.lat);
    });
  });

  describe("wgs84_to_bd09 and bd09_to_wgs84 (Baidu Polar Transformation)", () => {
    it("converts Beijing coordinates to Baidu BD-09 and inverts back within 1e-6 degrees", () => {
      const wgs = { lng: 116.397458, lat: 39.909187 };
      const bd = wgs84_to_bd09(wgs.lng, wgs.lat);

      expect(bd.lng).toBeGreaterThan(wgs.lng);
      expect(bd.lat).toBeGreaterThan(wgs.lat);

      const invertedWgs = bd09_to_wgs84(bd.lng, bd.lat);
      expect(Math.abs(invertedWgs.lng - wgs.lng)).toBeLessThan(1e-6);
      expect(Math.abs(invertedWgs.lat - wgs.lat)).toBeLessThan(1e-6);
    });

    it("passes international points through unaltered for BD-09 transforms", () => {
      const tokyo = { lng: 139.6917, lat: 35.6895 };
      const bd = wgs84_to_bd09(tokyo.lng, tokyo.lat);
      expect(bd.lng).toBe(tokyo.lng);
      expect(bd.lat).toBe(tokyo.lat);

      const reverse = bd09_to_wgs84(tokyo.lng, tokyo.lat);
      expect(reverse.lng).toBe(tokyo.lng);
      expect(reverse.lat).toBe(tokyo.lat);
    });
  });
});
