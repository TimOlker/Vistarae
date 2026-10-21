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
import { Draggable } from "@hello-pangea/dnd";
import {
  Clock,
  DollarSign,
  GripVertical,
  Navigation,
  Umbrella,
  BookmarkPlus,
  Check,
} from "lucide-react";
import type { ItineraryItemResponse } from "../../services/itineraryService";

interface ItineraryItemCardProps {
  item: ItineraryItemResponse;
  index: number;
  onImportPoi?: (item: ItineraryItemResponse) => Promise<void>;
}

export const ItineraryItemCard: React.FC<ItineraryItemCardProps> = ({
  item,
  index,
  onImportPoi,
}) => {
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(item.source_type === "USER_SAVED");

  const handleImport = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onImportPoi || imported || importing) return;
    try {
      setImporting(true);
      await onImportPoi(item);
      setImported(true);
    } catch {
      // Handled by parent toast/error handler
    } finally {
      setImporting(false);
    }
  };

  const formatCost = (cents: number): string => {
    if (cents <= 0) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
  };

  const formatTimeSlot = (start?: string | null, end?: string | null): string => {
    if (!start && !end) return "";
    const clean = (t: string) => t.slice(0, 5);
    if (start && end) return `${clean(start)} - ${clean(end)}`;
    return clean(start || end || "");
  };

  const formatDistance = (meters?: number | null): string => {
    if (!meters) return "";
    if (meters < 1000) return `${meters}m`;
    return `${(meters / 1000).toFixed(1)}km`;
  };

  return (
    <Draggable draggableId={item.id} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          style={{
            ...provided.draggableProps.style,
            marginBottom: "12px",
          }}
          className={`itinerary-item-card ${
            snapshot.isDragging ? "is-dragging" : ""
          }`}
        >
          {/* Transit Connection Pill from Previous POI */}
          {item.travel_time_prev_minutes && item.travel_distance_prev_meters ? (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                backgroundColor: "var(--bg-hover)",
                padding: "2px 8px",
                borderRadius: "var(--radius-full)",
                marginBottom: "8px",
              }}
            >
              <Navigation size={12} />
              <span>
                {item.travel_time_prev_minutes} min (
                {formatDistance(item.travel_distance_prev_meters)}) from previous
              </span>
            </div>
          ) : null}

          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "10px",
              padding: "12px",
              backgroundColor: "var(--bg-card)",
              borderRadius: "var(--radius-md)",
              border: `1px solid ${
                snapshot.isDragging ? "var(--accent)" : "var(--border-color)"
              }`,
              boxShadow: snapshot.isDragging
                ? "var(--shadow-lg)"
                : "var(--shadow-sm)",
              transition: "border-color var(--transition-fast), box-shadow var(--transition-fast)",
            }}
          >
            {/* Drag Handle */}
            <div
              {...provided.dragHandleProps}
              style={{
                cursor: "grab",
                color: "var(--text-muted)",
                paddingTop: "2px",
              }}
              title="Drag to reorder activity"
            >
              <GripVertical size={16} />
            </div>

            {/* Main Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "8px",
                  marginBottom: "4px",
                }}
              >
                <h4
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={item.title}
                >
                  {item.title}
                </h4>

                {/* Source Badge & 1-Click Import Button */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  {item.source_type === "AI_RECOMMENDED" && !imported ? (
                    <>
                      <span
                        data-testid="ai-suggestion-badge"
                        style={{
                          fontSize: "0.68rem",
                          padding: "2px 6px",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: "var(--accent-light)",
                          color: "var(--accent)",
                          fontWeight: 600,
                        }}
                      >
                        AI Suggestion
                      </span>
                      <button
                        type="button"
                        data-testid="import-poi-btn"
                        onClick={handleImport}
                        disabled={importing}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          fontSize: "0.7rem",
                          padding: "2px 6px",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: "var(--accent-light)",
                          color: "var(--accent)",
                          fontWeight: 500,
                          cursor: "pointer",
                        }}
                        title="Import to My Saved POIs"
                      >
                        <BookmarkPlus size={12} />
                        {importing ? "Saving..." : "Import"}
                      </button>
                    </>
                  ) : item.source_type === "USER_SAVED" || imported ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "3px",
                        fontSize: "0.68rem",
                        padding: "2px 6px",
                        borderRadius: "var(--radius-sm)",
                        backgroundColor: "rgba(16, 185, 129, 0.12)",
                        color: "var(--success)",
                        fontWeight: 500,
                      }}
                      title="Saved in your POI collection"
                    >
                      <Check size={11} /> Saved
                    </span>
                  ) : null}

                  {item.is_backup_for_id ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "3px",
                        fontSize: "0.68rem",
                        padding: "2px 6px",
                        borderRadius: "var(--radius-sm)",
                        backgroundColor: "rgba(245, 158, 11, 0.12)",
                        color: "var(--warning)",
                      }}
                      title="Indoor weather backup option"
                    >
                      <Umbrella size={11} /> Backup
                    </span>
                  ) : null}
                </div>
              </div>

              {/* Sub-info: Time, Duration, Cost, Category */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "0.78rem",
                  color: "var(--text-secondary)",
                }}
              >
                {item.start_time ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <Clock size={12} />
                    {formatTimeSlot(item.start_time, item.end_time)}
                  </span>
                ) : null}

                {item.duration_hours ? (
                  <span>{item.duration_hours}h duration</span>
                ) : null}

                <span style={{ display: "inline-flex", alignItems: "center", gap: "2px" }}>
                  <DollarSign size={12} />
                  {formatCost(item.cost_cents)}
                </span>

                {item.category ? (
                  <span
                    style={{
                      padding: "1px 6px",
                      borderRadius: "var(--radius-sm)",
                      backgroundColor: "var(--bg-hover)",
                      fontSize: "0.72rem",
                      textTransform: "capitalize",
                    }}
                  >
                    {item.category}
                  </span>
                ) : null}
              </div>

              {/* Notes */}
              {item.notes ? (
                <p
                  style={{
                    fontSize: "0.78rem",
                    color: "var(--text-muted)",
                    marginTop: "6px",
                    lineHeight: 1.3,
                  }}
                >
                  {item.notes}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </Draggable>
  );
};
