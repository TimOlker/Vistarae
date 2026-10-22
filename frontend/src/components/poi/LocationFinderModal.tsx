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

import React, { useState, useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  X,
  Search,
  MapPin,
  Layers,
  AlertTriangle,
  Check,
  Loader2,
  Compass,
} from "lucide-react";
import {
  forwardSearch,
  reverseGeocode,
  ForwardSearchResult,
  ReverseGeocodeResponse,
} from "../../services/geocodeService";
import { getMapLayers } from "../map/MapLayerSwitcher";
import type { LayerConfig, MapLayerId } from "../../types/map";

export interface LocationFinderModalProps {
  isOpen: boolean;
  initialLat?: number;
  initialLng?: number;
  onClose: () => void;
  onApply: (
    coords: { lat: number; lng: number },
    address?: ReverseGeocodeResponse,
  ) => void;
}

function createRasterStyle(
  layerConfig: LayerConfig,
): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      "raster-tiles": {
        type: "raster",
        tiles: layerConfig.tiles,
        tileSize: 256,
        attribution: layerConfig.attribution,
        maxzoom: layerConfig.maxZoom,
      },
    },
    layers: [
      {
        id: "raster-layer",
        type: "raster",
        source: "raster-tiles",
        minzoom: 0,
        maxzoom: layerConfig.maxZoom,
      },
    ],
  };
}

export const LocationFinderModal: React.FC<LocationFinderModalProps> = ({
  isOpen,
  initialLat = 37.8651,
  initialLng = -119.5383,
  onClose,
  onApply,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);

  // Selected Pin Coordinates
  const [selectedLat, setSelectedLat] = useState<number>(initialLat);
  const [selectedLng, setSelectedLng] = useState<number>(initialLng);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ForwardSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResultsDropdown, setShowResultsDropdown] = useState(false);
  const [specificityWarning, setSpecificityWarning] = useState<string | null>(
    null,
  );

  // Layer state
  const availableLayers = getMapLayers("local");
  const [activeLayerId, setActiveLayerId] = useState<MapLayerId>("osm");
  const [showLayerMenu, setShowLayerMenu] = useState(false);

  // Apply state
  const [isApplying, setIsApplying] = useState(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isOpen) {
      const validLat =
        typeof initialLat === "number" && !isNaN(initialLat) && initialLat !== 0
          ? initialLat
          : 37.8651;
      const validLng =
        typeof initialLng === "number" && !isNaN(initialLng) && initialLng !== 0
          ? initialLng
          : -119.5383;
      setSelectedLat(validLat);
      setSelectedLng(validLng);
      setSpecificityWarning(null);
      setSearchQuery("");
      setSearchResults([]);
    }
  }, [isOpen, initialLat, initialLng]);

  // Initialize MapLibre
  useEffect(() => {
    if (!isOpen || !mapContainerRef.current) return;

    const layerConfig =
      availableLayers.find((l) => l.id === activeLayerId) || availableLayers[0];
    const initialCenter: [number, number] = [selectedLng, selectedLat];

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style:
        layerConfig.type === "vector"
          ? layerConfig.styleUrl
          : createRasterStyle(layerConfig),
      center: initialCenter,
      zoom: 14,
      attributionControl: false,
    });

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true }),
      "top-right",
    );

    // Create Pin Marker
    const markerEl = document.createElement("div");
    markerEl.className = "location-finder-pin";
    markerEl.style.width = "30px";
    markerEl.style.height = "30px";
    markerEl.style.cursor = "pointer";
    markerEl.innerHTML = `
      <svg viewBox="0 0 24 24" width="30" height="30" fill="#2563eb" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
        <circle cx="12" cy="10" r="3" fill="#ffffff"></circle>
      </svg>
    `;

    const marker = new maplibregl.Marker({ element: markerEl, draggable: true })
      .setLngLat(initialCenter)
      .addTo(map);

    marker.on("dragend", () => {
      const lngLat = marker.getLngLat();
      setSelectedLat(lngLat.lat);
      setSelectedLng(lngLat.lng);
      setSpecificityWarning(null);
    });

    // Click canvas to place pin
    map.on("click", (e) => {
      const { lng, lat } = e.lngLat;
      setSelectedLat(lat);
      setSelectedLng(lng);
      marker.setLngLat([lng, lat]);
      setSpecificityWarning(null);
    });

    mapInstanceRef.current = map;
    markerRef.current = marker;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      markerRef.current = null;
    };
  }, [isOpen]);

  // Handle Layer Switch
  const handleSwitchLayer = (layerId: MapLayerId) => {
    setActiveLayerId(layerId);
    setShowLayerMenu(false);
    const map = mapInstanceRef.current;
    if (!map) return;

    const layerConfig = availableLayers.find((l) => l.id === layerId);
    if (!layerConfig) return;

    if (layerConfig.type === "vector" && layerConfig.styleUrl) {
      map.setStyle(layerConfig.styleUrl);
    } else {
      map.setStyle(createRasterStyle(layerConfig));
    }
  };

  // Debounced Forward Search
  const handleSearchInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (val.trim().length < 2) {
      setSearchResults([]);
      setShowResultsDropdown(false);
      return;
    }

    setIsSearching(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const results = await forwardSearch(val, 5);
        setSearchResults(results);
        setShowResultsDropdown(true);
      } finally {
        setIsSearching(false);
      }
    }, 500);
  };

  // Select Search Match
  const handleSelectMatch = (match: ForwardSearchResult) => {
    setShowResultsDropdown(false);
    setSearchQuery(match.name);
    setSelectedLat(match.lat);
    setSelectedLng(match.lng);

    const map = mapInstanceRef.current;
    const marker = markerRef.current;
    if (map && marker) {
      map.flyTo({
        center: [match.lng, match.lat],
        zoom: match.suggestedZoom,
        essential: true,
      });
      marker.setLngLat([match.lng, match.lat]);
    }

    if (!match.isSpecificLandmark) {
      setSpecificityWarning(
        `"${match.name}" is a broad regional or city centroid. Zoom in and click on the map to place a pinpoint marker on your exact attraction.`,
      );
    } else {
      setSpecificityWarning(null);
    }
  };

  // Handle Apply
  const handleApply = async () => {
    setIsApplying(true);
    try {
      let resolvedAddress: ReverseGeocodeResponse | undefined;
      try {
        resolvedAddress = await reverseGeocode(selectedLat, selectedLng);
      } catch (err) {
        console.warn("Reverse geocoding on apply failed", err);
      }

      onApply(
        {
          lat: Math.round(selectedLat * 100000) / 100000,
          lng: Math.round(selectedLng * 100000) / 100000,
        },
        resolvedAddress,
      );
      onClose();
    } finally {
      setIsApplying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop fade-in"
      onClick={onClose}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(4px)",
        zIndex: 6000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        className="location-finder-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "900px",
          maxWidth: "100%",
          height: "640px",
          maxHeight: "92vh",
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          boxShadow: "var(--shadow-lg)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header with Search and Layer Switcher */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            background: "var(--bg-card, #ffffff)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Compass size={18} style={{ color: "var(--accent, #2563eb)" }} />
              <h3 style={{ fontSize: "16px", fontWeight: 800, margin: 0 }}>
                Location Finder: Interactive Pinpoint Map
              </h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: "4px",
                color: "var(--text-muted)",
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Search Bar & Layer Switcher Row */}
          <div style={{ display: "flex", gap: "10px", position: "relative" }}>
            <div style={{ flex: 1, position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  left: "10px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {isSearching ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Search size={15} />
                )}
              </div>
              <input
                type="text"
                placeholder="Search landmarks, attractions, or cities (e.g. Mount Rushmore, Paris)..."
                value={searchQuery}
                onChange={handleSearchInput}
                onFocus={() => {
                  if (searchResults.length > 0) setShowResultsDropdown(true);
                }}
                style={{
                  width: "100%",
                  padding: "8px 12px 8px 34px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  fontSize: "13px",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-primary, #0f172a)",
                  outline: "none",
                }}
              />

              {/* Search Results Dropdown */}
              {showResultsDropdown && searchResults.length > 0 && (
                <div
                  style={{
                    position: "absolute",
                    top: "calc(100% + 4px)",
                    left: 0,
                    right: 0,
                    maxHeight: "220px",
                    overflowY: "auto",
                    background: "var(--bg-surface, #ffffff)",
                    borderRadius: "var(--radius-md, 8px)",
                    boxShadow: "var(--shadow-lg)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    zIndex: 7000,
                  }}
                >
                  {searchResults.map((match, idx) => (
                    <div
                      key={idx}
                      onClick={() => handleSelectMatch(match)}
                      style={{
                        padding: "8px 12px",
                        cursor: "pointer",
                        borderBottom: "1px solid var(--border-color, #f1f5f9)",
                        fontSize: "12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "2px",
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
                          color: "var(--text-primary)",
                        }}
                      >
                        {match.name}
                      </span>
                      <span
                        style={{ fontSize: "11px", color: "var(--text-muted)" }}
                      >
                        {match.display_name}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Layer Switcher Dropdown Button */}
            <div style={{ position: "relative" }}>
              <button
                type="button"
                onClick={() => setShowLayerMenu(!showLayerMenu)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-secondary, #475569)",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                <Layers size={14} />
                Layers
              </button>

              {showLayerMenu && (
                <div
                  style={{
                    position: "absolute",
                    right: 0,
                    top: "calc(100% + 4px)",
                    width: "200px",
                    background: "var(--bg-surface, #ffffff)",
                    borderRadius: "var(--radius-md, 8px)",
                    boxShadow: "var(--shadow-lg)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    zIndex: 7000,
                    padding: "4px 0",
                  }}
                >
                  {availableLayers.slice(0, 5).map((layer) => (
                    <div
                      key={layer.id}
                      onClick={() => handleSwitchLayer(layer.id)}
                      style={{
                        padding: "8px 12px",
                        cursor: "pointer",
                        fontSize: "12px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        color:
                          activeLayerId === layer.id
                            ? "var(--accent)"
                            : "var(--text-primary)",
                        fontWeight: activeLayerId === layer.id ? 700 : 500,
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
                      <span>{layer.name}</span>
                      {activeLayerId === layer.id && <Check size={14} />}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Specificity Warning Banner */}
          {specificityWarning && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-sm, 6px)",
                background: "#fef3c7",
                border: "1px solid #fde68a",
                color: "#92400e",
                fontSize: "11px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <AlertTriangle size={14} style={{ flexShrink: 0 }} />
              <span>{specificityWarning}</span>
            </div>
          )}
        </div>

        {/* Map Canvas */}
        <div
          style={{
            flex: 1,
            position: "relative",
            width: "100%",
            height: "100%",
          }}
        >
          <div
            ref={mapContainerRef}
            style={{ width: "100%", height: "100%" }}
          />

          {/* Floating Instructions Pill */}
          <div
            style={{
              position: "absolute",
              bottom: "16px",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(15, 23, 42, 0.8)",
              backdropFilter: "blur(4px)",
              color: "#ffffff",
              padding: "6px 14px",
              borderRadius: "var(--radius-full, 9999px)",
              fontSize: "11px",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: "6px",
              pointerEvents: "none",
              boxShadow: "0 4px 6px -1px rgba(0,0,0,0.2)",
            }}
          >
            <MapPin size={12} fill="#3b82f6" />
            Click anywhere on the map or drag pin to update position
          </div>
        </div>

        {/* Footer Coordinate Readout and Action Buttons */}
        <div
          style={{
            padding: "14px 20px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--bg-card, #ffffff)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "14px",
              fontSize: "12px",
            }}
          >
            <span>
              Latitude: <strong>{selectedLat.toFixed(5)}°</strong>
            </span>
            <span>
              Longitude: <strong>{selectedLng.toFixed(5)}°</strong>
            </span>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isApplying}
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
              type="button"
              onClick={handleApply}
              disabled={isApplying}
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
                cursor: isApplying ? "not-allowed" : "pointer",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              {isApplying ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Resolving Address...
                </>
              ) : (
                <>
                  <Check size={15} />
                  Apply Location
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
