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

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    getJobCandidates: vi.fn(),
    updateCandidate: vi.fn(),
    commitPhase2: vi.fn(),
    cancelPhase2: vi.fn(),
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
    latitude: 41.886,
    longitude: -87.717,
    photo_directory: "2005/Garfield Park",
    confidence_score: 90,
    description: "Botanical sanctuary featuring historic glasshouses and palm collections.",
    reason_to_visit: "Marvel at lush desert and tropical plant rooms.",
    tags: ["Botanical", "Chicago"],
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
      total_candidates: 2,
      candidates: mockEnrichedCandidates,
    });
  });

  it("renders enriched candidate table with descriptions, reasons to visit, and tags", async () => {
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

    expect(screen.getByText(/Ancient Buddhist temple in Asakusa/)).toBeInTheDocument();
    expect(screen.getAllByText(/Experience iconic Edo atmosphere/)[0]).toBeInTheDocument();
    expect(screen.getByText("Temple")).toBeInTheDocument();
    expect(screen.getByText("2 Ready to Commit")).toBeInTheDocument();
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

  it("opens POI edit modal, allows editing description/tags, and applies changes", async () => {
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
      expect(screen.getByTestId("edit-poi-btn-cand-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("edit-poi-btn-cand-1"));

    expect(screen.getByTestId("poi-edit-drawer")).toBeInTheDocument();

    const descInput = screen.getByTestId("edit-poi-description-input");
    fireEvent.change(descInput, { target: { value: "Updated description text." } });

    fireEvent.click(screen.getByTestId("save-edit-button"));

    expect(ingestApi.updateCandidate).toHaveBeenCalledWith("job-200", "cand-1", {
      poi_name: "Senso-ji",
      description: "Updated description text.",
      reason_to_visit: "Experience iconic Edo atmosphere and temple architecture.",
      tags: ["Temple", "Historic", "Buddhism"],
      street_address: "2 Chome-3-1 Asakusa",
      city: "Taito City",
      update_coordinates: false,
    });
  });

  it("displays 'Update Existing POI Coordinates' toggle in edit drawer for update candidates", async () => {
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
      expect(screen.getByTestId("edit-poi-btn-cand-2")).toBeInTheDocument();
    });

    // Open edit modal for Garfield Park Conservatory (update_existing)
    fireEvent.click(screen.getByTestId("edit-poi-btn-cand-2"));

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
});
