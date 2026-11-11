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

import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
import {
  POINameRecommendationsModal,
  extractNameRecommendations,
} from "../../components/ingest/POINameRecommendationsModal";
import type { CandidateItem } from "../../services/ingestApi";

vi.mock("maplibre-gl", () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      addControl: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      getSource: vi.fn(),
      flyTo: vi.fn(),
      remove: vi.fn(),
      resize: vi.fn(),
      on: vi.fn(),
      setStyle: vi.fn(),
      getZoom: vi.fn().mockReturnValue(12),
    })),
    Marker: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
      on: vi.fn(),
      getLngLat: vi.fn().mockReturnValue({ lat: 14.0825, lng: 44.4077 }),
      setPopup: vi.fn().mockReturnThis(),
    })),
    Popup: vi.fn().mockImplementation(() => ({
      setHTML: vi.fn().mockReturnThis(),
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
    })),
    NavigationControl: vi.fn(),
  },
}));

describe("POINameRecommendationsModal", () => {
  const mockCandidates: CandidateItem[] = [
    {
      id: "cand-1",
      job_id: "job-100",
      row_index: 0,
      poi_name: "Barakesh",
      recommended_poi_name: "Baraqish",
      recommended_disposition: "accept",
      latitude: 14.08253,
      longitude: 44.40778,
      city: "Baraqish",
      locality: "Baraqish",
      admin_level_2: "Al Ghayl District",
      admin_level_1: "Jawf Governorate",
      state_province: "Jawf Governorate",
      country: "Yemen",
      country_code: "YE",
      photo_directory: "",
      confidence_score: 90,
      phase_state: "phase_1_triage" as any,
    },
    {
      id: "cand-2",
      job_id: "job-100",
      row_index: 1,
      poi_name: "Okapi Faunal Reserve",
      raw_geocoding: { resolved_name: "Okapi Wildlife Reserve" },
      recommended_disposition: "accept",
      latitude: 1.416667,
      longitude: 28.583333,
      city: "Epulu",
      locality: "Epulu",
      admin_level_2: "Mambasa",
      admin_level_1: "Ituri",
      state_province: "Ituri",
      country: "Democratic Republic of the Congo",
      country_code: "CD",
      photo_directory: "",
      confidence_score: 90,
      phase_state: "phase_1_triage" as any,
    },
    {
      id: "cand-3",
      job_id: "job-100",
      row_index: 2,
      poi_name: "Eiffel Tower",
      recommended_poi_name: "Eiffel Tower", // Identical name -> should not recommend
      recommended_disposition: "accept",
      latitude: 48.8584,
      longitude: 2.2945,
      city: "Paris",
      country: "France",
      photo_directory: "",
      confidence_score: 90,
      phase_state: "phase_1_triage" as any,
    },
  ];

  it("extracts only candidates where the recommended name differs from the original name", () => {
    const recs = extractNameRecommendations(mockCandidates);
    expect(recs).toHaveLength(2);
    expect(recs[0].originalName).toBe("Barakesh");
    expect(recs[0].recommendedName).toBe("Baraqish");
    expect(recs[1].originalName).toBe("Okapi Faunal Reserve");
    expect(recs[1].recommendedName).toBe("Okapi Wildlife Reserve");
  });

  it("renders all required columns: original name, recommended name, locality, admin level 2, admin level 1, country, and default-off toggle", () => {
    render(
      <POINameRecommendationsModal
        isOpen={true}
        onClose={vi.fn()}
        candidates={mockCandidates}
        onAcceptChanges={vi.fn()}
      />,
    );

    // Verify modal title
    expect(screen.getByText("POI Name Recommendations")).toBeInTheDocument();
    expect(screen.getByText("2 Suggestions")).toBeInTheDocument();

    // Verify table headers
    expect(screen.getByText("Original POI Name")).toBeInTheDocument();
    expect(screen.getByText("Recommended POI Name")).toBeInTheDocument();
    expect(screen.getByText("Locality (Town/City)")).toBeInTheDocument();
    expect(screen.getByText("Admin Level 2 (County/District)")).toBeInTheDocument();
    expect(screen.getByText("Admin Level 1 (State/Province)")).toBeInTheDocument();
    expect(screen.getByText("Country")).toBeInTheDocument();

    // Verify row 1 fields
    expect(screen.getByText("Barakesh")).toBeInTheDocument();
    expect(screen.getAllByText("Baraqish").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Al Ghayl District")).toBeInTheDocument();
    expect(screen.getAllByText("Jawf Governorate").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Yemen").length).toBeGreaterThanOrEqual(1);

    // Verify accept toggle is default off (unchecked)
    const toggle1 = screen.getByTestId("accept-toggle-cand-1") as HTMLInputElement;
    const toggle2 = screen.getByTestId("accept-toggle-cand-2") as HTMLInputElement;
    expect(toggle1.checked).toBe(false);
    expect(toggle2.checked).toBe(false);

    // Footer starts with 0 selected
    const footer = screen.getByTestId("recommendations-footer");
    expect(footer).toHaveTextContent("0 of 2 changes will be applied");
  });

  it("displays the found location on the map in the right column when clicking on a POI row", async () => {
    render(
      <POINameRecommendationsModal
        isOpen={true}
        onClose={vi.fn()}
        candidates={mockCandidates}
        onAcceptChanges={vi.fn()}
      />,
    );

    // Initial selected item is the first one (Baraqish)
    const mapColumn = screen.getByTestId("recommendations-map-column");
    expect(mapColumn).toHaveTextContent("Baraqish");
    expect(mapColumn).toHaveTextContent("14.08253, 44.40778");

    // Click on row 2 (Okapi Wildlife Reserve)
    const row2 = screen.getByTestId("recommendation-row-cand-2");
    fireEvent.click(row2);

    // Right column updates to show Okapi
    await waitFor(() => {
      expect(mapColumn).toHaveTextContent("Okapi Wildlife Reserve");
      expect(mapColumn).toHaveTextContent("1.41667, 28.58333");
    });
  });

  it("toggles accept switches and updates 'Accept Changes' button activation", async () => {
    const handleAcceptChanges = vi.fn();

    render(
      <POINameRecommendationsModal
        isOpen={true}
        onClose={vi.fn()}
        candidates={mockCandidates}
        onAcceptChanges={handleAcceptChanges}
      />,
    );

    const acceptBtn = screen.getByTestId("accept-changes-btn");
    // Initially disabled because 0 are selected
    expect(acceptBtn).toBeDisabled();

    // Toggle row 1 on
    const toggle1 = screen.getByTestId("accept-toggle-cand-1");
    fireEvent.click(toggle1);

    const footer = screen.getByTestId("recommendations-footer");
    expect(footer).toHaveTextContent("1 of 2 changes will be applied");
    expect(acceptBtn).not.toBeDisabled();

    // Click "Accept Changes"
    fireEvent.click(acceptBtn);

    expect(handleAcceptChanges).toHaveBeenCalledTimes(1);
    expect(handleAcceptChanges).toHaveBeenCalledWith([
      {
        candidateId: "cand-1",
        newName: "Baraqish",
      },
    ]);
  });

  it("supports toggle-all to select or deselect all recommendations with one click", async () => {
    const handleAcceptChanges = vi.fn();

    render(
      <POINameRecommendationsModal
        isOpen={true}
        onClose={vi.fn()}
        candidates={mockCandidates}
        onAcceptChanges={handleAcceptChanges}
      />,
    );

    const toggleAllBtn = screen.getByTestId("toggle-all-recommendations-btn");
    fireEvent.click(toggleAllBtn);

    // Both should be checked
    const toggle1 = screen.getByTestId("accept-toggle-cand-1") as HTMLInputElement;
    const toggle2 = screen.getByTestId("accept-toggle-cand-2") as HTMLInputElement;
    expect(toggle1.checked).toBe(true);
    expect(toggle2.checked).toBe(true);

    const footer = screen.getByTestId("recommendations-footer");
    expect(footer).toHaveTextContent("2 of 2 changes will be applied");

    // Click Accept Changes
    const acceptBtn = screen.getByTestId("accept-changes-btn");
    fireEvent.click(acceptBtn);

    expect(handleAcceptChanges).toHaveBeenCalledWith([
      { candidateId: "cand-1", newName: "Baraqish" },
      { candidateId: "cand-2", newName: "Okapi Wildlife Reserve" },
    ]);
  });

  it("closes modal when clicking 'Keep Original Names'", () => {
    const handleClose = vi.fn();

    render(
      <POINameRecommendationsModal
        isOpen={true}
        onClose={handleClose}
        candidates={mockCandidates}
        onAcceptChanges={vi.fn()}
      />,
    );

    const cancelBtn = screen.getByTestId("cancel-recommendations-btn");
    fireEvent.click(cancelBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
