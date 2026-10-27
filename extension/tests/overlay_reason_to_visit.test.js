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

import { describe, it, expect, beforeEach, vi } from "vitest";
import { openCaptureOverlay } from "../content/content_script.js";

describe("Extension Capture Overlay Reason to Visit Field & Ordering (T-021 / REQ-CTX-034, SC-005)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="content">
        <h1>Pike Place Market</h1>
        <p>Historic public market in Seattle overlooking Elliott Bay.</p>
      </div>
    `;

    globalThis.chrome = {
      runtime: {
        getURL: (p) => `chrome-extension://test-id/${p}`,
        sendMessage: vi.fn(async (msg) => {
          if (msg.action === "EXTRACT_AND_CHECK") {
            return {
              candidate: {
                name: "Pike Place Market",
                description:
                  "Historic public market with artisan bakeries and seafood stalls.",
                reason_to_visit:
                  "Wander bustling market alleys to sample artisan cheeses and ciders.",
                addresses: [
                  {
                    street: "85 Pike St",
                    city: "Seattle",
                    state: "WA",
                    country: "United States",
                    postal_code: "98101",
                  },
                ],
                latitude: 47.6087,
                longitude: -122.34,
                official_website_url: "https://pikeplacemarket.org",
                wikipedia_url:
                  "https://en.wikipedia.org/wiki/Pike_Place_Market",
                hero_image_url: null,
                estimated_duration_hours: 3.0,
                estimated_duration_days: 0,
                rating: null,
                source_type: "Web",
                source_value: "https://pikeplacemarket.org",
                extraction_sources: ["pikeplacemarket.org"],
              },
              recommended_tags: ["market", "culinary"],
              deduplication: {
                status: "UNIQUE_LOCATION",
                recommended_action: "proceed",
              },
            };
          }
          if (msg.action === "GET_AUTH_STATUS") {
            return {
              isAuthenticated: true,
              email: "traveler@vistarae.com",
            };
          }
          if (msg.action === "GET_USER_TAGS") {
            return {
              tags: [
                { name: "Market", slug: "market" },
                { name: "Culinary", slug: "culinary" },
              ],
            };
          }
          if (msg.action === "SAVE_POI") {
            return { success: true, id: "poi-123" };
          }
          return {};
        }),
      },
    };
  });

  it("renders Reason to Visit multiline textarea positioned directly below Description (REQ-CTX-034)", async () => {
    await openCaptureOverlay({
      name: "Pike Place Market",
      description: "Initial description excerpt",
    });

    const root = document.querySelector("vistarae-capture-root");
    expect(root).not.toBeNull();
    const shadow = root.shadowRoot;
    expect(shadow).not.toBeNull();

    const descInput = shadow.querySelector("#vistarae-desc-input");
    const reasonInput = shadow.querySelector("#vistarae-reason-input");

    expect(descInput).not.toBeNull();
    expect(reasonInput).not.toBeNull();

    // Verify both are textareas for multiline editing
    expect(descInput.tagName.toLowerCase()).toBe("textarea");
    expect(reasonInput.tagName.toLowerCase()).toBe("textarea");

    // Verify visual ordering: Reason to Visit form group immediately follows Description form group
    const descGroup = descInput.closest(".vistarae-form-group");
    const reasonGroup = reasonInput.closest(".vistarae-form-group");

    expect(descGroup).not.toBeNull();
    expect(reasonGroup).not.toBeNull();
    expect(descGroup.nextElementSibling).toBe(reasonGroup);
  });

  it("populates Reason to Visit upon extraction and sends it in SAVE_POI payload (SC-005)", async () => {
    await openCaptureOverlay({
      name: "Pike Place Market",
      description: "Initial description excerpt",
    });

    const root = document.querySelector("vistarae-capture-root");
    const shadow = root.shadowRoot;

    // Allow background EXTRACT_AND_CHECK promise to resolve
    await vi.waitFor(() => {
      const reasonInput = shadow.querySelector("#vistarae-reason-input");
      expect(reasonInput.value).toBe(
        "Wander bustling market alleys to sample artisan cheeses and ciders.",
      );
    });

    // Edit Reason to Visit
    const reasonInput = shadow.querySelector("#vistarae-reason-input");
    reasonInput.value = "Updated traveler motivation: incredible fresh sourdough bread!";

    // Click Save to Vistarae
    const saveBtn = shadow.querySelector("#vistarae-save-btn");
    saveBtn.click();

    await vi.waitFor(() => {
      const calls = globalThis.chrome.runtime.sendMessage.mock.calls;
      const saveCall = calls.find((c) => c[0].action === "SAVE_POI");
      expect(saveCall).toBeDefined();
      expect(saveCall[0].poi.reason_to_visit).toBe(
        "Updated traveler motivation: incredible fresh sourdough bread!",
      );
      expect(saveCall[0].poi.name).toBe("Pike Place Market");
      expect(saveCall[0].poi.estimated_duration_hours).toBe(3.0);
    });
  });
});
