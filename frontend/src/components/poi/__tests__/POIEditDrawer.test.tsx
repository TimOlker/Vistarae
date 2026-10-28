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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { POIEditDrawer } from "../POIEditDrawer";
import type { POIMapFeature } from "../../../types/map";

if (typeof window !== "undefined" && !window.URL.createObjectURL) {
  window.URL.createObjectURL = vi.fn().mockReturnValue("blob:mock");
}

vi.mock("maplibre-gl", () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      on: vi.fn(),
      remove: vi.fn(),
      addControl: vi.fn(),
    })),
    NavigationControl: vi.fn(),
    Marker: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
    })),
    setWorkerUrl: vi.fn(),
  },
}));

// Mock apiFetch
vi.mock("../../../services/api", () => ({
  apiFetch: vi.fn(),
  ApiError: class extends Error {
    problem: any;
    constructor(problem: any) {
      super(problem.detail || "API Error");
      this.problem = problem;
    }
  },
}));

import { apiFetch } from "../../../services/api";

describe("POIEditDrawer (T-028 / REQ-CTX-035, SC-005)", () => {
  const samplePoi: POIMapFeature = {
    id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    name: "Glacier Overlook",
    canonical_lat: 48.5,
    canonical_lng: -113.8,
    render_lat: 48.5,
    render_lng: -113.8,
    visit_state: "not_visited",
    rating: 4,
    city: "West Glacier",
    state: "Montana",
    country: "United States",
    tags: ["national park", "scenic"],
    description: "Expansive viewpoint overlooking alpine ice fields.",
    reason_to_visit: "Unmatched sunrise vantage point with panoramic views of the continental divide.",
    addresses: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (apiFetch as any).mockResolvedValue({
      ...samplePoi,
      lat: 48.5,
      lon: -113.8,
    });
  });

  it("renders Reason to Visit textarea positioned directly below Description with correct initial values", async () => {
    render(
      <POIEditDrawer
        poi={samplePoi}
        isOpen={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    );

    const descTextarea = (await screen.findByPlaceholderText(
      /Detailed visitor notes, highlights/i
    )) as HTMLTextAreaElement;
    const reasonTextarea = (await screen.findByPlaceholderText(
      /Why a tourist would be interested in visiting/i
    )) as HTMLTextAreaElement;

    expect(descTextarea).toBeDefined();
    expect(reasonTextarea).toBeDefined();

    // Verify DOM ordering: reasonTextarea must appear after descTextarea
    const position = descTextarea.compareDocumentPosition(reasonTextarea);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Verify initial values
    expect(descTextarea.value).toBe("Expansive viewpoint overlooking alpine ice fields.");
    expect(reasonTextarea.value).toBe(
      "Unmatched sunrise vantage point with panoramic views of the continental divide."
    );
  });

  it("submits updated reason_to_visit on save", async () => {
    const onSaveMock = vi.fn();
    (apiFetch as any).mockImplementation((url: string, opts?: any) => {
      if (url.includes("check-duplicate")) {
        return Promise.resolve({ is_duplicate: false });
      }
      if (opts?.method === "PATCH") {
        return Promise.resolve({
          ...samplePoi,
          lat: 48.5,
          lon: -113.8,
          reason_to_visit: "Updated: Golden hour glow on peak summits.",
        });
      }
      return Promise.resolve({
        ...samplePoi,
        lat: 48.5,
        lon: -113.8,
      });
    });

    render(
      <POIEditDrawer
        poi={samplePoi}
        isOpen={true}
        onClose={vi.fn()}
        onSave={onSaveMock}
      />
    );

    const reasonTextarea = await screen.findByPlaceholderText(
      /Why a tourist would be interested in visiting/i
    );

    // Update reason to visit text
    fireEvent.change(reasonTextarea, {
      target: { value: "Updated: Golden hour glow on peak summits." },
    });

    const saveButton = screen.getByRole("button", { name: /save changes/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        `/api/pois/${samplePoi.id}`,
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining(
            '"reason_to_visit":"Updated: Golden hour glow on peak summits."'
          ),
        })
      );
      expect(onSaveMock).toHaveBeenCalledWith(
        expect.objectContaining({
          reason_to_visit: "Updated: Golden hour glow on peak summits.",
        })
      );
    });
  });

  it("renders tag selection pills instead of text input and toggles tags on click", async () => {
    const onSaveMock = vi.fn();
    const mockUserTags = [
      { id: "1", slug: "hiking", name: "Hiking", aliases: [], poi_count: 2 },
      { id: "2", slug: "national park", name: "National park", aliases: [], poi_count: 5 },
      { id: "3", slug: "scenic", name: "Scenic", aliases: [], poi_count: 8 },
    ];

    (apiFetch as any).mockImplementation((url: string, opts?: any) => {
      if (url.includes("/api/pois/tags")) {
        return Promise.resolve(mockUserTags);
      }
      if (url.includes("check-duplicate")) {
        return Promise.resolve({ is_duplicate: false });
      }
      if (opts?.method === "PATCH") {
        const body = JSON.parse(opts.body);
        return Promise.resolve({
          ...samplePoi,
          ...body,
          lat: 48.5,
          lon: -113.8,
        });
      }
      return Promise.resolve({
        ...samplePoi,
        lat: 48.5,
        lon: -113.8,
      });
    });

    render(
      <POIEditDrawer
        poi={samplePoi}
        isOpen={true}
        onClose={vi.fn()}
        onSave={onSaveMock}
      />
    );

    // Verify text input for tags is NOT present
    expect(screen.queryByPlaceholderText(/scenic, hiking, photography/i)).toBeNull();

    // Verify tag pills container is rendered
    const tagsContainer = await screen.findByTestId("vistarae-tags-container");
    expect(tagsContainer).toBeDefined();

    // samplePoi.tags are ["national park", "scenic"]
    const scenicPill = await screen.findByTestId("tag-pill-scenic");
    const hikingPill = await screen.findByTestId("tag-pill-hiking");

    expect(scenicPill.textContent).toContain("✓ Scenic");
    expect(scenicPill.classList.contains("active")).toBe(true);

    expect(hikingPill.textContent).toBe("Hiking");
    expect(hikingPill.classList.contains("active")).toBe(false);

    // Click hiking pill to add it
    fireEvent.click(hikingPill);
    expect(hikingPill.textContent).toContain("✓ Hiking");

    // Click scenic pill to remove it
    fireEvent.click(scenicPill);
    expect(scenicPill.textContent).toBe("Scenic");

    // Save and verify tags in payload
    const saveButton = screen.getByRole("button", { name: /save changes/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        `/api/pois/${samplePoi.id}`,
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining('"tags":["national park","hiking"]'),
        })
      );
      expect(onSaveMock).toHaveBeenCalledWith(
        expect.objectContaining({
          tags: ["national park", "hiking"],
        })
      );
    });
  });
});
