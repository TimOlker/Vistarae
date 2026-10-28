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
import type { POIMapFeature } from "../../types/map";
import { X, Star, MapPin, Tag, Edit3 } from "lucide-react";

export interface POIPopupCardProps {
  poi: POIMapFeature;
  onClose: () => void;
  onEdit?: (poi: POIMapFeature) => void;
}

export const POIPopupCard: React.FC<POIPopupCardProps> = ({
  poi,
  onClose,
  onEdit,
}) => {
  const [imageError, setImageError] = useState(false);
  const hasMultipleAddresses =
    Array.isArray(poi.addresses) && poi.addresses.length > 1;
  const addressCount = poi.addresses?.length || 1;
  const thumbnailUrl =
    poi.image_urls && poi.image_urls.length > 0 && !imageError
      ? poi.image_urls[0]
      : null;

  const renderStars = () => {
    if (!poi.rating) {
      return (
        <span
          data-testid="unrated-indicator"
          style={{
            fontSize: "11px",
            color: "var(--text-muted, #94a3b8)",
            fontWeight: 500,
          }}
        >
          Unrated
        </span>
      );
    }

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            size={12}
            fill={star <= poi.rating! ? "#f59e0b" : "none"}
            color={star <= poi.rating! ? "#f59e0b" : "#D1D5DB"}
          />
        ))}
        <span
          style={{
            fontSize: "11px",
            fontWeight: 700,
            marginLeft: "3px",
            color: "#B45309",
          }}
        >
          {poi.rating.toFixed(1)}
        </span>
      </div>
    );
  };

  return (
    <div
      className="poi-popup-card slide-up"
      data-testid="poi-popup-card"
      style={{
        width: "280px",
        padding: "14px",
        background: "var(--bg-surface, #ffffff)",
        color: "var(--text-primary, #0f172a)",
        borderRadius: "var(--radius-md, 10px)",
        boxShadow:
          "0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
        border: "1px solid var(--border-color, #e2e8f0)",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      {/* Header Row: Title & Close Button */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "8px",
        }}
      >
        <h4
          data-testid="poi-popup-title"
          style={{
            margin: 0,
            fontSize: "14px",
            fontWeight: 700,
            lineHeight: 1.3,
            color: "#111827",
          }}
        >
          {poi.name}
        </h4>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          data-testid="close-popup-btn"
          style={{
            background: "none",
            border: "none",
            padding: "2px",
            color: "var(--text-muted, #94a3b8)",
            cursor: "pointer",
            borderRadius: "4px",
          }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Thumbnail preview if valid image exists */}
      {thumbnailUrl && (
        <div
          style={{
            width: "100%",
            height: "110px",
            borderRadius: "6px",
            overflow: "hidden",
            backgroundColor: "#F3F4F6",
          }}
        >
          <img
            src={thumbnailUrl}
            alt={poi.name}
            data-testid="poi-popup-thumbnail"
            onError={() => setImageError(true)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        </div>
      )}

      {/* Rating & Visit Status */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "12px",
        }}
      >
        {renderStars()}
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            padding: "2px 6px",
            borderRadius: "4px",
            background:
              poi.visit_state === "visited_return"
                ? "#ecfdf5"
                : poi.visit_state === "visited_do_not_return"
                  ? "#fffbeb"
                  : "#eff6ff",
            color:
              poi.visit_state === "visited_return"
                ? "#047857"
                : poi.visit_state === "visited_do_not_return"
                  ? "#b45309"
                  : "#1d4ed8",
            textTransform: "capitalize",
          }}
        >
          {(poi.visit_state || "not_visited").replace(/_/g, " ")}
        </span>
      </div>

      {/* Estimated Visit Time & Duration Explanation */}
      {(poi.recommended_duration_hours != null ||
        (poi.recommended_visit_days != null && poi.recommended_visit_days > 0) ||
        poi.estimated_visit_time_notes) && (
        <div
          data-testid="poi-popup-duration"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "3px",
            fontSize: "11px",
            color: "var(--text-secondary, #475569)",
            backgroundColor: "var(--bg-hover, #f8fafc)",
            padding: "6px 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-color, #e2e8f0)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 600 }}>
            <span>⏱️ Estimated Visit:</span>
            <span>
              {poi.recommended_duration_hours != null ? `${poi.recommended_duration_hours} hrs` : "Flexible"}
              {poi.recommended_visit_days ? ` (${poi.recommended_visit_days} ${poi.recommended_visit_days === 1 ? "day" : "days"})` : ""}
            </span>
          </div>
          {poi.estimated_visit_time_notes && (
            <div style={{ fontSize: "10.5px", color: "var(--text-muted, #64748b)", fontStyle: "italic", whiteSpace: "pre-wrap" }}>
              {poi.estimated_visit_time_notes}
            </div>
          )}
        </div>
      )}

      {/* Address info: formatted or multiple locations badge */}
      {hasMultipleAddresses ? (
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <MapPin size={13} style={{ flexShrink: 0, color: "#2563EB" }} />
          <span
            data-testid="multi-location-badge"
            style={{
              padding: "2px 6px",
              borderRadius: "4px",
              backgroundColor: "#EFF6FF",
              color: "#1D4ED8",
              fontSize: "11px",
              fontWeight: 600,
            }}
          >
            Multiple Locations ({addressCount})
          </span>
        </div>
      ) : (
        (poi.city ||
          poi.address ||
          poi.country ||
          (poi.addresses && poi.addresses.length > 0)) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
              color: "var(--text-secondary, #475569)",
            }}
          >
            <MapPin size={13} style={{ flexShrink: 0, color: "#6B7280" }} />
            <span data-testid="single-address-summary">
              {(() => {
                const addr = poi.addresses?.[0];
                const city = addr?.city?.trim() || poi.city;
                // If addresses exist, state_province from the address record is authoritative
                const state =
                  poi.addresses && poi.addresses.length > 0
                    ? addr?.state_province?.trim()
                    : poi.state;
                const country = addr?.country?.trim() || poi.country;
                return (
                  [city, state, country].filter(Boolean).join(", ") ||
                  addr?.street ||
                  poi.address
                );
              })()}
            </span>
          </div>
        )
      )}

      {/* Tags */}
      {poi.tags && poi.tags.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            flexWrap: "wrap",
          }}
        >
          <Tag size={11} color="var(--text-muted, #94a3b8)" />
          {poi.tags.slice(0, 3).map((t) => (
            <span
              key={t}
              style={{
                fontSize: "10px",
                padding: "1px 5px",
                borderRadius: "4px",
                background: "var(--bg-hover, #f1f5f9)",
                color: "var(--text-secondary, #475569)",
              }}
            >
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Edit POI Action Button */}
      {onEdit && (
        <button
          type="button"
          onClick={() => onEdit(poi)}
          data-testid="popup-edit-poi-btn"
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            padding: "6px 12px",
            borderRadius: "6px",
            background: "#2563EB",
            color: "#ffffff",
            fontSize: "12px",
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
            marginTop: "2px",
          }}
        >
          <Edit3 size={13} />
          <span>Edit POI</span>
        </button>
      )}
    </div>
  );
};
