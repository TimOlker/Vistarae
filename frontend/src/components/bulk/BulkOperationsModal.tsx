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
import { X, AlertTriangle, Trash2, MapPin } from "lucide-react";

export type BulkEditOperationType =
  | "set_rating"
  | "add_visit_date"
  | "set_visit_again"
  | "add_tag"
  | "remove_tag"
  | "add_to_list"
  | "remove_from_list"
  | "update_address";

export interface BulkOperationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPoiIds: string[];
  mode: "edit" | "delete";
  onConfirmEdit: (action: BulkEditOperationType, payload: any) => Promise<void>;
  onConfirmDelete: () => Promise<void>;
}

export const BulkOperationsModal: React.FC<BulkOperationsModalProps> = ({
  isOpen,
  onClose,
  selectedPoiIds,
  mode,
  onConfirmEdit,
  onConfirmDelete,
}) => {
  const [operationType, setOperationType] =
    useState<BulkEditOperationType>("set_rating");

  // Form states
  const [rating, setRating] = useState<number>(5);
  const [visitDate, setVisitDate] = useState<string>(
    new Date().toISOString().split("T")[0],
  );
  const [wantToVisitAgain, setWantToVisitAgain] = useState<boolean>(true);
  const [tagName, setTagName] = useState<string>("");
  const [listId, setListId] = useState<string>("");

  // Address fields
  const [city, setCity] = useState<string>("");
  const [stateProvince, setStateProvince] = useState<string>("");
  const [country, setCountry] = useState<string>("");
  const [clearCity, setClearCity] = useState<boolean>(false);
  const [clearState, setClearState] = useState<boolean>(false);
  const [clearCountry, setClearCountry] = useState<boolean>(false);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      if (mode === "delete") {
        await onConfirmDelete();
      } else {
        let payload: any = {};
        if (operationType === "set_rating") {
          payload = { rating };
        } else if (operationType === "add_visit_date") {
          payload = { visit_date: visitDate };
        } else if (operationType === "set_visit_again") {
          payload = { want_to_visit_again: wantToVisitAgain };
        } else if (
          operationType === "add_tag" ||
          operationType === "remove_tag"
        ) {
          if (!tagName.trim()) {
            throw new Error("Please enter a valid tag name.");
          }
          payload = { tag_name: tagName.trim() };
        } else if (
          operationType === "add_to_list" ||
          operationType === "remove_from_list"
        ) {
          if (!listId.trim()) {
            throw new Error("Please provide a valid list UUID.");
          }
          payload = { list_id: listId.trim() };
        } else if (operationType === "update_address") {
          const clearFields: string[] = [];
          if (clearCity) clearFields.push("city");
          if (clearState) clearFields.push("state_province");
          if (clearCountry) clearFields.push("country");

          payload = {
            address: {
              city: clearCity ? null : city.trim() || null,
              state_province: clearState ? null : stateProvince.trim() || null,
              country: clearCountry ? null : country.trim() || null,
              clear_fields: clearFields,
            },
          };
        }

        await onConfirmEdit(operationType, payload);
      }
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute bulk operation.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={
        mode === "delete" ? "Bulk Delete Confirmation" : "Bulk Edit POIs"
      }
      data-testid="bulk-operations-modal"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1100,
      }}
    >
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          width: "500px",
          maxWidth: "92vw",
          maxHeight: "88vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.15)",
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
            {mode === "delete" ? (
              <Trash2 size={20} style={{ color: "#DC2626" }} />
            ) : (
              <MapPin size={20} style={{ color: "#2563EB" }} />
            )}
            <h3
              style={{
                margin: 0,
                fontSize: "16px",
                fontWeight: 600,
                color: "#111827",
              }}
            >
              {mode === "delete"
                ? `Bulk Delete ${selectedPoiIds.length} POIs`
                : `Bulk Edit ${selectedPoiIds.length} Selected POIs`}
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            data-testid="close-bulk-modal-btn"
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

        {/* Modal Form */}
        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            flex: 1,
          }}
        >
          <div
            style={{
              padding: "20px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            {errorMsg && (
              <div
                style={{
                  padding: "10px",
                  borderRadius: "6px",
                  backgroundColor: "#FEF2F2",
                  color: "#B91C1C",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <AlertTriangle size={15} />
                <span>{errorMsg}</span>
              </div>
            )}

            {mode === "delete" ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  padding: "8px 0",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                    padding: "12px",
                    backgroundColor: "#FEF2F2",
                    borderRadius: "6px",
                    border: "1px solid #FECACA",
                  }}
                >
                  <AlertTriangle
                    size={22}
                    style={{
                      color: "#DC2626",
                      flexShrink: 0,
                      marginTop: "2px",
                    }}
                  />
                  <div>
                    <p
                      style={{
                        margin: "0 0 4px 0",
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#991B1B",
                      }}
                    >
                      Permanent Deletion Warning
                    </p>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "13px",
                        color: "#B91C1C",
                        lineHeight: 1.4,
                      }}
                    >
                      Are you sure you want to delete these{" "}
                      <strong>{selectedPoiIds.length}</strong> points of
                      interest? All tags, lists, and location references
                      associated with these records will be permanently removed.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {/* Select Operation Type */}
                <div>
                  <label
                    htmlFor="bulk-operation-select"
                    style={{
                      display: "block",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#374151",
                      marginBottom: "6px",
                    }}
                  >
                    Select Field to Update
                  </label>
                  <select
                    id="bulk-operation-select"
                    value={operationType}
                    onChange={(e) =>
                      setOperationType(e.target.value as BulkEditOperationType)
                    }
                    data-testid="bulk-operation-type-select"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      border: "1px solid #D1D5DB",
                      borderRadius: "6px",
                      fontSize: "14px",
                      backgroundColor: "#F9FAFB",
                    }}
                  >
                    <option value="set_rating">Star Rating (0 - 5)</option>
                    <option value="add_visit_date">Add Visited Date</option>
                    <option value="set_visit_again">
                      Want to Visit Again Toggle
                    </option>
                    <option value="add_tag">Add Taxonomy Tag</option>
                    <option value="remove_tag">Remove Taxonomy Tag</option>
                    <option value="add_to_list">Add to Curated List</option>
                    <option value="remove_from_list">
                      Remove from Curated List
                    </option>
                    <option value="update_address">
                      Location (City, State, Country)
                    </option>
                  </select>
                </div>

                {/* Operation Content Panels */}
                {operationType === "set_rating" && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#374151",
                      }}
                    >
                      Assign Star Rating
                    </span>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      {[0, 1, 2, 3, 4, 5].map((val) => (
                        <button
                          key={val}
                          type="button"
                          onClick={() => setRating(val)}
                          data-testid={`bulk-rating-opt-${val}`}
                          style={{
                            padding: "6px 12px",
                            borderRadius: "6px",
                            border: `1px solid ${
                              rating === val ? "#2563EB" : "#D1D5DB"
                            }`,
                            backgroundColor:
                              rating === val ? "#EFF6FF" : "#FFFFFF",
                            color: rating === val ? "#2563EB" : "#374151",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          {val === 0 ? "0 (Unrated)" : `${val} ★`}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {operationType === "add_visit_date" && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <label
                      htmlFor="bulk-visit-date-input"
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#374151",
                      }}
                    >
                      Visited Date
                    </label>
                    <input
                      id="bulk-visit-date-input"
                      type="date"
                      value={visitDate}
                      onChange={(e) => setVisitDate(e.target.value)}
                      data-testid="bulk-visit-date-input"
                      style={{
                        padding: "8px 10px",
                        borderRadius: "6px",
                        border: "1px solid #D1D5DB",
                        fontSize: "14px",
                      }}
                    />
                    <p
                      style={{
                        margin: 0,
                        fontSize: "12px",
                        color: "#6B7280",
                      }}
                    >
                      Appends to visit history and marks each POI as visited.
                    </p>
                  </div>
                )}

                {operationType === "set_visit_again" && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#374151",
                      }}
                    >
                      Future Return Intent
                    </span>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <button
                        type="button"
                        onClick={() => setWantToVisitAgain(true)}
                        style={{
                          flex: 1,
                          padding: "8px",
                          borderRadius: "6px",
                          border: `1px solid ${
                            wantToVisitAgain ? "#10B981" : "#D1D5DB"
                          }`,
                          backgroundColor: wantToVisitAgain
                            ? "#ECFDF5"
                            : "#FFFFFF",
                          color: wantToVisitAgain ? "#047857" : "#374151",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Yes, Want to Visit Again
                      </button>
                      <button
                        type="button"
                        onClick={() => setWantToVisitAgain(false)}
                        style={{
                          flex: 1,
                          padding: "8px",
                          borderRadius: "6px",
                          border: `1px solid ${
                            !wantToVisitAgain ? "#6B7280" : "#D1D5DB"
                          }`,
                          backgroundColor: !wantToVisitAgain
                            ? "#F3F4F6"
                            : "#FFFFFF",
                          color: !wantToVisitAgain ? "#1F2937" : "#374151",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        No (Been there, done that)
                      </button>
                    </div>
                  </div>
                )}

                {(operationType === "add_tag" ||
                  operationType === "remove_tag") && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <label
                      htmlFor="bulk-tag-input"
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#374151",
                      }}
                    >
                      {operationType === "add_tag"
                        ? "Tag to Add"
                        : "Tag to Remove"}
                    </label>
                    <input
                      id="bulk-tag-input"
                      type="text"
                      placeholder="e.g. favorite, must-see, unesco"
                      value={tagName}
                      onChange={(e) => setTagName(e.target.value)}
                      data-testid="bulk-tag-input"
                      style={{
                        padding: "8px 10px",
                        borderRadius: "6px",
                        border: "1px solid #D1D5DB",
                        fontSize: "14px",
                      }}
                    />
                  </div>
                )}

                {(operationType === "add_to_list" ||
                  operationType === "remove_from_list") && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <label
                      htmlFor="bulk-list-id-input"
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: "#374151",
                      }}
                    >
                      List UUID
                    </label>
                    <input
                      id="bulk-list-id-input"
                      type="text"
                      placeholder="UUID of target curated list"
                      value={listId}
                      onChange={(e) => setListId(e.target.value)}
                      data-testid="bulk-list-id-input"
                      style={{
                        padding: "8px 10px",
                        borderRadius: "6px",
                        border: "1px solid #D1D5DB",
                        fontSize: "14px",
                      }}
                    />
                  </div>
                )}

                {operationType === "update_address" && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                      padding: "14px",
                      backgroundColor: "#F9FAFB",
                      borderRadius: "6px",
                      border: "1px solid #E5E7EB",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "12px",
                        color: "#6B7280",
                        lineHeight: 1.4,
                      }}
                    >
                      Updates strictly the primary address (
                      <code>addresses[0]</code>), preserving any secondary
                      locations. Check &quot;Clear&quot; to reset a component to
                      empty.
                    </div>

                    {/* City */}
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: "4px",
                        }}
                      >
                        <label
                          htmlFor="bulk-city-input"
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            color: "#374151",
                          }}
                        >
                          City / Town
                        </label>
                        <label
                          style={{
                            fontSize: "11px",
                            color: "#6B7280",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={clearCity}
                            onChange={(e) => setClearCity(e.target.checked)}
                          />
                          Clear City
                        </label>
                      </div>
                      <input
                        id="bulk-city-input"
                        type="text"
                        disabled={clearCity}
                        placeholder="e.g. Kyoto"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        data-testid="bulk-city-input"
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          border: "1px solid #D1D5DB",
                          fontSize: "13px",
                          backgroundColor: clearCity ? "#F3F4F6" : "#FFFFFF",
                        }}
                      />
                    </div>

                    {/* State / Province */}
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: "4px",
                        }}
                      >
                        <label
                          htmlFor="bulk-state-input"
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            color: "#374151",
                          }}
                        >
                          State / Province
                        </label>
                        <label
                          style={{
                            fontSize: "11px",
                            color: "#6B7280",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={clearState}
                            onChange={(e) => setClearState(e.target.checked)}
                          />
                          Clear State
                        </label>
                      </div>
                      <input
                        id="bulk-state-input"
                        type="text"
                        disabled={clearState}
                        placeholder="e.g. Kyoto Prefecture"
                        value={stateProvince}
                        onChange={(e) => setStateProvince(e.target.value)}
                        data-testid="bulk-state-input"
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          border: "1px solid #D1D5DB",
                          fontSize: "13px",
                          backgroundColor: clearState ? "#F3F4F6" : "#FFFFFF",
                        }}
                      />
                    </div>

                    {/* Country */}
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: "4px",
                        }}
                      >
                        <label
                          htmlFor="bulk-country-input"
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            color: "#374151",
                          }}
                        >
                          Country
                        </label>
                        <label
                          style={{
                            fontSize: "11px",
                            color: "#6B7280",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={clearCountry}
                            onChange={(e) => setClearCountry(e.target.checked)}
                          />
                          Clear Country
                        </label>
                      </div>
                      <input
                        id="bulk-country-input"
                        type="text"
                        disabled={clearCountry}
                        placeholder="e.g. Japan"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        data-testid="bulk-country-input"
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          border: "1px solid #D1D5DB",
                          fontSize: "13px",
                          backgroundColor: clearCountry ? "#F3F4F6" : "#FFFFFF",
                        }}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Modal Footer */}
          <div
            style={{
              padding: "14px 20px",
              borderTop: "1px solid #E5E7EB",
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              data-testid="cancel-bulk-modal-btn"
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
              type="submit"
              disabled={isSubmitting}
              data-testid="confirm-bulk-action-btn"
              style={{
                padding: "6px 16px",
                fontSize: "13px",
                fontWeight: 600,
                color: "#FFFFFF",
                backgroundColor: mode === "delete" ? "#DC2626" : "#2563EB",
                border: "none",
                borderRadius: "6px",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                opacity: isSubmitting ? 0.7 : 1,
              }}
            >
              {isSubmitting
                ? "Processing..."
                : mode === "delete"
                  ? `Delete ${selectedPoiIds.length} POIs`
                  : "Apply Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
