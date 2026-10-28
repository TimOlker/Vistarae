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
import { POIPopupCard } from "../../../components/map/POIPopupCard";
import type { POIMapFeature } from "../../../types/map";

describe("POIPopupCard (T-035, T-036 / REQ-MAIN-038, REQ-MAIN-039)", () => {
  const singleAddressPoi: POIMapFeature = {
    id: "poi-louvre",
    name: "Louvre Museum",
    canonical_lat: 48.8606,
    canonical_lng: 2.3376,
    render_lat: 48.8606,
    render_lng: 2.3376,
    visit_state: "visited_return",
    rating: 5,
    city: "Paris",
    state: "Île-de-France",
    country: "France",
    tags: ["museum", "art"],
    image_urls: ["https://example.com/louvre.jpg"],
    addresses: [
      { city: "Paris", state_province: "Île-de-France", country: "France" },
    ],
  };

  const multiAddressPoi: POIMapFeature = {
    id: "poi-metro",
    name: "Paris Metro Station",
    canonical_lat: 48.8566,
    canonical_lng: 2.3522,
    render_lat: 48.8566,
    render_lng: 2.3522,
    visit_state: "not_visited",
    rating: null,
    tags: ["transit"],
    addresses: [
      { city: "Paris", street: "Station A" },
      { city: "Paris", street: "Station B" },
      { city: "Paris", street: "Station C" },
    ],
  };

  it("renders canonical name, rating, address, thumbnail, and edit button for single-address POI", () => {
    const onClose = vi.fn();
    const onEdit = vi.fn();

    render(
      <POIPopupCard poi={singleAddressPoi} onClose={onClose} onEdit={onEdit} />,
    );

    expect(screen.getByTestId("poi-popup-card")).toBeInTheDocument();
    expect(screen.getByTestId("poi-popup-title")).toHaveTextContent(
      "Louvre Museum",
    );
    expect(screen.getByTestId("single-address-summary")).toHaveTextContent(
      "Paris, Île-de-France, France",
    );
    expect(
      screen.queryByTestId("multi-location-badge"),
    ).not.toBeInTheDocument();

    const img = screen.getByTestId("poi-popup-thumbnail");
    expect(img).toHaveAttribute("src", "https://example.com/louvre.jpg");

    // Star rating check: 5.0 rating displayed
    expect(screen.getByText("5.0")).toBeInTheDocument();
    expect(screen.queryByTestId("unrated-indicator")).not.toBeInTheDocument();

    // Trigger edit button
    const editBtn = screen.getByTestId("popup-edit-poi-btn");
    fireEvent.click(editBtn);
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(singleAddressPoi);

    // Trigger close button
    const closeBtn = screen.getByTestId("close-popup-btn");
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders multiple locations badge and Unrated indicator for unrated multi-address POI", () => {
    const onClose = vi.fn();

    render(<POIPopupCard poi={multiAddressPoi} onClose={onClose} />);

    expect(screen.getByTestId("poi-popup-title")).toHaveTextContent(
      "Paris Metro Station",
    );
    expect(screen.getByTestId("multi-location-badge")).toHaveTextContent(
      "Multiple Locations (3)",
    );
    expect(
      screen.queryByTestId("single-address-summary"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("unrated-indicator")).toHaveTextContent(
      "Unrated",
    );
  });

  it("handles image load errors by hiding thumbnail preview gracefully", () => {
    render(<POIPopupCard poi={singleAddressPoi} onClose={vi.fn()} />);

    const img = screen.getByTestId("poi-popup-thumbnail");
    fireEvent.error(img);

    // Image should now be removed from DOM
    expect(screen.queryByTestId("poi-popup-thumbnail")).not.toBeInTheDocument();
  });

  it("does not display a state when location in DB has no state defined", () => {
    const eltzCastlePoi: POIMapFeature = {
      id: "poi-eltz",
      name: "Eltz Castle",
      canonical_lat: 50.2052,
      canonical_lng: 7.3366,
      render_lat: 50.2052,
      render_lng: 7.3366,
      visit_state: "not_visited",
      rating: 5,
      city: "Wierschem",
      country: "Germany",
      tags: ["castle"],
      addresses: [
        {
          city: "Wierschem",
          country: "Germany",
        },
      ],
    };

    render(<POIPopupCard poi={eltzCastlePoi} onClose={vi.fn()} />);

    expect(screen.getByTestId("single-address-summary")).toHaveTextContent(
      "Wierschem, Germany",
    );
    expect(screen.getByTestId("single-address-summary")).not.toHaveTextContent(
      "California",
    );
  });
});
