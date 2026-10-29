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

import React, { useState, useEffect } from "react";
import {
  X,
  Star,
  Save,
  Trash2,
  Calendar,
  Clock,
  Link as LinkIcon,
  FolderPlus,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  MapPin,
  Compass,
  FileText,
  Loader2,
} from "lucide-react";
import { apiFetch, ApiError } from "../../services/api";
import { TagSelector } from "../tags/TagSelector";
import { ParentPOISelector } from "./ParentPOISelector";
import { MultiAddressEditor, AddressRecord } from "./MultiAddressEditor";
import { LocationFinderModal } from "./LocationFinderModal";
import { DuplicateCollisionModal } from "./DuplicateCollisionModal";
import { POIMergeModal } from "./POIMergeModal";
import {
  reverseGeocode,
  type ReverseGeocodeResponse,
} from "../../services/geocodeService";
import type { POIMapFeature, VisitState } from "../../types/map";
import type { components } from "../../types/api";

type POIUpdateRequest = components["schemas"]["POIUpdateRequest"];

export interface POIEditDrawerProps {
  poi: POIMapFeature | any | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updated: any) => void;
  onDelete?: (id: string) => void | Promise<void>;
  onOpenLocationFinder?: (initialCoords: { lat: number; lng: number }) => void;
  onOpenMerge?: (sourcePoi: any, targetPoi: any) => void;
}

export const POIEditDrawer: React.FC<POIEditDrawerProps> = ({
  poi,
  isOpen,
  onClose,
  onSave,
  onDelete,
  onOpenLocationFinder,
}) => {
  // Core scalar state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [reasonToVisit, setReasonToVisit] = useState("");
  const [rating, setRating] = useState<number>(0);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  // Coordinates
  const [lat, setLat] = useState<number>(0);
  const [lon, setLon] = useState<number>(0);

  // Hierarchical parent
  const [parentPoiId, setParentPoiId] = useState<string | null>(null);
  const [parentPoiName, setParentPoiName] = useState<string | null>(null);

  // Addresses
  const [addresses, setAddresses] = useState<AddressRecord[]>([]);

  // Duration
  const [recommendedDurationHours, setRecommendedDurationHours] =
    useState<string>("");
  const [recommendedVisitDays, setRecommendedVisitDays] = useState<number>(1);
  const [estimatedVisitTimeNotes, setEstimatedVisitTimeNotes] =
    useState<string>("");

  // Provenance
  const [sourceType, setSourceType] = useState<string>("Manual");
  const [sourceValue, setSourceValue] = useState<string>("");

  // URLs
  const [officialUrl, setOfficialUrl] = useState<string>("");
  const [wikiUrl, setWikiUrl] = useState<string>("");

  // Photos & Media
  const [directoryPaths, setDirectoryPaths] = useState<string[]>([]);
  const [newDirectoryPath, setNewDirectoryPath] = useState<string>("");
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [newImageUrl, setNewImageUrl] = useState<string>("");

  // Visit tracking
  const [visitedDates, setVisitedDates] = useState<string[]>([]);
  const [newVisitDate, setNewVisitDate] = useState<string>("");
  const [wantToVisitAgain, setWantToVisitAgain] = useState<boolean>(false);

  // Initial coordinates for change detection (FR-012, FR-013)
  const [initialLat, setInitialLat] = useState<number>(0);
  const [initialLon, setInitialLon] = useState<number>(0);

  // Duplicate collision & merge modal states (US4, T-030)
  const [isDuplicateModalOpen, setIsDuplicateModalOpen] =
    useState<boolean>(false);
  const [collisionCandidate, setCollisionCandidate] = useState<any | null>(
    null,
  );
  const [isMergeModalOpen, setIsMergeModalOpen] = useState<boolean>(false);
  const [mergeTarget, setMergeTarget] = useState<any | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLocationFinderOpen, setIsLocationFinderOpen] =
    useState<boolean>(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleApplyLocation = (
    coords: { lat: number; lng: number },
    address?: ReverseGeocodeResponse,
  ) => {
    setLat(coords.lat);
    setLon(coords.lng);
    if (address && address.country) {
      const newAddr: AddressRecord = {
        street: address.street || "",
        city: address.city || "",
        state_province: address.state_province || "",
        country: address.country || "",
        postal_code: address.postal_code || "",
      };
      setAddresses((prev) => {
        if (
          prev.length === 0 ||
          (prev.length === 1 && !prev[0].country.trim())
        ) {
          return [newAddr];
        }
        return [...prev, newAddr];
      });
    }
  };

  // Load detailed POI data on open
  useEffect(() => {
    if (!poi || !isOpen) return;
    setIsConfirmingDelete(false);
    setIsDeleting(false);

    // Initialize baseline from POIMapFeature
    const baselineLat = poi.canonical_lat ?? poi.lat ?? 0;
    const baselineLon = poi.canonical_lng ?? poi.lon ?? 0;
    setName(poi.name || "");
    setDescription(poi.description || "");
    setReasonToVisit(poi.reason_to_visit || "");
    setLat(baselineLat);
    setLon(baselineLon);
    setInitialLat(baselineLat);
    setInitialLon(baselineLon);
    setRating(poi.rating || 0);
    setParentPoiId(poi.parent_poi_id || null);
    setOfficialUrl(poi.official_url || "");
    setWikiUrl(poi.wiki_url || "");
    if (poi.addresses && poi.addresses.length > 0) {
      setAddresses(poi.addresses);
    } else if (poi.address) {
      setAddresses([
        {
          street: poi.address,
          city: poi.city || "",
          state_province: poi.state || "",
          country: poi.country || "",
        },
      ]);
    } else {
      setAddresses([]);
    }
    const initialTags: string[] = Array.isArray(poi.tags)
      ? poi.tags
          .map((t: any) => (typeof t === "string" ? t : t.slug || t.name))
          .filter(Boolean)
      : [];
    setSelectedTags(initialTags);

    // Baseline visit lifecycle tracking
    const rawVisitedDates =
      Array.isArray(poi.visited_dates) && poi.visited_dates.length > 0
        ? poi.visited_dates.map(String).sort()
        : poi.visit_state === "visited_return" ||
          poi.visit_state === "visited_do_not_return" ||
          poi.already_visited
          ? ["2024-06-01"]
          : [];
    setVisitedDates(rawVisitedDates);

    const initialWantAgain =
      poi.want_to_visit_again !== undefined && poi.want_to_visit_again !== null
        ? Boolean(poi.want_to_visit_again)
        : poi.visit_state === "visited_return";
    setWantToVisitAgain(initialWantAgain);
    setEstimatedVisitTimeNotes(poi.estimated_visit_time_notes || "");
    setSourceType((poi as any).source_type || "Manual");
    setSourceValue((poi as any).source_value || "");

    // Fetch full rich record from backend
    const loadFullPOI = async () => {
      const isUuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          poi.id,
        );
      if (!isUuid) {
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const fullData = await apiFetch<any>(`/api/pois/${poi.id}`);
        setName(fullData.name || "");
        setDescription(fullData.description || "");
        setReasonToVisit(fullData.reason_to_visit || "");
        const fetchedLat = fullData.lat ?? fullData.latitude ?? baselineLat;
        const fetchedLon = fullData.lon ?? fullData.longitude ?? baselineLon;
        setLat(fetchedLat);
        setLon(fetchedLon);
        setInitialLat(fetchedLat);
        setInitialLon(fetchedLon);
        setParentPoiId(fullData.parent_poi_id || null);
        setParentPoiName(fullData.parent_poi_name || null);
        setAddresses(fullData.addresses || []);
        setRecommendedDurationHours(
          fullData.recommended_duration_hours != null
            ? String(fullData.recommended_duration_hours)
            : "",
        );
        setRecommendedVisitDays(fullData.recommended_visit_days || 1);
        setEstimatedVisitTimeNotes(fullData.estimated_visit_time_notes || "");
        setSourceType(fullData.source_type || "Manual");
        setSourceValue(fullData.source_value || "");
        setOfficialUrl(fullData.official_url || "");
        setWikiUrl(fullData.wiki_url || "");
        setDirectoryPaths(fullData.directory_paths || []);
        setImageUrls(fullData.image_urls || []);
        setVisitedDates((fullData.visited_dates || []).map(String).sort());
        setWantToVisitAgain(Boolean(fullData.want_to_visit_again));
        setRating(fullData.rating || 0);
        if (fullData.tags && Array.isArray(fullData.tags)) {
          const fetchedTags = fullData.tags
            .map((t: any) => (typeof t === "string" ? t : t.slug || t.name))
            .filter(Boolean);
          setSelectedTags(fetchedTags);
        }
      } catch (err) {
        console.warn(
          "Could not fetch extended POI details; using map feature draft",
          err,
        );
      } finally {
        setIsLoading(false);
      }
    };

    loadFullPOI();
  }, [poi, isOpen]);

  if (!isOpen || !poi) return null;

  // Deterministic visit lifecycle badges
  const isAlreadyVisited = visitedDates.length > 0;
  const isVisitPending = !isAlreadyVisited || wantToVisitAgain;

  // Add visit date
  const handleAddVisitDate = () => {
    if (!newVisitDate.trim()) return;
    if (!visitedDates.includes(newVisitDate.trim())) {
      const updated = [...visitedDates, newVisitDate.trim()].sort();
      setVisitedDates(updated);
    }
    setNewVisitDate("");
  };

  const handleRemoveVisitDate = (dateToRemove: string) => {
    setVisitedDates(visitedDates.filter((d) => d !== dateToRemove));
  };

  // Directory picker (hybrid showDirectoryPicker or text)
  const handlePickDirectory = async () => {
    try {
      if ("showDirectoryPicker" in window) {
        // @ts-ignore - Chrome File System Access API
        const dirHandle = await window.showDirectoryPicker();
        if (dirHandle?.name && !directoryPaths.includes(dirHandle.name)) {
          setDirectoryPaths([...directoryPaths, dirHandle.name]);
        }
      } else {
        // Fallback text input alert / prompt
        const manual = window.prompt(
          "Enter local directory path for photo folder:",
        );
        if (
          manual &&
          manual.trim() &&
          !directoryPaths.includes(manual.trim())
        ) {
          setDirectoryPaths([...directoryPaths, manual.trim()]);
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        console.error("Directory picker error", err);
      }
    }
  };

  const handleAddManualDirectory = () => {
    if (!newDirectoryPath.trim()) return;
    if (!directoryPaths.includes(newDirectoryPath.trim())) {
      setDirectoryPaths([...directoryPaths, newDirectoryPath.trim()]);
    }
    setNewDirectoryPath("");
  };

  const handleRemoveDirectory = (idx: number) => {
    setDirectoryPaths(directoryPaths.filter((_, i) => i !== idx));
  };

  // Image URLs
  const handleAddImageUrl = () => {
    if (!newImageUrl.trim()) return;
    if (!imageUrls.includes(newImageUrl.trim())) {
      setImageUrls([...imageUrls, newImageUrl.trim()]);
    }
    setNewImageUrl("");
  };

  const handleRemoveImageUrl = (idx: number) => {
    setImageUrls(imageUrls.filter((_, i) => i !== idx));
  };

  // Helper to construct current in-memory draft
  const getCurrentDraft = (currentAddrs: AddressRecord[]) => {
    const parsedTags = selectedTags;

    const isVisited = visitedDates.length > 0;
    const isPending = !isVisited || wantToVisitAgain;
    const derivedVisitState: VisitState = isVisited
      ? wantToVisitAgain
        ? "visited_return"
        : "visited_do_not_return"
      : "not_visited";

    return {
      ...poi,
      name: name.trim(),
      description: description.trim() || undefined,
      reason_to_visit: reasonToVisit.trim() || undefined,
      parent_poi_id: parentPoiId || undefined,
      parent_poi_name: parentPoiName || undefined,
      addresses: currentAddrs,
      city: currentAddrs.find((a) => a.city?.trim())?.city || poi.city,
      state:
        currentAddrs.length > 0
          ? currentAddrs.find((a) => a.state_province?.trim())?.state_province
          : poi.state,
      country:
        currentAddrs.find((a) => a.country?.trim())?.country || poi.country,
      lat,
      lon,
      latitude: lat,
      longitude: lon,
      canonical_lat: lat,
      canonical_lng: lon,
      render_lat: lat,
      render_lng: lon,
      rating: rating > 0 ? rating : null,
      recommended_duration_hours: recommendedDurationHours
        ? parseFloat(recommendedDurationHours)
        : null,
      recommended_visit_days: recommendedVisitDays || 1,
      estimated_visit_time_notes: estimatedVisitTimeNotes.trim() || null,
      source_type: sourceType,
      source_value: sourceValue.trim() || undefined,
      official_url: officialUrl.trim() || undefined,
      wiki_url: wikiUrl.trim() || undefined,
      directory_paths: directoryPaths,
      image_urls: imageUrls,
      visited_dates: visitedDates,
      want_to_visit_again: wantToVisitAgain,
      already_visited: isVisited,
      visit_pending: isPending,
      visit_state: derivedVisitState,
      tags: parsedTags,
    };
  };

  const executeSave = async (skipDuplicateCheck = false) => {
    if (isSaving) return;

    setErrorMessage(null);
    setIsSaving(true);

    try {
      let activeAddresses = [...addresses];

      // Coordinate change check (> 0.00001 deg)
      const coordsChanged =
        Math.abs(lat - initialLat) > 0.00001 ||
        Math.abs(lon - initialLon) > 0.00001;

      // FR-012: Auto-backfill reverse geocoded address before save if coordinates changed and address lacks country
      if (coordsChanged && lat !== 0 && lon !== 0) {
        const needsCountry =
          activeAddresses.length === 0 ||
          activeAddresses.every((a) => !a.country || !a.country.trim());

        if (needsCountry) {
          try {
            const rev = await reverseGeocode(lat, lon);
            if (rev && rev.country) {
              const backfilled: AddressRecord = {
                street: rev.street || "",
                city: rev.city || "",
                state_province: rev.state_province || "",
                country: rev.country || "",
                postal_code: rev.postal_code || "",
              };
              if (
                activeAddresses.length === 0 ||
                (activeAddresses.length === 1 &&
                  !activeAddresses[0].country.trim())
              ) {
                activeAddresses = [backfilled];
              } else {
                activeAddresses = [...activeAddresses, backfilled];
              }
              setAddresses(activeAddresses);
            }
          } catch (revErr) {
            console.warn(
              "Auto-backfill reverse geocode attempt skipped or failed",
              revErr,
            );
          }
        }
      }

      // FR-013: Pre-save duplicate collision check (unless skipDuplicateCheck)
      if (!skipDuplicateCheck && name.trim()) {
        try {
          const dupRes = await apiFetch<any>("/api/pois/check-duplicate", {
            method: "POST",
            body: JSON.stringify({
              name: name.trim(),
              latitude: lat,
              longitude: lon,
              exclude_poi_id: poi.id || undefined,
            }),
          });

          if (dupRes.is_duplicate && dupRes.candidate) {
            setCollisionCandidate(dupRes.candidate);
            setIsDuplicateModalOpen(true);
            setIsSaving(false);
            return;
          }
        } catch (dupErr) {
          console.warn(
            "Duplicate collision probe failed, proceeding with direct save",
            dupErr,
          );
        }
      }

      const parsedTags = selectedTags;

      const validSourceType = (
        ["Web", "CSV", "Manual", "Photo"].includes(sourceType)
          ? sourceType
          : "Manual"
      ) as "Web" | "CSV" | "Manual" | "Photo";

      const resolvedCity =
        activeAddresses.find((a) => a.city?.trim())?.city?.trim() || poi.city;
      const resolvedState =
        activeAddresses.length > 0
          ? activeAddresses.find((a) => a.state_province?.trim())?.state_province?.trim()
          : poi.state;
      const resolvedCountry =
        activeAddresses.find((a) => a.country?.trim())?.country?.trim() ||
        poi.country;

      const payload: POIUpdateRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        reason_to_visit: reasonToVisit.trim() || undefined,
        parent_poi_id: parentPoiId || undefined,
        addresses: activeAddresses.length > 0 ? activeAddresses : undefined,
        city: resolvedCity || undefined,
        state: resolvedState || undefined,
        states: resolvedState ? [resolvedState] : [],
        country: resolvedCountry || undefined,
        countries: resolvedCountry ? [resolvedCountry] : [],
        latitude: lat,
        longitude: lon,
        rating: rating > 0 ? rating : null,
        recommended_duration_hours: recommendedDurationHours
          ? parseFloat(recommendedDurationHours)
          : null,
        recommended_visit_days: recommendedVisitDays || 1,
        estimated_visit_time_notes: estimatedVisitTimeNotes.trim() || undefined,
        source_type: validSourceType,
        source_value: sourceValue.trim() || undefined,
        official_url: officialUrl.trim() || undefined,
        wiki_url: wikiUrl.trim() || undefined,
        directory_paths: directoryPaths,
        image_urls: imageUrls,
        visited_dates: visitedDates,
        want_to_visit_again: wantToVisitAgain,
        tags: parsedTags,
      };

      const isUuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          poi.id,
        );
      if (!isUuid) {
        onSave(getCurrentDraft(activeAddresses));
        setIsSaving(false);
        onClose();
        return;
      }

      const updated = await apiFetch<any>(`/api/pois/${poi.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      const finalLat = updated.lat ?? updated.latitude ?? lat;
      const finalLng = updated.lon ?? updated.longitude ?? lon;
      const finalTags = Array.isArray(updated.tags)
        ? updated.tags.map((t: any) => (typeof t === "string" ? t : t.slug || t.name))
        : selectedTags;

      const isVisited = visitedDates.length > 0;
      const isPending = !isVisited || wantToVisitAgain;
      const derivedVisitState: VisitState = isVisited
        ? wantToVisitAgain
          ? "visited_return"
          : "visited_do_not_return"
        : "not_visited";

      // Synchronize with parent app state
      onSave({
        ...poi,
        name: updated.name,
        canonical_lat: finalLat,
        canonical_lng: finalLng,
        render_lat: finalLat,
        render_lng: finalLng,
        city: updated.city || resolvedCity || poi.city,
        state:
          updated.state ||
          updated.states?.[0] ||
          resolvedState ||
          poi.state,
        country:
          updated.country ||
          updated.countries?.[0] ||
          resolvedCountry ||
          poi.country,
        visit_state: updated.visit_state || derivedVisitState,
        already_visited: updated.already_visited ?? isVisited,
        visit_pending: updated.visit_pending ?? isPending,
        want_to_visit_again: updated.want_to_visit_again ?? wantToVisitAgain,
        visited_dates: updated.visited_dates ?? visitedDates,
        rating: updated.rating,
        tags: finalTags,
        description: updated.description,
        reason_to_visit: updated.reason_to_visit ?? (reasonToVisit.trim() || undefined),
        addresses: updated.addresses,
        parent_poi_id: updated.parent_poi_id,
        parent_poi_name: updated.parent_poi_name,
      });

      onClose();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(
          err.problem.detail || err.problem.title || "Failed to update POI.",
        );
      } else {
        setErrorMessage(
          err?.message || "An unexpected error occurred while saving.",
        );
      }
    } finally {
      setIsSaving(false);
    }
  };

  // Submit update
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSave(false);
  };

  return (
    <div
      className="poi-drawer-overlay fade-in"
      onClick={onClose}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.45)",
        backdropFilter: "blur(3px)",
        zIndex: 5000,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        className="poi-drawer-content slide-up"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "520px",
          maxWidth: "100%",
          height: "100%",
          background: "var(--bg-surface, #ffffff)",
          color: "var(--text-primary, #0f172a)",
          boxShadow: "var(--shadow-lg)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          padding: "24px",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingBottom: "16px",
            borderBottom: "1px solid var(--border-color, #e2e8f0)",
            marginBottom: "16px",
          }}
        >
          <div>
            <h3 style={{ fontSize: "18px", fontWeight: 800, margin: 0 }}>
              Edit Point of Interest
            </h3>
            <span
              style={{ fontSize: "12px", color: "var(--text-muted, #64748b)" }}
            >
              ID: {poi.id}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close POI Editor"
            style={{
              padding: "6px",
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Error Alert Banner */}
        {errorMessage && (
          <div
            style={{
              padding: "10px 14px",
              marginBottom: "16px",
              borderRadius: "var(--radius-md, 8px)",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              fontSize: "12px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        {isLoading ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: "10px",
              color: "var(--text-muted)",
            }}
          >
            <Loader2 size={28} className="animate-spin" />
            <span style={{ fontSize: "13px" }}>Loading POI details...</span>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "18px",
              flex: 1,
            }}
          >
            {/* Section 1: Basic Identity */}
            <div>
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  display: "block",
                  marginBottom: "6px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                Name <span style={{ color: "var(--danger, #ef4444)" }}>*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  fontSize: "13px",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-primary, #0f172a)",
                }}
              />
            </div>

            {/* Section 2: Multiline Description with Character Counter */}
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "6px",
                }}
              >
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <FileText
                    size={14}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Description (Markdown supported)
                </label>
                <span
                  style={{
                    fontSize: "11px",
                    color:
                      description.length > 9500
                        ? "var(--warning, #f59e0b)"
                        : "var(--text-muted, #94a3b8)",
                  }}
                >
                  {description.length.toLocaleString()} / 10,000
                </span>
              </div>
              <textarea
                rows={4}
                maxLength={10000}
                placeholder="Detailed visitor notes, highlights, entrance instructions, or scenic overlooks..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  fontSize: "13px",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-primary, #0f172a)",
                  resize: "vertical",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Section 2b: Reason to Visit (Why Visit) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <label
                  htmlFor="poi-reason-to-visit"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "var(--text-secondary, #475569)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  <Compass
                    size={14}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Reason to Visit
                </label>
                <span
                  style={{
                    fontSize: "11px",
                    color:
                      reasonToVisit.length > 9500
                        ? "var(--warning, #f59e0b)"
                        : "var(--text-muted, #94a3b8)",
                  }}
                >
                  {reasonToVisit.length.toLocaleString()} / 10,000
                </span>
              </div>
              <textarea
                id="poi-reason-to-visit"
                rows={4}
                maxLength={10000}
                placeholder="Why a tourist would be interested in visiting (e.g., scenic sunset vistas, historic architecture, specialty dishes)..."
                value={reasonToVisit}
                onChange={(e) => setReasonToVisit(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  fontSize: "13px",
                  background: "var(--bg-surface, #ffffff)",
                  color: "var(--text-primary, #0f172a)",
                  resize: "vertical",
                  fontFamily: "inherit",
                }}
              />
            </div>

            {/* Section 3: Hierarchical Parent Selector */}
            <ParentPOISelector
              activePoiId={poi.id}
              selectedParentId={parentPoiId}
              selectedParentName={parentPoiName}
              onChange={(newParentId, newParentName) => {
                setParentPoiId(newParentId);
                setParentPoiName(newParentName);
              }}
            />

            {/* Section 4: Coordinates & Map Finder */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
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
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <Compass
                    size={14}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Coordinates (WGS-84)
                </label>
                <button
                  type="button"
                  onClick={() => {
                    if (onOpenLocationFinder) {
                      onOpenLocationFinder({ lat, lng: lon });
                    } else {
                      setIsLocationFinderOpen(true);
                    }
                  }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--accent-light, #eff6ff)",
                    color: "var(--accent, #2563eb)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  <MapPin size={12} />
                  Find on Map
                </button>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "8px",
                }}
              >
                <div>
                  <span
                    style={{ fontSize: "11px", color: "var(--text-muted)" }}
                  >
                    Latitude
                  </span>
                  <input
                    type="number"
                    step="any"
                    min="-90"
                    max="90"
                    value={lat}
                    onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                    }}
                  />
                </div>
                <div>
                  <span
                    style={{ fontSize: "11px", color: "var(--text-muted)" }}
                  >
                    Longitude
                  </span>
                  <input
                    type="number"
                    step="any"
                    min="-180"
                    max="180"
                    value={lon}
                    onChange={(e) => setLon(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Section 5: Multi-Address Editor */}
            <MultiAddressEditor
              addresses={addresses}
              onChange={(updatedAddresses) => setAddresses(updatedAddresses)}
            />

            {/* Section 6: Recommended Duration */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
              }}
            >
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  marginBottom: "8px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                <Clock size={14} style={{ color: "var(--accent, #2563eb)" }} />
                Estimated Visit Time & Itinerary Allocation
              </label>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "8px",
                }}
              >
                <div>
                  <span
                    style={{ fontSize: "11px", fontWeight: 500, color: "var(--text-secondary, #475569)" }}
                  >
                    Duration (Hours)
                  </span>
                  <input
                    type="number"
                    step="any"
                    min="0.1"
                    max="24.0"
                    placeholder="e.g. 2.5"
                    value={recommendedDurationHours}
                    onChange={(e) =>
                      setRecommendedDurationHours(e.target.value)
                    }
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                      marginTop: "3px",
                    }}
                  />
                  <span
                    style={{
                      fontSize: "10px",
                      color: "var(--text-muted, #64748b)",
                      display: "block",
                      marginTop: "3px",
                      lineHeight: 1.3,
                    }}
                  >
                    Active visit duration (e.g. 2.5h)
                  </span>
                </div>
                <div>
                  <span
                    style={{ fontSize: "11px", fontWeight: 500, color: "var(--text-secondary, #475569)" }}
                  >
                    Itinerary Days
                  </span>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={recommendedVisitDays}
                    onChange={(e) =>
                      setRecommendedVisitDays(parseInt(e.target.value, 10) || 1)
                    }
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                      marginTop: "3px",
                    }}
                  />
                  <span
                    style={{
                      fontSize: "10px",
                      color: "var(--text-muted, #64748b)",
                      display: "block",
                      marginTop: "3px",
                      lineHeight: 1.3,
                    }}
                  >
                    Trip days allocated (1 = single-day)
                  </span>
                </div>
              </div>

              {/* Multiline explanation of visit duration reasoning */}
              <div style={{ marginTop: "10px" }}>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 500,
                    color: "var(--text-secondary, #475569)",
                    display: "block",
                    marginBottom: "3px",
                  }}
                >
                  Visit Duration Reasoning & Notes
                </span>
                <textarea
                  rows={3}
                  value={estimatedVisitTimeNotes}
                  onChange={(e) => setEstimatedVisitTimeNotes(e.target.value)}
                  placeholder="Explain visit duration reasoning (e.g. 45-min guided tour, 30-min treasury exhibit, shuttle walk)..."
                  style={{
                    width: "100%",
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "12px",
                    resize: "vertical",
                    fontFamily: "inherit",
                    lineHeight: 1.4,
                  }}
                />
              </div>
            </div>

            {/* Section 7: Visit Tracking & Lifecycle Badges */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <Calendar
                    size={14}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Visit Lifecycle Tracking
                </label>
                {/* Badges */}
                <div style={{ display: "flex", gap: "6px" }}>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: "var(--radius-full, 9999px)",
                      background: isAlreadyVisited ? "#dcfce7" : "#f1f5f9",
                      color: isAlreadyVisited ? "#15803d" : "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                    }}
                  >
                    <CheckCircle2 size={10} />
                    Already Visited
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: "var(--radius-full, 9999px)",
                      background: isVisitPending ? "#dbeafe" : "#f1f5f9",
                      color: isVisitPending ? "#1d4ed8" : "#94a3b8",
                    }}
                  >
                    Visit Pending
                  </span>
                </div>
              </div>

              {/* Want to visit again checkbox */}
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontSize: "12px",
                  cursor: "pointer",
                  color: "var(--text-primary)",
                }}
              >
                <input
                  type="checkbox"
                  checked={wantToVisitAgain}
                  onChange={(e) => setWantToVisitAgain(e.target.checked)}
                  style={{ cursor: "pointer" }}
                />
                <span>Want to visit again (keeps Visit Pending active)</span>
              </label>

              {/* Visited Dates List */}
              <div>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-secondary)",
                    display: "block",
                    marginBottom: "4px",
                  }}
                >
                  Visited Dates ({visitedDates.length})
                </span>
                <div
                  style={{ display: "flex", gap: "6px", marginBottom: "8px" }}
                >
                  <input
                    type="date"
                    value={newVisitDate}
                    onChange={(e) => setNewVisitDate(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleAddVisitDate}
                    style={{
                      padding: "6px 10px",
                      borderRadius: "var(--radius-sm, 6px)",
                      background: "var(--accent-light, #eff6ff)",
                      color: "var(--accent, #2563eb)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "11px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    Add Date
                  </button>
                </div>

                {visitedDates.length > 0 && (
                  <div
                    style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}
                  >
                    {visitedDates.map((d) => (
                      <span
                        key={d}
                        style={{
                          fontSize: "11px",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-sm, 4px)",
                          background: "var(--bg-hover, #f1f5f9)",
                          border: "1px solid var(--border-color, #e2e8f0)",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        {d}
                        <X
                          size={12}
                          style={{
                            cursor: "pointer",
                            color: "var(--text-muted)",
                          }}
                          onClick={() => handleRemoveVisitDate(d)}
                        />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Section 8: Provenance */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
              }}
            >
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  display: "block",
                  marginBottom: "8px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                Origin Provenance
              </label>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 2fr",
                  gap: "8px",
                }}
              >
                <div>
                  <span
                    style={{ fontSize: "11px", color: "var(--text-muted)" }}
                  >
                    Source Type
                  </span>
                  <select
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                    }}
                  >
                    <option value="Manual">Manual</option>
                    <option value="Web">Web</option>
                    <option value="CSV">CSV</option>
                    <option value="Photo">Photo</option>
                  </select>
                </div>
                <div>
                  <span
                    style={{ fontSize: "11px", color: "var(--text-muted)" }}
                  >
                    Source Details
                  </span>
                  <input
                    type="text"
                    maxLength={1000}
                    placeholder="URL, campaign, or source file"
                    value={sourceValue}
                    onChange={(e) => setSourceValue(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      fontSize: "12px",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Section 9: Official & Wikipedia URLs */}
            <div
              style={{ display: "flex", flexDirection: "column", gap: "10px" }}
            >
              <div>
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <LinkIcon
                    size={13}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Official Website URL
                </label>
                <input
                  type="url"
                  maxLength={2000}
                  placeholder="https://..."
                  value={officialUrl}
                  onChange={(e) => setOfficialUrl(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "12px",
                  }}
                />
              </div>

              <div>
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginBottom: "4px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <LinkIcon
                    size={13}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Wikipedia URL
                </label>
                <input
                  type="url"
                  maxLength={2000}
                  placeholder="https://en.wikipedia.org/wiki/..."
                  value={wikiUrl}
                  onChange={(e) => setWikiUrl(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "12px",
                  }}
                />
              </div>
            </div>

            {/* Section 10: Local Photo Folders */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
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
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--text-secondary, #475569)",
                  }}
                >
                  <FolderPlus
                    size={14}
                    style={{ color: "var(--accent, #2563eb)" }}
                  />
                  Local Photo Folders ({directoryPaths.length})
                </label>
                <button
                  type="button"
                  onClick={handlePickDirectory}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "4px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--accent-light, #eff6ff)",
                    color: "var(--accent, #2563eb)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  <FolderPlus size={12} />
                  Browse Folder
                </button>
              </div>

              {/* Manual Directory Path Input */}
              <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
                <input
                  type="text"
                  placeholder="e.g. D:/Photos/Trip2026"
                  value={newDirectoryPath}
                  onChange={(e) => setNewDirectoryPath(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "12px",
                  }}
                />
                <button
                  type="button"
                  onClick={handleAddManualDirectory}
                  style={{
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--bg-hover, #f1f5f9)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Add Path
                </button>
              </div>

              {directoryPaths.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  {directoryPaths.map((path, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "4px 8px",
                        borderRadius: "var(--radius-sm, 4px)",
                        background: "var(--bg-hover, #f1f5f9)",
                        fontSize: "11px",
                      }}
                    >
                      <span
                        style={{
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {path}
                      </span>
                      <Trash2
                        size={13}
                        style={{
                          cursor: "pointer",
                          color: "var(--danger, #ef4444)",
                          flexShrink: 0,
                        }}
                        onClick={() => handleRemoveDirectory(idx)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Section 11: Image Gallery URLs */}
            <div
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-card, #ffffff)",
              }}
            >
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  marginBottom: "8px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                <ImageIcon
                  size={14}
                  style={{ color: "var(--accent, #2563eb)" }}
                />
                Image Gallery URLs ({imageUrls.length})
              </label>
              <div style={{ display: "flex", gap: "6px", marginBottom: "8px" }}>
                <input
                  type="url"
                  placeholder="https://example.com/image.jpg"
                  value={newImageUrl}
                  onChange={(e) => setNewImageUrl(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm, 6px)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "12px",
                  }}
                />
                <button
                  type="button"
                  onClick={handleAddImageUrl}
                  style={{
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm, 6px)",
                    background: "var(--accent-light, #eff6ff)",
                    color: "var(--accent, #2563eb)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Add Image
                </button>
              </div>

              {imageUrls.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  {imageUrls.map((url, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "4px 8px",
                        borderRadius: "var(--radius-sm, 4px)",
                        background: "var(--bg-hover, #f1f5f9)",
                        fontSize: "11px",
                      }}
                    >
                      <span
                        style={{
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {url}
                      </span>
                      <Trash2
                        size={13}
                        style={{
                          cursor: "pointer",
                          color: "var(--danger, #ef4444)",
                          flexShrink: 0,
                        }}
                        onClick={() => handleRemoveImageUrl(idx)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Section 12: Rating */}
            <div>
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  marginBottom: "6px",
                  color: "var(--text-secondary, #475569)",
                }}
              >
                <Star
                  size={14}
                  style={{ color: "var(--warning, #f59e0b)" }}
                />
                Rating
              </label>
              <div style={{ display: "flex", gap: "4px" }}>
                {[1, 2, 3, 4, 5].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setRating(rating === s ? 0 : s)}
                    style={{
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      padding: "2px",
                      color:
                        s <= rating
                          ? "var(--warning, #f59e0b)"
                          : "var(--border-color, #cbd5e1)",
                    }}
                  >
                    <Star
                      size={18}
                      fill={
                        s <= rating
                          ? "var(--warning, #f59e0b)"
                          : "transparent"
                      }
                    />
                  </button>
                ))}
              </div>
            </div>

            {/* Section 13: Tag Selection */}
            <TagSelector
              selectedTags={selectedTags}
              onChange={setSelectedTags}
            />

            {/* Action Buttons */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingTop: "16px",
                borderTop: "1px solid var(--border-color, #e2e8f0)",
                marginTop: "12px",
              }}
            >
              {onDelete ? (
                isConfirmingDelete ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      background: "var(--bg-hover, #fef2f2)",
                      border: "1px solid #fecaca",
                      padding: "6px 10px",
                      borderRadius: "var(--radius-md, 8px)",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#b91c1c",
                      }}
                    >
                      Are you sure?
                    </span>
                    <button
                      type="button"
                      disabled={isDeleting}
                      onClick={async () => {
                        setIsDeleting(true);
                        try {
                          await onDelete(poi.id);
                        } finally {
                          setIsDeleting(false);
                          setIsConfirmingDelete(false);
                        }
                      }}
                      style={{
                        padding: "5px 10px",
                        fontSize: "12px",
                        fontWeight: 700,
                        background: "#dc2626",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      {isDeleting ? "Deleting..." : "Yes, Delete"}
                    </button>
                    <button
                      type="button"
                      disabled={isDeleting}
                      onClick={() => setIsConfirmingDelete(false)}
                      style={{
                        padding: "5px 10px",
                        fontSize: "12px",
                        fontWeight: 600,
                        background: "#ffffff",
                        color: "#374151",
                        border: "1px solid #d1d5db",
                        borderRadius: "4px",
                        cursor: "pointer",
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsConfirmingDelete(true)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "8px 12px",
                      borderRadius: "var(--radius-md, 8px)",
                      background: "transparent",
                      color: "var(--danger, #ef4444)",
                      border: "1px solid var(--danger, #ef4444)",
                      fontSize: "13px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    <Trash2 size={15} />
                    Delete POI
                  </button>
                )
              ) : (
                <div />
              )}

              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isSaving}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: "var(--bg-hover, #f1f5f9)",
                    border: "1px solid var(--border-color, #e2e8f0)",
                    color: "var(--text-secondary, #475569)",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "8px 20px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: isSaving
                      ? "var(--text-muted)"
                      : "var(--accent, #2563eb)",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: isSaving ? "not-allowed" : "pointer",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  {isSaving ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save size={15} />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
        <LocationFinderModal
          isOpen={isLocationFinderOpen}
          initialLat={lat}
          initialLng={lon}
          onClose={() => setIsLocationFinderOpen(false)}
          onApply={(coords, revAddr) => {
            handleApplyLocation(coords, revAddr);
            setIsLocationFinderOpen(false);
          }}
        />
        <DuplicateCollisionModal
          isOpen={isDuplicateModalOpen}
          draftPoi={getCurrentDraft(addresses)}
          collisionCandidate={collisionCandidate}
          onSaveAsNew={() => {
            setIsDuplicateModalOpen(false);
            executeSave(true);
          }}
          onMerge={(_draft, existing) => {
            setIsDuplicateModalOpen(false);
            setMergeTarget(
              existing || (collisionCandidate ? collisionCandidate.poi : null),
            );
            setIsMergeModalOpen(true);
          }}
          onCancel={() => {
            setIsDuplicateModalOpen(false);
            setCollisionCandidate(null);
          }}
        />
        <POIMergeModal
          isOpen={isMergeModalOpen}
          sourcePoi={getCurrentDraft(addresses)}
          targetPoi={mergeTarget}
          isDraftSource={true}
          onClose={() => {
            setIsMergeModalOpen(false);
            setMergeTarget(null);
          }}
          onSuccess={(mergedTarget) => {
            setIsMergeModalOpen(false);
            setMergeTarget(null);
            onSave(mergedTarget);
            onClose();
          }}
        />
      </div>
    </div>
  );
};
