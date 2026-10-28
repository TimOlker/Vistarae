// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { BasePoiParser, registerParser } from "./BasePoiParser.js";

export class GenericSelectionParser extends BasePoiParser {
  constructor() {
    super("GenericSelectionParser");
  }

  canParse(url, document) {
    // Fallback parser accepts any URL
    return true;
  }

  parse(document, selectionText = "", url = "") {
    const effectiveUrl = url || document.location?.href || "";

    // 1. Title extraction
    const ogTitle = document
      .querySelector('meta[property="og:title"]')
      ?.getAttribute("content");
    const twitterTitle = document
      .querySelector('meta[name="twitter:title"]')
      ?.getAttribute("content");
    const h1 = document.querySelector("h1")?.textContent?.trim();
    const docTitle = document.title
      ? document.title.split(/[-|•–]/)[0].trim()
      : "Saved Travel POI";

    const name = ogTitle || twitterTitle || h1 || docTitle;

    // 2. Description extraction
    const ogDesc = document
      .querySelector('meta[property="og:description"]')
      ?.getAttribute("content");
    const metaDesc = document
      .querySelector('meta[name="description"]')
      ?.getAttribute("content");
    const description = selectionText.trim() || ogDesc || metaDesc || "";

    // 3. Photo extraction
    const ogImage = document
      .querySelector('meta[property="og:image"]')
      ?.getAttribute("content");
    const photoUrls = ogImage ? [ogImage] : [];

    return {
      name,
      description,
      category: "experience",
      address: "",
      latitude: null,
      longitude: null,
      rating: null,
      source_url: effectiveUrl,
      photo_urls: photoUrls,
      tags: ["web-capture"],
    };
  }
}

// Auto-register fallback parser (must be registered last in priority chain)
registerParser(new GenericSelectionParser());
