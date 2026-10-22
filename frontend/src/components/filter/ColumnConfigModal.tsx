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
import { ArrowUp, ArrowDown, X, Columns } from "lucide-react";
import type { SortDirection, TableConfig } from "../../types/filter";

export interface ColumnConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: TableConfig;
  onApply: (updated: TableConfig) => void;
}

const ALL_COLUMNS: Array<{ id: string; label: string }> = [
  { id: "name", label: "POI Name" },
  { id: "city", label: "City / Town" },
  { id: "state", label: "State / Province" },
  { id: "country", label: "Country" },
  { id: "rating", label: "Star Rating" },
  { id: "visit_state", label: "Visit Status" },
  { id: "tags", label: "Taxonomy Tags" },
];

export const ColumnConfigModal: React.FC<ColumnConfigModalProps> = ({
  isOpen,
  onClose,
  config,
  onApply,
}) => {
  const [visibleCols, setVisibleCols] = useState<string[]>(
    config.visible_columns,
  );
  const [colOrder, setColOrder] = useState<string[]>(
    config.column_order.length > 0
      ? config.column_order
      : ALL_COLUMNS.map((c) => c.id),
  );
  const [sortCol, setSortCol] = useState<string>(config.sort.column || "name");
  const [sortDir, setSortDir] = useState<SortDirection>(
    config.sort.direction || "asc",
  );

  if (!isOpen) return null;

  const handleToggleVisible = (id: string) => {
    if (visibleCols.includes(id)) {
      if (visibleCols.length === 1) return; // Keep at least one column
      setVisibleCols(visibleCols.filter((c) => c !== id));
    } else {
      setVisibleCols([...visibleCols, id]);
    }
  };

  const handleMove = (index: number, direction: "up" | "down") => {
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= colOrder.length) return;
    const next = [...colOrder];
    const temp = next[index];
    next[index] = next[targetIdx];
    next[targetIdx] = temp;
    setColOrder(next);
  };

  const handleSave = () => {
    onApply({
      visible_columns: visibleCols,
      column_order: colOrder,
      sort: {
        column: sortCol,
        direction: sortDir,
      },
    });
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Table Columns and Sort Settings"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: "var(--bg-surface, #ffffff)",
          borderRadius: "12px",
          width: "440px",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow:
            "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Columns size={18} style={{ color: "var(--accent, #2563eb)" }} />
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>
              Customize Table Columns
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div
          style={{
            padding: "16px 20px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          {/* Column Ordering & Visibility */}
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: "8px",
              }}
            >
              Visible Columns & Sequence
            </label>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "6px" }}
            >
              {colOrder.map((colId, index) => {
                const meta = ALL_COLUMNS.find((c) => c.id === colId) || {
                  id: colId,
                  label: colId,
                };
                const isChecked = visibleCols.includes(colId);
                return (
                  <div
                    key={colId}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      backgroundColor: isChecked
                        ? "var(--bg-surface, #ffffff)"
                        : "#f8fafc",
                    }}
                  >
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        fontSize: "13px",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleVisible(colId)}
                      />
                      <span
                        style={{
                          fontWeight: isChecked ? 600 : 400,
                          color: isChecked ? "inherit" : "var(--text-muted)",
                        }}
                      >
                        {meta.label}
                      </span>
                    </label>

                    <div style={{ display: "flex", gap: "4px" }}>
                      <button
                        type="button"
                        aria-label={`Move ${meta.label} up`}
                        disabled={index === 0}
                        onClick={() => handleMove(index, "up")}
                        style={{
                          padding: "2px 6px",
                          borderRadius: "4px",
                          border: "1px solid var(--border-color, #cbd5e1)",
                          background: "transparent",
                          cursor: index === 0 ? "not-allowed" : "pointer",
                          opacity: index === 0 ? 0.4 : 1,
                        }}
                      >
                        <ArrowUp size={12} />
                      </button>
                      <button
                        type="button"
                        aria-label={`Move ${meta.label} down`}
                        disabled={index === colOrder.length - 1}
                        onClick={() => handleMove(index, "down")}
                        style={{
                          padding: "2px 6px",
                          borderRadius: "4px",
                          border: "1px solid var(--border-color, #cbd5e1)",
                          background: "transparent",
                          cursor:
                            index === colOrder.length - 1
                              ? "not-allowed"
                              : "pointer",
                          opacity: index === colOrder.length - 1 ? 0.4 : 1,
                        }}
                      >
                        <ArrowDown size={12} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Default Sorting */}
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: "8px",
              }}
            >
              Default Sorting Specification (REQ-MAIN-019)
            </label>
            <div style={{ display: "flex", gap: "10px" }}>
              <select
                aria-label="Sort column"
                value={sortCol}
                onChange={(e) => setSortCol(e.target.value)}
                style={{
                  flex: 1,
                  padding: "6px 10px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  fontSize: "13px",
                }}
              >
                {ALL_COLUMNS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>

              <select
                aria-label="Sort direction"
                value={sortDir}
                onChange={(e) => setSortDir(e.target.value as SortDirection)}
                style={{
                  width: "140px",
                  padding: "6px 10px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  fontSize: "13px",
                }}
              >
                <option value="asc">Ascending (A-Z, 0-9)</option>
                <option value="desc">Descending (Z-A, 9-0)</option>
                <option value="unsorted">Unsorted</option>
              </select>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
            padding: "12px 20px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
            backgroundColor: "var(--bg-hover, #f8fafc)",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "1px solid var(--border-color, #cbd5e1)",
              background: "transparent",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            data-testid="apply-column-config-btn"
            onClick={handleSave}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Apply Columns
          </button>
        </div>
      </div>
    </div>
  );
};

export default ColumnConfigModal;
