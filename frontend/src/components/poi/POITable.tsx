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

import React, { useMemo } from "react";
import type { POIMapFeature, VisitState } from "../../types/map";
import type { TableConfig } from "../../types/filter";
import {
  Star,
  MapPin,
  Eye,
  Edit3,
  Filter,
  CheckSquare,
  Square,
} from "lucide-react";
import { BulkActionsToolbar } from "../bulk/BulkActionsToolbar";

export interface POITableProps {
  pois: POIMapFeature[];
  selectedPoiId?: string | null;
  isViewportFilterActive: boolean;
  onToggleViewportFilter: (active: boolean) => void;
  onSelectPOI: (poi: POIMapFeature) => void;
  onEditPOI?: (poi: POIMapFeature) => void;
  tableConfig?: TableConfig;
  multiSelectMode?: boolean;
  onToggleMultiSelectMode?: () => void;
  selectedPoiIds?: string[];
  onToggleSelectPoi?: (id: string) => void;
  onToggleSelectAll?: () => void;
  onOpenBulkEdit?: () => void;
  onOpenBulkDelete?: () => void;
  onDeselectAll?: () => void;
}

export const POITable: React.FC<POITableProps> = ({
  pois,
  selectedPoiId,
  isViewportFilterActive,
  onToggleViewportFilter,
  onSelectPOI,
  onEditPOI,
  tableConfig,
  multiSelectMode = false,
  onToggleMultiSelectMode,
  selectedPoiIds = [],
  onToggleSelectPoi,
  onToggleSelectAll,
  onOpenBulkEdit,
  onOpenBulkDelete,
  onDeselectAll,
}) => {
  // Sort POIs based on tableConfig if specified
  const sortedPois = useMemo(() => {
    if (!tableConfig?.sort || tableConfig.sort.direction === "unsorted") {
      return pois;
    }
    const { column, direction } = tableConfig.sort;
    const modifier = direction === "desc" ? -1 : 1;

    return [...pois].sort((a, b) => {
      let valA: any = "";
      let valB: any = "";

      if (column === "name") {
        valA = a.name || "";
        valB = b.name || "";
        return valA.localeCompare(valB) * modifier;
      }
      if (column === "city") {
        valA = a.city || "";
        valB = b.city || "";
        return valA.localeCompare(valB) * modifier;
      }
      if (column === "state") {
        valA = a.state || "";
        valB = b.state || "";
        return valA.localeCompare(valB) * modifier;
      }
      if (column === "country") {
        valA = a.country || "";
        valB = b.country || "";
        return valA.localeCompare(valB) * modifier;
      }
      if (column === "rating") {
        valA = a.rating ?? -1;
        valB = b.rating ?? -1;
        return (valA - valB) * modifier;
      }
      if (column === "visit_state") {
        valA = a.visit_state || "";
        valB = b.visit_state || "";
        return valA.localeCompare(valB) * modifier;
      }
      if (column === "tags") {
        valA = (a.tags || []).join(",");
        valB = (b.tags || []).join(",");
        return valA.localeCompare(valB) * modifier;
      }
      return 0;
    });
  }, [pois, tableConfig]);

  // Determine active columns and order
  const activeColumns = useMemo(() => {
    const defaultCols = ["name", "city", "rating", "visit_state", "tags"];
    if (!tableConfig) return defaultCols;

    const visibleSet = new Set(tableConfig.visible_columns);
    const order =
      tableConfig.column_order.length > 0
        ? tableConfig.column_order
        : defaultCols;
    return order.filter((col) => visibleSet.has(col));
  }, [tableConfig]);

  const allFilteredSelected = useMemo(() => {
    if (pois.length === 0) return false;
    return pois.every((p) => selectedPoiIds.includes(p.id));
  }, [pois, selectedPoiIds]);

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

  const renderStars = (rating: number | null | undefined) => {
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

  const renderColumnHeader = (colId: string) => {
    switch (colId) {
      case "name":
        return "Name";
      case "city":
        return "City / Town";
      case "state":
        return "State / Province";
      case "country":
        return "Country";
      case "rating":
        return "Rating";
      case "visit_state":
        return "Status";
      case "tags":
        return "Tags";
      default:
        return colId;
    }
  };

  const renderCell = (colId: string, poi: POIMapFeature) => {
    switch (colId) {
      case "name":
        return (
          <span style={{ fontWeight: 600, color: "#111827" }}>{poi.name}</span>
        );
      case "city":
        return (
          <span style={{ color: "var(--text-secondary, #475569)" }}>
            {poi.city || "—"}
          </span>
        );
      case "state":
        return (
          <span style={{ color: "var(--text-secondary, #475569)" }}>
            {poi.state || "—"}
          </span>
        );
      case "country":
        return (
          <span style={{ color: "var(--text-secondary, #475569)" }}>
            {poi.country || "—"}
          </span>
        );
      case "rating":
        return renderStars(poi.rating);
      case "visit_state":
        return renderVisitBadge(poi.visit_state);
      case "tags":
        return (
          <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
            {(poi.tags || []).slice(0, 3).map((tag) => (
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
        );
      default:
        return null;
    }
  };

  return (
    <div
      className="poi-table-container"
      data-testid="poi-table-container"
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
          padding: "10px 16px",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          background: "var(--bg-card, #ffffff)",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, margin: 0 }}>
            Points of Interest ({pois.length})
          </h3>

          {/* Multi-Select Toggle Button */}
          {onToggleMultiSelectMode && (
            <button
              type="button"
              onClick={onToggleMultiSelectMode}
              data-testid="multi-select-toggle-btn"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "5px",
                padding: "4px 8px",
                borderRadius: "5px",
                fontSize: "12px",
                fontWeight: 600,
                border: "1px solid #D1D5DB",
                backgroundColor: multiSelectMode ? "#EFF6FF" : "#F9FAFB",
                color: multiSelectMode ? "#2563EB" : "#4B5563",
                cursor: "pointer",
              }}
            >
              {multiSelectMode ? (
                <CheckSquare size={14} />
              ) : (
                <Square size={14} />
              )}
              <span>
                {multiSelectMode ? "Cancel Multi-Select" : "Multi-Select"}
              </span>
            </button>
          )}
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

      {/* Bulk Actions Toolbar */}
      {multiSelectMode &&
        selectedPoiIds.length > 0 &&
        onOpenBulkEdit &&
        onOpenBulkDelete &&
        onDeselectAll && (
          <BulkActionsToolbar
            selectedCount={selectedPoiIds.length}
            onOpenBulkEdit={onOpenBulkEdit}
            onOpenBulkDelete={onOpenBulkDelete}
            onDeselectAll={onDeselectAll}
          />
        )}

      {/* Table content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {sortedPois.length === 0 ? (
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
                : "No POIs match your filter criteria or none saved yet."}
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
                  background: "none",
                  border: "none",
                  cursor: "pointer",
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
                {/* Master checkbox column if multi-select mode */}
                {multiSelectMode && (
                  <th style={{ padding: "10px 14px", width: "40px" }}>
                    <input
                      type="checkbox"
                      data-testid="master-select-all-checkbox"
                      aria-label="Select all visible POIs"
                      checked={allFilteredSelected}
                      onChange={onToggleSelectAll}
                      style={{ cursor: "pointer", accentColor: "#2563eb" }}
                    />
                  </th>
                )}

                {activeColumns.map((colId) => (
                  <th key={colId} style={{ padding: "10px 14px" }}>
                    {renderColumnHeader(colId)}
                  </th>
                ))}
                <th style={{ padding: "10px 14px", textAlign: "right" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPois.map((poi) => {
                const isSelected = poi.id === selectedPoiId;
                const isChecked = selectedPoiIds.includes(poi.id);

                return (
                  <tr
                    key={poi.id}
                    onClick={() => {
                      if (multiSelectMode && onToggleSelectPoi) {
                        onToggleSelectPoi(poi.id);
                      } else {
                        onSelectPOI(poi);
                      }
                    }}
                    data-testid={`poi-row-${poi.id}`}
                    style={{
                      borderBottom: "1px solid var(--border-color, #f1f5f9)",
                      background: isChecked
                        ? "#F0FDF4"
                        : isSelected
                          ? "var(--accent-light, #eff6ff)"
                          : "transparent",
                      cursor: "pointer",
                      transition: "background 100ms ease",
                    }}
                  >
                    {/* Row checkbox in multi-select mode */}
                    {multiSelectMode && (
                      <td
                        style={{ padding: "10px 14px" }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          data-testid={`poi-checkbox-${poi.id}`}
                          aria-label={`Select ${poi.name}`}
                          checked={isChecked}
                          onChange={() => onToggleSelectPoi?.(poi.id)}
                          style={{ cursor: "pointer", accentColor: "#2563eb" }}
                        />
                      </td>
                    )}

                    {activeColumns.map((colId) => (
                      <td key={colId} style={{ padding: "10px 14px" }}>
                        {renderCell(colId, poi)}
                      </td>
                    ))}

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
                            background: "none",
                            border: "none",
                            cursor: "pointer",
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
                              background: "none",
                              border: "none",
                              cursor: "pointer",
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
