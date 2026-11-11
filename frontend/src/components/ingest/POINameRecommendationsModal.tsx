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

import React, { useState, useMemo } from "react";
import {
  X,
  Sparkles,
  MapPin,
  CheckCircle2,
  ArrowRight,
  CheckSquare,
  Square,
  AlertCircle,
} from "lucide-react";
import type { CandidateItem } from "../../services/ingestApi";
import { WorkbenchMap } from "./WorkbenchMap";

export interface POINameRecommendationItem {
  candidate: CandidateItem;
  originalName: string;
  recommendedName: string;
  locality: string;
  adminLevel2: string;
  adminLevel1: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
}

export interface POINameRecommendationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  candidates: CandidateItem[];
  onAcceptChanges: (
    acceptedUpdates: Array<{ candidateId: string; newName: string }>,
  ) => Promise<void> | void;
}

/**
 * Extracts candidate POIs that have an enhanced or canonical name recommendation
 * differing from the original staged POI name.
 */
export function extractNameRecommendations(
  candidates: CandidateItem[],
): POINameRecommendationItem[] {
  const recommendations: POINameRecommendationItem[] = [];

  for (const c of candidates) {
    let recName: string | null = null;

    if (c.recommended_poi_name && typeof c.recommended_poi_name === "string") {
      recName = c.recommended_poi_name.trim();
    } else if (
      c.raw_geocoding &&
      typeof c.raw_geocoding === "object" &&
      typeof c.raw_geocoding.resolved_name === "string"
    ) {
      recName = c.raw_geocoding.resolved_name.trim();
    } else if (
      Array.isArray(c.addresses) &&
      c.addresses.length > 0 &&
      c.addresses[0]?.raw_geocoding?.resolved_name
    ) {
      recName = String(c.addresses[0].raw_geocoding.resolved_name).trim();
    }

    if (
      recName &&
      recName.length > 0 &&
      recName.toLowerCase() !== (c.poi_name || "").trim().toLowerCase()
    ) {
      const lat =
        c.latitude != null && !isNaN(Number(c.latitude))
          ? Number(c.latitude)
          : null;
      const lon =
        c.longitude != null && !isNaN(Number(c.longitude))
          ? Number(c.longitude)
          : null;

      recommendations.push({
        candidate: c,
        originalName: (c.poi_name || "").trim(),
        recommendedName: recName,
        locality: c.locality || c.city || "",
        adminLevel2: c.admin_level_2 || "",
        adminLevel1: c.admin_level_1 || c.state_province || "",
        country: c.country || "",
        latitude: lat,
        longitude: lon,
      });
    }
  }

  return recommendations;
}

export const POINameRecommendationsModal: React.FC<
  POINameRecommendationsModalProps
> = ({ isOpen, onClose, candidates, onAcceptChanges }) => {
  const recommendations = useMemo(
    () => extractNameRecommendations(candidates),
    [candidates],
  );

  // Accept toggle state per candidate ID (default off = false)
  const [acceptedMap, setAcceptedMap] = useState<Record<string, boolean>>({});
  // Selected candidate ID for map preview in the right column
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Default selection to first item when list is populated
  const activeCandidateId =
    selectedCandidateId && recommendations.some((r) => r.candidate.id === selectedCandidateId)
      ? selectedCandidateId
      : recommendations[0]?.candidate.id || null;

  const activeItem = useMemo(
    () => recommendations.find((r) => r.candidate.id === activeCandidateId) || null,
    [recommendations, activeCandidateId],
  );

  if (!isOpen) return null;

  const handleToggle = (candidateId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setAcceptedMap((prev) => ({
      ...prev,
      [candidateId]: !prev[candidateId],
    }));
  };

  const acceptedCount = recommendations.filter(
    (r) => acceptedMap[r.candidate.id],
  ).length;

  const handleToggleAll = () => {
    const allChecked = recommendations.every(
      (r) => acceptedMap[r.candidate.id],
    );
    const updated: Record<string, boolean> = {};
    for (const r of recommendations) {
      updated[r.candidate.id] = !allChecked;
    }
    setAcceptedMap(updated);
  };

  const handleApplyChanges = async () => {
    const acceptedUpdates = recommendations
      .filter((r) => acceptedMap[r.candidate.id])
      .map((r) => ({
        candidateId: r.candidate.id,
        newName: r.recommendedName,
      }));

    setIsSubmitting(true);
    try {
      await onAcceptChanges(acceptedUpdates);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.75)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      data-testid="poi-name-recommendations-modal"
    >
      <div
        style={{
          width: "95vw",
          maxWidth: "1350px",
          height: "90vh",
          maxHeight: "880px",
          backgroundColor: "#ffffff",
          borderRadius: "12px",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          overflow: "hidden",
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 24px",
            borderBottom: "1px solid #e2e8f0",
            backgroundColor: "#f8fafc",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                backgroundColor: "#e0f2fe",
                color: "#0284c7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Sparkles size={20} />
            </div>
            <div>
              <h2
                style={{
                  fontSize: "18px",
                  fontWeight: 700,
                  color: "#0f172a",
                  margin: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                POI Name Recommendations
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    backgroundColor: "#e2e8f0",
                    color: "#334155",
                    padding: "2px 8px",
                    borderRadius: "12px",
                  }}
                >
                  {recommendations.length} {recommendations.length === 1 ? "Suggestion" : "Suggestions"}
                </span>
              </h2>
              <p
                style={{
                  fontSize: "13px",
                  color: "#64748b",
                  margin: "2px 0 0 0",
                }}
              >
                Canonical names, official landmarks, and alternate spellings found during geocoding.
                Review and toggle the names you want to accept.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            data-testid="close-recommendations-modal-btn"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#94a3b8",
              padding: "6px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            title="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body: Two-column layout */}
        <div
          style={{
            flex: 1,
            display: "flex",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          {/* Left Column: Scrolled Table of Recommendations */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              borderRight: "1px solid #e2e8f0",
              overflow: "hidden",
            }}
          >
            {/* Table Control Bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 20px",
                backgroundColor: "#f1f5f9",
                borderBottom: "1px solid #e2e8f0",
                fontSize: "12px",
                color: "#475569",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  type="button"
                  onClick={handleToggleAll}
                  data-testid="toggle-all-recommendations-btn"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    background: "none",
                    border: "1px solid #cbd5e1",
                    borderRadius: "4px",
                    padding: "4px 8px",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                    color: "#1e293b",
                    backgroundColor: "#ffffff",
                  }}
                >
                  {recommendations.length > 0 &&
                  recommendations.every((r) => acceptedMap[r.candidate.id]) ? (
                    <>
                      <CheckSquare size={14} color="#0284c7" /> Deselect All
                    </>
                  ) : (
                    <>
                      <Square size={14} color="#64748b" /> Select All
                    </>
                  )}
                </button>
                <span>
                  <strong>{acceptedCount}</strong> of {recommendations.length} selected
                </span>
              </div>
              <span style={{ fontSize: "11px", color: "#64748b" }}>
                Click a row to preview on the map
              </span>
            </div>

            {/* Scrollable Table Area */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                overflowX: "auto",
              }}
              data-testid="recommendations-scrolled-section"
            >
              {recommendations.length === 0 ? (
                <div
                  style={{
                    padding: "48px 24px",
                    textAlign: "center",
                    color: "#64748b",
                  }}
                >
                  <CheckCircle2 size={40} color="#10b981" style={{ margin: "0 auto 12px" }} />
                  <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#1e293b", margin: 0 }}>
                    No POI Name Recommendations
                  </h3>
                  <p style={{ fontSize: "13px", marginTop: "6px" }}>
                    All staged POI names currently match their canonical geocoded locations.
                  </p>
                </div>
              ) : (
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    textAlign: "left",
                    fontSize: "12px",
                  }}
                  data-testid="recommendations-table"
                >
                  <thead>
                    <tr
                      style={{
                        backgroundColor: "#f8fafc",
                        borderBottom: "1px solid #cbd5e1",
                        position: "sticky",
                        top: 0,
                        zIndex: 10,
                      }}
                    >
                      <th style={{ padding: "10px 14px", width: "80px", textAlign: "center" }}>
                        Accept
                      </th>
                      <th style={{ padding: "10px 14px", minWidth: "160px" }}>Original POI Name</th>
                      <th style={{ padding: "10px 14px", minWidth: "160px" }}>Recommended POI Name</th>
                      <th style={{ padding: "10px 14px", minWidth: "110px" }}>Locality (Town/City)</th>
                      <th style={{ padding: "10px 14px", minWidth: "110px" }}>Admin Level 2 (County/District)</th>
                      <th style={{ padding: "10px 14px", minWidth: "120px" }}>Admin Level 1 (State/Province)</th>
                      <th style={{ padding: "10px 14px", minWidth: "100px" }}>Country</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recommendations.map((rec) => {
                      const isSelected = rec.candidate.id === activeCandidateId;
                      const isAccepted = Boolean(acceptedMap[rec.candidate.id]);

                      return (
                        <tr
                          key={rec.candidate.id}
                          onClick={() => setSelectedCandidateId(rec.candidate.id)}
                          data-testid={`recommendation-row-${rec.candidate.id}`}
                          style={{
                            borderBottom: "1px solid #e2e8f0",
                            backgroundColor: isSelected
                              ? "#f0f9ff"
                              : isAccepted
                              ? "#f8fafc"
                              : "#ffffff",
                            cursor: "pointer",
                            transition: "background-color 0.1s ease",
                          }}
                        >
                          {/* Accept Toggle (default off) */}
                          <td
                            style={{
                              padding: "10px 14px",
                              textAlign: "center",
                              verticalAlign: "middle",
                            }}
                          >
                            <label
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                cursor: "pointer",
                                position: "relative",
                              }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="checkbox"
                                checked={isAccepted}
                                onChange={() => handleToggle(rec.candidate.id)}
                                data-testid={`accept-toggle-${rec.candidate.id}`}
                                style={{
                                  width: "16px",
                                  height: "16px",
                                  accentColor: "#0284c7",
                                  cursor: "pointer",
                                }}
                              />
                            </label>
                          </td>

                          {/* Original POI Name */}
                          <td
                            style={{
                              padding: "10px 14px",
                              fontWeight: 500,
                              color: isAccepted ? "#64748b" : "#0f172a",
                              textDecoration: isAccepted ? "line-through" : "none",
                            }}
                          >
                            {rec.originalName}
                          </td>

                          {/* Recommended POI Name */}
                          <td style={{ padding: "10px 14px" }}>
                            <div
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                                fontWeight: 600,
                                color: isAccepted ? "#0369a1" : "#0284c7",
                              }}
                            >
                              <Sparkles size={12} color="#0284c7" />
                              {rec.recommendedName}
                            </div>
                          </td>

                          {/* Locality (Town / City) */}
                          <td style={{ padding: "10px 14px", color: "#334155" }}>
                            {rec.locality || <span style={{ color: "#94a3b8" }}>—</span>}
                          </td>

                          {/* Admin Level 2 (County / District) */}
                          <td style={{ padding: "10px 14px", color: "#334155" }}>
                            {rec.adminLevel2 || <span style={{ color: "#94a3b8" }}>—</span>}
                          </td>

                          {/* Admin Level 1 (State / Province / Region) */}
                          <td style={{ padding: "10px 14px", color: "#334155" }}>
                            {rec.adminLevel1 || <span style={{ color: "#94a3b8" }}>—</span>}
                          </td>

                          {/* Country */}
                          <td style={{ padding: "10px 14px", color: "#334155" }}>
                            {rec.country || <span style={{ color: "#94a3b8" }}>—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Right Column: Interactive Map Preview of Found Location */}
          <div
            style={{
              width: "420px",
              minWidth: "360px",
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#f8fafc",
              overflow: "hidden",
            }}
            data-testid="recommendations-map-column"
          >
            {/* Right Column Header */}
            <div
              style={{
                padding: "12px 16px",
                borderBottom: "1px solid #e2e8f0",
                backgroundColor: "#ffffff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "#1e293b",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}
              >
                <MapPin size={14} color="#0284c7" />
                Found Location Map Preview
              </div>
              {activeItem ? (
                <div style={{ marginTop: "6px" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a" }}>
                    {activeItem.recommendedName}
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#64748b",
                      marginTop: "2px",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <span>Original: {activeItem.originalName}</span>
                    <ArrowRight size={10} />
                    <span style={{ color: "#0284c7", fontWeight: 600 }}>Recommended</span>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                  Select a candidate to view on the map
                </div>
              )}
            </div>

            {/* Map Container */}
            <div
              style={{
                flex: 1,
                position: "relative",
                minHeight: "260px",
                backgroundColor: "#e2e8f0",
              }}
            >
              {activeItem && activeItem.latitude != null && activeItem.longitude != null ? (
                <WorkbenchMap
                  latitude={activeItem.latitude}
                  longitude={activeItem.longitude}
                  onChangeLocation={() => {}}
                />
              ) : (
                <div
                  style={{
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#64748b",
                    padding: "24px",
                    textAlign: "center",
                  }}
                >
                  <AlertCircle size={32} color="#94a3b8" style={{ marginBottom: "8px" }} />
                  <div style={{ fontSize: "13px", fontWeight: 600 }}>
                    No Coordinates Available
                  </div>
                  <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px" }}>
                    Coordinates could not be mapped for this item.
                  </div>
                </div>
              )}
            </div>

            {/* Location Metadata Summary Card */}
            {activeItem && (
              <div
                style={{
                  padding: "12px 16px",
                  borderTop: "1px solid #e2e8f0",
                  backgroundColor: "#ffffff",
                  fontSize: "11px",
                  color: "#334155",
                }}
              >
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <div>
                    <span style={{ color: "#64748b" }}>Coordinates: </span>
                    <strong>
                      {activeItem.latitude != null && activeItem.longitude != null
                        ? `${activeItem.latitude.toFixed(5)}, ${activeItem.longitude.toFixed(5)}`
                        : "—"}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b" }}>Country: </span>
                    <strong>{activeItem.country || "—"}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b" }}>Town / City: </span>
                    <strong>{activeItem.locality || "—"}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#64748b" }}>State / Prov: </span>
                    <strong>{activeItem.adminLevel1 || "—"}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer: Outside of the scrolled section */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 24px",
            borderTop: "1px solid #e2e8f0",
            backgroundColor: "#f8fafc",
            flexShrink: 0,
          }}
          data-testid="recommendations-footer"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{ fontSize: "13px", color: "#334155" }}>
              <strong>{acceptedCount}</strong> of <strong>{recommendations.length}</strong> changes
              will be applied
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              type="button"
              onClick={onClose}
              data-testid="cancel-recommendations-btn"
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                backgroundColor: "#ffffff",
                color: "#334155",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Keep Original Names
            </button>

            <button
              type="button"
              onClick={handleApplyChanges}
              disabled={isSubmitting || acceptedCount === 0}
              data-testid="accept-changes-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 18px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: acceptedCount > 0 ? "#0284c7" : "#94a3b8",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
                cursor: acceptedCount > 0 && !isSubmitting ? "pointer" : "not-allowed",
                boxShadow:
                  acceptedCount > 0 ? "0 1px 2px 0 rgba(0, 0, 0, 0.05)" : "none",
              }}
            >
              <CheckCircle2 size={16} />
              {isSubmitting ? "Applying..." : "Accept Changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

