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
import { TagSelector } from "../../../components/tags/TagSelector";
import * as apiModule from "../../../services/api";

vi.mock("../../../services/api", () => ({
  apiFetch: vi.fn(),
}));

const mockTags = [
  {
    id: "tag-1",
    slug: "fortification",
    name: "Fortification",
    aliases: ["castle"],
    poi_count: 3,
  },
  {
    id: "tag-2",
    slug: "historic",
    name: "Historic",
    aliases: ["heritage"],
    poi_count: 2,
  },
  {
    id: "tag-3",
    slug: "scenic",
    name: "Scenic",
    aliases: ["viewpoint"],
    poi_count: 5,
  },
];

describe("TagSelector (matches extension tag selection)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and renders configured tags as pills with correct selection states", async () => {
    (apiModule.apiFetch as any).mockResolvedValueOnce(mockTags);
    const onChangeMock = vi.fn();

    render(
      <TagSelector
        selectedTags={["historic"]}
        onChange={onChangeMock}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("tag-pill-historic")).toBeDefined();
    });

    const historicPill = screen.getByTestId("tag-pill-historic");
    const scenicPill = screen.getByTestId("tag-pill-scenic");
    const fortPill = screen.getByTestId("tag-pill-fortification");

    // Selected pill has checkmark and active class
    expect(historicPill.textContent).toContain("✓ Historic");
    expect(historicPill.classList.contains("active")).toBe(true);

    // Unselected pills do not have checkmark
    expect(scenicPill.textContent).toBe("Scenic");
    expect(scenicPill.classList.contains("active")).toBe(false);
    expect(fortPill.textContent).toBe("Fortification");
    expect(fortPill.classList.contains("active")).toBe(false);
  });

  it("calls onChange to add tag when unselected pill is clicked", async () => {
    (apiModule.apiFetch as any).mockResolvedValueOnce(mockTags);
    const onChangeMock = vi.fn();

    render(
      <TagSelector
        selectedTags={["historic"]}
        onChange={onChangeMock}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("tag-pill-scenic")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("tag-pill-scenic"));

    expect(onChangeMock).toHaveBeenCalledWith(["historic", "scenic"]);
  });

  it("calls onChange to remove tag when active pill is clicked", async () => {
    (apiModule.apiFetch as any).mockResolvedValueOnce(mockTags);
    const onChangeMock = vi.fn();

    render(
      <TagSelector
        selectedTags={["historic", "scenic"]}
        onChange={onChangeMock}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("tag-pill-historic")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("tag-pill-historic"));

    expect(onChangeMock).toHaveBeenCalledWith(["scenic"]);
  });

  it("includes pre-existing POI tags that are not in configured tags", async () => {
    (apiModule.apiFetch as any).mockResolvedValueOnce(mockTags);
    const onChangeMock = vi.fn();

    render(
      <TagSelector
        selectedTags={["coastal_cave"]}
        onChange={onChangeMock}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("tag-pill-coastal_cave")).toBeDefined();
    });

    const customPill = screen.getByTestId("tag-pill-coastal_cave");
    expect(customPill.textContent).toContain("✓ Coastal cave");
    expect(customPill.classList.contains("active")).toBe(true);
  });

  it("displays empty state message when no tags are configured and none selected", async () => {
    (apiModule.apiFetch as any).mockResolvedValueOnce([]);

    render(
      <TagSelector
        selectedTags={[]}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/No configured tags found in your Vistarae library/i),
      ).toBeDefined();
    });
  });

  it("uses provided availableTags prop directly without api call", async () => {
    const onChangeMock = vi.fn();

    render(
      <TagSelector
        selectedTags={[]}
        onChange={onChangeMock}
        availableTags={mockTags}
      />,
    );

    expect(screen.getByTestId("tag-pill-fortification")).toBeDefined();
    expect(apiModule.apiFetch).not.toHaveBeenCalled();
  });
});

