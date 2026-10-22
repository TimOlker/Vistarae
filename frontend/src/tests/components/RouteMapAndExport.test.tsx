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
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RouteMap } from "../../components/planner/RouteMap";
import { PrintExportView } from "../../components/planner/PrintExportView";
import { ItineraryItemCard } from "../../components/planner/ItineraryItemCard";
import type {
  ItineraryResponse,
  ItineraryItemResponse,
} from "../../services/itineraryService";

// Mock MapLibre GL
const mockAddSource = vi.fn();
const mockAddLayer = vi.fn();
const mockFitBounds = vi.fn();
const mockSetLngLat = vi.fn().mockReturnThis();
const mockSetPopup = vi.fn().mockReturnThis();
const mockAddTo = vi.fn().mockReturnThis();
const mockRemove = vi.fn();

vi.mock("maplibre-gl", () => {
  return {
    default: {
      Map: vi.fn().mockImplementation(() => ({
        addControl: vi.fn(),
        addSource: mockAddSource,
        addLayer: mockAddLayer,
        getSource: vi.fn().mockReturnValue(null),
        isStyleLoaded: vi.fn().mockReturnValue(true),
        fitBounds: mockFitBounds,
        remove: mockRemove,
      })),
      NavigationControl: vi.fn(),
      Marker: vi.fn().mockImplementation(() => ({
        setLngLat: mockSetLngLat,
        setPopup: mockSetPopup,
        addTo: mockAddTo,
        remove: vi.fn(),
      })),
      Popup: vi.fn().mockImplementation(() => ({
        setHTML: vi.fn().mockReturnThis(),
      })),
      LngLatBounds: vi.fn().mockImplementation(() => ({
        extend: vi.fn().mockReturnThis(),
      })),
    },
  };
});

// Mock @hello-pangea/dnd Draggable wrapper
vi.mock("@hello-pangea/dnd", () => ({
  Draggable: ({
    children,
  }: {
    children: (provided: any, snapshot: any) => React.ReactNode;
  }) =>
    children(
      {
        draggableProps: {},
        dragHandleProps: {},
        innerRef: vi.fn(),
      },
      { isDragging: false },
    ),
}));

const sampleItinerary: ItineraryResponse = {
  id: "itin-wa-01",
  user_id: "user-test",
  title: "Pacific Northwest Explorer",
  destination: "Seattle & Olympic National Park",
  start_date: "2026-08-10",
  end_date: "2026-08-12",
  budget_cents: 150000,
  total_estimated_cost_cents: 95000,
  currency: "USD",
  status: "draft",
  days: [
    {
      id: "day-1",
      itinerary_id: "itin-wa-01",
      day_number: 1,
      calendar_date: "2026-08-10",
      total_cost_cents: 35000,
      items: [
        {
          id: "item-1",
          itinerary_day_id: "day-1",
          title: "Space Needle",
          order_index: 0,
          start_time: "09:00:00",
          end_time: "11:00:00",
          duration_hours: "2.00",
          source_type: "USER_SAVED",
          cost_cents: 3500,
          latitude: 47.6205,
          longitude: -122.3493,
          category: "observation",
          poi_id: "poi-sn",
          notes: "Panoramic city view",
        },
        {
          id: "item-2",
          itinerary_day_id: "day-1",
          title: "Chihuly Garden and Glass",
          order_index: 1,
          start_time: "11:30:00",
          end_time: "13:30:00",
          duration_hours: "2.00",
          source_type: "AI_RECOMMENDED",
          cost_cents: 3200,
          latitude: 47.6206,
          longitude: -122.3505,
          category: "museum",
          poi_id: null,
          travel_time_prev_minutes: 5,
          travel_distance_prev_meters: 250,
        },
      ],
    },
    {
      id: "day-2",
      itinerary_id: "itin-wa-01",
      day_number: 2,
      calendar_date: "2026-08-11",
      total_cost_cents: 20000,
      items: [
        {
          id: "item-3",
          itinerary_day_id: "day-2",
          title: "Lake Crescent Lodge",
          order_index: 0,
          start_time: "10:00:00",
          end_time: "14:00:00",
          duration_hours: "4.00",
          source_type: "USER_SAVED",
          cost_cents: 0,
          latitude: 48.0583,
          longitude: -123.8017,
          category: "lake",
          poi_id: "poi-lc",
        },
      ],
    },
  ],
  circuit_breaker_warnings: [],
  advisories: [],
};

describe("RouteMap and Export Views (REQ-PLAN-014, REQ-PLAN-015, REQ-PLAN-016)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("RouteMap Component (REQ-PLAN-015)", () => {
    it("renders day selector tabs including All Days (Macro) and individual days", () => {
      render(<RouteMap itinerary={sampleItinerary} />);

      expect(screen.getByTestId("route-filter-all")).toHaveTextContent(
        "All Days (Macro)",
      );
      expect(screen.getByTestId("route-filter-day-1")).toHaveTextContent(
        "Day 1",
      );
      expect(screen.getByTestId("route-filter-day-2")).toHaveTextContent(
        "Day 2",
      );
    });

    it("toggles between macro mode and day 1 daily leg mode", () => {
      const onSelectDay = vi.fn();
      render(
        <RouteMap itinerary={sampleItinerary} onSelectDay={onSelectDay} />,
      );

      // Click Day 1
      fireEvent.click(screen.getByTestId("route-filter-day-1"));
      expect(onSelectDay).toHaveBeenCalledWith("day-1");

      // Click All Days
      fireEvent.click(screen.getByTestId("route-filter-all"));
      expect(onSelectDay).toHaveBeenCalledWith(null);
    });
  });

  describe("AI POI 1-Click Import Flow (REQ-PLAN-014)", () => {
    it("renders 'Import to My POIs' button on AI_RECOMMENDED item and executes onImportPoi", async () => {
      const aiItem: ItineraryItemResponse = {
        id: "item-ai-1",
        itinerary_day_id: "day-1",
        title: "Olympic National Park Rainforest",
        order_index: 2,
        start_time: "14:00:00",
        end_time: "17:00:00",
        duration_hours: "3.00",
        source_type: "AI_RECOMMENDED",
        cost_cents: 0,
        latitude: 47.8596,
        longitude: -123.9348,
        category: "nature",
        poi_id: null,
      };

      const onImportPoi = vi.fn().mockResolvedValue(undefined);

      render(
        <ItineraryItemCard item={aiItem} index={0} onImportPoi={onImportPoi} />,
      );

      // Verify AI badge and Import button
      expect(screen.getByText("AI Suggestion")).toBeInTheDocument();
      const importBtn = screen.getByTitle("Import to My Saved POIs");
      expect(importBtn).toBeInTheDocument();

      fireEvent.click(importBtn);

      await waitFor(() => {
        expect(onImportPoi).toHaveBeenCalledTimes(1);
        expect(onImportPoi).toHaveBeenCalledWith(aiItem);
      });
    });
  });

  describe("PrintExportView Component (REQ-PLAN-016)", () => {
    it("renders trip overview and all scheduled days with transit details", () => {
      render(<PrintExportView itinerary={sampleItinerary} />);

      expect(screen.getByTestId("print-title")).toHaveTextContent(
        "Pacific Northwest Explorer",
      );
      expect(
        screen.getByText("Seattle & Olympic National Park"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("print-day-1")).toBeInTheDocument();
      expect(screen.getByTestId("print-day-2")).toBeInTheDocument();
      expect(screen.getByText("Space Needle")).toBeInTheDocument();
      expect(screen.getByText("Chihuly Garden and Glass")).toBeInTheDocument();
      expect(screen.getByText(/5 min transit/i)).toBeInTheDocument();
    });

    it("triggers window.print() when clicking the Print / Save PDF button", () => {
      const printSpy = vi.spyOn(window, "print").mockImplementation(() => {});

      render(<PrintExportView itinerary={sampleItinerary} />);

      const printBtn = screen.getByTestId("print-export-btn");
      expect(printBtn).toBeInTheDocument();
      fireEvent.click(printBtn);

      expect(printSpy).toHaveBeenCalledTimes(1);
      printSpy.mockRestore();
    });

    it("invokes onClose when clicking Back to Workbench button", () => {
      const onClose = vi.fn();
      render(<PrintExportView itinerary={sampleItinerary} onClose={onClose} />);

      const backBtn = screen.getByTestId("print-back-btn");
      fireEvent.click(backBtn);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
