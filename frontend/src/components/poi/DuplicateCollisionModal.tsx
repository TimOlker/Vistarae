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
 * Duplicate Collision Interception Modal (T-029).
 *
 * Implements REQ-SAVE-003:
 * When a saved POI draft matches an existing POI within 200m and similarity >= 0.60,
 * intercepts save and provides 3-way triage:
 * 1. "Create as New": proceeds with saving as an independent record
 * 2. "Merge": launches POIMergeModal with in-memory draft as source and existing POI as target
 * 3. "Cancel": aborts save and preserves draft in POI Editor
 */

import React from "react";
import {
  AlertTriangle,
  GitMerge,
  PlusCircle,
  X,
  MapPin,
  Star,
  FileText,
} from "lucide-react";

export interface DuplicateCollisionModalProps {
  isOpen: boolean;
  draftPoi: any;
  collisionCandidate: {
    poi_id: string;
    name: string;
    distance_meters: number;
    name_similarity: number;
    poi?: any;
  } | null;
  onSaveAsNew: () => void;
  onMerge: (sourceDraft: any, targetExisting: any) => void;
  onCancel: () => void;
}

export const DuplicateCollisionModal: React.FC<
  DuplicateCollisionModalProps
> = ({
  isOpen,
  draftPoi,
  collisionCandidate,
  onSaveAsNew,
  onMerge,
  onCancel,
}) => {
  if (!isOpen || !collisionCandidate) return null;

  const existing = collisionCandidate.poi || {};
  const similarityPct = Math.round(
    (collisionCandidate.name_similarity || 0) * 100,
  );
  const distanceMeters = Math.round(collisionCandidate.distance_meters || 0);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 2300,
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
          maxWidth: "680px",
          borderRadius: "var(--radius-lg, 12px)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          overflow: "hidden",
          border: "1px solid var(--border-color, #e2e8f0)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Warning Header */}
        <div
          style={{
            padding: "16px 20px",
            background: "#fffbeb",
            borderBottom: "1px solid #fef3c7",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "50%",
                background: "#fef3c7",
                color: "#d97706",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <AlertTriangle size={20} />
            </div>
            <div>
              <h3
                style={{
                  margin: 0,
                  fontSize: "16px",
                  fontWeight: 800,
                  color: "#92400e",
                }}
              >
                Potential Duplicate Detected
              </h3>
              <span style={{ fontSize: "12px", color: "#b45309" }}>
                A similar point of interest already exists in your library
                nearby.
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close duplicate prompt"
            style={{
              background: "transparent",
              border: "none",
              color: "#92400e",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Proximity & Similarity Badges */}
        <div
          style={{
            padding: "12px 20px",
            background: "#f8fafc",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          <span
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              background: "#eff6ff",
              color: "#2563eb",
              border: "1px solid #bfdbfe",
            }}
          >
            📍 {distanceMeters} meters away
          </span>
          <span
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              background: "#ecfdf5",
              color: "#059669",
              border: "1px solid #a7f3d0",
            }}
          >
            🔤 {similarityPct}% name match
          </span>
        </div>

        {/* Comparison Cards: Draft vs Existing */}
        <div
          style={{
            padding: "20px",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "16px",
          }}
        >
          {/* Left: Your Draft */}
          <div
            style={{
              padding: "14px",
              borderRadius: "8px",
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontSize: "12px",
            }}
          >
            <div
              style={{
                fontSize: "10px",
                fontWeight: 800,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              Your Active Draft
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a" }}
            >
              {draftPoi?.name || "Untitled POI"}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                color: "#64748b",
              }}
            >
              <MapPin size={12} />
              <span>
                {draftPoi?.lat != null ? Number(draftPoi.lat).toFixed(4) : "—"},{" "}
                {draftPoi?.lon != null ? Number(draftPoi.lon).toFixed(4) : "—"}
              </span>
            </div>
            {draftPoi?.description && (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "6px",
                  color: "#475569",
                  fontSize: "11px",
                  maxHeight: "44px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                <FileText
                  size={12}
                  style={{ flexShrink: 0, marginTop: "2px" }}
                />
                <span>{draftPoi.description}</span>
              </div>
            )}
            {draftPoi?.addresses && draftPoi.addresses.length > 0 && (
              <div style={{ fontSize: "11px", color: "#64748b" }}>
                {draftPoi.addresses[0].city
                  ? `${draftPoi.addresses[0].city}, `
                  : ""}
                {draftPoi.addresses[0].country}
              </div>
            )}
          </div>

          {/* Right: Existing POI */}
          <div
            style={{
              padding: "14px",
              borderRadius: "8px",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontSize: "12px",
            }}
          >
            <div
              style={{
                fontSize: "10px",
                fontWeight: 800,
                color: "#2563eb",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              Existing Saved POI
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, color: "#1e3a8a" }}
            >
              {collisionCandidate.name}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                color: "#3b82f6",
              }}
            >
              <MapPin size={12} />
              <span>
                {existing.lat != null ? Number(existing.lat).toFixed(4) : "—"},{" "}
                {existing.lon != null ? Number(existing.lon).toFixed(4) : "—"}
              </span>
            </div>
            {existing.description && (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "6px",
                  color: "#1e40af",
                  fontSize: "11px",
                  maxHeight: "44px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                <FileText
                  size={12}
                  style={{ flexShrink: 0, marginTop: "2px" }}
                />
                <span>{existing.description}</span>
              </div>
            )}
            {existing.rating ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  color: "#d97706",
                }}
              >
                <Star size={12} fill="#d97706" />
                <span>{existing.rating} Stars</span>
              </div>
            ) : null}
          </div>
        </div>

        {/* Action Prompt Description */}
        <div
          style={{
            padding: "0 20px 16px 20px",
            fontSize: "12px",
            color: "#64748b",
            lineHeight: 1.5,
          }}
        >
          Would you like to merge your draft edits directly into the existing
          POI, create a separate POI anyway, or cancel to review your changes?
        </div>

        {/* 3-Way Triage Footer Buttons */}
        <div
          style={{
            padding: "16px 20px",
            borderTop: "1px solid #e2e8f0",
            background: "#f8fafc",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "10px",
          }}
        >
          {/* Option C: Cancel */}
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: "8px 14px",
              borderRadius: "6px",
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              color: "#475569",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>

          <div style={{ display: "flex", gap: "8px" }}>
            {/* Option A: Create as New */}
            <button
              type="button"
              onClick={onSaveAsNew}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 14px",
                borderRadius: "6px",
                background: "#f1f5f9",
                border: "1px solid #cbd5e1",
                color: "#1e293b",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <PlusCircle size={15} />
              Save as New
            </button>

            {/* Option B: Merge Draft */}
            <button
              type="button"
              onClick={() => onMerge(draftPoi, existing)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 18px",
                borderRadius: "6px",
                background: "var(--accent, #2563eb)",
                border: "none",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(37, 99, 235, 0.2)",
              }}
            >
              <GitMerge size={15} />
              Merge Draft into Existing
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
