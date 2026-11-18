// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
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

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";

afterEach(() => {
  cleanup();
});

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
      setStyle: vi.fn(),
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
    startBulkEnrichment: vi.fn(),
    getBulkEnrichmentProgress: vi.fn(),
    cancelBulkEnrichment: vi.fn(),
    heartbeatBulkEnrichment: vi.fn(),
    getBulkEnrichmentSummary: vi.fn(),
  },
}));

vi.mock("../../services/api", () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/tags")) {
      return Promise.resolve([]);
    }
    return Promise.resolve({});
  }),
}));

vi.mock("../../services/geocodeService", () => ({
  reverseGeocode: vi.fn().mockResolvedValue({
    street: "123 Trail Road",
    city: "Parkdale",
    country: "USA",
    cached: false,
  }),
  extractCoordinatesFromUrl: vi.fn().mockResolvedValue(null),
  forwardSearch: vi.fn().mockResolvedValue([]),
  forwardGeocode: vi.fn().mockResolvedValue(null),
}));

describe("WorkbenchFilter - Completeness & Exemption Filtering (REQ-EXM-005, 006, 007)", () => {
  const testCandidates: CandidateItem[] = [
    {
      id: "cand-fully-complete",
      job_id: "job-1",
      row_index: 0,
      poi_name: "Fully Populated Resort",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 45.1,
      longitude: -121.5,
      street_address: "100 Timberline Lodge Rd",
      city: "Government Camp",
      state_province: "Oregon",
      country: "United States",
      country_code: "US",
      hero_image_url: "https://example.com/timberline.jpg",
      official_url: "https://timberlinelodge.com",
      related_websites: [{ name: "Official", url: "https://timberlinelodge.com" }],
      no_address: false,
      no_websites: false,
      confidence_score: 95,
      tags: ["Resort"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
    {
      id: "cand-exempted-no-addr",
      job_id: "job-1",
      row_index: 1,
      poi_name: "Mount Hood Summit",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 45.3735,
      longitude: -121.6959,
      street_address: null,
      city: "Government Camp",
      state_province: "Oregon",
      country: "United States",
      country_code: "US",
      hero_image_url: "https://example.com/summit.jpg",
      official_url: "https://usfs.gov/mthood",
      related_websites: [{ name: "USFS", url: "https://usfs.gov/mthood" }],
      no_address: true,
      no_websites: false,
      confidence_score: 90,
      tags: ["Peak"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
    {
      id: "cand-needs-action",
      job_id: "job-1",
      row_index: 2,
      poi_name: "Unknown Wilderness Spring",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 45.2,
      longitude: -121.7,
      street_address: null,
      city: null,
      country: null,
      hero_image_url: null,
      official_url: null,
      related_websites: [],
      no_address: false,
      no_websites: false,
      confidence_score: 40,
      tags: [],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 3,
      candidates: testCandidates,
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
      </ToastProvider>,
    );

  it("renders 'Needs Action' and 'Exempted' options in the completeness filter (REQ-EXM-005)", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("completeness-filter")).toBeInTheDocument();
    });

    const select = screen.getByTestId("completeness-filter") as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((opt) => opt.value);

    expect(optionValues).toContain("needs_action");
    expect(optionValues).toContain("exempted");
  });

  it("filters candidates to only show exempted records when 'Exempted' filter is selected (REQ-EXM-006)", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-exempted-no-addr")).toBeInTheDocument();
    });

    const select = screen.getByTestId("completeness-filter") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "exempted" } });

    await waitFor(() => {
      // Mount Hood Summit has no_address = true, so it should be visible
      expect(screen.getByTestId("candidate-row-cand-exempted-no-addr")).toBeInTheDocument();
      // Fully Populated Resort and Unknown Wilderness Spring have no exemptions, so they shouldn't appear
      expect(screen.queryByTestId("candidate-row-cand-fully-complete")).not.toBeInTheDocument();
      expect(screen.queryByTestId("candidate-row-cand-needs-action")).not.toBeInTheDocument();
    });
  });

  it("filters candidates to only show unexempted incomplete records when 'Needs Action' filter is selected (REQ-EXM-007)", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("candidate-row-cand-needs-action")).toBeInTheDocument();
    });

    const select = screen.getByTestId("completeness-filter") as HTMLSelectElement;

    fireEvent.change(select, { target: { value: "needs_action" } });

    await waitFor(() => {
      // Unknown Wilderness Spring has missing data and no exemptions -> Needs Action
      expect(screen.getByTestId("candidate-row-cand-needs-action")).toBeInTheDocument();
      // Mount Hood Summit has no_address=true covering its missing street address -> Not in Needs Action
      expect(screen.queryByTestId("candidate-row-cand-exempted-no-addr")).not.toBeInTheDocument();
      // Fully Populated Resort has all fields -> Not in Needs Action
      expect(screen.queryByTestId("candidate-row-cand-fully-complete")).not.toBeInTheDocument();
    });
  });
});
