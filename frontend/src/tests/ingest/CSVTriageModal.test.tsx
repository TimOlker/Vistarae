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
import { CSVTriageModal } from "../../components/ingest/CSVTriageModal";
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
    })),
    Marker: vi.fn().mockImplementation(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
      remove: vi.fn(),
    })),
    NavigationControl: vi.fn(),
  },
}));

vi.mock("../../services/geocodeService", () => ({
  reverseGeocode: vi.fn().mockResolvedValue({
    street: "123 Main St",
    city: "Chicago",
    state_province: "Illinois",
    country: "United States",
    postal_code: "60601",
    cached: true,
  }),
  forwardGeocode: vi.fn().mockResolvedValue({
    latitude: 41.8819,
    longitude: -87.6278,
    street: "123 Main St",
    city: "Chicago",
    state_province: "Illinois",
    country: "United States",
    postal_code: "60601",
    cached: true,
  }),
}));

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    getJobCandidates: vi.fn(),
    updateCandidate: vi.fn(),
    proceedPhase1: vi.fn(),
    cancelPhase1: vi.fn(),
  },
}));

const mockCandidates: CandidateItem[] = [
  {
    id: "cand-1",
    job_id: "job-100",
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
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_1_triage",
  },
  {
    id: "cand-2",
    job_id: "job-100",
    row_index: 1,
    poi_name: "Monte Alban",
    recommended_disposition: "sublocation",
    user_disposition: null,
    parent_poi_id: null,
    parent_poi_name: null,
    latitude: 17.0438,
    longitude: -96.768,
    photo_directory: "Mexico/Monte Alban",
    confidence_score: 85,
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_1_triage",
  },
  {
    id: "cand-3",
    job_id: "job-100",
    row_index: 2,
    poi_name: "Garfield Park Conservatory",
    recommended_disposition: "update_existing",
    user_disposition: null,
    latitude: 41.886,
    longitude: -87.717,
    photo_directory: "2005/Garfield Park",
    confidence_score: 90,
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_1_triage",
  },
  {
    id: "cand-4",
    job_id: "job-100",
    row_index: 3,
    poi_name: "Mystery Spot",
    recommended_disposition: "accept",
    user_disposition: null,
    latitude: null,
    longitude: null,
    photo_directory: "Mystery",
    confidence_score: 20,
    update_coordinates: false,
    is_skipped: false,
    phase_state: "phase_1_triage",
  },
];

const mockExistingPOIs = [
  {
    id: "poi-parent-1",
    name: "Oaxaca Historic Center",
    latitude: 17.06,
    longitude: -96.72,
  },
];

describe("CSVTriageModal (Phase 1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.getJobCandidates).mockResolvedValue({
      job_id: "job-100",
      total_candidates: 3,
      candidates: mockCandidates,
    });
  });

  it("renders candidate table rows with names, confidence, and directories", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
      expect(screen.getAllByText("Monte Alban")[0]).toBeInTheDocument();
      expect(screen.getAllByText("Garfield Park Conservatory")[0]).toBeInTheDocument();
    });

    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("Japan 2023/Sensoji")).toBeInTheDocument();
  });

  it("displays mini map with coordinates for selected candidate", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-mini-map")).toBeInTheDocument();
    });
  });

  it("maintains and recovers map display when switching between POIs with and without coordinates", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    // Initial POI (Senso-ji) has coordinates -> map container visible
    await waitFor(() => {
      expect(screen.getByTestId("candidate-mini-map-container")).toHaveStyle({ display: "block" });
      expect(screen.getByTestId("mini-map-placeholder")).toHaveStyle({ display: "none" });
    });

    // Select candidate 4 (Mystery Spot - no coordinates)
    fireEvent.click(screen.getByTestId("candidate-row-cand-4"));
    expect(screen.getByTestId("candidate-mini-map-container")).toHaveStyle({ display: "none" });
    expect(screen.getByTestId("mini-map-placeholder")).toHaveStyle({ display: "flex" });

    // Select candidate 1 again (Senso-ji - has coordinates)
    fireEvent.click(screen.getByTestId("candidate-row-cand-1"));
    expect(screen.getByTestId("candidate-mini-map-container")).toHaveStyle({ display: "block" });
    expect(screen.getByTestId("mini-map-placeholder")).toHaveStyle({ display: "none" });
  });

  it("changes candidate disposition dropdown and sends PATCH update", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockCandidates[0],
      user_disposition: "ignore",
    });

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("disposition-select-cand-1")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("disposition-select-cand-1"), {
      target: { value: "ignore" },
    });

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-1", {
      user_disposition: "ignore",
    });
  });

  it("toggles 'Update Coordinates' for update_existing row", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockCandidates[2],
      update_coordinates: true,
    });

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("update-coords-toggle-cand-3")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("update-coords-toggle-cand-3"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-3", {
      update_coordinates: true,
    });
  });

  it("links parent POI when existing POI marker is clicked for sublocation", async () => {
    vi.mocked(ingestApi.updateCandidate).mockResolvedValue({
      ...mockCandidates[1],
      parent_poi_id: "poi-parent-1",
      parent_poi_name: "Oaxaca Historic Center",
    });

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Monte Alban")[0]).toBeInTheDocument();
    });

    // Select candidate 2 (Monte Alban - sublocation)
    fireEvent.click(screen.getByTestId("candidate-row-cand-2"));

    // Click existing POI marker in map panel
    fireEvent.click(screen.getByTestId("poi-marker-poi-parent-1"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-2", {
      parent_poi_id: "poi-parent-1",
      user_disposition: "sublocation",
    });
  });

  it("cancels Phase 1 import and purges staging records", async () => {
    vi.mocked(ingestApi.cancelPhase1).mockResolvedValue({
      job_id: "job-100",
      purged_count: 3,
      message: "Purged",
    });

    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={onClose}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("cancel-triage-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("cancel-triage-button"));

    await waitFor(() => {
      expect(ingestApi.cancelPhase1).toHaveBeenCalledWith("job-100");
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("saves progress and closes without purging when Save & Close is clicked", async () => {
    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={onClose}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("save-close-triage-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("save-close-triage-button"));

    expect(onClose).toHaveBeenCalled();
    expect(ingestApi.cancelPhase1).not.toHaveBeenCalled();
  });

  it("advances non-ignored candidates to Phase 2", async () => {
    vi.mocked(ingestApi.proceedPhase1).mockResolvedValue({
      job_id: "job-100",
      message: "Advanced",
      advanced_count: 3,
      ignored_count: 0,
    });

    const onProceed = vi.fn();

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={onProceed}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("proceed-phase2-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("proceed-phase2-button"));

    await waitFor(() => {
      expect(ingestApi.proceedPhase1).toHaveBeenCalledWith("job-100");
      expect(onProceed).toHaveBeenCalled();
    });
  });
  it("displays Pick on Map button when candidate has missing coordinates and allows picking", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Mystery Spot")).toBeInTheDocument();
    });

    // Select cand-4 which has null coordinates
    fireEvent.click(screen.getByText("Mystery Spot"));

    await waitFor(() => {
      expect(screen.getByTestId("pick-on-map-placeholder-btn")).toBeInTheDocument();
    });

    // Click Pick on Map
    fireEvent.click(screen.getByTestId("pick-on-map-placeholder-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("candidate-mini-map-container")).toBeInTheDocument();
      expect(screen.getByText(/Click map or drag pin to set coordinates/i)).toBeInTheDocument();
    });
  });

  it("handles forward geocoding from address fields", async () => {
    const { forwardGeocode } = await import("../../services/geocodeService");

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-4")).toBeInTheDocument();
    });

    // Edit cand-4
    fireEvent.click(screen.getByTestId("candidate-row-cand-4"));

    await waitFor(() => {
      expect(screen.getByTestId("forward-geocode-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("forward-geocode-btn"));

    await waitFor(() => {
      expect(forwardGeocode).toHaveBeenCalled();
    });
  });

  it("handles reverse geocoding to fill address from coordinates", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-1")).toBeInTheDocument();
    });

    // Edit cand-1 which already has lat/long
    fireEvent.click(screen.getByTestId("candidate-row-cand-1"));

    await waitFor(() => {
      expect(screen.getByTestId("reverse-geocode-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("reverse-geocode-btn"));

    await waitFor(() => {
      expect(reverseGeocode).toHaveBeenCalledWith(35.7147, 139.7966);
    });
  });
  it("attempts to open local folder when directory is clicked", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("open-folder-btn-cand-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("open-folder-btn-cand-1"));
    // Expect open-folder interaction to execute without error
    expect(screen.getByTestId("open-folder-btn-cand-1")).toBeInTheDocument();
  });

  it("supports Sort Priority dropdown between POI and Location with dynamic column ordering and multi-tier sorting", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-1")).toBeInTheDocument();
    });

    // 1. Verify sort priority select exists and defaults to "poi"
    const sortPrioritySelect = screen.getByRole("combobox", {
      name: /sort priority/i,
    }) as HTMLSelectElement;
    expect(sortPrioritySelect).toBeInTheDocument();
    expect(sortPrioritySelect.value).toBe("poi");

    // 2. In "poi" mode, check column headers start with POI Name -> Country -> State / Province -> City / Town
    const tableHeaders = screen.getAllByRole("columnheader");
    expect(tableHeaders[1]).toHaveTextContent(/POI Name/i);
    expect(tableHeaders[2]).toHaveTextContent(/Country/i);
    expect(tableHeaders[3]).toHaveTextContent(/State \/ Province/i);
    expect(tableHeaders[4]).toHaveTextContent(/City \/ Town/i);

    // Verify POI name is bolded
    const sensojiCell = screen.getAllByText("Senso-ji")[0];
    expect(sensojiCell).toHaveStyle({ fontWeight: 700 });

    // 3. Switch to "location" priority
    fireEvent.change(sortPrioritySelect, { target: { value: "location" } });
    expect(sortPrioritySelect.value).toBe("location");

    // Column headers should now start with Country -> State / Province -> City / Town -> POI Name
    const reorderedHeaders = screen.getAllByRole("columnheader");
    expect(reorderedHeaders[1]).toHaveTextContent(/Country/i);
    expect(reorderedHeaders[2]).toHaveTextContent(/State \/ Province/i);
    expect(reorderedHeaders[3]).toHaveTextContent(/City \/ Town/i);
    expect(reorderedHeaders[4]).toHaveTextContent(/POI Name/i);

    // 4. Test column header click overrides sort priority
    fireEvent.click(screen.getByText(/Confidence/i));
    // Header should still keep selected column order while sorting by confidence
    const headersAfterOverride = screen.getAllByRole("columnheader");
    expect(headersAfterOverride[1]).toHaveTextContent(/Country/i);
  });

  it("displays Open Folder button in the Edit Candidate Details panel when candidate has directory", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("candidate-row-cand-1"));

    await waitFor(() => {
      expect(screen.getByTestId("edit-details-open-folder-btn")).toBeInTheDocument();
      expect(screen.getAllByText("Japan 2023/Sensoji").length).toBeGreaterThanOrEqual(2);
    });

    fireEvent.click(screen.getByTestId("edit-details-open-folder-btn"));
    expect(screen.getByTestId("edit-details-open-folder-btn")).toBeInTheDocument();
  });

  it("displays notice in Nearby POIs section when candidate has missing coordinates", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-4")).toBeInTheDocument();
    });

    // Select candidate 4 (Mystery Spot - null coordinates)
    fireEvent.click(screen.getByTestId("candidate-row-cand-4"));

    await waitFor(() => {
      expect(screen.getByTestId("no-coords-nearby-notice")).toBeInTheDocument();
      expect(
        screen.getByText(/Coordinates required to find nearby POIs/i),
      ).toBeInTheDocument();
    });
  });

  it("lists nearby POIs from DB and CSV batch and allows setting and unlinking parent POI", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-2")).toBeInTheDocument();
    });

    // Select candidate 2 (Monte Alban - 17.0438, -96.768)
    fireEvent.click(screen.getByTestId("candidate-row-cand-2"));

    await waitFor(() => {
      // Monte Alban is ~5.4 km from Oaxaca Historic Center (DB)
      expect(screen.getByTestId("nearby-radius-slider")).toBeInTheDocument();
      expect(screen.getByTestId("nearby-poi-poi-parent-1")).toBeInTheDocument();
      expect(screen.getByText("Oaxaca Historic Center")).toBeInTheDocument();
      expect(screen.getByText("DB")).toBeInTheDocument();
    });

    // Adjust radius slider to 1 km (too small to include Oaxaca Historic Center)
    const slider = screen.getByTestId("nearby-radius-slider");
    fireEvent.change(slider, { target: { value: "1" } });

    await waitFor(() => {
      expect(
        screen.getByText(/No POIs found within 1 km/i),
      ).toBeInTheDocument();
    });

    // Increase radius back to 10 km
    fireEvent.change(slider, { target: { value: "10" } });

    await waitFor(() => {
      expect(screen.getByTestId("nearby-poi-poi-parent-1")).toBeInTheDocument();
    });

    // Click "Set as Parent"
    fireEvent.click(screen.getByTestId("poi-marker-poi-parent-1"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-2", {
      parent_poi_id: "poi-parent-1",
      user_disposition: "sublocation",
    });

    // Verify current parent banner and unlink
    await waitFor(() => {
      expect(screen.getByTestId("current-parent-banner")).toBeInTheDocument();
      expect(screen.getByTestId("unlink-parent-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("unlink-parent-btn"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-2", {
      parent_poi_id: null,
      user_disposition: "accept",
    });
  });

  it("displays excluded tally count and renders excluded privacy badge for candidates in exclusion zones", async () => {
    const candidatesWithExcluded: CandidateItem[] = [
      ...mockCandidates,
      {
        id: "cand-excluded",
        job_id: "job-100",
        row_index: 3,
        poi_name: "Private Residence",
        recommended_disposition: "exclude",
        user_disposition: null,
        latitude: 41.8819,
        longitude: -87.6278,
        street_address: "123 Private Way",
        city: "Chicago",
        state_province: "Illinois",
        country: "United States",
        photo_directory: "Private",
        confidence_score: 90,
        update_coordinates: false,
        is_skipped: false,
        phase_state: "phase_1_triage",
      },
    ];

    (ingestApi.getJobCandidates as any).mockResolvedValue({
      job_id: "job-100",
      total_count: candidatesWithExcluded.length,
      candidates: candidatesWithExcluded,
    });

    render(
      <ToastProvider>
        <CSVTriageModal
          isOpen={true}
          jobId="job-100"
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-excluded")).toBeInTheDocument();
    });

    // Check tally indicator has 1 Excluded
    const tallyExcluded = screen.getByTestId("tally-excluded");
    expect(tallyExcluded).toBeInTheDocument();
    expect(tallyExcluded).toHaveTextContent("1 Excluded");

    // Check excluded badge on row
    expect(screen.getByTestId("excluded-badge-cand-excluded")).toBeInTheDocument();
    expect(screen.getByText("Excluded (Privacy Zone)")).toBeInTheDocument();

    // Change disposition of cand-1 to exclude
    const select = screen.getByTestId("disposition-select-cand-1");
    fireEvent.change(select, { target: { value: "exclude" } });

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-1", {
      user_disposition: "exclude",
    });

    // Tally should now show 2 Excluded
    await waitFor(() => {
      expect(screen.getByTestId("tally-excluded")).toHaveTextContent("2 Excluded");
    });
  });

  it("supports multi-select disposition filtering and toggling visibility of candidate rows", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    // When not filtering, visible count at the bottom should NOT be displayed
    expect(screen.queryByTestId("visible-candidates-count")).toBeNull();

    // Open multi-select disposition dropdown
    const dispBtn = screen.getByTestId("disposition-filter-button");
    expect(dispBtn).toHaveTextContent(/All Dispositions \(4\)/i);
    fireEvent.click(dispBtn);

    expect(screen.getByTestId("disposition-filter-dropdown")).toBeInTheDocument();

    // Uncheck "accept"
    const acceptCheckbox = screen.getByTestId("disposition-checkbox-accept");
    expect(acceptCheckbox).toBeChecked();
    fireEvent.click(acceptCheckbox);

    // Accept candidates (Senso-ji, Mystery Spot) should now be hidden in table
    expect(screen.queryByTestId("candidate-row-cand-1")).toBeNull();
    expect(screen.queryByTestId("candidate-row-cand-4")).toBeNull();
    // Sublocation (Monte Alban) and Update (Garfield Park Conservatory) should still be displayed
    expect(screen.getByTestId("candidate-row-cand-2")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-row-cand-3")).toBeInTheDocument();

    // Visible count at bottom must now be displayed!
    const visibleCount = screen.getByTestId("visible-candidates-count");
    expect(visibleCount).toBeInTheDocument();
    expect(visibleCount).toHaveTextContent("2 of 4 Displayed");

    // Click "Clear" to unselect all dispositions
    const clearBtn = screen.getByTestId("deselect-all-dispositions-btn");
    fireEvent.click(clearBtn);

    expect(screen.getByText(/No candidate records match your current filter criteria/i)).toBeInTheDocument();
    expect(screen.getByTestId("visible-candidates-count")).toHaveTextContent("0 of 4 Displayed");

    // Click "All" to reselect all dispositions
    const allBtn = screen.getByTestId("select-all-dispositions-btn");
    fireEvent.click(allBtn);

    expect(screen.getByTestId("candidate-row-cand-1")).toBeInTheDocument();
    expect(screen.queryByTestId("visible-candidates-count")).toBeNull();
  });

  it("displays visible count at the bottom when filtering by search text and hides it when cleared", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    expect(screen.queryByTestId("visible-candidates-count")).toBeNull();

    const searchInput = screen.getByPlaceholderText(/search candidate name/i);
    fireEvent.change(searchInput, { target: { value: "Senso" } });

    // Only Senso-ji is visible
    expect(screen.getByTestId("candidate-row-cand-1")).toBeInTheDocument();
    expect(screen.queryByTestId("candidate-row-cand-2")).toBeNull();
    expect(screen.queryByTestId("candidate-row-cand-3")).toBeNull();

    const visibleCount = screen.getByTestId("visible-candidates-count");
    expect(visibleCount).toBeInTheDocument();
    expect(visibleCount).toHaveTextContent("1 of 4 Displayed");

    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.queryByTestId("visible-candidates-count")).toBeNull();
  });

  it("supports selecting multiple POIs and bulk editing country, state, and city without changing unprovided fields", async () => {
    vi.mocked(ingestApi.updateCandidate).mockImplementation(async (jobId, candId, updates) => {
      const match = mockCandidates.find((c) => c.id === candId);
      return {
        ...match!,
        ...updates,
      } as any;
    });

    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    // Checkbox for cand-1 and cand-2
    const check1 = screen.getByTestId("select-candidate-cand-1");
    const check2 = screen.getByTestId("select-candidate-cand-2");

    fireEvent.click(check1);
    fireEvent.click(check2);

    // Bulk Edit button should appear
    const bulkEditBtn = screen.getByTestId("bulk-edit-button");
    expect(bulkEditBtn).toBeInTheDocument();
    expect(bulkEditBtn).toHaveTextContent("Bulk Edit (2)");

    fireEvent.click(bulkEditBtn);

    // Modal opens
    expect(screen.getByTestId("bulk-edit-modal-form")).toBeInTheDocument();

    // Fill in only City / Town = "Kyoto", leave Country and State blank
    const cityInput = screen.getByTestId("bulk-city-input");
    fireEvent.change(cityInput, { target: { value: "Kyoto" } });

    const confirmBtn = screen.getByTestId("confirm-bulk-edit-button");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-1", {
        city: "Kyoto",
      });
      expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-100", "cand-2", {
        city: "Kyoto",
      });
    });

    // Modal should close and selection should be cleared
    await waitFor(() => {
      expect(screen.queryByTestId("bulk-edit-modal-form")).toBeNull();
      expect(screen.queryByTestId("bulk-edit-button")).toBeNull();
    });
  });

  it("supports Select All visible candidates checkbox in table header", async () => {
    render(
      <ToastProvider>
        <CSVTriageModal
          jobId="job-100"
          isOpen={true}
          onClose={vi.fn()}
          onProceedToPhase2={vi.fn()}
          existingPOIs={mockExistingPOIs}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Senso-ji")[0]).toBeInTheDocument();
    });

    const selectAllCheckbox = screen.getByTestId("select-all-candidates-checkbox");
    expect(selectAllCheckbox).not.toBeChecked();

    // Select all
    fireEvent.click(selectAllCheckbox);

    expect(screen.getByTestId("bulk-edit-button")).toHaveTextContent("Bulk Edit (4)");

    // Click Deselect button
    const deselectBtn = screen.getByTestId("deselect-all-button");
    fireEvent.click(deselectBtn);

    expect(screen.queryByTestId("bulk-edit-button")).toBeNull();
    expect(selectAllCheckbox).not.toBeChecked();
  });
});