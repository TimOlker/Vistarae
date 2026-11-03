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

import React, { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";

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

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapRef.current) return;

    const defaultLat = latitude != null ? latitude : 20.0;
    const defaultLon = longitude != null ? longitude : 0.0;
    const defaultZoom = latitude != null && longitude != null ? 13 : 2;

    try {
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
        center: [defaultLon, defaultLat],
        zoom: defaultZoom,
      });

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

      // Click to relocate pin
      if (typeof (map as any).on === "function") {
        (map as any).on("click", (e: any) => {
          if (e && e.lngLat) {
            onChangeLocation(e.lngLat.lat, e.lngLat.lng);
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

  // Synchronize Primary Marker & Viewport
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (latitude != null && longitude != null && !isNaN(latitude) && !isNaN(longitude)) {
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
          .setLngLat([longitude, latitude])
          .addTo(map);

        if (typeof (marker as any).on === "function") {
          (marker as any).on("dragend", () => {
            const pos = marker.getLngLat();
            if (pos) onChangeLocation(pos.lat, pos.lng);
          });
        }

        primaryMarkerRef.current = marker;
      } else {
        primaryMarkerRef.current.setLngLat([longitude, latitude]);
      }

      map.flyTo({ center: [longitude, latitude], zoom: Math.max(map.getZoom(), 12) });
    } else {
      if (primaryMarkerRef.current) {
        primaryMarkerRef.current.remove();
        primaryMarkerRef.current = null;
      }
    }
  }, [latitude, longitude, onChangeLocation]);

  // Synchronize Nearby Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear old nearby markers
    nearbyMarkersRef.current.forEach((m) => m.remove());
    nearbyMarkersRef.current = [];

    nearbyPoints.forEach((pt) => {
      if (pt.latitude == null || pt.longitude == null || isNaN(pt.latitude) || isNaN(pt.longitude)) return;

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
        `<strong>${pt.name}</strong><br/><span style="font-size:11px;color:#64748b;">${pt.type} (~${pt.distanceMiles < 0.1 ? Math.round(pt.distanceMiles * 5280) + ' ft' : pt.distanceMiles.toFixed(1) + ' mi'})</span>`
      );

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([pt.longitude, pt.latitude])
        .setPopup(popup)
        .addTo(map);

      nearbyMarkersRef.current.push(marker);
    });
  }, [nearbyPoints]);

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
