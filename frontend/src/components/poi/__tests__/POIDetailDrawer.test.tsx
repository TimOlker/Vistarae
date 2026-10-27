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

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { POIDetailDrawer } from "../POIDetailDrawer";
import type { POIMapFeature } from "../../../types/map";

describe("POIDetailDrawer (T-028 / REQ-CTX-036, SC-005)", () => {
  const samplePoi: POIMapFeature = {
    id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    name: "Coastal Sea Cave",
    canonical_lat: 36.5,
    canonical_lng: -121.9,
    render_lat: 36.5,
    render_lng: -121.9,
    visit_state: "not_visited",
    rating: 5,
    city: "Carmel",
    state: "California",
    country: "United States",
    tags: ["coastal", "cave"],
    description: "Tide-carved natural sandstone arch and cavern.",
    reason_to_visit: "Bioluminescent algae glow during extreme low tide evening events.",
    addresses: [],
  };

  it("renders dedicated Why Visit card immediately following Description block", () => {
    render(
      <POIDetailDrawer
        poi={samplePoi}
        isOpen={true}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />
    );

    const descTextarea = screen.getByLabelText(/Description/i) as HTMLTextAreaElement;
    const whyVisitCard = screen.getByTestId("detail-why-visit-card");
    const reasonTextarea = screen.getByLabelText(/Why Visit \(Reason to Visit\)/i) as HTMLTextAreaElement;

    expect(descTextarea).toBeDefined();
    expect(whyVisitCard).toBeDefined();
    expect(reasonTextarea).toBeDefined();

    // Verify visual order: whyVisitCard follows descTextarea
    const position = descTextarea.compareDocumentPosition(whyVisitCard);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    // Verify values populated
    expect(descTextarea.value).toBe("Tide-carved natural sandstone arch and cavern.");
    expect(reasonTextarea.value).toBe(
      "Bioluminescent algae glow during extreme low tide evening events."
    );
  });

  it("passes updated reason_to_visit in onSave payload upon form submission", () => {
    const onSaveMock = vi.fn();

    render(
      <POIDetailDrawer
        poi={samplePoi}
        isOpen={true}
        onClose={vi.fn()}
        onSave={onSaveMock}
      />
    );

    const reasonTextarea = screen.getByLabelText(/Why Visit \(Reason to Visit\)/i);
    fireEvent.change(reasonTextarea, {
      target: { value: "Accessible via kayaks for guided wildlife photography." },
    });

    const submitBtn = screen.getByRole("button", { name: /save changes/i });
    fireEvent.click(submitBtn);

    expect(onSaveMock).toHaveBeenCalledWith(
      expect.objectContaining({
        reason_to_visit: "Accessible via kayaks for guided wildlife photography.",
      })
    );
  });
});
