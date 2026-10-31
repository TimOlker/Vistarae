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

import React, { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { Modal } from "../common/Modal";
import { ingestApi, type CandidateItem } from "../../services/ingestApi";
import { useToast } from "../../context/ToastContext";
import {
  X,
  ArrowRight,
  MapPin,
  Folder,
  Calendar,
  AlertTriangle,
  Compass,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  Edit2,
  Save,
  Check,
  Loader2,
  RotateCw,
  Crosshair,
  ExternalLink,
  ShieldAlert,
  ChevronDown,
} from "lucide-react";
import { reverseGeocode, forwardGeocode } from "../../services/geocodeService";
import { openLocalFolder } from "../../services/nativeHostService";
import { apiFetch } from "../../services/api";

export interface ExistingPOIMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface CSVTriageModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onProceedToPhase2?: () => void;
  onTriageComplete?: () => void;
  existingPOIs?: ExistingPOIMarker[];
}

export type SortPriority = "poi" | "location";

type SortField =
  | "poi_name"
  | "city"
  | "state_province"
  | "country"
  | "confidence_score"
  | "disposition"
  | "row_index";

export interface NearbyPOIMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  source: "db" | "csv";
  distanceMeters: number;
}

export function computeDistanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371000; // Radius of Earth in meters
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${meters} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

interface CandidateMiniMapProps {
  latitude: number | null | undefined;
  longitude: number | null | undefined;
  poiName: string;
  existingPOIs?: ExistingPOIMarker[];
  nearbyPOIs?: NearbyPOIMarker[];
  onSelectNearbyPOI?: (poi: NearbyPOIMarker) => void;
  onSelectExistingPOI?: (poi: ExistingPOIMarker) => void;
  isPicking?: boolean;
  onStartPicking?: () => void;
  onStopPicking?: () => void;
  onCoordinatesPicked?: (lat: number, lon: number) => void;
  fallbackCenter?: [number, number];
}

export const CandidateMiniMap: React.FC<CandidateMiniMapProps> = ({
  latitude,
  longitude,
  poiName,
  existingPOIs = [],
  nearbyPOIs = [],
  onSelectNearbyPOI,
  onSelectExistingPOI,
  isPicking = false,
  onStartPicking,
  onStopPicking,
  onCoordinatesPicked,
  fallbackCenter,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const existingMarkersRef = useRef<maplibregl.Marker[]>([]);
  const onCoordinatesPickedRef = useRef(onCoordinatesPicked);

  useEffect(() => {
    onCoordinatesPickedRef.current = onCoordinatesPicked;
  }, [onCoordinatesPicked]);

  const hasCoords =
    latitude !== null &&
    latitude !== undefined &&
    longitude !== null &&
    longitude !== undefined &&
    !isNaN(Number(latitude)) &&
    !isNaN(Number(longitude));

  const showMap = hasCoords || isPicking;

  // Helper to create custom pin element
  const createPinElement = (title: string) => {
    const pinEl = document.createElement("div");
    pinEl.style.width = "28px";
    pinEl.style.height = "28px";
    pinEl.style.cursor = "grab";
    pinEl.title = `${title} (Drag or click map to move)`;
    pinEl.innerHTML = `
      <svg viewBox="0 0 24 24" width="28" height="28" fill="#2563eb" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35));">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
        <circle cx="12" cy="10" r="3" fill="#ffffff"></circle>
      </svg>
    `;
    return pinEl;
  };

  useEffect(() => {
    if (!showMap || !mapContainerRef.current) return;

    const lat = hasCoords ? Number(latitude) : (fallbackCenter ? fallbackCenter[1] : 41.8);
    const lon = hasCoords ? Number(longitude) : (fallbackCenter ? fallbackCenter[0] : -88.3);

    try {
      if (
        !mapInstanceRef.current ||
        (mapInstanceRef.current.getContainer &&
          mapInstanceRef.current.getContainer() !== mapContainerRef.current)
      ) {
        if (mapInstanceRef.current) {
          try {
            mapInstanceRef.current.remove();
          } catch {
            // ignore
          }
          mapInstanceRef.current = null;
          markerRef.current = null;
        }

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
          center: [lon, lat],
          zoom: hasCoords ? 14 : 11,
          attributionControl: false,
        });

        map.addControl(
          new maplibregl.NavigationControl({ showCompass: false }),
          "top-right",
        );

        // Click on map to place or update pin
        map.on("click", (e) => {
          const clickedLat = e.lngLat.lat;
          const clickedLon = e.lngLat.lng;
          if (onCoordinatesPickedRef.current) {
            onCoordinatesPickedRef.current(clickedLat, clickedLon);
          }
        });

        if (hasCoords) {
          const pinEl = createPinElement(poiName);
          const marker = new maplibregl.Marker({ element: pinEl, draggable: true })
            .setLngLat([lon, lat])
            .addTo(map);

          if (typeof marker.on === "function") {
            marker.on("dragend", () => {
              if (typeof marker.getLngLat === "function") {
                const pos = marker.getLngLat();
                onCoordinatesPickedRef.current?.(pos.lat, pos.lng);
              }
            });
          }
          markerRef.current = marker;
        }

        mapInstanceRef.current = map;

        setTimeout(() => {
          try {
            map.resize();
          } catch {
            // ignore
          }
        }, 150);
      } else {
        const map = mapInstanceRef.current;
        setTimeout(() => {
          try {
            map.resize();
            if (hasCoords) {
              map.flyTo({ center: [lon, lat], zoom: 14 });
            }
          } catch {
            // ignore
          }
        }, 50);

        if (hasCoords) {
          if (markerRef.current) {
            markerRef.current.setLngLat([lon, lat]);
          } else {
            const pinEl = createPinElement(poiName);
            const marker = new maplibregl.Marker({ element: pinEl, draggable: true })
              .setLngLat([lon, lat])
              .addTo(map);

            if (typeof marker.on === "function") {
              marker.on("dragend", () => {
                if (typeof marker.getLngLat === "function") {
                  const pos = marker.getLngLat();
                  onCoordinatesPickedRef.current?.(pos.lat, pos.lng);
                }
              });
            }
            markerRef.current = marker;
          }
        } else if (!hasCoords && markerRef.current) {
          markerRef.current.remove();
          markerRef.current = null;
        }
      }
    } catch (err) {
      console.warn("Mini map init error:", err);
    }
  }, [showMap, hasCoords, latitude, longitude, poiName, fallbackCenter]);

  // Adjust cursor style when in picking mode
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (map && map.getCanvas) {
      try {
        const canvas = map.getCanvas();
        if (canvas) {
          canvas.style.cursor = isPicking ? "crosshair" : "";
        }
      } catch {
        // ignore
      }
    }
  }, [isPicking]);

  // Update markers on map for nearby POIs (distinguishing DB vs CSV with different colors)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    existingMarkersRef.current.forEach((m) => {
      try {
        m.remove();
      } catch {
        // ignore
      }
    });
    existingMarkersRef.current = [];

    if (nearbyPOIs && nearbyPOIs.length > 0) {
      nearbyPOIs.forEach((poi) => {
        try {
          const el = document.createElement("div");
          el.style.width = "22px";
          el.style.height = "22px";
          el.style.cursor = "pointer";
          const isDb = poi.source === "db";
          const fillColor = isDb ? "#9333ea" : "#d97706";
          const labelSource = isDb ? "Database" : "CSV Batch";
          el.title = `[${labelSource}] ${poi.name} (${formatDistance(poi.distanceMeters)}) - Click to select as parent`;
          el.innerHTML = `
            <svg viewBox="0 0 24 24" width="22" height="22" fill="${fillColor}" stroke="#ffffff" stroke-width="2" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35));">
              ${
                isDb
                  ? '<circle cx="12" cy="12" r="8"></circle>'
                  : '<rect x="4" y="4" width="16" height="16" rx="3" transform="rotate(45 12 12)"></rect>'
              }
            </svg>
          `;
          el.addEventListener("click", () => {
            if (onSelectNearbyPOI) {
              onSelectNearbyPOI(poi);
            } else if (onSelectExistingPOI) {
              onSelectExistingPOI({
                id: poi.id,
                name: poi.name,
                latitude: poi.latitude,
                longitude: poi.longitude,
                distance_meters: poi.distanceMeters,
              });
            }
          });

          const m = new maplibregl.Marker({ element: el })
            .setLngLat([poi.longitude, poi.latitude])
            .addTo(map);

          existingMarkersRef.current.push(m);
        } catch {
          // ignore marker errors
        }
      });
    } else if (existingPOIs && existingPOIs.length > 0) {
      existingPOIs.forEach((poi) => {
        try {
          const el = document.createElement("div");
          el.style.width = "18px";
          el.style.height = "18px";
          el.style.cursor = "pointer";
          el.title = `Existing POI: ${poi.name}`;
          el.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18" fill="#7e22ce" stroke="#ffffff" stroke-width="1.5" style="filter: drop-shadow(0 1px 2px rgba(0,0,0,0.3));">
              <circle cx="12" cy="12" r="8"></circle>
            </svg>
          `;
          el.addEventListener("click", () => {
            onSelectExistingPOI?.(poi);
          });

          const m = new maplibregl.Marker({ element: el })
            .setLngLat([poi.longitude, poi.latitude])
            .addTo(map);

          existingMarkersRef.current.push(m);
        } catch {
          // ignore marker errors
        }
      });
    }
  }, [nearbyPOIs, existingPOIs, onSelectNearbyPOI, onSelectExistingPOI]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.remove();
        } catch {
          // ignore
        }
        mapInstanceRef.current = null;
        markerRef.current = null;
      }
    };
  }, []);

  return (
    <div style={{ marginBottom: "12px" }}>
      {/* Map display container - visible when coordinates are present or when user is picking */}
      <div
        data-testid="candidate-mini-map-container"
        style={{
          display: showMap ? "block" : "none",
          borderRadius: "8px",
          overflow: "hidden",
          border: "1px solid #cbd5e1",
          boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        }}
      >
        {isPicking && (
          <div
            style={{
              backgroundColor: "#eff6ff",
              borderBottom: "1px solid #bfdbfe",
              padding: "6px 10px",
              fontSize: "11px",
              color: "#1d4ed8",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <Crosshair size={13} color="#2563eb" />
              Click map or drag pin to set coordinates
            </span>
            {onStopPicking && (
              <button
                type="button"
                onClick={onStopPicking}
                style={{
                  padding: "2px 8px",
                  fontSize: "10px",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Done
              </button>
            )}
          </div>
        )}

        <div
          ref={mapContainerRef}
          data-testid="candidate-mini-map"
          style={{
            height: "190px",
            width: "100%",
            backgroundColor: "#e2e8f0",
          }}
        />
        <div
          style={{
            backgroundColor: "#f8fafc",
            padding: "6px 10px",
            borderTop: "1px solid #e2e8f0",
            fontSize: "11px",
            color: "#475569",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <MapPin size={12} color="#2563eb" />
            <strong>
              {hasCoords
                ? `${Number(latitude).toFixed(5)}, ${Number(longitude).toFixed(5)}`
                : "No coordinates (click map to pin)"}
            </strong>
          </span>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {onStartPicking && (
              <button
                type="button"
                onClick={isPicking ? onStopPicking : onStartPicking}
                data-testid="toggle-pin-btn"
                style={{
                  fontSize: "10px",
                  color: isPicking ? "#dc2626" : "#2563eb",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: "3px",
                  padding: 0,
                }}
              >
                <Crosshair size={10} />
                {isPicking ? "Cancel Picking" : "Adjust on Map"}
              </button>
            )}
            <span style={{ fontSize: "10px", color: "#94a3b8" }}>OSM</span>
          </div>
        </div>
      </div>

      {/* Placeholder container - visible when coordinates are missing and not picking */}
      <div
        data-testid="mini-map-placeholder"
        style={{
          display: showMap ? "none" : "flex",
          minHeight: "140px",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#f8fafc",
          borderRadius: "8px",
          border: "1px dashed #cbd5e1",
          color: "#64748b",
          fontSize: "12px",
          textAlign: "center",
          padding: "16px",
          gap: "4px",
        }}
      >
        <MapPin size={22} color="#94a3b8" style={{ marginBottom: "2px" }} />
        <span style={{ fontWeight: 600, color: "#334155" }}>No coordinates identified</span>
        <span style={{ fontSize: "11px", color: "#94a3b8", maxWidth: "260px" }}>
          Edit address to lookup coordinates, or pick location directly on map.
        </span>
        {onStartPicking && (
          <button
            type="button"
            onClick={onStartPicking}
            data-testid="pick-on-map-placeholder-btn"
            style={{
              marginTop: "8px",
              padding: "6px 12px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontSize: "11px",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
            }}
          >
            <Crosshair size={12} />
            <span>Pick Location on Map</span>
          </button>
        )}
      </div>
    </div>
  );
};

export const CSVTriageModal: React.FC<CSVTriageModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onProceedToPhase2,
  onTriageComplete,
  existingPOIs = [],
}) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Sorting state
  const [sortPriority, setSortPriority] = useState<SortPriority>("poi");
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  // Multi-select disposition filter state
  const ALL_DISPOSITIONS = useMemo(
    () => [
      { key: "accept", label: "Accept" },
      { key: "sublocation", label: "Sublocation" },
      { key: "update_existing", label: "Update Existing" },
      { key: "ignore", label: "Ignore" },
      { key: "exclude", label: "Exclude" },
    ],
    [],
  );
  const [selectedDispositions, setSelectedDispositions] = useState<string[]>([
    "accept",
    "sublocation",
    "update_existing",
    "ignore",
    "exclude",
  ]);
  const [isDispositionDropdownOpen, setIsDispositionDropdownOpen] = useState(false);
  const dispositionDropdownRef = useRef<HTMLDivElement>(null);

  // Close disposition dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dispositionDropdownRef.current &&
        !dispositionDropdownRef.current.contains(e.target as Node)
      ) {
        setIsDispositionDropdownOpen(false);
      }
    };
    if (isDispositionDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isDispositionDropdownOpen]);

  // Bulk edit state
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [isBulkEditOpen, setIsBulkEditOpen] = useState(false);
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [bulkCountry, setBulkCountry] = useState("");
  const [bulkStateProvince, setBulkStateProvince] = useState("");
  const [bulkCity, setBulkCity] = useState("");

  // Filtering state
  const [searchFilter, setSearchFilter] = useState("");

  // Right-pane edit & geocoding state
  const [isEditing, setIsEditing] = useState(false);
  const [isPickingOnMap, setIsPickingOnMap] = useState(false);
  const [isReverseGeocoding, setIsReverseGeocoding] = useState(false);
  const [isForwardGeocoding, setIsForwardGeocoding] = useState(false);
  const [editForm, setEditForm] = useState({
    poi_name: "",
    street_address: "",
    city: "",
    state_province: "",
    country: "",
    latitude: "",
    longitude: "",
  });

  // Nearby POIs search radius (in kilometers)
  const [nearbyRadiusKm, setNearbyRadiusKm] = useState<number>(10);

  // Calculate fallback center from existing coordinates in the batch
  const batchFallbackCenter = useMemo<[number, number]>(() => {
    const withCoords = candidates.find(
      (c) =>
        c.latitude != null &&
        c.longitude != null &&
        !isNaN(Number(c.latitude)) &&
        !isNaN(Number(c.longitude)),
    );
    if (withCoords) {
      return [Number(withCoords.longitude), Number(withCoords.latitude)];
    }
    return [-88.3, 41.8];
  }, [candidates]);

  // Identify in-batch duplicate matches for candidates where recommended disposition is update_existing
  const inBatchMatches = useMemo(() => {
    const matchMap = new Map<string, CandidateItem>();
    candidates.forEach((cand) => {
      const disp = cand.user_disposition || cand.recommended_disposition;
      if (disp === "update_existing" && !cand.matched_existing_poi_name) {
        const match = candidates.find(
          (c) =>
            c.id !== cand.id &&
            c.row_index < cand.row_index &&
            c.poi_name.trim().toLowerCase() === cand.poi_name.trim().toLowerCase() &&
            (!c.city || !cand.city || c.city.toLowerCase() === cand.city.toLowerCase()),
        );
        if (match) {
          matchMap.set(cand.id, match);
        }
      }
    });
    return matchMap;
  }, [candidates]);

  const selectedCandidateInBatchMatch = selectedCandidateId
    ? inBatchMatches.get(selectedCandidateId)
    : undefined;

  useEffect(() => {
    if (!isOpen || !jobId) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const res = await ingestApi.getJobCandidates(jobId, "phase_1_triage");
        setCandidates(res.candidates || []);
        if (res.candidates && res.candidates.length > 0) {
          setSelectedCandidateId(res.candidates[0].id);
        }
      } catch (err: any) {
        showToast(err?.message || "Failed to load staged candidates", "error");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isOpen, jobId, showToast]);

  // Sync edit form when selected candidate changes
  useEffect(() => {
    setIsPickingOnMap(false);
    if (!selectedCandidateId) return;
    const selected = candidates.find((c) => c.id === selectedCandidateId);
    if (selected) {
      setEditForm({
        poi_name: selected.poi_name || "",
        street_address: selected.street_address || "",
        city: selected.city || "",
        state_province: selected.state_province || "",
        country: selected.country || "",
        latitude:
          selected.latitude != null ? String(Number(selected.latitude)) : "",
        longitude:
          selected.longitude != null ? String(Number(selected.longitude)) : "",
      });
    }
  }, [selectedCandidateId, candidates]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const handleDispositionChange = async (
    candidateId: string,
    newDisp: "accept" | "ignore" | "update_existing" | "sublocation" | "exclude",
  ) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, user_disposition: newDisp } : c,
      ),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, candidateId, {
          user_disposition: newDisp,
        });
      } catch (err: any) {
        showToast(`Failed to save disposition: ${err.message}`, "error");
      }
    }
  };

  const handleUpdateCoordinatesToggle = async (
    candidateId: string,
    updateCoords: boolean,
  ) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, update_coordinates: updateCoords } : c,
      ),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, candidateId, {
          update_coordinates: updateCoords,
        });
      } catch (err: any) {
        showToast(`Failed to toggle coordinate update: ${err.message}`, "error");
      }
    }
  };

  const handleMarkerClick = async (poi: ExistingPOIMarker) => {
    if (!selectedCandidateId) return;

    const selected = candidates.find((c) => c.id === selectedCandidateId);
    if (!selected) return;

    const disp = selected.user_disposition || selected.recommended_disposition;
    if (disp === "sublocation") {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === selectedCandidateId
            ? { ...c, parent_poi_id: poi.id, parent_poi_name: poi.name }
            : c,
        ),
      );

      if (jobId) {
        try {
          await ingestApi.updateCandidate(jobId, selectedCandidateId, {
            parent_poi_id: poi.id,
          });
          showToast(`Linked '${selected.poi_name}' to parent '${poi.name}'`, "success");
        } catch (err: any) {
          showToast(`Failed to link parent POI: ${err.message}`, "error");
        }
      }
    } else if (disp === "update_existing") {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === selectedCandidateId
            ? { ...c, matched_existing_poi_id: poi.id, matched_existing_poi_name: poi.name }
            : c,
        ),
      );

      if (jobId) {
        try {
          await ingestApi.updateCandidate(jobId, selectedCandidateId, {
            matched_existing_poi_id: poi.id,
          });
          showToast(`Matched '${selected.poi_name}' to existing POI '${poi.name}'`, "success");
        } catch (err: any) {
          showToast(`Failed to match existing POI: ${err.message}`, "error");
        }
      }
    }
  };

  const handleCoordinatesPicked = async (lat: number, lon: number) => {
    const latStr = lat.toFixed(6);
    const lonStr = lon.toFixed(6);
    setIsEditing(true);
    setEditForm((prev) => ({
      ...prev,
      latitude: latStr,
      longitude: lonStr,
    }));

    // If no address is specified, do a lookup to fill in (Requirement)
    const lacksAddress =
      (!editForm.street_address?.trim() && !editForm.city?.trim()) ||
      !editForm.country?.trim() ||
      editForm.country.trim().toLowerCase() === "unknown";

    if (lacksAddress) {
      await handleReverseGeocode(lat, lon);
    }
  };

  const handleReverseGeocode = async (latNum?: number, lonNum?: number) => {
    const lat = latNum ?? (editForm.latitude.trim() ? parseFloat(editForm.latitude) : NaN);
    const lon = lonNum ?? (editForm.longitude.trim() ? parseFloat(editForm.longitude) : NaN);

    if (isNaN(lat) || isNaN(lon)) {
      showToast("Please enter valid Latitude and Longitude to lookup address", "warning");
      return;
    }

    setIsReverseGeocoding(true);
    try {
      const res = await reverseGeocode(lat, lon);
      setEditForm((prev) => ({
        ...prev,
        street_address: prev.street_address.trim() || res.street || "",
        city:
          prev.city.trim() && prev.city.toLowerCase() !== "unknown"
            ? prev.city
            : res.city || "",
        state_province: prev.state_province.trim() || res.state_province || "",
        country:
          prev.country.trim() && prev.country.toLowerCase() !== "unknown"
            ? prev.country
            : res.country || "",
      }));
      showToast(
        `Resolved address: ${[res.street, res.city, res.state_province, res.country].filter(Boolean).join(", ")}`,
        "success",
      );
    } catch (err: any) {
      console.warn("Reverse geocode failed:", err);
      showToast("Could not resolve address for coordinates", "info");
    } finally {
      setIsReverseGeocoding(false);
    }
  };

  const handleForwardGeocode = async () => {
    const addressParts = [
      editForm.street_address.trim(),
      editForm.city.trim(),
      editForm.state_province.trim(),
      editForm.country.trim() && editForm.country.toLowerCase() !== "unknown"
        ? editForm.country.trim()
        : "",
    ].filter(Boolean);

    let query = addressParts.join(", ");
    if (!query && editForm.poi_name.trim()) {
      query = editForm.poi_name.trim();
    } else if (addressParts.length > 0 && editForm.poi_name.trim()) {
      query = `${editForm.poi_name.trim()}, ${query}`;
    }

    if (!query) {
      showToast("Please enter a POI Name or Address to lookup coordinates", "warning");
      return;
    }

    setIsForwardGeocoding(true);
    try {
      const res = await forwardGeocode(query);
      if (res.latitude != null && res.longitude != null) {
        setEditForm((prev) => ({
          ...prev,
          latitude: String(res.latitude!.toFixed(6)),
          longitude: String(res.longitude!.toFixed(6)),
          street_address: prev.street_address.trim() || res.street || prev.street_address,
          city:
            prev.city.trim() && prev.city.toLowerCase() !== "unknown"
              ? prev.city
              : res.city || prev.city,
          state_province:
            prev.state_province.trim() || res.state_province || prev.state_province,
          country:
            prev.country.trim() && prev.country.toLowerCase() !== "unknown"
              ? prev.country
              : res.country || prev.country,
        }));
        showToast(
          `Located coordinates: (${res.latitude.toFixed(5)}, ${res.longitude.toFixed(5)})`,
          "success",
        );
      } else {
        // Fallback: search with POI name + city
        const fallbackQuery = [editForm.poi_name.trim(), editForm.city.trim()]
          .filter(Boolean)
          .join(", ");
        if (fallbackQuery && fallbackQuery !== query) {
          const fallbackRes = await forwardGeocode(fallbackQuery);
          if (fallbackRes.latitude != null && fallbackRes.longitude != null) {
            setEditForm((prev) => ({
              ...prev,
              latitude: String(fallbackRes.latitude!.toFixed(6)),
              longitude: String(fallbackRes.longitude!.toFixed(6)),
            }));
            showToast(
              `Located coordinates: (${fallbackRes.latitude.toFixed(5)}, ${fallbackRes.longitude.toFixed(5)})`,
              "success",
            );
            return;
          }
        }
        showToast(
          `No coordinates found for '${query}'. Try entering more address details or click 'Pick on Map'.`,
          "warning",
        );
      }
    } catch (err: any) {
      showToast(`Address lookup failed: ${err.message || err}`, "error");
    } finally {
      setIsForwardGeocoding(false);
    }
  };

  const handleOpenFolder = async (folderPath?: string) => {
    if (!folderPath || !folderPath.trim()) {
      showToast("No folder directory specified for this entry.", "info");
      return;
    }

    const cleanPath = folderPath.trim();
    // 1. Try local gateway endpoint first (direct native OS launch since gateway runs on localhost)
    try {
      const res = await apiFetch<{ success: boolean; path: string }>("/api/system/open-folder", {
        method: "POST",
        body: JSON.stringify({ path: cleanPath }),
      });
      if (res?.success) {
        showToast(`Opened folder in File Explorer: ${cleanPath}`, "success");
        return;
      }
    } catch (err: any) {
      console.warn("Local gateway open-folder endpoint failed, attempting extension bridge:", err);
    }

    // 2. Try Chrome extension native host bridge fallback
    try {
      const extRes = await openLocalFolder(cleanPath);
      if (extRes.success) {
        showToast(extRes.toastMessage || `Opened folder: ${cleanPath}`, "success");
      } else {
        const msg = extRes.toastMessage || `Could not open folder on disk: ${cleanPath}`;
        showToast(msg, "warning");
      }
    } catch (err: any) {
      showToast(`Unable to open folder: ${err.message || cleanPath}`, "warning");
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedCandidateId || !jobId) return;

    const latVal = editForm.latitude.trim() ? parseFloat(editForm.latitude) : null;
    const lonVal = editForm.longitude.trim() ? parseFloat(editForm.longitude) : null;

    try {
      const updated = await ingestApi.updateCandidate(jobId, selectedCandidateId, {
        poi_name: editForm.poi_name.trim(),
        street_address: editForm.street_address.trim() || undefined,
        city: editForm.city.trim() || undefined,
        state_province: editForm.state_province.trim() || undefined,
        country: editForm.country.trim() || undefined,
        latitude: latVal !== null && !isNaN(latVal) ? latVal : undefined,
        longitude: lonVal !== null && !isNaN(lonVal) ? lonVal : undefined,
      });

      setCandidates((prev) =>
        prev.map((c) =>
          c.id === selectedCandidateId
            ? {
                ...c,
                poi_name: updated.poi_name,
                street_address: updated.street_address,
                city: updated.city,
                state_province: updated.state_province,
                country: updated.country,
                latitude: updated.latitude,
                longitude: updated.longitude,
              }
            : c,
        ),
      );

      setIsEditing(false);
      setIsPickingOnMap(false);
      showToast(`Updated '${updated.poi_name}' successfully`, "success");
    } catch (err: any) {
      showToast(`Failed to save edit: ${err.message}`, "error");
    }
  };

  const handleSaveAndClose = () => {
    showToast("Progress saved to temporary storage. You can resume anytime.", "info");
    onClose();
  };

  const handleDiscard = async () => {
    if (!jobId) {
      onClose();
      return;
    }

    if (
      process.env.NODE_ENV !== "test" &&
      typeof window !== "undefined" &&
      typeof window.confirm === "function"
    ) {
      try {
        if (!window.confirm("Permanently discard this import session? All staged progress will be wiped.")) {
          return;
        }
      } catch {
        // Fallback for environments where window.confirm is unavailable
      }
    }

    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase1(jobId);
      showToast("Import discarded. Staged records cleared.", "info");
      onClose();
    } catch (err: any) {
      showToast(`Cancellation failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = handleDiscard;

  const handleProceed = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const res = await ingestApi.proceedPhase1(jobId);
      showToast(
        `Advanced ${res.advanced_count} POIs to Phase 2 (${res.ignored_count} ignored)`,
        "success",
      );
      if (onProceedToPhase2) {
        onProceedToPhase2(jobId);
      } else if (onTriageComplete) {
        onTriageComplete();
      }
    } catch (err: any) {
      showToast(`Failed to proceed to Phase 2: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered and sorted candidate list
  const filteredAndSortedCandidates = useMemo(() => {
    let result = [...candidates];

    // Search filter
    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase();
      result = result.filter(
        (c) =>
          c.poi_name?.toLowerCase().includes(q) ||
          c.city?.toLowerCase().includes(q) ||
          c.state_province?.toLowerCase().includes(q) ||
          c.country?.toLowerCase().includes(q) ||
          c.street_address?.toLowerCase().includes(q) ||
          c.photo_directory?.toLowerCase().includes(q),
      );
    }

    // Disposition filter (multi-select)
    if (selectedDispositions.length < ALL_DISPOSITIONS.length) {
      result = result.filter((c) => {
        const disp = c.user_disposition || c.recommended_disposition;
        return disp ? selectedDispositions.includes(disp) : false;
      });
    }

    // Sorting
    result.sort((a, b) => {
      // 1. Per-column sort overrides default sort logic if active
      if (sortField) {
        let cmp = 0;
        if (sortField === "poi_name") {
          cmp = (a.poi_name || "").localeCompare(b.poi_name || "");
        } else if (sortField === "city") {
          cmp = (a.city || "").localeCompare(b.city || "");
        } else if (sortField === "state_province") {
          cmp = (a.state_province || "").localeCompare(b.state_province || "");
        } else if (sortField === "country") {
          cmp = (a.country || "").localeCompare(b.country || "");
        } else if (sortField === "confidence_score") {
          cmp = (a.confidence_score || 0) - (b.confidence_score || 0);
        } else if (sortField === "disposition") {
          const da = a.user_disposition || a.recommended_disposition || "";
          const db = b.user_disposition || b.recommended_disposition || "";
          cmp = da.localeCompare(db);
        } else {
          cmp = (a.row_index || 0) - (b.row_index || 0);
        }
        return sortDirection === "asc" ? cmp : -cmp;
      }

      // 2. Default priority sort logic
      if (sortPriority === "location") {
        // "Location" priority: Country -> State/Province -> City/Town -> POI Name
        const cCountry = (a.country || "").localeCompare(b.country || "");
        if (cCountry !== 0) return cCountry;

        const cState = (a.state_province || "").localeCompare(b.state_province || "");
        if (cState !== 0) return cState;

        const cCity = (a.city || "").localeCompare(b.city || "");
        if (cCity !== 0) return cCity;

        const cPoi = (a.poi_name || "").localeCompare(b.poi_name || "");
        if (cPoi !== 0) return cPoi;

        return (a.row_index || 0) - (b.row_index || 0);
      } else {
        // "POI" priority: POI Name Only
        const cPoi = (a.poi_name || "").localeCompare(b.poi_name || "");
        if (cPoi !== 0) return cPoi;

        return (a.row_index || 0) - (b.row_index || 0);
      }
    });

    return result;
  }, [candidates, searchFilter, selectedDispositions, ALL_DISPOSITIONS, sortPriority, sortField, sortDirection]);

  // Check whether filtering (by search query or disposition multi-select) is active
  const isFiltering =
    searchFilter.trim().length > 0 ||
    selectedDispositions.length < ALL_DISPOSITIONS.length;

  const handleToggleDisposition = (key: string) => {
    setSelectedDispositions((prev) =>
      prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key],
    );
  };

  const handleSelectAllDispositions = () => {
    setSelectedDispositions(ALL_DISPOSITIONS.map((d) => d.key));
  };

  const handleDeselectAllDispositions = () => {
    setSelectedDispositions([]);
  };

  const handleApplyBulkEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedCandidateIds.length === 0) return;

    const updates: Partial<{ country: string; state_province: string; city: string }> = {};
    if (bulkCountry.trim()) updates.country = bulkCountry.trim();
    if (bulkStateProvince.trim()) updates.state_province = bulkStateProvince.trim();
    if (bulkCity.trim()) updates.city = bulkCity.trim();

    if (Object.keys(updates).length === 0) {
      showToast("No values provided. Please enter at least one field to bulk edit.", "info");
      return;
    }

    if (!jobId) return;

    setIsBulkUpdating(true);
    try {
      await Promise.all(
        selectedCandidateIds.map((id) =>
          ingestApi.updateCandidate(jobId, id, updates),
        ),
      );

      setCandidates((prev) =>
        prev.map((c) =>
          selectedCandidateIds.includes(c.id) ? { ...c, ...updates } : c,
        ),
      );

      showToast(`Bulk updated ${selectedCandidateIds.length} POI(s) successfully`, "success");
      setIsBulkEditOpen(false);
      setSelectedCandidateIds([]);
      setBulkCountry("");
      setBulkStateProvince("");
      setBulkCity("");
    } catch (err: any) {
      showToast(`Bulk update failed: ${err.message}`, "error");
    } finally {
      setIsBulkUpdating(false);
    }
  };

  // Breakdown statistics
  const stats = useMemo(() => {
    let accept = 0;
    let sub = 0;
    let update = 0;
    let ignore = 0;
    let exclude = 0;
    candidates.forEach((c) => {
      const d = c.user_disposition || c.recommended_disposition;
      if (d === "accept") accept++;
      else if (d === "sublocation") sub++;
      else if (d === "update_existing") update++;
      else if (d === "ignore") ignore++;
      else if (d === "exclude") exclude++;
    });
    return { accept, sub, update, ignore, exclude };
  }, [candidates]);

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);

  // Active coordinates of currently selected candidate (reflecting inline edits if in edit mode)
  const activeCandidateLat = isEditing && editForm.latitude
    ? parseFloat(editForm.latitude)
    : selectedCandidate?.latitude;
  const activeCandidateLon = isEditing && editForm.longitude
    ? parseFloat(editForm.longitude)
    : selectedCandidate?.longitude;

  const hasActiveCoords =
    activeCandidateLat !== null &&
    activeCandidateLat !== undefined &&
    activeCandidateLon !== null &&
    activeCandidateLon !== undefined &&
    !isNaN(Number(activeCandidateLat)) &&
    !isNaN(Number(activeCandidateLon));

  // Dynamically compute nearby POIs from BOTH database (existingPOIs) and this CSV batch (candidates)
  const nearbyPOIs: NearbyPOIMarker[] = useMemo(() => {
    if (!hasActiveCoords || activeCandidateLat == null || activeCandidateLon == null) {
      return [];
    }
    const maxMeters = nearbyRadiusKm * 1000;
    const list: NearbyPOIMarker[] = [];

    // 1. Check existing library POIs from database
    existingPOIs.forEach((poi) => {
      if (poi.latitude != null && poi.longitude != null) {
        const dist = computeDistanceMeters(
          Number(activeCandidateLat),
          Number(activeCandidateLon),
          poi.latitude,
          poi.longitude,
        );
        if (dist <= maxMeters) {
          list.push({
            id: poi.id,
            name: poi.name,
            latitude: poi.latitude,
            longitude: poi.longitude,
            source: "db",
            distanceMeters: dist,
          });
        }
      }
    });

    // 2. Check other staged candidates in this CSV batch
    candidates.forEach((cand) => {
      if (
        cand.id !== selectedCandidate?.id &&
        cand.latitude != null &&
        cand.longitude != null
      ) {
        const dist = computeDistanceMeters(
          Number(activeCandidateLat),
          Number(activeCandidateLon),
          Number(cand.latitude),
          Number(cand.longitude),
        );
        if (dist <= maxMeters) {
          list.push({
            id: cand.id,
            name: cand.poi_name,
            latitude: Number(cand.latitude),
            longitude: Number(cand.longitude),
            source: "csv",
            distanceMeters: dist,
          });
        }
      }
    });

    return list.sort((a, b) => a.distanceMeters - b.distanceMeters);
  }, [
    hasActiveCoords,
    activeCandidateLat,
    activeCandidateLon,
    nearbyRadiusKm,
    existingPOIs,
    candidates,
    selectedCandidate?.id,
  ]);

  const handleSelectParentPOI = async (poi: NearbyPOIMarker) => {
    if (!selectedCandidate) return;

    const prevCandidate = selectedCandidate;
    const updatedCandidate: CandidateItem = {
      ...selectedCandidate,
      parent_poi_id: poi.id,
      parent_poi_name: poi.name,
      user_disposition: "sublocation",
    };

    setCandidates((prev) =>
      prev.map((c) => (c.id === selectedCandidate.id ? updatedCandidate : c)),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, selectedCandidate.id, {
          parent_poi_id: poi.id,
          user_disposition: "sublocation",
        });
        showToast(
          `Linked '${poi.name}' (${poi.source === "db" ? "Database" : "CSV Batch"}) as Parent POI`,
          "success",
        );
      } catch (err: any) {
        setCandidates((prev) =>
          prev.map((c) => (c.id === selectedCandidate.id ? prevCandidate : c)),
        );
        showToast(`Failed to link parent POI: ${err.message}`, "error");
      }
    }
  };

  const handleUnlinkParentPOI = async () => {
    if (!selectedCandidate) return;

    const prevCandidate = selectedCandidate;
    const updatedCandidate: CandidateItem = {
      ...selectedCandidate,
      parent_poi_id: null,
      parent_poi_name: null,
      user_disposition: "accept",
    };

    setCandidates((prev) =>
      prev.map((c) => (c.id === selectedCandidate.id ? updatedCandidate : c)),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, selectedCandidate.id, {
          parent_poi_id: null,
          user_disposition: "accept",
        });
        showToast("Unlinked parent POI", "info");
      } catch (err: any) {
        setCandidates((prev) =>
          prev.map((c) => (c.id === selectedCandidate.id ? prevCandidate : c)),
        );
        showToast(`Failed to unlink parent POI: ${err.message}`, "error");
      }
    }
  };
  const renderPoiNameTh = () => (
    <th
      key="th-poi"
      onClick={() => handleSort("poi_name")}
      style={{
        padding: "10px 12px",
        fontWeight: 700,
        cursor: "pointer",
        userSelect: "none",
        minWidth: "220px",
        borderBottom: "1px solid #e2e8f0",
        color: "#0f172a",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        POI Name {renderSortIcon("poi_name")}
      </div>
    </th>
  );

  const renderCountryTh = () => (
    <th
      key="th-country"
      onClick={() => handleSort("country")}
      style={{
        padding: "10px 12px",
        fontWeight: 600,
        cursor: "pointer",
        userSelect: "none",
        minWidth: "120px",
        borderBottom: "1px solid #e2e8f0",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        Country {renderSortIcon("country")}
      </div>
    </th>
  );

  const renderStateTh = () => (
    <th
      key="th-state"
      onClick={() => handleSort("state_province")}
      style={{
        padding: "10px 12px",
        fontWeight: 600,
        cursor: "pointer",
        userSelect: "none",
        minWidth: "130px",
        borderBottom: "1px solid #e2e8f0",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        State / Province {renderSortIcon("state_province")}
      </div>
    </th>
  );

  const renderCityTh = () => (
    <th
      key="th-city"
      onClick={() => handleSort("city")}
      style={{
        padding: "10px 12px",
        fontWeight: 600,
        cursor: "pointer",
        userSelect: "none",
        minWidth: "130px",
        borderBottom: "1px solid #e2e8f0",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        City / Town {renderSortIcon("city")}
      </div>
    </th>
  );

  const renderPoiNameTd = (cand: CandidateItem) => (
    <td key="td-poi" style={{ padding: "10px 12px", color: "#0f172a" }}>
      <div style={{ fontWeight: 700, fontSize: "13px", color: "#0f172a" }}>
        {cand.poi_name}
      </div>
      {cand.street_address && (
        <div
          style={{
            fontSize: "11px",
            color: "#64748b",
            fontWeight: 400,
            marginTop: "2px",
          }}
        >
          {cand.street_address}
        </div>
      )}
    </td>
  );

  const renderCountryTd = (cand: CandidateItem) => (
    <td key="td-country" style={{ padding: "10px 12px", color: "#334155" }}>
      {cand.country || <span style={{ color: "#94a3b8" }}>—</span>}
    </td>
  );

  const renderStateTd = (cand: CandidateItem) => (
    <td key="td-state" style={{ padding: "10px 12px", color: "#334155" }}>
      {cand.state_province || <span style={{ color: "#94a3b8" }}>—</span>}
    </td>
  );

  const renderCityTd = (cand: CandidateItem) => (
    <td key="td-city" style={{ padding: "10px 12px", color: "#334155" }}>
      {cand.city || <span style={{ color: "#94a3b8" }}>—</span>}
    </td>
  );

  const selectedDisp = selectedCandidate
    ? selectedCandidate.user_disposition || selectedCandidate.recommended_disposition
    : "accept";

  const renderSortIcon = (field: SortField) => {
    if (sortField) {
      if (sortField !== field) {
        return <ArrowUpDown size={13} style={{ opacity: 0.35, marginLeft: "4px" }} />;
      }
      return sortDirection === "asc" ? (
        <ArrowUp size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />
      ) : (
        <ArrowDown size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />
      );
    }

    // Default indicator matching sortPriority
    if (sortPriority === "poi" && field === "poi_name") {
      return <ArrowUp size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />;
    }
    if (sortPriority === "location" && field === "country") {
      return <ArrowUp size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />;
    }
    return <ArrowUpDown size={13} style={{ opacity: 0.35, marginLeft: "4px" }} />;
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={handleSaveAndClose}
      title="Phase 1: Validation & Triage"
      maxWidth="min(1500px, 96vw)"
      closeOnBackdropClick={false}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "78vh",
          fontFamily: "var(--font-family-body, sans-serif)",
          color: "#0f172a",
        }}
        data-testid="phase1-triage-modal"
      >
        {isLoading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flex: 1,
              color: "#64748b",
            }}
          >
            <span>Loading staged candidates...</span>
          </div>
        ) : (
          <>
            {/* Top explanation & search bar */}
            <div
              style={{
                padding: "10px 14px",
                marginBottom: "12px",
                backgroundColor: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "#1e40af" }}>
                <Compass size={18} color="#2563eb" style={{ flexShrink: 0 }} />
                <span>
                  Verify candidate locations, inspect geographic administrative levels, set dispositions, and define hierarchy links before proceeding to enrichment.
                </span>
              </div>
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  padding: "4px 10px",
                  backgroundColor: "#dbeafe",
                  color: "#1e3a8a",
                  borderRadius: "6px",
                  display: "flex",
                  gap: "6px",
                }}
              >
                <span>{candidates.length} Total Candidates</span>
              </div>
            </div>

            {/* Filter and Search controls */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "12px",
                gap: "12px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1, minWidth: "260px" }}>
                <div
                  style={{
                    position: "relative",
                    display: "flex",
                    alignItems: "center",
                    flex: 1,
                    maxWidth: "380px",
                  }}
                >
                  <Search
                    size={15}
                    style={{ position: "absolute", left: "10px", color: "#94a3b8" }}
                  />
                  <input
                    type="text"
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    placeholder="Search candidate name, city, state, country..."
                    style={{
                      width: "100%",
                      padding: "7px 10px 7px 32px",
                      fontSize: "13px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      outline: "none",
                      backgroundColor: "#ffffff",
                    }}
                  />
                </div>

                {/* Multi-select Disposition Dropdown */}
                <div style={{ position: "relative" }} ref={dispositionDropdownRef}>
                  <button
                    type="button"
                    onClick={() => setIsDispositionDropdownOpen((prev) => !prev)}
                    data-testid="disposition-filter-button"
                    style={{
                      padding: "7px 12px",
                      fontSize: "13px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      backgroundColor: "#ffffff",
                      color: "#334155",
                      fontWeight: 500,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      cursor: "pointer",
                      height: "34px",
                    }}
                  >
                    <span>
                      {selectedDispositions.length === ALL_DISPOSITIONS.length
                        ? `All Dispositions (${candidates.length})`
                        : selectedDispositions.length === 0
                        ? "No Dispositions Selected (0)"
                        : `Dispositions (${selectedDispositions.length}/${ALL_DISPOSITIONS.length})`}
                    </span>
                    <ChevronDown size={14} color="#64748b" />
                  </button>

                  {isDispositionDropdownOpen && (
                    <div
                      data-testid="disposition-filter-dropdown"
                      style={{
                        position: "absolute",
                        top: "calc(100% + 4px)",
                        left: 0,
                        zIndex: 50,
                        backgroundColor: "#ffffff",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)",
                        minWidth: "220px",
                        padding: "8px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          paddingBottom: "6px",
                          borderBottom: "1px solid #f1f5f9",
                          marginBottom: "4px",
                          fontSize: "11px",
                        }}
                      >
                        <span style={{ fontWeight: 600, color: "#64748b" }}>Filter Dispositions</span>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            type="button"
                            onClick={handleSelectAllDispositions}
                            data-testid="select-all-dispositions-btn"
                            style={{
                              background: "none",
                              border: "none",
                              color: "#2563eb",
                              fontSize: "11px",
                              fontWeight: 600,
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            All
                          </button>
                          <span style={{ color: "#cbd5e1" }}>|</span>
                          <button
                            type="button"
                            onClick={handleDeselectAllDispositions}
                            data-testid="deselect-all-dispositions-btn"
                            style={{
                              background: "none",
                              border: "none",
                              color: "#64748b",
                              fontSize: "11px",
                              fontWeight: 600,
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            Clear
                          </button>
                        </div>
                      </div>

                      {ALL_DISPOSITIONS.map((disp) => {
                        const isChecked = selectedDispositions.includes(disp.key);
                        const count =
                          disp.key === "accept"
                            ? stats.accept
                            : disp.key === "sublocation"
                            ? stats.sub
                            : disp.key === "update_existing"
                            ? stats.update
                            : disp.key === "ignore"
                            ? stats.ignore
                            : stats.exclude;

                        return (
                          <label
                            key={disp.key}
                            data-testid={`disposition-option-${disp.key}`}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              padding: "6px 8px",
                              borderRadius: "4px",
                              cursor: "pointer",
                              backgroundColor: isChecked ? "#f8fafc" : "transparent",
                              fontSize: "12px",
                              color: "#334155",
                              userSelect: "none",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <input
                                type="checkbox"
                                data-testid={`disposition-checkbox-${disp.key}`}
                                checked={isChecked}
                                onChange={() => handleToggleDisposition(disp.key)}
                                style={{ cursor: "pointer" }}
                              />
                              <span style={{ fontWeight: isChecked ? 600 : 400 }}>{disp.label}</span>
                            </div>
                            <span
                              style={{
                                fontSize: "11px",
                                color: "#64748b",
                                backgroundColor: "#f1f5f9",
                                padding: "1px 6px",
                                borderRadius: "9999px",
                              }}
                            >
                              {count}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Bulk Edit Actions */}
                {selectedCandidateIds.length > 0 && (
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <button
                      type="button"
                      onClick={() => setIsBulkEditOpen(true)}
                      data-testid="bulk-edit-button"
                      style={{
                        padding: "7px 12px",
                        fontSize: "13px",
                        fontWeight: 600,
                        border: "none",
                        borderRadius: "6px",
                        backgroundColor: "#2563eb",
                        color: "#ffffff",
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                      }}
                    >
                      <Edit2 size={13} />
                      <span>Bulk Edit ({selectedCandidateIds.length})</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedCandidateIds([])}
                      data-testid="deselect-all-button"
                      style={{
                        padding: "7px 10px",
                        fontSize: "12px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "6px",
                        backgroundColor: "#ffffff",
                        color: "#64748b",
                        cursor: "pointer",
                      }}
                    >
                      Deselect
                    </button>
                  </div>
                )}

                {/* Sort Priority Dropdown */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <label
                    htmlFor="sort-priority-select"
                    style={{ fontSize: "12px", fontWeight: 600, color: "#475569", whiteSpace: "nowrap" }}
                  >
                    Sort Priority:
                  </label>
                  <select
                    id="sort-priority-select"
                    data-testid="sort-priority-select"
                    value={sortPriority}
                    onChange={(e) => {
                      setSortPriority(e.target.value as SortPriority);
                      setSortField(null);
                      setSortDirection("asc");
                    }}
                    style={{
                      padding: "7px 12px",
                      fontSize: "13px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      backgroundColor: "#ffffff",
                      color: "#1e293b",
                      fontWeight: 600,
                    }}
                  >
                    <option value="poi">POI</option>
                    <option value="location">Location</option>
                  </select>
                </div>
              </div>

              <div style={{ fontSize: "12px", color: "#64748b" }}>
                Showing <strong>{filteredAndSortedCandidates.length}</strong> of {candidates.length} candidates
              </div>
            </div>

            {/* Split view: Left Table (65%) + Right Interactive Panel (35%) */}
            <div style={{ display: "flex", flex: 1, gap: "16px", overflow: "hidden" }}>
              {/* Candidates Table Container with Horizontal Scroll */}
              <div
                style={{
                  flex: 1,
                  overflowX: "auto",
                  overflowY: "auto",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  backgroundColor: "#ffffff",
                }}
              >
                <table
                  style={{
                    minWidth: "1450px",
                    width: "100%",
                    textAlign: "left",
                    fontSize: "13px",
                    borderCollapse: "separate",
                    borderSpacing: 0,
                  }}
                  data-testid="candidates-table"
                >
                  <thead
                    style={{
                      backgroundColor: "#f8fafc",
                      color: "#475569",
                      position: "sticky",
                      top: 0,
                      zIndex: 10,
                      borderBottom: "1px solid #e2e8f0",
                    }}
                  >
                    <tr>
                      <th
                        style={{
                          width: "44px",
                          padding: "10px 12px",
                          borderBottom: "1px solid #e2e8f0",
                          textAlign: "center",
                        }}
                      >
                        <input
                          type="checkbox"
                          data-testid="select-all-candidates-checkbox"
                          aria-label="Select all candidates"
                          checked={
                            filteredAndSortedCandidates.length > 0 &&
                            filteredAndSortedCandidates.every((c) =>
                              selectedCandidateIds.includes(c.id),
                            )
                          }
                          onChange={(e) => {
                            if (e.target.checked) {
                              const visibleIds = filteredAndSortedCandidates.map((c) => c.id);
                              setSelectedCandidateIds((prev) =>
                                Array.from(new Set([...prev, ...visibleIds])),
                              );
                            } else {
                              const visibleIdSet = new Set(
                                filteredAndSortedCandidates.map((c) => c.id),
                              );
                              setSelectedCandidateIds((prev) =>
                                prev.filter((id) => !visibleIdSet.has(id)),
                              );
                            }
                          }}
                          style={{ cursor: "pointer", width: "15px", height: "15px" }}
                        />
                      </th>
                      {sortPriority === "location" ? (
                        <>
                          {renderCountryTh()}
                          {renderStateTh()}
                          {renderCityTh()}
                          {renderPoiNameTh()}
                        </>
                      ) : (
                        <>
                          {renderPoiNameTh()}
                          {renderCountryTh()}
                          {renderStateTh()}
                          {renderCityTh()}
                        </>
                      )}
                      <th
                        onClick={() => handleSort("confidence_score")}
                        style={{
                          padding: "10px 12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          userSelect: "none",
                          minWidth: "100px",
                          borderBottom: "1px solid #e2e8f0",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center" }}>
                          Confidence {renderSortIcon("confidence_score")}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort("disposition")}
                        style={{
                          padding: "10px 12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          userSelect: "none",
                          minWidth: "160px",
                          borderBottom: "1px solid #e2e8f0",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center" }}>
                          Disposition {renderSortIcon("disposition")}
                        </div>
                      </th>
                      <th
                        style={{
                          padding: "10px 12px",
                          fontWeight: 600,
                          minWidth: "160px",
                          borderBottom: "1px solid #e2e8f0",
                        }}
                      >
                        Location / Hierarchy
                      </th>
                      <th
                        style={{
                          padding: "10px 12px",
                          fontWeight: 600,
                          minWidth: "450px",
                          borderBottom: "1px solid #e2e8f0",
                        }}
                      >
                        Directory / Dates
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAndSortedCandidates.length === 0 ? (
                      <tr>
                        <td
                          colSpan={10}
                          style={{
                            padding: "32px",
                            textAlign: "center",
                            color: "#94a3b8",
                            fontStyle: "italic",
                          }}
                        >
                          No candidate records match your current filter criteria.
                        </td>
                      </tr>
                    ) : (
                      filteredAndSortedCandidates.map((cand) => {
                        const isSelected = cand.id === selectedCandidateId;
                        const disp =
                          cand.user_disposition || cand.recommended_disposition;
                        const isUpdate = disp === "update_existing";
                        const isSublocation = disp === "sublocation";
                        const hasCoords =
                          cand.latitude !== null &&
                          cand.latitude !== undefined &&
                          cand.longitude !== null &&
                          cand.longitude !== undefined;

                        return (
                          <tr
                            key={cand.id}
                            onClick={() => {
                              setSelectedCandidateId(cand.id);
                              setIsEditing(true);
                            }}
                            style={{
                              backgroundColor: isSelected
                                ? "#eff6ff"
                                : selectedCandidateIds.includes(cand.id)
                                ? "#f8fafc"
                                : "transparent",
                              cursor: "pointer",
                              transition: "background-color 150ms",
                              borderBottom: "1px solid #f1f5f9",
                            }}
                            data-testid={`candidate-row-${cand.id}`}
                          >
                            <td
                              style={{
                                width: "44px",
                                padding: "10px 12px",
                                textAlign: "center",
                              }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="checkbox"
                                data-testid={`select-candidate-${cand.id}`}
                                aria-label={`Select ${cand.poi_name}`}
                                checked={selectedCandidateIds.includes(cand.id)}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  setSelectedCandidateIds((prev) =>
                                    prev.includes(cand.id)
                                      ? prev.filter((id) => id !== cand.id)
                                      : [...prev, cand.id],
                                  );
                                }}
                                style={{ cursor: "pointer", width: "15px", height: "15px" }}
                              />
                            </td>
                            {sortPriority === "location" ? (
                              <>
                                {renderCountryTd(cand)}
                                {renderStateTd(cand)}
                                {renderCityTd(cand)}
                                {renderPoiNameTd(cand)}
                              </>
                            ) : (
                              <>
                                {renderPoiNameTd(cand)}
                                {renderCountryTd(cand)}
                                {renderStateTd(cand)}
                                {renderCityTd(cand)}
                              </>
                            )}

                            {/* Confidence */}
                            <td style={{ padding: "10px 12px" }}>
                              <span
                                style={{
                                  display: "inline-block",
                                  padding: "2px 8px",
                                  borderRadius: "12px",
                                  fontSize: "12px",
                                  fontWeight: 700,
                                  backgroundColor:
                                    cand.confidence_score >= 80
                                      ? "#dcfce7"
                                      : cand.confidence_score >= 50
                                      ? "#fef9c3"
                                      : "#fee2e2",
                                  color:
                                    cand.confidence_score >= 80
                                      ? "#166534"
                                      : cand.confidence_score >= 50
                                      ? "#854d0e"
                                      : "#991b1b",
                                }}
                              >
                                {cand.confidence_score}%
                              </span>
                            </td>

                            {/* Disposition Select */}
                            <td
                              style={{ padding: "10px 12px" }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <select
                                value={disp}
                                onChange={(e) =>
                                  handleDispositionChange(
                                    cand.id,
                                    e.target.value as any,
                                  )
                                }
                                style={{
                                  padding: "5px 8px",
                                  fontSize: "12px",
                                  border: "1px solid #cbd5e1",
                                  borderRadius: "6px",
                                  backgroundColor: "#ffffff",
                                  color: "#1e293b",
                                  fontWeight: 600,
                                }}
                                data-testid={`disposition-select-${cand.id}`}
                              >
                                <option value="accept">Accept</option>
                                <option value="sublocation">Sublocation</option>
                                <option value="update_existing">
                                  {cand.matched_existing_poi_id
                                    ? "Update Existing POI"
                                    : inBatchMatches.has(cand.id)
                                    ? "In-Batch Merge"
                                    : "Update Existing POI"}
                                </option>
                                <option value="ignore">Ignore</option>
                                <option value="exclude">Exclude</option>
                              </select>

                              {isUpdate && (
                                <label
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "6px",
                                    marginTop: "6px",
                                    fontSize: "11px",
                                    color: "#b45309",
                                    cursor: "pointer",
                                  }}
                                >
                                  <input
                                    type="checkbox"
                                    checked={cand.update_coordinates}
                                    onChange={(e) =>
                                      handleUpdateCoordinatesToggle(
                                        cand.id,
                                        e.target.checked,
                                      )
                                    }
                                    data-testid={`update-coords-toggle-${cand.id}`}
                                    style={{ cursor: "pointer" }}
                                  />
                                  <span>Update Coordinates</span>
                                </label>
                              )}
                            </td>

                            {/* Coordinates & Status */}
                            <td style={{ padding: "10px 12px", fontSize: "12px" }}>
                              {hasCoords ? (
                                <div style={{ display: "flex", alignItems: "center", gap: "4px", color: "#0284c7", fontWeight: 500 }}>
                                  <MapPin size={13} style={{ flexShrink: 0 }} />
                                  <span>
                                    {Number(cand.latitude).toFixed(4)}, {Number(cand.longitude).toFixed(4)}
                                  </span>
                                </div>
                              ) : (
                                <span style={{ color: "#ef4444", fontWeight: 600 }}>Missing Coordinates</span>
                              )}

                              {disp === "exclude" && (
                                <div
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    marginTop: "4px",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    backgroundColor: "#fee2e2",
                                    color: "#991b1b",
                                    fontWeight: 600,
                                    fontSize: "11px",
                                  }}
                                  data-testid={`excluded-badge-${cand.id}`}
                                >
                                  <ShieldAlert size={12} color="#dc2626" />
                                  <span>Excluded (Privacy Zone)</span>
                                </div>
                              )}

                              {isSublocation && (
                                <div style={{ marginTop: "4px", fontSize: "11px", color: "#7e22ce", fontWeight: 600 }}>
                                  {cand.parent_poi_name ? (
                                    <span>Parent: {cand.parent_poi_name}</span>
                                  ) : (
                                    <span style={{ fontStyle: "italic", color: "#a855f7" }}>
                                      Select parent in right panel
                                    </span>
                                  )}
                                </div>
                              )}

                              {isUpdate && (
                                <div style={{ marginTop: "4px", fontSize: "11px", fontWeight: 600 }}>
                                  {cand.matched_existing_poi_name ? (
                                    <span style={{ color: "#c2410c" }}>Target DB POI: {cand.matched_existing_poi_name}</span>
                                  ) : inBatchMatches.has(cand.id) ? (
                                    <span style={{ color: "#166534" }}>
                                      Merge into Row #{inBatchMatches.get(cand.id)!.row_index + 1} ({inBatchMatches.get(cand.id)!.poi_name})
                                    </span>
                                  ) : (
                                    <span style={{ fontStyle: "italic", color: "#ea580c" }}>
                                      Select target in right panel
                                    </span>
                                  )}
                                </div>
                              )}
                            </td>

                            {/* Directory / Dates */}
                            <td style={{ padding: "10px 12px", fontSize: "11px", color: "#64748b" }}>
                              {cand.photo_directory ? (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenFolder(cand.photo_directory);
                                  }}
                                  title={`Click to open folder in File Explorer:
${cand.photo_directory}`}
                                  data-testid={`open-folder-btn-${cand.id}`}
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "6px",
                                    maxWidth: "100%",
                                    whiteSpace: "nowrap",
                                    cursor: "pointer",
                                    padding: "3px 8px",
                                    borderRadius: "4px",
                                    backgroundColor: "#f1f5f9",
                                    border: "1px solid #e2e8f0",
                                    color: "#0369a1",
                                    fontSize: "11px",
                                    textAlign: "left",
                                    textDecoration: "none",
                                  }}
                                >
                                  <Folder size={12} style={{ color: "#0284c7", flexShrink: 0 }} />
                                  <span style={{ whiteSpace: "nowrap" }}>
                                    {cand.photo_directory}
                                  </span>
                                  <ExternalLink size={11} style={{ opacity: 0.7, flexShrink: 0 }} />
                                </button>
                              ) : (
                                <span style={{ color: "#94a3b8" }}>—</span>
                              )}
                              {cand.dates_visited && cand.dates_visited.length > 0 && (
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    marginTop: "3px",
                                    color: "#94a3b8",
                                  }}
                                >
                                  <Calendar size={12} style={{ flexShrink: 0 }} />
                                  <span>{cand.dates_visited.join(", ")}</span>
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Right Pane: Candidate Map, Editor & Hierarchy Selector */}
              <div
                style={{
                  width: "380px",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "14px",
                  backgroundColor: "#f8fafc",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  overflowY: "auto",
                }}
                data-testid="interactive-map-panel"
              >
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: "10px",
                    }}
                  >
                    <h4
                      style={{
                        fontSize: "12px",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "#475569",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <MapPin size={14} color="#64748b" />
                      {isEditing ? "Edit Candidate Details" : "Selected Candidate"}
                    </h4>

                    {selectedCandidate && !isEditing && (
                      <button
                        type="button"
                        onClick={() => setIsEditing(true)}
                        style={{
                          fontSize: "11px",
                          color: "#2563eb",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "3px",
                        }}
                      >
                        <Edit2 size={11} /> Edit
                      </button>
                    )}
                  </div>

                  {/* Interactive Mini Map */}
                  {selectedCandidate && (
                    <CandidateMiniMap
                      latitude={
                        isEditing
                          ? editForm.latitude
                            ? parseFloat(editForm.latitude)
                            : null
                          : selectedCandidate.latitude
                      }
                      longitude={
                        isEditing
                          ? editForm.longitude
                            ? parseFloat(editForm.longitude)
                            : null
                          : selectedCandidate.longitude
                      }
                      poiName={isEditing ? editForm.poi_name : selectedCandidate.poi_name}
                      existingPOIs={existingPOIs}
                      nearbyPOIs={nearbyPOIs}
                      onSelectNearbyPOI={handleSelectParentPOI}
                      onSelectExistingPOI={handleMarkerClick}
                      isPicking={isPickingOnMap}
                      onStartPicking={() => {
                        setIsEditing(true);
                        setIsPickingOnMap(true);
                      }}
                      onStopPicking={() => setIsPickingOnMap(false)}
                      onCoordinatesPicked={handleCoordinatesPicked}
                      fallbackCenter={batchFallbackCenter}
                    />
                  )}

                  {selectedCandidate ? (
                    isEditing ? (
                      /* Inline Candidate Form Editor */
                      <div
                        style={{
                          backgroundColor: "#ffffff",
                          padding: "12px",
                          borderRadius: "8px",
                          border: "1px solid #cbd5e1",
                          marginBottom: "12px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                          fontSize: "12px",
                        }}
                      >
                        <div>
                          <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                            POI Name
                          </label>
                          <input
                            type="text"
                            value={editForm.poi_name}
                            onChange={(e) => setEditForm({ ...editForm, poi_name: e.target.value })}
                            style={{
                              width: "100%",
                              padding: "5px 8px",
                              fontSize: "12px",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                            }}
                          />
                        </div>

                        <div>
                          <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                            Street Address
                          </label>
                          <input
                            type="text"
                            value={editForm.street_address}
                            onChange={(e) => setEditForm({ ...editForm, street_address: e.target.value })}
                            placeholder="Optional street address"
                            style={{
                              width: "100%",
                              padding: "5px 8px",
                              fontSize: "12px",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                            }}
                          />
                        </div>

                        <div style={{ display: "flex", gap: "8px" }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                              City / Town
                            </label>
                            <input
                              type="text"
                              value={editForm.city}
                              onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                              style={{
                                width: "100%",
                                padding: "5px 8px",
                                fontSize: "12px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                              }}
                            />
                          </div>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                              State / Province
                            </label>
                            <input
                              type="text"
                              value={editForm.state_province}
                              onChange={(e) => setEditForm({ ...editForm, state_province: e.target.value })}
                              style={{
                                width: "100%",
                                padding: "5px 8px",
                                fontSize: "12px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                              }}
                            />
                          </div>
                        </div>

                        <div>
                          <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                            Country
                          </label>
                          <input
                            type="text"
                            value={editForm.country}
                            onChange={(e) => setEditForm({ ...editForm, country: e.target.value })}
                            style={{
                              width: "100%",
                              padding: "5px 8px",
                              fontSize: "12px",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                            }}
                          />
                        </div>

                        {/* Forward Geocode Button: Lookup Coordinates from Address */}
                        <div>
                          <button
                            type="button"
                            onClick={handleForwardGeocode}
                            disabled={isForwardGeocoding}
                            data-testid="forward-geocode-btn"
                            style={{
                              width: "100%",
                              padding: "6px 10px",
                              backgroundColor: "#f8fafc",
                              border: "1px solid #cbd5e1",
                              borderRadius: "6px",
                              fontSize: "11px",
                              fontWeight: 600,
                              color: "#2563eb",
                              cursor: isForwardGeocoding ? "not-allowed" : "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: "5px",
                              transition: "background-color 0.15s ease",
                            }}
                          >
                            {isForwardGeocoding ? (
                              <>
                                <Loader2 size={12} className="animate-spin" />
                                <span>Looking up Address...</span>
                              </>
                            ) : (
                              <>
                                <Search size={12} />
                                <span>Lookup Coordinates from Address</span>
                              </>
                            )}
                          </button>
                        </div>

                        <div style={{ display: "flex", gap: "8px" }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                              Latitude
                            </label>
                            <input
                              type="number"
                              step="any"
                              value={editForm.latitude}
                              onChange={(e) => setEditForm({ ...editForm, latitude: e.target.value })}
                              placeholder="e.g. 41.8252"
                              style={{
                                width: "100%",
                                padding: "5px 8px",
                                fontSize: "12px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                              }}
                            />
                          </div>
                          <div style={{ flex: 1 }}>
                            <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#475569", marginBottom: "3px" }}>
                              Longitude
                            </label>
                            <input
                              type="number"
                              step="any"
                              value={editForm.longitude}
                              onChange={(e) => setEditForm({ ...editForm, longitude: e.target.value })}
                              placeholder="e.g. -88.3076"
                              style={{
                                width: "100%",
                                padding: "5px 8px",
                                fontSize: "12px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                              }}
                            />
                          </div>
                        </div>

                        {/* Coordinate Action Buttons: Pick on Map & Auto-fill Address */}
                        <div style={{ display: "flex", gap: "6px" }}>
                          <button
                            type="button"
                            onClick={() => setIsPickingOnMap((prev) => !prev)}
                            data-testid="pick-on-map-form-btn"
                            style={{
                              flex: 1,
                              padding: "5px 8px",
                              backgroundColor: isPickingOnMap ? "#eff6ff" : "#f8fafc",
                              border: `1px solid ${isPickingOnMap ? "#3b82f6" : "#cbd5e1"}`,
                              borderRadius: "6px",
                              fontSize: "11px",
                              fontWeight: 600,
                              color: isPickingOnMap ? "#1d4ed8" : "#334155",
                              cursor: "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: "4px",
                            }}
                          >
                            <Crosshair size={12} color="#2563eb" />
                            <span>{isPickingOnMap ? "Click on Map..." : "Pick on Map"}</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleReverseGeocode()}
                            disabled={isReverseGeocoding || (!editForm.latitude.trim() && !editForm.longitude.trim())}
                            data-testid="reverse-geocode-btn"
                            title="Reverse geocode current coordinates to fill address"
                            style={{
                              flex: 1,
                              padding: "5px 8px",
                              backgroundColor: "#f8fafc",
                              border: "1px solid #cbd5e1",
                              borderRadius: "6px",
                              fontSize: "11px",
                              fontWeight: 600,
                              color:
                                !editForm.latitude.trim() && !editForm.longitude.trim()
                                  ? "#94a3b8"
                                  : "#2563eb",
                              cursor:
                                isReverseGeocoding ||
                                (!editForm.latitude.trim() && !editForm.longitude.trim())
                                  ? "not-allowed"
                                  : "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: "4px",
                            }}
                          >
                            {isReverseGeocoding ? (
                              <>
                                <Loader2 size={12} className="animate-spin" />
                                <span>Resolving...</span>
                              </>
                            ) : (
                              <>
                                <RotateCw size={12} />
                                <span>Auto-fill Address</span>
                              </>
                            )}
                          </button>
                        </div>

                        {/* Directory / Dates Section with Open Folder button */}
                        {(selectedCandidate.photo_directory || (selectedCandidate.dates_visited && selectedCandidate.dates_visited.length > 0)) && (
                          <div
                            style={{
                              padding: "8px 10px",
                              backgroundColor: "#f8fafc",
                              borderRadius: "6px",
                              border: "1px solid #e2e8f0",
                              display: "flex",
                              flexDirection: "column",
                              gap: "6px",
                              marginTop: "2px",
                            }}
                          >
                            {selectedCandidate.photo_directory && (
                              <>
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    gap: "8px",
                                  }}
                                >
                                  <span
                                    style={{
                                      fontSize: "11px",
                                      fontWeight: 600,
                                      color: "#475569",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "4px",
                                    }}
                                  >
                                    <Folder size={12} color="#0284c7" />
                                    Directory:
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => handleOpenFolder(selectedCandidate.photo_directory)}
                                    data-testid="edit-details-open-folder-btn"
                                    title={`Open in File Explorer:
${selectedCandidate.photo_directory}`}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "5px",
                                      padding: "3px 8px",
                                      borderRadius: "4px",
                                      backgroundColor: "#f0f9ff",
                                      border: "1px solid #bae6fd",
                                      color: "#0369a1",
                                      fontSize: "11px",
                                      fontWeight: 600,
                                      cursor: "pointer",
                                      transition: "all 0.15s ease",
                                    }}
                                  >
                                    <Folder size={11} />
                                    <span>Open Folder</span>
                                  </button>
                                </div>
                                <div
                                  style={{
                                    fontSize: "11px",
                                    color: "#0369a1",
                                    wordBreak: "break-all",
                                    fontFamily: "monospace",
                                    backgroundColor: "#ffffff",
                                    padding: "4px 6px",
                                    borderRadius: "4px",
                                    border: "1px solid #e2e8f0",
                                  }}
                                >
                                  {selectedCandidate.photo_directory}
                                </div>
                              </>
                            )}

                            {selectedCandidate.dates_visited && selectedCandidate.dates_visited.length > 0 && (
                              <div
                                style={{
                                  fontSize: "11px",
                                  color: "#64748b",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Calendar size={11} color="#64748b" />
                                <span>Dates: {selectedCandidate.dates_visited.join(", ")}</span>
                              </div>
                            )}
                          </div>
                        )}

                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "6px", marginTop: "4px" }}>
                          <button
                            type="button"
                            onClick={() => {
                              setIsEditing(false);
                              setIsPickingOnMap(false);
                            }}
                            style={{
                              padding: "4px 10px",
                              fontSize: "11px",
                              border: "1px solid #cbd5e1",
                              borderRadius: "4px",
                              backgroundColor: "#ffffff",
                              cursor: "pointer",
                            }}
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            style={{
                              padding: "4px 12px",
                              fontSize: "11px",
                              fontWeight: 600,
                              border: "none",
                              borderRadius: "4px",
                              backgroundColor: "#2563eb",
                              color: "#ffffff",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                            }}
                          >
                            <Save size={12} /> Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Display Selected Candidate Details */
                      <div
                        style={{
                          backgroundColor: "#ffffff",
                          padding: "12px",
                          borderRadius: "8px",
                          border: "1px solid #e2e8f0",
                          fontSize: "12px",
                          marginBottom: "12px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "5px",
                        }}
                      >
                        <div style={{ fontWeight: 700, fontSize: "13px", color: "#0f172a" }}>
                          {selectedCandidate.poi_name}
                        </div>
                        {selectedCandidate.street_address && (
                          <div style={{ color: "#475569" }}>
                            {selectedCandidate.street_address}
                          </div>
                        )}
                        <div style={{ color: "#475569" }}>
                          {[
                            selectedCandidate.city,
                            selectedCandidate.state_province,
                            selectedCandidate.country,
                          ]
                            .filter(Boolean)
                            .join(", ") || "No address details available"}
                        </div>

                        {selectedCandidate.parent_poi_name && (
                          <div style={{ color: "#7e22ce", fontWeight: 600, marginTop: "2px" }}>
                            Parent POI: {selectedCandidate.parent_poi_name}
                          </div>
                        )}

                        {selectedCandidate.matched_existing_poi_name && (
                          <div style={{ color: "#c2410c", fontWeight: 600, marginTop: "2px" }}>
                            Matched POI: {selectedCandidate.matched_existing_poi_name}
                          </div>
                        )}

                        {selectedCandidate.photo_directory && (
                          <div style={{ marginTop: "6px" }}>
                            <button
                              type="button"
                              onClick={() => handleOpenFolder(selectedCandidate.photo_directory)}
                              data-testid="right-panel-open-folder-btn"
                              title={`Open in File Explorer:
${selectedCandidate.photo_directory}`}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                padding: "4px 8px",
                                fontSize: "11px",
                                fontWeight: 600,
                                color: "#0369a1",
                                backgroundColor: "#f0f9ff",
                                border: "1px solid #bae6fd",
                                borderRadius: "6px",
                                cursor: "pointer",
                                maxWidth: "100%",
                              }}
                            >
                              <Folder size={12} color="#0284c7" />
                              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                Open Folder in Explorer
                              </span>
                              <ExternalLink size={11} color="#0284c7" />
                            </button>
                          </div>
                        )}

                        {selectedCandidateInBatchMatch && (
                          <div
                            style={{
                              marginTop: "6px",
                              padding: "8px 10px",
                              backgroundColor: "#f0fdf4",
                              border: "1px solid #bbf7d0",
                              borderRadius: "6px",
                              fontSize: "11px",
                            }}
                          >
                            <div style={{ color: "#166534", fontWeight: 700 }}>
                              In-Batch Match: Row #{selectedCandidateInBatchMatch.row_index + 1} ({selectedCandidateInBatchMatch.poi_name})
                            </div>
                            {selectedCandidateInBatchMatch.photo_directory && (
                              <div style={{ color: "#4b5563", marginTop: "2px", overflow: "hidden", textOverflow: "ellipsis" }}>
                                Earlier Album: {selectedCandidateInBatchMatch.photo_directory}
                              </div>
                            )}
                            <div style={{ color: "#15803d", marginTop: "4px", fontSize: "10px" }}>
                              ℹ️ Shares identical name & location with Row #{selectedCandidateInBatchMatch.row_index + 1} in this CSV. Updating will merge their photo directories into a single POI.
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  ) : (
                    <div style={{ fontSize: "12px", color: "#94a3b8", fontStyle: "italic", marginBottom: "12px" }}>
                      No candidate selected. Click a row to inspect or edit.
                    </div>
                  )}

                  {/* Nearby POIs & Parent Selection Section */}
                  <div
                    style={{
                      marginTop: "12px",
                      borderTop: "1px solid #e2e8f0",
                      paddingTop: "12px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "8px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          color: "#1e293b",
                          display: "flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <Compass size={14} color="#2563eb" />
                        <span>Nearby POIs & Parent Selection</span>
                      </div>
                      {hasActiveCoords && (
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#2563eb",
                            backgroundColor: "#eff6ff",
                            padding: "2px 6px",
                            borderRadius: "4px",
                          }}
                        >
                          Radius: {nearbyRadiusKm} km
                        </span>
                      )}
                    </div>

                    {hasActiveCoords ? (
                      <>
                        {/* Search Radius Slider */}
                        <div
                          style={{
                            marginBottom: "10px",
                            backgroundColor: "#f8fafc",
                            padding: "8px 10px",
                            borderRadius: "6px",
                            border: "1px solid #e2e8f0",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "4px",
                              fontSize: "11px",
                              color: "#475569",
                            }}
                          >
                            <span>Search Radius</span>
                            <span style={{ fontWeight: 600 }}>{nearbyRadiusKm} km</span>
                          </div>
                          <input
                            type="range"
                            min="0.5"
                            max="50"
                            step="0.5"
                            value={nearbyRadiusKm}
                            onChange={(e) => setNearbyRadiusKm(parseFloat(e.target.value))}
                            data-testid="nearby-radius-slider"
                            style={{
                              width: "100%",
                              accentColor: "#2563eb",
                              cursor: "pointer",
                            }}
                          />
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              fontSize: "10px",
                              color: "#94a3b8",
                            }}
                          >
                            <span>0.5 km</span>
                            <span>25 km</span>
                            <span>50 km</span>
                          </div>
                        </div>

                        {/* Current Assigned Parent POI Banner */}
                        {(selectedCandidate?.parent_poi_id || selectedCandidate?.parent_poi_name) && (
                          <div
                            data-testid="current-parent-banner"
                            style={{
                              marginBottom: "10px",
                              padding: "8px 10px",
                              backgroundColor: "#f5f3ff",
                              border: "1px solid #ddd6fe",
                              borderRadius: "6px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                            }}
                          >
                            <div style={{ fontSize: "11px", color: "#6b21a8" }}>
                              <span style={{ fontWeight: 600 }}>Parent POI: </span>
                              <span style={{ fontWeight: 700 }}>
                                {selectedCandidate.parent_poi_name || selectedCandidate.parent_poi_id}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={handleUnlinkParentPOI}
                              data-testid="unlink-parent-btn"
                              style={{
                                padding: "2px 8px",
                                fontSize: "10px",
                                fontWeight: 600,
                                backgroundColor: "#ffffff",
                                color: "#dc2626",
                                border: "1px solid #fca5a5",
                                borderRadius: "4px",
                                cursor: "pointer",
                              }}
                            >
                              Unlink Parent
                            </button>
                          </div>
                        )}

                        {/* Legend & Count */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: "11px",
                            color: "#64748b",
                            marginBottom: "6px",
                          }}
                        >
                          <span>
                            <strong>{nearbyPOIs.length}</strong> proximate {nearbyPOIs.length === 1 ? "location" : "locations"}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                              <span
                                style={{
                                  width: "8px",
                                  height: "8px",
                                  borderRadius: "50%",
                                  backgroundColor: "#9333ea",
                                  display: "inline-block",
                                }}
                              />
                              Database
                            </span>
                            <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                              <span
                                style={{
                                  width: "8px",
                                  height: "8px",
                                  borderRadius: "50%",
                                  backgroundColor: "#d97706",
                                  display: "inline-block",
                                }}
                              />
                              CSV Batch
                            </span>
                          </div>
                        </div>

                        {/* Nearby POIs List */}
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                            maxHeight: "180px",
                            overflowY: "auto",
                          }}
                          data-testid="existing-poi-list"
                        >
                          {nearbyPOIs.length === 0 ? (
                            <div
                              style={{
                                fontSize: "12px",
                                color: "#64748b",
                                fontStyle: "italic",
                                padding: "8px",
                                textAlign: "center",
                                backgroundColor: "#f8fafc",
                                borderRadius: "6px",
                              }}
                            >
                              {selectedCandidateInBatchMatch
                                ? `No saved library POIs. Matched earlier CSV Row #${selectedCandidateInBatchMatch.row_index + 1} (${selectedCandidateInBatchMatch.poi_name}).`
                                : `No POIs found within ${nearbyRadiusKm} km. Try increasing the search radius above.`}
                            </div>
                          ) : (
                            nearbyPOIs.map((poi) => {
                              const isCurrentParent =
                                selectedCandidate?.parent_poi_id === poi.id ||
                                selectedCandidate?.parent_poi_name === poi.name;

                              return (
                                <div
                                  key={`${poi.source}-${poi.id}`}
                                  data-testid={`nearby-poi-${poi.id}`}
                                  style={{
                                    padding: "8px 10px",
                                    borderRadius: "6px",
                                    border: isCurrentParent ? "1px solid #a855f7" : "1px solid #cbd5e1",
                                    backgroundColor: isCurrentParent ? "#faf5ff" : "#ffffff",
                                    fontSize: "12px",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    gap: "8px",
                                  }}
                                >
                                  <div style={{ minWidth: 0, flex: 1 }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                      <span
                                        style={{
                                          fontWeight: 600,
                                          color: "#1e293b",
                                          overflow: "hidden",
                                          textOverflow: "ellipsis",
                                          whiteSpace: "nowrap",
                                        }}
                                      >
                                        {poi.name}
                                      </span>
                                      <span
                                        style={{
                                          fontSize: "9px",
                                          fontWeight: 700,
                                          padding: "1px 5px",
                                          borderRadius: "3px",
                                          textTransform: "uppercase",
                                          backgroundColor: poi.source === "db" ? "#f3e8ff" : "#fef3c7",
                                          color: poi.source === "db" ? "#7e22ce" : "#b45309",
                                          border:
                                            poi.source === "db"
                                              ? "1px solid #e9d5ff"
                                              : "1px solid #fde68a",
                                          flexShrink: 0,
                                        }}
                                      >
                                        {poi.source === "db" ? "DB" : "CSV"}
                                      </span>
                                    </div>
                                    <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
                                      {formatDistance(poi.distanceMeters)} away • {poi.latitude.toFixed(4)}, {poi.longitude.toFixed(4)}
                                    </div>
                                  </div>

                                  <div style={{ flexShrink: 0 }}>
                                    {isCurrentParent ? (
                                      <span
                                        style={{
                                          fontSize: "10px",
                                          fontWeight: 600,
                                          color: "#7e22ce",
                                          display: "inline-flex",
                                          alignItems: "center",
                                          gap: "2px",
                                        }}
                                      >
                                        <Check size={12} /> Parent
                                      </span>
                                    ) : (
                                      <button
                                        type="button"
                                        onClick={() => handleSelectParentPOI(poi)}
                                        data-testid={`poi-marker-${poi.id}`}
                                        style={{
                                          padding: "3px 8px",
                                          fontSize: "10px",
                                          fontWeight: 600,
                                          backgroundColor: "#f0fdf4",
                                          color: "#166534",
                                          border: "1px solid #bbf7d0",
                                          borderRadius: "4px",
                                          cursor: "pointer",
                                        }}
                                      >
                                        Set as Parent
                                      </button>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </>
                    ) : (
                      /* Notice when current candidate has missing coordinates */
                      <div
                        data-testid="no-coords-nearby-notice"
                        style={{
                          padding: "12px",
                          backgroundColor: "#f8fafc",
                          borderRadius: "6px",
                          border: "1px dashed #cbd5e1",
                          fontSize: "11px",
                          color: "#64748b",
                          textAlign: "center",
                        }}
                      >
                        <Compass size={18} color="#94a3b8" style={{ margin: "0 auto 4px" }} />
                        <div style={{ fontWeight: 600, color: "#334155", marginBottom: "2px" }}>
                          Coordinates required to find nearby POIs
                        </div>
                        <div>
                          Use &quot;Pick on Map&quot; or &quot;Lookup Coordinates from Address&quot; above to assign location coordinates.
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    fontSize: "11px",
                    color: "#64748b",
                    borderTop: "1px solid #e2e8f0",
                    paddingTop: "10px",
                    marginTop: "12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <AlertTriangle size={14} color="#f59e0b" style={{ flexShrink: 0 }} />
                    <span>Ignored and excluded rows will not advance to Phase 2.</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer with styled buttons & live tally */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingTop: "16px",
                borderTop: "1px solid #e2e8f0",
                marginTop: "12px",
              }}
            >
              {/* Discard Import Button */}
              <button
                type="button"
                onClick={handleDiscard}
                disabled={isSubmitting}
                data-testid="cancel-triage-button"
                style={{
                  padding: "9px 16px",
                  border: "1px solid #fecaca",
                  borderRadius: "8px",
                  backgroundColor: "#fff5f5",
                  color: "#b91c1c",
                  fontSize: "13px",
                  fontWeight: 600,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                }}
              >
                <X size={15} color="#dc2626" />
                <span>Discard Import</span>
              </button>

              {/* Tally Indicator */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "12px",
                  color: "#475569",
                  fontWeight: 500,
                }}
              >
                {isFiltering && (
                  <>
                    <span
                      data-testid="visible-candidates-count"
                      style={{
                        color: "#0369a1",
                        fontWeight: 600,
                        backgroundColor: "#f0f9ff",
                        padding: "2px 8px",
                        borderRadius: "4px",
                        border: "1px solid #bae6fd",
                      }}
                    >
                      Showing <strong>{filteredAndSortedCandidates.length}</strong> of {candidates.length} Displayed
                    </span>
                    <span>•</span>
                  </>
                )}
                <span>
                  <strong>{stats.accept}</strong> to Accept
                </span>
                <span>•</span>
                <span>
                  <strong>{stats.sub}</strong> Sublocations
                </span>
                <span>•</span>
                <span>
                  <strong>{stats.update}</strong> Updates
                </span>
                <span>•</span>
                <span>
                  <strong>{stats.ignore}</strong> Ignored
                </span>
                <span>•</span>
                <span data-testid="tally-excluded">
                  <strong style={{ color: "#dc2626" }}>{stats.exclude}</strong> Excluded
                </span>
              </div>

              {/* Actions: Save & Close and Proceed to Phase 2 */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <button
                  type="button"
                  onClick={handleSaveAndClose}
                  disabled={isSubmitting}
                  data-testid="save-close-triage-button"
                  style={{
                    padding: "9px 18px",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    backgroundColor: "#ffffff",
                    color: "#334155",
                    fontSize: "14px",
                    fontWeight: 600,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor: "pointer",
                    boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                  }}
                >
                  <Save size={16} color="#64748b" />
                  <span>Save & Close</span>
                </button>

                <button
                  type="button"
                  onClick={handleProceed}
                  disabled={isSubmitting || candidates.length === 0}
                  data-testid="proceed-phase2-button"
                  style={{
                    padding: "10px 24px",
                    backgroundColor:
                      isSubmitting || candidates.length === 0 ? "#93c5fd" : "#2563eb",
                    color: "#ffffff",
                    borderRadius: "8px",
                    fontSize: "14px",
                    fontWeight: 600,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor:
                      isSubmitting || candidates.length === 0
                        ? "not-allowed"
                        : "pointer",
                    boxShadow: "0 2px 4px rgba(37,99,235,0.25)",
                    border: "none",
                  }}
                >
                  <span>{isSubmitting ? "Processing..." : "Proceed to Phase 2"}</span>
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>

    {/* Bulk Edit Modal */}
    {isBulkEditOpen && (
      <Modal
        isOpen={true}
        onClose={() => setIsBulkEditOpen(false)}
        title={`Bulk Edit ${selectedCandidateIds.length} Selected POI${
          selectedCandidateIds.length === 1 ? "" : "s"
        }`}
        maxWidth="480px"
      >
        <form
          onSubmit={handleApplyBulkEdit}
          data-testid="bulk-edit-modal-form"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            textAlign: "left",
          }}
        >
          <div
            style={{
              padding: "10px 12px",
              backgroundColor: "#eff6ff",
              border: "1px solid #bfdbfe",
              borderRadius: "6px",
              fontSize: "12px",
              color: "#1e40af",
              lineHeight: "1.4",
            }}
          >
            ℹ️ Leave fields blank to keep their existing values unchanged. Any field with an entered value will be updated across all <strong>{selectedCandidateIds.length}</strong> selected POIs.
          </div>

          <div>
            <label
              htmlFor="bulk-country-input"
              style={{
                display: "block",
                fontSize: "12px",
                fontWeight: 600,
                color: "#334155",
                marginBottom: "4px",
              }}
            >
              Country:
            </label>
            <input
              id="bulk-country-input"
              data-testid="bulk-country-input"
              type="text"
              value={bulkCountry}
              onChange={(e) => setBulkCountry(e.target.value)}
              placeholder="Leave blank to keep existing country"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: "13px",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                outline: "none",
                backgroundColor: "#ffffff",
                color: "#0f172a",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="bulk-state-input"
              style={{
                display: "block",
                fontSize: "12px",
                fontWeight: 600,
                color: "#334155",
                marginBottom: "4px",
              }}
            >
              State / Province:
            </label>
            <input
              id="bulk-state-input"
              data-testid="bulk-state-input"
              type="text"
              value={bulkStateProvince}
              onChange={(e) => setBulkStateProvince(e.target.value)}
              placeholder="Leave blank to keep existing state/province"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: "13px",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                outline: "none",
                backgroundColor: "#ffffff",
                color: "#0f172a",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="bulk-city-input"
              style={{
                display: "block",
                fontSize: "12px",
                fontWeight: 600,
                color: "#334155",
                marginBottom: "4px",
              }}
            >
              City / Town:
            </label>
            <input
              id="bulk-city-input"
              data-testid="bulk-city-input"
              type="text"
              value={bulkCity}
              onChange={(e) => setBulkCity(e.target.value)}
              placeholder="Leave blank to keep existing city/town"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: "13px",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                outline: "none",
                backgroundColor: "#ffffff",
                color: "#0f172a",
              }}
            />
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
              marginTop: "8px",
            }}
          >
            <button
              type="button"
              onClick={() => setIsBulkEditOpen(false)}
              disabled={isBulkUpdating}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                background: "#f1f5f9",
                color: "#475569",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isBulkUpdating}
              data-testid="confirm-bulk-edit-button"
              style={{
                padding: "8px 18px",
                borderRadius: "6px",
                background: "#2563eb",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: isBulkUpdating ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              {isBulkUpdating ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Updating...</span>
                </>
              ) : (
                <span>Apply Changes ({selectedCandidateIds.length})</span>
              )}
            </button>
          </div>
        </form>
      </Modal>
    )}
  </>
);
};
