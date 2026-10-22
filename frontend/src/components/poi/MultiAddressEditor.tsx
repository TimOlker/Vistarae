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
import { Plus, Trash2, MapPin } from "lucide-react";
import type { components } from "../../types/poi-edit-api";

export type AddressRecord = components["schemas"]["AddressRecord"];

export interface MultiAddressEditorProps {
  addresses: AddressRecord[];
  onChange: (addresses: AddressRecord[]) => void;
  disabled?: boolean;
}

export const MultiAddressEditor: React.FC<MultiAddressEditorProps> = ({
  addresses,
  onChange,
  disabled = false,
}) => {
  const handleAddAddress = () => {
    const newAddress: AddressRecord = {
      street: "",
      city: "",
      state_province: "",
      country: "",
      postal_code: "",
    };
    onChange([...addresses, newAddress]);
  };

  const handleRemoveAddress = (index: number) => {
    const updated = addresses.filter((_, i) => i !== index);
    onChange(updated);
  };

  const handleFieldChange = (
    index: number,
    field: keyof AddressRecord,
    value: string,
  ) => {
    const updated = addresses.map((addr, i) => {
      if (i === index) {
        return { ...addr, [field]: value };
      }
      return addr;
    });
    onChange(updated);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        width: "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <label
          style={{
            fontSize: "12px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            gap: "6px",
            color: "var(--text-secondary, #475569)",
          }}
        >
          <MapPin size={14} style={{ color: "var(--accent, #2563eb)" }} />
          Addresses ({addresses.length})
        </label>
        {!disabled && (
          <button
            type="button"
            onClick={handleAddAddress}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm, 6px)",
              background: "var(--accent-light, #eff6ff)",
              color: "var(--accent, #2563eb)",
              border: "1px solid var(--border-color, #e2e8f0)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Plus size={13} />
            Add Address
          </button>
        )}
      </div>

      {addresses.length === 0 ? (
        <div
          style={{
            padding: "16px",
            border: "1px dashed var(--border-color, #cbd5e1)",
            borderRadius: "var(--radius-md, 8px)",
            textAlign: "center",
            fontSize: "12px",
            color: "var(--text-muted, #94a3b8)",
          }}
        >
          No structured addresses entered. Click &ldquo;Add Address&rdquo; to
          add street, city, state, and country.
        </div>
      ) : (
        addresses.map((addr, index) => (
          <div
            key={index}
            style={{
              padding: "12px",
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-color, #e2e8f0)",
              background: "var(--bg-card, #ffffff)",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              position: "relative",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                borderBottom: "1px solid var(--border-color, #f1f5f9)",
                paddingBottom: "6px",
              }}
            >
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "var(--text-secondary, #475569)",
                }}
              >
                Address #{index + 1}
              </span>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => handleRemoveAddress(index)}
                  title="Remove address"
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    padding: "2px",
                    color: "var(--danger, #ef4444)",
                  }}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>

            {/* Street input */}
            <div>
              <label
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  display: "block",
                  marginBottom: "4px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                Street Address
              </label>
              <input
                type="text"
                disabled={disabled}
                placeholder="e.g. 9035 Village Dr"
                maxLength={255}
                value={addr.street || ""}
                onChange={(e) =>
                  handleFieldChange(index, "street", e.target.value)
                }
                style={{
                  width: "100%",
                  padding: "6px 10px",
                  borderRadius: "var(--radius-sm, 6px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-primary, #0f172a)",
                  fontSize: "12px",
                }}
              />
            </div>

            {/* City & State Row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "8px",
              }}
            >
              <div>
                <label
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    display: "block",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  City
                </label>
                <input
                  type="text"
                  disabled={disabled}
                  placeholder="e.g. Yosemite Valley"
                  maxLength={100}
                  value={addr.city || ""}
                  onChange={(e) =>
                    handleFieldChange(index, "city", e.target.value)
                  }
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    background: "var(--bg-surface, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                    fontSize: "12px",
                  }}
                />
              </div>

              <div>
                <label
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    display: "block",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  State / Province
                </label>
                <input
                  type="text"
                  disabled={disabled}
                  placeholder="e.g. CA or California"
                  maxLength={100}
                  value={addr.state_province || ""}
                  onChange={(e) =>
                    handleFieldChange(index, "state_province", e.target.value)
                  }
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    background: "var(--bg-surface, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                    fontSize: "12px",
                  }}
                />
              </div>
            </div>

            {/* Country & Postal Code Row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "8px",
              }}
            >
              <div>
                <label
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    display: "block",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  Country{" "}
                  <span style={{ color: "var(--danger, #ef4444)" }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  disabled={disabled}
                  placeholder="e.g. United States or US"
                  maxLength={100}
                  value={addr.country || ""}
                  onChange={(e) =>
                    handleFieldChange(index, "country", e.target.value)
                  }
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: !addr.country?.trim()
                      ? "1px solid var(--warning, #f59e0b)"
                      : "1px solid var(--border-color, #e2e8f0)",
                    background: "var(--bg-surface, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                    fontSize: "12px",
                  }}
                />
              </div>

              <div>
                <label
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    display: "block",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  Postal / ZIP Code
                </label>
                <input
                  type="text"
                  disabled={disabled}
                  placeholder="e.g. 95389"
                  maxLength={32}
                  value={addr.postal_code || ""}
                  onChange={(e) =>
                    handleFieldChange(index, "postal_code", e.target.value)
                  }
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    background: "var(--bg-surface, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                    fontSize: "12px",
                  }}
                />
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
};
