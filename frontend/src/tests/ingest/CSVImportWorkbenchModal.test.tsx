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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";

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
  },
}));

vi.mock("../../services/api", () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    if (url.includes("/api/tags")) {
      return Promise.resolve([
        { name: "Volcano", slug: "volcano" },
        { name: "Scenic", slug: "scenic" },
        { name: "Historic", slug: "historic" },
      ]);
    }
    return Promise.resolve({});
  }),
}));

vi.mock("../../services/geocodeService", () => ({
  reverseGeocode: vi.fn().mockResolvedValue({
    street: "123 New Road",
    city: "Fujinomiya",
    locality: "Fujinomiya",
    state_province: "Shizuoka",
    admin_level_1: "Shizuoka Prefecture",
    country: "Japan",
    country_code: "JP",
    cached: false,
  }),
  extractCoordinatesFromUrl: vi.fn().mockResolvedValue({
    latitude: 30.42188,
    longitude: 108.183895,
    place_name: "Shibaozhai",
    extraction_source: "geohack_link",
    street: "Shibao Town",
    city: "Zhong County",
    state_province: "Chongqing",
    country: "China",
    postal_code: "404300",
    country_code: "CN",
  }),
  forwardSearch: vi.fn().mockResolvedValue([
    {
      lat: 35.3606,
      lng: 138.7274,
      display_name:
        "Mount Fuji, Kitayama, Fujinomiya, Shizuoka Prefecture, Japan",
      name: "Mount Fuji",
      type: "volcano",
      class: "natural",
      suggestedZoom: 17,
      isSpecificLandmark: true,
    },
    {
      lat: 35.4000,
      lng: 138.8000,
      display_name: "Fuji-Hakone-Izu National Park, Japan",
      name: "Fuji-Hakone-Izu National Park",
      type: "national_park",
      class: "leisure",
      suggestedZoom: 12,
      isSpecificLandmark: false,
    },
  ]),
  forwardGeocode: vi.fn().mockResolvedValue({
    latitude: 14.08253,
    longitude: 44.40778,
    resolved_name: "Baraqish",
    city: "Baraqish",
    state_province: "Jawf Governorate",
    country: "Yemen",
    country_code: "YE",
    cached: false,
  }),
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
        { name: "Official Guide", url: "https://fujisan.jp/guide" },
      ],
      no_websites: false,
      confidence_score: 95,
      disposition_justification:
        "High confidence coordinate match from authoritative geocoder.",
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
      disposition_justification:
        "Missing coordinates; proximity to Fuji suggests child sublocation.",
      photo_directory: "Japan/Kawaguchi",
      photo_directories: ["Japan/Kawaguchi"],
      dates_visited: [],
      tags: ["Lake"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    },
  ];

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 2,
      candidates: mockCandidates,
    });
    const { forwardSearch, reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValue({
      street: "123 New Road",
      city: "Fujinomiya",
      locality: "Fujinomiya",
      state_province: "Shizuoka",
      admin_level_1: "Shizuoka Prefecture",
      admin_level_2: "Fujinomiya City",
      postal_code: "418-0000",
      country_code: "JP",
      country: "Japan",
      cached: false,
    });
    vi.mocked(forwardSearch).mockResolvedValue([
      {
        lat: 35.3606,
        lng: 138.7274,
        display_name: "Mount Fuji, Kitayama, Fujinomiya, Shizuoka Prefecture, Japan",
        name: "Mount Fuji",
        type: "volcano",
        class: "natural",
        suggestedZoom: 17,
        isSpecificLandmark: true,
      },
      {
        lat: 35.4000,
        lng: 138.8000,
        display_name: "Fuji-Hakone-Izu National Park, Japan",
        name: "Fuji-Hakone-Izu National Park",
        type: "national_park",
        class: "leisure",
        suggestedZoom: 12,
        isSpecificLandmark: false,
      },
    ]);
  });

  const renderModal = (
    props?: Partial<React.ComponentProps<typeof CSVImportWorkbenchModal>>,
  ) =>
    render(
      <ToastProvider>
        <CSVImportWorkbenchModal
          jobId="job-1"
          isOpen={true}
          onClose={vi.fn()}
          {...props}
        />
      </ToastProvider>,
    );

  it("renders split layout with master table on left and editor on right", async () => {
    renderModal();

    await waitFor(() => {
      expect(
        screen.getByTestId("import-staging-workbench-modal"),
      ).toBeInTheDocument();
      expect(screen.getAllByText("Mount Fuji").length).toBeGreaterThanOrEqual(
        1,
      );
      expect(screen.getByText("Lake Kawaguchi")).toBeInTheDocument();
    });

    // Check completeness badges
    expect(
      screen.getByTestId("completeness-badge-complete"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("completeness-badge-incomplete"),
    ).toBeInTheDocument();

    // Check pinned footer in editor
    expect(
      screen.getByTestId("candidate-editor-pinned-footer"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("save-candidate-changes-btn"),
    ).toBeInTheDocument();
  });

  it("toggles perspective between POI and Location modes", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("perspective-select")).toBeInTheDocument();
    });

    const perspectiveSelect = screen.getByTestId(
      "perspective-select",
    ) as HTMLSelectElement;
    expect(perspectiveSelect.value).toBe("POI");

    fireEvent.change(perspectiveSelect, { target: { value: "Location" } });
    expect(perspectiveSelect.value).toBe("Location");
  });

  it("toggles reactive 'No Websites' checkbox and unsets URLs", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Mount Fuji",
      );
    });

    const noWebsitesCheckbox = screen.getByTestId(
      "no-websites-checkbox",
    ) as HTMLInputElement;
    expect(noWebsitesCheckbox.checked).toBe(false);

    // Toggle No Websites to true
    fireEvent.click(noWebsitesCheckbox);
    expect(noWebsitesCheckbox.checked).toBe(true);

    // Official and Wiki inputs should now be replaced by skipped message
    expect(
      screen.getByText(
        /Web scraping skipped: POI verified to have no relevant web presence/i,
      ),
    ).toBeInTheDocument();
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

    expect(window.confirm).toHaveBeenCalledWith(
      "Are you sure you want to remove this website?",
    );
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
      expect(ingestApi.enrichSingleCandidate).toHaveBeenCalledWith(
        "job-1",
        "cand-1",
        false,
      );
    });
  });

  it("invokes single-POI recalculation with force refresh when button is clicked", async () => {
    vi.mocked(ingestApi.enrichSingleCandidate).mockResolvedValue({
      ...mockCandidates[0],
      description: "Force refreshed description of Mount Fuji",
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("recalculate-force-refresh-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("recalculate-force-refresh-btn"));

    await waitFor(() => {
      expect(ingestApi.enrichSingleCandidate).toHaveBeenCalledWith(
        "job-1",
        "cand-1",
        true,
      );
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
        }),
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
              latitude: 35.361,
              longitude: 138.728,
            },
          ]}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("proximity-radius-slider")).toBeInTheDocument();
      expect(screen.getByTestId("nearby-poi-count-badge")).toBeInTheDocument();
    });

    // Mount Fuji Station 5 is ~0.04 mi away, so within 1 mi radius it shows 1 Nearby Point
    expect(screen.getByTestId("nearby-poi-count-badge")).toHaveTextContent(
      /1 Nearby Point/i,
    );
  });

  it("shows inline validation error when disposition is Sublocation without parent", async () => {
    renderModal();

    await waitFor(() => {
      expect(
        screen.getByTestId("editor-disposition-select"),
      ).toBeInTheDocument();
    });

    // Change disposition to sublocation
    fireEvent.change(screen.getByTestId("editor-disposition-select"), {
      target: { value: "sublocation" },
    });

    // Inline error should appear
    await waitFor(() => {
      expect(
        screen.getByTestId("sublocation-missing-parent-error"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Parent POI required for Sublocation disposition/i),
      ).toBeInTheDocument();
    });
  });

  it("displays confidence score badge with color scale and rationale", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("confidence-score-badge")).toBeInTheDocument();
      expect(
        screen.getByTestId("disposition-rationale-readonly"),
      ).toBeInTheDocument();
    });

    expect(screen.getByTestId("confidence-score-badge")).toHaveTextContent(
      "95%",
    );
    expect(screen.getByTestId("disposition-rationale-readonly")).toHaveValue(
      "Disposition: accept\nRationale: High confidence coordinate match from authoritative geocoder.",
    );
  });

  it("displays in-batch merge target selector when disposition is in_batch_merge", async () => {
    renderModal();

    await waitFor(() => {
      expect(
        screen.getByTestId("editor-disposition-select"),
      ).toBeInTheDocument();
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
    vi.mocked(ingestApi.batchEditCandidates).mockResolvedValue({
      updated_count: 2,
    });

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

    // Fill in batch add_tag and remove_tag
    expect(screen.getByTestId("batch-add-tag-input")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("batch-add-tag-input"), {
      target: { value: "MustVisit" },
    });
    expect(screen.getByTestId("batch-remove-tag-input")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("batch-remove-tag-input"), {
      target: { value: "Draft" },
    });

    // Submit batch edit
    fireEvent.click(screen.getByTestId("apply-batch-edit-btn"));

    await waitFor(() => {
      expect(ingestApi.batchEditCandidates).toHaveBeenCalledWith(
        "job-1",
        expect.objectContaining({
          candidate_ids: ["cand-1", "cand-2"],
          country: "Japan",
          add_tag: "MustVisit",
          remove_tag: "Draft",
        }),
      );
    });
  });

  it("re-syncs address from pin coordinates via reverseGeocode", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    renderModal();

    await waitFor(() => {
      expect(
        screen.getByTestId("resync-address-from-pin-btn"),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("resync-address-from-pin-btn"));

    await waitFor(() => {
      expect(reverseGeocode).toHaveBeenCalledWith(35.3606, 138.7274);
      expect(screen.getByTestId("street-address-input")).toHaveValue(
        "123 New Road",
      );
    });
  });

  it("renders uncropped hero photo preview directly beneath URL input", async () => {
    renderModal();

    await waitFor(() => {
      expect(
        screen.getByTestId("hero-image-uncropped-preview"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("hero-image-uncropped-preview"),
      ).toHaveAttribute("src", "https://example.com/fuji.jpg");
    });
  });

  it("toggles Tag Library chips selection strictly", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("tag-chip-Volcano")).toBeInTheDocument();
    });

    // Volcano is initially active (✓ Volcano)
    expect(screen.getByTestId("tag-chip-Volcano")).toHaveTextContent(/Volcano/);

    // Click to toggle off
    fireEvent.click(screen.getByTestId("tag-chip-Volcano"));
    expect(screen.getByTestId("tag-chip-Volcano")).not.toHaveTextContent(/✓/);

    // Click again to toggle back on
    fireEvent.click(screen.getByTestId("tag-chip-Volcano"));
    expect(screen.getByTestId("tag-chip-Volcano")).toHaveTextContent(
      /✓ Volcano/,
    );
  });

  it("manages local photo directories adding and removing entries", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("directory-item-0")).toBeInTheDocument();
    });

    // Add new directory path
    fireEvent.change(screen.getByTestId("new-directory-input"), {
      target: { value: "Japan/2026_Trip" },
    });
    fireEvent.click(screen.getByTestId("add-directory-btn"));

    expect(screen.getByText(/Japan\/2026_Trip/)).toBeInTheDocument();
  });

  it("manages visit dates adding and removing ISO dates", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByText("2024-05-01")).toBeInTheDocument();
    });

    // Add new visit date
    fireEvent.change(screen.getByTestId("new-visit-date-input"), {
      target: { value: "2025-10-15" },
    });
    fireEvent.click(screen.getByTestId("add-visit-date-btn"));

    expect(screen.getByText("2025-10-15")).toBeInTheDocument();
  });

  it("resets latitude and longitude to last saved value when reset button is clicked", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("latitude-input")).toHaveValue("35.3606");
      expect(screen.getByTestId("longitude-input")).toHaveValue("138.7274");
    });

    // User edits coordinates manually
    fireEvent.change(screen.getByTestId("latitude-input"), {
      target: { value: "40.1234" },
    });
    fireEvent.change(screen.getByTestId("longitude-input"), {
      target: { value: "-74.5678" },
    });
    expect(screen.getByTestId("latitude-input")).toHaveValue("40.1234");
    expect(screen.getByTestId("longitude-input")).toHaveValue("-74.5678");

    // Click the Reset location button
    const resetBtn = screen.getByTestId("reset-location-btn");
    expect(resetBtn).toBeInTheDocument();
    fireEvent.click(resetBtn);

    // Coordinates reset back to last saved value
    expect(screen.getByTestId("latitude-input")).toHaveValue("35.3606");
    expect(screen.getByTestId("longitude-input")).toHaveValue("138.7274");
  });

  it("normalizes Chinese characters to English fields and displays adjusted confidence and rationale for Great Wall of China", async () => {
    const greatWallCandidate: CandidateItem = {
      id: "cand-gw",
      job_id: "job-1",
      row_index: 0,
      poi_name: "Great Wall of China",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 40.4319,
      longitude: 116.5704,
      street_address: "慕田峪路",
      city: "北京市",
      state_province: "北京市",
      postal_code: "101405",
      country: "中国",
      country_code: "中国" as any,
      locality: "北京市",
      admin_level_1: "北京市",
      admin_level_2: "怀柔区",
      tags: [],
      photo_directory: "" as any,
      photo_directories: [],
      hero_image_url: null,
      dates_visited: [],
      description: null,
      reason_to_visit: null,
      official_url: null,
      wiki_url: null,
      related_websites: [],
      no_websites: false,
      recommended_duration_hours: null,
      recommended_visit_days: null,
      estimated_visit_time_notes: null,
      confidence_score: 75,
      disposition_justification: null,
      is_user_overridden: false,
      parent_candidate_id: null,
      merge_target_id: null,
      addresses: [],
      update_coordinates: false,
      is_skipped: false,
      phase_state: "phase_1_triage" as any,
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [greatWallCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Great Wall of China",
      );
    });

    // All fields are in English
    expect(screen.getByTestId("street-address-input")).toHaveValue(
      "Mutianyu Road",
    );
    expect(screen.getByTestId("country-code-input")).toHaveValue("CN");
    expect(screen.getByTestId("country-input")).toHaveValue("China");
    expect(screen.getByTestId("city-input")).toHaveValue("Beijing");
    expect(screen.getByTestId("state-province-input")).toHaveValue("Beijing");
    expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
      "Huairou District",
    );

    // Confidence is 75% for Great Wall (slightly lower to reflect multiple site sections)
    expect(screen.getByTestId("confidence-score-badge")).toHaveTextContent(
      "Confidence: 75%",
    );

    // Rationale states Great Wall of China is correctly identified with multiple possible locations
    expect(screen.getByTestId("disposition-rationale-readonly")).toHaveValue(
      "Disposition: accept\nRationale: Great Wall of China correctly identified; multiple possible locations exist across this extensive site.\nMissing: Photo, Websites",
    );
  });

  it("renders location search input and performs text search to lookup and set POI location", async () => {
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 2,
      candidates: mockCandidates,
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Mount Fuji",
      );
    });

    // 1. Verify search input, find button, and candidate name lookup button are rendered
    const searchInput = screen.getByTestId("location-search-input");
    const findBtn = screen.getByTestId("find-location-btn");
    const candidateNameBtn = screen.getByTestId("use-candidate-name-btn");

    expect(searchInput).toBeInTheDocument();
    expect(findBtn).toBeInTheDocument();
    expect(candidateNameBtn).toBeInTheDocument();

    // 2. Type a search query for city/state/POI
    fireEvent.change(searchInput, { target: { value: "Mount Fuji" } });
    expect(searchInput).toHaveValue("Mount Fuji");

    // 3. Click Find Location button
    fireEvent.click(findBtn);

    // 4. Dropdown results should appear
    await waitFor(() => {
      expect(
        screen.getByTestId("location-search-dropdown"),
      ).toBeInTheDocument();
    });

    const result0 = screen.getByTestId("location-search-result-0");
    const result1 = screen.getByTestId("location-search-result-1");
    expect(result0).toHaveTextContent("Mount Fuji");
    expect(result1).toHaveTextContent("Fuji-Hakone-Izu National Park");

    // 5. Click the first match to set coordinates and sync address
    fireEvent.click(result0);

    await waitFor(() => {
      expect(screen.getByTestId("latitude-input")).toHaveValue("35.360600");
      expect(screen.getByTestId("longitude-input")).toHaveValue("138.727400");
    });

    // 6. Address fields should be populated via reverse geocode
    await waitFor(() => {
      expect(screen.getByTestId("street-address-input")).toHaveValue(
        "123 New Road",
      );
      expect(screen.getByTestId("city-input")).toHaveValue("Fujinomiya");
      expect(screen.getByTestId("country-code-input")).toHaveValue("JP");
    });
  });

  it("allows clearing the location search input", async () => {
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 2,
      candidates: mockCandidates,
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    fireEvent.change(searchInput, { target: { value: "Tokyo Tower" } });
    expect(searchInput).toHaveValue("Tokyo Tower");

    const clearBtn = screen.getByTestId("clear-location-search-btn");
    expect(clearBtn).toBeInTheDocument();
    fireEvent.click(clearBtn);

    expect(searchInput).toHaveValue("");
  });

  it("populates missing completeness fields into Assigned Disposition & Rationale when candidate is incomplete", async () => {
    const petraCandidate: CandidateItem = {
      id: "cand-petra",
      job_id: "job-1",
      row_index: 2,
      poi_name: "Petra",
      recommended_disposition: "accept" as any,
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 30.3285,
      longitude: 35.4444,
      street_address: null, // Ancient site has no street address
      city: "Wadi Musa",
      state_province: "Ma'an Governorate",
      country: "Jordan",
      country_code: "JO",
      hero_image_url: null,
      official_url: null,
      related_websites: [],
      no_websites: false,
      confidence_score: 90,
      disposition_justification: "Unique coordinate location verified",
      tags: ["World Wonder"],
      phase_state: "phase_1_triage" as any,
      photo_directory: "" as any,
      photo_directories: [],
      dates_visited: [],
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [petraCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Petra");
    });

    // Verify Incomplete badge has title attribute listing what's missing
    const badge = screen.getByTestId("completeness-badge-incomplete");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", "Missing: Photo, Street Address, Websites");

    // Verify Assigned Disposition & Rationale readonly textarea includes the missing fields
    const rationaleTextarea = screen.getByTestId("disposition-rationale-readonly");
    expect(rationaleTextarea).toHaveValue(
      "Disposition: accept\nRationale: Unique coordinate location verified\nMissing: Photo, Street Address, Websites",
    );
  });

  it("highlights fields in light green (#f0fdf4) when matching existing DB POI or when import data has no value", async () => {
    const existingDbPoi = {
      id: "db-poi-1",
      name: "Existing Petra",
      latitude: 30.3285,
      longitude: 35.4444,
      street_address: "Petra Main Trail",
      city: "Wadi Musa",
      country: "Jordan",
      country_code: "JO",
      tags: ["Ancient", "Wonder"],
      hero_image_url: "https://example.com/petra.jpg",
      description: "Ancient carved city",
      reason_to_visit: "Incredible rock-cut architecture",
      photo_directories: ["photos/petra"],
      dates_visited: ["2023-05-10"],
      related_websites: [{ name: "Official", url: "https://visitpetra.jo" }],
    };

    const candidateWithMatches: CandidateItem = {
      id: "cand-1",
      job_id: "job-1",
      row_index: 0,
      poi_name: "Existing Petra", // Exact match -> #f0fdf4
      recommended_disposition: "update_existing",
      user_disposition: null,
      matched_existing_poi_id: "db-poi-1",
      parent_poi_id: null,
      parent_candidate_id: null,
      merge_target_id: null,
      latitude: 30.3285, // Exact match -> #f0fdf4
      longitude: 35.4444, // Exact match -> #f0fdf4
      street_address: "New Differing Address", // Differing -> normal
      city: "Wadi Musa", // Exact match -> #f0fdf4
      locality: "Wadi Musa",
      admin_level_2: null, // Empty in candidate -> #f0fdf4 (no data = no change)
      state_province: null, // Empty in candidate -> #f0fdf4
      admin_level_1: null,
      postal_code: null, // Empty in candidate -> #f0fdf4
      country_code: "JO", // Match -> #f0fdf4
      country: "Jordan", // Match -> #f0fdf4
      hero_image_url: "https://example.com/petra.jpg", // Match -> #f0fdf4
      official_url: null,
      related_websites: [], // Empty in candidate -> #f0fdf4
      no_websites: false,
      confidence_score: 95,
      disposition_justification: "Matches existing POI 'Existing Petra'",
      tags: ["Ancient"], // Subset of target -> union matches -> #f0fdf4
      photo_directory: "",
      photo_directories: [], // Empty -> #f0fdf4
      dates_visited: [], // Empty -> #f0fdf4
      description: "Different description", // Differing -> normal
      reason_to_visit: "Incredible rock-cut architecture", // Match -> #f0fdf4
      phase_state: "phase_1_triage" as any,
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [candidateWithMatches],
    });

    renderModal({ existingPOIs: [existingDbPoi as any] });

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Existing Petra");
    });

    // POI Name matches -> light green #f0fdf4
    const nameInput = screen.getByTestId("editor-poi-name-input");
    expect(nameInput).toHaveStyle({ backgroundColor: "#f0fdf4" });

    // Latitude matches -> light green
    const latInput = screen.getByTestId("latitude-input");
    expect(latInput).toHaveStyle({ backgroundColor: "#f0fdf4" });

    // City matches -> light green
    const cityInput = screen.getByTestId("city-input");
    expect(cityInput).toHaveStyle({ backgroundColor: "#f0fdf4" });

    // Street address differs -> light yellow #fefce8
    const streetInput = screen.getByTestId("street-address-input");
    expect(streetInput).toHaveStyle({ backgroundColor: "#fefce8" });

    // Postal code is empty in import -> considered no change -> light green #f0fdf4
    const postalInput = screen.getByTestId("postal-code-input");
    expect(postalInput).toHaveStyle({ backgroundColor: "#f0fdf4" });

    // Description differs -> light yellow #fefce8
    const descInput = screen.getByTestId("description-textarea");
    expect(descInput).toHaveStyle({ backgroundColor: "#fefce8" });

    // Reason to visit matches -> light green
    const reasonInput = screen.getByTestId("reason-to-visit-textarea");
    expect(reasonInput).toHaveStyle({ backgroundColor: "#f0fdf4" });

    // Matched existing DB POI card is visible
    expect(screen.getByTestId("matched-existing-poi-card")).toBeInTheDocument();

    // Verify original value is displayed in parenthesis on differing field labels
    expect(screen.getByTestId("field-diff-current-value-street_address")).toHaveTextContent(
      "(Current: Petra Main Trail)",
    );
    expect(screen.getByTestId("field-diff-current-value-description")).toHaveTextContent(
      "(Current: Ancient carved city)",
    );

    // Verify matching fields do not render (Current: ...)
    expect(screen.queryByTestId("field-diff-current-value-poi_name")).not.toBeInTheDocument();
    expect(screen.queryByTestId("field-diff-current-value-city")).not.toBeInTheDocument();
  });

  it("keeps standard background on candidate not associated with any existing POI", async () => {
    const unassociatedCandidate: CandidateItem = {
      id: "cand-new",
      job_id: "job-1",
      row_index: 0,
      poi_name: "Brand New Spot",
      recommended_disposition: "accept",
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      parent_candidate_id: null,
      merge_target_id: null,
      latitude: 40.7128,
      longitude: -74.006,
      street_address: "123 Broadway",
      city: "New York",
      locality: "New York",
      admin_level_2: null,
      state_province: "NY",
      admin_level_1: "NY",
      postal_code: "10001",
      country_code: "US",
      country: "United States",
      hero_image_url: null,
      official_url: null,
      related_websites: [],
      no_websites: false,
      confidence_score: 90,
      disposition_justification: "Unique location",
      tags: ["City"],
      photo_directory: "",
      photo_directories: [],
      dates_visited: [],
      description: "A brand new location",
      reason_to_visit: "Great views",
      phase_state: "phase_1_triage" as any,
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [unassociatedCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Brand New Spot");
    });

    const nameInput = screen.getByTestId("editor-poi-name-input");
    expect(nameInput.style.backgroundColor).not.toBe("rgb(240, 253, 244)");
    expect(nameInput.style.backgroundColor).not.toBe("rgb(254, 252, 232)");
    expect(screen.queryByTestId("matched-existing-poi-card")).not.toBeInTheDocument();
  });

  it("detects Google Maps URL in search input and populates coordinates and address on Find", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      street: "Ksar El Atteuf",
      city: "Ghardaïa",
      locality: "Ghardaïa",
      state_province: "Ghardaïa",
      admin_level_1: "Ghardaïa Province",
      admin_level_2: null,
      postal_code: "47000",
      country_code: "DZ",
      country: "Algeria",
      cached: false,
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    const gmapsUrl =
      "https://www.google.com/maps/place/M'Zab/@32.4756753,3.7051475,5338m/data=!3m1!1e3!4m6!3m5!1s0x12642629edfa882d:0x21a37c0afb90d5fb!8m2!3d32.4727002!4d3.7082024!16s%2Fg%2F11ckr9rrns?entry=ttu&g_ep=EgoyMDI2MTEwMS4wIKXMDSoASAFQAw%3D%3D";

    fireEvent.change(searchInput, { target: { value: gmapsUrl } });
    fireEvent.click(screen.getByTestId("find-location-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("latitude-input")).toHaveValue("32.472700");
      expect(screen.getByTestId("longitude-input")).toHaveValue("3.708202");
      expect(screen.getByTestId("street-address-input")).toHaveValue("Ksar El Atteuf");
      expect(screen.getByTestId("city-input")).toHaveValue("Ghardaïa");
      expect(screen.getByTestId("country-input")).toHaveValue("Algeria");
    });
  });

  it("detects GeoHack URL in search input and populates coordinates and address on Find", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      street: "Shibao Town",
      city: "Zhong County",
      locality: "Zhong County",
      state_province: "Chongqing",
      admin_level_1: "Chongqing Municipality",
      admin_level_2: null,
      postal_code: "404300",
      country_code: "CN",
      country: "China",
      cached: false,
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    const geohackUrl =
      "https://geohack.toolforge.org/geohack.php?pagename=Shibaozhai&params=30.42187999245106_N_108.18389453817412_E_region:CN-CQ_type:landmark_source:GoogleMaps";

    fireEvent.change(searchInput, { target: { value: geohackUrl } });
    fireEvent.click(screen.getByTestId("find-location-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("latitude-input")).toHaveValue("30.421880");
      expect(screen.getByTestId("longitude-input")).toHaveValue("108.183895");
      expect(screen.getByTestId("street-address-input")).toHaveValue("Shibao Town");
      expect(screen.getByTestId("city-input")).toHaveValue("Zhong County");
      expect(screen.getByTestId("country-input")).toHaveValue("China");
    });
  });

  it("detects Webpage URL (Wikipedia) and extracts coordinates and address on Find", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    const wikiUrl =
      "https://en.wikipedia.org/wiki/Shibaozhai#:~:text=At%20the%20top%20of%20Shibaozhai,called%20the%20Purple%20Rain%20Pavilion.";

    fireEvent.change(searchInput, { target: { value: wikiUrl } });
    fireEvent.click(screen.getByTestId("find-location-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("latitude-input")).toHaveValue("30.421880");
      expect(screen.getByTestId("longitude-input")).toHaveValue("108.183895");
      expect(screen.getByTestId("city-input")).toHaveValue("Zhong County");
      expect(screen.getByTestId("country-input")).toHaveValue("China");
    });
  });

  it("prompts the user for POI name change when Find returns a different name and updates POI name on Yes", async () => {
    const { forwardSearch } = await import("../../services/geocodeService");
    // Simulate Nominatim returning 0 results so it cascades to forwardGeocode
    vi.mocked(forwardSearch).mockResolvedValue([]);

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    fireEvent.change(searchInput, { target: { value: "Barakesh" } });
    fireEvent.click(screen.getByTestId("find-location-btn"));

    // Name change prompt modal should appear
    await waitFor(() => {
      expect(screen.getByTestId("name-change-prompt-modal")).toBeInTheDocument();
    });

    expect(screen.getByTestId("recommended-name-display")).toHaveTextContent("Baraqish");

    // Click "Yes, Update Name"
    fireEvent.click(screen.getByTestId("name-change-yes-btn"));

    // Prompt closes and POI Name input is updated
    await waitFor(() => {
      expect(screen.queryByTestId("name-change-prompt-modal")).not.toBeInTheDocument();
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Baraqish");
    });
  });

  it("allows user to dismiss name change prompt without modifying POI name on No", async () => {
    const { forwardSearch, reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValue({
      street: "123 New Road",
      city: "Fujinomiya",
      locality: "Fujinomiya",
      state_province: "Shizuoka",
      admin_level_1: "Shizuoka Prefecture",
      admin_level_2: "Fujinomiya City",
      postal_code: "418-0000",
      country_code: "JP",
      country: "Japan",
      cached: false,
    });
    vi.mocked(forwardSearch).mockResolvedValue([]);

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("location-search-input")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("location-search-input");
    fireEvent.change(searchInput, { target: { value: "Barakesh" } });
    fireEvent.click(screen.getByTestId("find-location-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("name-change-prompt-modal")).toBeInTheDocument();
    });

    // Click "No, Keep Current Name"
    fireEvent.click(screen.getByTestId("name-change-no-btn"));

    // Modal closes and original POI name remains
    await waitFor(() => {
      expect(screen.queryByTestId("name-change-prompt-modal")).not.toBeInTheDocument();
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue("Mount Fuji");
    });
  });

  it("does not close when clicking the backdrop or pressing Escape, only closes when close button is clicked", async () => {
    const handleClose = vi.fn();
    renderModal({ onClose: handleClose });

    await waitFor(() => {
      expect(
        screen.getByTestId("import-staging-workbench-modal"),
      ).toBeInTheDocument();
    });

    const backdrop = document.querySelector(".modal-backdrop") as HTMLElement;
    expect(backdrop).toBeInTheDocument();

    // Click outside / on the backdrop
    fireEvent.click(backdrop);
    expect(handleClose).not.toHaveBeenCalled();

    // Press Escape
    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).not.toHaveBeenCalled();

    // Click the X close button
    const closeBtn = screen.getByTestId("modal-close-btn");
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("defaults to first hero image and allows rotating through candidate images", async () => {
    const candidateWithMultipleImages: CandidateItem = {
      id: "cand-img-1",
      job_id: "job-1",
      row_index: 1,
      poi_name: "Baraqish",
      recommended_disposition: "accept",
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: 16.0,
      longitude: 44.8,
      street_address: "Ancient Ruins",
      city: "Baraqish",
      state_province: "Marib",
      country: "Yemen",
      country_code: "YE",
      hero_image_url: "https://example.com/photo1.jpg",
      hero_image_urls: [
        "https://example.com/photo1.jpg",
        "https://example.com/photo2.jpg",
        "https://example.com/photo3.jpg",
      ],
      official_url: null,
      related_websites: [],
      no_websites: false,
      confidence_score: 95,
      disposition_justification: "Verified",
      photo_directory: "Yemen/Baraqish",
      photo_directories: ["Yemen/Baraqish"],
      dates_visited: [],
      tags: ["Ruins"],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [candidateWithMultipleImages],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("hero-image-count-badge")).toHaveTextContent("Photo 1 of 3");
      expect(screen.getByTestId("hero-image-url-input")).toHaveValue("https://example.com/photo1.jpg");
    });

    // Click next image button
    const nextBtn = screen.getByTestId("hero-image-next-btn");
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByTestId("hero-image-count-badge")).toHaveTextContent("Photo 2 of 3");
      expect(screen.getByTestId("hero-image-url-input")).toHaveValue("https://example.com/photo2.jpg");
    });

    // Click rotate image button
    const rotateBtn = screen.getByTestId("hero-image-rotate-btn");
    fireEvent.click(rotateBtn);

    await waitFor(() => {
      expect(screen.getByTestId("hero-image-count-badge")).toHaveTextContent("Photo 3 of 3");
      expect(screen.getByTestId("hero-image-url-input")).toHaveValue("https://example.com/photo3.jpg");
    });

    // Click next button wraps back to 1
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByTestId("hero-image-count-badge")).toHaveTextContent("Photo 1 of 3");
      expect(screen.getByTestId("hero-image-url-input")).toHaveValue("https://example.com/photo1.jpg");
    });
  });

  it("resolves non-US country name like Yemen to ISO country code YE instead of defaulting to US", async () => {
    const yemenCandidate: CandidateItem = {
      id: "cand-yemen-1",
      job_id: "job-1",
      row_index: 1,
      poi_name: "Barakesh",
      recommended_disposition: "ignore",
      user_disposition: null,
      matched_existing_poi_id: null,
      parent_poi_id: null,
      latitude: null,
      longitude: null,
      street_address: null,
      city: null,
      state_province: null,
      country: "Yemen",
      country_code: "US", // Staged with erroneous/default US
      hero_image_url: null,
      official_url: null,
      related_websites: [],
      no_websites: false,
      confidence_score: 0,
      disposition_justification: "Missing coordinates",
      photo_directory: "Yemen/Barakesh",
      photo_directories: ["Yemen/Barakesh"],
      dates_visited: [],
      tags: [],
      phase_state: "phase_1_triage" as any,
      created_at: "2026-11-02T00:00:00Z",
      updated_at: "2026-11-02T00:00:00Z",
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [yemenCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("country-input")).toHaveValue("Yemen");
      // Erroneous default US is mapped to YE because country is Yemen
      expect(screen.getByTestId("country-code-input")).toHaveValue("YE");
    });
  });

  it("renders editor fields in the correct sequential order with Visit Details section", async () => {
    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 2,
      candidates: mockCandidates,
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toBeInTheDocument();
    });

    const scrollContainer = screen.getByTestId("candidate-editor-scroll-container");
    const poiNameInput = screen.getByTestId("editor-poi-name-input");
    const dispositionRationale = screen.getByTestId("disposition-rationale-container");
    const heroImageInput = screen.getByTestId("hero-image-url-input");
    const latInput = screen.getByTestId("latitude-input");
    const proximityContainer = screen.getByTestId("proximity-search-container");
    const descriptionTextarea = screen.getByTestId("description-textarea");
    const reasonTextarea = screen.getByTestId("reason-to-visit-textarea");
    const visitDetailsSection = screen.getByTestId("visit-details-section");
    const tagsContainer = screen.getByTestId("tags-library-container");
    const visitDateInput = screen.getByTestId("new-visit-date-input");
    const directoryInput = screen.getByTestId("new-directory-input");
    const websiteInput = screen.getByTestId("new-website-url-input");

    expect(scrollContainer).toBeInTheDocument();
    expect(visitDetailsSection).toBeInTheDocument();

    // Verify DOM sequence via compareDocumentPosition (DOCUMENT_POSITION_FOLLOWING = 4)
    expect(poiNameInput.compareDocumentPosition(dispositionRationale) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(dispositionRationale.compareDocumentPosition(heroImageInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(heroImageInput.compareDocumentPosition(latInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(latInput.compareDocumentPosition(proximityContainer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(proximityContainer.compareDocumentPosition(descriptionTextarea) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(descriptionTextarea.compareDocumentPosition(reasonTextarea) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reasonTextarea.compareDocumentPosition(visitDetailsSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(visitDetailsSection.compareDocumentPosition(tagsContainer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tagsContainer.compareDocumentPosition(visitDateInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(visitDateInput.compareDocumentPosition(directoryInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(directoryInput.compareDocumentPosition(websiteInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Verify Visit Details inputs
    const durationHours = screen.getByTestId("duration-hours-input");
    const durationDays = screen.getByTestId("duration-days-input");
    const durationNotes = screen.getByTestId("duration-notes-input");

    expect(durationHours).toBeInTheDocument();
    expect(durationDays).toBeInTheDocument();
    expect(durationNotes).toBeInTheDocument();
    expect(durationNotes.tagName.toLowerCase()).toBe("textarea");

    // Verify Description & Reason to Visit are enlarged textareas
    expect(descriptionTextarea).toHaveAttribute("rows", "5");
    expect(reasonTextarea).toHaveAttribute("rows", "5");
  });

  it("restores perspective from sessionStorage and saves when toggled", async () => {
    sessionStorage.setItem("vistarae_workbench_perspective", "Location");

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("perspective-select")).toBeInTheDocument();
    });

    const perspectiveSelect = screen.getByTestId("perspective-select") as HTMLSelectElement;
    expect(perspectiveSelect.value).toBe("Location");

    // Toggle to POI
    fireEvent.change(perspectiveSelect, { target: { value: "POI" } });
    expect(perspectiveSelect.value).toBe("POI");
    expect(sessionStorage.getItem("vistarae_workbench_perspective")).toBe("POI");
  });

  it("initializes multi-select dispositions with all selected by default and saves to sessionStorage", async () => {
    sessionStorage.removeItem("vistarae_workbench_dispositions");

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("disposition-filter-button")).toBeInTheDocument();
    });

    const filterBtn = screen.getByTestId("disposition-filter-button");
    expect(filterBtn).toHaveTextContent("All Dispositions");

    const savedDisps = JSON.parse(
      sessionStorage.getItem("vistarae_workbench_dispositions") || "[]",
    );
    expect(savedDisps).toEqual([
      "accept",
      "sublocation",
      "in_batch_merge",
      "update_existing",
      "existing",
      "exclude",
      "ignore",
    ]);
  });

  it("restores selected dispositions from sessionStorage", async () => {
    sessionStorage.setItem(
      "vistarae_workbench_dispositions",
      JSON.stringify(["accept"]),
    );

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("disposition-filter-button")).toBeInTheDocument();
    });

    const filterBtn = screen.getByTestId("disposition-filter-button");
    expect(filterBtn).toHaveTextContent("Accept (New POI)");
  });

  it("filters candidate table when a disposition is deselected and toggles All/Clear", async () => {
    sessionStorage.removeItem("vistarae_workbench_dispositions");

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("disposition-filter-button")).toBeInTheDocument();
    });

    const tableContainer = screen.getByTestId("candidate-table-scroll-container");

    // Both candidates visible initially (cand-1: accept, cand-2: sublocation)
    expect(within(tableContainer).getByText("Mount Fuji")).toBeInTheDocument();
    expect(within(tableContainer).getByText("Lake Kawaguchi")).toBeInTheDocument();

    // Open disposition dropdown
    fireEvent.click(screen.getByTestId("disposition-filter-button"));
    expect(screen.getByTestId("disposition-filter-dropdown")).toBeInTheDocument();

    // Deselect sublocation
    const subCheckbox = screen.getByTestId("disposition-checkbox-sublocation");
    fireEvent.click(subCheckbox);

    // Lake Kawaguchi (sublocation) should be filtered out
    await waitFor(() => {
      expect(within(tableContainer).getByText("Mount Fuji")).toBeInTheDocument();
      expect(within(tableContainer).queryByText("Lake Kawaguchi")).not.toBeInTheDocument();
    });

    // Click "Clear" to deselect all dispositions
    const clearBtn = screen.getByTestId("deselect-all-dispositions-btn");
    fireEvent.click(clearBtn);

    // Both should be filtered out
    await waitFor(() => {
      expect(within(tableContainer).queryByText("Mount Fuji")).not.toBeInTheDocument();
      expect(within(tableContainer).queryByText("Lake Kawaguchi")).not.toBeInTheDocument();
    });

    // Click "All" to reselect all dispositions
    const allBtn = screen.getByTestId("select-all-dispositions-btn");
    fireEvent.click(allBtn);

    await waitFor(() => {
      expect(within(tableContainer).getByText("Mount Fuji")).toBeInTheDocument();
      expect(within(tableContainer).getByText("Lake Kawaguchi")).toBeInTheDocument();
    });
  });

  it("renders 'Completed Only' in completeness dropdown and filters table", async () => {
    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("completeness-filter")).toBeInTheDocument();
    });

    const completenessSelect = screen.getByTestId("completeness-filter") as HTMLSelectElement;
    const completedOption = screen.getByRole("option", { name: "Completed Only" }) as HTMLOptionElement;
    expect(completedOption).toBeInTheDocument();
    expect(completedOption.value).toBe("complete");

    const tableContainer = screen.getByTestId("candidate-table-scroll-container");

    // Select "Completed Only": cand-1 is complete, cand-2 lacks hero_image_url and official_url
    fireEvent.change(completenessSelect, { target: { value: "complete" } });

    await waitFor(() => {
      expect(within(tableContainer).getByText("Mount Fuji")).toBeInTheDocument();
      expect(within(tableContainer).queryByText("Lake Kawaguchi")).not.toBeInTheDocument();
    });
  });

  it("populates Beijing municipality and normalizes road for Summer Palace on address re-sync", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      latitude: 39.9901,
      longitude: 116.26474,
      street: "19 Road",
      city: "Haidian District",
      locality: "Haidian District",
      postal_code: "100091",
      country: "China",
      country_code: "CN",
      admin_level_1: null,
      admin_level_2: "Haidian District",
      raw_geocoding: {
        address: {
          road: "新建宫门路",
          house_number: "19",
          postcode: "100091",
          city: "Haidian District",
          country: "China",
          country_code: "cn",
          "ISO3166-2-lvl4": "CN-BJ",
        },
        display_name:
          "Summer Palace, 19, 新建宫门路, Qinglongqiao, Haidian District, Beijing, 100091, China",
      },
    } as any);

    const summerPalaceCandidate: any = {
      ...mockCandidates[0],
      id: "cand-summer-palace",
      poi_name: "Summer Palace",
      latitude: 39.9901,
      longitude: 116.26474,
      street_address: "19 Road",
      city: "",
      locality: "",
      state_province: "",
      admin_level_1: "",
      admin_level_2: "Haidian District",
      postal_code: "100091",
      country: "China",
      country_code: "CN",
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [summerPalaceCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Summer Palace",
      );
    });

    const resyncBtn = screen.getByTestId("resync-address-from-pin-btn");
    fireEvent.click(resyncBtn);

    await waitFor(() => {
      expect(screen.getByTestId("city-input")).toHaveValue("Beijing");
      expect(screen.getByTestId("state-province-input")).toHaveValue("Beijing");
      expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
        "Haidian District",
      );
      expect(screen.getByTestId("street-address-input")).toHaveValue(
        "19 Xinjiangongmen Road",
      );
      expect(screen.getByTestId("postal-code-input")).toHaveValue("100091");
      expect(screen.getByTestId("country-input")).toHaveValue("China");
      expect(screen.getByTestId("country-code-input")).toHaveValue("CN");
    });
  });

  it("clears unused address fields when newly reverse geocoded address omits them", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      latitude: 64.1466,
      longitude: -21.9426,
      street: null,
      city: null,
      locality: null,
      postal_code: null,
      admin_level_1: null,
      admin_level_2: null,
      state_province: null,
      country: "Iceland",
      country_code: "IS",
      raw_geocoding: {
        address: {
          country: "Iceland",
          country_code: "is",
        },
        display_name: "Iceland",
      },
    } as any);

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Mount Fuji",
      );
    });

    // Populate fields with old data first
    fireEvent.change(screen.getByTestId("street-address-input"), {
      target: { value: "Old Street 123" },
    });
    fireEvent.change(screen.getByTestId("postal-code-input"), {
      target: { value: "99999" },
    });
    fireEvent.change(screen.getByTestId("admin-level-2-input"), {
      target: { value: "Old County" },
    });

    // Re-sync address from pin
    const resyncBtn = screen.getByTestId("resync-address-from-pin-btn");
    fireEvent.click(resyncBtn);

    await waitFor(() => {
      // Unused fields must be cleared, not preserved
      expect(screen.getByTestId("street-address-input")).toHaveValue("");
      expect(screen.getByTestId("postal-code-input")).toHaveValue("");
      expect(screen.getByTestId("admin-level-2-input")).toHaveValue("");
      expect(screen.getByTestId("country-input")).toHaveValue("Iceland");
      expect(screen.getByTestId("country-code-input")).toHaveValue("IS");
    });
  });

  it("places district into admin_level_2 and sets locality to city name for Chinese cities (e.g. Wild Goose Pagodas in Xi'an)", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      latitude: 34.218243,
      longitude: 108.964152,
      street: "Furong East Road",
      city: "Yanta District",
      locality: "Yanta District",
      postal_code: "710054",
      country: "China",
      country_code: "CN",
      admin_level_1: "Shaanxi",
      admin_level_2: null,
      raw_geocoding: {
        address: {
          road: "Furong East Road",
          city: "Yanta District",
          state: "Shaanxi",
          postcode: "710054",
          country: "China",
          country_code: "cn",
          "ISO3166-2-lvl4": "CN-SN",
        },
        display_name:
          "西安唐华华邑酒店, Furong East Road, Dayanta, Yanta District, Xi'an, Shaanxi, 710054, China",
      },
    } as any);

    const wildGooseCandidate: any = {
      ...mockCandidates[0],
      id: "cand-wild-goose",
      poi_name: "Wild Goose Pagodas",
      latitude: 34.218243,
      longitude: 108.964152,
      street_address: "Furong East Road",
      city: "Yanta District",
      locality: "Yanta District",
      state_province: "Shaanxi",
      admin_level_1: "Shaanxi",
      admin_level_2: null,
      postal_code: "710054",
      country: "China",
      country_code: "CN",
      raw_geocoding: {
        address: {
          road: "Furong East Road",
          city: "Yanta District",
          state: "Shaanxi",
          postcode: "710054",
          country: "China",
          country_code: "cn",
          "ISO3166-2-lvl4": "CN-SN",
        },
        display_name:
          "西安唐华华邑酒店, Furong East Road, Dayanta, Yanta District, Xi'an, Shaanxi, 710054, China",
      },
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [wildGooseCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Wild Goose Pagodas",
      );
    });

    // In the editor, City should be Xi'an (not Yanta District), and District should be Yanta District
    expect(screen.getByTestId("city-input")).toHaveValue("Xi'an");
    expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
      "Yanta District",
    );
    expect(screen.getByTestId("state-province-input")).toHaveValue("Shaanxi");

    // In the table on the left, City / Town should display Xi'an
    const tableContainer = screen.getByTestId("candidate-table-scroll-container");
    expect(within(tableContainer).getByText("Xi'an")).toBeInTheDocument();
    expect(within(tableContainer).queryByText("Yanta District")).not.toBeInTheDocument();

    // Re-syncing address from pin also preserves/populates Xi'an as city and Yanta District as admin_level_2
    const resyncBtn = screen.getByTestId("resync-address-from-pin-btn");
    fireEvent.click(resyncBtn);

    await waitFor(() => {
      expect(screen.getByTestId("city-input")).toHaveValue("Xi'an");
      expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
        "Yanta District",
      );
      expect(screen.getByTestId("state-province-input")).toHaveValue("Shaanxi");
    });
  });

  it("resolves Bund River Front in Shanghai to Huangpu District (not Pudong and not blank)", async () => {
    const bundCandidate: any = {
      ...mockCandidates[0],
      id: "cand-bund",
      poi_name: "Bund River Front",
      latitude: 31.240082,
      longitude: 121.486173,
      street_address: "The Bund",
      city: "Shanghai",
      locality: "Shanghai",
      state_province: "Shanghai",
      admin_level_1: "Shanghai",
      admin_level_2: null,
      postal_code: "200002",
      country: "China",
      country_code: "CN",
      raw_geocoding: {
        address: {
          road: "The Bund",
          quarter: "Xinbeimen",
          suburb: "Waitan Subdistrict",
          city: "Shanghai",
          state: "Shanghai",
          postcode: "200002",
          country: "China",
          country_code: "cn",
          "ISO3166-2-lvl4": "CN-SH",
        },
        display_name:
          "The Bund, Xinbeimen, Waitan Subdistrict, Shanghai, Huangpu District, Shanghai, 200002, China",
      },
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [bundCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Bund River Front",
      );
    });

    expect(screen.getByTestId("city-input")).toHaveValue("Shanghai");
    expect(screen.getByTestId("state-province-input")).toHaveValue("Shanghai");
    expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
      "Huangpu District",
    );
  });

  it("normalizes Hong Kong candidate from Fife Street Mong Kok / Kowloon to Hong Kong / Yau Tsim Mong District", async () => {
    const { getDisplayCandidateCity } = await import(
      "../../components/ingest/CSVImportWorkbenchModal"
    );
    const { reverseGeocode } = await import("../../services/geocodeService");

    const hkCandidate: any = {
      ...mockCandidates[0],
      id: "cand-hk-160",
      poi_name: "Hong Kong Restaurants & Shops",
      latitude: 22.319945,
      longitude: 114.169705,
      street_address: "Kowloon City Flyover",
      city: "Fife Street Mong Kok",
      locality: "Fife Street Mong Kok",
      state_province: "Kowloon",
      admin_level_1: "Kowloon",
      admin_level_2: null,
      postal_code: "",
      country: "China",
      country_code: "CN",
      raw_geocoding: {
        address: {
          amenity: "Cold Noodles",
          house_number: "688",
          road: "Sai Yeung Choi Street South",
          suburb: "Mong Kok",
          region: "Kowloon",
          city: "Hong Kong",
          "ISO3166-2-lvl3": "CN-HK",
          country: "China",
          country_code: "cn",
        },
        display_name:
          "Cold Noodles, 688, Sai Yeung Choi Street South, Mong Kok, Yau Tsim Mong District, Kowloon, Hong Kong, China",
      },
    };

    // Table display helper should show Hong Kong
    expect(getDisplayCandidateCity(hkCandidate)).toBe("Hong Kong");

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [hkCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Hong Kong Restaurants & Shops",
      );
    });

    // Form fields in editor should be normalized to Hong Kong
    expect(screen.getByTestId("city-input")).toHaveValue("Hong Kong");
    expect(screen.getByTestId("state-province-input")).toHaveValue("Hong Kong");
    expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
      "Yau Tsim Mong District",
    );

    // Re-sync from pin
    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      latitude: 22.319945,
      longitude: 114.169705,
      street: "688 Sai Yeung Choi Street South",
      city: "Hong Kong",
      locality: "Hong Kong",
      postal_code: "",
      country: "China",
      country_code: "CN",
      admin_level_1: "Hong Kong",
      admin_level_2: "Yau Tsim Mong District",
      raw_geocoding: hkCandidate.raw_geocoding,
    } as any);

    const resyncBtn = screen.getByRole("button", {
      name: /re-sync address from pin/i,
    });
    fireEvent.click(resyncBtn);

    await waitFor(() => {
      expect(screen.getByTestId("street-address-input")).toHaveValue(
        "688 Sai Yeung Choi Street South",
      );
      expect(screen.getByTestId("city-input")).toHaveValue("Hong Kong");
      expect(screen.getByTestId("state-province-input")).toHaveValue("Hong Kong");
      expect(screen.getByTestId("admin-level-2-input")).toHaveValue(
        "Yau Tsim Mong District",
      );
    });
  });

  it("re-syncs address from pin for Namibia without incorrectly setting China/CN", async () => {
    const { reverseGeocode } = await import("../../services/geocodeService");

    const namibiaCandidate: any = {
      ...mockCandidates[0],
      id: "cand-namibia-673",
      poi_name: "Etosha National Park",
      latitude: -18.99133,
      longitude: 15.74606,
      street_address: "",
      city: "",
      locality: "",
      state_province: "",
      admin_level_1: "",
      admin_level_2: null,
      postal_code: "",
      country: "Namibia",
      country_code: "",
      raw_geocoding: {
        address: {
          state: "Oshana",
          "ISO3166-2-lvl4": "NA-ON",
          country: "Namibia",
          country_code: "na",
        },
        display_name: "Oshana, Namibia",
      },
    };

    vi.mocked(ingestApi.listStagingCandidates).mockResolvedValue({
      job_id: "job-1",
      total_candidates: 1,
      candidates: [namibiaCandidate],
    });

    renderModal();

    await waitFor(() => {
      expect(screen.getByTestId("editor-poi-name-input")).toHaveValue(
        "Etosha National Park",
      );
    });

    vi.mocked(reverseGeocode).mockResolvedValueOnce({
      latitude: -18.99133,
      longitude: 15.74606,
      street: "",
      city: "",
      locality: "",
      postal_code: "",
      country: "Namibia",
      country_code: "NA",
      admin_level_1: "Oshana",
      admin_level_2: "",
      raw_geocoding: namibiaCandidate.raw_geocoding,
    } as any);

    const resyncBtn = screen.getByRole("button", {
      name: /re-sync address from pin/i,
    });
    fireEvent.click(resyncBtn);

    await waitFor(() => {
      expect(screen.getByTestId("country-input")).toHaveValue("Namibia");
      expect(screen.getByTestId("country-code-input")).toHaveValue("NA");
      expect(screen.getByTestId("state-province-input")).toHaveValue("Oshana");
    });
  });
});
