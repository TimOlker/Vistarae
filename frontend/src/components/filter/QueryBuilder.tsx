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
import { Plus, Trash2, GitFork } from "lucide-react";
import type { QueryGroup, RuleClause } from "../../types/filter";

export interface QueryBuilderProps {
  queryGroup: QueryGroup;
  onChange: (updated: QueryGroup) => void;
  depth?: number;
}

const FIELD_OPTIONS = [
  { value: "city", label: "City / Town" },
  { value: "state_province", label: "State / Province" },
  { value: "country", label: "Country" },
  { value: "rating", label: "Rating (Stars)" },
  { value: "visit_state", label: "Visit Lifecycle State" },
  { value: "already_visited", label: "Already Visited" },
  { value: "visit_pending", label: "Visit Pending" },
  { value: "has_parent", label: "Has Parent (Sub-location)" },
  { value: "tag", label: "Taxonomy Tag" },
  { value: "list_id", label: "Curated List ID" },
];

function getOperatorsForField(
  field: string,
): Array<{ value: string; label: string }> {
  switch (field) {
    case "city":
    case "state_province":
      return [
        { value: "equals", label: "equals" },
        { value: "not_equals", label: "does not equal" },
        { value: "contains", label: "contains" },
        { value: "is_empty", label: "is empty" },
        { value: "is_not_empty", label: "is not empty" },
      ];
    case "country":
      return [
        { value: "equals", label: "equals" },
        { value: "not_equals", label: "does not equal" },
      ];
    case "rating":
      return [
        { value: ">=", label: "greater than or equal (>=)" },
        { value: "<=", label: "less than or equal (<=)" },
        { value: ">", label: "greater than (>)" },
        { value: "<", label: "less than (<)" },
        { value: "=", label: "equals (=)" },
        { value: "!=", label: "not equals (!=)" },
      ];
    case "visit_state":
      return [
        { value: "equals", label: "equals" },
        { value: "not_equals", label: "does not equal" },
      ];
    case "already_visited":
    case "visit_pending":
    case "has_parent":
      return [{ value: "equals", label: "is" }];
    case "tag":
      return [
        { value: "has_tag", label: "has tag" },
        { value: "lacks_tag", label: "lacks tag" },
      ];
    case "list_id":
      return [
        { value: "in_list", label: "in list" },
        { value: "not_in_list", label: "not in list" },
      ];
    default:
      return [{ value: "equals", label: "equals" }];
  }
}

export const QueryBuilder: React.FC<QueryBuilderProps> = ({
  queryGroup,
  onChange,
  depth = 0,
}) => {
  const isAnd = queryGroup.conjunction !== "OR";

  const handleToggleConjunction = () => {
    onChange({
      ...queryGroup,
      conjunction: isAnd ? "OR" : "AND",
    });
  };

  const handleAddClause = () => {
    const newClause: RuleClause = {
      id: "clause-" + Math.random().toString(36).substring(2, 9),
      field: "country",
      operator: "equals",
      value: "",
    };
    onChange({
      ...queryGroup,
      rules: [...queryGroup.rules, newClause],
    });
  };

  const handleAddGroup = () => {
    const newGroup: QueryGroup = {
      id: "group-" + Math.random().toString(36).substring(2, 9),
      conjunction: "AND",
      rules: [
        {
          id: "clause-" + Math.random().toString(36).substring(2, 9),
          field: "city",
          operator: "equals",
          value: "",
        },
      ],
    };
    onChange({
      ...queryGroup,
      rules: [...queryGroup.rules, newGroup],
    });
  };

  const handleUpdateClause = (index: number, updatedClause: RuleClause) => {
    const nextRules = [...queryGroup.rules];
    nextRules[index] = updatedClause;
    onChange({ ...queryGroup, rules: nextRules });
  };

  const handleUpdateSubGroup = (index: number, updatedGroup: QueryGroup) => {
    const nextRules = [...queryGroup.rules];
    nextRules[index] = updatedGroup;
    onChange({ ...queryGroup, rules: nextRules });
  };

  const handleRemoveRule = (index: number) => {
    const nextRules = queryGroup.rules.filter((_, i) => i !== index);
    onChange({ ...queryGroup, rules: nextRules });
  };

  return (
    <div
      className="query-builder-group"
      data-testid={`query-group-depth-${depth}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        padding: depth === 0 ? "0px" : "10px",
        borderRadius: "8px",
        backgroundColor:
          depth === 0 ? "transparent" : "var(--bg-hover, #f8fafc)",
        border: depth === 0 ? "none" : "1px solid var(--border-color, #e2e8f0)",
      }}
    >
      {/* Header toolbar: conjunction and actions */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "4px",
        }}
      >
        <span style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
          Match
        </span>
        <button
          type="button"
          data-testid="conjunction-toggle"
          onClick={handleToggleConjunction}
          style={{
            padding: "2px 8px",
            fontSize: "12px",
            fontWeight: 700,
            borderRadius: "4px",
            border: "1px solid var(--border-color, #cbd5e1)",
            backgroundColor: isAnd ? "#dbeafe" : "#fef3c7",
            color: isAnd ? "#1d4ed8" : "#b45309",
            cursor: "pointer",
          }}
        >
          {queryGroup.conjunction} (click to toggle)
        </button>
        <span style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
          of the following conditions:
        </span>
      </div>

      {/* Rules list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {queryGroup.rules.map((ruleNode, idx) => {
          if ("conjunction" in ruleNode) {
            // Nested sub-group
            return (
              <div key={ruleNode.id} style={{ position: "relative" }}>
                <QueryBuilder
                  queryGroup={ruleNode as QueryGroup}
                  onChange={(updated) => handleUpdateSubGroup(idx, updated)}
                  depth={depth + 1}
                />
                <button
                  type="button"
                  aria-label="Remove group"
                  onClick={() => handleRemoveRule(idx)}
                  style={{
                    position: "absolute",
                    top: "8px",
                    right: "8px",
                    background: "none",
                    border: "none",
                    color: "var(--text-muted, #94a3b8)",
                    cursor: "pointer",
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          }

          // Leaf Rule Clause
          const clause = ruleNode as RuleClause;
          const availableOps = getOperatorsForField(clause.field);
          const isValueDisabled =
            clause.operator === "is_empty" ||
            clause.operator === "is_not_empty";

          return (
            <div
              key={clause.id}
              data-testid={`rule-clause-row-${idx}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
                backgroundColor: "var(--bg-surface, #ffffff)",
                padding: "6px 10px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              {/* Field Select */}
              <select
                aria-label="Filter dimension"
                value={clause.field}
                onChange={(e) => {
                  const nextField = e.target.value;
                  const ops = getOperatorsForField(nextField);
                  handleUpdateClause(idx, {
                    ...clause,
                    field: nextField,
                    operator: ops[0].value,
                    value: nextField === "rating" ? 4 : "",
                  });
                }}
                style={{
                  padding: "4px 8px",
                  fontSize: "12px",
                  borderRadius: "4px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  backgroundColor: "var(--bg-surface, #ffffff)",
                }}
              >
                {FIELD_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>

              {/* Operator Select */}
              <select
                aria-label="Filter operator"
                value={clause.operator}
                onChange={(e) =>
                  handleUpdateClause(idx, {
                    ...clause,
                    operator: e.target.value,
                  })
                }
                style={{
                  padding: "4px 8px",
                  fontSize: "12px",
                  borderRadius: "4px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  backgroundColor: "var(--bg-surface, #ffffff)",
                }}
              >
                {availableOps.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>

              {/* Value Input */}
              {!isValueDisabled && (
                <>
                  {clause.field === "already_visited" ||
                  clause.field === "visit_pending" ||
                  clause.field === "has_parent" ? (
                    <select
                      aria-label="Boolean value"
                      value={String(clause.value)}
                      onChange={(e) =>
                        handleUpdateClause(idx, {
                          ...clause,
                          value: e.target.value === "true",
                        })
                      }
                      style={{
                        padding: "4px 8px",
                        fontSize: "12px",
                        borderRadius: "4px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        backgroundColor: "var(--bg-surface, #ffffff)",
                      }}
                    >
                      <option value="true">True (Yes)</option>
                      <option value="false">False (No)</option>
                    </select>
                  ) : clause.field === "visit_state" ? (
                    <select
                      aria-label="Visit state value"
                      value={String(clause.value || "not_visited")}
                      onChange={(e) =>
                        handleUpdateClause(idx, {
                          ...clause,
                          value: e.target.value,
                        })
                      }
                      style={{
                        padding: "4px 8px",
                        fontSize: "12px",
                        borderRadius: "4px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        backgroundColor: "var(--bg-surface, #ffffff)",
                      }}
                    >
                      <option value="not_visited">Not Visited</option>
                      <option value="visited_return">
                        Visited - Want to Return
                      </option>
                      <option value="visited_do_not_return">
                        Visited - Do Not Return
                      </option>
                    </select>
                  ) : clause.field === "rating" ? (
                    <select
                      aria-label="Rating stars"
                      value={Number(clause.value ?? 4)}
                      onChange={(e) =>
                        handleUpdateClause(idx, {
                          ...clause,
                          value: Number(e.target.value),
                        })
                      }
                      style={{
                        padding: "4px 8px",
                        fontSize: "12px",
                        borderRadius: "4px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        backgroundColor: "var(--bg-surface, #ffffff)",
                      }}
                    >
                      <option value={5}>5 Stars ★★★★★</option>
                      <option value={4}>4 Stars ★★★★☆</option>
                      <option value={3}>3 Stars ★★★☆☆</option>
                      <option value={2}>2 Stars ★★☆☆☆</option>
                      <option value={1}>1 Star ★☆☆☆☆</option>
                      <option value={0}>0 Stars (Unrated)</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      aria-label="Filter text value"
                      placeholder="Enter value..."
                      value={clause.value ?? ""}
                      onChange={(e) =>
                        handleUpdateClause(idx, {
                          ...clause,
                          value: e.target.value,
                        })
                      }
                      style={{
                        padding: "4px 8px",
                        fontSize: "12px",
                        borderRadius: "4px",
                        border: "1px solid var(--border-color, #cbd5e1)",
                        minWidth: "140px",
                        flex: 1,
                      }}
                    />
                  )}
                </>
              )}

              {/* Remove Clause Button */}
              <button
                type="button"
                aria-label="Remove condition"
                title="Remove condition"
                onClick={() => handleRemoveRule(idx)}
                style={{
                  background: "none",
                  border: "none",
                  padding: "4px",
                  color: "var(--text-muted, #94a3b8)",
                  cursor: "pointer",
                }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>

      {/* Action Buttons: Add Condition, Add Sub-group */}
      <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
        <button
          type="button"
          data-testid="add-clause-button"
          onClick={handleAddClause}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "4px 10px",
            fontSize: "12px",
            fontWeight: 500,
            borderRadius: "4px",
            border: "1px dashed var(--border-color, #cbd5e1)",
            backgroundColor: "transparent",
            color: "var(--accent, #2563eb)",
            cursor: "pointer",
          }}
        >
          <Plus size={13} />
          <span>Add Condition</span>
        </button>

        {depth < 2 && (
          <button
            type="button"
            data-testid="add-group-button"
            onClick={handleAddGroup}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 10px",
              fontSize: "12px",
              fontWeight: 500,
              borderRadius: "4px",
              border: "1px dashed var(--border-color, #cbd5e1)",
              backgroundColor: "transparent",
              color: "var(--text-secondary, #475569)",
              cursor: "pointer",
            }}
          >
            <GitFork size={13} />
            <span>Add Sub-group</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default QueryBuilder;
