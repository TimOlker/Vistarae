// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { BasePoiParser, registerParser } from "./BasePoiParser.js";

export class TripAdvisorParser extends BasePoiParser {
  constructor() {
    super("TripAdvisorParser");
  }

  canParse(url, document) {
    if (!url) return false;
    return url.includes("tripadvisor.com");
  }

  parse(document, selectionText = "", url = "") {
    const effectiveUrl = url || document.location?.href || "";

    // Check JSON-LD metadata first for high-fidelity schema.org objects
    let ldData = null;
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    for (const script of scripts) {
      try {
        const parsed = JSON.parse(script.textContent || "{}");
        const types = [
          "Place",
          "TouristAttraction",
          "Restaurant",
          "LodgingBusiness",
          "LocalBusiness",
        ];
        if (types.includes(parsed["@type"])) {
          ldData = parsed;
          break;
        } else if (Array.isArray(parsed["@graph"])) {
          const match = parsed["@graph"].find((item) =>
            types.includes(item["@type"]),
          );
          if (match) {
            ldData = match;
            break;
          }
        }
      } catch (_) {
        // Ignore unparseable JSON-LD blocks
      }
    }

    // 1. Title extraction
    const titleEl =
      document.querySelector('h1[data-automation="mainH1"]') ||
      document.querySelector("h1.biGQs") ||
      document.querySelector("h1");
    const name =
      ldData?.name ||
      (titleEl ? titleEl.textContent.trim() : "TripAdvisor POI");

    // 2. Address extraction
    let address = "";
    if (ldData?.address) {
      if (typeof ldData.address === "string") {
        address = ldData.address;
      } else if (typeof ldData.address === "object") {
        const parts = [
          ldData.address.streetAddress,
          ldData.address.addressLocality,
          ldData.address.addressRegion,
          ldData.address.postalCode,
          ldData.address.addressCountry,
        ].filter(Boolean);
        address = parts.join(", ");
      }
    }
    if (!address) {
      const addrEl =
        document.querySelector('button[href*="Maps"] span') ||
        document.querySelector(".dummyAddress") ||
        document.querySelector("span.yEWoV");
      address = addrEl ? addrEl.textContent.trim() : "";
    }

    // 3. Coordinates extraction
    let latitude = ldData?.geo?.latitude
      ? parseFloat(ldData.geo.latitude)
      : null;
    let longitude = ldData?.geo?.longitude
      ? parseFloat(ldData.geo.longitude)
      : null;

    // 4. Rating extraction (bubble rating 1-5)
    let rating = null;
    if (ldData?.aggregateRating?.ratingValue) {
      rating = Math.min(
        5,
        Math.max(1, Math.round(parseFloat(ldData.aggregateRating.ratingValue))),
      );
    } else {
      const bubbleEl =
        document.querySelector('svg[aria-label*="bubbles"]') ||
        document.querySelector('span[class*="bubble_"]');
      if (bubbleEl) {
        const label =
          bubbleEl.getAttribute("aria-label") || bubbleEl.className || "";
        const match = label.match(/(\d+(\.\d+)?)/);
        if (match) {
          rating = Math.min(5, Math.max(1, Math.round(parseFloat(match[1]))));
        }
      }
    }

    // 5. Category
    let category = "attraction";
    if (ldData?.["@type"]) {
      const type = ldData["@type"].toLowerCase();
      if (type.includes("restaurant")) category = "dining";
      else if (type.includes("lodging")) category = "lodging";
    }

    return {
      name,
      description:
        selectionText.trim() ||
        ldData?.description ||
        `Captured from TripAdvisor: ${name}`,
      category,
      address,
      latitude,
      longitude,
      rating,
      source_url: effectiveUrl,
      tags: ["tripadvisor", category],
    };
  }
}

// Auto-register instance
registerParser(new TripAdvisorParser());
