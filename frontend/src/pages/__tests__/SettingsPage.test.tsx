// @vitest-environment jsdom
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

import { vi } from "vitest";

vi.mock("maplibre-gl", () => ({
  default: {
    Map: vi.fn(() => ({
      on: vi.fn(),
      remove: vi.fn(),
      addControl: vi.fn(),
    })),
    NavigationControl: vi.fn(),
  },
}));

import "@testing-library/jest-dom/vitest";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SettingsPage, normalizeScrapingDomain } from "../SettingsPage";

const mockUpdateScrapingDomains = vi.fn();
const mockShowToast = vi.fn();

vi.mock("../../context/PreferencesContext", () => ({
  usePreferences: () => ({
    ui: {
      theme: "light",
      landing_page: "pois",
      default_view_mode: "table",
      compact_mode: false,
      font_size: "medium",
      sidebar_collapsed: false,
      email_notifications: true,
      push_notifications: false,
      sound_effects: false,
    },
    poi: {
      default_sort: "name_asc",
      cluster_radius: 50,
      map_language: "local",
      pin_color_presets: {},
    },
    planner: {
      pacing_mode: "BALANCED",
      meal_interval_hours: 4.0,
      daily_start_time: "09:00",
      daily_end_time: "19:00",
      default_currency: "USD",
    },
    validScrapingDomains: ["wikipedia.org", "tripadvisor.com"],
    updateUI: vi.fn(),
    updatePOI: vi.fn(),
    updatePlanner: vi.fn(),
    updateScrapingDomains: mockUpdateScrapingDomains,
  }),
}));

vi.mock("../../context/ToastContext", () => ({
  useToast: () => ({
    showToast: mockShowToast,
  }),
}));

describe("normalizeScrapingDomain helper", () => {
  it("trims leading https://, www., and trailing slash", () => {
    expect(normalizeScrapingDomain("https://www.hillmanwonders.com/")).toBe(
      "hillmanwonders.com"
    );
  });

  it("trims leading http:// and multiple trailing slashes", () => {
    expect(normalizeScrapingDomain("http://en.wikipedia.org///")).toBe(
      "en.wikipedia.org"
    );
  });

  it("decodes URL encoding such as %20", () => {
    expect(normalizeScrapingDomain("https://example.com/top%20attractions/")).toBe(
      "example.com/top attractions"
    );
  });

  it("handles protocol-relative URLs and www.", () => {
    expect(normalizeScrapingDomain("//www.atlasobscura.com/places/")).toBe(
      "atlasobscura.com/places"
    );
  });

  it("handles empty or whitespace strings", () => {
    expect(normalizeScrapingDomain("")).toBe("");
    expect(normalizeScrapingDomain("   ")).toBe("");
  });
});

describe("SettingsPage Scraping Sources tab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes input when adding a new domain with protocol, www, and trailing slash", () => {
    render(<SettingsPage initialTab="scraping" />);

    const input = screen.getByPlaceholderText("e.g. timeout.com");
    const addButton = screen.getByRole("button", { name: /Add Domain/i });

    fireEvent.change(input, {
      target: { value: "https://www.hillmanwonders.com/" },
    });
    fireEvent.click(addButton);

    // Should display normalized domain "hillmanwonders.com"
    expect(screen.getByText("hillmanwonders.com")).toBeInTheDocument();
  });

  it("decodes %20 into a space when adding a domain", () => {
    render(<SettingsPage initialTab="scraping" />);

    const input = screen.getByPlaceholderText("e.g. timeout.com");
    const addButton = screen.getByRole("button", { name: /Add Domain/i });

    fireEvent.change(input, {
      target: { value: "https://example.com/cool%20spots/" },
    });
    fireEvent.click(addButton);

    expect(screen.getByText("example.com/cool spots")).toBeInTheDocument();
  });

  it("shows a warning toast when clicking Add Domain with an empty input", () => {
    render(<SettingsPage initialTab="scraping" />);

    const addButton = screen.getByRole("button", { name: /Add Domain/i });
    fireEvent.click(addButton);

    expect(mockShowToast).toHaveBeenCalledWith(
      "Please enter a domain before adding",
      "warning"
    );
  });
});
