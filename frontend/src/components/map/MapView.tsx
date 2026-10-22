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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import type Supercluster from "supercluster";
import { X } from "lucide-react";
import type {
  BoundingBox,
  MapLayerId,
  POIMapFeature,
  LayerConfig,
} from "../../types/map";
import type { LayoutMode } from "../../types/layout";
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
import { POIPopupCard } from "./POIPopupCard";

function createRasterStyle(
  layerConfig: LayerConfig,
): maplibregl.StyleSpecification {
  return {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
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
  layoutMode?: LayoutMode;
  onLayerChange?: (layer: MapLayerId) => void;
  onSaveDefaultLayer?: (layer: MapLayerId) => void;
  onPOIClick?: (poi: POIMapFeature) => void;
  onEditPOI?: (poi: POIMapFeature) => void;
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
  layoutMode = "split",
  onLayerChange,
  onSaveDefaultLayer,
  onPOIClick,
  onEditPOI,
  onPinDrop,
  onViewportChange,
  onFetchServerViewport,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const superclusterIndexRef = useRef<Supercluster<
    POIMapFeature,
    Supercluster.AnyProps
  > | null>(null);
  const poisRef = useRef<POIMapFeature[]>(pois);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [sessionLayer, setSessionLayer] = useState<MapLayerId>(controlledLayer);
  const sessionLayerRef = useRef<MapLayerId>(controlledLayer);

  // User Story 4: Active popup POI and co-located disambiguation
  const [activePopupPoi, setActivePopupPoi] = useState<POIMapFeature | null>(
    null,
  );
  const [activePopupCoords, setActivePopupCoords] = useState<
    [number, number] | null
  >(null);
  const [popupPixel, setPopupPixel] = useState<{ x: number; y: number } | null>(
    null,
  );

  const [colocatedPois, setColocatedPois] = useState<POIMapFeature[] | null>(
    null,
  );
  const [colocatedCoords, setColocatedCoords] = useState<
    [number, number] | null
  >(null);
  const [colocatedPixel, setColocatedPixel] = useState<{
    x: number;
    y: number;
  } | null>(null);

  const activePopupCoordsRef = useRef<[number, number] | null>(null);
  const colocatedCoordsRef = useRef<[number, number] | null>(null);

  useEffect(() => {
    poisRef.current = pois;
  }, [pois]);

  useEffect(() => {
    activePopupCoordsRef.current = activePopupCoords;
    if (activePopupCoords && mapRef.current?.project) {
      setPopupPixel(mapRef.current.project(activePopupCoords));
    } else if (!activePopupCoords) {
      setPopupPixel(null);
    }
  }, [activePopupCoords]);

  useEffect(() => {
    colocatedCoordsRef.current = colocatedCoords;
    if (colocatedCoords && mapRef.current?.project) {
      setColocatedPixel(mapRef.current.project(colocatedCoords));
    } else if (!colocatedCoords) {
      setColocatedPixel(null);
    }
  }, [colocatedCoords]);

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
        | maplibregl.GeoJSONSource
        | undefined;
      if (!source) return;

      const bbox = getMapBBox(map);
      const zoom = map.getZoom();

      // Client-side Supercluster (< 1,000 POIs)
      if (totalPoiCount < 1000) {
        const index = createSuperclusterIndex(pois, layer);
        superclusterIndexRef.current = index;
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
        try {
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
        } catch (err) {
          console.warn("Could not register cluster-count text layer:", err);
        }
      }

      if (!mapInstance.getLayer?.("unclustered-point")) {
        mapInstance.addLayer({
          id: "unclustered-point",
          type: "circle",
          source: "pois",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": [
              "coalesce",
              ["get", "pin_color"],
              [
                "match",
                ["get", "visit_state"],
                "visited_return",
                "#10b981", // Emerald green
                "visited_do_not_return",
                "#f59e0b", // Amber
                /* 'not_visited' or default */
                "#2563eb", // Royal blue
              ],
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
              | maplibregl.RasterTileSource
              | undefined)
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
      | maplibregl.RasterTileSource
      | undefined;

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

      // Expand cluster on click with 300ms easing and co-located detection
      if (map.getLayer?.("clusters")) {
        const clusterFeatures = map.queryRenderedFeatures(e.point, {
          layers: ["clusters"],
        });
        if (clusterFeatures.length > 0) {
          const clusterId = clusterFeatures[0].properties?.cluster_id;
          const index = superclusterIndexRef.current;

          if (index && clusterId !== undefined) {
            let leaves: Array<GeoJSON.Feature<GeoJSON.Point, POIMapFeature>> =
              [];
            try {
              leaves = index.getLeaves(clusterId, Infinity);
            } catch (err) {
              console.warn("Could not query cluster leaves:", err);
            }

            if (leaves && leaves.length > 0) {
              const coords = leaves.map(
                (l) => (l.geometry as GeoJSON.Point).coordinates,
              );
              const firstLng = coords[0][0];
              const firstLat = coords[0][1];
              const isAllCoLocated = coords.every(
                ([lng, lat]) =>
                  Math.abs(lng - firstLng) < 1e-6 &&
                  Math.abs(lat - firstLat) < 1e-6,
              );

              // REQ-MAIN-037: At max zoom (z >= 19.5) or if all child POIs are co-located
              if (map.getZoom() >= 19.5 || isAllCoLocated) {
                const childPois = leaves.map(
                  (l) => l.properties as POIMapFeature,
                );
                setColocatedPois(childPois);
                setColocatedCoords([firstLng, firstLat]);
                if (map.project) {
                  setColocatedPixel(map.project([firstLng, firstLat]));
                }
                setActivePopupPoi(null);
                setActivePopupCoords(null);
                setPopupPixel(null);
                return;
              }

              // REQ-MAIN-036 / SC-005: Compute bounding box and ease camera in 300ms
              let minLng = Infinity;
              let minLat = Infinity;
              let maxLng = -Infinity;
              let maxLat = -Infinity;

              for (const [lng, lat] of coords) {
                if (lng < minLng) minLng = lng;
                if (lat < minLat) minLat = lat;
                if (lng > maxLng) maxLng = lng;
                if (lat > maxLat) maxLat = lat;
              }

              map.fitBounds(
                [
                  [minLng, minLat],
                  [maxLng, maxLat],
                ],
                { padding: 60, maxZoom: 18, duration: 300 },
              );
              return;
            }
          }

          // Fallback if index not ready
          const point = clusterFeatures[0].geometry as GeoJSON.Point;
          map.easeTo({
            center: point.coordinates as [number, number],
            zoom: map.getZoom() + 2,
            duration: 300,
          });
          return;
        }
      }

      // Check if click was on an unclustered POI pin
      if (map.getLayer?.("unclustered-point")) {
        const features = map.queryRenderedFeatures(e.point, {
          layers: ["unclustered-point"],
        });

        if (features.length > 0) {
          const rawPoi = features[0].properties as POIMapFeature;
          // Look up full POI from poisRef to preserve complex objects
          const fullPoi =
            poisRef.current.find((p) => p.id === rawPoi.id) || rawPoi;

          const pointGeom = features[0].geometry as GeoJSON.Point;
          const pinCoords: [number, number] = pointGeom?.coordinates
            ? [pointGeom.coordinates[0], pointGeom.coordinates[1]]
            : [
                fullPoi.render_lng ?? fullPoi.canonical_lng,
                fullPoi.render_lat ?? fullPoi.canonical_lat,
              ];

          setActivePopupPoi(fullPoi);
          setActivePopupCoords(pinCoords);
          if (map.project) {
            setPopupPixel(map.project(pinCoords));
          }
          setColocatedPois(null);
          setColocatedCoords(null);
          setColocatedPixel(null);

          if (onPOIClick) {
            onPOIClick(fullPoi);
          }
          return;
        }
      }

      // Clicking background closes open popups
      setActivePopupPoi(null);
      setActivePopupCoords(null);
      setPopupPixel(null);
      setColocatedPois(null);
      setColocatedCoords(null);
      setColocatedPixel(null);
    });

    // Handle map move to keep overlays anchored
    const handleMapMove = () => {
      const currentMap = mapRef.current;
      if (!currentMap || typeof currentMap.project !== "function") return;
      if (activePopupCoordsRef.current) {
        setPopupPixel(currentMap.project(activePopupCoordsRef.current));
      }
      if (colocatedCoordsRef.current) {
        setColocatedPixel(currentMap.project(colocatedCoordsRef.current));
      }
    };

    map.on("move", handleMapMove);

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

    // Watch container size changes (e.g. split/focus mode toggles) to trigger map.resize()
    let resizeObserver: ResizeObserver | null = null;
    const container = mapContainerRef.current;
    if (typeof ResizeObserver !== "undefined" && container) {
      resizeObserver = new ResizeObserver(() => {
        if (mapRef.current && typeof mapRef.current.resize === "function") {
          mapRef.current.resize();
        }
      });
      resizeObserver.observe(container);
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      map.remove();
    };
  }, []); // Run once on mount

  // Resize map canvas immediately on layoutMode change without WebGL reload
  useEffect(() => {
    if (mapRef.current && typeof mapRef.current.resize === "function") {
      mapRef.current.resize();
      const timer = setTimeout(() => {
        if (mapRef.current && typeof mapRef.current.resize === "function") {
          mapRef.current.resize();
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [layoutMode]);

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

      {/* User Story 4: Single POI Rich Popup Card */}
      {activePopupPoi && popupPixel && (
        <div
          data-testid="map-popup-overlay"
          style={{
            position: "absolute",
            left: `${popupPixel.x}px`,
            top: `${popupPixel.y}px`,
            transform: "translate(-50%, -100%) translateY(-14px)",
            zIndex: 25,
            pointerEvents: "auto",
          }}
        >
          <POIPopupCard
            poi={activePopupPoi}
            onClose={() => {
              setActivePopupPoi(null);
              setActivePopupCoords(null);
              setPopupPixel(null);
            }}
            onEdit={(poi) => {
              setActivePopupPoi(null);
              setActivePopupCoords(null);
              setPopupPixel(null);
              if (onEditPOI) {
                onEditPOI(poi);
              }
            }}
          />
        </div>
      )}

      {/* User Story 4: Co-located POIs Disambiguation List Popup */}
      {colocatedPois && colocatedPixel && (
        <div
          data-testid="map-colocated-overlay"
          style={{
            position: "absolute",
            left: `${colocatedPixel.x}px`,
            top: `${colocatedPixel.y}px`,
            transform: "translate(-50%, -100%) translateY(-14px)",
            zIndex: 25,
            pointerEvents: "auto",
          }}
        >
          <div
            data-testid="colocated-popup-list"
            style={{
              width: "290px",
              maxHeight: "320px",
              padding: "12px",
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
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h4
                data-testid="colocated-popup-title"
                style={{
                  margin: 0,
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "#111827",
                }}
              >
                Co-located POIs ({colocatedPois.length})
              </h4>
              <button
                type="button"
                onClick={() => {
                  setColocatedPois(null);
                  setColocatedCoords(null);
                  setColocatedPixel(null);
                }}
                data-testid="close-colocated-popup-btn"
                aria-label="Close"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "2px",
                  color: "var(--text-muted, #94a3b8)",
                }}
              >
                <X size={15} />
              </button>
            </div>
            <p
              style={{
                margin: 0,
                fontSize: "11px",
                color: "var(--text-secondary, #64748b)",
              }}
            >
              Multiple places share this location at max zoom. Select a place:
            </p>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                overflowY: "auto",
                maxHeight: "210px",
              }}
            >
              {colocatedPois.map((p) => (
                <div
                  key={p.id}
                  data-testid={`colocated-poi-item-${p.id}`}
                  onClick={() => {
                    setColocatedPois(null);
                    setColocatedCoords(null);
                    setColocatedPixel(null);
                    setActivePopupPoi(p);
                    const coords: [number, number] = [
                      p.render_lng ?? p.canonical_lng,
                      p.render_lat ?? p.canonical_lat,
                    ];
                    setActivePopupCoords(coords);
                    if (mapRef.current?.project) {
                      setPopupPixel(mapRef.current.project(coords));
                    }
                    if (onPOIClick) onPOIClick(p);
                  }}
                  style={{
                    padding: "6px 8px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color, #f1f5f9)",
                    cursor: "pointer",
                    transition: "background 0.15s ease",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "var(--bg-hover, #f8fafc)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "2px",
                      minWidth: 0,
                    }}
                  >
                    <span
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#111827",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {p.name}
                    </span>
                    <span
                      style={{
                        fontSize: "10px",
                        color: "var(--text-secondary, #64748b)",
                      }}
                    >
                      {[p.city, p.country].filter(Boolean).join(", ") ||
                        p.address ||
                        "No address"}
                    </span>
                  </div>
                  {p.rating && (
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#b45309",
                        flexShrink: 0,
                        marginLeft: "6px",
                      }}
                    >
                      ★ {p.rating}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

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
