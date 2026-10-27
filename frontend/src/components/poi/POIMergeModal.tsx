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

/**
 * Selective Field-by-Field POI Comparison & Atomic Merge Modal (T-025).
 *
 * Implements REQ-MERGE-001 through REQ-MERGE-005:
 * - Dual-column layout comparing Source POI vs Target POI
 * - "Show all fields" toggle (defaulting to diff-only view)
 * - Radio button selection for scalar values
 * - Checkbox selection for multi-value set attributes with deduplication
 * - Confirmation alert and atomic re-parenting execution via POST /api/pois/merge
 */

import React, { useState, useEffect, useMemo } from "react";
import {
  X,
  GitMerge,
  CheckCircle2,
  AlertTriangle,
  Calendar,
  Folder,
  Tag,
  Loader2,
  Eye,
  EyeOff,
} from "lucide-react";
import { apiFetch, ApiError } from "../../services/api";
import type { AddressRecord } from "./MultiAddressEditor";

export interface POIMergeModalProps {
  isOpen: boolean;
  sourcePoi: any | null;
  targetPoi: any | null;
  isDraftSource?: boolean;
  onClose: () => void;
  onSuccess: (updatedTarget: any) => void;
}

function addressKey(addr: AddressRecord): string {
  return [
    addr.street || "",
    addr.city || "",
    addr.state_province || "",
    addr.country || "",
    addr.postal_code || "",
  ]
    .map((s) => s.trim().toLowerCase())
    .join("|");
}

export const POIMergeModal: React.FC<POIMergeModalProps> = ({
  isOpen,
  sourcePoi,
  targetPoi,
  isDraftSource = false,
  onClose,
  onSuccess,
}) => {
  // Toggle for diff-only vs all fields (default false = diff-only)
  const [showAllFields, setShowAllFields] = useState<boolean>(false);

  // Scalar resolutions: 'source' | 'target'
  const [selectedScalars, setSelectedScalars] = useState<
    Record<string, "source" | "target">
  >({});

  // Set selections: sets of selected item identifiers
  const [selectedAddresses, setSelectedAddresses] = useState<
    Record<string, AddressRecord>
  >({});
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
  const [selectedDirectories, setSelectedDirectories] = useState<Set<string>>(
    new Set(),
  );
  const [selectedImageUrls, setSelectedImageUrls] = useState<Set<string>>(
    new Set(),
  );
  const [selectedVisitedDates, setSelectedVisitedDates] = useState<Set<string>>(
    new Set(),
  );

  // Merge submission state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [showConfirmPrompt, setShowConfirmPrompt] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize selections when modal opens or POIs change
  useEffect(() => {
    if (!isOpen || !sourcePoi || !targetPoi) return;

    // By default, prefer target values for scalars
    setSelectedScalars({
      name: "target",
      description: targetPoi.description ? "target" : "source",
      rating: targetPoi.rating ? "target" : "source",
      parent_poi: targetPoi.parent_poi_id ? "target" : "source",
      duration: targetPoi.recommended_duration_hours ? "target" : "source",
      provenance: targetPoi.source_type ? "target" : "source",
      official_url: targetPoi.official_url ? "target" : "source",
      wiki_url: targetPoi.wiki_url ? "target" : "source",
      coordinates: "target",
      want_to_visit_again: targetPoi.want_to_visit_again ? "target" : "source",
    });

    // Multi-value sets: select union by default
    const addrMap: Record<string, AddressRecord> = {};
    const srcAddrs: AddressRecord[] = sourcePoi.addresses || [];
    const tgtAddrs: AddressRecord[] = targetPoi.addresses || [];
    [...tgtAddrs, ...srcAddrs].forEach((a) => {
      if (a && a.country) {
        addrMap[addressKey(a)] = a;
      }
    });
    setSelectedAddresses(addrMap);

    // Tags
    const parseTags = (p: any): string[] => {
      if (!p || !p.tags) return [];
      return p.tags.map((t: any) => (typeof t === "string" ? t : t.name));
    };
    setSelectedTags(
      new Set([...parseTags(targetPoi), ...parseTags(sourcePoi)]),
    );

    // Directories
    setSelectedDirectories(
      new Set([
        ...(targetPoi.directory_paths || []),
        ...(sourcePoi.directory_paths || []),
      ]),
    );

    // Image URLs
    setSelectedImageUrls(
      new Set([
        ...(targetPoi.image_urls || []),
        ...(sourcePoi.image_urls || []),
      ]),
    );

    // Visited Dates
    setSelectedVisitedDates(
      new Set([
        ...(targetPoi.visited_dates || []),
        ...(sourcePoi.visited_dates || []),
      ]),
    );

    setShowConfirmPrompt(false);
    setErrorMessage(null);
  }, [isOpen, sourcePoi, targetPoi]);

  // Diff detection helper
  const diffs = useMemo(() => {
    if (!sourcePoi || !targetPoi) return {};

    const srcLat = sourcePoi.canonical_lat ?? sourcePoi.lat ?? 0;
    const srcLng = sourcePoi.canonical_lng ?? sourcePoi.lon ?? 0;
    const tgtLat = targetPoi.canonical_lat ?? targetPoi.lat ?? 0;
    const tgtLng = targetPoi.canonical_lng ?? targetPoi.lon ?? 0;

    const parseTags = (p: any) =>
      (p?.tags || [])
        .map((t: any) => (typeof t === "string" ? t : t.name).toLowerCase())
        .sort();

    return {
      name: (sourcePoi.name || "").trim() !== (targetPoi.name || "").trim(),
      description:
        (sourcePoi.description || "").trim() !==
        (targetPoi.description || "").trim(),
      rating: sourcePoi.rating !== targetPoi.rating,
      parent_poi: sourcePoi.parent_poi_id !== targetPoi.parent_poi_id,
      duration:
        sourcePoi.recommended_duration_hours !==
          targetPoi.recommended_duration_hours ||
        sourcePoi.recommended_visit_days !== targetPoi.recommended_visit_days,
      provenance:
        sourcePoi.source_type !== targetPoi.source_type ||
        sourcePoi.source_value !== targetPoi.source_value,
      official_url:
        (sourcePoi.official_url || "").trim() !==
        (targetPoi.official_url || "").trim(),
      wiki_url:
        (sourcePoi.wiki_url || "").trim() !== (targetPoi.wiki_url || "").trim(),
      coordinates:
        Math.abs(srcLat - tgtLat) > 0.00001 ||
        Math.abs(srcLng - tgtLng) > 0.00001,
      want_to_visit_again:
        sourcePoi.want_to_visit_again !== targetPoi.want_to_visit_again,
      addresses:
        JSON.stringify((sourcePoi.addresses || []).map(addressKey).sort()) !==
        JSON.stringify((targetPoi.addresses || []).map(addressKey).sort()),
      tags:
        JSON.stringify(parseTags(sourcePoi)) !==
        JSON.stringify(parseTags(targetPoi)),
      directories:
        JSON.stringify((sourcePoi.directory_paths || []).sort()) !==
        JSON.stringify((targetPoi.directory_paths || []).sort()),
      image_urls:
        JSON.stringify((sourcePoi.image_urls || []).sort()) !==
        JSON.stringify((targetPoi.image_urls || []).sort()),
      visited_dates:
        JSON.stringify((sourcePoi.visited_dates || []).sort()) !==
        JSON.stringify((targetPoi.visited_dates || []).sort()),
    };
  }, [sourcePoi, targetPoi]);

  if (!isOpen || !sourcePoi || !targetPoi) return null;

  const handleScalarSelect = (field: string, origin: "source" | "target") => {
    setSelectedScalars((prev) => ({ ...prev, [field]: origin }));
  };

  const handleToggleSetItem = (
    item: string,
    set: Set<string>,
    setter: React.Dispatch<React.SetStateAction<Set<string>>>,
  ) => {
    const next = new Set(set);
    if (next.has(item)) {
      next.delete(item);
    } else {
      next.add(item);
    }
    setter(next);
  };

  const handleToggleAddress = (addr: AddressRecord) => {
    const k = addressKey(addr);
    setSelectedAddresses((prev) => {
      const next = { ...prev };
      if (next[k]) {
        delete next[k];
      } else {
        next[k] = addr;
      }
      return next;
    });
  };

  const executeMerge = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      // Assemble scalars based on choices
      const pick = (field: string) =>
        selectedScalars[field] === "source" ? sourcePoi : targetPoi;

      const srcLat = sourcePoi.canonical_lat ?? sourcePoi.lat;
      const srcLng = sourcePoi.canonical_lng ?? sourcePoi.lon;
      const tgtLat = targetPoi.canonical_lat ?? targetPoi.lat;
      const tgtLng = targetPoi.canonical_lng ?? targetPoi.lon;
      const coordsPoi =
        selectedScalars["coordinates"] === "source" ? sourcePoi : targetPoi;
      const finalLat = coordsPoi === sourcePoi ? srcLat : tgtLat;
      const finalLng = coordsPoi === sourcePoi ? srcLng : tgtLng;

      const synthesizedScalars: Record<string, any> = {
        name: pick("name").name,
        description: pick("description").description || null,
        rating: pick("rating").rating ?? null,
        parent_poi_id: pick("parent_poi").parent_poi_id || null,
        recommended_duration_hours:
          pick("duration").recommended_duration_hours ?? null,
        recommended_visit_days: pick("duration").recommended_visit_days ?? 1,
        estimated_visit_time_notes: pick("duration").estimated_visit_time_notes ?? null,
        source_type: pick("provenance").source_type || null,
        source_value: pick("provenance").source_value || null,
        official_url: pick("official_url").official_url || null,
        wiki_url: pick("wiki_url").wiki_url || null,
        want_to_visit_again: Boolean(
          pick("want_to_visit_again").want_to_visit_again,
        ),
        latitude: finalLat,
        longitude: finalLng,
      };

      const synthesizedSets: Record<string, any> = {
        addresses: Object.values(selectedAddresses),
        tags: Array.from(selectedTags),
        directory_paths: Array.from(selectedDirectories),
        image_urls: Array.from(selectedImageUrls),
        visited_dates: Array.from(selectedVisitedDates).sort(),
      };

      const payload = {
        source_poi_id: isDraftSource ? null : sourcePoi.id,
        target_poi_id: targetPoi.id,
        selected_scalars: synthesizedScalars,
        selected_sets: synthesizedSets,
      };

      const response = await apiFetch<any>("/api/pois/merge", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      onSuccess(response.target_poi);
      onClose();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(
          (err as any).detail || err.message || "Failed to merge POIs.",
        );
      } else {
        setErrorMessage(
          err.message || "An unexpected error occurred during merge.",
        );
      }
      setShowConfirmPrompt(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 2200,
        background: "rgba(15, 23, 42, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
    >
      <div
        style={{
          background: "var(--bg-primary, #ffffff)",
          color: "var(--text-primary, #0f172a)",
          width: "100%",
          maxWidth: "1040px",
          maxHeight: "92vh",
          borderRadius: "var(--radius-lg, 12px)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          border: "1px solid var(--border-color, #e2e8f0)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--bg-secondary, #f8fafc)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                background: "var(--accent-light, #eff6ff)",
                color: "var(--accent, #2563eb)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <GitMerge size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: "17px", fontWeight: 800 }}>
                Merge Points of Interest
              </h3>
              <span
                style={{
                  fontSize: "12px",
                  color: "var(--text-muted, #64748b)",
                }}
              >
                Select fields to synthesize into the canonical target POI.
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {/* Show all fields toggle */}
            <button
              type="button"
              onClick={() => setShowAllFields(!showAllFields)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "var(--radius-md, 6px)",
                background: showAllFields
                  ? "var(--accent-light, #eff6ff)"
                  : "transparent",
                color: showAllFields
                  ? "var(--accent, #2563eb)"
                  : "var(--text-secondary, #475569)",
                border: "1px solid var(--border-color, #cbd5e1)",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {showAllFields ? <Eye size={14} /> : <EyeOff size={14} />}
              {showAllFields ? "Showing All Fields" : "Diff-Only View"}
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close merge dialog"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted, #64748b)",
                cursor: "pointer",
                padding: "4px",
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Error message banner */}
        {errorMessage && (
          <div
            style={{
              padding: "10px 24px",
              background: "#fef2f2",
              borderBottom: "1px solid #fecaca",
              color: "#b91c1c",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <AlertTriangle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Dual Column Headers */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "180px 1fr 1fr",
            padding: "12px 24px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
            background: "var(--bg-primary, #ffffff)",
            fontWeight: 700,
            fontSize: "13px",
          }}
        >
          <div style={{ color: "var(--text-muted, #64748b)" }}>Attribute</div>
          <div
            style={{
              color: "#d97706",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                display: "inline-block",
                padding: "2px 6px",
                borderRadius: "4px",
                background: "#fef3c7",
                fontSize: "10px",
                fontWeight: 800,
              }}
            >
              SOURCE {isDraftSource ? "(DRAFT)" : "(WILL DELETE)"}
            </span>
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {sourcePoi.name || "Untitled POI"}
            </span>
          </div>
          <div
            style={{
              color: "var(--accent, #2563eb)",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                display: "inline-block",
                padding: "2px 6px",
                borderRadius: "4px",
                background: "var(--accent-light, #eff6ff)",
                fontSize: "10px",
                fontWeight: 800,
              }}
            >
              TARGET (CANONICAL)
            </span>
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {targetPoi.name}
            </span>
          </div>
        </div>

        {/* Comparison Body */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 24px",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
          }}
        >
          {/* Row: POI Name */}
          {(showAllFields || diffs.name) && (
            <div className="merge-row" style={rowStyle(diffs.name)}>
              <div style={labelStyle}>POI Name</div>
              <div>
                <label
                  style={radioOptionStyle(selectedScalars.name === "source")}
                >
                  <input
                    type="radio"
                    name="scalar_name"
                    checked={selectedScalars.name === "source"}
                    onChange={() => handleScalarSelect("name", "source")}
                  />
                  <span>{sourcePoi.name}</span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(selectedScalars.name === "target")}
                >
                  <input
                    type="radio"
                    name="scalar_name"
                    checked={selectedScalars.name === "target"}
                    onChange={() => handleScalarSelect("name", "target")}
                  />
                  <span>{targetPoi.name}</span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Description */}
          {(showAllFields || diffs.description) && (
            <div className="merge-row" style={rowStyle(diffs.description)}>
              <div style={labelStyle}>Description</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.description === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_description"
                    checked={selectedScalars.description === "source"}
                    onChange={() => handleScalarSelect("description", "source")}
                  />
                  <span style={{ fontSize: "12px", whiteSpace: "pre-wrap" }}>
                    {sourcePoi.description || (
                      <em style={{ color: "#94a3b8" }}>Empty</em>
                    )}
                  </span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.description === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_description"
                    checked={selectedScalars.description === "target"}
                    onChange={() => handleScalarSelect("description", "target")}
                  />
                  <span style={{ fontSize: "12px", whiteSpace: "pre-wrap" }}>
                    {targetPoi.description || (
                      <em style={{ color: "#94a3b8" }}>Empty</em>
                    )}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Star Rating */}
          {(showAllFields || diffs.rating) && (
            <div className="merge-row" style={rowStyle(diffs.rating)}>
              <div style={labelStyle}>Star Rating</div>
              <div>
                <label
                  style={radioOptionStyle(selectedScalars.rating === "source")}
                >
                  <input
                    type="radio"
                    name="scalar_rating"
                    checked={selectedScalars.rating === "source"}
                    onChange={() => handleScalarSelect("rating", "source")}
                  />
                  <span>
                    {sourcePoi.rating
                      ? `⭐ ${sourcePoi.rating} Stars`
                      : "Unrated"}
                  </span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(selectedScalars.rating === "target")}
                >
                  <input
                    type="radio"
                    name="scalar_rating"
                    checked={selectedScalars.rating === "target"}
                    onChange={() => handleScalarSelect("rating", "target")}
                  />
                  <span>
                    {targetPoi.rating
                      ? `⭐ ${targetPoi.rating} Stars`
                      : "Unrated"}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Coordinates */}
          {(showAllFields || diffs.coordinates) && (
            <div className="merge-row" style={rowStyle(diffs.coordinates)}>
              <div style={labelStyle}>Coordinates</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.coordinates === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_coordinates"
                    checked={selectedScalars.coordinates === "source"}
                    onChange={() => handleScalarSelect("coordinates", "source")}
                  />
                  <span style={{ fontSize: "12px" }}>
                    {sourcePoi.canonical_lat ?? sourcePoi.lat},{" "}
                    {sourcePoi.canonical_lng ?? sourcePoi.lon}
                  </span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.coordinates === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_coordinates"
                    checked={selectedScalars.coordinates === "target"}
                    onChange={() => handleScalarSelect("coordinates", "target")}
                  />
                  <span style={{ fontSize: "12px" }}>
                    {targetPoi.canonical_lat ?? targetPoi.lat},{" "}
                    {targetPoi.canonical_lng ?? targetPoi.lon}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Parent POI */}
          {(showAllFields || diffs.parent_poi) && (
            <div className="merge-row" style={rowStyle(diffs.parent_poi)}>
              <div style={labelStyle}>Parent POI</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.parent_poi === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_parent"
                    checked={selectedScalars.parent_poi === "source"}
                    onChange={() => handleScalarSelect("parent_poi", "source")}
                  />
                  <span>{sourcePoi.parent_poi_name || "None"}</span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.parent_poi === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_parent"
                    checked={selectedScalars.parent_poi === "target"}
                    onChange={() => handleScalarSelect("parent_poi", "target")}
                  />
                  <span>{targetPoi.parent_poi_name || "None"}</span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Recommended Duration */}
          {(showAllFields || diffs.duration) && (
            <div className="merge-row" style={rowStyle(diffs.duration)}>
              <div style={labelStyle}>Estimated Duration</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.duration === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_duration"
                    checked={selectedScalars.duration === "source"}
                    onChange={() => handleScalarSelect("duration", "source")}
                  />
                  <span>
                    {sourcePoi.recommended_duration_hours ?? "—"} hrs per visit ({sourcePoi.recommended_visit_days ?? 1} itinerary day{(sourcePoi.recommended_visit_days ?? 1) === 1 ? "" : "s"})
                    {sourcePoi.estimated_visit_time_notes && <em style={{ display: "block", fontSize: "11px", color: "var(--text-muted)" }}>{sourcePoi.estimated_visit_time_notes}</em>}
                  </span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.duration === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_duration"
                    checked={selectedScalars.duration === "target"}
                    onChange={() => handleScalarSelect("duration", "target")}
                  />
                  <span>
                    {targetPoi.recommended_duration_hours ?? "—"} hrs per visit ({targetPoi.recommended_visit_days ?? 1} itinerary day{(targetPoi.recommended_visit_days ?? 1) === 1 ? "" : "s"})
                    {targetPoi.estimated_visit_time_notes && <em style={{ display: "block", fontSize: "11px", color: "var(--text-muted)" }}>{targetPoi.estimated_visit_time_notes}</em>}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Provenance */}
          {(showAllFields || diffs.provenance) && (
            <div className="merge-row" style={rowStyle(diffs.provenance)}>
              <div style={labelStyle}>Source Provenance</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.provenance === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_provenance"
                    checked={selectedScalars.provenance === "source"}
                    onChange={() => handleScalarSelect("provenance", "source")}
                  />
                  <span>
                    {sourcePoi.source_type || "Manual"}{" "}
                    {sourcePoi.source_value
                      ? `(${sourcePoi.source_value})`
                      : ""}
                  </span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.provenance === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_provenance"
                    checked={selectedScalars.provenance === "target"}
                    onChange={() => handleScalarSelect("provenance", "target")}
                  />
                  <span>
                    {targetPoi.source_type || "Manual"}{" "}
                    {targetPoi.source_value
                      ? `(${targetPoi.source_value})`
                      : ""}
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Row: Official & Wikipedia URLs */}
          {(showAllFields || diffs.official_url || diffs.wiki_url) && (
            <div
              className="merge-row"
              style={rowStyle(diffs.official_url || diffs.wiki_url)}
            >
              <div style={labelStyle}>Official & Wiki Links</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.official_url === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_urls"
                    checked={selectedScalars.official_url === "source"}
                    onChange={() => {
                      handleScalarSelect("official_url", "source");
                      handleScalarSelect("wiki_url", "source");
                    }}
                  />
                  <div style={{ fontSize: "11px", wordBreak: "break-all" }}>
                    <div>Off: {sourcePoi.official_url || "—"}</div>
                    <div>Wiki: {sourcePoi.wiki_url || "—"}</div>
                  </div>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.official_url === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_urls"
                    checked={selectedScalars.official_url === "target"}
                    onChange={() => {
                      handleScalarSelect("official_url", "target");
                      handleScalarSelect("wiki_url", "target");
                    }}
                  />
                  <div style={{ fontSize: "11px", wordBreak: "break-all" }}>
                    <div>Off: {targetPoi.official_url || "—"}</div>
                    <div>Wiki: {targetPoi.wiki_url || "—"}</div>
                  </div>
                </label>
              </div>
            </div>
          )}

          {/* Row: Want to visit again */}
          {(showAllFields || diffs.want_to_visit_again) && (
            <div
              className="merge-row"
              style={rowStyle(diffs.want_to_visit_again)}
            >
              <div style={labelStyle}>Want to Visit Again</div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.want_to_visit_again === "source",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_want_again"
                    checked={selectedScalars.want_to_visit_again === "source"}
                    onChange={() =>
                      handleScalarSelect("want_to_visit_again", "source")
                    }
                  />
                  <span>{sourcePoi.want_to_visit_again ? "Yes" : "No"}</span>
                </label>
              </div>
              <div>
                <label
                  style={radioOptionStyle(
                    selectedScalars.want_to_visit_again === "target",
                  )}
                >
                  <input
                    type="radio"
                    name="scalar_want_again"
                    checked={selectedScalars.want_to_visit_again === "target"}
                    onChange={() =>
                      handleScalarSelect("want_to_visit_again", "target")
                    }
                  />
                  <span>{targetPoi.want_to_visit_again ? "Yes" : "No"}</span>
                </label>
              </div>
            </div>
          )}

          {/* Section: Set Multi-value attributes */}
          <div
            style={{
              paddingTop: "12px",
              borderTop: "1px solid var(--border-color, #e2e8f0)",
              fontWeight: 700,
              fontSize: "14px",
              color: "var(--accent, #2563eb)",
            }}
          >
            Multi-Value Set Attributes (Union & Checkbox Resolution)
          </div>

          {/* Multi-value: Addresses */}
          {(showAllFields || diffs.addresses) && (
            <div className="merge-row" style={rowStyle(diffs.addresses)}>
              <div style={labelStyle}>
                <div>Addresses</div>
                <span style={{ fontSize: "10px", color: "#64748b" }}>
                  Checked items will be retained
                </span>
              </div>
              <div
                style={{
                  gridColumn: "span 2",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                {Array.from(
                  new Map(
                    [
                      ...(targetPoi.addresses || []),
                      ...(sourcePoi.addresses || []),
                    ].map((a) => [addressKey(a), a]),
                  ).values(),
                ).map((addr) => {
                  const k = addressKey(addr);
                  const isChecked = Boolean(selectedAddresses[k]);
                  return (
                    <label
                      key={k}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        padding: "6px 10px",
                        borderRadius: "6px",
                        background: isChecked
                          ? "var(--accent-light, #eff6ff)"
                          : "#f8fafc",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        fontSize: "12px",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleAddress(addr)}
                      />
                      <span>
                        {addr.street ? `${addr.street}, ` : ""}
                        {addr.city ? `${addr.city}, ` : ""}
                        {addr.state_province ? `${addr.state_province}, ` : ""}
                        <strong>{addr.country}</strong>
                        {addr.postal_code ? ` (${addr.postal_code})` : ""}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Multi-value: Tags */}
          {(showAllFields || diffs.tags) && (
            <div className="merge-row" style={rowStyle(diffs.tags)}>
              <div style={labelStyle}>Tags</div>
              <div
                style={{
                  gridColumn: "span 2",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                }}
              >
                {Array.from(
                  new Set([
                    ...(targetPoi.tags || []).map((t: any) =>
                      typeof t === "string" ? t : t.name,
                    ),
                    ...(sourcePoi.tags || []).map((t: any) =>
                      typeof t === "string" ? t : t.name,
                    ),
                  ]),
                ).map((tag) => {
                  const isChecked = selectedTags.has(tag);
                  return (
                    <label
                      key={tag}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "4px 10px",
                        borderRadius: "16px",
                        background: isChecked
                          ? "var(--accent, #2563eb)"
                          : "#f1f5f9",
                        color: isChecked ? "#ffffff" : "#475569",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() =>
                          handleToggleSetItem(
                            tag,
                            selectedTags,
                            setSelectedTags,
                          )
                        }
                        style={{ display: "none" }}
                      />
                      <Tag size={12} />
                      {tag}
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Multi-value: Visited Dates */}
          {(showAllFields || diffs.visited_dates) && (
            <div className="merge-row" style={rowStyle(diffs.visited_dates)}>
              <div style={labelStyle}>Visited Dates</div>
              <div
                style={{
                  gridColumn: "span 2",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                }}
              >
                {Array.from(
                  new Set([
                    ...(targetPoi.visited_dates || []),
                    ...(sourcePoi.visited_dates || []),
                  ]),
                )
                  .sort()
                  .map((date) => {
                    const isChecked = selectedVisitedDates.has(date);
                    return (
                      <label
                        key={date}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "4px 10px",
                          borderRadius: "6px",
                          background: isChecked ? "#ecfdf5" : "#f8fafc",
                          color: isChecked ? "#065f46" : "#475569",
                          border: `1px solid ${
                            isChecked ? "#a7f3d0" : "#e2e8f0"
                          }`,
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() =>
                            handleToggleSetItem(
                              date,
                              selectedVisitedDates,
                              setSelectedVisitedDates,
                            )
                          }
                        />
                        <Calendar size={12} />
                        {date}
                      </label>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Multi-value: Photo Directories */}
          {(showAllFields || diffs.directories) && (
            <div className="merge-row" style={rowStyle(diffs.directories)}>
              <div style={labelStyle}>Photo Folders</div>
              <div
                style={{
                  gridColumn: "span 2",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                {Array.from(
                  new Set([
                    ...(targetPoi.directory_paths || []),
                    ...(sourcePoi.directory_paths || []),
                  ]),
                ).map((path) => {
                  const isChecked = selectedDirectories.has(path);
                  return (
                    <label
                      key={path}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        padding: "6px 10px",
                        borderRadius: "6px",
                        background: isChecked
                          ? "var(--accent-light, #eff6ff)"
                          : "#f8fafc",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        fontSize: "12px",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() =>
                          handleToggleSetItem(
                            path,
                            selectedDirectories,
                            setSelectedDirectories,
                          )
                        }
                      />
                      <Folder
                        size={13}
                        style={{ color: "var(--accent, #2563eb)" }}
                      />
                      <span style={{ fontFamily: "monospace" }}>{path}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Confirmation Alert Prompt */}
        {showConfirmPrompt && (
          <div
            style={{
              padding: "12px 24px",
              background: "#fffbeb",
              borderTop: "1px solid #fef3c7",
              color: "#92400e",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <AlertTriangle
                size={18}
                style={{ color: "#d97706", flexShrink: 0 }}
              />
              <span>
                <strong>Warning:</strong> Merging will permanently update{" "}
                <strong>{targetPoi.name}</strong>{" "}
                {isDraftSource
                  ? "with draft values."
                  : `and delete ${sourcePoi.name}. Dependent itinerary items and child POIs will be re-parented.`}{" "}
                This action cannot be undone.
              </span>
            </div>
            <div style={{ display: "flex", gap: "8px", flexShrink: 0 }}>
              <button
                type="button"
                onClick={() => setShowConfirmPrompt(false)}
                style={{
                  padding: "5px 12px",
                  borderRadius: "6px",
                  background: "#ffffff",
                  border: "1px solid #d1d5db",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Back
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={executeMerge}
                style={{
                  padding: "5px 14px",
                  borderRadius: "6px",
                  background: "#b45309",
                  border: "none",
                  color: "#ffffff",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                {isSubmitting ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <CheckCircle2 size={13} />
                )}
                Yes, Execute Merge
              </button>
            </div>
          </div>
        )}

        {/* Footer Actions */}
        {!showConfirmPrompt && (
          <div
            style={{
              padding: "16px 24px",
              borderTop: "1px solid var(--border-color, #e2e8f0)",
              background: "var(--bg-secondary, #f8fafc)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "#ffffff",
                border: "1px solid var(--border-color, #cbd5e1)",
                color: "var(--text-secondary, #475569)",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => setShowConfirmPrompt(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 20px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                border: "none",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(37, 99, 235, 0.2)",
              }}
            >
              <GitMerge size={16} />
              Review & Merge POIs
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const labelStyle: React.CSSProperties = {
  fontWeight: 700,
  fontSize: "12px",
  color: "var(--text-secondary, #475569)",
  display: "flex",
  flexDirection: "column",
  gap: "2px",
};

function rowStyle(isDiff: boolean = false): React.CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: "180px 1fr 1fr",
    gap: "16px",
    padding: "10px 14px",
    borderRadius: "8px",
    background: isDiff ? "rgba(245, 158, 11, 0.04)" : "transparent",
    border: isDiff
      ? "1px dashed rgba(245, 158, 11, 0.3)"
      : "1px solid transparent",
  };
}

function radioOptionStyle(isSelected: boolean): React.CSSProperties {
  return {
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    padding: "8px 12px",
    borderRadius: "6px",
    background: isSelected
      ? "var(--accent-light, #eff6ff)"
      : "var(--bg-secondary, #f8fafc)",
    border: `1px solid ${
      isSelected ? "var(--accent, #2563eb)" : "var(--border-color, #e2e8f0)"
    }`,
    fontSize: "13px",
    fontWeight: isSelected ? 600 : 400,
    cursor: "pointer",
    transition: "all 0.15s ease",
  };
}
