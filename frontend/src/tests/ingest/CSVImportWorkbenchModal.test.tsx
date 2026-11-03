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
import { CSVImportWorkbenchModal } from "../../components/ingest/CSVImportWorkbenchModal";
import { ingestApi, type CandidateItem } from "../../services/ingestApi";
import { ToastProvider } from "../../context/ToastContext";

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
      getZoom: vi.fn().mockReturnValue(12),
    })),
    Marker: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
      on: vi.fn(),
      getLngLat: vi.fn().mockReturnValue({ lat: 35.3606, lng: 138.7274 }),
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

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    listStagingCandidates: vi.fn(),
    updateStagingCandidate: vi.fn(),
    enrichSingleCandidate: vi.fn(),
    enrichAllCandidates: vi.fn(),
    batchEditCandidates: vi.fn(),
    commitWorkbenchJob: vi.fn(),
    cancelPhase1: vi.fn(),
  },
}));

describe("CSVImportWorkbenchModal (Unified Staging Workbench)", () => {
  const mockCandidates: CandidateItem[] = [
    {
      id: "cand-1",
      job_id: "job-1",
      row_index: 0,
      poi_name: "Mount Fuji",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 35.3606,
      longitude: 138.7274,
      street_address: "Kitayama",
      city: "Fujinomiya",
      state_province: "Shizuoka",
      country: "Japan",
      country_code: "JP",
      admin_level_1: "Shizuoka Prefecture",
      admin_level_2: "Fujinomiya City",
      locality: "Fujinomiya",
      hero_image_url: "https://example.com/fuji.jpg",
      official_url: "https://fujisan.jp",
      related_websites: [
        { name: "Official Guide", url: "https://fujisan.jp/guide" }
      ],
      no_websites: false,
      confidence_score: 95,
      disposition_justification: "High confidence coordinate match from authoritative geocoder.",
      photo_directory: "Japan/Fuji",
      photo_directories: ["Japan/Fuji"],
      dates_visited: ["2024-05-01"],
      tags: ["Volcano", "Scenic"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
    {
      id: "cand-2",
      job_id: "job-1",
      row_index: 1,
      poi_name: "Lake Kawaguchi",
      recommended_disposition: "sublocation" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: null,
      longitude: null,
      street_address: null,
      city: "Fujikawaguchiko",
      state_province: "Yamanashi",
      country: "Japan",
      country_code: "JP",
      hero_image_url: null,
      official_url: null,
      related_websites: [],
      no_websites: false,
      confidence_score: 50,
      disposition_justification: "Missing coordinates; proximity to Fuji suggests child sublocation.",
      photo_directory: "Japan/Kawaguchi",
      photo_directories: ["Japan/Kawaguchi"],
      dates_visited: [],
      tags: ["Lake"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 2,
      candidates: mockCandidates,
    });
  });

  const renderModal = () =>
    render(
      <ToastProvider>
        <CSVImportWorkbenchModal
          jobId="job-1"
          isOpen={true}
          onClose={vi.fn()}
        />
      </ToastProvider>
    );

  it("renders split layout with master table on left and editor on right", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("import-staging-workbench-modal")).toBeInTheDocument();
      expect(screen.getAllByText("Mount Fuji").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Lake Kawaguchi")).toBeInTheDocument();
    });

    // Check completeness badges
    expect(screen.getByTestId("completeness-badge-complete")).toBeInTheDocument();
    expect(screen.getByTestId("completeness-badge-incomplete")).toBeInTheDocument();

    // Check pinned footer in editor
    expect(screen.getByTestId("candidate-editor-pinned-footer")).toBeInTheDocument();
    expect(screen.getByTestId("save-candidate-changes-btn")).toBeInTheDocument();
  });

  it("toggles perspective between POI and Location modes", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("perspective-select")).toBeInTheDocument();
    });

    const perspectiveSelect = screen.getByTestId("perspective-select") as HTMLSelectElement;
    expect(perspectiveSelect.value).toBe("POI");

    fireEvent.change(perspectiveSelect, { target: { value: "Location" } });
    expect(perspectiveSelect.value).toBe("Location");
  });

  it("toggles reactive 'No Websites' checkbox and unsets URLs", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Mount Fuji");
    });

    const noWebsitesCheckbox = screen.getByTestId("no-websites-checkbox") as HTMLInputElement;
    expect(noWebsitesCheckbox.checked).toBe(false);

    // Toggle No Websites to true
    fireEvent.click(noWebsitesCheckbox);
    expect(noWebsitesCheckbox.checked).toBe(true);

    // Official and Wiki inputs should now be replaced by skipped message
    expect(screen.getByText(/Web scraping skipped: POI verified to have no relevant web presence/i)).toBeInTheDocument();
  });

  it("adds and deletes a dynamic website with confirmation prompt", async () => {
    window.confirm = vi.fn().mockReturnValue(true);

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("add-website-btn")).toBeInTheDocument();
    });

    // Add website
    fireEvent.change(screen.getByTestId("new-website-name-input"), {
      target: { value: "Fuji Webcam" },
    });
    fireEvent.change(screen.getByTestId("new-website-url-input"), {
      target: { value: "https://fuji-cam.jp" },
    });
    fireEvent.click(screen.getByTestId("add-website-btn"));

    expect(screen.getByText(/Fuji Webcam/i)).toBeInTheDocument();

    // Delete a website
    const deleteBtn = screen.getByTestId("delete-website-btn-0");
    fireEvent.click(deleteBtn);

    expect(window.confirm).toHaveBeenCalledWith("Are you sure you want to remove this website?");
  });

  it("invokes single-POI enrichment when 'AI Enrich POI' is clicked", async () => {
    vi.mocked(ingestApi.enrichSingleCandidate).mockResolvedValue({
      ...mockCandidates[0],
      description: "Enriched description of Mount Fuji",
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("ai-enrich-poi-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("ai-enrich-poi-btn"));

    await waitFor(() => {
      expect(ingestApi.enrichSingleCandidate).toHaveBeenCalledWith("job-1", "cand-1");
    });
  });

  it("saves modified candidate changes using pinned footer button", async () => {
    vi.mocked(ingestApi.updateStagingCandidate).mockResolvedValue({
      ...mockCandidates[0],
      poi_name: "Mount Fuji Sacred Peak",
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("editor-poi-name-input"), {
      target: { value: "Mount Fuji Sacred Peak" },
    });

    fireEvent.click(screen.getByTestId("save-candidate-changes-btn"));

    await waitFor(() => {
      expect(ingestApi.updateStagingCandidate).toHaveBeenCalledWith(
        "job-1",
        "cand-1",
        expect.objectContaining({
          poi_name: "Mount Fuji Sacred Peak",
        })
      );
    });
  });

  it("updates proximity search radius and displays nearby count badge", async () => {
    render(
      <ToastProvider>
        <CSVImportWorkbenchModal
          jobId="job-1"
          isOpen={true}
          onClose={vi.fn()}
          existingPOIs={[
            {
              id: "poi-nearby-1",
              name: "Mount Fuji Station 5",
              latitude: 35.3610,
              longitude: 138.7280,
            },
          ]}
        />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("proximity-radius-slider")).toBeInTheDocument();
      expect(screen.getByTestId("nearby-poi-count-badge")).toBeInTheDocument();
    });

    // Mount Fuji Station 5 is ~0.04 mi away, so within 1 mi radius it shows 1 Nearby Point
    expect(screen.getByTestId("nearby-poi-count-badge")).toHaveTextContent(/1 Nearby Point/i);
  });

  it("shows inline validation error when disposition is Sublocation without parent", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-disposition-select")).toBeInTheDocument();
    });

    // Change disposition to sublocation
    fireEvent.change(screen.getByTestId("editor-disposition-select"), {
      target: { value: "sublocation" },
    });

    // Inline error should appear
    await waitFor(() => {
      expect(screen.getByTestId("sublocation-missing-parent-error")).toBeInTheDocument();
      expect(screen.getByText(/Parent POI required for Sublocation disposition/i)).toBeInTheDocument();
    });
  });

  it("displays confidence score badge with color scale and rationale", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("confidence-score-badge")).toBeInTheDocument();
      expect(screen.getByTestId("disposition-rationale-readonly")).toBeInTheDocument();
    });

    expect(screen.getByTestId("confidence-score-badge")).toHaveTextContent("95%");
    expect(screen.getByTestId("disposition-rationale-readonly")).toHaveValue(
      "Disposition: accept\nRationale: High confidence coordinate match from authoritative geocoder."
    );
  });

  it("displays in-batch merge target selector when disposition is in_batch_merge", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-disposition-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("editor-disposition-select"), {
      target: { value: "in_batch_merge" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("in-batch-merge-card")).toBeInTheDocument();
      expect(screen.getByTestId("merge-target-select")).toBeInTheDocument();
    });
  });

  it("applies batch edits across selected candidates", async () => {
    vi.mocked(ingestApi.batchEditCandidates).mockResolvedValue({ updated_count: 2 });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("select-all-checkbox")).toBeInTheDocument();
    });

    // Select all candidates
    fireEvent.click(screen.getByTestId("select-all-checkbox"));

    // Click Batch Edit button
    expect(screen.getByTestId("batch-edit-btn")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("batch-edit-btn"));

    // Fill in batch country
    await waitFor(() => {
      expect(screen.getByTestId("batch-country-input")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("batch-country-input"), {
      target: { value: "Japan" },
    });

    // Submit batch edit
    fireEvent.click(screen.getByTestId("apply-batch-edit-btn"));

    await waitFor(() => {
      expect(ingestApi.batchEditCandidates).toHaveBeenCalledWith(
        "job-1",
        expect.objectContaining({
          candidate_ids: ["cand-1", "cand-2"],
          country: "Japan",
        })
      );
    });
  });
});
