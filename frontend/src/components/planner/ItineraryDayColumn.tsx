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
import { Droppable } from "@hello-pangea/dnd";
import { AlertCircle, Clock } from "lucide-react";
import { ItineraryItemCard } from "./ItineraryItemCard";
import { MissingMealCard } from "./MissingMealCard";
import type {
  ItineraryDayResponse,
  ItineraryItemResponse,
  MissingMealAdvisory,
} from "../../services/itineraryService";

interface ItineraryDayColumnProps {
  day: ItineraryDayResponse;
  advisories?: MissingMealAdvisory[];
  onImportPoi?: (item: ItineraryItemResponse) => Promise<void>;
  onPackLunch?: (advisory: MissingMealAdvisory) => void;
}

export const ItineraryDayColumn: React.FC<ItineraryDayColumnProps> = ({
  day,
  advisories = [],
  onImportPoi,
  onPackLunch,
}) => {
  const dayAdvisories = advisories.filter(
    (a) => a.day_number === day.day_number,
  );

  // Compute total active duration for the day
  const totalDuration = (day.items || []).reduce(
    (sum, item) => sum + (parseFloat(item.duration_hours || "0") || 0),
    0,
  );
  const isOverplanned = totalDuration > 10.0;

  const formatDate = (dateStr: string): string => {
    try {
      const d = new Date(dateStr + "T00:00:00");
      return d.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const formatCost = (cents: number): string => {
    return `$${(cents / 100).toFixed(0)}`;
  };

  return (
    <div
      style={{
        flex: "0 0 320px",
        minWidth: "300px",
        maxWidth: "360px",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "var(--bg-surface)",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--border-color)",
        padding: "16px",
        maxHeight: "calc(100vh - 220px)",
      }}
    >
      {/* Column Header */}
      <div style={{ marginBottom: "12px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "4px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                padding: "2px 8px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--accent-light)",
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: "0.85rem",
              }}
            >
              Day {day.day_number}
            </div>
            <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>
              {formatDate(day.calendar_date || "")}
            </h3>
          </div>

          <span
            style={{
              fontSize: "0.8rem",
              fontWeight: 600,
              color: "var(--text-secondary)",
            }}
          >
            {formatCost(day.total_cost_cents)}
            {day.target_budget_cents
              ? ` / ${formatCost(day.target_budget_cents)}`
              : ""}
          </span>
        </div>

        {/* Duration & Circuit Breaker Badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "0.75rem",
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              color: isOverplanned ? "var(--warning)" : "var(--text-muted)",
              fontWeight: isOverplanned ? 600 : 400,
            }}
          >
            <Clock size={12} /> {totalDuration.toFixed(1)}h planned
          </span>

          {isOverplanned ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "3px",
                color: "var(--warning)",
                backgroundColor: "rgba(245, 158, 11, 0.12)",
                padding: "1px 6px",
                borderRadius: "var(--radius-sm)",
                fontWeight: 600,
                fontSize: "0.7rem",
              }}
              title="Daily exploration exceeds 10 hours limit"
            >
              <AlertCircle size={10} /> Over-planned
            </span>
          ) : null}
        </div>
      </div>

      {/* Droppable Items List */}
      <Droppable droppableId={day.id}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            style={{
              flex: 1,
              overflowY: "auto",
              paddingRight: "4px",
              minHeight: "160px",
              backgroundColor: snapshot.isDraggingOver
                ? "var(--bg-hover)"
                : "transparent",
              borderRadius: "var(--radius-md)",
              transition: "background-color var(--transition-fast)",
            }}
          >
            {/* Missing meal advisories */}
            {dayAdvisories.map((adv, idx) => (
              <MissingMealCard
                key={`${adv.day_number}-${adv.meal_type}-${idx}`}
                advisory={adv}
                onPackLunch={onPackLunch}
              />
            ))}

            {/* Itinerary Items */}
            {(day.items || []).map((item, index) => (
              <ItineraryItemCard
                key={item.id}
                item={item}
                index={index}
                onImportPoi={onImportPoi}
              />
            ))}

            {provided.placeholder}

            {(day.items || []).length === 0 && dayAdvisories.length === 0 ? (
              <div
                style={{
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--text-muted)",
                  fontSize: "0.85rem",
                  border: "2px dashed var(--border-color)",
                  borderRadius: "var(--radius-md)",
                  padding: "24px 16px",
                  textAlign: "center",
                }}
              >
                Drag activities here to schedule Day {day.day_number}
              </div>
            ) : null}
          </div>
        )}
      </Droppable>
    </div>
  );
};
