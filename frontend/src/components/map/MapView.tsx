// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type { BoundingBox, MapLayerId, POIMapFeature } from "../../types/map";
import {
  createSuperclusterIndex,
  getClustersForViewport,
  filterPOIsByViewport,
} from "../../services/clustering";
import {
  isInChinaBBox,
  gcj02_to_wgs84,
  bd09_to_wgs84,
} from "../../utils/coordinates";
import { MapLayerSwitcher, MAP_LAYERS } from "./MapLayerSwitcher";

export interface MapViewProps {
  pois: POIMapFeature[];
  totalPoiCount: number;
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  activeLayer?: MapLayerId;
  defaultLayer?: MapLayerId;
  selectedPoiId?: string | null;
  isPinDropMode?: boolean;
  onLayerChange?: (layer: MapLayerId) => void;
  onSaveDefaultLayer?: (layer: MapLayerId) => void;
  onPOIClick?: (poi: POIMapFeature) => void;
  onPinDrop?: (coords: { lng: number; lat: number }) => void;
  onViewportChange?: (bbox: BoundingBox, visiblePois: POIMapFeature[]) => void;
  onFetchServerViewport?: (
    bbox: BoundingBox,
    signal: AbortSignal,
  ) => Promise<void>;
}

export const MapView: React.FC<MapViewProps> = ({
  pois,
  totalPoiCount,
  initialCenter = [116.397458, 39.909187], // Default Beijing center
  initialZoom = 10,
  activeLayer: controlledLayer = "osm",
  defaultLayer = "osm",
  selectedPoiId,
  isPinDropMode = false,
  onLayerChange,
  onSaveDefaultLayer,
  onPOIClick,
  onPinDrop,
  onViewportChange,
  onFetchServerViewport,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [sessionLayer, setSessionLayer] = useState<MapLayerId>(controlledLayer);

  // Sync internal layer state if parent changes controlled layer
  useEffect(() => {
    setSessionLayer(controlledLayer);
  }, [controlledLayer]);

  // Extract current map bounding box
  const getMapBBox = useCallback((map: maplibregl.Map): BoundingBox => {
    const bounds = map.getBounds();
    return {
      minLng: bounds.getWest(),
      minLat: bounds.getSouth(),
      maxLng: bounds.getEast(),
      maxLat: bounds.getNorth(),
    };
  }, []);

  // Update in-memory GeoJSON cluster data
  const updateGeoJSONSource = useCallback(
    (map: maplibregl.Map, layer: MapLayerId) => {
      const source = map.getSource("pois") as
        maplibregl.GeoJSONSource | undefined;
      if (!source) return;

      const bbox = getMapBBox(map);
      const zoom = map.getZoom();

      // Client-side Supercluster (< 1,000 POIs)
      if (totalPoiCount < 1000) {
        const index = createSuperclusterIndex(pois, layer);
        const clusterGeoJSON = getClustersForViewport(index, bbox, zoom);
        source.setData(clusterGeoJSON);

        // Notify parent of visible POIs in current viewport
        if (onViewportChange) {
          const visible = filterPOIsByViewport(pois, bbox);
          onViewportChange(bbox, visible);
        }
      }
    },
    [pois, totalPoiCount, getMapBBox, onViewportChange],
  );

  // Handle layer switching without page reload or full map recreation
  const handleLayerSelect = useCallback(
    (newLayerId: MapLayerId) => {
      setSessionLayer(newLayerId);
      if (onLayerChange) {
        onLayerChange(newLayerId);
      }

      const map = mapRef.current;
      if (!map) return;

      const targetLayer =
        MAP_LAYERS.find((l) => l.id === newLayerId) || MAP_LAYERS[0];
      const rasterSource = map.getSource("raster-tiles") as
        maplibregl.RasterTileSource | undefined;

      if (rasterSource && "setTiles" in rasterSource) {
        // MapLibre raster setTiles
        (
          rasterSource as unknown as { setTiles: (tiles: string[]) => void }
        ).setTiles(targetLayer.tiles);
      }

      // Re-project markers in memory for the active layer
      updateGeoJSONSource(map, newLayerId);
    },
    [onLayerChange, updateGeoJSONSource],
  );

  // Map initialization
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const initialLayerConfig =
      MAP_LAYERS.find((l) => l.id === sessionLayer) || MAP_LAYERS[0];

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          "raster-tiles": {
            type: "raster",
            tiles: initialLayerConfig.tiles,
            tileSize: 256,
            attribution: initialLayerConfig.attribution,
          },
        },
        layers: [
          {
            id: "raster-layer",
            type: "raster",
            source: "raster-tiles",
            minzoom: 0,
            maxzoom: initialLayerConfig.maxZoom,
          },
        ],
      },
      center: initialCenter,
      zoom: initialZoom,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-left");

    map.on("load", () => {
      // Add GeoJSON POI source with cluster configuration
      map.addSource("pois", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      // Cluster circles layer
      map.addLayer({
        id: "clusters",
        type: "circle",
        source: "pois",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "point_count"],
            "#3b82f6", // blue
            10,
            "#10b981", // green
            30,
            "#f59e0b", // amber
          ],
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 24, 30, 30],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Cluster count labels
      map.addLayer({
        id: "cluster-count",
        type: "symbol",
        source: "pois",
        filter: ["has", "point_count"],
        layout: {
          "text-field": "{point_count_abbreviated}",
          "text-size": 12,
        },
        paint: {
          "text-color": "#ffffff",
        },
      });

      // Individual unclustered POI pins
      map.addLayer({
        id: "unclustered-point",
        type: "circle",
        source: "pois",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "match",
            ["get", "visit_state"],
            "visited_return",
            "#10b981", // Emerald green
            "visited_do_not_return",
            "#f59e0b", // Amber
            /* 'not_visited' or default */
            "#2563eb", // Royal blue
          ],
          "circle-radius": 8,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Populate initial GeoJSON data
      updateGeoJSONSource(map, sessionLayer);
    });

    // Handle pin drop with reverse Newton numerical iteration
    map.on("click", (e) => {
      if (isPinDropMode && onPinDrop) {
        let { lng, lat } = e.lngLat;

        // If active layer is shifted within China bbox, invert to canonical WGS-84
        if (isInChinaBBox(lng, lat)) {
          if (sessionLayer === "amap") {
            const canonical = gcj02_to_wgs84(lng, lat);
            lng = canonical.lng;
            lat = canonical.lat;
          } else if (sessionLayer === "baidu") {
            const canonical = bd09_to_wgs84(lng, lat);
            lng = canonical.lng;
            lat = canonical.lat;
          }
        }

        onPinDrop({ lng, lat });
        return;
      }

      // Check if click was on an unclustered POI pin
      const features = map.queryRenderedFeatures(e.point, {
        layers: ["unclustered-point"],
      });

      if (features.length > 0 && onPOIClick) {
        const poiData = features[0].properties as POIMapFeature;
        onPOIClick(poiData);
      }
    });

    // Expand cluster on click
    map.on("click", "clusters", (e) => {
      const features = map.queryRenderedFeatures(e.point, {
        layers: ["clusters"],
      });
      if (!features.length) return;

      const point = features[0].geometry as GeoJSON.Point;

      map.easeTo({
        center: point.coordinates as [number, number],
        zoom: map.getZoom() + 2,
      });
    });

    // Cursor pointer style on markers
    map.on("mouseenter", "clusters", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "clusters", () => {
      map.getCanvas().style.cursor = "";
    });
    map.on("mouseenter", "unclustered-point", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "unclustered-point", () => {
      map.getCanvas().style.cursor = "";
    });

    // Viewport motion debouncing logic
    const handleMoveStart = () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
    };

    const handleMoveEnd = () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // 300ms Debounce interval
      debounceTimerRef.current = setTimeout(() => {
        const currentMap = mapRef.current;
        if (!currentMap) return;

        // If dataset < 1,000, update in-memory Supercluster
        if (totalPoiCount < 1000) {
          updateGeoJSONSource(currentMap, sessionLayer);
        } else if (onFetchServerViewport) {
          // If dataset >= 1,000, abort previous in-flight request and fetch from backend
          if (abortControllerRef.current) {
            abortControllerRef.current.abort();
          }

          const controller = new AbortController();
          abortControllerRef.current = controller;

          const bbox = getMapBBox(currentMap);
          onFetchServerViewport(bbox, controller.signal).catch((err) => {
            if (err.name !== "AbortError") {
              console.error("Failed to query server viewport:", err);
            }
          });
        }
      }, 300);
    };

    map.on("movestart", handleMoveStart);
    map.on("moveend", handleMoveEnd);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      map.remove();
    };
  }, []); // Run once on mount

  // Update GeoJSON when POIs or total count change
  useEffect(() => {
    const map = mapRef.current;
    if (map && map.isStyleLoaded()) {
      updateGeoJSONSource(map, sessionLayer);
    }
  }, [pois, totalPoiCount, sessionLayer, updateGeoJSONSource]);

  // Center on selected POI when selection changes
  useEffect(() => {
    if (!selectedPoiId || !mapRef.current) return;
    const targetPOI = pois.find((p) => p.id === selectedPoiId);
    if (targetPOI) {
      mapRef.current.flyTo({
        center: [targetPOI.canonical_lng, targetPOI.canonical_lat],
        zoom: Math.max(mapRef.current.getZoom(), 14),
        essential: true,
      });
    }
  }, [selectedPoiId, pois]);

  return (
    <div
      className="map-view-wrapper"
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "400px",
        borderRadius: "var(--radius-md, 10px)",
        overflow: "hidden",
      }}
    >
      <div
        ref={mapContainerRef}
        className="map-canvas-container"
        style={{ width: "100%", height: "100%" }}
      />

      <div
        className="map-controls-overlay"
        style={{
          position: "absolute",
          top: "12px",
          right: "12px",
          zIndex: 10,
        }}
      >
        <MapLayerSwitcher
          activeLayer={sessionLayer}
          defaultLayer={defaultLayer}
          onLayerChange={handleLayerSelect}
          onSaveAsDefault={onSaveDefaultLayer}
        />
      </div>

      {isPinDropMode && (
        <div
          className="pin-drop-banner fade-in"
          style={{
            position: "absolute",
            bottom: "20px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--accent, #2563eb)",
            color: "#ffffff",
            padding: "8px 16px",
            borderRadius: "var(--radius-full, 9999px)",
            boxShadow: "var(--shadow-lg)",
            fontWeight: 600,
            fontSize: "13px",
            pointerEvents: "none",
            zIndex: 10,
          }}
        >
          📍 Click anywhere on the map to set location pin
        </div>
      )}
    </div>
  );
};
