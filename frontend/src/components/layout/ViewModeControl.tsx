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
import { Columns, Map as MapIcon, Table as TableIcon } from "lucide-react";
import type { LayoutMode, ViewModeOption } from "../../types/layout";

export interface ViewModeControlProps {
  mode: LayoutMode;
  onChange: (mode: LayoutMode) => void;
  className?: string;
}

const VIEW_OPTIONS: ViewModeOption[] = [
  {
    mode: "split",
    label: "Split View",
    ariaLabel: "Switch to Split View (Map and Table side-by-side)",
    tooltip: "Split View (58% Map, 42% Table)",
  },
  {
    mode: "map_only",
    label: "Map Only",
    ariaLabel: "Switch to Map Only (100% width)",
    tooltip: "Map Only (100% width)",
  },
  {
    mode: "table_only",
    label: "Table Only",
    ariaLabel: "Switch to Table Only (100% width)",
    tooltip: "Table Only (100% width)",
  },
];

export const ViewModeControl: React.FC<ViewModeControlProps> = ({
  mode,
  onChange,
  className = "",
}) => {
  return (
    <div
      role="group"
      aria-label="Layout view mode"
      className={`view-mode-control ${className}`.trim()}
      style={{
        display: "inline-flex",
        alignItems: "center",
        backgroundColor: "var(--bg-muted, #f1f5f9)",
        borderRadius: "8px",
        padding: "3px",
        border: "1px solid var(--border-color, #e2e8f0)",
        gap: "2px",
      }}
    >
      {VIEW_OPTIONS.map((option) => {
        const isActive = mode === option.mode;
        return (
          <button
            key={option.mode}
            type="button"
            data-testid={`view-mode-${option.mode}`}
            aria-pressed={isActive}
            aria-label={option.ariaLabel}
            title={option.tooltip}
            onClick={() => onChange(option.mode)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              fontSize: "12px",
              fontWeight: isActive ? 600 : 500,
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              transition: "all 0.15s ease",
              backgroundColor: isActive
                ? "var(--bg-surface, #ffffff)"
                : "transparent",
              color: isActive
                ? "var(--accent, #2563eb)"
                : "var(--text-muted, #64748b)",
              boxShadow: isActive
                ? "0 1px 2px rgba(0, 0, 0, 0.05), 0 1px 1px rgba(0, 0, 0, 0.02)"
                : "none",
              outline: "none",
            }}
          >
            {option.mode === "split" && (
              <Columns size={14} aria-hidden="true" />
            )}
            {option.mode === "map_only" && (
              <MapIcon size={14} aria-hidden="true" />
            )}
            {option.mode === "table_only" && (
              <TableIcon size={14} aria-hidden="true" />
            )}
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default ViewModeControl;
