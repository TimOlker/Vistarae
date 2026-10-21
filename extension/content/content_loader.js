// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

/**
 * Manifest V3 dynamic loader for ES Module content scripts.
 */
(async () => {
  try {
    const src = chrome.runtime.getURL("content/content_script.js");
    await import(src);
  } catch (err) {
    console.error("Vistarae: Failed to dynamically load content script:", err);
  }
})();
