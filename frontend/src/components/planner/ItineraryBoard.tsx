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

import React, { useState } from "react";
import { DragDropContext, DropResult } from "@hello-pangea/dnd";
import { AlertTriangle } from "lucide-react";
import { ItineraryDayColumn } from "./ItineraryDayColumn";
import { DayShortageModal } from "./DayShortageModal";
import {
  itineraryService,
  type ItineraryResponse,
  type ItineraryItemResponse,
  type CircuitBreakerWarning,
} from "../../services/itineraryService";

export interface ItineraryBoardProps {
  itinerary: ItineraryResponse;
  onItineraryUpdated?: (updated: ItineraryResponse) => void;
  onUpdateItinerary?: (updated: ItineraryResponse) => void;
  onImportPoi?: (item: ItineraryItemResponse) => Promise<void>;
  onExtendTrip?: () => void;
}

export const ItineraryBoard: React.FC<ItineraryBoardProps> = ({
  itinerary,
  onItineraryUpdated,
  onUpdateItinerary,
  onImportPoi,
  onExtendTrip,
}) => {
  const notifyUpdated = onItineraryUpdated || onUpdateItinerary || (() => {});

  const [activeWarning, setActiveWarning] =
    useState<CircuitBreakerWarning | null>(() =>
      itinerary.circuit_breaker_warnings &&
      itinerary.circuit_breaker_warnings.length > 0
        ? itinerary.circuit_breaker_warnings[0]
        : null,
    );

  const days = itinerary.days || [];
  const advisories = itinerary.advisories || [];

  // Check if any day has active exploration exceeding 10 hours
  const overplannedDays = days.filter((d) => {
    const totalHours = (d.items || []).reduce((sum, item) => {
      const dur = parseFloat(item.duration_hours || "0");
      if (dur > 0) return sum + dur;
      if (item.start_time && item.end_time) {
        const [sh, sm] = item.start_time.split(":").map(Number);
        const [eh, em] = item.end_time.split(":").map(Number);
        const diff = (eh * 60 + em - (sh * 60 + sm)) / 60;
        return sum + (diff > 0 ? diff : 0);
      }
      return sum;
    }, 0);
    return totalHours > 10.0;
  });

  const handleDragEnd = async (result: DropResult) => {
    const { source, destination } = result;
    if (!destination) return;
    if (
      source.droppableId === destination.droppableId &&
      source.index === destination.index
    ) {
      return;
    }

    // 1. Optimistic Local State Update
    const sourceDay = days.find((d) => d.id === source.droppableId);
    const destDay = days.find((d) => d.id === destination.droppableId);
    if (!sourceDay || !destDay) return;

    const sourceItems = Array.from(sourceDay.items || []);
    const destItems =
      source.droppableId === destination.droppableId
        ? sourceItems
        : Array.from(destDay.items || []);

    const [movedItem] = sourceItems.splice(source.index, 1);
    movedItem.itinerary_day_id = destination.droppableId;
    destItems.splice(destination.index, 0, movedItem);

    // Update order_index on affected items
    destItems.forEach((item, idx) => {
      item.order_index = idx;
    });
    if (source.droppableId !== destination.droppableId) {
      sourceItems.forEach((item, idx) => {
        item.order_index = idx;
      });
    }

    const optimisticDays = days.map((day) => {
      if (day.id === source.droppableId) {
        return { ...day, items: sourceItems };
      }
      if (day.id === destination.droppableId) {
        return { ...day, items: destItems };
      }
      return day;
    });

    const optimisticItinerary: ItineraryResponse = {
      ...itinerary,
      days: optimisticDays,
    };
    notifyUpdated(optimisticItinerary);

    // 2. Persist to Backend API
    try {
      const reorderPayload = {
        items: destItems.map((item, idx) => ({
          item_id: item.id,
          itinerary_day_id: destination.droppableId,
          order_index: idx,
          start_time: item.start_time,
          end_time: item.end_time,
        })),
      };

      const serverUpdated = await itineraryService.reorderItems(
        itinerary.id,
        reorderPayload,
      );
      notifyUpdated(serverUpdated);
    } catch {
      // Revert optimistic update on error
      notifyUpdated(itinerary);
    }
  };

  const handleImportPoi = async (item: ItineraryItemResponse) => {
    if (onImportPoi) {
      await onImportPoi(item);
      return;
    }
    await itineraryService.importPoiToSaved({
      name: item.title,
      lat: item.latitude,
      lng: item.longitude,
      description: item.notes,
      category: item.category,
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Circuit Breaker Amber Banner */}
      {overplannedDays.length > 0 ? (
        <div
          data-testid="circuit-breaker-banner"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            backgroundColor: "rgba(245, 158, 11, 0.12)",
            border: "1px solid var(--warning, #f59e0b)",
            borderRadius: "var(--radius-md, 8px)",
            padding: "10px 16px",
            marginBottom: "16px",
            color: "var(--text-primary, #0f172a)",
            fontSize: "0.88rem",
          }}
        >
          <AlertTriangle size={18} color="var(--warning, #f59e0b)" />
          <span>
            <strong>Over-planning Alert:</strong> Day{" "}
            {overplannedDays.map((d) => d.day_number).join(", ")} exceeds 10
            hours of active daily exploration. Consider redistributing
            activities across days to prevent travel fatigue.
          </span>
        </div>
      ) : null}

      {/* Drag and Drop Day Columns Container */}
      <DragDropContext onDragEnd={handleDragEnd}>
        <div
          data-testid="itinerary-board-columns"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "16px",
            overflowX: "auto",
            paddingBottom: "16px",
            flex: 1,
          }}
        >
          {days.map((day) => (
            <ItineraryDayColumn
              key={day.id}
              day={day}
              advisories={advisories}
              onImportPoi={handleImportPoi}
            />
          ))}
        </div>
      </DragDropContext>

      {/* Day Shortage Modal */}
      {activeWarning &&
      activeWarning.threshold_hours &&
      parseFloat(activeWarning.threshold_hours) > 0 ? (
        <DayShortageModal
          warning={activeWarning}
          isOpen={Boolean(activeWarning)}
          onClose={() => setActiveWarning(null)}
          onExtendTrip={onExtendTrip}
        />
      ) : null}
    </div>
  );
};
