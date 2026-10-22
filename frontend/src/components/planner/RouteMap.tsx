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

/**
 * RouteMap component (T028, REQ-PLAN-015).
 * Dual-mode interactive route map:
 *  - Macro trip overview: all days fitted to bounding box with day-colored markers and connecting polylines.
 *  - Daily leg mode: zoomed into selected day with numbered sequence pins (1, 2, 3...) and leg paths.
 */

import React, { useEffect, useRef, useState, useMemo } from "react";
import maplibregl from "maplibre-gl";
import { Layers } from "lucide-react";
import type {
  ItineraryResponse,
  ItineraryItemResponse,
} from "../../services/itineraryService";

export interface RouteMapProps {
  itinerary: ItineraryResponse;
  selectedDayId?: string | null;
  onSelectDay?: (dayId: string | null) => void;
  onSelectItem?: (item: ItineraryItemResponse) => void;
}

const DAY_COLORS = [
  "#2563eb", // Day 1: Blue
  "#059669", // Day 2: Emerald
  "#d97706", // Day 3: Amber
  "#7c3aed", // Day 4: Violet
  "#db2777", // Day 5: Pink
  "#0891b2", // Day 6: Cyan
  "#ea580c", // Day 7: Orange
  "#4f46e5", // Day 8: Indigo
];

export const RouteMap: React.FC<RouteMapProps> = ({
  itinerary,
  selectedDayId: controlledSelectedDayId,
  onSelectDay,
  onSelectItem,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const [internalSelectedDayId, setInternalSelectedDayId] = useState<
    string | null
  >(controlledSelectedDayId ?? null);

  const selectedDayId =
    controlledSelectedDayId !== undefined
      ? controlledSelectedDayId
      : internalSelectedDayId;

  const handleDaySelect = (dayId: string | null) => {
    setInternalSelectedDayId(dayId);
    if (onSelectDay) {
      onSelectDay(dayId);
    }
  };

  // Collect all items with valid coordinates
  const days = useMemo(() => itinerary.days ?? [], [itinerary.days]);

  const activeDay = useMemo(() => {
    if (!selectedDayId) return null;
    return days.find((d) => d.id === selectedDayId) ?? null;
  }, [days, selectedDayId]);

  // Points to render on current view
  const activeItems = useMemo(() => {
    if (activeDay) {
      return (activeDay.items ?? [])
        .filter(
          (it) =>
            typeof (it.latitude ?? (it as any).lat) === "number" &&
            typeof (it.longitude ?? (it as any).lng) === "number",
        )
        .sort((a, b) => a.order_index - b.order_index);
    }
    // Macro mode: collect all items across all days
    const allItems: { item: ItineraryItemResponse; dayIndex: number }[] = [];
    days.forEach((day, dIdx) => {
      (day.items ?? [])
        .filter(
          (it) =>
            typeof (it.latitude ?? (it as any).lat) === "number" &&
            typeof (it.longitude ?? (it as any).lng) === "number",
        )
        .sort((a, b) => a.order_index - b.order_index)
        .forEach((it) => {
          allItems.push({ item: it, dayIndex: dIdx });
        });
    });
    return allItems;
  }, [activeDay, days]);

  // Initialize MapLibre Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapRef.current) return;

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
        center: [-122.3321, 47.6062], // Default Pacific NW
        zoom: 9,
      });

      map.addControl(new maplibregl.NavigationControl(), "top-left");
      mapRef.current = map;
    } catch (err) {
      console.warn("MapLibre GL failed to initialize:", err);
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update markers, route polylines, and camera bounds
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // Helper to add GeoJSON line source/layer
    const updateRouteLine = (
      coordinates: [number, number][],
      color: string,
    ) => {
      const sourceId = "itinerary-route-source";
      const layerId = "itinerary-route-layer";

      if (map.getSource(sourceId)) {
        (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData({
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates,
          },
        });
      } else if (map.isStyleLoaded()) {
        map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates,
            },
          },
        });

        map.addLayer({
          id: layerId,
          type: "line",
          source: sourceId,
          layout: {
            "line-join": "round",
            "line-cap": "round",
          },
          paint: {
            "line-color": color,
            "line-width": 3,
            "line-opacity": 0.8,
            "line-dasharray": [2, 2],
          },
        });
      }
    };

    const isDailyMode = activeDay !== null;
    const coordinates: [number, number][] = [];

    if (isDailyMode) {
      // Daily leg mode: numbered sequence pins (1, 2, 3...)
      const items = activeItems as ItineraryItemResponse[];
      const dayColor =
        DAY_COLORS[
          days.findIndex((d) => d.id === activeDay.id) % DAY_COLORS.length
        ];

      items.forEach((item, idx) => {
        const lng = item.longitude ?? (item as any).lng;
        const lat = item.latitude ?? (item as any).lat;
        coordinates.push([lng, lat]);

        const el = document.createElement("div");
        el.className = "itinerary-marker-pin";
        el.setAttribute("data-testid", `map-marker-${item.id}`);
        el.style.width = "28px";
        el.style.height = "28px";
        el.style.borderRadius = "50%";
        el.style.backgroundColor = dayColor;
        el.style.color = "#ffffff";
        el.style.display = "flex";
        el.style.alignItems = "center";
        el.style.justifyContent = "center";
        el.style.fontSize = "12px";
        el.style.fontWeight = "bold";
        el.style.boxShadow = "0 2px 6px rgba(0,0,0,0.3)";
        el.style.border = "2px solid #ffffff";
        el.style.cursor = "pointer";
        el.innerText = `${idx + 1}`;

        el.onclick = () => {
          if (onSelectItem) onSelectItem(item);
        };

        const timeStr =
          item.start_time && item.end_time
            ? `${item.start_time.slice(0, 5)} - ${item.end_time.slice(0, 5)}`
            : "";

        const transitInfo = item.travel_time_prev_minutes
          ? `<div style="color: #2563eb; font-size: 11px; margin-top: 4px;">
              Transit: ${item.travel_time_prev_minutes}m (${
                item.travel_distance_prev_meters
                  ? (item.travel_distance_prev_meters / 1000).toFixed(1) + "km"
                  : ""
              })
            </div>`
          : "";

        const popup = new maplibregl.Popup({ offset: 15 }).setHTML(`
          <div style="font-family: inherit; font-size: 13px; padding: 4px;">
            <div style="font-weight: 700; color: #0f172a;">${idx + 1}. ${
              item.title
            }</div>
            ${
              timeStr
                ? `<div style="color: #64748b; font-size: 11px; margin-top: 2px;">${timeStr}</div>`
                : ""
            }
            ${transitInfo}
          </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([lng, lat])
          .setPopup(popup)
          .addTo(map);

        markersRef.current.push(marker);
      });

      if (map.isStyleLoaded()) {
        updateRouteLine(coordinates, dayColor);
      }
    } else {
      // Macro mode: color-coded day markers and overall connecting route
      const itemsWithDay = activeItems as {
        item: ItineraryItemResponse;
        dayIndex: number;
      }[];

      itemsWithDay.forEach(({ item, dayIndex }) => {
        const lng = item.longitude ?? (item as any).lng;
        const lat = item.latitude ?? (item as any).lat;
        coordinates.push([lng, lat]);
        const dayColor = DAY_COLORS[dayIndex % DAY_COLORS.length];

        const el = document.createElement("div");
        el.className = "itinerary-marker-pin-macro";
        el.setAttribute("data-testid", `map-marker-macro-${item.id}`);
        el.style.width = "22px";
        el.style.height = "22px";
        el.style.borderRadius = "50%";
        el.style.backgroundColor = dayColor;
        el.style.color = "#ffffff";
        el.style.display = "flex";
        el.style.alignItems = "center";
        el.style.justifyContent = "center";
        el.style.fontSize = "10px";
        el.style.fontWeight = "bold";
        el.style.boxShadow = "0 2px 4px rgba(0,0,0,0.25)";
        el.style.border = "2px solid #ffffff";
        el.style.cursor = "pointer";
        el.innerText = `D${dayIndex + 1}`;

        el.onclick = () => {
          if (onSelectItem) onSelectItem(item);
        };

        const timeStr =
          item.start_time && item.end_time
            ? `${item.start_time.slice(0, 5)} - ${item.end_time.slice(0, 5)}`
            : "";

        const popup = new maplibregl.Popup({ offset: 12 }).setHTML(`
          <div style="font-family: inherit; font-size: 13px; padding: 4px;">
            <div style="font-weight: 700; color: #0f172a;">Day ${
              dayIndex + 1
            }: ${item.title}</div>
            ${
              timeStr
                ? `<div style="color: #64748b; font-size: 11px; margin-top: 2px;">${timeStr}</div>`
                : ""
            }
          </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([lng, lat])
          .setPopup(popup)
          .addTo(map);

        markersRef.current.push(marker);
      });

      if (map.isStyleLoaded()) {
        updateRouteLine(coordinates, "#3b82f6");
      }
    }

    // Auto-fit bounds if we have waypoints
    if (coordinates.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      coordinates.forEach((coord) => bounds.extend(coord));
      try {
        map.fitBounds(bounds, {
          padding: 50,
          maxZoom: 14,
          duration: 600,
        });
      } catch {
        // Safe catch for zero-dimension bounds in tests
      }
    }
  }, [activeDay, activeItems, days, onSelectItem]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: "100%",
        position: "relative",
        background: "var(--bg-surface, #ffffff)",
        borderRadius: "var(--radius-lg, 12px)",
        overflow: "hidden",
        border: "1px solid var(--border-color, #e2e8f0)",
      }}
    >
      {/* Route Filter Navigation Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 16px",
          background: "var(--bg-surface, #ffffff)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          zIndex: 10,
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Layers size={16} color="var(--accent, #2563eb)" />
          <span
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: "var(--text-primary, #0f172a)",
            }}
          >
            Route Navigator
          </span>
        </div>

        {/* Day selection tabs */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            flexWrap: "wrap",
          }}
        >
          <button
            type="button"
            data-testid="route-filter-all"
            onClick={() => handleDaySelect(null)}
            style={{
              padding: "5px 12px",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              border: "1px solid",
              borderColor:
                selectedDayId === null
                  ? "var(--accent, #2563eb)"
                  : "var(--border-color, #e2e8f0)",
              background:
                selectedDayId === null
                  ? "var(--accent-light, #eff6ff)"
                  : "transparent",
              color:
                selectedDayId === null
                  ? "var(--accent, #2563eb)"
                  : "var(--text-secondary, #475569)",
            }}
          >
            All Days (Macro)
          </button>

          {days.map((day, idx) => {
            const isSelected = selectedDayId === day.id;
            const dayColor = DAY_COLORS[idx % DAY_COLORS.length];
            return (
              <button
                key={day.id}
                type="button"
                data-testid={`route-filter-day-${idx + 1}`}
                onClick={() => handleDaySelect(day.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "5px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "1px solid",
                  borderColor: isSelected
                    ? dayColor
                    : "var(--border-color, #e2e8f0)",
                  background: isSelected ? `${dayColor}18` : "transparent",
                  color: isSelected
                    ? dayColor
                    : "var(--text-secondary, #475569)",
                }}
              >
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    backgroundColor: dayColor,
                  }}
                />
                <span>Day {idx + 1}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Map Canvas Container */}
      <div
        ref={mapContainerRef}
        data-testid="route-map-container"
        style={{
          flex: 1,
          width: "100%",
          minHeight: "360px",
          position: "relative",
        }}
      />
    </div>
  );
};
