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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from "react";
import type { POIMapFeature, VisitState } from "../../types/map";
import { X, Star, Save, Trash2 } from "lucide-react";
import { TagSelector } from "../tags/TagSelector";

interface POIDetailDrawerProps {
  poi: POIMapFeature | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updated: POIMapFeature) => void;
  onDelete?: (id: string) => void;
}

export const POIDetailDrawer: React.FC<POIDetailDrawerProps> = ({
  poi,
  isOpen,
  onClose,
  onSave,
  onDelete,
}) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [reasonToVisit, setReasonToVisit] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [visitState, setVisitState] = useState<VisitState>("not_visited");
  const [rating, setRating] = useState<number>(0);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  useEffect(() => {
    if (poi) {
      setName(poi.name);
      setDescription(poi.description || "");
      setReasonToVisit(poi.reason_to_visit || "");
      setCity(poi.city || "");
      setAddress(poi.address || "");
      setVisitState(poi.visit_state);
      setRating(poi.rating || 0);
      setSelectedTags(
        Array.isArray(poi.tags)
          ? poi.tags
              .map((t: any) => (typeof t === "string" ? t : t.slug || t.name))
              .filter(Boolean)
          : [],
      );
    }
  }, [poi]);

  if (!isOpen || !poi) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const updated: POIMapFeature = {
      ...poi,
      name,
      description: description.trim() || undefined,
      reason_to_visit: reasonToVisit.trim() || undefined,
      city,
      address,
      visit_state: visitState,
      rating: rating > 0 ? rating : null,
      tags: selectedTags,
    };
    onSave(updated);
    onClose();
  };

  return (
    <div
      className="poi-drawer-overlay fade-in"
      onClick={onClose}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(2px)",
        zIndex: 5000,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        className="poi-drawer-content slide-up"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "420px",
          maxWidth: "100%",
          height: "100%",
          background: "var(--bg-surface, #ffffff)",
          color: "var(--text-primary, #0f172a)",
          boxShadow: "var(--shadow-lg)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          padding: "24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "20px",
          }}
        >
          <h3 style={{ fontSize: "18px", fontWeight: 800 }}>
            Edit Point of Interest
          </h3>
          <button
            type="button"
            onClick={onClose}
            style={{ padding: "4px", color: "var(--text-muted)" }}
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            flex: 1,
          }}
        >
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>

          {/* Description Block */}
          <div>
            <label
              htmlFor="detail-poi-description"
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Description
            </label>
            <textarea
              id="detail-poi-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this location is..."
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
                resize: "vertical",
                fontFamily: "inherit",
              }}
            />
          </div>

          {/* Dedicated Why Visit card immediately following Description */}
          <div
            data-testid="detail-why-visit-card"
            style={{
              padding: "12px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--bg-hover, #f8fafc)",
              border: "1px solid var(--border-color, #e2e8f0)",
            }}
          >
            <label
              htmlFor="detail-poi-reason-to-visit"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                fontWeight: 700,
                color: "var(--accent, #2563eb)",
                marginBottom: "6px",
              }}
            >
              Why Visit (Reason to Visit)
            </label>
            <textarea
              id="detail-poi-reason-to-visit"
              rows={3}
              value={reasonToVisit}
              onChange={(e) => setReasonToVisit(e.target.value)}
              placeholder="Why visit this location..."
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #cbd5e1)",
                fontSize: "13px",
                resize: "vertical",
                fontFamily: "inherit",
                background: "var(--bg-surface, #ffffff)",
              }}
            />
          </div>

          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Visit Status
            </label>
            <select
              value={visitState}
              onChange={(e) => setVisitState(e.target.value as VisitState)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            >
              <option value="not_visited">Not Visited</option>
              <option value="visited_return">Visited (Would Return)</option>
              <option value="visited_do_not_return">
                Visited (Will Not Return)
              </option>
            </select>
          </div>

          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Rating
            </label>
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star === rating ? 0 : star)}
                  style={{ padding: "4px" }}
                >
                  <Star
                    size={20}
                    fill={star <= rating ? "#f59e0b" : "none"}
                    color={star <= rating ? "#f59e0b" : "var(--text-muted)"}
                  />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              City
            </label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Beijing"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>

          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Address / Notes
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Full address or location note"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>

          <TagSelector
            selectedTags={selectedTags}
            onChange={setSelectedTags}
          />

          <div
            style={{
              marginTop: "auto",
              paddingTop: "20px",
              display: "flex",
              gap: "10px",
            }}
          >
            <button
              type="submit"
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                padding: "10px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
              }}
            >
              <Save size={15} />
              <span>Save Changes</span>
            </button>

            {onDelete && (
              <button
                type="button"
                onClick={() => {
                  onDelete(poi.id);
                  onClose();
                }}
                title="Delete POI"
                style={{
                  padding: "10px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "var(--bg-hover, #f1f5f9)",
                  color: "var(--danger, #ef4444)",
                }}
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};
