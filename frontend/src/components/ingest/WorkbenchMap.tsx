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

import React, { useEffect, useRef, useState, useMemo } from "react";
import maplibregl from "maplibre-gl";
import type { LayerConfig, MapLayerId } from "../../types/map";
import { getMapLayers } from "../map/MapLayerSwitcher";
import {
  isInChinaBBox,
  wgs84_to_gcj02,
  gcj02_to_wgs84,
  wgs84_to_bd09,
  bd09_to_wgs84,
} from "../../utils/coordinates";

export interface NearbyPointMarker {
  name: string;
  type: "DB POI" | "Batch Candidate";
  latitude: number;
  longitude: number;
  distanceMiles: number;
}

export interface WorkbenchMapProps {
  latitude: number | null;
  longitude: number | null;
  onChangeLocation: (lat: number, lon: number) => void;
  nearbyPoints?: NearbyPointMarker[];
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

export const WorkbenchMap: React.FC<WorkbenchMapProps> = ({
  latitude,
  longitude,
  onChangeLocation,
  nearbyPoints = [],
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const primaryMarkerRef = useRef<maplibregl.Marker | null>(null);
  const nearbyMarkersRef = useRef<maplibregl.Marker[]>([]);

  const availableLayers = useMemo(() => getMapLayers("local"), []);
  const [activeLayerId, setActiveLayerId] = useState<MapLayerId>("osm");
  const activeLayer = useMemo(
    () =>
      availableLayers.find((l) => l.id === activeLayerId) || availableLayers[0],
    [availableLayers, activeLayerId],
  );
  const activeLayerRef = useRef(activeLayer);
  activeLayerRef.current = activeLayer;

  // Helper to project canonical WGS-84 coordinate to visual map space (shifted if in China and layer is shifted)
  const toDisplayCoords = (lat: number, lon: number): [number, number] => {
    if (isInChinaBBox(lon, lat)) {
      if (activeLayer.id === "amap") {
        const shifted = wgs84_to_gcj02(lon, lat);
        return [shifted.lng, shifted.lat];
      } else if (activeLayer.id === "baidu") {
        const shifted = wgs84_to_bd09(lon, lat);
        return [shifted.lng, shifted.lat];
      }
    }
    return [lon, lat];
  };

  // Helper to convert clicked/dragged visual map space coordinate back to canonical WGS-84
  const toWgs84Coords = (
    dispLat: number,
    dispLon: number,
  ): { lat: number; lon: number } => {
    if (isInChinaBBox(dispLon, dispLat)) {
      const curLayer = activeLayerRef.current;
      if (curLayer.id === "amap") {
        const unshifted = gcj02_to_wgs84(dispLon, dispLat);
        return { lat: unshifted.lat, lon: unshifted.lng };
      } else if (curLayer.id === "baidu") {
        const unshifted = bd09_to_wgs84(dispLon, dispLat);
        return { lat: unshifted.lat, lon: unshifted.lng };
      }
    }
    return { lat: dispLat, lon: dispLon };
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapRef.current) return;

    const defaultLat = latitude != null ? latitude : 20.0;
    const defaultLon = longitude != null ? longitude : 0.0;
    const defaultZoom = latitude != null && longitude != null ? 13 : 2;
    const [initLon, initLat] = toDisplayCoords(defaultLat, defaultLon);

    try {
      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: createRasterStyle(activeLayerRef.current),
        center: [initLon, initLat],
        zoom: defaultZoom,
      });

      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        "top-left",
      );

      // Click to relocate pin
      if (typeof (map as any).on === "function") {
        (map as any).on("click", (e: any) => {
          if (e && e.lngLat) {
            const canonical = toWgs84Coords(e.lngLat.lat, e.lngLat.lng);
            onChangeLocation(canonical.lat, canonical.lon);
          }
        });
      }

      mapRef.current = map;
    } catch (err) {
      console.warn("MapLibre GL failed to initialize in environment:", err);
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update map style when active layer changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.setStyle !== "function") return;
    try {
      if (activeLayer.type === "vector" && activeLayer.styleUrl) {
        map.setStyle(activeLayer.styleUrl);
      } else {
        map.setStyle(createRasterStyle(activeLayer));
      }
    } catch (err) {
      console.warn("Could not set map layer in WorkbenchMap:", err);
    }
  }, [activeLayerId, activeLayer]);

  // Synchronize Primary Marker & Viewport
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (
      latitude != null &&
      longitude != null &&
      !isNaN(latitude) &&
      !isNaN(longitude)
    ) {
      const [dispLon, dispLat] = toDisplayCoords(latitude, longitude);

      if (!primaryMarkerRef.current) {
        // Create draggable marker
        const el = document.createElement("div");
        el.className = "primary-pin";
        el.style.width = "24px";
        el.style.height = "24px";
        el.style.borderRadius = "50%";
        el.style.backgroundColor = "#2563eb";
        el.style.border = "3px solid #ffffff";
        el.style.boxShadow = "0 2px 6px rgba(0,0,0,0.3)";
        el.style.cursor = "grab";

        const marker = new maplibregl.Marker({ element: el, draggable: true })
          .setLngLat([dispLon, dispLat])
          .addTo(map);

        if (typeof (marker as any).on === "function") {
          (marker as any).on("dragend", () => {
            const pos = marker.getLngLat();
            if (pos) {
              const canonical = toWgs84Coords(pos.lat, pos.lng);
              onChangeLocation(canonical.lat, canonical.lon);
            }
          });
        }

        primaryMarkerRef.current = marker;
      } else {
        primaryMarkerRef.current.setLngLat([dispLon, dispLat]);
      }

      map.flyTo({
        center: [dispLon, dispLat],
        zoom: Math.max(map.getZoom(), 12),
      });
    } else {
      if (primaryMarkerRef.current) {
        primaryMarkerRef.current.remove();
        primaryMarkerRef.current = null;
      }
    }
  }, [latitude, longitude, activeLayerId, onChangeLocation]);

  // Synchronize Nearby Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear old nearby markers
    nearbyMarkersRef.current.forEach((m) => m.remove());
    nearbyMarkersRef.current = [];

    nearbyPoints.forEach((pt) => {
      if (
        pt.latitude == null ||
        pt.longitude == null ||
        isNaN(pt.latitude) ||
        isNaN(pt.longitude)
      )
        return;

      const [ptLon, ptLat] = toDisplayCoords(pt.latitude, pt.longitude);

      const el = document.createElement("div");
      el.className = "nearby-pin";
      el.style.width = "14px";
      el.style.height = "14px";
      el.style.borderRadius = "50%";
      el.style.backgroundColor = pt.type === "DB POI" ? "#7c3aed" : "#0284c7";
      el.style.border = "2px solid #ffffff";
      el.style.boxShadow = "0 1px 4px rgba(0,0,0,0.25)";
      el.style.cursor = "pointer";

      const popup = new maplibregl.Popup({ offset: 12 }).setHTML(
        `<strong>${
          pt.name
        }</strong><br/><span style="font-size:11px;color:#64748b;">${
          pt.type
        } (~${
          pt.distanceMiles < 0.1
            ? Math.round(pt.distanceMiles * 5280) + " ft"
            : pt.distanceMiles.toFixed(1) + " mi"
        })</span>`,
      );

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([ptLon, ptLat])
        .setPopup(popup)
        .addTo(map);

      nearbyMarkersRef.current.push(marker);
    });
  }, [nearbyPoints, activeLayerId]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "220px",
        minHeight: "220px",
        borderRadius: "6px",
        overflow: "hidden",
        border: "1px solid #cbd5e1",
        backgroundColor: "#f8fafc",
      }}
      data-testid="workbench-map-wrapper"
    >
      <div
        ref={mapContainerRef}
        data-testid="workbench-map-container"
        style={{ width: "100%", height: "100%" }}
      />

      {/* Map Vendor / Layer Selector */}
      <div
        style={{
          position: "absolute",
          top: "8px",
          right: "8px",
          zIndex: 10,
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderRadius: "4px",
          boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
          padding: "2px 6px",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
        data-testid="workbench-map-layer-selector"
      >
        <span style={{ fontSize: "10px", fontWeight: 700, color: "#64748b" }}>
          Layer:
        </span>
        <select
          value={activeLayerId}
          onChange={(e) => setActiveLayerId(e.target.value as MapLayerId)}
          data-testid="workbench-map-layer-select"
          style={{
            fontSize: "11px",
            border: "none",
            backgroundColor: "transparent",
            color: "#0f172a",
            fontWeight: 600,
            cursor: "pointer",
            outline: "none",
          }}
        >
          {availableLayers.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>

      {latitude == null && (
        <div
          data-testid="map-no-coords-overlay"
          style={{
            position: "absolute",
            bottom: "8px",
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(15, 23, 42, 0.85)",
            color: "#ffffff",
            padding: "4px 10px",
            borderRadius: "14px",
            fontSize: "11px",
            fontWeight: 500,
            pointerEvents: "none",
          }}
        >
          Click map to plot coordinates
        </div>
      )}
    </div>
  );
};
