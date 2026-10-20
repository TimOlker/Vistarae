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
import { openCaptureOverlay } from "../../../../extension/content/content_script.js";

describe("In-Page Shadow DOM Capture Overlay Controller", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="app">
        <h1>Grand Canyon National Park</h1>
        <p>A mile-deep chasm carved by the Colorado River.</p>
      </div>
    `;

    // @ts-ignore
    globalThis.chrome = {
      runtime: {
        getURL: (path: string) => `chrome-extension://test-id/${path}`,
        sendMessage: vi.fn(async (msg: any) => {
          if (msg.action === "EXTRACT_AND_CHECK") {
            return {
              candidate: {
                name: "Grand Canyon National Park",
                address: "Arizona, USA",
                category: "viewpoint",
              },
              deduplication: {
                status: "UNIQUE_LOCATION",
              },
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

  it("injects <vistarae-capture-root> with open Shadow DOM into document", async () => {
    await openCaptureOverlay({ text: "Grand Canyon vista" });

    const container = document.querySelector("vistarae-capture-root");
    expect(container).not.toBeNull();
    expect(container?.shadowRoot).not.toBeNull();

    // Verify modal elements inside Shadow Root
    const titleInput = container?.shadowRoot?.querySelector(
      "#vistarae-name-input",
    ) as HTMLInputElement;
    expect(titleInput).not.toBeNull();
    expect(titleInput.value).toBe("Grand Canyon National Park");
  });

  it("removes overlay on Escape key press", async () => {
    await openCaptureOverlay();
    expect(document.querySelector("vistarae-capture-root")).not.toBeNull();

    // Dispatch Escape event
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(document.querySelector("vistarae-capture-root")).toBeNull();
  });

  it("removes overlay when clicking the close button", async () => {
    await openCaptureOverlay();
    const container = document.querySelector("vistarae-capture-root");
    const closeBtn = container?.shadowRoot?.querySelector(
      "#vistarae-close-btn",
    ) as HTMLButtonElement;
    expect(closeBtn).not.toBeNull();

    closeBtn.click();
    expect(document.querySelector("vistarae-capture-root")).toBeNull();
  });
});
