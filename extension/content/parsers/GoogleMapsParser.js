// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import {
  BasePoiParser,
  registerParser,
  sanitizeDestinationTitle,
} from "./BasePoiParser.js";

export class GoogleMapsParser extends BasePoiParser {
  constructor() {
    super("GoogleMapsParser");
  }

  canParse(url, document) {
    if (!url) return false;
    return url.includes("google.com/maps") || url.includes("maps.google.com");
  }

  parse(document, selectionText = "", url = "") {
    const effectiveUrl = url || document.location?.href || "";

    // 1. Title extraction with robust fallback and branding sanitization
    const titleEl =
      document.querySelector("h1.DUwDvf") ||
      document.querySelector("h1.fontHeadlineLarge") ||
      document.querySelector("div.x3AX1-LfntMc-header-title-title") ||
      document.querySelector("h1");
    const rawName = titleEl
      ? titleEl.textContent.trim()
      : document.title || "Google Maps POI";
    const name =
      sanitizeDestinationTitle(rawName, "google_maps") || "Google Maps POI";

    // 2. Category extraction
    const catEl =
      document.querySelector('button[jsaction*="category"]') ||
      document.querySelector(".DkEaL") ||
      document.querySelector("button.DkEaL");
    const category = catEl ? catEl.textContent.trim() : "landmark";

    // 3. Address extraction and leading icon glyph stripping (🖈, 📍)
    const addressEl =
      document.querySelector('button[data-item-id*="address"]') ||
      document.querySelector('button[aria-label*="Address:"]') ||
      document.querySelector(".Io6YTe.fontBodyMedium");
    const rawAddress = addressEl ? addressEl.textContent.trim() : "";
    const address = rawAddress
      .replace(/^[\s\W\uD800-\uDFFF\u2000-\u2BFF\u2600-\u27FF]+/u, "")
      .trim();

    // 4. Coordinates extraction from URL (e.g., @37.7303,-119.5736,15z)
    let latitude = null;
    let longitude = null;
    const coordMatch = effectiveUrl.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
    if (coordMatch) {
      latitude = parseFloat(coordMatch[1]);
      longitude = parseFloat(coordMatch[2]);
    }

    // 5. Rating extraction (e.g., "4.8 stars 1,234 reviews")
    let rating = null;
    const ratingEl =
      document.querySelector('span[aria-label*="stars"]') ||
      document.querySelector("div.fontDisplayLarge");
    if (ratingEl) {
      const ratingText =
        ratingEl.getAttribute("aria-label") || ratingEl.textContent || "";
      const rMatch = ratingText.match(/(\d+(\.\d+)?)/);
      if (rMatch) {
        rating = Math.min(5, Math.max(1, Math.round(parseFloat(rMatch[1]))));
      }
    }

    // 6. Photo extraction
    const photoUrls = [];
    const imgEl =
      document.querySelector('button[jsaction*="pane.heroHeaderImage"] img') ||
      document.querySelector('img[decoding="async"]');
    if (imgEl && imgEl.src) {
      photoUrls.push(imgEl.src);
    }

    return {
      name,
      description: selectionText.trim() || `Captured from Google Maps: ${name}`,
      category,
      address,
      raw_address: rawAddress,
      latitude,
      longitude,
      hero_image_url: photoUrls[0] || null,
      rating,
      source_url: effectiveUrl,
      photo_urls: photoUrls,
      tags: ["google-maps", category.toLowerCase().replace(/\s+/g, "-")],
    };
  }
}

// Auto-register instance
registerParser(new GoogleMapsParser());
