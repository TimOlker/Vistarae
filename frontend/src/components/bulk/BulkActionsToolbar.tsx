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
import { Edit2, Trash2, X, AlertTriangle } from "lucide-react";

export interface BulkActionsToolbarProps {
  selectedCount: number;
  onOpenBulkEdit: () => void;
  onOpenBulkDelete: () => void;
  onDeselectAll: () => void;
  maxCeiling?: number;
}

export const BulkActionsToolbar: React.FC<BulkActionsToolbarProps> = ({
  selectedCount,
  onOpenBulkEdit,
  onOpenBulkDelete,
  onDeselectAll,
  maxCeiling = 500,
}) => {
  if (selectedCount === 0) return null;

  const isOverCeiling = selectedCount > maxCeiling;
  const canPerformAction = selectedCount > 0 && !isOverCeiling;

  return (
    <div
      data-testid="bulk-actions-toolbar"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 16px",
        backgroundColor: isOverCeiling ? "#FEF2F2" : "#EFF6FF",
        borderBottom: `1px solid ${isOverCeiling ? "#FECACA" : "#BFDBFE"}`,
        transition: "all 0.2s ease-in-out",
        gap: "12px",
        flexWrap: "wrap",
      }}
    >
      {/* Selection count badge & alert */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span
          data-testid="selected-count-badge"
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: isOverCeiling ? "#DC2626" : "#1D4ED8",
          }}
        >
          {selectedCount} POI{selectedCount === 1 ? "" : "s"} selected
        </span>

        {isOverCeiling && (
          <span
            data-testid="ceiling-exceeded-warning"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "2px 8px",
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: 600,
              backgroundColor: "#FEE2E2",
              color: "#B91C1C",
            }}
          >
            <AlertTriangle size={14} />
            Maximum batch ceiling is {maxCeiling} POIs
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <button
          type="button"
          onClick={onOpenBulkEdit}
          disabled={!canPerformAction}
          data-testid="bulk-edit-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            padding: "5px 12px",
            backgroundColor: canPerformAction ? "#2563EB" : "#93C5FD",
            color: "#FFFFFF",
            border: "none",
            borderRadius: "5px",
            fontSize: "12px",
            fontWeight: 600,
            cursor: canPerformAction ? "pointer" : "not-allowed",
          }}
        >
          <Edit2 size={13} />
          <span>Bulk Edit</span>
        </button>

        <button
          type="button"
          onClick={onOpenBulkDelete}
          disabled={!canPerformAction}
          data-testid="bulk-delete-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            padding: "5px 12px",
            backgroundColor: canPerformAction ? "#DC2626" : "#FCA5A5",
            color: "#FFFFFF",
            border: "none",
            borderRadius: "5px",
            fontSize: "12px",
            fontWeight: 600,
            cursor: canPerformAction ? "pointer" : "not-allowed",
          }}
        >
          <Trash2 size={13} />
          <span>Bulk Delete</span>
        </button>

        <button
          type="button"
          onClick={onDeselectAll}
          data-testid="deselect-all-btn"
          title="Deselect all records"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            padding: "5px 8px",
            backgroundColor: "transparent",
            color: "#4B5563",
            border: "1px solid #D1D5DB",
            borderRadius: "5px",
            fontSize: "12px",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          <X size={13} />
          <span>Deselect All</span>
        </button>
      </div>
    </div>
  );
};
