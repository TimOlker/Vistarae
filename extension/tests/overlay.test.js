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

describe("Extension Capture Overlay Field Parity & Synchronization (REQ-EXT-010, REQ-EXT-014, REQ-EXT-015, REQ-EXT-016, REQ-EXT-029)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="content">
        <h1>Bamburgh Castle</h1>
        <p>A spectacular fortress on the Northumberland coast.</p>
      </div>
    `;

    globalThis.chrome = {
      runtime: {
        getURL: (p) => `chrome-extension://test-id/${p}`,
        sendMessage: vi.fn(async (msg) => {
          if (msg.action === "EXTRACT_AND_CHECK") {
            return {
              candidate: {
                name: "Bamburgh Castle",
                description:
                  "Historic Norman fortress standing atop a basalt crag.",
                addresses: [
                  {
                    street: "Bamburgh Castle",
                    city: "Bamburgh",
                    state: "Northumberland",
                    country: "United Kingdom",
                    postal_code: "NE69 7DF",
                  },
                ],
                latitude: 55.6089,
                longitude: -1.7099,
                official_website_url: "https://www.bamburghcastle.com",
                wikipedia_url: "https://en.wikipedia.org/wiki/Bamburgh_Castle",
                hero_image_url: "https://upload.wikimedia.org/bamburgh.jpg",
                estimated_duration_hours: 3.5,
                estimated_duration_days: 0,
                rating: null,
                source_type: "Web",
                source_value: "https://en.wikipedia.org/wiki/Bamburgh_Castle",
                extraction_sources: ["wikipedia.org"],
              },
              recommended_tags: ["fortification", "historic"],
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
          if (msg.action === "SAVE_POI") {
            return { success: true };
          }
          return {};
        }),
      },
    };
  });

  it("renders 1:1 field parity with POI Editor (REQ-EXT-014)", async () => {
    await openCaptureOverlay();
    const container = document.querySelector("vistarae-capture-root");
    const shadow = container?.shadowRoot;

    expect(shadow).not.toBeNull();
    // 1. Name
    expect(shadow.querySelector("#vistarae-name-input")).not.toBeNull();
    // 2. Description
    expect(shadow.querySelector("#vistarae-desc-input")).not.toBeNull();
    // 3. Addresses
    expect(
      shadow.querySelector("#vistarae-addresses-container"),
    ).not.toBeNull();
    // 4. Coordinates
    expect(shadow.querySelector("#vistarae-lat-input")).not.toBeNull();
    expect(shadow.querySelector("#vistarae-lng-input")).not.toBeNull();
    // 5. Official Website URL
    expect(shadow.querySelector("#vistarae-official-url-input")).not.toBeNull();
    // 6. Wikipedia URL
    expect(
      shadow.querySelector("#vistarae-wikipedia-url-input"),
    ).not.toBeNull();
    // 7. Hero Image URL
    expect(shadow.querySelector("#vistarae-hero-image-input")).not.toBeNull();
    // 8. Duration Hours & Days
    expect(
      shadow.querySelector("#vistarae-duration-hours-input"),
    ).not.toBeNull();
    expect(
      shadow.querySelector("#vistarae-duration-days-input"),
    ).not.toBeNull();
    // 9. Parent POI
    expect(shadow.querySelector("#vistarae-parent-container")).not.toBeNull();
    // 10. Vetted Tags
    expect(shadow.querySelector("#vistarae-tags-container")).not.toBeNull();
  });

  it("omits local photo folder fields during web capture (REQ-EXT-015)", async () => {
    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;

    expect(shadow.querySelector("#vistarae-photo-folders-input")).toBeNull();
    expect(shadow.querySelector(".photo-folder-picker")).toBeNull();
  });

  it("leaves star rating unassigned (null/0) by default until traveler explicitly rates (REQ-EXT-016)", async () => {
    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;

    const ratingInput = shadow.querySelector("#vistarae-rating-input");
    // Rating should be null, empty string, or 0
    expect(ratingInput ? ratingInput.value : null).toBeFalsy();
  });

  it("displays authenticated user email and status badge in overlay header (REQ-EXT-010)", async () => {
    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;

    // Fast-forward microtasks for GET_AUTH_STATUS
    await new Promise((r) => setTimeout(r, 10));

    const userEmail = shadow.querySelector("#vistarae-user-email");
    expect(userEmail).not.toBeNull();
  });

  it("renders recommended vetted tag toggle pills (REQ-EXT-029)", async () => {
    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;

    // Fast-forward microtasks for EXTRACT_AND_CHECK
    await new Promise((r) => setTimeout(r, 20));

    const tagContainer = shadow.querySelector("#vistarae-tags-container");
    expect(tagContainer).not.toBeNull();
  });

  it("renders 3-way triage prompt and persists parent POI on Make Child selection (REQ-EXT-032, T-036)", async () => {
    // Override EXTRACT_AND_CHECK to return NEARBY_PARENT
    globalThis.chrome.runtime.sendMessage = vi.fn(async (msg) => {
      if (msg.action === "EXTRACT_AND_CHECK") {
        return {
          candidate: {
            name: "Cloud Gate",
            description: "Outdoor sculpture in Millennium Park.",
            latitude: 41.8827,
            longitude: -87.6233,
          },
          recommended_tags: ["sculpture"],
          deduplication: {
            status: "NEARBY_PARENT",
            distance_meters: 25.0,
            similarity_score: 0.12,
            existing_poi_id: "00000000-0000-0000-0000-000000000001",
            existing_poi_name: "Millennium Park",
            scale_classification: "macro",
            recommended_action: "make_child",
          },
        };
      }
      if (msg.action === "GET_AUTH_STATUS") {
        return { isAuthenticated: true, email: "traveler@vistarae.com" };
      }
      return {};
    });

    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;
    await new Promise((r) => setTimeout(r, 20));

    // Verify all 3 action buttons exist
    const makeChildBtn = shadow.querySelector("#vistarae-triage-make-child");
    const proceedBtn = shadow.querySelector("#vistarae-triage-proceed");
    const abortBtn = shadow.querySelector("#vistarae-triage-abort");

    expect(makeChildBtn).not.toBeNull();
    expect(proceedBtn).not.toBeNull();
    expect(abortBtn).not.toBeNull();

    // Click Make Child
    makeChildBtn.click();

    // Verify parent POI values are populated
    const parentIdInput = shadow.querySelector("#vistarae-parent-id");
    const parentNameInput = shadow.querySelector("#vistarae-parent-name");
    expect(parentIdInput.value).toBe("00000000-0000-0000-0000-000000000001");
    expect(parentNameInput.value).toBe("Millennium Park");
  });

  it("renders Leaflet mini-map container and reselect location button (REQ-FR-011, REQ-FR-012)", async () => {
    // Provide a mocked L global on window
    const mockMap = {
      setView: vi.fn(),
      on: vi.fn(),
      invalidateSize: vi.fn(),
    };
    const mockMarker = {
      setLatLng: vi.fn(),
      on: vi.fn(),
      dragging: { enable: vi.fn(), disable: vi.fn() },
    };
    globalThis.L = {
      map: vi.fn(() => mockMap),
      tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
      divIcon: vi.fn(() => ({})),
      marker: vi.fn(() => ({ addTo: vi.fn(() => mockMarker) })),
    };

    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;
    await new Promise((r) => setTimeout(r, 20));

    const minimap = shadow.querySelector("#vistarae-minimap");
    const reselectBtn = shadow.querySelector("#vistarae-reselect-map-btn");
    expect(minimap).not.toBeNull();
    expect(reselectBtn).not.toBeNull();
    expect(reselectBtn.textContent).toContain("Reselect Location");

    // Click Reselect Location to toggle mode
    reselectBtn.click();
    expect(reselectBtn.textContent).toContain("Done Reselecting");
    expect(reselectBtn.classList.contains("active")).toBe(true);

    // Toggle back
    reselectBtn.click();
    expect(reselectBtn.textContent).toContain("Reselect Location");
    expect(reselectBtn.classList.contains("active")).toBe(false);
  });

  it("renders View buttons next to URL inputs and opens new tab on click (REQ-FR-004, REQ-FR-005, REQ-FR-006)", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;
    await new Promise((r) => setTimeout(r, 20));

    const officialBtn = shadow.querySelector("#vistarae-view-official-btn");
    const wikiBtn = shadow.querySelector("#vistarae-view-wiki-btn");

    expect(officialBtn).not.toBeNull();
    expect(wikiBtn).not.toBeNull();

    // Candidate payload has both URLs, so buttons should be enabled
    expect(officialBtn.disabled).toBe(false);
    expect(wikiBtn.disabled).toBe(false);

    // Click View for Official Website
    officialBtn.click();
    expect(openSpy).toHaveBeenCalledWith(
      "https://www.bamburghcastle.com",
      "_blank",
      "noopener,noreferrer",
    );

    // Click View for Wikipedia
    wikiBtn.click();
    expect(openSpy).toHaveBeenCalledWith(
      "https://en.wikipedia.org/wiki/Bamburgh_Castle",
      "_blank",
      "noopener,noreferrer",
    );

    openSpy.mockRestore();
  });

  it("renders Hero Image preview card and probes image load (REQ-FR-007, REQ-FR-008, REQ-FR-009, REQ-FR-010)", async () => {
    await openCaptureOverlay();
    const shadow = document.querySelector("vistarae-capture-root")?.shadowRoot;
    await new Promise((r) => setTimeout(r, 20));

    const heroCard = shadow.querySelector("#vistarae-hero-preview-card");
    const reloadBtn = shadow.querySelector("#vistarae-hero-reload-btn");
    const heroInput = shadow.querySelector("#vistarae-hero-image-input");

    expect(heroCard).not.toBeNull();
    expect(reloadBtn).not.toBeNull();
    expect(heroInput.value).toBe("https://upload.wikimedia.org/bamburgh.jpg");
  });
});
