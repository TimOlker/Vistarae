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

import { describe, it, expect, beforeEach } from "vitest";
import fs from "fs";
import path from "path";

describe("Extension Browser Page Streamlining & Companion Hub (REQ-EXT-010 to REQ-EXT-013)", () => {
  let doc;

  beforeEach(() => {
    const htmlPath = path.resolve(__dirname, "../browser/browser.html");
    const htmlContent = fs.readFileSync(htmlPath, "utf-8");
    const parser = new DOMParser();
    doc = parser.parseFromString(htmlContent, "text/html");
  });

  it("omits CSV export button, POI table, search bar, and category filters (REQ-EXT-011)", () => {
    // Assert complete elimination of tabular UI elements
    expect(doc.getElementById("btn-export-csv")).toBeNull();
    expect(doc.getElementById("poi-tbody")).toBeNull();
    expect(doc.getElementById("poi-table")).toBeNull();
    expect(doc.getElementById("input-search")).toBeNull();
    expect(doc.getElementById("select-category")).toBeNull();
  });

  it("renders educational companion hub with purpose, shortcut instructions, and web app link (REQ-EXT-013)", () => {
    const companionHub =
      doc.querySelector(".companion-hub") ||
      doc.querySelector(".companion-card") ||
      doc.querySelector("main");
    expect(companionHub).not.toBeNull();

    // Verify keyboard shortcut instructions
    const pageText = doc.body.textContent;
    expect(pageText).toMatch(/Ctrl\s*\+\s*Shift\s*\+\s*S/i);

    // Verify navigation button to Web App
    const openWebAppBtn = doc.getElementById("btn-open-webapp");
    expect(openWebAppBtn).not.toBeNull();

    // Verify server connectivity status indicator element
    const serverStatus =
      doc.getElementById("server-status-badge") ||
      doc.getElementById("server-status");
    expect(serverStatus).not.toBeNull();
  });

  it("provides placeholders for authenticated user email and status badge (REQ-EXT-010)", () => {
    const userEmailEl = doc.getElementById("user-email");
    const userBadgeEl =
      doc.getElementById("user-status-badge") ||
      doc.getElementById("auth-status-badge");

    expect(userEmailEl).not.toBeNull();
    expect(userBadgeEl).not.toBeNull();
  });

  it("does not contain any hardcoded demo mock POIs in browser source files (REQ-EXT-012)", () => {
    const jsPath = path.resolve(__dirname, "../browser/browser.js");
    const jsContent = fs.readFileSync(jsPath, "utf-8");

    expect(jsContent).not.toContain("Glacier Point Overlook");
    expect(jsContent).not.toContain("Mist Trail to Vernal Fall");
    expect(jsContent).not.toContain("C:\\Photos\\Yosemite");
  });
});
