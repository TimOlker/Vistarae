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

import { describe, it, expect, beforeEach } from "vitest";
import {
  BasePoiParser,
  findParserForUrl,
  parserRegistry,
} from "../../../../extension/content/parsers/BasePoiParser.js";
import { GoogleMapsParser } from "../../../../extension/content/parsers/GoogleMapsParser.js";
import { RoadtrippersParser } from "../../../../extension/content/parsers/RoadtrippersParser.js";
import { TripAdvisorParser } from "../../../../extension/content/parsers/TripAdvisorParser.js";
import { GenericSelectionParser } from "../../../../extension/content/parsers/GenericSelectionParser.js";

describe("Polymorphic Scraper Registry & Parsers", () => {
  beforeEach(() => {
    // Reset registry to clean state and re-register in standard priority order
    parserRegistry.length = 0;
    parserRegistry.push(new GoogleMapsParser());
    parserRegistry.push(new RoadtrippersParser());
    parserRegistry.push(new TripAdvisorParser());
    parserRegistry.push(new GenericSelectionParser());
  });

  it("selects GoogleMapsParser for google.com/maps URLs", () => {
    const parser = findParserForUrl(
      "https://www.google.com/maps/place/Glacier+Point/@37.7303,-119.5736,15z",
      document,
    );
    expect(parser?.name).toBe("GoogleMapsParser");
  });

  it("extracts place attributes and coordinates correctly from Google Maps DOM mock", () => {
    const parser = new GoogleMapsParser();
    const mockDoc =
      document.implementation.createHTMLDocument("Google Maps Test");
    mockDoc.body.innerHTML = `
      <h1 class="DUwDvf">Glacier Point</h1>
      <button jsaction="pane.category">Scenic Overlook</button>
      <button data-item-id="address">Glacier Point Rd, Yosemite National Park, CA 95389</button>
      <span aria-label="4.9 stars 4,521 reviews"></span>
    `;

    const url =
      "https://www.google.com/maps/place/Glacier+Point/@37.7303,-119.5736,15z";
    const result = parser.parse(mockDoc, "Breathtaking vista", url);

    expect(result.name).toBe("Glacier Point");
    expect(result.category).toBe("Scenic Overlook");
    expect(result.address).toBe(
      "Glacier Point Rd, Yosemite National Park, CA 95389",
    );
    expect(result.latitude).toBeCloseTo(37.7303, 4);
    expect(result.longitude).toBeCloseTo(-119.5736, 4);
    expect(result.rating).toBe(5);
  });

  it("selects RoadtrippersParser for roadtrippers.com URLs and parses waypoint attributes", () => {
    const parser = findParserForUrl(
      "https://maps.roadtrippers.com/trips/12345",
      document,
    );
    expect(parser?.name).toBe("RoadtrippersParser");

    const mockDoc = document.implementation.createHTMLDocument("Roadtrippers");
    mockDoc.body.innerHTML = `
      <h1 class="place-title">Half Dome Village</h1>
      <span class="category-badge">Campground</span>
      <div class="place-address">Yosemite Valley, CA</div>
      <div data-lat="37.738" data-lng="-119.572"></div>
    `;

    const result = parser!.parse(
      mockDoc,
      "",
      "https://roadtrippers.com/places/123",
    );
    expect(result.name).toBe("Half Dome Village");
    expect(result.category).toBe("Campground");
    expect(result.latitude).toBeCloseTo(37.738, 3);
    expect(result.longitude).toBeCloseTo(-119.572, 3);
  });

  it("selects TripAdvisorParser and parses JSON-LD metadata for attractions", () => {
    const parser = findParserForUrl(
      "https://www.tripadvisor.com/Attraction_Review-g61000-d144211",
      document,
    );
    expect(parser?.name).toBe("TripAdvisorParser");

    const mockDoc = document.implementation.createHTMLDocument("TripAdvisor");
    const jsonLd = {
      "@type": "TouristAttraction",
      name: "Yosemite Falls",
      description: "Iconic waterfall plunging into Yosemite Valley",
      geo: {
        latitude: "37.7566",
        longitude: "-119.5969",
      },
      address: {
        streetAddress: "Yosemite Valley",
        addressRegion: "CA",
        addressCountry: "US",
      },
      aggregateRating: {
        ratingValue: "4.8",
      },
    };

    const script = mockDoc.createElement("script");
    script.type = "application/ld+json";
    script.textContent = JSON.stringify(jsonLd);
    mockDoc.head.appendChild(script);

    const result = parser!.parse(
      mockDoc,
      "",
      "https://www.tripadvisor.com/Attraction_Review",
    );
    expect(result.name).toBe("Yosemite Falls");
    expect(result.latitude).toBeCloseTo(37.7566, 4);
    expect(result.longitude).toBeCloseTo(-119.5969, 4);
    expect(result.rating).toBe(5);
  });

  it("falls back to GenericSelectionParser for general web pages and extracts OpenGraph metadata", () => {
    const parser = findParserForUrl(
      "https://www.outdoorphotographer.com/california-overlooks",
      document,
    );
    expect(parser?.name).toBe("GenericSelectionParser");

    const mockDoc = document.implementation.createHTMLDocument(
      "Yosemite Photography Guide",
    );
    const ogTitle = mockDoc.createElement("meta");
    ogTitle.setAttribute("property", "og:title");
    ogTitle.setAttribute("content", "Top 10 Sunset Spots in Yosemite");
    mockDoc.head.appendChild(ogTitle);

    const result = parser!.parse(
      mockDoc,
      "Tunnel View provides the most cinematic framing of Half Dome and El Capitan.",
      "https://example.com/guide",
    );
    expect(result.name).toBe("Top 10 Sunset Spots in Yosemite");
    expect(result.description).toContain(
      "Tunnel View provides the most cinematic framing",
    );
    expect(result.category).toBe("experience");
  });
});
