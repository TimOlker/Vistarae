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
});
