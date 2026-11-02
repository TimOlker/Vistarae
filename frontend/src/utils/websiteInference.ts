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

/**
 * Frequently used travel & POI website domains and mappings to human-readable site names.
 */
export const KNOWN_DOMAIN_NAMES: Record<string, string> = {
  "wikipedia.org": "Wikipedia",
  "wikidata.org": "Wikidata",
  "atlasobscura.com": "Atlas Obscura",
  "tripadvisor.com": "Tripadvisor",
  "tripadvisor.co.uk": "Tripadvisor",
  "tripadvisor.ca": "Tripadvisor",
  "roadtrippers.com": "Roadtrippers",
  "alltrails.com": "AllTrails",
  "nationaltrust.org.uk": "National Trust",
  "english-heritage.org.uk": "English Heritage",
  "historicenvironment.scot": "Historic Environment Scotland",
  "cadw.gov.wales": "Cadw",
  "nps.gov": "National Park Service",
  "unesco.org": "UNESCO World Heritage",
  "whc.unesco.org": "UNESCO World Heritage",
  "visitwales.com": "Visit Wales",
  "visitscotland.com": "Visit Scotland",
  "visitengland.com": "Visit England",
  "museum.wales": "National Museum Wales",
  "lonelyplanet.com": "Lonely Planet",
  "foursquare.com": "Foursquare",
  "yelp.com": "Yelp",
  "google.com": "Google Maps",
  "maps.google.com": "Google Maps",
  "openstreetmap.org": "OpenStreetMap",
  "artsandculture.google.com": "Google Arts & Culture",
  "nationalparks.org": "National Parks",
  "britannica.com": "Encyclopedia Britannica",
  "timeout.com": "Time Out",
  "theguardian.com": "The Guardian Travel",
};

/**
 * Determines a readable Site Name from a URL using known domains and heuristic parsing.
 *
 * @param url The website URL string.
 * @returns Human-readable site name (e.g. "Atlas Obscura", "Tripadvisor", "Caerleon Museum").
 */
export function inferWebsiteName(url: string): string {
  if (!url || !url.trim()) return "Website";
  try {
    const trimmed = url.trim();
    const withScheme =
      trimmed.startsWith("http://") || trimmed.startsWith("https://")
        ? trimmed
        : `https://${trimmed}`;
    const parsed = new URL(withScheme);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");

    // 1. Direct or suffix match in KNOWN_DOMAIN_NAMES
    for (const [dom, name] of Object.entries(KNOWN_DOMAIN_NAMES)) {
      if (host === dom || host.endsWith(`.${dom}`)) {
        return name;
      }
    }

    // 2. Generic heuristic: strip multi-part TLDs and extract brand segment
    const commonTlds = new Set([
      "com",
      "org",
      "net",
      "gov",
      "edu",
      "io",
      "co",
      "uk",
      "wales",
      "scot",
      "us",
      "ca",
      "au",
      "de",
      "fr",
      "es",
      "it",
      "jp",
      "travel",
      "info",
    ]);

    const parts = host.split(".").filter((p) => p.length > 0 && !commonTlds.has(p));
    const brandPart = parts.length > 0 ? parts[parts.length - 1] : host;

    // Convert hyphenated / snake_case names to Title Case words
    const words = brandPart
      .replace(/[-_]/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);

    if (words.length > 0) {
      return words
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(" ");
    }

    return host;
  } catch {
    return "Website";
  }
}

