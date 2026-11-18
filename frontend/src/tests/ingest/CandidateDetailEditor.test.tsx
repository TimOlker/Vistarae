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
      return Promise.resolve([
        { name: "Scenic", slug: "scenic" },
      ]);
    }
    return Promise.resolve({});
  }),
}));

vi.mock("../../services/geocodeService", () => ({
  reverseGeocode: vi.fn().mockResolvedValue({
    street: "123 Mountain Pass",
    city: "Highland",
    country: "USA",
    cached: false,
  }),
  extractCoordinatesFromUrl: vi.fn().mockResolvedValue(null),
  forwardSearch: vi.fn().mockResolvedValue([]),
  forwardGeocode: vi.fn().mockResolvedValue(null),
}));

describe("CandidateDetailEditor - Exemption Checkboxes & Rules (REQ-EXM-008, 010, 011, 026, 027)", () => {
  const candidateWithMissingData: CandidateItem = {
    id: "cand-missing-1",
    job_id: "job-1",
    row_index: 0,
    poi_name: "Eagle Peak Overlook",
    recommended_disposition: "accept" as any,
    user_disposition: null,
    matched_existing_poi_id: null,
    parent_poi_id: null,
    latitude: 45.1234,
    longitude: -121.5678,
    street_address: null,
    city: "Hood River",
    state_province: "Oregon",
    country: "United States",
    country_code: "US",
    hero_image_url: null,
    official_url: null,
    related_websites: [],
    no_address: false,
    no_websites: false,
    confidence_score: 85,
    tags: ["Viewpoint"],
    phase_state: "phase_1_triage" as any,
    created_at: "2026-11-02T00:00:00Z",
    updated_at: "2026-11-02T00:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [{ ...candidateWithMissingData }],
    });
    vi.mocked(ingestApi.updateStagingCandidate).mockResolvedValue({
      ...candidateWithMissingData,
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

  it("renders dedicated Data Availability section with independent checkboxes", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("data-availability-section")).toBeInTheDocument();
    });

    const noAddressCheckbox = screen.getByTestId("no-address-checkbox") as HTMLInputElement;
    const noWebsitesCheckbox = screen.getByTestId("no-websites-checkbox") as HTMLInputElement;

    expect(noAddressCheckbox).toBeInTheDocument();
    expect(noWebsitesCheckbox).toBeInTheDocument();
    expect(noAddressCheckbox.checked).toBe(false);
    expect(noWebsitesCheckbox.checked).toBe(false);
  });

  it("toggles 'No address available' checkbox, disables street address input, and shows banner", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("no-address-checkbox")).toBeInTheDocument();
    });

    const noAddressCheckbox = screen.getByTestId("no-address-checkbox") as HTMLInputElement;
    const streetInput = screen.getByTestId("street-address-input") as HTMLInputElement;

    expect(streetInput).not.toBeDisabled();

    // Check No Address
    fireEvent.click(noAddressCheckbox);
    expect(noAddressCheckbox.checked).toBe(true);
    expect(streetInput).toBeDisabled();
    expect(screen.getByTestId("no-address-banner")).toBeInTheDocument();

    // Uncheck No Address
    fireEvent.click(noAddressCheckbox);
    expect(noAddressCheckbox.checked).toBe(false);
    expect(streetInput).not.toBeDisabled();
    expect(screen.queryByTestId("no-address-banner")).not.toBeInTheDocument();
  });

  it("auto-resets no_address when user enters a street address (REQ-EXM-026)", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("no-address-checkbox")).toBeInTheDocument();
    });

    const noAddressCheckbox = screen.getByTestId("no-address-checkbox") as HTMLInputElement;
    const streetInput = screen.getByTestId("street-address-input") as HTMLInputElement;

    // Toggle on
    fireEvent.click(noAddressCheckbox);
    expect(noAddressCheckbox.checked).toBe(true);

    // Enter non-empty street address
    fireEvent.change(streetInput, { target: { value: "100 Skyline Trail" } });
    expect(noAddressCheckbox.checked).toBe(false);
    expect(streetInput.value).toBe("100 Skyline Trail");
  });

  it("saves updated exemption flags on candidate save (REQ-EXM-011)", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("no-address-checkbox")).toBeInTheDocument();
    });

    const noAddressCheckbox = screen.getByTestId("no-address-checkbox");
    const noWebsitesCheckbox = screen.getByTestId("no-websites-checkbox");

    fireEvent.click(noAddressCheckbox);
    fireEvent.click(noWebsitesCheckbox);

    const saveBtn = screen.getByTestId("save-candidate-changes-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(ingestApi.updateStagingCandidate).toHaveBeenCalledWith(
        "job-1",
        "cand-missing-1",
        expect.objectContaining({
          no_address: true,
          no_websites: true,
        }),
      );
    });
  });
});
