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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import type { POIMapFeature, VisitState } from "../../types/map";
import { Star, MapPin, Eye, Edit3, Filter } from "lucide-react";

interface POITableProps {
  pois: POIMapFeature[];
  selectedPoiId?: string | null;
  isViewportFilterActive: boolean;
  onToggleViewportFilter: (active: boolean) => void;
  onSelectPOI: (poi: POIMapFeature) => void;
  onEditPOI?: (poi: POIMapFeature) => void;
}

export const POITable: React.FC<POITableProps> = ({
  pois,
  selectedPoiId,
  isViewportFilterActive,
  onToggleViewportFilter,
  onSelectPOI,
  onEditPOI,
}) => {
  const renderVisitBadge = (state: VisitState) => {
    switch (state) {
      case "visited_return":
        return (
          <span
            style={{
              padding: "3px 8px",
              borderRadius: "9999px",
              fontSize: "11px",
              fontWeight: 600,
              background: "#ecfdf5",
              color: "#047857",
              border: "1px solid #a7f3d0",
            }}
          >
            Visited (Return)
          </span>
        );
      case "visited_do_not_return":
        return (
          <span
            style={{
              padding: "3px 8px",
              borderRadius: "9999px",
              fontSize: "11px",
              fontWeight: 600,
              background: "#fffbeb",
              color: "#b45309",
              border: "1px solid #fde68a",
            }}
          >
            Visited (No Return)
          </span>
        );
      default:
        return (
          <span
            style={{
              padding: "3px 8px",
              borderRadius: "9999px",
              fontSize: "11px",
              fontWeight: 600,
              background: "#eff6ff",
              color: "#1d4ed8",
              border: "1px solid #bfdbfe",
            }}
          >
            Not Visited
          </span>
        );
    }
  };

  const renderStars = (rating: number | null) => {
    if (!rating) return <span style={{ color: "var(--text-muted)" }}>—</span>;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            size={13}
            fill={star <= rating ? "#f59e0b" : "none"}
            color={star <= rating ? "#f59e0b" : "var(--text-muted)"}
          />
        ))}
      </div>
    );
  };

  return (
    <div
      className="poi-table-container"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--bg-surface, #ffffff)",
        borderRadius: "var(--radius-md, 10px)",
        border: "1px solid var(--border-color, #e2e8f0)",
        overflow: "hidden",
      }}
    >
      {/* Header controls bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "12px 16px",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          background: "var(--bg-card, #ffffff)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <h3 style={{ fontSize: "15px", fontWeight: 700 }}>
            Points of Interest ({pois.length})
          </h3>
        </div>

        {/* Viewport Filter Toggle */}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--text-secondary, #475569)",
            cursor: "pointer",
          }}
        >
          <Filter
            size={14}
            color={isViewportFilterActive ? "var(--accent)" : "inherit"}
          />
          <span>Filter to map viewport</span>
          <input
            type="checkbox"
            checked={isViewportFilterActive}
            onChange={(e) => onToggleViewportFilter(e.target.checked)}
            style={{ cursor: "pointer", accentColor: "var(--accent, #2563eb)" }}
          />
        </label>
      </div>

      {/* Table content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {pois.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "48px 16px",
              textAlign: "center",
              color: "var(--text-muted, #94a3b8)",
              gap: "12px",
            }}
          >
            <MapPin size={32} strokeWidth={1.5} />
            <p style={{ fontSize: "14px", fontWeight: 500 }}>
              {isViewportFilterActive
                ? "No POIs found in the current map viewport."
                : "No POIs saved yet. Add a location or import a CSV."}
            </p>
            {isViewportFilterActive && (
              <button
                type="button"
                onClick={() => onToggleViewportFilter(false)}
                style={{
                  fontSize: "12px",
                  color: "var(--accent, #2563eb)",
                  textDecoration: "underline",
                  fontWeight: 600,
                }}
              >
                Disable viewport filter to view all POIs
              </button>
            )}
          </div>
        ) : (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              textAlign: "left",
              fontSize: "13px",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--border-color, #e2e8f0)",
                  background: "var(--bg-hover, #f8fafc)",
                  color: "var(--text-muted, #64748b)",
                  fontSize: "11px",
                  textTransform: "uppercase",
                  fontWeight: 700,
                }}
              >
                <th style={{ padding: "10px 14px" }}>Name</th>
                <th style={{ padding: "10px 14px" }}>Status</th>
                <th style={{ padding: "10px 14px" }}>Rating</th>
                <th style={{ padding: "10px 14px" }}>Location</th>
                <th style={{ padding: "10px 14px" }}>Tags</th>
                <th style={{ padding: "10px 14px", textAlign: "right" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {pois.map((poi) => {
                const isSelected = poi.id === selectedPoiId;
                return (
                  <tr
                    key={poi.id}
                    onClick={() => onSelectPOI(poi)}
                    style={{
                      borderBottom: "1px solid var(--border-color, #f1f5f9)",
                      background: isSelected
                        ? "var(--accent-light, #eff6ff)"
                        : "transparent",
                      cursor: "pointer",
                      transition: "background 100ms ease",
                    }}
                  >
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>
                      {poi.name}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      {renderVisitBadge(poi.visit_state)}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      {renderStars(poi.rating)}
                    </td>
                    <td
                      style={{
                        padding: "10px 14px",
                        color: "var(--text-secondary, #475569)",
                      }}
                    >
                      {poi.city ||
                        poi.address ||
                        `${poi.canonical_lat.toFixed(4)}, ${poi.canonical_lng.toFixed(4)}`}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <div
                        style={{
                          display: "flex",
                          gap: "4px",
                          flexWrap: "wrap",
                        }}
                      >
                        {poi.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            style={{
                              background: "var(--bg-hover, #f1f5f9)",
                              color: "var(--text-secondary, #475569)",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              fontSize: "11px",
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td style={{ padding: "10px 14px", textAlign: "right" }}>
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <button
                          type="button"
                          title="Center on map"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectPOI(poi);
                          }}
                          style={{
                            padding: "4px",
                            borderRadius: "4px",
                            color: "var(--text-secondary)",
                          }}
                        >
                          <Eye size={15} />
                        </button>
                        {onEditPOI && (
                          <button
                            type="button"
                            title="Edit details"
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditPOI(poi);
                            }}
                            style={{
                              padding: "4px",
                              borderRadius: "4px",
                              color: "var(--text-secondary)",
                            }}
                          >
                            <Edit3 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
