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

import React, { useState, useMemo, useCallback } from "react";
import type { BoundingBox, MapLayerId, POIMapFeature } from "../types/map";
import { MapView } from "../components/map/MapView";
import { POITable } from "../components/poi/POITable";
import { POIEditDrawer } from "../components/poi/POIEditDrawer";
import { usePreferences } from "../context/PreferencesContext";

// Seed demonstration POIs across mainland China and international destinations
export const INITIAL_DEMO_POIS: POIMapFeature[] = [
  {
    id: "poi-bj-tiananmen",
    name: "Tiananmen Square",
    canonical_lng: 116.397458,
    canonical_lat: 39.909187,
    render_lng: 116.397458,
    render_lat: 39.909187,
    visit_state: "visited_return",
    rating: 5,
    tags: ["historic", "plaza", "landmark"],
    city: "Beijing",
    country: "China",
  },
  {
    id: "poi-bj-forbiddencity",
    name: "The Palace Museum (Forbidden City)",
    canonical_lng: 116.397027,
    canonical_lat: 39.917865,
    render_lng: 116.397027,
    render_lat: 39.917865,
    visit_state: "visited_return",
    rating: 5,
    tags: ["unesco", "palace", "history"],
    city: "Beijing",
    country: "China",
  },
  {
    id: "poi-sh-tower",
    name: "Shanghai Tower",
    canonical_lng: 121.505676,
    canonical_lat: 31.233519,
    render_lng: 121.505676,
    render_lat: 31.233519,
    visit_state: "visited_return",
    rating: 5,
    tags: ["skyscraper", "architecture", "viewpoint"],
    city: "Shanghai",
    country: "China",
  },
  {
    id: "poi-sh-bund",
    name: "The Bund",
    canonical_lng: 121.4905,
    canonical_lat: 31.2415,
    render_lng: 121.4905,
    render_lat: 31.2415,
    visit_state: "visited_return",
    rating: 4,
    tags: ["waterfront", "colonial", "nightview"],
    city: "Shanghai",
    country: "China",
  },
  {
    id: "poi-fr-eiffel",
    name: "Eiffel Tower",
    canonical_lng: 2.2945,
    canonical_lat: 48.8584,
    render_lng: 2.2945,
    render_lat: 48.8584,
    visit_state: "not_visited",
    rating: null,
    tags: ["monument", "romantic"],
    city: "Paris",
    country: "France",
  },
];

export interface HomePageProps {
  pois?: POIMapFeature[];
  onUpdatePois?: (updated: POIMapFeature[]) => void;
  isPickingLocation?: boolean;
  onLocationPicked?: (coords: { lng: number; lat: number }) => void;
}

export const HomePage: React.FC<HomePageProps> = ({
  pois: propsPois,
  onUpdatePois: propsOnUpdatePois,
  isPickingLocation = false,
  onLocationPicked,
}) => {
  const { poi } = usePreferences();
  const [internalPois, setInternalPois] =
    useState<POIMapFeature[]>(INITIAL_DEMO_POIS);
  const pois = propsPois || internalPois;

  const setPois = useCallback(
    (newPois: POIMapFeature[]) => {
      if (propsOnUpdatePois) {
        propsOnUpdatePois(newPois);
      } else {
        setInternalPois(newPois);
      }
    },
    [propsOnUpdatePois],
  );

  const [activeLayer, setActiveLayer] = useState<MapLayerId>(
    (poi.default_map_layer as MapLayerId) || "osm",
  );
  const [selectedPoiId, setSelectedPoiId] = useState<string | null>(null);
  const [isViewportFilterActive, setIsViewportFilterActive] =
    useState<boolean>(false);
  const [visibleViewportPois, setVisibleViewportPois] =
    useState<POIMapFeature[]>(INITIAL_DEMO_POIS);
  const [currentBbox, setCurrentBbox] = useState<BoundingBox | null>(null);

  // Detail drawer state
  const [drawerPoi, setDrawerPoi] = useState<POIMapFeature | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Handle viewport changes from MapView
  const handleViewportChange = useCallback(
    (bbox: BoundingBox, visible: POIMapFeature[]) => {
      setCurrentBbox(bbox);
      setVisibleViewportPois(visible);
    },
    [],
  );

  // Handle server-side viewport query when POIs >= 1,000
  const handleFetchServerViewport = useCallback(
    async (bbox: BoundingBox, signal: AbortSignal) => {
      try {
        const query = `bbox=${bbox.minLng},${bbox.minLat},${bbox.maxLng},${bbox.maxLat}`;
        const res = await fetch(`/api/pois?${query}`, { signal });
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data.items)) {
          setPois(data.items);
        }
      } catch (err: unknown) {
        if ((err as Error).name !== "AbortError") {
          console.error("Server viewport fetch error:", err);
        }
      }
    },
    [setPois],
  );

  // Filter table rows based on viewport toggle
  const displayedTablePois = useMemo(() => {
    if (!isViewportFilterActive) {
      return pois;
    }
    return visibleViewportPois;
  }, [isViewportFilterActive, pois, visibleViewportPois]);

  const handleSelectPOI = (poi: POIMapFeature) => {
    setSelectedPoiId(poi.id);
  };

  const handleEditPOI = (poi: POIMapFeature) => {
    setDrawerPoi(poi);
    setIsDrawerOpen(true);
  };

  const handleSaveDrawerPOI = (updated: POIMapFeature) => {
    const next = pois.map((p) => (p.id === updated.id ? updated : p));
    setPois(next);
    setIsDrawerOpen(false);
  };

  const handleDeleteDrawerPOI = (id: string) => {
    const next = pois.filter((p) => p.id !== id);
    setPois(next);
    setIsDrawerOpen(false);
    if (selectedPoiId === id) setSelectedPoiId(null);
  };

  return (
    <div
      className="home-page-layout"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 53px)",
        width: "100vw",
        overflow: "hidden",
        background: "var(--bg-primary, #f8fafc)",
      }}
    >
      {/* Sub-bar: Exploration status and coordinates */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 20px",
          background: "var(--bg-surface, #ffffff)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          fontSize: "12px",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <span style={{ color: "var(--text-muted)" }}>
            Total POIs:{" "}
            <strong style={{ color: "var(--text-primary)" }}>
              {pois.length}
            </strong>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Active Layer:{" "}
            <strong style={{ color: "var(--accent, #2563eb)" }}>
              {activeLayer}
            </strong>
          </span>
        </div>

        {isPickingLocation && (
          <div
            style={{
              padding: "2px 10px",
              borderRadius: "9999px",
              background: "#fef3c7",
              color: "#b45309",
              fontWeight: 700,
              animation: "pulse 1.5s infinite",
            }}
          >
            🎯 Pin Drop Mode: Click anywhere on the map to place location
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            color: "var(--text-muted)",
          }}
        >
          {currentBbox && (
            <span>
              Viewport: [{currentBbox.minLng.toFixed(2)},{" "}
              {currentBbox.minLat.toFixed(2)}] to [
              {currentBbox.maxLng.toFixed(2)}, {currentBbox.maxLat.toFixed(2)}]
            </span>
          )}
        </div>
      </div>

      {/* Main Content: Split Map & Table */}
      <main
        style={{
          display: "flex",
          flex: 1,
          overflow: "hidden",
          padding: "12px 16px",
          gap: "16px",
        }}
      >
        {/* Left Side: Interactive Map */}
        <div style={{ flex: 1.4, height: "100%", position: "relative" }}>
          <MapView
            pois={pois}
            totalPoiCount={pois.length}
            activeLayer={activeLayer}
            defaultLayer={(poi.default_map_layer as MapLayerId) || "osm"}
            mapLanguage={poi.map_language || "local"}
            selectedPoiId={selectedPoiId}
            onLayerChange={setActiveLayer}
            onPOIClick={(poi) => {
              handleSelectPOI(poi);
              handleEditPOI(poi);
            }}
            onViewportChange={handleViewportChange}
            onFetchServerViewport={handleFetchServerViewport}
            isPinDropMode={isPickingLocation}
            onPinDrop={onLocationPicked}
          />
        </div>

        {/* Right Side: Synchronized POI Table */}
        <div style={{ flex: 1.0, height: "100%" }}>
          <POITable
            pois={displayedTablePois}
            selectedPoiId={selectedPoiId}
            isViewportFilterActive={isViewportFilterActive}
            onToggleViewportFilter={setIsViewportFilterActive}
            onSelectPOI={handleSelectPOI}
            onEditPOI={handleEditPOI}
          />
        </div>
      </main>

      {/* Enhanced Edit Drawer */}
      <POIEditDrawer
        poi={drawerPoi}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSave={handleSaveDrawerPOI}
        onDelete={handleDeleteDrawerPOI}
      />
    </div>
  );
};

export default HomePage;
