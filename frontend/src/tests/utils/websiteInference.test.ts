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
import { inferWebsiteName, KNOWN_DOMAIN_NAMES } from "../../utils/websiteInference";

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
});

