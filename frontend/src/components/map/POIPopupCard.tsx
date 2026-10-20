// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import type { POIMapFeature } from "../../types/map";
import { X, Star, MapPin, Tag } from "lucide-react";

interface POIPopupCardProps {
  poi: POIMapFeature;
  onClose: () => void;
  onEdit?: (poi: POIMapFeature) => void;
}

export const POIPopupCard: React.FC<POIPopupCardProps> = ({
  poi,
  onClose,
  onEdit,
}) => {
  return (
    <div
      className="poi-popup-card slide-up"
      style={{
        width: "280px",
        padding: "14px",
        background: "var(--bg-surface, #ffffff)",
        color: "var(--text-primary, #0f172a)",
        borderRadius: "var(--radius-md, 10px)",
        boxShadow: "var(--shadow-lg)",
        border: "1px solid var(--border-color, #e2e8f0)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "8px",
          marginBottom: "8px",
        }}
      >
        <h4 style={{ fontSize: "15px", fontWeight: 700, lineHeight: 1.2 }}>
          {poi.name}
        </h4>
        <button
          type="button"
          onClick={onClose}
          style={{
            padding: "2px",
            color: "var(--text-muted, #94a3b8)",
            cursor: "pointer",
          }}
        >
          <X size={16} />
        </button>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "8px",
          fontSize: "12px",
        }}
      >
        {poi.rating && (
          <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
            <Star size={13} fill="#f59e0b" color="#f59e0b" />
            <span style={{ fontWeight: 600 }}>{poi.rating.toFixed(1)}</span>
          </div>
        )}
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            padding: "1px 6px",
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
          }}
        >
          {poi.visit_state.replace(/_/g, " ")}
        </span>
      </div>

      {(poi.city || poi.address) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "12px",
            color: "var(--text-secondary, #475569)",
            marginBottom: "8px",
          }}
        >
          <MapPin size={13} style={{ flexShrink: 0 }} />
          <span>{poi.city || poi.address}</span>
        </div>
      )}

      {poi.tags.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            flexWrap: "wrap",
            marginBottom: "10px",
          }}
        >
          <Tag size={12} color="var(--text-muted)" />
          {poi.tags.map((t) => (
            <span
              key={t}
              style={{
                fontSize: "10px",
                padding: "2px 5px",
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

      {onEdit && (
        <button
          type="button"
          onClick={() => onEdit(poi)}
          style={{
            width: "100%",
            padding: "6px 12px",
            borderRadius: "var(--radius-sm, 6px)",
            background: "var(--accent, #2563eb)",
            color: "#ffffff",
            fontSize: "12px",
            fontWeight: 600,
            textAlign: "center",
          }}
        >
          Edit Details
        </button>
      )}
    </div>
  );
};
