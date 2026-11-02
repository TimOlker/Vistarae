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
import { CSVPhase2ReviewModal } from "../../components/ingest/CSVPhase2ReviewModal";
import { ingestApi, type CandidateItem } from "../../services/ingestApi";
import { ToastProvider } from "../../context/ToastContext";
import { ToastBanner } from "../../components/common/ToastBanner";

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
      getContainer: vi.fn(),
    })),
    Marker: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
      on: vi.fn(),
    })),
    NavigationControl: vi.fn(),
  },
}));

vi.mock("../../services/api" , () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/tags") || url.includes("/api/pois/tags")) {
      return Promise.resolve([
        { id: "tag-1", name: "Sightseeing", slug: "sightseeing" },
        { id: "tag-2", name: "Landmark", slug: "landmark" },
        { id: "tag-3", name: "Temple", slug: "temple" },
        { id: "tag-4", name: "Historic", slug: "historic" },
        { id: "tag-5", name: "Buddhism", slug: "buddhism" },
        { id: "tag-6", name: "Botanical", slug: "botanical" },
        { id: "tag-7", name: "Chicago", slug: "chicago" },
      ]);
    }
    return Promise.resolve({});
  }),
}));

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    getJobCandidates: vi.fn(),
    updateCandidate: vi.fn(),
    commitPhase2: vi.fn(),
    cancelPhase2: vi.fn(),
    enrichPhase2: vi.fn(),
    getPhase2Progress: vi.fn(),
    backToPhase1: vi.fn(),
  },
}));

const mockEnrichedCandidates: CandidateItem[] = [
  {
    id: "cand-1",
    job_id: "job-200",
    row_index: 0,
    poi_name: "Senso-ji",
    recommended_disposition: "accept",
    user_disposition: null,
    latitude: 35.7147,
    longitude: 139.7966,
    street_address: "2 Chome-3-1 Asakusa",
    city: "Taito City",
    country: "Japan",
    dates_visited: ["2023-04-10"],
    photo_directory: "Japan 2023/Sensoji",
    confidence_score: 95,
    description: "Ancient Buddhist temple in Asakusa famous for Kaminarimon Gate.",
    reason_to_visit: "Experience iconic Edo atmosphere and temple architecture.",
    official_url: "https://www.senso-ji.jp",
    wiki_url: "https://en.wikipedia.org/wiki/Sens%C5%8D-ji",
    hero_image_url: "https://upload.wikimedia.org/sensoji.jpg",
    recommended_duration_hours: 2.0,
    recommended_visit_days: 0,
    estimated_visit_time_notes: "Estimated 2 hours for main temple and Nakamise street.",
    tags: ["Temple", "Historic", "Buddhism"],
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_2_enriched",
  },
  {
    id: "cand-2",
    job_id: "job-200",
    row_index: 1,
    poi_name: "Garfield Park Conservatory",
    recommended_disposition: "update_existing",
    user_disposition: null,
    matched_existing_poi_id: "poi-existing-123",
    latitude: 41.886,
    longitude: -87.717,
    city: "Chicago",
    state_province: "Illinois",
    country: "United States",
    photo_directory: "2005/Garfield Park",
    confidence_score: 90,
    description: "Botanical sanctuary featuring historic glasshouses and palm collections.",
    reason_to_visit: "Marvel at lush desert and tropical plant rooms.",
    official_url: null,
    wiki_url: null,
    hero_image_url: null,
    recommended_duration_hours: 2.5,
    recommended_visit_days: 0,
    estimated_visit_time_notes: "Estimated 2.5 hours exploring multiple plant houses.",
    tags: ["Botanical", "Chicago"],
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_2_enriched",
  },
  {
    id: "cand-3",
    job_id: "job-200",
    row_index: 2,
    poi_name: "Ignored POI",
    recommended_disposition: "ignore",
    user_disposition: null,
    confidence_score: 10,
    photo_directory: "",
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_2_enriched",
  },
  {
    id: "cand-4",
    job_id: "job-200",
    row_index: 3,
    poi_name: "Excluded Privacy POI",
    recommended_disposition: "exclude",
    user_disposition: null,
    confidence_score: 0,
    photo_directory: "",
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_2_enriched",
  },
];

describe("CSVPhase2ReviewModal (Phase 2)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.getJobCandidates).mockResolvedValue({
      job_id: "job-200",
      total_candidates: 4,
      candidates: mockEnrichedCandidates,
    });
    vi.mocked(ingestApi.getPhase2Progress).mockResolvedValue({
      job_id: "job-200",
      total_count: 2,
      enriched_count: 2,
      is_complete: true,
      percent_complete: 100,
      status_message: "Complete",
    });
  });

  it("renders enriched candidate table with descriptions, durations, reasons to visit, and tags", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
      expect(screen.getAllByText("Garfield Park Conservatory")[0]).toBeInTheDocument();
    });

    // Ignored and excluded candidates should NOT be displayed
    expect(screen.queryByText("Ignored POI")).not.toBeInTheDocument();
    expect(screen.queryByText("Excluded Privacy POI")).not.toBeInTheDocument();

    expect(screen.getByText("2 Ready to Commit")).toBeInTheDocument();

    // Clicking candidate row opens the details panel with description, reason to visit, and tags
    fireEvent.click(screen.getByTestId("enriched-row-cand-1"));
    expect(screen.getAllByText(/Ancient Buddhist temple in Asakusa/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Experience iconic Edo atmosphere/)[0]).toBeInTheDocument();
    expect(screen.getAllByText("Temple")[0]).toBeInTheDocument();
  });

  it("toggles skip state on candidate and dispatches update", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockEnrichedCandidates[0],
      is_skipped: true,
    });

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("skip-toggle-cand-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("skip-toggle-cand-1"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-1", {
      is_skipped: true,
    });
  });

  it("allows selecting a candidate, editing rich fields, and saving changes", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockEnrichedCandidates[0],
      description: "Updated description text.",
    });

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("enriched-row-cand-1")).toBeInTheDocument();
    });

    // Selecting candidate populates the right panel editor
    fireEvent.click(screen.getByTestId("enriched-row-cand-1"));

    expect(screen.getByTestId("poi-edit-drawer")).toBeInTheDocument();

    // Verify rich inputs exist
    expect(screen.getByTestId("related-websites-section")).toBeInTheDocument();
    expect(screen.getByTestId("edit-poi-hero-image-input")).toBeInTheDocument();
    expect(screen.getByTestId("hero-image-preview")).toBeInTheDocument();
    expect(screen.getByTestId("edit-poi-duration-hours-input")).toBeInTheDocument();
    expect(screen.getByTestId("edit-poi-duration-notes-input")).toBeInTheDocument();

    const descInput = screen.getByTestId("edit-poi-description-input");
    fireEvent.change(descInput, { target: { value: "Updated description text." } });

    fireEvent.click(screen.getByTestId("save-edit-button"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-1", {
      poi_name: "Senso-ji",
      description: "Updated description text.",
      reason_to_visit: "Experience iconic Edo atmosphere and temple architecture.",
      official_url: "https://www.senso-ji.jp",
      wiki_url: "https://en.wikipedia.org/wiki/Sens%C5%8D-ji",
      related_websites: [
        { name: "Official Website", url: "https://www.senso-ji.jp" },
        { name: "Wikipedia", url: "https://en.wikipedia.org/wiki/Sens%C5%8D-ji" },
      ],
      hero_image_url: "https://upload.wikimedia.org/sensoji.jpg",
      recommended_duration_hours: 2,
      recommended_visit_days: 1,
      estimated_visit_time_notes: "Estimated 2 hours for main temple and Nakamise street.",
      tags: ["Temple", "Historic", "Buddhism"],
      street_address: "2 Chome-3-1 Asakusa",
      city: "Taito City",
      update_coordinates: false,
    });
  });

  it("displays 'Update Existing POI Coordinates' toggle in right panel for update candidates", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("enriched-row-cand-2")).toBeInTheDocument();
    });

    // Click candidate 2 (update_existing)
    fireEvent.click(screen.getByTestId("enriched-row-cand-2"));

    expect(screen.getByTestId("edit-update-coordinates-toggle")).toBeInTheDocument();
  });

  it("commits enriched candidates to database when 'Save to DB' is clicked", async () => {
    vi.mocked(ingestApi.commitPhase2).mockResolvedValue({
      job_id: "job-200",
      committed_count: 2,
      created_pois: ["new-poi-1"],
      merged_pois: ["merged-poi-1"],
      message: "Success",
    });

    const onCommit = vi.fn();

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={onCommit}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("save-to-db-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("save-to-db-button"));

    await waitFor(() => {
      expect(ingestApi.commitPhase2).toHaveBeenCalledWith("job-200");
      expect(onCommit).toHaveBeenCalled();
    });
  });

  it("cancels Phase 2 review and purges staging records", async () => {
    vi.mocked(ingestApi.cancelPhase2).mockResolvedValue({
      job_id: "job-200",
      purged_count: 2,
      message: "Purged",
    });

    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={onClose}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("cancel-phase2-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("cancel-phase2-button"));

    await waitFor(() => {
      expect(ingestApi.cancelPhase2).toHaveBeenCalledWith("job-200");
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("saves progress and closes without purging when Save & Close is clicked", async () => {
    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={onClose}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("save-close-phase2-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("save-close-phase2-button"));

    expect(onClose).toHaveBeenCalled();
    expect(ingestApi.cancelPhase2).not.toHaveBeenCalled();
  });

  it("reverts candidates and calls onBackToPhase1 when 'Back to Phase 1' is clicked", async () => {
    vi.mocked(ingestApi.backToPhase1).mockResolvedValue({
      job_id: "job-200",
      advanced_count: 2,
      ignored_count: 0,
      message: "Reverted",
    });

    const onBack = vi.fn();

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
          onBackToPhase1={onBack}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("back-to-phase1-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("back-to-phase1-button"));

    await waitFor(() => {
      expect(ingestApi.backToPhase1).toHaveBeenCalledWith("job-200");
      expect(onBack).toHaveBeenCalledWith("job-200");
    });
  });

  it("triggers AI enrichment and opens progress modal when 'AI Enrich All' is clicked", async () => {
    vi.mocked(ingestApi.enrichPhase2).mockResolvedValue({
      job_id: "job-200",
      message: "Queued",
      advanced_count: 0,
      ignored_count: 0,
    });

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("ai-enrich-all-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("ai-enrich-all-btn"));

    await waitFor(() => {
      expect(ingestApi.enrichPhase2).toHaveBeenCalledWith("job-200");
      expect(screen.getByTestId("enrichment-progress-modal")).toBeInTheDocument();
    });
  });

  it("supports multi-selecting POIs via row checkboxes and select-all checkbox", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("select-all-phase2-checkbox")).toBeInTheDocument();
      expect(screen.getByTestId("candidate-checkbox-cand-1")).toBeInTheDocument();
      expect(screen.getByTestId("candidate-checkbox-cand-2")).toBeInTheDocument();
    });

    // Individual select
    fireEvent.click(screen.getByTestId("candidate-checkbox-cand-1"));
    expect(screen.getByTestId("bulk-actions-toolbar")).toBeInTheDocument();
    expect(screen.getByText("1 POI(s) selected")).toBeInTheDocument();

    // Select-all
    fireEvent.click(screen.getByTestId("select-all-phase2-checkbox"));
    expect(screen.getByText("2 POI(s) selected")).toBeInTheDocument();

    // Bulk tag panel appears when >1 selected
    expect(screen.getByTestId("bulk-tag-panel")).toBeInTheDocument();

    // Clear selection
    fireEvent.click(screen.getByTestId("clear-selection-btn"));
    expect(screen.queryByTestId("bulk-actions-toolbar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bulk-tag-panel")).not.toBeInTheDocument();
  });

  it("bulk adds a tag to all selected POIs without duplicates", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockEnrichedCandidates[0],
      tags: ["Temple", "Historic", "Buddhism", "Landmark"],
    });

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("select-all-phase2-checkbox")).toBeInTheDocument();
    });

    // Select both candidates
    fireEvent.click(screen.getByTestId("select-all-phase2-checkbox"));

    expect(screen.getByTestId("bulk-add-tag-landmark")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bulk-add-tag-landmark"));

    await waitFor(() => {
      // Both cand-1 and cand-2 receive "Landmark"
      expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-1", {
        tags: ["Temple", "Historic", "Buddhism", "Landmark"],
      });
      expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-2", {
        tags: ["Botanical", "Chicago", "Landmark"],
      });
    });
  });

  it("bulk removes a tag from all selected POIs where present", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockEnrichedCandidates[0],
      tags: ["Historic", "Buddhism"],
    });

    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("select-all-phase2-checkbox")).toBeInTheDocument();
    });

    // Select both candidates
    fireEvent.click(screen.getByTestId("select-all-phase2-checkbox"));

    // cand-1 has "Temple", cand-2 does not
    expect(screen.getByTestId("bulk-remove-tag-temple")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bulk-remove-tag-temple"));

    await waitFor(() => {
      // cand-1 gets updated with Temple removed
      expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-1", {
        tags: ["Historic", "Buddhism"],
      });
      // cand-2 did not have Temple, so not updated
      expect(ingestApi.updateCandidate).not.toHaveBeenCalledWith(
        "job-200",
        "cand-2",
        expect.anything(),
      );
    });
  });

  it("limits assigned tags strictly to the configured Tags Library without custom tags or case duplicates", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("enriched-row-cand-1")).toBeInTheDocument();
    });

    // Click candidate 1 to inspect
    fireEvent.click(screen.getByTestId("enriched-row-cand-1"));

    // "Temple" is already in cand-1 tags, clicking it toggles off
    const templeTag = screen.getByTestId("approved-tag-temple");
    expect(templeTag).toBeInTheDocument();
    fireEvent.click(templeTag);

    // Custom tag input must NOT exist
    expect(screen.queryByTestId("add-custom-tag-input")).not.toBeInTheDocument();
    expect(screen.queryByTestId("add-custom-tag-btn")).not.toBeInTheDocument();

    // In bulk panel, custom tag input must NOT exist either
    fireEvent.click(screen.getByTestId("select-all-phase2-checkbox"));
    expect(screen.queryByTestId("bulk-custom-tag-input")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bulk-add-custom-tag-btn")).not.toBeInTheDocument();
  });

  it("aborts export and displays warning toast when 0 candidates checked in Phase 2 Review", async () => {
    const exportApi = await import("../../services/exportApi");
    const exportSpy = vi.spyOn(exportApi, "exportPhase2Candidates").mockResolvedValue(undefined);

    render(
      <ToastProvider>
        <ToastBanner />
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("export-selected-phase2-btn")).toBeInTheDocument();
    });

    const exportBtn = screen.getByTestId("export-selected-phase2-btn");
    fireEvent.click(exportBtn);

    expect(exportSpy).not.toHaveBeenCalled();
    expect(screen.getByText("No records selected. Please select at least one record to export.")).toBeInTheDocument();
  });

  it("exports checked candidates in Phase 2 Review when clicked", async () => {
    const exportApi = await import("../../services/exportApi");
    const exportSpy = vi.spyOn(exportApi, "exportPhase2Candidates").mockResolvedValue(undefined);

    render(
      <ToastProvider>
        <ToastBanner />
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("select-all-phase2-checkbox")).toBeInTheDocument();
    });

    // Select all candidates
    fireEvent.click(screen.getByTestId("select-all-phase2-checkbox"));

    const formatSelect = screen.getByTestId("export-format-select-phase2");
    fireEvent.change(formatSelect, { target: { value: "json" } });

    const exportBtn = screen.getByTestId("export-selected-phase2-btn");
    fireEvent.click(exportBtn);

    expect(exportSpy).toHaveBeenCalledWith("job-200", expect.arrayContaining(["cand-1", "cand-2"]), "json");
  });

  it("supports Sort Priority dropdown between POI and Location with dynamic column ordering and column sort overrides", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    // 1. Verify sort priority select exists and defaults to "poi"
    const sortPrioritySelect = screen.getByRole("combobox", {
      name: /sort priority/i,
    }) as HTMLSelectElement;
    expect(sortPrioritySelect).toBeInTheDocument();
    expect(sortPrioritySelect.value).toBe("poi");

    // 2. In "poi" mode, check column headers start with POI Name -> Country -> State / Province -> City / Town
    const tableHeaders = screen.getAllByRole("columnheader");
    expect(tableHeaders[1]).toHaveTextContent(/Status/i);
    expect(tableHeaders[2]).toHaveTextContent(/POI Name/i);
    expect(tableHeaders[3]).toHaveTextContent(/Country/i);
    expect(tableHeaders[4]).toHaveTextContent(/State \/ Province/i);
    expect(tableHeaders[5]).toHaveTextContent(/City \/ Town/i);

    // Verify POI name is bolded (fontWeight: 700)
    const sensojiCell = screen.getAllByText("Senso-ji")[0];
    expect(sensojiCell).toHaveStyle({ fontWeight: 700 });

    // In "poi" mode, "Garfield Park Conservatory" precedes "Senso-ji" alphabetically
    const poiNamesPoiMode = screen.getAllByText(/Garfield Park Conservatory|Senso-ji/);
    expect(poiNamesPoiMode[0]).toHaveTextContent("Garfield Park Conservatory");
    expect(poiNamesPoiMode[1]).toHaveTextContent("Senso-ji");

    // 3. Switch to "location" priority
    fireEvent.change(sortPrioritySelect, { target: { value: "location" } });
    expect(sortPrioritySelect.value).toBe("location");

    // Column headers should now start with Country -> State / Province -> City / Town -> POI Name
    const reorderedHeaders = screen.getAllByRole("columnheader");
    expect(reorderedHeaders[1]).toHaveTextContent(/Status/i);
    expect(reorderedHeaders[2]).toHaveTextContent(/Country/i);
    expect(reorderedHeaders[3]).toHaveTextContent(/State \/ Province/i);
    expect(reorderedHeaders[4]).toHaveTextContent(/City \/ Town/i);
    expect(reorderedHeaders[5]).toHaveTextContent(/POI Name/i);

    // In "location" mode, "Japan" precedes "United States", so "Senso-ji" comes first
    const poiNamesLocMode = screen.getAllByText(/Garfield Park Conservatory|Senso-ji/);
    expect(poiNamesLocMode[0]).toHaveTextContent("Senso-ji");
    expect(poiNamesLocMode[1]).toHaveTextContent("Garfield Park Conservatory");

    // 4. Test column header click overrides sort priority while keeping column order
    fireEvent.click(screen.getByText(/Disposition/i));
    const headersAfterOverride = screen.getAllByRole("columnheader");
    expect(headersAfterOverride[2]).toHaveTextContent(/Country/i);
    expect(headersAfterOverride[5]).toHaveTextContent(/POI Name/i);
  });

  it("renders Data Status column, highlights incomplete rows, and displays Location Map on POI selection", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          jobId="job-200"
          isOpen={true}
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    // 1. Verify Data Status column header exists
    expect(screen.getByText(/Data Status/i)).toBeInTheDocument();

    // 2. cand-1 (Senso-ji) has all fields populated -> Complete
    const cand1Status = screen.getByTestId("data-status-cand-1");
    expect(cand1Status).toHaveTextContent(/Complete/i);

    // 3. cand-2 (Garfield Park Conservatory) is missing URLs/photo -> Incomplete
    const cand2Status = screen.getByTestId("data-status-cand-2");
    expect(cand2Status).toHaveTextContent(/Incomplete/i);

    // 4. Incomplete row has subtle amber background indicating manual intervention needed
    const rowCand2 = screen.getByTestId("enriched-row-cand-2");
    expect(rowCand2).toHaveStyle({ backgroundColor: "rgb(255, 251, 235)" }); // #fffbeb

    // 5. Clicking on a POI row displays the interactive location map at the bottom of the right panel
    fireEvent.click(screen.getByTestId("enriched-row-cand-1"));
    expect(screen.getByTestId("poi-location-map-container")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-mini-map")).toBeInTheDocument();

    // 6. Test sorting by Data Status
    fireEvent.click(screen.getByText(/Data Status/i));
    const statusHeaders = screen.getAllByRole("columnheader");
    expect(statusHeaders[8]).toHaveTextContent(/Data Status/i);
  });

  it("highlights empty fields with light amber background in edit information drawer", async () => {
    render(
      <ToastProvider>
        <CSVPhase2ReviewModal
          isOpen={true}
          jobId="job-200"
          onClose={vi.fn()}
          onCommitComplete={vi.fn()}
        />
      </ToastProvider>,
    );

    // Click candidate 2 (which has null hero_image_url, official_url, and wiki_url)
    const row2 = await screen.findByTestId("enriched-row-cand-2");
    fireEvent.click(row2);

    const heroInput = screen.getByTestId("edit-poi-hero-image-input");
    expect(heroInput).toHaveStyle({ backgroundColor: "rgb(255, 251, 235)" });
    expect(screen.getByTestId("related-websites-section")).toBeInTheDocument();

    // Click candidate 1 (which has all URLs populated)
    const row1 = screen.getByTestId("enriched-row-cand-1");
    fireEvent.click(row1);

    expect(screen.getByTestId("edit-poi-hero-image-input")).toHaveStyle({
      backgroundColor: "rgb(255, 255, 255)",
    });
    expect(screen.getByTestId("related-websites-section")).toBeInTheDocument();
  });
});
