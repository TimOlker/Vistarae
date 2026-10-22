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

import React, { useState, useMemo, useCallback, useEffect } from "react";
import type { BoundingBox, MapLayerId, POIMapFeature } from "../types/map";
import type { LayoutMode } from "../types/layout";
import type {
  FilterRule,
  PinColorScheme,
  QueryGroup,
  TableConfig,
} from "../types/filter";
import { ViewModeControl } from "../components/layout/ViewModeControl";
import { MapView } from "../components/map/MapView";
import { POITable } from "../components/poi/POITable";
import { POIEditDrawer } from "../components/poi/POIEditDrawer";
import { FilterBar } from "../components/filter/FilterBar";
import {
  BulkOperationsModal,
  type BulkEditOperationType,
} from "../components/bulk/BulkOperationsModal";
import { usePreferences } from "../context/PreferencesContext";
import * as filterRuleService from "../services/filterRuleService";
import * as bulkService from "../services/bulkService";
import { evaluateQueryTree } from "../utils/filterEvaluator";
import { computePoiPinColor } from "../utils/pinColor";

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

  const [layoutMode, setLayoutMode] = useState<LayoutMode>("split");
  const [activeLayer, setActiveLayer] = useState<MapLayerId>(
    (poi.default_map_layer as MapLayerId) || "osm",
  );
  const [selectedPoiId, setSelectedPoiId] = useState<string | null>(null);
  const [isViewportFilterActive, setIsViewportFilterActive] =
    useState<boolean>(true);
  const [visibleViewportPois, setVisibleViewportPois] =
    useState<POIMapFeature[]>(INITIAL_DEMO_POIS);
  const [currentBbox, setCurrentBbox] = useState<BoundingBox | null>(null);

  // Detail drawer state
  const [drawerPoi, setDrawerPoi] = useState<POIMapFeature | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // User Story 2: Filter rules, table config, pin color scheme
  const [queryGroup, setQueryGroup] = useState<QueryGroup>({
    id: "root",
    conjunction: "AND",
    rules: [],
  });
  const [activeFilterGroup, setActiveFilterGroup] = useState<QueryGroup | null>(
    null,
  );
  const [tableConfig, setTableConfig] = useState<TableConfig>({
    visible_columns: ["name", "city", "rating", "visit_state", "tags"],
    column_order: [
      "name",
      "city",
      "state",
      "country",
      "rating",
      "visit_state",
      "tags",
    ],
    sort: {
      column: "name",
      direction: "asc",
    },
  });
  const [pinColorScheme, setPinColorScheme] = useState<PinColorScheme>({
    mode: "uniform",
    default_color: "#2563EB",
    palette: {},
    rule_mappings: [],
  });
  const [savedRules, setSavedRules] = useState<FilterRule[]>([]);
  const [activeRuleId, setActiveRuleId] = useState<string | null>(null);
  const [serverFilteredPois, setServerFilteredPois] = useState<
    POIMapFeature[] | null
  >(null);

  // User Story 3: Multi-select & Bulk operations
  const [multiSelectMode, setMultiSelectMode] = useState<boolean>(false);
  const [selectedPoiIds, setSelectedPoiIds] = useState<string[]>([]);
  const [bulkModalOpen, setBulkModalOpen] = useState<boolean>(false);
  const [bulkModalMode, setBulkModalMode] = useState<"edit" | "delete">("edit");
  const [bulkNotification, setBulkNotification] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Dismiss notification automatically after 4 seconds
  useEffect(() => {
    if (!bulkNotification) return;
    const timer = setTimeout(() => {
      setBulkNotification(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [bulkNotification]);

  // Load saved rules on mount
  useEffect(() => {
    let isMounted = true;
    if (typeof filterRuleService.listFilterRules === "function") {
      filterRuleService
        .listFilterRules()
        .then((res) => {
          if (isMounted) {
            setSavedRules(Array.isArray(res) ? res : res?.items || []);
          }
        })
        .catch((err) => {
          console.warn("Could not load filter rules:", err);
        });
    }
    return () => {
      isMounted = false;
    };
  }, []);

  // Handle saved rule actions
  const handleSelectRule = (rule: FilterRule | null) => {
    if (!rule) {
      setActiveRuleId(null);
      return;
    }
    setActiveRuleId(rule.id);
    setQueryGroup(rule.query_tree);
    setActiveFilterGroup(rule.query_tree);
    if (rule.table_config) {
      setTableConfig(rule.table_config);
    }
    if (rule.pin_color_scheme) {
      setPinColorScheme(rule.pin_color_scheme);
    }
  };

  const handleSaveRule = async (name: string, isOverwrite: boolean) => {
    if (isOverwrite && activeRuleId) {
      const updated = await filterRuleService.updateFilterRule(activeRuleId, {
        name,
        query_tree: queryGroup,
        table_config: tableConfig,
        pin_color_scheme: pinColorScheme,
      });
      setSavedRules(savedRules.map((r) => (r.id === updated.id ? updated : r)));
    } else {
      const created = await filterRuleService.createFilterRule({
        name,
        query_tree: queryGroup,
        table_config: tableConfig,
        pin_color_scheme: pinColorScheme,
      });
      setSavedRules([...savedRules, created]);
      setActiveRuleId(created.id);
    }
  };

  const handleDeleteRule = async (id: string) => {
    await filterRuleService.deleteFilterRule(id);
    setSavedRules(savedRules.filter((r) => r.id !== id));
    if (activeRuleId === id) {
      setActiveRuleId(null);
    }
  };

  // Hybrid Filter Execution (REQ-MAIN-010)
  const handleApplyFilter = useCallback(async () => {
    setActiveFilterGroup(queryGroup);

    // If dataset >= 1,000 POIs, delegate query to backend PostGIS endpoint
    if (pois.length >= 1000) {
      try {
        const bboxParam = currentBbox
          ? `${currentBbox.minLng},${currentBbox.minLat},${currentBbox.maxLng},${currentBbox.maxLat}`
          : undefined;
        const results = await filterRuleService.queryPois(
          queryGroup,
          bboxParam,
        );
        setServerFilteredPois(results.items);
      } catch (err) {
        console.error("Hybrid filter query failed:", err);
      }
    } else {
      setServerFilteredPois(null);
    }
  }, [queryGroup, pois.length, currentBbox]);

  const handleClearFilter = useCallback(() => {
    const emptyGroup: QueryGroup = {
      id: "root",
      conjunction: "AND",
      rules: [],
    };
    setQueryGroup(emptyGroup);
    setActiveFilterGroup(null);
    setServerFilteredPois(null);
  }, []);

  // Filtered POIs
  const filteredPois = useMemo(() => {
    if (!activeFilterGroup || activeFilterGroup.rules.length === 0) {
      return pois;
    }
    if (pois.length >= 1000 && serverFilteredPois !== null) {
      return serverFilteredPois;
    }
    return pois.filter((p) => evaluateQueryTree(p, activeFilterGroup));
  }, [pois, activeFilterGroup, serverFilteredPois]);

  // Dynamic pin color scheme calculation
  const colorizedPois = useMemo(() => {
    return filteredPois.map((p) => ({
      ...p,
      pin_color: computePoiPinColor(p, pinColorScheme),
    }));
  }, [filteredPois, pinColorScheme]);

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

  // Filter table rows based on viewport toggle and active filters
  const displayedTablePois = useMemo(() => {
    if (!isViewportFilterActive) {
      return colorizedPois;
    }
    const visibleIds = new Set(visibleViewportPois.map((v) => v.id));
    return colorizedPois.filter((p) => visibleIds.has(p.id));
  }, [isViewportFilterActive, colorizedPois, visibleViewportPois]);

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

  // Multi-select & Bulk Operation Handlers (US3 / REQ-MAIN-022 to REQ-MAIN-035)
  const handleToggleMultiSelectMode = useCallback(() => {
    setMultiSelectMode((prev) => {
      if (prev) {
        setSelectedPoiIds([]);
      }
      return !prev;
    });
  }, []);

  const handleToggleSelectPoi = useCallback((id: string) => {
    setSelectedPoiIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const handleToggleSelectAll = useCallback(() => {
    const allSelected = displayedTablePois.every((p) =>
      selectedPoiIds.includes(p.id),
    );
    if (allSelected) {
      setSelectedPoiIds([]);
    } else {
      setSelectedPoiIds(displayedTablePois.map((p) => p.id));
    }
  }, [displayedTablePois, selectedPoiIds]);

  const handleDeselectAll = useCallback(() => {
    setSelectedPoiIds([]);
  }, []);

  const handleOpenBulkEdit = useCallback(() => {
    setBulkModalMode("edit");
    setBulkModalOpen(true);
  }, []);

  const handleOpenBulkDelete = useCallback(() => {
    setBulkModalMode("delete");
    setBulkModalOpen(true);
  }, []);

  const handleConfirmBulkEdit = useCallback(
    async (action: BulkEditOperationType, payload: any) => {
      try {
        const res = await bulkService.bulkEditPois(
          selectedPoiIds,
          action,
          payload,
        );

        // Optimistically apply edits locally
        const targetIds = new Set(selectedPoiIds);
        const updatedPois = pois.map((p) => {
          if (!targetIds.has(p.id)) return p;
          const updated = { ...p };

          if (action === "set_rating") {
            updated.rating = payload.rating;
          } else if (action === "add_visit_date") {
            updated.already_visited = true;
            if (updated.want_to_visit_again) {
              updated.visit_state = "visited_return";
              updated.visit_pending = true;
            } else {
              updated.visit_state = "visited_do_not_return";
              updated.visit_pending = false;
            }
          } else if (action === "set_visit_again") {
            updated.want_to_visit_again = payload.want_to_visit_again;
            if (updated.already_visited) {
              updated.visit_state = payload.want_to_visit_again
                ? "visited_return"
                : "visited_do_not_return";
              updated.visit_pending = payload.want_to_visit_again;
            }
          } else if (action === "add_tag") {
            const currentTags = updated.tags || [];
            if (!currentTags.includes(payload.tag_name)) {
              updated.tags = [...currentTags, payload.tag_name];
            }
          } else if (action === "remove_tag") {
            updated.tags = (updated.tags || []).filter(
              (t) => t !== payload.tag_name,
            );
          } else if (action === "update_address") {
            const addr = payload.address || {};
            if (addr.city !== undefined) updated.city = addr.city || undefined;
            if (addr.country !== undefined)
              updated.country = addr.country || undefined;
          }

          return updated;
        });

        setPois(updatedPois);
        setSelectedPoiIds([]);
        setBulkNotification({
          message: `Successfully updated ${res.modified_count} POI${
            res.modified_count === 1 ? "" : "s"
          }.`,
          type: "success",
        });
      } catch (err: any) {
        setBulkNotification({
          message: err.message || "Bulk edit failed.",
          type: "error",
        });
        throw err;
      }
    },
    [pois, selectedPoiIds, setPois],
  );

  const handleConfirmBulkDelete = useCallback(async () => {
    try {
      const res = await bulkService.bulkDeletePois(selectedPoiIds);
      const targetIds = new Set(selectedPoiIds);
      setPois(pois.filter((p) => !targetIds.has(p.id)));
      setSelectedPoiIds([]);
      setBulkNotification({
        message: `Successfully deleted ${res.deleted_count} POI${
          res.deleted_count === 1 ? "" : "s"
        }.`,
        type: "success",
      });
    } catch (err: any) {
      setBulkNotification({
        message: err.message || "Bulk delete failed.",
        type: "error",
      });
      throw err;
    }
  }, [pois, selectedPoiIds, setPois]);

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
      {/* Sub-bar: Exploration status, layout control, and coordinates */}
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

        {/* Center: View Mode Segmented Control */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <ViewModeControl mode={layoutMode} onChange={setLayoutMode} />
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
        </div>

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

      {/* Bulk operation notification banner */}
      {bulkNotification && (
        <div
          role="status"
          data-testid="bulk-notification-banner"
          style={{
            padding: "8px 20px",
            backgroundColor:
              bulkNotification.type === "success" ? "#DCFCE7" : "#FEE2E2",
            color: bulkNotification.type === "success" ? "#166534" : "#991B1B",
            fontSize: "13px",
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid rgba(0,0,0,0.06)",
          }}
        >
          <span>{bulkNotification.message}</span>
          <button
            onClick={() => setBulkNotification(null)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
              color: "inherit",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Visual Filter Bar & View Profile Manager */}
      <FilterBar
        queryGroup={queryGroup}
        onQueryGroupChange={setQueryGroup}
        onApplyFilter={handleApplyFilter}
        onClearFilter={handleClearFilter}
        savedRules={savedRules}
        activeRuleId={activeRuleId}
        onSelectRule={handleSelectRule}
        onSaveRule={handleSaveRule}
        onDeleteRule={handleDeleteRule}
        tableConfig={tableConfig}
        onTableConfigChange={setTableConfig}
        pinColorScheme={pinColorScheme}
        onPinColorSchemeChange={setPinColorScheme}
      />

      {/* Main Content: Split Map & Table */}
      <main
        style={{
          display: "flex",
          flex: 1,
          overflow: "hidden",
          padding: "12px 16px",
          gap: layoutMode === "split" ? "16px" : "0px",
        }}
      >
        {/* Left Side: Interactive Map */}
        <div
          data-testid="map-container"
          style={{
            display: layoutMode === "table_only" ? "none" : "flex",
            flex: layoutMode === "map_only" ? 1 : 1.4,
            width: layoutMode === "map_only" ? "100%" : undefined,
            height: "100%",
            position: "relative",
            minWidth: 0,
            transition: "flex 0.15s ease",
          }}
        >
          <MapView
            pois={colorizedPois}
            totalPoiCount={colorizedPois.length}
            activeLayer={activeLayer}
            defaultLayer={(poi.default_map_layer as MapLayerId) || "osm"}
            mapLanguage={poi.map_language || "local"}
            selectedPoiId={selectedPoiId}
            layoutMode={layoutMode}
            onLayerChange={setActiveLayer}
            onPOIClick={handleSelectPOI}
            onEditPOI={handleEditPOI}
            onViewportChange={handleViewportChange}
            onFetchServerViewport={handleFetchServerViewport}
            isPinDropMode={isPickingLocation}
            onPinDrop={onLocationPicked}
          />
        </div>

        {/* Right Side: Synchronized POI Table */}
        <div
          data-testid="table-container"
          style={{
            display: layoutMode === "map_only" ? "none" : "flex",
            flex: layoutMode === "table_only" ? 1 : 1.0,
            width: layoutMode === "table_only" ? "100%" : undefined,
            height: "100%",
            minWidth: 0,
            flexDirection: "column",
            transition: "flex 0.15s ease",
          }}
        >
          <POITable
            pois={displayedTablePois}
            selectedPoiId={selectedPoiId}
            isViewportFilterActive={isViewportFilterActive}
            onToggleViewportFilter={setIsViewportFilterActive}
            onSelectPOI={handleSelectPOI}
            onEditPOI={handleEditPOI}
            tableConfig={tableConfig}
            multiSelectMode={multiSelectMode}
            onToggleMultiSelectMode={handleToggleMultiSelectMode}
            selectedPoiIds={selectedPoiIds}
            onToggleSelectPoi={handleToggleSelectPoi}
            onToggleSelectAll={handleToggleSelectAll}
            onOpenBulkEdit={handleOpenBulkEdit}
            onOpenBulkDelete={handleOpenBulkDelete}
            onDeselectAll={handleDeselectAll}
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

      {/* Bulk Operations Modal */}
      <BulkOperationsModal
        isOpen={bulkModalOpen}
        onClose={() => setBulkModalOpen(false)}
        selectedPoiIds={selectedPoiIds}
        mode={bulkModalMode}
        onConfirmEdit={handleConfirmBulkEdit}
        onConfirmDelete={handleConfirmBulkDelete}
      />
    </div>
  );
};

export default HomePage;
