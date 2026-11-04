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

import { describe, it, expect } from "vitest";
import { inferWebsiteName, isMapServiceWebsite } from "../../utils/websiteInference";

describe("websiteInference", () => {
  it("resolves known domains to human-readable names", () => {
    expect(inferWebsiteName("https://en.wikipedia.org/wiki/Roman_baths")).toBe("Wikipedia");
    expect(inferWebsiteName("https://www.wikidata.org/wiki/Q12345")).toBe("Wikidata");
    expect(inferWebsiteName("https://www.atlasobscura.com/places/beaser-garden-maze")).toBe("Atlas Obscura");
    expect(inferWebsiteName("https://www.tripadvisor.com/Attraction_Review-d123")).toBe("Tripadvisor");
    expect(inferWebsiteName("https://museum.wales/roman/")).toBe("National Museum Wales");
    expect(inferWebsiteName("https://cadw.gov.wales/days-out/location/caerleon")).toBe("Cadw");
    expect(inferWebsiteName("https://www.nationaltrust.org.uk/visit/wales")).toBe("National Trust");
  });

  it("handles URLs without scheme or with www", () => {
    expect(inferWebsiteName("alltrails.com/trail/us/illinois/blackwell")).toBe("AllTrails");
    expect(inferWebsiteName("http://roadtrippers.com/trips")).toBe("Roadtrippers");
  });

  it("heuristically infers clean brand name for unknown domains", () => {
    expect(inferWebsiteName("https://www.examplecastle.co.uk/visit")).toBe("Examplecastle");
    expect(inferWebsiteName("https://highland-adventures.com/tours")).toBe("Highland Adventures");
  });

  it("falls back to Website for invalid or empty strings", () => {
    expect(inferWebsiteName("")).toBe("Website");
    expect(inferWebsiteName("   ")).toBe("Website");
  });

  describe("isMapServiceWebsite", () => {
    it("identifies OpenStreetMap URLs and names", () => {
      expect(isMapServiceWebsite("https://www.openstreetmap.org/relation/12345")).toBe(true);
      expect(isMapServiceWebsite("https://osm.org/node/987")).toBe(true);
      expect(isMapServiceWebsite("https://example.com", "OpenStreetMap")).toBe(true);
      expect(isMapServiceWebsite("https://example.com", "OSM")).toBe(true);
    });

    it("identifies Google Maps URLs and names", () => {
      expect(isMapServiceWebsite("https://www.google.com/maps/place/Eiffel+Tower")).toBe(true);
      expect(isMapServiceWebsite("https://maps.google.com/?q=Paris")).toBe(true);
      expect(isMapServiceWebsite("https://maps.app.goo.gl/xyz123")).toBe(true);
      expect(isMapServiceWebsite("https://example.com", "Google Maps")).toBe(true);
    });

    it("identifies Bing, Apple, and other navigation services", () => {
      expect(isMapServiceWebsite("https://www.bing.com/maps?osid=1")).toBe(true);
      expect(isMapServiceWebsite("https://maps.apple.com/?address=Central+Park")).toBe(true);
      expect(isMapServiceWebsite("https://www.mapquest.com/us/ny/new-york")).toBe(true);
      expect(isMapServiceWebsite("https://www.waze.com/live-map/directions")).toBe(true);
      expect(isMapServiceWebsite("https://geohack.toolforge.org/geohack.php?params=48_51_24_N_2_21_07_E")).toBe(true);
    });

    it("returns false for non-mapping POI websites", () => {
      expect(isMapServiceWebsite("https://en.wikipedia.org/wiki/Eiffel_Tower", "Wikipedia")).toBe(false);
      expect(isMapServiceWebsite("https://www.toureiffel.paris/en", "Official Website")).toBe(false);
      expect(isMapServiceWebsite("https://www.alltrails.com/trail/france/paris", "AllTrails")).toBe(false);
      expect(isMapServiceWebsite("https://www.atlasobscura.com/places/eiffel-tower")).toBe(false);
      expect(isMapServiceWebsite(null, null)).toBe(false);
      expect(isMapServiceWebsite("", "")).toBe(false);
    });
  });
});

