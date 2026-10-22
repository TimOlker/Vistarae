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
import {
  ChevronDown,
  ChevronUp,
  Filter,
  RotateCcw,
  Columns,
  Palette,
  Check,
} from "lucide-react";
import type {
  FilterRule,
  PinColorScheme,
  QueryGroup,
  TableConfig,
} from "../../types/filter";
import { QueryBuilder } from "./QueryBuilder";
import { SavedRuleSelector } from "./SavedRuleSelector";
import { ColumnConfigModal } from "./ColumnConfigModal";
import { PinColorSchemeModal } from "./PinColorSchemeModal";

export interface FilterBarProps {
  queryGroup: QueryGroup;
  onQueryGroupChange: (updated: QueryGroup) => void;
  onApplyFilter: () => void;
  onClearFilter: () => void;
  savedRules: FilterRule[];
  activeRuleId: string | null;
  onSelectRule: (rule: FilterRule | null) => void;
  onSaveRule: (name: string, isOverwrite: boolean) => Promise<void>;
  onDeleteRule: (id: string) => Promise<void>;
  tableConfig: TableConfig;
  onTableConfigChange: (updated: TableConfig) => void;
  pinColorScheme: PinColorScheme;
  onPinColorSchemeChange: (updated: PinColorScheme) => void;
}

function countClauses(group: QueryGroup): number {
  let count = 0;
  for (const item of group.rules) {
    if ("rules" in item) {
      count += countClauses(item as QueryGroup);
    } else {
      count += 1;
    }
  }
  return count;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  queryGroup,
  onQueryGroupChange,
  onApplyFilter,
  onClearFilter,
  savedRules,
  activeRuleId,
  onSelectRule,
  onSaveRule,
  onDeleteRule,
  tableConfig,
  onTableConfigChange,
  pinColorScheme,
  onPinColorSchemeChange,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [isColumnModalOpen, setIsColumnModalOpen] = useState<boolean>(false);
  const [isPinModalOpen, setIsPinModalOpen] = useState<boolean>(false);

  const clauseCount = countClauses(queryGroup);

  return (
    <div
      data-testid="filter-bar"
      style={{
        borderBottom: "1px solid #E5E7EB",
        backgroundColor: "#FFFFFF",
        transition: "all 0.2s ease-in-out",
      }}
    >
      {/* Primary Toolbar Row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 16px",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        {/* Left Section: Expand Toggle & Summary */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            data-testid="filter-bar-toggle-btn"
            aria-expanded={isExpanded}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              backgroundColor: isExpanded ? "#EFF6FF" : "#F9FAFB",
              color: isExpanded ? "#2563EB" : "#374151",
              border: `1px solid ${isExpanded ? "#BFDBFE" : "#D1D5DB"}`,
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <Filter size={15} />
            <span>Filters & Views</span>
            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {/* Active Criteria Summary Badge */}
          <span
            data-testid="active-criteria-badge"
            style={{
              padding: "3px 8px",
              borderRadius: "9999px",
              fontSize: "12px",
              fontWeight: 500,
              backgroundColor: clauseCount > 0 ? "#DCFCE7" : "#F3F4F6",
              color: clauseCount > 0 ? "#166534" : "#6B7280",
            }}
          >
            {clauseCount > 0
              ? `${clauseCount} active criteria`
              : "No active filters"}
          </span>
        </div>

        {/* Center Section: Saved Rules Selector */}
        <div style={{ flex: 1, minWidth: "240px", maxWidth: "420px" }}>
          <SavedRuleSelector
            savedRules={savedRules}
            activeRuleId={activeRuleId}
            onSelectRule={onSelectRule}
            onSaveRule={onSaveRule}
            onDeleteRule={onDeleteRule}
          />
        </div>

        {/* Right Section: View Customizations & Execution Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            type="button"
            onClick={() => setIsColumnModalOpen(true)}
            data-testid="open-column-config-btn"
            title="Configure POI Table Columns"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "5px",
              padding: "6px 10px",
              backgroundColor: "#F9FAFB",
              border: "1px solid #D1D5DB",
              borderRadius: "6px",
              fontSize: "13px",
              color: "#374151",
              cursor: "pointer",
            }}
          >
            <Columns size={15} />
            <span>Columns</span>
          </button>

          <button
            type="button"
            onClick={() => setIsPinModalOpen(true)}
            data-testid="open-pin-colors-btn"
            title="Configure Map Pin Color Scheme"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "5px",
              padding: "6px 10px",
              backgroundColor: "#F9FAFB",
              border: "1px solid #D1D5DB",
              borderRadius: "6px",
              fontSize: "13px",
              color: "#374151",
              cursor: "pointer",
            }}
          >
            <Palette size={15} />
            <span>Pin Colors</span>
          </button>

          <div
            style={{
              width: "1px",
              height: "20px",
              backgroundColor: "#E5E7EB",
              margin: "0 2px",
            }}
          />

          <button
            type="button"
            onClick={onClearFilter}
            data-testid="clear-filter-btn"
            title="Reset active query filters"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "6px 10px",
              backgroundColor: "#FFFFFF",
              border: "1px solid #D1D5DB",
              borderRadius: "6px",
              fontSize: "13px",
              color: "#4B5563",
              cursor: "pointer",
            }}
          >
            <RotateCcw size={14} />
            <span>Clear</span>
          </button>

          <button
            type="button"
            onClick={onApplyFilter}
            data-testid="apply-filter-btn"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              backgroundColor: "#2563EB",
              border: "none",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: 600,
              color: "#FFFFFF",
              cursor: "pointer",
              boxShadow: "0 1px 2px rgba(0, 0, 0, 0.05)",
            }}
          >
            <Check size={15} />
            <span>Apply</span>
          </button>
        </div>
      </div>

      {/* Expandable Visual Query Builder Panel */}
      {isExpanded && (
        <div
          data-testid="query-builder-container"
          style={{
            padding: "16px",
            borderTop: "1px solid #E5E7EB",
            backgroundColor: "#F9FAFB",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "#374151",
              }}
            >
              Visual Query Builder
            </span>
            <span style={{ fontSize: "12px", color: "#6B7280" }}>
              Combine multiple conditions to filter both Map and POI Table
            </span>
          </div>

          <QueryBuilder queryGroup={queryGroup} onChange={onQueryGroupChange} />

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
              paddingTop: "8px",
              borderTop: "1px solid #E5E7EB",
            }}
          >
            <button
              type="button"
              onClick={onClearFilter}
              style={{
                padding: "6px 12px",
                fontSize: "13px",
                color: "#4B5563",
                backgroundColor: "#FFFFFF",
                border: "1px solid #D1D5DB",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              Reset Clauses
            </button>
            <button
              type="button"
              onClick={onApplyFilter}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 16px",
                backgroundColor: "#2563EB",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: 600,
                color: "#FFFFFF",
                cursor: "pointer",
              }}
            >
              <Check size={14} />
              Apply Filter
            </button>
          </div>
        </div>
      )}

      {/* Modals */}
      <ColumnConfigModal
        isOpen={isColumnModalOpen}
        onClose={() => setIsColumnModalOpen(false)}
        config={tableConfig}
        onApply={onTableConfigChange}
      />

      <PinColorSchemeModal
        isOpen={isPinModalOpen}
        onClose={() => setIsPinModalOpen(false)}
        scheme={pinColorScheme}
        onApply={onPinColorSchemeChange}
      />
    </div>
  );
};
