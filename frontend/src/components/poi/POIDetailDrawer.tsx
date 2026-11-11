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
import { X, Star, Save, Trash2, ExternalLink, Globe } from "lucide-react";
import { TagSelector } from "../tags/TagSelector";
import { reconstructWebsitesList } from "../../utils/websiteInference";

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
          overflow: "hidden",
          padding: 0,
        }}
      >
        <div
          style={{
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px 16px 24px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <h3 style={{ fontSize: "18px", fontWeight: 800, margin: 0 }}>
            Edit Point of Interest
          </h3>
          <button
            type="button"
            onClick={onClose}
            style={{ padding: "4px", color: "var(--text-muted)", background: "transparent", border: "none", cursor: "pointer" }}
          >
            <X size={18} />
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              padding: "20px 24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
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
              rows={4}
              value={reasonToVisit}
              onChange={(e) => setReasonToVisit(e.target.value)}
              placeholder="- Key Highlight: Direct experiential reason why a traveler should visit..."
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #cbd5e1)",
                fontSize: "13px",
                resize: "vertical",
                fontFamily: "inherit",
                background: "var(--bg-surface, #ffffff)",
                lineHeight: 1.4,
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

          {/* Related Websites & Research */}
          {(() => {
            const sites = reconstructWebsitesList(poi as any);
            if (sites.length === 0) return null;
            return (
              <div
                data-testid="detail-related-websites-card"
                style={{
                  padding: "12px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "var(--bg-hover, #f8fafc)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                }}
              >
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--text-secondary, #475569)",
                    marginBottom: "8px",
                  }}
                >
                  <Globe size={13} style={{ color: "var(--accent, #2563eb)" }} />
                  Related Websites & Research ({sites.length})
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {sites.map((site, idx) => (
                    <div
                      key={`${site.url}-${idx}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        padding: "6px 10px",
                        borderRadius: "var(--radius-sm, 6px)",
                        background: "var(--bg-surface, #ffffff)",
                        border: "1px solid var(--border-color, #e2e8f0)",
                        fontSize: "12px",
                      }}
                    >
                      <span style={{ fontWeight: 600, color: "var(--text-primary, #0f172a)", minWidth: "90px" }}>
                        {site.name}:
                      </span>
                      <a
                        href={site.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: "var(--accent, #2563eb)",
                          textDecoration: "none",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "3px",
                        }}
                        title={site.url}
                      >
                        {site.url} <ExternalLink size={11} />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          <TagSelector
            selectedTags={selectedTags}
            onChange={setSelectedTags}
          />
        </div>

        <div
          style={{
            flexShrink: 0,
            padding: "16px 24px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
            background: "var(--bg-surface, #ffffff)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            boxShadow: "0 -2px 10px rgba(0, 0, 0, 0.05)",
            gap: "10px",
          }}
        >
          {onDelete ? (
            <button
              type="button"
              onClick={() => {
                onDelete(poi.id);
                onClose();
              }}
              title="Delete POI"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                background: "transparent",
                color: "var(--danger, #ef4444)",
                border: "1px solid var(--danger, #ef4444)",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Trash2 size={15} />
              Delete POI
            </button>
          ) : (
            <div />
          )}

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--bg-hover, #f1f5f9)",
                border: "1px solid var(--border-color, #e2e8f0)",
                color: "var(--text-secondary, #475569)",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 20px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                border: "none",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <Save size={15} />
              Save Changes
            </button>
          </div>
        </div>
      </form>
      </div>
    </div>
  );
};
