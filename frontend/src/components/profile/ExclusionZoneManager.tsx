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

import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import {
  exclusionZoneService,
  type ExclusionZoneItem,
} from "../../services/exclusionZoneService";
import { useToast } from "../../context/ToastContext";
import {
  Shield,
  ShieldAlert,
  MapPin,
  Trash2,
  Plus,
  Crosshair,
  Loader2,
  Compass,
} from "lucide-react";

/**
 * Generates a GeoJSON Polygon representing a circle on the globe.
 */
function createGeoJSONCircle(
  center: [number, number],
  radiusKm: number,
  points = 64,
): GeoJSON.Feature<GeoJSON.Polygon> {
  const [lng, lat] = center;
  const coords: [number, number][] = [];
  const distanceX = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180));
  const distanceY = radiusKm / 110.574;

  for (let i = 0; i < points; i++) {
    const theta = (i / points) * (2 * Math.PI);
    const x = distanceX * Math.cos(theta);
    const y = distanceY * Math.sin(theta);
    coords.push([lng + x, lat + y]);
  }
  coords.push(coords[0]);

  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "Polygon",
      coordinates: [coords],
    },
  };
}

export const ExclusionZoneManager: React.FC = () => {
  const { showToast } = useToast();

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);
  const pendingMarkerRef = useRef<maplibregl.Marker | null>(null);
  const existingMarkersRef = useRef<maplibregl.Marker[]>([]);

  const [zones, setZones] = useState<ExclusionZoneItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // New zone draft state
  const [zoneName, setZoneName] = useState("");
  const [zoneRadiusKm, setZoneRadiusKm] = useState<number>(1.0);
  const [pickedCenter, setPickedCenter] = useState<[number, number] | null>(null);

  // Load existing exclusion zones
  const loadZones = async () => {
    setIsLoading(true);
    try {
      const data = await exclusionZoneService.getExclusionZones();
      setZones(data);
    } catch (err: any) {
      showToast(err?.message || "Failed to load exclusion zones", "error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadZones();
  }, []);

  // Initialize MapLibre GL Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapInstanceRef.current) {
      try {
        mapInstanceRef.current.remove();
      } catch {
        // ignore
      }
      mapInstanceRef.current = null;
    }

    const defaultCenter: [number, number] =
      zones.length > 0 ? [zones[0].longitude, zones[0].latitude] : [-88.3, 41.8];

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          "osm-tiles": {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "osm-layer",
            type: "raster",
            source: "osm-tiles",
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: defaultCenter,
      zoom: zones.length > 0 ? 12 : 10,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("click", (e) => {
      const lng = e.lngLat.lng;
      const lat = e.lngLat.lat;
      setPickedCenter([lng, lat]);
    });

    mapInstanceRef.current = map;

    return () => {
      try {
        map.remove();
      } catch {
        // ignore
      }
      mapInstanceRef.current = null;
    };
  }, []);

  // Sync saved exclusion zone circle layers on map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const renderLayers = () => {
      // Clear existing zone markers
      existingMarkersRef.current.forEach((m) => {
        try {
          m.remove();
        } catch {
          // ignore
        }
      });
      existingMarkersRef.current = [];

      // Update source for all saved zones GeoJSON
      const featureCollection: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: zones.map((z) => {
          const circleFeature = createGeoJSONCircle([z.longitude, z.latitude], z.radius_km);
          circleFeature.properties = {
            id: z.id,
            name: z.name,
            radius_km: z.radius_km,
          };
          return circleFeature;
        }),
      };

      if (map.getSource("saved-exclusion-zones")) {
        const src = map.getSource("saved-exclusion-zones") as maplibregl.GeoJSONSource;
        if (typeof src.setData === "function") {
          src.setData(featureCollection);
        }
      } else {
        map.addSource("saved-exclusion-zones", {
          type: "geojson",
          data: featureCollection,
        });

        map.addLayer({
          id: "saved-exclusion-zones-fill",
          type: "fill",
          source: "saved-exclusion-zones",
          paint: {
            "fill-color": "#dc2626",
            "fill-opacity": 0.22,
          },
        });

        map.addLayer({
          id: "saved-exclusion-zones-line",
          type: "line",
          source: "saved-exclusion-zones",
          paint: {
            "line-color": "#b91c1c",
            "line-width": 2,
            "line-dasharray": [2, 2],
          },
        });
      }

      // Add markers with zone labels
      zones.forEach((z) => {
        try {
          const el = document.createElement("div");
          el.style.display = "flex";
          el.style.alignItems = "center";
          el.style.gap = "4px";
          el.style.padding = "2px 8px";
          el.style.backgroundColor = "#fee2e2";
          el.style.border = "1px solid #ef4444";
          el.style.borderRadius = "9999px";
          el.style.fontSize = "11px";
          el.style.fontWeight = "700";
          el.style.color = "#991b1b";
          el.style.boxShadow = "0 1px 3px rgba(0,0,0,0.2)";
          el.style.cursor = "pointer";
          el.title = `${z.name} (${z.radius_km} km radius)`;
          el.innerHTML = `<span>🛡️ ${z.name}</span>`;

          const m = new maplibregl.Marker({ element: el })
            .setLngLat([z.longitude, z.latitude])
            .addTo(map);

          existingMarkersRef.current.push(m);
        } catch {
          // ignore
        }
      });
    };

    if (map.isStyleLoaded && map.isStyleLoaded()) {
      renderLayers();
    } else {
      map.once("load", renderLayers);
    }
  }, [zones]);

  // Update pending / draft zone circle and pin preview
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (!pickedCenter) {
      if (pendingMarkerRef.current) {
        pendingMarkerRef.current.remove();
        pendingMarkerRef.current = null;
      }
      if (map.getSource("pending-exclusion-zone")) {
        const src = map.getSource("pending-exclusion-zone") as maplibregl.GeoJSONSource;
        if (typeof src.setData === "function") {
          src.setData({ type: "FeatureCollection", features: [] });
        }
      }
      return;
    }

    // Place or update pending marker
    if (!pendingMarkerRef.current) {
      const pinEl = document.createElement("div");
      pinEl.style.width = "26px";
      pinEl.style.height = "26px";
      pinEl.style.cursor = "grab";
      pinEl.innerHTML = `
        <svg viewBox="0 0 24 24" width="26" height="26" fill="#dc2626" stroke="#ffffff" stroke-width="2" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35));">
          <circle cx="12" cy="12" r="9"></circle>
          <path d="M12 7v5l3 3" stroke="#ffffff" stroke-width="2" stroke-linecap="round"></path>
        </svg>
      `;
      const marker = new maplibregl.Marker({ element: pinEl, draggable: true })
        .setLngLat(pickedCenter)
        .addTo(map);

      if (typeof marker.on === "function") {
        marker.on("dragend", () => {
          if (typeof marker.getLngLat === "function") {
            const pos = marker.getLngLat();
            setPickedCenter([pos.lng, pos.lat]);
          }
        });
      }
      pendingMarkerRef.current = marker;
    } else {
      pendingMarkerRef.current.setLngLat(pickedCenter);
    }

    // Render pending circle polygon
    const pendingCircle = createGeoJSONCircle(pickedCenter, zoneRadiusKm);
    const featureCollection: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [pendingCircle],
    };

    if (map.getSource("pending-exclusion-zone")) {
      const src = map.getSource("pending-exclusion-zone") as maplibregl.GeoJSONSource;
      if (typeof src.setData === "function") {
        src.setData(featureCollection);
      }
    } else if (map.isStyleLoaded && map.isStyleLoaded()) {
      map.addSource("pending-exclusion-zone", {
        type: "geojson",
        data: featureCollection,
      });

      map.addLayer({
        id: "pending-exclusion-zone-fill",
        type: "fill",
        source: "pending-exclusion-zone",
        paint: {
          "fill-color": "#2563eb",
          "fill-opacity": 0.25,
        },
      });

      map.addLayer({
        id: "pending-exclusion-zone-line",
        type: "line",
        source: "pending-exclusion-zone",
        paint: {
          "line-color": "#1d4ed8",
          "line-width": 2,
        },
      });
    }
  }, [pickedCenter, zoneRadiusKm]);

  const handleSaveZone = async () => {
    if (!pickedCenter) {
      showToast("Please click on the map to set the center of the exclusion zone.", "error");
      return;
    }
    const trimmedName = zoneName.trim();
    if (!trimmedName) {
      showToast("Please enter a name for the exclusion zone (e.g. Home or Office).", "error");
      return;
    }

    setIsSaving(true);
    try {
      const newZone = await exclusionZoneService.createExclusionZone({
        name: trimmedName,
        latitude: pickedCenter[1],
        longitude: pickedCenter[0],
        radius_km: zoneRadiusKm,
      });

      setZones((prev) => [...prev, newZone]);
      setZoneName("");
      setPickedCenter(null);
      showToast(`Created privacy exclusion zone "${newZone.name}"!`, "success");
    } catch (err: any) {
      showToast(err?.message || "Failed to create exclusion zone", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteZone = async (zone: ExclusionZoneItem) => {
    setDeletingId(zone.id);
    try {
      await exclusionZoneService.deleteExclusionZone(zone.id);
      setZones((prev) => prev.filter((z) => z.id !== zone.id));
      showToast(`Deleted exclusion zone "${zone.name}".`, "info");
    } catch (err: any) {
      showToast(err?.message || "Failed to delete exclusion zone", "error");
    } finally {
      setDeletingId(null);
    }
  };

  const handleFlyToZone = (zone: ExclusionZoneItem) => {
    const map = mapInstanceRef.current;
    if (map) {
      map.flyTo({
        center: [zone.longitude, zone.latitude],
        zoom: 13,
      });
    }
  };

  return (
    <div
      data-testid="exclusion-zones-section"
      style={{
        background: "var(--bg-surface, #ffffff)",
        borderRadius: "var(--radius-lg, 16px)",
        border: "1px solid var(--border-color, #e2e8f0)",
        boxShadow: "var(--shadow-sm)",
        padding: "24px",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: "8px",
        }}
      >
        <ShieldAlert size={20} color="#dc2626" />
        <h2 style={{ fontSize: "17px", fontWeight: 700, margin: 0 }}>
          Privacy &amp; Exclusion Zones
        </h2>
      </div>

      <p
        style={{
          fontSize: "13px",
          color: "var(--text-secondary)",
          marginBottom: "16px",
          lineHeight: 1.5,
        }}
      >
        Protect sensitive locations (such as your home, children&apos;s school, or workplace) from being
        inadvertently saved or exported. Any POIs captured manually, clipped via the extension, or imported
        from CSV inside these zones will trigger a confirmation warning or be excluded.
      </p>

      {/* Main Grid: Interactive Map + Configuration Controls */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 340px",
          gap: "16px",
          marginBottom: "16px",
        }}
      >
        {/* Interactive Map */}
        <div
          style={{
            borderRadius: "10px",
            overflow: "hidden",
            border: "1px solid #cbd5e1",
            position: "relative",
            minHeight: "360px",
            backgroundColor: "#e2e8f0",
          }}
        >
          <div
            ref={mapContainerRef}
            data-testid="exclusion-map-container"
            style={{ width: "100%", height: "100%", minHeight: "360px" }}
          />

          <div
            style={{
              position: "absolute",
              top: "10px",
              left: "10px",
              backgroundColor: "rgba(255, 255, 255, 0.95)",
              padding: "4px 8px",
              borderRadius: "6px",
              fontSize: "11px",
              fontWeight: 600,
              color: "#334155",
              boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <Crosshair size={12} color="#dc2626" />
            <span>Click map to place zone center</span>
          </div>
        </div>

        {/* Create / Edit Form Card */}
        <div
          style={{
            backgroundColor: "#f8fafc",
            borderRadius: "10px",
            border: "1px solid #e2e8f0",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ fontWeight: 700, fontSize: "13px", color: "#0f172a" }}>
              Add New Exclusion Zone
            </div>

            {/* Zone Name */}
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "11px",
                  fontWeight: 600,
                  color: "#475569",
                  marginBottom: "4px",
                }}
              >
                Zone Name *
              </label>
              <input
                type="text"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="e.g., Home, Kids' School, Office"
                data-testid="exclusion-zone-name-input"
                style={{
                  width: "100%",
                  padding: "6px 10px",
                  fontSize: "12px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  boxSizing: "border-box",
                }}
              />
            </div>

            {/* Radius Slider */}
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  color: "#475569",
                  marginBottom: "4px",
                }}
              >
                <span style={{ fontWeight: 600 }}>Exclusion Radius</span>
                <span
                  style={{
                    fontWeight: 700,
                    color: "#dc2626",
                    backgroundColor: "#fee2e2",
                    padding: "1px 6px",
                    borderRadius: "4px",
                  }}
                >
                  {zoneRadiusKm.toFixed(1)} km
                </span>
              </div>
              <input
                type="range"
                min="0.2"
                max="25"
                step="0.2"
                value={zoneRadiusKm}
                onChange={(e) => setZoneRadiusKm(parseFloat(e.target.value))}
                data-testid="exclusion-zone-radius-slider"
                style={{ width: "100%", accentColor: "#dc2626", cursor: "pointer" }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "10px",
                  color: "#94a3b8",
                }}
              >
                <span>0.2 km</span>
                <span>12.5 km</span>
                <span>25 km</span>
              </div>
            </div>

            {/* Coordinates Status */}
            <div
              style={{
                padding: "8px 10px",
                backgroundColor: pickedCenter ? "#f0fdf4" : "#fef2f2",
                border: `1px solid ${pickedCenter ? "#bbf7d0" : "#fecaca"}`,
                borderRadius: "6px",
                fontSize: "11px",
              }}
            >
              {pickedCenter ? (
                <div style={{ color: "#166534" }}>
                  <span style={{ fontWeight: 600 }}>Center Coordinates:</span>
                  <div>
                    {pickedCenter[1].toFixed(5)}, {pickedCenter[0].toFixed(5)}
                  </div>
                </div>
              ) : (
                <div style={{ color: "#991b1b" }}>
                  ⚠️ No center selected. Click anywhere on the map to place the exclusion pin.
                </div>
              )}
            </div>
          </div>

          {/* Form Actions */}
          <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
            {pickedCenter && (
              <button
                type="button"
                onClick={() => setPickedCenter(null)}
                style={{
                  padding: "7px 12px",
                  backgroundColor: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            )}
            <button
              type="button"
              onClick={handleSaveZone}
              disabled={isSaving || !pickedCenter || !zoneName.trim()}
              data-testid="save-exclusion-zone-btn"
              style={{
                flex: 1,
                padding: "7px 14px",
                backgroundColor: !pickedCenter || !zoneName.trim() ? "#94a3b8" : "#dc2626",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: !pickedCenter || !zoneName.trim() || isSaving ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "5px",
                boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
              }}
            >
              {isSaving ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Plus size={14} />
                  <span>Save Exclusion Zone</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Saved Exclusion Zones List */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "10px",
          }}
        >
          <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b" }}>
            Configured Privacy Zones ({zones.length})
          </div>
        </div>

        {zones.length === 0 ? (
          <div
            data-testid="no-exclusion-zones"
            style={{
              padding: "16px",
              textAlign: "center",
              backgroundColor: "#f8fafc",
              border: "1px dashed #cbd5e1",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#64748b",
            }}
          >
            No privacy exclusion zones defined. Click on the map above to protect your private locations.
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: "10px",
            }}
            data-testid="exclusion-zones-list"
          >
            {zones.map((zone) => (
              <div
                key={zone.id}
                data-testid={`exclusion-zone-card-${zone.id}`}
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                  backgroundColor: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                }}
              >
                <div
                  onClick={() => handleFlyToZone(zone)}
                  style={{ cursor: "pointer", flex: 1, minWidth: 0 }}
                  title="Click to view on map"
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "2px",
                    }}
                  >
                    <Shield size={14} color="#dc2626" />
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: "13px",
                        color: "#0f172a",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {zone.name}
                    </span>
                  </div>
                  <div style={{ fontSize: "11px", color: "#64748b" }}>
                    Radius: <strong>{zone.radius_km.toFixed(1)} km</strong> •{" "}
                    {zone.latitude.toFixed(4)}, {zone.longitude.toFixed(4)}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleDeleteZone(zone)}
                  disabled={deletingId === zone.id}
                  data-testid={`delete-exclusion-zone-${zone.id}`}
                  title="Delete zone"
                  style={{
                    padding: "6px",
                    backgroundColor: "#fee2e2",
                    border: "1px solid #fecaca",
                    borderRadius: "6px",
                    color: "#dc2626",
                    cursor: deletingId === zone.id ? "not-allowed" : "pointer",
                    marginLeft: "8px",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {deletingId === zone.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

