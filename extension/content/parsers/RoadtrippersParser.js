// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { BasePoiParser, registerParser } from "./BasePoiParser.js";

export class RoadtrippersParser extends BasePoiParser {
  constructor() {
    super("RoadtrippersParser");
  }

  canParse(url, document) {
    if (!url) return false;
    return url.includes("roadtrippers.com");
  }

  parse(document, selectionText = "", url = "") {
    const effectiveUrl = url || document.location?.href || "";

    // 1. Title extraction
    const titleEl =
      document.querySelector("h1.place-title") ||
      document.querySelector("h1.waypoint-title") ||
      document.querySelector("h1");
    const name = titleEl ? titleEl.textContent.trim() : "Roadtrippers Waypoint";

    // 2. Category / Tags
    const tagElements = document.querySelectorAll(
      ".category-badge, .place-category, .tag-pill",
    );
    const tags = Array.from(tagElements)
      .map((el) => el.textContent.trim())
      .filter(Boolean);
    const category = tags[0] || "scenic_drive";

    // 3. Address extraction
    const addressEl =
      document.querySelector(".place-address") ||
      document.querySelector('[data-testid="address"]') ||
      document.querySelector(".address");
    const address = addressEl ? addressEl.textContent.trim() : "";

    // 4. Embedded coordinates extraction
    let latitude = null;
    let longitude = null;
    const markerEl = document.querySelector("[data-lat][data-lng]");
    if (markerEl) {
      latitude = parseFloat(markerEl.getAttribute("data-lat") || "0") || null;
      longitude = parseFloat(markerEl.getAttribute("data-lng") || "0") || null;
    } else {
      // Check window.__INITIAL_STATE__ or meta geo tags
      const metaLat = document.querySelector(
        'meta[property="place:location:latitude"]',
      );
      const metaLng = document.querySelector(
        'meta[property="place:location:longitude"]',
      );
      if (metaLat && metaLng) {
        latitude = parseFloat(metaLat.getAttribute("content") || "0") || null;
        longitude = parseFloat(metaLng.getAttribute("content") || "0") || null;
      }
    }

    // 5. Description
    const descEl =
      document.querySelector(".place-description") ||
      document.querySelector(".description-text");
    const description =
      selectionText.trim() ||
      (descEl
        ? descEl.textContent.trim()
        : `Captured from Roadtrippers: ${name}`);

    return {
      name,
      description,
      category,
      address,
      latitude,
      longitude,
      source_url: effectiveUrl,
      tags: [
        "roadtrippers",
        ...tags.map((t) => t.toLowerCase().replace(/\s+/g, "-")),
      ],
    };
  }
}

// Auto-register instance
registerParser(new RoadtrippersParser());
