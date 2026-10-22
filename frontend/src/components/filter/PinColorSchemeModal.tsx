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
import { X, Palette, Plus, Trash2 } from "lucide-react";
import type { PinColorMode, PinColorScheme } from "../../types/filter";

export interface PinColorSchemeModalProps {
  isOpen: boolean;
  onClose: () => void;
  scheme: PinColorScheme;
  onApply: (updated: PinColorScheme) => void;
}

const DEFAULT_RATING_PALETTE: Record<string, string> = {
  "1": "#EF4444",
  "2": "#F97316",
  "3": "#EAB308",
  "4": "#3B82F6",
  "5": "#10B981",
  "0": "#6B7280",
};

const DEFAULT_VISIT_PALETTE: Record<string, string> = {
  not_visited: "#3B82F6",
  visited_return: "#10B981",
  visited_do_not_return: "#6B7280",
};

export const PinColorSchemeModal: React.FC<PinColorSchemeModalProps> = ({
  isOpen,
  onClose,
  scheme,
  onApply,
}) => {
  const [mode, setMode] = useState<PinColorMode>(scheme.mode || "uniform");
  const [defaultColor, setDefaultColor] = useState<string>(
    scheme.default_color || "#3B82F6",
  );
  const [ratingPalette, setRatingPalette] = useState<Record<string, string>>({
    ...DEFAULT_RATING_PALETTE,
    ...(scheme.mode === "rating" ? scheme.palette : {}),
  });
  const [visitPalette, setVisitPalette] = useState<Record<string, string>>({
    ...DEFAULT_VISIT_PALETTE,
    ...(scheme.mode === "visit_status" ? scheme.palette : {}),
  });
  const [customRules, setCustomRules] = useState<
    Array<{ field: string; operator: string; value: any; color: string }>
  >(scheme.rule_mappings || []);

  if (!isOpen) return null;

  const handleAddCustomRule = () => {
    setCustomRules([
      ...customRules,
      { field: "tag", operator: "has_tag", value: "", color: "#8B5CF6" },
    ]);
  };

  const handleRemoveCustomRule = (index: number) => {
    setCustomRules(customRules.filter((_, idx) => idx !== index));
  };

  const handleUpdateCustomRule = (index: number, field: string, val: any) => {
    const updated = [...customRules];
    updated[index] = { ...updated[index], [field]: val };
    setCustomRules(updated);
  };

  const handleSave = () => {
    let finalPalette: Record<string, string> = {};
    if (mode === "rating") {
      finalPalette = ratingPalette;
    } else if (mode === "visit_status") {
      finalPalette = visitPalette;
    }

    onApply({
      mode,
      default_color: defaultColor,
      palette: finalPalette,
      rule_mappings: mode === "custom" ? customRules : [],
    });
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Map Pin Color Scheme Settings"
      data-testid="pin-color-scheme-modal"
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
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          width: "520px",
          maxWidth: "92vw",
          maxHeight: "85vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #E5E7EB",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Palette size={20} style={{ color: "#3B82F6" }} />
            <h3
              style={{
                margin: 0,
                fontSize: "16px",
                fontWeight: 600,
                color: "#111827",
              }}
            >
              Map Pin Color Scheme
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            data-testid="close-pin-modal-btn"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              color: "#6B7280",
              borderRadius: "4px",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div
          style={{
            padding: "20px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <div>
            <label
              htmlFor="pin-color-mode-select"
              style={{
                display: "block",
                fontSize: "13px",
                fontWeight: 600,
                color: "#374151",
                marginBottom: "6px",
              }}
            >
              Color Scheme Mode
            </label>
            <select
              id="pin-color-mode-select"
              value={mode}
              onChange={(e) => setMode(e.target.value as PinColorMode)}
              data-testid="pin-mode-select"
              style={{
                width: "100%",
                padding: "8px 10px",
                border: "1px solid #D1D5DB",
                borderRadius: "6px",
                fontSize: "14px",
                outline: "none",
                backgroundColor: "#F9FAFB",
              }}
            >
              <option value="uniform">Uniform (All pins same color)</option>
              <option value="rating">Star Rating (1 - 5 stars)</option>
              <option value="visit_status">
                Visit Status (Visited vs Not Visited)
              </option>
              <option value="custom">Custom Tag / Condition Rules</option>
            </select>
          </div>

          {/* Fallback / Uniform Default Color */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 12px",
              backgroundColor: "#F3F4F6",
              borderRadius: "6px",
            }}
          >
            <div>
              <span
                style={{ fontSize: "13px", fontWeight: 500, color: "#374151" }}
              >
                {mode === "uniform" ? "Pin Color" : "Default / Fallback Color"}
              </span>
              <p
                style={{
                  margin: "2px 0 0 0",
                  fontSize: "11px",
                  color: "#6B7280",
                }}
              >
                Hex: {defaultColor.toUpperCase()}
              </p>
            </div>
            <input
              type="color"
              value={defaultColor}
              onChange={(e) => setDefaultColor(e.target.value)}
              data-testid="default-color-picker"
              aria-label="Select default pin color"
              style={{
                width: "36px",
                height: "36px",
                border: "1px solid #D1D5DB",
                borderRadius: "6px",
                cursor: "pointer",
                padding: "2px",
              }}
            />
          </div>

          {/* Rating Mode Options */}
          {mode === "rating" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                border: "1px solid #E5E7EB",
                borderRadius: "6px",
                padding: "12px",
              }}
            >
              <span
                style={{ fontSize: "13px", fontWeight: 600, color: "#374151" }}
              >
                Star Rating Colors
              </span>
              {[
                { key: "5", label: "5 Stars (Exceptional)" },
                { key: "4", label: "4 Stars (Great)" },
                { key: "3", label: "3 Stars (Good)" },
                { key: "2", label: "2 Stars (Fair)" },
                { key: "1", label: "1 Star (Poor)" },
                { key: "0", label: "Unrated (0 Stars)" },
              ].map(({ key, label }) => (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontSize: "13px", color: "#4B5563" }}>
                    {label}
                  </span>
                  <input
                    type="color"
                    value={ratingPalette[key] || "#3B82F6"}
                    aria-label={`Color for ${label}`}
                    onChange={(e) =>
                      setRatingPalette({
                        ...ratingPalette,
                        [key]: e.target.value,
                      })
                    }
                    data-testid={`rating-color-${key}`}
                    style={{
                      width: "32px",
                      height: "30px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                      cursor: "pointer",
                    }}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Visit Status Mode Options */}
          {mode === "visit_status" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                border: "1px solid #E5E7EB",
                borderRadius: "6px",
                padding: "12px",
              }}
            >
              <span
                style={{ fontSize: "13px", fontWeight: 600, color: "#374151" }}
              >
                Visit Status Colors
              </span>
              {[
                { key: "not_visited", label: "Not Visited (Dream)" },
                { key: "visited_return", label: "Visited (Want to Return)" },
                {
                  key: "visited_do_not_return",
                  label: "Visited (Been There, Done That)",
                },
              ].map(({ key, label }) => (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span style={{ fontSize: "13px", color: "#4B5563" }}>
                    {label}
                  </span>
                  <input
                    type="color"
                    value={visitPalette[key] || "#3B82F6"}
                    aria-label={`Color for ${label}`}
                    onChange={(e) =>
                      setVisitPalette({
                        ...visitPalette,
                        [key]: e.target.value,
                      })
                    }
                    data-testid={`visit-color-${key}`}
                    style={{
                      width: "32px",
                      height: "30px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "4px",
                      cursor: "pointer",
                    }}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Custom Mode Options */}
          {mode === "custom" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                border: "1px solid #E5E7EB",
                borderRadius: "6px",
                padding: "12px",
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
                  Rule Mappings
                </span>
                <button
                  type="button"
                  onClick={handleAddCustomRule}
                  data-testid="add-custom-color-rule-btn"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "4px 8px",
                    fontSize: "12px",
                    fontWeight: 500,
                    color: "#3B82F6",
                    background: "rgba(59, 130, 246, 0.08)",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  <Plus size={14} /> Add Mapping
                </button>
              </div>

              {customRules.length === 0 ? (
                <p
                  style={{
                    margin: "8px 0",
                    fontSize: "12px",
                    color: "#6B7280",
                    fontStyle: "italic",
                  }}
                >
                  No custom mappings defined. All pins will use the default
                  color above.
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    maxHeight: "180px",
                    overflowY: "auto",
                  }}
                >
                  {customRules.map((rule, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "6px",
                        backgroundColor: "#F9FAFB",
                        borderRadius: "4px",
                      }}
                    >
                      <select
                        value={rule.field}
                        aria-label={`Field for rule ${idx + 1}`}
                        onChange={(e) =>
                          handleUpdateCustomRule(idx, "field", e.target.value)
                        }
                        style={{
                          padding: "4px 6px",
                          fontSize: "12px",
                          borderRadius: "4px",
                          border: "1px solid #D1D5DB",
                        }}
                      >
                        <option value="tag">Tag</option>
                        <option value="country">Country</option>
                        <option value="city">City</option>
                        <option value="visit_state">Visit State</option>
                      </select>
                      <input
                        type="text"
                        placeholder="Value (e.g. favorite)"
                        value={rule.value || ""}
                        aria-label={`Value for rule ${idx + 1}`}
                        onChange={(e) =>
                          handleUpdateCustomRule(idx, "value", e.target.value)
                        }
                        style={{
                          flex: 1,
                          padding: "4px 6px",
                          fontSize: "12px",
                          borderRadius: "4px",
                          border: "1px solid #D1D5DB",
                        }}
                      />
                      <input
                        type="color"
                        value={rule.color || "#3B82F6"}
                        aria-label={`Color for rule ${idx + 1}`}
                        onChange={(e) =>
                          handleUpdateCustomRule(idx, "color", e.target.value)
                        }
                        style={{
                          width: "28px",
                          height: "26px",
                          border: "1px solid #D1D5DB",
                          borderRadius: "4px",
                          cursor: "pointer",
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveCustomRule(idx)}
                        aria-label={`Delete custom rule ${idx + 1}`}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#EF4444",
                          cursor: "pointer",
                          padding: "2px",
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid #E5E7EB",
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            data-testid="cancel-pin-modal-btn"
            style={{
              padding: "6px 14px",
              fontSize: "13px",
              fontWeight: 500,
              color: "#374151",
              backgroundColor: "#F3F4F6",
              border: "1px solid #D1D5DB",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            data-testid="save-pin-scheme-btn"
            style={{
              padding: "6px 16px",
              fontSize: "13px",
              fontWeight: 500,
              color: "#ffffff",
              backgroundColor: "#3B82F6",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Apply Scheme
          </button>
        </div>
      </div>
    </div>
  );
};
