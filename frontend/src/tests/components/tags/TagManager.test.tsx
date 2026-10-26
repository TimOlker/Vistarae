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
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { TagManager } from "../../../components/tags/TagManager";
import * as apiModule from "../../../services/api";
import { ToastProvider } from "../../../context/ToastContext";

vi.mock("../../../services/api", () => ({
  apiFetch: vi.fn(),
}));

const mockTags = [
  {
    id: "tag-1",
    slug: "fortification",
    name: "Fortification",
    aliases: ["castle", "fort", "citadel"],
    poi_count: 5,
    created_at: "2026-10-22T10:00:00Z",
  },
  {
    id: "tag-2",
    slug: "historic",
    name: "Historic",
    aliases: ["history", "heritage"],
    poi_count: 0,
    created_at: "2026-10-22T10:05:00Z",
  },
  {
    id: "tag-3",
    slug: "building",
    name: "Building",
    aliases: ["skyscraper"],
    poi_count: 2,
    created_at: "2026-10-22T10:10:00Z",
  },
];

const renderComponent = () => {
  return render(
    <ToastProvider>
      <TagManager />
    </ToastProvider>,
  );
};

describe("TagManager Component (REQ-EXT-002, REQ-EXT-004, REQ-EXT-005, REQ-EXT-006)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and renders tags in alphabetical order", async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([...mockTags]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("tag-list")).toBeDefined();
    });

    const items = screen.getAllByTestId(/tag-item-/);
    expect(items.length).toBe(3);

    // Alphabetical order: Building, Fortification, Historic
    expect(items[0].textContent).toContain("Building");
    expect(items[1].textContent).toContain("Fortification");
    expect(items[2].textContent).toContain("Historic");
  });

  it("filters tags via search input by name, slug, or alias", async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([...mockTags]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("tag-list")).toBeDefined();
    });

    const searchInput = screen.getByTestId("tag-search-input");
    fireEvent.change(searchInput, { target: { value: "castle" } });

    const items = screen.getAllByTestId(/tag-item-/);
    expect(items.length).toBe(1);
    expect(items[0].textContent).toContain("Fortification");
  });

  it("opens Add Tag modal and creates tag with derived slug and aliases", async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([...mockTags]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("add-tag-btn")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("add-tag-btn"));
    expect(screen.getByTestId("add-tag-modal")).toBeDefined();

    const nameInput = screen.getByTestId("new-tag-name-input");
    const aliasesInput = screen.getByTestId("new-tag-aliases-input");

    fireEvent.change(nameInput, { target: { value: "Museum Ship" } });
    fireEvent.change(aliasesInput, { target: { value: "submarine, warship" } });

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce({
      id: "tag-4",
      slug: "museum_ship",
      name: "Museum Ship",
      aliases: ["submarine", "warship"],
      poi_count: 0,
    });
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([
      ...mockTags,
      {
        id: "tag-4",
        slug: "museum_ship",
        name: "Museum Ship",
        aliases: ["submarine", "warship"],
        poi_count: 0,
      },
    ]);

    fireEvent.click(screen.getByTestId("submit-create-tag-btn"));

    await waitFor(() => {
      expect(apiModule.apiFetch).toHaveBeenCalledWith("/api/pois/tags", {
        method: "POST",
        body: JSON.stringify({
          name: "Museum Ship",
          slug: "museum_ship",
          aliases: ["submarine", "warship"],
        }),
      });
    });
  });

  it("handles deletion conflict modal when tag is referenced by POIs (REQ-EXT-006)", async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([...mockTags]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("delete-tag-btn-fortification")).toBeDefined();
    });

    // Fortification has poi_count = 5
    fireEvent.click(screen.getByTestId("delete-tag-btn-fortification"));

    // Should immediately open deletion conflict modal
    const conflictModal = screen.getByTestId("delete-conflict-modal");
    expect(conflictModal).toBeDefined();
    expect(within(conflictModal).getByText(/Cannot Delete Tag in Use/)).toBeDefined();
    expect(within(conflictModal).getByText(/5 POIs/)).toBeDefined();

    const remediationLink = screen.getByTestId("view-affected-pois-btn") as HTMLAnchorElement;
    expect(remediationLink.getAttribute("href")).toBe("/?filter_tag=fortification");
  });

  it("confirms and deletes unused tag when poi_count is 0 (REQ-EXT-007)", async () => {
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([...mockTags]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId("delete-tag-btn-historic")).toBeDefined();
    });

    // Historic has poi_count = 0
    fireEvent.click(screen.getByTestId("delete-tag-btn-historic"));

    // Should open standard confirmation modal
    expect(screen.getByTestId("delete-confirm-modal")).toBeDefined();
    expect(screen.getByText(/Delete Tag "Historic"\?/)).toBeDefined();

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce({});
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce([mockTags[0], mockTags[2]]);

    fireEvent.click(screen.getByTestId("confirm-delete-tag-btn"));

    await waitFor(() => {
      expect(apiModule.apiFetch).toHaveBeenCalledWith("/api/pois/tags/tag-2", {
        method: "DELETE",
      });
    });
  });
});
