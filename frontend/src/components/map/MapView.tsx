// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type {
  BoundingBox,
  MapLayerId,
  POIMapFeature,
  LayerConfig,
} from "../../types/map";
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
import { MapLayerSwitcher, getMapLayers } from "./MapLayerSwitcher";

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

export interface MapViewProps {
  pois: POIMapFeature[];
  totalPoiCount: number;
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  activeLayer?: MapLayerId;
  defaultLayer?: MapLayerId;
  mapLanguage?: string;
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
  mapLanguage = "local",
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
  const sessionLayerRef = useRef<MapLayerId>(controlledLayer);

  // Sync internal layer state if parent changes controlled layer
  useEffect(() => {
    setSessionLayer(controlledLayer);
    sessionLayerRef.current = controlledLayer;
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
      if (!map || !map.isStyleLoaded()) return;
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

  // Ensure POI source and cluster layers are present (e.g. after style reload)
  const ensurePOILayers = useCallback(
    (mapInstance: maplibregl.Map, currentLayer: MapLayerId) => {
      if (!mapInstance || !mapInstance.isStyleLoaded()) return;

      if (!mapInstance.getSource("pois")) {
        mapInstance.addSource("pois", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }

      if (!mapInstance.getLayer?.("clusters")) {
        mapInstance.addLayer({
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
            "circle-radius": [
              "step",
              ["get", "point_count"],
              18,
              10,
              24,
              30,
              30,
            ],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
      }

      if (!mapInstance.getLayer?.("cluster-count")) {
        mapInstance.addLayer({
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
      }

      if (!mapInstance.getLayer?.("unclustered-point")) {
        mapInstance.addLayer({
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
      }

      updateGeoJSONSource(mapInstance, currentLayer);
    },
    [updateGeoJSONSource],
  );

  // Handle layer switching without page reload or full map recreation
  const handleLayerSelect = useCallback(
    (newLayerId: MapLayerId) => {
      setSessionLayer(newLayerId);
      sessionLayerRef.current = newLayerId;
      if (onLayerChange) {
        onLayerChange(newLayerId);
      }

      const map = mapRef.current;
      if (!map) return;

      const layers = getMapLayers(mapLanguage);
      const targetLayer = layers.find((l) => l.id === newLayerId) || layers[0];

      if (targetLayer.type === "vector" && targetLayer.styleUrl) {
        map.setStyle(targetLayer.styleUrl);
      } else {
        const rasterSource = map.isStyleLoaded()
          ? (map.getSource("raster-tiles") as
              maplibregl.RasterTileSource | undefined)
          : undefined;

        if (rasterSource && "setTiles" in rasterSource) {
          (
            rasterSource as unknown as { setTiles: (tiles: string[]) => void }
          ).setTiles(targetLayer.tiles);
          updateGeoJSONSource(map, newLayerId);
        } else {
          map.setStyle(createRasterStyle(targetLayer));
        }
      }
    },
    [onLayerChange, updateGeoJSONSource, mapLanguage],
  );

  // Dynamically update raster tiles when mapLanguage or sessionLayer changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const layers = getMapLayers(mapLanguage);
    const targetLayer = layers.find((l) => l.id === sessionLayer) || layers[0];
    if (targetLayer.type === "vector" || !targetLayer.tiles?.length) return;

    const rasterSource = map.getSource("raster-tiles") as
      maplibregl.RasterTileSource | undefined;

    if (rasterSource && "setTiles" in rasterSource) {
      (
        rasterSource as unknown as { setTiles: (tiles: string[]) => void }
      ).setTiles(targetLayer.tiles);
    }
  }, [mapLanguage, sessionLayer]);

  // Map initialization
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const layers = getMapLayers(mapLanguage);
    const initialLayerConfig =
      layers.find((l) => l.id === sessionLayer) || layers[0];

    const initialStyle: string | maplibregl.StyleSpecification =
      initialLayerConfig.type === "vector" && initialLayerConfig.styleUrl
        ? initialLayerConfig.styleUrl
        : createRasterStyle(initialLayerConfig);

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: initialStyle,
      center: initialCenter,
      zoom: initialZoom,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-left");

    map.on("load", () => {
      ensurePOILayers(map, sessionLayerRef.current);
    });

    map.on("styledata", () => {
      ensurePOILayers(map, sessionLayerRef.current);
    });

    // Handle pin drop with reverse Newton numerical iteration
    map.on("click", (e) => {
      if (isPinDropMode && onPinDrop) {
        let { lng, lat } = e.lngLat;

        // If active layer is shifted within China bbox, invert to canonical WGS-84
        if (isInChinaBBox(lng, lat)) {
          if (sessionLayerRef.current === "amap") {
            const canonical = gcj02_to_wgs84(lng, lat);
            lng = canonical.lng;
            lat = canonical.lat;
          } else if (sessionLayerRef.current === "baidu") {
            const canonical = bd09_to_wgs84(lng, lat);
            lng = canonical.lng;
            lat = canonical.lat;
          }
        }

        onPinDrop({ lng, lat });
        return;
      }

      if (!map.isStyleLoaded()) return;

      // Expand cluster on click
      if (map.getLayer?.("clusters")) {
        const clusterFeatures = map.queryRenderedFeatures(e.point, {
          layers: ["clusters"],
        });
        if (clusterFeatures.length > 0) {
          const point = clusterFeatures[0].geometry as GeoJSON.Point;
          map.easeTo({
            center: point.coordinates as [number, number],
            zoom: map.getZoom() + 2,
          });
          return;
        }
      }

      // Check if click was on an unclustered POI pin
      if (map.getLayer?.("unclustered-point")) {
        const features = map.queryRenderedFeatures(e.point, {
          layers: ["unclustered-point"],
        });

        if (features.length > 0 && onPOIClick) {
          const poiData = features[0].properties as POIMapFeature;
          onPOIClick(poiData);
        }
      }
    });

    // Cursor pointer style on hover
    map.on("mousemove", (e) => {
      if (!map.isStyleLoaded()) return;
      const queryLayers = ["clusters", "unclustered-point"].filter((l) =>
        Boolean(map.getLayer?.(l)),
      );
      if (!queryLayers.length) return;
      const features = map.queryRenderedFeatures(e.point, {
        layers: queryLayers,
      });
      map.getCanvas().style.cursor = features.length > 0 ? "pointer" : "";
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
          language={mapLanguage}
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
