// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import type { LayerConfig, MapLayerId } from "../../types/map";
import { Layers, Check, Bookmark } from "lucide-react";

export const MAP_LAYERS: LayerConfig[] = [
  {
    id: "osm",
    name: "OpenStreetMap",
    isShifted: false,
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  },
  {
    id: "satellite",
    name: "Satellite (Esri)",
    isShifted: false,
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    maxZoom: 18,
    attribution: "© Esri, Maxar, Earthstar Geographics",
  },
  {
    id: "road",
    name: "Road (Voyager)",
    isShifted: false,
    tiles: [
      "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    ],
    maxZoom: 19,
    attribution: "© CARTO, © OpenStreetMap contributors",
  },
  {
    id: "google-roadmap",
    name: "Google Maps",
    isShifted: false,
    tiles: ["https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"],
    maxZoom: 20,
    attribution: "© Google",
  },
  {
    id: "google-hybrid",
    name: "Google Hybrid",
    isShifted: false,
    tiles: ["https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"],
    maxZoom: 20,
    attribution: "© Google",
  },
  {
    id: "amap",
    name: "AutoNavi / Amap (GCJ-02)",
    isShifted: true,
    tiles: [
      "https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
    ],
    maxZoom: 18,
    attribution: "© AutoNavi (高德地图)",
  },
  {
    id: "baidu",
    name: "Baidu Maps (BD-09)",
    isShifted: true,
    tiles: [
      "https://api.map.baidu.com/customimage/tile?&x={x}&y={y}&z={z}&udt=20200825&scale=1",
    ],
    maxZoom: 18,
    attribution: "© Baidu (百度地图)",
  },
];

interface MapLayerSwitcherProps {
  activeLayer: MapLayerId;
  defaultLayer?: MapLayerId;
  onLayerChange: (layerId: MapLayerId) => void;
  onSaveAsDefault?: (layerId: MapLayerId) => void;
}

export const MapLayerSwitcher: React.FC<MapLayerSwitcherProps> = ({
  activeLayer,
  defaultLayer,
  onLayerChange,
  onSaveAsDefault,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const handleSaveDefault = () => {
    if (onSaveAsDefault) {
      onSaveAsDefault(activeLayer);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
    }
  };

  return (
    <div className="map-layer-switcher" style={{ position: "relative" }}>
      <button
        type="button"
        className="layer-switcher-toggle"
        onClick={() => setIsOpen((prev) => !prev)}
        title="Change map layer"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "8px 12px",
          background: "var(--bg-surface, #ffffff)",
          color: "var(--text-primary, #0f172a)",
          borderRadius: "var(--radius-md, 8px)",
          boxShadow: "var(--shadow-md)",
          fontWeight: 600,
          fontSize: "13px",
          border: "1px solid var(--border-color, #e2e8f0)",
        }}
      >
        <Layers size={16} />
        <span>Layers</span>
      </button>

      {isOpen && (
        <div
          className="layer-switcher-panel slide-up"
          style={{
            position: "absolute",
            top: "42px",
            right: 0,
            width: "260px",
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-md, 8px)",
            boxShadow: "var(--shadow-lg)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "10px",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              fontSize: "12px",
              fontWeight: 700,
              textTransform: "uppercase",
              color: "var(--text-muted, #94a3b8)",
              marginBottom: "8px",
              paddingLeft: "4px",
            }}
          >
            Base Map Layers
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {MAP_LAYERS.map((layer) => {
              const isActive = layer.id === activeLayer;
              const isDefault = layer.id === defaultLayer;

              return (
                <button
                  key={layer.id}
                  type="button"
                  onClick={() => {
                    onLayerChange(layer.id);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: isActive
                      ? "var(--accent-light, #eff6ff)"
                      : "transparent",
                    color: isActive
                      ? "var(--accent, #2563eb)"
                      : "var(--text-primary, #0f172a)",
                    fontSize: "13px",
                    fontWeight: isActive ? 600 : 400,
                    textAlign: "left",
                    transition: "background 150ms ease",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <span>{layer.name}</span>
                    {layer.isShifted && (
                      <span
                        style={{
                          fontSize: "10px",
                          padding: "1px 5px",
                          borderRadius: "4px",
                          background: "#fef3c7",
                          color: "#b45309",
                          fontWeight: 700,
                        }}
                      >
                        Shifted
                      </span>
                    )}
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    {isDefault && (
                      <span
                        title="Configured default layer"
                        style={{ fontSize: "10px", color: "var(--text-muted)" }}
                      >
                        (Default)
                      </span>
                    )}
                    {isActive && (
                      <Check size={14} color="var(--accent, #2563eb)" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {onSaveAsDefault && (
            <div
              style={{
                marginTop: "10px",
                paddingTop: "8px",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <button
                type="button"
                onClick={handleSaveDefault}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  width: "100%",
                  padding: "6px 10px",
                  borderRadius: "var(--radius-sm, 6px)",
                  background: justSaved
                    ? "var(--success, #10b981)"
                    : "var(--bg-hover, #f1f5f9)",
                  color: justSaved
                    ? "#ffffff"
                    : "var(--text-secondary, #475569)",
                  fontSize: "12px",
                  fontWeight: 600,
                  transition: "background 150ms ease",
                }}
              >
                <Bookmark size={13} />
                <span>
                  {justSaved ? "Saved as Default!" : "Save as Default"}
                </span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
