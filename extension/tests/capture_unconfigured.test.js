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

describe("Extension Capture Unconfigured Travel Style Non-Blocking Behavior (T-045 / REQ-CTX-013)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="content">
        <h1>Grand Canyon National Park</h1>
        <p>Iconic layered red rock formations and scenic vistas in northern Arizona.</p>
      </div>
    `;

    globalThis.chrome = {
      runtime: {
        getURL: (p) => `chrome-extension://test-id/${p}`,
        sendMessage: vi.fn(async (msg) => {
          if (msg.action === "EXTRACT_AND_CHECK") {
            // Unconfigured travel style: candidate extracted with standard base prompts
            return {
              candidate: {
                name: "Grand Canyon National Park",
                description:
                  "Vast national park famous for layered bands of red rock revealing millions of years of geological history.",
                reason_to_visit:
                  "Visitors are drawn to Grand Canyon for its breathtaking panoramic overlooks, hiking trails, and awe-inspiring scale.",
                addresses: [
                  {
                    street: "South Rim",
                    city: "Grand Canyon Village",
                    state: "AZ",
                    country: "United States",
                    postal_code: "86023",
                  },
                ],
                latitude: 36.0544,
                longitude: -112.1401,
                official_website_url: "https://nps.gov/grca",
                wikipedia_url:
                  "https://en.wikipedia.org/wiki/Grand_Canyon_National_Park",
                hero_image_url: null,
                estimated_duration_hours: 12.0,
                estimated_duration_days: 1,
                rating: null,
                source_type: "Web",
                source_value: "https://nps.gov/grca",
                extracted_tags: ["nature", "scenic", "national-park"],
              },
              verdict: {
                match_type: "UNIQUE_LOCATION",
                similarity_score: 0.0,
                distance_meters: 999999.0,
              },
            };
          }
          if (msg.action === "GET_AUTH_STATUS") {
            return {
              isAuthenticated: true,
              user: {
                id: "11111111-1111-1111-1111-111111111111",
                email: "unconfigured@example.com",
                travel_style_description: null, // Unconfigured travel style
              },
            };
          }
          if (msg.action === "GET_USER_TAGS") {
            return { tags: [] };
          }
          return {};
        }),
      },
    };
  });

  it("does not render onboarding modal or block capture when travel style is unconfigured (REQ-CTX-013)", async () => {
    openCaptureOverlay({
      name: "Grand Canyon National Park",
      description: "Iconic layered red rock canyon.",
      url: "https://nps.gov/grca",
    });

    const root = document.querySelector("vistarae-capture-root");
    expect(root).not.toBeNull();
    const shadow = root.shadowRoot;
    expect(shadow).not.toBeNull();

    // Verify host document has no onboarding popup or modal
    expect(document.querySelector(".vistarae-onboarding-modal")).toBeNull();
    expect(
      document.querySelector("[data-testid='travel-style-onboarding-modal']"),
    ).toBeNull();

    // Verify shadow DOM has no modal blocking capture
    expect(shadow.querySelector(".vistarae-onboarding-modal")).toBeNull();

    // Verify capture overlay container is rendered and active
    const modalContainer = shadow.querySelector(".vistarae-modal-container");
    expect(modalContainer).not.toBeNull();

    // Wait for async extraction and enrichment
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify fields populated with base prompts
    const nameInput = shadow.querySelector("#vistarae-name-input");
    const descInput = shadow.querySelector("#vistarae-desc-input");
    const reasonInput = shadow.querySelector("#vistarae-reason-input");

    expect(nameInput.value).toBe("Grand Canyon National Park");
    expect(descInput.value).toContain(
      "Vast national park famous for layered bands",
    );
    expect(reasonInput.value).toContain("Visitors are drawn to Grand Canyon");

    // Save button remains interactive and non-blocked
    const saveBtn = shadow.querySelector("#vistarae-save-btn");
    expect(saveBtn).not.toBeNull();
    expect(saveBtn.disabled).toBe(false);
  });
});
