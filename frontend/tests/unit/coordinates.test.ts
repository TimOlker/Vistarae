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

import { describe, it, expect } from "vitest";
import {
  isInChinaBBox,
  wgs84_to_gcj02,
  gcj02_to_wgs84,
  wgs84_to_bd09,
  bd09_to_wgs84,
  CHINA_BBOX,
  isGoogleMapsUrl,
  parseGoogleMapsUrl,
  isGeohackUrl,
  parseGeohackUrl,
  isWebpageUrl,
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

  describe("Google Maps URL Coordinate Parser", () => {
    it("detects Google Maps URLs accurately with isGoogleMapsUrl", () => {
      expect(
        isGoogleMapsUrl(
          "https://www.google.com/maps/place/M'Zab/@32.4756753,3.7051475"
        )
      ).toBe(true);
      expect(isGoogleMapsUrl("https://maps.google.com/?q=37.7749,-122.4194")).toBe(true);
      expect(isGoogleMapsUrl("https://goo.gl/maps/abc123xyz")).toBe(true);
      expect(isGoogleMapsUrl("https://maps.app.goo.gl/shortlink")).toBe(true);
      expect(isGoogleMapsUrl("Check this: https://www.google.com/maps/@12,34,5z")).toBe(true);
      expect(isGoogleMapsUrl("Eiffel Tower, Paris")).toBe(false);
      expect(isGoogleMapsUrl("https://bing.com/maps")).toBe(false);
      expect(isGoogleMapsUrl("")).toBe(false);
    });

    it("parses user-provided M'Zab Google Maps URL with pin data parameters (!3d and !4d)", () => {
      const url =
        "https://www.google.com/maps/place/M'Zab/@32.4756753,3.7051475,5338m/data=!3m1!1e3!4m6!3m5!1s0x12642629edfa882d:0x21a37c0afb90d5fb!8m2!3d32.4727002!4d3.7082024!16s%2Fg%2F11ckr9rrns?entry=ttu&g_ep=EgoyMDI2MTEwMS4wIKXMDSoASAFQAw%3D%3D";
      const result = parseGoogleMapsUrl(url);

      expect(result).not.toBeNull();
      // Should prioritize exact pin coordinates from !3d and !4d over viewport @ coords
      expect(result?.lat).toBeCloseTo(32.4727002, 6);
      expect(result?.lng).toBeCloseTo(3.7082024, 6);
      expect(result?.placeName).toBe("M'Zab");
    });

    it("parses viewport center coordinates (@lat,lng)", () => {
      const url = "https://www.google.com/maps/@37.774929,-122.419416,15z";
      const result = parseGoogleMapsUrl(url);

      expect(result).not.toBeNull();
      expect(result?.lat).toBeCloseTo(37.774929, 6);
      expect(result?.lng).toBeCloseTo(-122.419416, 6);
    });

    it("parses query parameters (?q=lat,lng, ?ll=lat,lng, loc:lat,lng)", () => {
      const url1 = "https://maps.google.com/?q=48.8584,2.2945";
      const res1 = parseGoogleMapsUrl(url1);
      expect(res1?.lat).toBeCloseTo(48.8584, 4);
      expect(res1?.lng).toBeCloseTo(2.2945, 4);

      const url2 = "https://maps.google.com/?q=loc:51.5074,-0.1278";
      const res2 = parseGoogleMapsUrl(url2);
      expect(res2?.lat).toBeCloseTo(51.5074, 4);
      expect(res2?.lng).toBeCloseTo(-0.1278, 4);

      const url3 = "https://www.google.com/maps?daddr=40.7128,-74.0060";
      const res3 = parseGoogleMapsUrl(url3);
      expect(res3?.lat).toBeCloseTo(40.7128, 4);
      expect(res3?.lng).toBeCloseTo(-74.0060, 4);
    });

    it("parses direct coordinates in place and search paths", () => {
      const url1 = "https://www.google.com/maps/place/35.6762,139.6503";
      const res1 = parseGoogleMapsUrl(url1);
      expect(res1?.lat).toBeCloseTo(35.6762, 4);
      expect(res1?.lng).toBeCloseTo(139.6503, 4);

      const url2 = "https://www.google.com/maps/search/-33.8688,+151.2093";
      const res2 = parseGoogleMapsUrl(url2);
      expect(res2?.lat).toBeCloseTo(-33.8688, 4);
      expect(res2?.lng).toBeCloseTo(151.2093, 4);
    });

    it("parses directions URL destinations", () => {
      const url = "https://www.google.com/maps/dir/Current+Location/34.0522,-118.2437";
      const result = parseGoogleMapsUrl(url);
      expect(result?.lat).toBeCloseTo(34.0522, 4);
      expect(result?.lng).toBeCloseTo(-118.2437, 4);
    });

    it("parses embed map URLs (!2d<lng>!3d<lat>)", () => {
      const url =
        "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3153.0!2d-122.4194!3d37.7749!2m3";
      const result = parseGoogleMapsUrl(url);
      expect(result?.lat).toBeCloseTo(37.7749, 4);
      expect(result?.lng).toBeCloseTo(-122.4194, 4);
    });

    it("extracts coordinates when URL is surrounded by conversational text", () => {
      const text =
        "Check this scenic location: https://www.google.com/maps/place/Overlook/@45.1234,-110.5678,12z let me know!";
      const result = parseGoogleMapsUrl(text);
      expect(result?.lat).toBeCloseTo(45.1234, 4);
      expect(result?.lng).toBeCloseTo(-110.5678, 4);
      expect(result?.placeName).toBe("Overlook");
    });

    it("returns place name with NaN coords if URL has place name but no coordinates", () => {
      const url = "https://www.google.com/maps/place/Yellowstone+National+Park";
      const result = parseGoogleMapsUrl(url);
      expect(result).not.toBeNull();
      expect(result?.placeName).toBe("Yellowstone National Park");
      expect(isNaN(result?.lat as number)).toBe(true);
    });

    it("returns null for non-Google Maps text", () => {
      expect(parseGoogleMapsUrl("Grand Canyon South Rim")).toBeNull();
      expect(parseGoogleMapsUrl("https://example.com/place/123")).toBeNull();
    });
  });

  describe("GeoHack URL Coordinate Parser", () => {
    it("detects GeoHack URLs with isGeohackUrl", () => {
      expect(
        isGeohackUrl(
          "https://geohack.toolforge.org/geohack.php?pagename=Shibaozhai&params=30.42187999_N_108.18389_E"
        )
      ).toBe(true);
      expect(isGeohackUrl("https://en.wikipedia.org/wiki/Shibaozhai")).toBe(false);
      expect(isGeohackUrl("")).toBe(false);
    });

    it("parses user-provided Shibaozhai GeoHack URL with decimal params and pagename", () => {
      const url =
        "https://geohack.toolforge.org/geohack.php?pagename=Shibaozhai&params=30.42187999245106_N_108.18389453817412_E_region:CN-CQ_type:landmark_source:GoogleMaps";
      const result = parseGeohackUrl(url);

      expect(result).not.toBeNull();
      expect(result?.lat).toBeCloseTo(30.42187999, 6);
      expect(result?.lng).toBeCloseTo(108.1838945, 6);
      expect(result?.placeName).toBe("Shibaozhai");
    });

    it("parses DMS GeoHack parameters (deg_min_sec_N_deg_min_sec_W)", () => {
      const url =
        "https://geohack.toolforge.org/geohack.php?pagename=Big_Ben&params=51_30_02_N_0_07_29_W_type:landmark";
      const result = parseGeohackUrl(url);

      expect(result).not.toBeNull();
      expect(result?.lat).toBeCloseTo(51.500555, 4);
      expect(result?.lng).toBeCloseTo(-0.124722, 4);
      expect(result?.placeName).toBe("Big Ben");
    });

    it("parses deg_min GeoHack parameters (30_25.5_N_108_11.5_E)", () => {
      const url =
        "https://geohack.toolforge.org/geohack.php?params=30_25.5_N_108_11.5_E";
      const result = parseGeohackUrl(url);

      expect(result).not.toBeNull();
      expect(result?.lat).toBeCloseTo(30.425, 3);
      expect(result?.lng).toBeCloseTo(108.191666, 3);
    });

    it("parses semicolon-delimited decimal params (40.7128;-74.0060)", () => {
      const url = "https://geohack.toolforge.org/geohack.php?params=40.7128;-74.0060";
      const result = parseGeohackUrl(url);

      expect(result).not.toBeNull();
      expect(result?.lat).toBeCloseTo(40.7128, 4);
      expect(result?.lng).toBeCloseTo(-74.006, 4);
    });
  });

  describe("Webpage URL Detector (isWebpageUrl)", () => {
    it("identifies valid HTTP/HTTPS and www URLs", () => {
      expect(isWebpageUrl("https://en.wikipedia.org/wiki/Shibaozhai")).toBe(true);
      expect(
        isWebpageUrl(
          "https://www.tripadvisor.com/Attraction_Review-g1487177-d552670-Reviews-Shi_Bao_Zhai-Zhong_County.html"
        )
      ).toBe(true);
      expect(isWebpageUrl("http://example.com/place")).toBe(true);
      expect(isWebpageUrl("www.nps.gov/yell")).toBe(true);
      expect(isWebpageUrl("Shibaozhai Temple")).toBe(false);
      expect(isWebpageUrl("Denver, CO")).toBe(false);
      expect(isWebpageUrl("")).toBe(false);
    });
  });
});
