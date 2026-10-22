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

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, Loader2, Network } from "lucide-react";
import { apiFetch } from "../../services/api";
import type { components } from "../../types/poi-edit-api";

type ParentPOICandidate = components["schemas"]["ParentPOICandidate"];

export interface ParentPOISelectorProps {
  activePoiId?: string;
  selectedParentId?: string | null;
  selectedParentName?: string | null;
  onChange: (parentId: string | null, parentName: string | null) => void;
  disabled?: boolean;
}

export const ParentPOISelector: React.FC<ParentPOISelectorProps> = ({
  activePoiId,
  selectedParentId,
  selectedParentName,
  onChange,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<ParentPOICandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentName, setCurrentName] = useState<string | null>(
    selectedParentName || null,
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setCurrentName(selectedParentName || null);
  }, [selectedParentName]);

  const fetchCandidates = useCallback(
    async (searchQuery: string) => {
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        if (searchQuery.trim()) {
          params.set("query", searchQuery.trim());
        }
        if (activePoiId) {
          params.set("exclude_poi_id", activePoiId);
        }
        params.set("limit", "15");

        const endpoint = `/api/pois/parents?${params.toString()}`;
        const data = await apiFetch<ParentPOICandidate[]>(endpoint);
        setCandidates(data || []);
      } catch (err) {
        console.error("Failed to fetch candidate parent POIs", err);
        setCandidates([]);
      } finally {
        setIsLoading(false);
      }
    },
    [activePoiId],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setIsOpen(true);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      fetchCandidates(val);
    }, 300);
  };

  const handleSelect = (candidate: ParentPOICandidate) => {
    setCurrentName(candidate.name);
    setQuery("");
    setIsOpen(false);
    onChange(candidate.id, candidate.name);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentName(null);
    setQuery("");
    onChange(null, null);
  };

  const handleFocus = () => {
    setIsOpen(true);
    fetchCandidates(query);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <label
        style={{
          fontSize: "12px",
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginBottom: "6px",
          color: "var(--text-secondary, #475569)",
        }}
      >
        <Network size={14} style={{ color: "var(--accent, #2563eb)" }} />
        Parent POI (Hierarchy)
      </label>

      {/* Selected Parent Display Chip or Search Input */}
      {selectedParentId && currentName ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderRadius: "var(--radius-md, 8px)",
            border: "1px solid var(--border-color, #e2e8f0)",
            background: "var(--bg-hover, #f8fafc)",
            fontSize: "13px",
            color: "var(--text-primary, #0f172a)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              overflow: "hidden",
            }}
          >
            <span
              style={{
                fontSize: "10px",
                fontWeight: 800,
                padding: "2px 6px",
                borderRadius: "var(--radius-sm, 4px)",
                background: "var(--accent-light, #eff6ff)",
                color: "var(--accent, #2563eb)",
                textTransform: "uppercase",
              }}
            >
              Parent
            </span>
            <span
              style={{
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {currentName}
            </span>
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={handleClear}
              aria-label="Remove parent POI"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "2px",
                borderRadius: "var(--radius-full, 9999px)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--text-muted, #94a3b8)",
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>
      ) : (
        <div style={{ position: "relative" }}>
          <div
            style={{
              position: "absolute",
              left: "10px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--text-muted, #94a3b8)",
              display: "flex",
              alignItems: "center",
            }}
          >
            {isLoading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Search size={15} />
            )}
          </div>
          <input
            type="text"
            disabled={disabled}
            value={query}
            placeholder="Search candidate parent POIs..."
            onChange={handleInputChange}
            onFocus={handleFocus}
            style={{
              width: "100%",
              padding: "8px 12px 8px 34px",
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-color, #e2e8f0)",
              background: "var(--bg-surface, #ffffff)",
              color: "var(--text-primary, #0f172a)",
              fontSize: "13px",
              outline: "none",
            }}
          />
        </div>
      )}

      {/* Typeahead Dropdown */}
      {isOpen && !selectedParentId && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            maxHeight: "220px",
            overflowY: "auto",
            background: "var(--bg-surface, #ffffff)",
            border: "1px solid var(--border-color, #e2e8f0)",
            borderRadius: "var(--radius-md, 8px)",
            boxShadow: "var(--shadow-lg, 0 10px 15px -3px rgba(0,0,0,0.1))",
            zIndex: 6000,
          }}
        >
          {isLoading && candidates.length === 0 ? (
            <div
              style={{
                padding: "12px",
                textAlign: "center",
                fontSize: "12px",
                color: "var(--text-muted)",
              }}
            >
              Loading parent candidates...
            </div>
          ) : candidates.length === 0 ? (
            <div
              style={{
                padding: "12px",
                textAlign: "center",
                fontSize: "12px",
                color: "var(--text-muted)",
              }}
            >
              No eligible parent POIs found
            </div>
          ) : (
            candidates.map((c) => (
              <div
                key={c.id}
                onClick={() => handleSelect(c)}
                style={{
                  padding: "8px 12px",
                  cursor: "pointer",
                  borderBottom: "1px solid var(--border-color, #e2e8f0)",
                  fontSize: "13px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  transition: "background var(--transition-fast)",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    "var(--bg-hover, #f8fafc)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background =
                    "transparent";
                }}
              >
                <span
                  style={{
                    fontWeight: 600,
                    color: "var(--text-primary, #0f172a)",
                  }}
                >
                  {c.name}
                </span>
                {c.location_summary && (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--text-muted, #64748b)",
                    }}
                  >
                    {c.location_summary}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
