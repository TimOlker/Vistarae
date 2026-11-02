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

import React, { useEffect, useMemo, useState, useCallback } from "react";
import { Modal } from "../common/Modal";
import {
  ingestApi,
  type CandidateItem,
  type CandidateUpdateRequest,
} from "../../services/ingestApi";
import { useToast } from "../../context/ToastContext";
import {
  X,
  MapPin,
  AlertTriangle,
  Search,
  Save,
  Check,
  Loader2,
  Sparkles,
  Globe,
  Download,
  Trash2,
  Image as ImageIcon,
} from "lucide-react";

export interface ExistingPOIMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface CSVImportWorkbenchModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onCommitComplete?: (summary: { committed_count: number }) => void;
  existingPOIs?: ExistingPOIMarker[];
}

export type CompletenessFilter =
  | "all"
  | "incomplete"
  | "missing_photo"
  | "missing_location"
  | "missing_websites";

export const PROXIMITY_STEPS = [
  { label: "100 ft", miles: 100 / 5280 },
  { label: "500 ft", miles: 500 / 5280 },
  { label: "0.25 mi", miles: 0.25 },
  { label: "0.5 mi", miles: 0.5 },
  { label: "1 mi", miles: 1.0 },
  { label: "5 mi", miles: 5.0 },
  { label: "10 mi", miles: 10.0 },
  { label: "25 mi", miles: 25.0 },
  { label: "50 mi", miles: 50.0 },
  { label: "100 mi", miles: 100.0 },
];

function haversineMiles(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 3958.8;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export const CSVImportWorkbenchModal: React.FC<CSVImportWorkbenchModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onCommitComplete,
  existingPOIs = [],
}) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingCandidate, setIsSavingCandidate] = useState(false);
  const [isEnrichingSingle, setIsEnrichingSingle] = useState(false);
  const [isEnrichingAll, setIsEnrichingAll] = useState(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [completenessFilter, setCompletenessFilter] = useState<CompletenessFilter>("all");
  const [dispositionFilter, setDispositionFilter] = useState<string>("all");

  // Multi-select for Batch Editing
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [isBatchEditOpen, setIsBatchEditOpen] = useState(false);
  const [batchCountry, setBatchCountry] = useState("");
  const [batchState, setBatchState] = useState("");
  const [batchCity, setBatchCity] = useState("");
  const [batchDateVisited, setBatchDateVisited] = useState("");
  const [isBatchUpdating, setIsBatchUpdating] = useState(false);

  // Sorting
  const [sortField, setSortField] = useState<keyof CandidateItem | "completeness">("row_index");
  const [sortAsc, setSortAsc] = useState(true);

  // Right-Panel Editor State
  const [editPoiName, setEditPoiName] = useState("");
  const [editDisposition, setEditDisposition] = useState<string>("accept");
  const [editLatitude, setEditLatitude] = useState("");
  const [editLongitude, setEditLongitude] = useState("");
  const [editStreetAddress, setEditStreetAddress] = useState("");
  const [editCity, setEditCity] = useState("");
  const [editStateProvince, setEditStateProvince] = useState("");
  const [editPostalCode, setEditPostalCode] = useState("");
  const [editCountry, setEditCountry] = useState("");
  const [editHeroImageUrl, setEditHeroImageUrl] = useState("");
  const [editOfficialUrl, setEditOfficialUrl] = useState("");
  const [editWikiUrl, setEditWikiUrl] = useState("");
  const [editNoWebsites, setEditNoWebsites] = useState(false);
  const [editDurationHours, setEditDurationHours] = useState("");
  const [editDurationDays, setEditDurationDays] = useState("");
  const [editDurationNotes, setEditDurationNotes] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [newTagInput, setNewTagInput] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editReasonToVisit, setEditReasonToVisit] = useState("");
  const [editParentPoiId, setEditParentPoiId] = useState<string>("");
  const [editParentCandidateId, setEditParentCandidateId] = useState<string>("");
  const [editMergeTargetId, setEditMergeTargetId] = useState<string>("");
  const [editDispositionJustification, setEditDispositionJustification] = useState<string>("");
  const [editIsUserOverridden, setEditIsUserOverridden] = useState(false);

  // Selected candidate object
  const selectedCandidate = useMemo(() => {
    return candidates.find((c) => c.id === selectedCandidateId) || null;
  }, [candidates, selectedCandidateId]);

  // Proximity search radius (FR-013, FR-026)
  const [proximityRadiusIndex, setProximityRadiusIndex] = useState(4); // default 1 mi

  const nearbyPoints = useMemo(() => {
    const lat = parseFloat(editLatitude);
    const lon = parseFloat(editLongitude);
    if (isNaN(lat) || isNaN(lon)) return [];

    const radius = PROXIMITY_STEPS[proximityRadiusIndex].miles;
    const list: Array<{ name: string; type: "DB POI" | "Batch Candidate"; distanceMiles: number }> = [];

    for (const p of existingPOIs) {
      const d = haversineMiles(lat, lon, p.latitude, p.longitude);
      if (d <= radius) {
        list.push({ name: p.name, type: "DB POI", distanceMiles: d });
      }
    }

    for (const c of candidates) {
      if (c.id === selectedCandidateId || c.latitude == null || c.longitude == null) continue;
      const d = haversineMiles(lat, lon, c.latitude, c.longitude);
      if (d <= radius) {
        list.push({ name: c.poi_name, type: "Batch Candidate", distanceMiles: d });
      }
    }

    return list.sort((a, b) => a.distanceMiles - b.distanceMiles);
  }, [editLatitude, editLongitude, proximityRadiusIndex, existingPOIs, candidates, selectedCandidateId]);

  // Load candidates on open / filter change
  const loadCandidates = useCallback(async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const res = await ingestApi.listStagingCandidates(jobId, {
        completeness: completenessFilter,
        disposition: dispositionFilter !== "all" ? dispositionFilter : undefined,
        search: searchQuery.trim() || undefined,
      });
      setCandidates(res.candidates);
      if (res.candidates.length > 0) {
        // If current selection is not in list, select the first
        if (!selectedCandidateId || !res.candidates.some((c) => c.id === selectedCandidateId)) {
          setSelectedCandidateId(res.candidates[0].id);
        }
      } else {
        setSelectedCandidateId(null);
      }
    } catch (err: unknown) {
      showToast("Failed to load candidates", "error");
    } finally {
      setIsLoading(false);
    }
  }, [jobId, completenessFilter, dispositionFilter, searchQuery, selectedCandidateId, showToast]);

  useEffect(() => {
    if (isOpen && jobId) {
      loadCandidates();
    }
  }, [isOpen, jobId, loadCandidates]);

  // Synchronize editor state when selected candidate changes
  useEffect(() => {
    if (selectedCandidate) {
      setEditPoiName(selectedCandidate.poi_name || "");
      setEditDisposition(selectedCandidate.user_disposition || selectedCandidate.recommended_disposition || "accept");
      setEditLatitude(selectedCandidate.latitude != null ? String(selectedCandidate.latitude) : "");
      setEditLongitude(selectedCandidate.longitude != null ? String(selectedCandidate.longitude) : "");
      setEditStreetAddress(selectedCandidate.street_address || "");
      setEditCity(selectedCandidate.city || "");
      setEditStateProvince(selectedCandidate.state_province || "");
      setEditPostalCode(selectedCandidate.postal_code || "");
      setEditCountry(selectedCandidate.country || "");
      setEditHeroImageUrl(selectedCandidate.hero_image_url || "");
      setEditOfficialUrl(selectedCandidate.official_url || "");
      setEditWikiUrl(selectedCandidate.wiki_url || "");
      setEditNoWebsites(Boolean(selectedCandidate.no_websites));
      setEditDurationHours(
        selectedCandidate.recommended_duration_hours != null
          ? String(selectedCandidate.recommended_duration_hours)
          : ""
      );
      setEditDurationDays(
        selectedCandidate.recommended_visit_days != null
          ? String(selectedCandidate.recommended_visit_days)
          : ""
      );
      setEditDurationNotes(selectedCandidate.estimated_visit_time_notes || "");
      setEditTags([...(selectedCandidate.tags || [])]);
      setEditDescription(selectedCandidate.description || "");
      setEditReasonToVisit(selectedCandidate.reason_to_visit || "");
      setEditParentPoiId(selectedCandidate.parent_poi_id || "");
      setEditParentCandidateId(selectedCandidate.parent_candidate_id || "");
      setEditMergeTargetId(selectedCandidate.merge_target_id || "");
      setEditDispositionJustification(selectedCandidate.disposition_justification || "");
      setEditIsUserOverridden(Boolean(selectedCandidate.is_user_overridden));
    }
  }, [selectedCandidate]);

  // Completeness calculator helper
  const isCandidateComplete = (cand: CandidateItem): boolean => {
    const hasPhoto = Boolean(cand.hero_image_url && cand.hero_image_url.trim());
    const hasLocation = cand.latitude != null && cand.longitude != null && Boolean(cand.street_address && cand.street_address.trim());
    const hasWebsites = Boolean(cand.official_url && cand.official_url.trim()) || Boolean(cand.no_websites);
    return hasPhoto && hasLocation && hasWebsites;
  };

  // Sort & filter candidates in table
  const sortedCandidates = useMemo(() => {
    return [...candidates].sort((a, b) => {
      let valA: any = a[sortField as keyof CandidateItem];
      let valB: any = b[sortField as keyof CandidateItem];
      if (sortField === "completeness") {
        valA = isCandidateComplete(a) ? 1 : 0;
        valB = isCandidateComplete(b) ? 1 : 0;
      }
      if (valA === valB) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;
      if (valA < valB) return sortAsc ? -1 : 1;
      return sortAsc ? 1 : -1;
    });
  }, [candidates, sortField, sortAsc]);

  const handleSort = (field: keyof CandidateItem | "completeness") => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  // Multi-select toggle
  const toggleSelectAll = () => {
    if (selectedCandidateIds.length === candidates.length) {
      setSelectedCandidateIds([]);
    } else {
      setSelectedCandidateIds(candidates.map((c) => c.id));
    }
  };

  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedCandidateIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Single-candidate enrichment: "AI Enrich POI" (FR-006)
  const handleEnrichSingle = async () => {
    if (!jobId || !selectedCandidateId) return;
    setIsEnrichingSingle(true);
    try {
      const enriched = await ingestApi.enrichSingleCandidate(jobId, selectedCandidateId);
      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidateId ? enriched : c))
      );
      showToast(`Enriched ${enriched.poi_name}!`, "success");
    } catch (err: unknown) {
      showToast("Failed to enrich POI details", "error");
    } finally {
      setIsEnrichingSingle(false);
    }
  };

  // Asynchronous Bulk Enrichment: "AI Enrich All" (FR-007, FR-030)
  const handleEnrichAll = async () => {
    if (!jobId) return;
    setIsEnrichingAll(true);
    try {
      const res = await ingestApi.enrichAllCandidates(jobId);
      showToast(res.message || "Bulk AI enrichment queued in background", "info");
      // Poll progress or reload after short delay
      setTimeout(() => {
        loadCandidates();
        setIsEnrichingAll(false);
      }, 3000);
    } catch (err: unknown) {
      showToast("Failed to launch batch enrichment", "error");
      setIsEnrichingAll(false);
    }
  };

  // Reactive "No Websites" checkbox toggle (FR-010)
  const handleNoWebsitesToggle = (checked: boolean) => {
    setEditNoWebsites(checked);
    if (checked) {
      setEditOfficialUrl("");
      setEditWikiUrl("");
    }
  };

  // Save changes to current candidate
  const handleSaveCandidateChanges = async () => {
    if (!jobId || !selectedCandidateId) return;

    // Validate sublocation parent requirement (FR-018)
    if (editDisposition === "sublocation" && !editParentCandidateId && !editParentPoiId) {
      showToast("Sublocation requires an assigned parent POI", "error");
      return;
    }

    setIsSavingCandidate(true);
    try {
      const updatePayload: CandidateUpdateRequest = {
        poi_name: editPoiName.trim(),
        user_disposition: editDisposition as any,
        latitude: editLatitude ? parseFloat(editLatitude) : null,
        longitude: editLongitude ? parseFloat(editLongitude) : null,
        street_address: editStreetAddress.trim() || null,
        city: editCity.trim() || null,
        state_province: editStateProvince.trim() || null,
        postal_code: editPostalCode.trim() || null,
        country: editCountry.trim() || null,
        hero_image_url: editHeroImageUrl.trim() || null,
        official_url: editOfficialUrl.trim() || null,
        wiki_url: editWikiUrl.trim() || null,
        no_websites: editNoWebsites,
        recommended_duration_hours: editDurationHours ? parseFloat(editDurationHours) : null,
        recommended_visit_days: editDurationDays ? parseInt(editDurationDays, 10) : null,
        estimated_visit_time_notes: editDurationNotes.trim() || null,
        tags: editTags,
        description: editDescription.trim() || null,
        reason_to_visit: editReasonToVisit.trim() || null,
        parent_poi_id: editParentPoiId ? (editParentPoiId as any) : null,
        parent_candidate_id: editParentCandidateId ? (editParentCandidateId as any) : null,
        merge_target_id: editMergeTargetId ? (editMergeTargetId as any) : null,
        disposition_justification: editDispositionJustification.trim() || null,
        is_user_overridden: editIsUserOverridden,
      };

      const updated = await ingestApi.updateStagingCandidate(jobId, selectedCandidateId, updatePayload);
      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidateId ? updated : c))
      );
      showToast("Candidate changes saved!", "success");
    } catch (err: any) {
      const msg = err?.message || "Failed to save candidate changes";
      showToast(msg, "error");
    } finally {
      setIsSavingCandidate(false);
    }
  };

  // Apply Batch Edits to selected rows (FR-024)
  const handleApplyBatchEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId || selectedCandidateIds.length === 0) return;
    setIsBatchUpdating(true);
    try {
      const res = await ingestApi.batchEditCandidates(jobId, {
        candidate_ids: selectedCandidateIds,
        country: batchCountry.trim() || undefined,
        state_province: batchState.trim() || undefined,
        city: batchCity.trim() || undefined,
        date_visited: batchDateVisited.trim() || undefined,
      });
      showToast(`Updated ${res.updated_count} candidates!`, "success");
      setIsBatchEditOpen(false);
      setSelectedCandidateIds([]);
      loadCandidates();
    } catch (err: unknown) {
      showToast("Batch update failed", "error");
    } finally {
      setIsBatchUpdating(false);
    }
  };

  // Commit All Accepted Candidates (FR-012)
  const handleCommitWorkbench = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const summary = await ingestApi.commitWorkbenchJob(jobId);
      showToast(`Committed ${summary.committed_count} POIs to your map!`, "success");
      if (onCommitComplete) {
        onCommitComplete(summary);
      }
      onClose();
    } catch (err: any) {
      showToast(err?.message || "Commit failed", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Discard Entire Staging Batch (FR-015)
  const handleDiscardBatch = async () => {
    if (!jobId) return;
    if (!window.confirm("Are you sure you want to discard this entire import batch? All staged records will be purged.")) {
      return;
    }
    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase1(jobId);
      showToast("Import batch discarded.", "info");
      onClose();
    } catch (err: unknown) {
      showToast("Failed to discard batch", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Export Selected / All Candidates to CSV (FR-014)
  const handleExportCSV = () => {
    const listToExport = selectedCandidateIds.length > 0
      ? candidates.filter((c) => selectedCandidateIds.includes(c.id))
      : candidates;

    if (listToExport.length === 0) {
      showToast("No candidates available to export", "info");
      return;
    }

    const headers = [
      "Row",
      "POI Name",
      "Disposition",
      "Latitude",
      "Longitude",
      "Address",
      "City",
      "State",
      "Country",
      "Hero Image URL",
      "Official URL",
      "Tags",
      "Description",
    ];

    const rows = listToExport.map((c) => [
      c.row_index + 1,
      `"${(c.poi_name || "").replace(/"/g, '""')}"`,
      c.user_disposition || c.recommended_disposition,
      c.latitude ?? "",
      c.longitude ?? "",
      `"${(c.street_address || "").replace(/"/g, '""')}"`,
      `"${(c.city || "").replace(/"/g, '""')}"`,
      `"${(c.state_province || "").replace(/"/g, '""')}"`,
      `"${(c.country || "").replace(/"/g, '""')}"`,
      `"${(c.hero_image_url || "").replace(/"/g, '""')}"`,
      `"${(c.official_url || "").replace(/"/g, '""')}"`,
      `"${(c.tags || []).join("; ").replace(/"/g, '""')}"`,
      `"${(c.description || "").replace(/"/g, '""')}"`,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `vistarae_staging_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        backgroundColor: "rgba(15, 23, 42, 0.75)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      data-testid="import-staging-workbench-modal"
    >
      <div
        style={{
          width: "96vw",
          maxWidth: "1560px",
          height: "92vh",
          backgroundColor: "#ffffff",
          borderRadius: "12px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Top Header Bar */}
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid #e2e8f0",
            backgroundColor: "#f8fafc",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: 0 }}>
                POI Import Staging Workbench
              </h2>
              <span
                style={{
                  fontSize: "12px",
                  padding: "2px 8px",
                  borderRadius: "12px",
                  backgroundColor: "#e0f2fe",
                  color: "#0369a1",
                  fontWeight: 600,
                }}
              >
                {candidates.length} Candidate{candidates.length === 1 ? "" : "s"}
              </span>
            </div>
            <p style={{ fontSize: "12px", color: "#64748b", margin: "2px 0 0 0" }}>
              Inspect, enrich with AI, and resolve POIs in one unified workspace before committing.
            </p>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {selectedCandidateIds.length > 0 && (
              <button
                type="button"
                onClick={() => setIsBatchEditOpen(true)}
                data-testid="batch-edit-btn"
                style={{
                  padding: "6px 12px",
                  backgroundColor: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#334155",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  cursor: "pointer",
                }}
              >
                <span>Batch Edit ({selectedCandidateIds.length})</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleEnrichAll}
              disabled={isEnrichingAll || candidates.length === 0}
              data-testid="ai-enrich-all-btn"
              style={{
                padding: "6px 12px",
                backgroundColor: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#1d4ed8",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                cursor: isEnrichingAll ? "not-allowed" : "pointer",
              }}
            >
              {isEnrichingAll ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              <span>AI Enrich All</span>
            </button>

            <button
              type="button"
              onClick={handleExportCSV}
              data-testid="export-csv-btn"
              title="Export candidates to CSV"
              style={{
                padding: "6px 12px",
                backgroundColor: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#475569",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                cursor: "pointer",
              }}
            >
              <Download size={14} />
              <span>Export</span>
            </button>

            <button
              type="button"
              onClick={handleDiscardBatch}
              data-testid="discard-batch-btn"
              style={{
                padding: "6px 12px",
                backgroundColor: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#be123c",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                cursor: "pointer",
              }}
            >
              <Trash2 size={14} />
              <span>Discard</span>
            </button>

            <button
              type="button"
              onClick={handleCommitWorkbench}
              disabled={isSubmitting || candidates.length === 0}
              data-testid="commit-import-btn"
              style={{
                padding: "7px 16px",
                backgroundColor: "#16a34a",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: "6px",
                cursor: isSubmitting ? "not-allowed" : "pointer",
                boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
              }}
            >
              {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              <span>Commit Import</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              data-testid="workbench-close-btn"
              style={{
                padding: "6px",
                backgroundColor: "transparent",
                border: "none",
                color: "#64748b",
                cursor: "pointer",
                borderRadius: "6px",
                marginLeft: "6px",
              }}
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Main Split Body Container */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left Master Table Panel */}
          <div
            style={{
              flex: "0 0 58%",
              display: "flex",
              flexDirection: "column",
              borderRight: "1px solid #e2e8f0",
              overflow: "hidden",
            }}
          >
            {/* Filter Bar */}
            <div
              style={{
                padding: "10px 14px",
                borderBottom: "1px solid #f1f5f9",
                backgroundColor: "#ffffff",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                flexWrap: "wrap",
                flexShrink: 0,
              }}
            >
              {/* Search input */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 10px",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  flex: 1,
                  minWidth: "180px",
                  backgroundColor: "#ffffff",
                }}
              >
                <Search size={14} color="#94a3b8" />
                <input
                  type="text"
                  placeholder="Search by name, city, tag..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="workbench-search-input"
                  style={{
                    border: "none",
                    outline: "none",
                    width: "100%",
                    fontSize: "12px",
                  }}
                />
              </div>

              {/* Completeness Filter */}
              <select
                value={completenessFilter}
                onChange={(e) => setCompletenessFilter(e.target.value as CompletenessFilter)}
                data-testid="workbench-completeness-filter"
                style={{
                  padding: "6px 10px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "12px",
                  color: "#334155",
                  backgroundColor: "#f8fafc",
                  cursor: "pointer",
                }}
              >
                <option value="all">All Items</option>
                <option value="incomplete">Incomplete Only</option>
                <option value="missing_photo">Missing Photo</option>
                <option value="missing_location">Missing Coordinates/Address</option>
                <option value="missing_websites">Missing Websites</option>
              </select>

              {/* Disposition Filter */}
              <select
                value={dispositionFilter}
                onChange={(e) => setDispositionFilter(e.target.value)}
                data-testid="workbench-disposition-filter"
                style={{
                  padding: "6px 10px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "12px",
                  color: "#334155",
                  backgroundColor: "#f8fafc",
                  cursor: "pointer",
                }}
              >
                <option value="all">All Dispositions</option>
                <option value="accept">Accept (New POI)</option>
                <option value="sublocation">Sublocation</option>
                <option value="in_batch_merge">In-Batch Merge</option>
                <option value="update_existing">Update Existing POI</option>
                <option value="exclude">Exclude</option>
                <option value="ignore">Ignore</option>
              </select>
            </div>

            {/* Candidate Table */}
            <div style={{ flex: 1, overflowY: "auto", overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                <thead>
                  <tr style={{ backgroundColor: "#f8fafc", position: "sticky", top: 0, zIndex: 10, textAlign: "left" }}>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", width: "36px" }}>
                      <input
                        type="checkbox"
                        checked={candidates.length > 0 && selectedCandidateIds.length === candidates.length}
                        onChange={toggleSelectAll}
                        data-testid="select-all-checkbox"
                        style={{ cursor: "pointer" }}
                      />
                    </th>
                    <th
                      onClick={() => handleSort("row_index")}
                      style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", width: "40px", cursor: "pointer" }}
                    >
                      #
                    </th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", width: "46px" }}>
                      Photo
                    </th>
                    <th
                      onClick={() => handleSort("poi_name")}
                      style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", cursor: "pointer" }}
                    >
                      POI Name
                    </th>
                    <th
                      onClick={() => handleSort("completeness")}
                      style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", width: "110px", cursor: "pointer" }}
                    >
                      Completeness
                    </th>
                    <th style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>
                      Location
                    </th>
                    <th
                      onClick={() => handleSort("user_disposition")}
                      style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0", width: "140px", cursor: "pointer" }}
                    >
                      Disposition
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCandidates.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "32px", color: "#94a3b8" }}>
                        {isLoading ? "Loading candidates..." : "No candidates found matching the selected filters."}
                      </td>
                    </tr>
                  ) : (
                    sortedCandidates.map((cand) => {
                      const isSelected = cand.id === selectedCandidateId;
                      const isChecked = selectedCandidateIds.includes(cand.id);
                      const complete = isCandidateComplete(cand);
                      const disp = cand.user_disposition || cand.recommended_disposition || "accept";

                      return (
                        <tr
                          key={cand.id}
                          onClick={() => setSelectedCandidateId(cand.id)}
                          data-testid={`candidate-row-${cand.id}`}
                          style={{
                            cursor: "pointer",
                            backgroundColor: isSelected
                              ? "#eff6ff"
                              : isChecked
                              ? "#f8fafc"
                              : "transparent",
                            borderBottom: "1px solid #f1f5f9",
                            transition: "background-color 0.1s ease",
                          }}
                        >
                          {/* Checkbox */}
                          <td style={{ padding: "8px 10px" }} onClick={(e) => toggleSelectRow(cand.id, e)}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}}
                              data-testid={`row-checkbox-${cand.id}`}
                              style={{ cursor: "pointer" }}
                            />
                          </td>

                          {/* Row Number */}
                          <td style={{ padding: "8px 10px", color: "#64748b", fontWeight: 500 }}>
                            {cand.row_index + 1}
                          </td>

                          {/* Hero Thumbnail */}
                          <td style={{ padding: "6px 8px" }}>
                            {cand.hero_image_url ? (
                              <img
                                src={cand.hero_image_url}
                                alt={cand.poi_name}
                                style={{
                                  width: "36px",
                                  height: "36px",
                                  objectFit: "cover",
                                  borderRadius: "4px",
                                  border: "1px solid #e2e8f0",
                                }}
                                onError={(e) => {
                                  (e.target as HTMLElement).style.display = "none";
                                }}
                              />
                            ) : (
                              <div
                                style={{
                                  width: "36px",
                                  height: "36px",
                                  borderRadius: "4px",
                                  backgroundColor: "#f1f5f9",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  color: "#94a3b8",
                                }}
                              >
                                <ImageIcon size={16} />
                              </div>
                            )}
                          </td>

                          {/* POI Name */}
                          <td style={{ padding: "8px 10px" }}>
                            <div style={{ fontWeight: 600, color: "#1e293b" }}>{cand.poi_name}</div>
                            {cand.is_duplicate && (
                              <span
                                style={{
                                  display: "inline-block",
                                  fontSize: "10px",
                                  padding: "1px 5px",
                                  borderRadius: "4px",
                                  backgroundColor: "#fef3c7",
                                  color: "#b45309",
                                  fontWeight: 600,
                                  marginTop: "2px",
                                }}
                              >
                                Potential Duplicate
                              </span>
                            )}
                          </td>

                          {/* Completeness Badge */}
                          <td style={{ padding: "8px 10px" }}>
                            {complete ? (
                              <span
                                data-testid={`completeness-badge-complete`}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                  backgroundColor: "#dcfce7",
                                  color: "#15803d",
                                }}
                              >
                                <Check size={11} /> Complete
                              </span>
                            ) : (
                              <span
                                data-testid={`completeness-badge-incomplete`}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                  backgroundColor: "#fef3c7",
                                  color: "#b45309",
                                }}
                              >
                                <AlertTriangle size={11} /> Incomplete
                              </span>
                            )}
                          </td>

                          {/* Location */}
                          <td style={{ padding: "8px 10px", color: "#475569" }}>
                            {cand.city
                              ? `${cand.city}${cand.country ? `, ${cand.country}` : ""}`
                              : cand.state_province
                              ? `${cand.state_province}${cand.country ? `, ${cand.country}` : ""}`
                              : cand.country || "No City"}
                          </td>

                          {/* Disposition */}
                          <td style={{ padding: "8px 10px" }}>
                            <span
                              style={{
                                display: "inline-block",
                                fontSize: "11px",
                                fontWeight: 600,
                                padding: "2px 6px",
                                borderRadius: "4px",
                                backgroundColor:
                                  disp === "accept"
                                    ? "#f0fdf4"
                                    : disp === "sublocation"
                                    ? "#faf5ff"
                                    : disp === "in_batch_merge"
                                    ? "#eff6ff"
                                    : disp === "exclude" || disp === "ignore"
                                    ? "#fef2f2"
                                    : "#f8fafc",
                                color:
                                  disp === "accept"
                                    ? "#166534"
                                    : disp === "sublocation"
                                    ? "#7e22ce"
                                    : disp === "in_batch_merge"
                                    ? "#1d4ed8"
                                    : disp === "exclude" || disp === "ignore"
                                    ? "#991b1b"
                                    : "#475569",
                                border: "1px solid #e2e8f0",
                              }}
                            >
                              {disp}
                            </span>
                            {cand.is_user_overridden && (
                              <span
                                data-testid={`override-badge-${cand.id}`}
                                style={{
                                  display: "inline-block",
                                  marginLeft: "4px",
                                  fontSize: "9px",
                                  fontWeight: 700,
                                  backgroundColor: "#fef3c7",
                                  color: "#92400e",
                                  padding: "1px 4px",
                                  borderRadius: "3px",
                                }}
                              >
                                Override
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right Candidate Editor Panel */}
          <div
            style={{
              flex: "0 0 42%",
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#ffffff",
              overflow: "hidden",
            }}
          >
            {selectedCandidate ? (
              <>
                {/* Fixed Editor Header */}
                <div
                  style={{
                    padding: "12px 18px",
                    borderBottom: "1px solid #e2e8f0",
                    backgroundColor: "#f8fafc",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexShrink: 0,
                  }}
                >
                  <div>
                    <span style={{ fontSize: "11px", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                      Candidate #{selectedCandidate.row_index + 1} of {candidates.length}
                    </span>
                    <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#0f172a", margin: "2px 0 0 0" }}>
                      {editPoiName || "Untitled POI"}
                    </h3>
                  </div>

                  {/* Single-Candidate AI Enrich Button (FR-006) */}
                  <button
                    type="button"
                    onClick={handleEnrichSingle}
                    disabled={isEnrichingSingle}
                    data-testid="ai-enrich-poi-btn"
                    style={{
                      padding: "6px 12px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      cursor: isEnrichingSingle ? "not-allowed" : "pointer",
                      boxShadow: "0 1px 2px rgba(37,99,235,0.2)",
                    }}
                  >
                    {isEnrichingSingle ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    <span>{isEnrichingSingle ? "Enriching..." : "AI Enrich POI"}</span>
                  </button>
                </div>

                {/* Scrollable Body Container */}
                <div
                  style={{
                    flex: 1,
                    overflowY: "auto",
                    padding: "16px 18px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                  }}
                  data-testid="candidate-editor-scroll-container"
                >
                  {/* POI Name & Disposition */}
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ flex: 2 }}>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#475569", marginBottom: "4px" }}>
                        POI Name:
                      </label>
                      <input
                        type="text"
                        value={editPoiName}
                        onChange={(e) => setEditPoiName(e.target.value)}
                        data-testid="editor-poi-name-input"
                        style={{ width: "100%", padding: "7px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px" }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#475569", marginBottom: "4px" }}>
                        Disposition:
                      </label>
                      <select
                        value={editDisposition}
                        onChange={(e) => {
                          setEditDisposition(e.target.value);
                          setEditIsUserOverridden(true);
                          if (!editDispositionJustification) {
                            setEditDispositionJustification(`User overridden from ${selectedCandidate.recommended_disposition}`);
                          }
                        }}
                        data-testid="editor-disposition-select"
                        style={{ width: "100%", padding: "7px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "13px", backgroundColor: "#ffffff" }}
                      >
                        <option value="accept">Accept (New POI)</option>
                        <option value="sublocation">Sublocation</option>
                        <option value="in_batch_merge">In-Batch Merge</option>
                        <option value="update_existing">Update Existing POI</option>
                        <option value="exclude">Exclude</option>
                        <option value="ignore">Ignore</option>
                      </select>
                    </div>
                  </div>

                  {/* Disposition Justification & Override Indicator */}
                  {editIsUserOverridden && (
                    <div
                      style={{
                        padding: "8px 12px",
                        backgroundColor: "#fefce8",
                        border: "1px solid #fef08a",
                        borderRadius: "6px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
                        <span style={{ fontSize: "11px", fontWeight: 700, color: "#854d0e" }}>
                          Disposition Justification (User Overridden):
                        </span>
                        <span style={{ fontSize: "10px", fontWeight: 700, backgroundColor: "#fde047", color: "#713f12", padding: "1px 5px", borderRadius: "3px" }}>
                          Overridden
                        </span>
                      </div>
                      <input
                        type="text"
                        value={editDispositionJustification}
                        onChange={(e) => setEditDispositionJustification(e.target.value)}
                        placeholder="Reason for changing disposition..."
                        data-testid="disposition-justification-input"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>
                  )}

                  {/* Sublocation Hierarchy Assignment */}
                  {editDisposition === "sublocation" && (
                    <div
                      style={{
                        padding: "10px 12px",
                        backgroundColor: "#faf5ff",
                        border: "1px solid #e9d5ff",
                        borderRadius: "6px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                      }}
                    >
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "#6b21a8" }}>
                        Sublocation Parent Assignment:
                      </span>

                      {!editParentCandidateId && !editParentPoiId && (
                        <div
                          data-testid="sublocation-missing-parent-error"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            backgroundColor: "#fef2f2",
                            border: "1px solid #fecaca",
                            color: "#b91c1c",
                            fontSize: "11px",
                            fontWeight: 600,
                          }}
                        >
                          <AlertTriangle size={14} />
                          <span>Parent POI required for Sublocation disposition</span>
                        </div>
                      )}

                      <div>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#581c87", marginBottom: "2px" }}>
                          Parent Candidate (in this CSV batch):
                        </label>
                        <select
                          value={editParentCandidateId}
                          onChange={(e) => setEditParentCandidateId(e.target.value)}
                          data-testid="parent-candidate-select"
                          style={{ width: "100%", padding: "6px 8px", borderRadius: "4px", border: "1px solid #c084fc", fontSize: "12px", backgroundColor: "#ffffff" }}
                        >
                          <option value="">-- None (Or select DB Parent below) --</option>
                          {candidates
                            .filter((c) => c.id !== selectedCandidate.id)
                            .map((c) => (
                              <option key={c.id} value={c.id}>
                                Row #{c.row_index + 1}: {c.poi_name}
                              </option>
                            ))}
                        </select>
                      </div>

                      <div>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#581c87", marginBottom: "2px" }}>
                          Or Parent POI (Existing in Database):
                        </label>
                        <select
                          value={editParentPoiId}
                          onChange={(e) => setEditParentPoiId(e.target.value)}
                          data-testid="parent-poi-select"
                          style={{ width: "100%", padding: "6px 8px", borderRadius: "4px", border: "1px solid #c084fc", fontSize: "12px", backgroundColor: "#ffffff" }}
                        >
                          <option value="">-- None --</option>
                          {existingPOIs.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  {/* In-Batch Merge Target Assignment */}
                  {editDisposition === "in_batch_merge" && (
                    <div
                      style={{
                        padding: "10px 12px",
                        backgroundColor: "#eff6ff",
                        border: "1px solid #bfdbfe",
                        borderRadius: "6px",
                      }}
                    >
                      <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#1e40af", marginBottom: "4px" }}>
                        Merge Target Candidate:
                      </label>
                      <select
                        value={editMergeTargetId}
                        onChange={(e) => setEditMergeTargetId(e.target.value)}
                        data-testid="merge-target-select"
                        style={{ width: "100%", padding: "6px 8px", borderRadius: "4px", border: "1px solid #93c5fd", fontSize: "12px", backgroundColor: "#ffffff" }}
                      >
                        <option value="">-- Select Target Candidate --</option>
                        {candidates
                          .filter((c) => c.id !== selectedCandidate.id)
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              Row #{c.row_index + 1}: {c.poi_name}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}

                  {/* Hero Photo & Uncropped Preview */}
                  <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "12px" }}>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#475569", marginBottom: "4px" }}>
                      Hero Photo URL:
                    </label>
                    <input
                      type="url"
                      value={editHeroImageUrl}
                      onChange={(e) => setEditHeroImageUrl(e.target.value)}
                      placeholder="https://example.com/photo.jpg"
                      data-testid="hero-image-url-input"
                      style={{ width: "100%", padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                    />

                    {/* Uncropped Live Preview */}
                    {editHeroImageUrl && (
                      <div
                        style={{
                          marginTop: "10px",
                          borderRadius: "6px",
                          backgroundColor: "#0f172a",
                          padding: "6px",
                          textAlign: "center",
                        }}
                      >
                        <img
                          src={editHeroImageUrl}
                          alt="Hero Preview"
                          data-testid="hero-image-uncropped-preview"
                          style={{
                            maxHeight: "220px",
                            maxWidth: "100%",
                            objectFit: "contain",
                            borderRadius: "4px",
                          }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = "none";
                          }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Coordinates & Location Fields */}
                  <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 700, color: "#1e293b", display: "flex", alignItems: "center", gap: "6px" }}>
                        <MapPin size={14} color="#0284c7" /> Location Coordinates & Address
                      </span>
                    </div>

                    <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Latitude:</label>
                        <input
                          type="text"
                          value={editLatitude}
                          onChange={(e) => setEditLatitude(e.target.value)}
                          placeholder="e.g. 41.8781"
                          data-testid="latitude-input"
                          style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Longitude:</label>
                        <input
                          type="text"
                          value={editLongitude}
                          onChange={(e) => setEditLongitude(e.target.value)}
                          placeholder="e.g. -87.6298"
                          data-testid="longitude-input"
                          style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                        />
                      </div>
                    </div>

                    <div style={{ marginBottom: "6px" }}>
                      <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Street Address:</label>
                      <input
                        type="text"
                        value={editStreetAddress}
                        onChange={(e) => setEditStreetAddress(e.target.value)}
                        placeholder="Street address..."
                        data-testid="street-address-input"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>

                    <div style={{ display: "flex", gap: "8px" }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>City / Town:</label>
                        <input
                          type="text"
                          value={editCity}
                          onChange={(e) => setEditCity(e.target.value)}
                          data-testid="city-input"
                          style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>State / Province:</label>
                        <input
                          type="text"
                          value={editStateProvince}
                          onChange={(e) => setEditStateProvince(e.target.value)}
                          data-testid="state-province-input"
                          style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Country:</label>
                        <input
                          type="text"
                          value={editCountry}
                          onChange={(e) => setEditCountry(e.target.value)}
                          data-testid="country-input"
                          style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                        />
                      </div>
                    </div>

                    {/* Proximity Radius Slider & Nearby Count Badge (FR-013, FR-026) */}
                    <div
                      style={{
                        marginTop: "12px",
                        padding: "10px",
                        backgroundColor: "#f8fafc",
                        borderRadius: "6px",
                        border: "1px solid #e2e8f0",
                      }}
                      data-testid="proximity-search-container"
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "6px",
                        }}
                      >
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "#334155" }}>
                          Nearby Search Radius: <strong>{PROXIMITY_STEPS[proximityRadiusIndex].label}</strong>
                        </span>
                        <span
                          data-testid="nearby-poi-count-badge"
                          style={{
                            padding: "2px 8px",
                            borderRadius: "12px",
                            backgroundColor: nearbyPoints.length > 0 ? "#e0f2fe" : "#f1f5f9",
                            color: nearbyPoints.length > 0 ? "#0369a1" : "#64748b",
                            fontSize: "11px",
                            fontWeight: 700,
                          }}
                        >
                          {nearbyPoints.length} Nearby Point{nearbyPoints.length === 1 ? "" : "s"}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={PROXIMITY_STEPS.length - 1}
                        value={proximityRadiusIndex}
                        onChange={(e) => setProximityRadiusIndex(parseInt(e.target.value, 10))}
                        data-testid="proximity-radius-slider"
                        style={{ width: "100%", cursor: "pointer" }}
                      />
                      {nearbyPoints.length > 0 && (
                        <div style={{ marginTop: "6px", maxHeight: "80px", overflowY: "auto", fontSize: "11px" }}>
                          {nearbyPoints.slice(0, 5).map((np, idx) => (
                            <div key={idx} style={{ color: "#475569", padding: "1px 0" }}>
                              • {np.name} ({np.type}, ~{np.distanceMiles < 0.1 ? `${Math.round(np.distanceMiles * 5280)} ft` : `${np.distanceMiles.toFixed(1)} mi`})
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Related Websites & Reactive "No Websites" Checkbox (FR-010) */}
                  <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ fontSize: "12px", fontWeight: 700, color: "#1e293b", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Globe size={14} color="#2563eb" /> Related Websites
                      </span>

                      {/* Reactive No Websites Checkbox */}
                      <label
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          fontSize: "11px",
                          fontWeight: 600,
                          color: "#475569",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={editNoWebsites}
                          onChange={(e) => handleNoWebsitesToggle(e.target.checked)}
                          data-testid="no-websites-checkbox"
                          style={{ cursor: "pointer" }}
                        />
                        <span>No Websites</span>
                      </label>
                    </div>

                    {!editNoWebsites ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        <div>
                          <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Official Website:</label>
                          <input
                            type="url"
                            value={editOfficialUrl}
                            onChange={(e) => {
                              setEditOfficialUrl(e.target.value);
                              if (e.target.value.trim()) setEditNoWebsites(false);
                            }}
                            placeholder="https://..."
                            data-testid="official-url-input"
                            style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Wikipedia Article:</label>
                          <input
                            type="url"
                            value={editWikiUrl}
                            onChange={(e) => {
                              setEditWikiUrl(e.target.value);
                              if (e.target.value.trim()) setEditNoWebsites(false);
                            }}
                            placeholder="https://en.wikipedia.org/wiki/..."
                            data-testid="wiki-url-input"
                            style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          padding: "8px",
                          borderRadius: "4px",
                          backgroundColor: "#f1f5f9",
                          color: "#64748b",
                          fontSize: "11px",
                          fontStyle: "italic",
                        }}
                      >
                        Web scraping skipped: POI verified to have no relevant web presence.
                      </div>
                    )}
                  </div>

                  {/* Visit Duration & Notes */}
                  <div style={{ display: "flex", gap: "8px" }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Est. Hours:</label>
                      <input
                        type="number"
                        step="0.5"
                        value={editDurationHours}
                        onChange={(e) => setEditDurationHours(e.target.value)}
                        placeholder="2.5"
                        data-testid="duration-hours-input"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Est. Days:</label>
                      <input
                        type="number"
                        value={editDurationDays}
                        onChange={(e) => setEditDurationDays(e.target.value)}
                        placeholder="1"
                        data-testid="duration-days-input"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>
                    <div style={{ flex: 2 }}>
                      <label style={{ display: "block", fontSize: "10px", fontWeight: 600, color: "#64748b" }}>Visit Timing Notes:</label>
                      <input
                        type="text"
                        value={editDurationNotes}
                        onChange={(e) => setEditDurationNotes(e.target.value)}
                        placeholder="Best early morning..."
                        data-testid="duration-notes-input"
                        style={{ width: "100%", padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>
                  </div>

                  {/* Tags */}
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#475569", marginBottom: "4px" }}>
                      Tags:
                    </label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "6px" }}>
                      {editTags.map((tag) => (
                        <span
                          key={tag}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "2px 8px",
                            borderRadius: "12px",
                            backgroundColor: "#f1f5f9",
                            fontSize: "11px",
                            color: "#334155",
                          }}
                        >
                          {tag}
                          <button
                            type="button"
                            onClick={() => setEditTags(editTags.filter((t) => t !== tag))}
                            style={{ border: "none", background: "none", padding: 0, cursor: "pointer", color: "#94a3b8" }}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <input
                        type="text"
                        placeholder="Add tag and press Enter..."
                        value={newTagInput}
                        onChange={(e) => setNewTagInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && newTagInput.trim()) {
                            e.preventDefault();
                            if (!editTags.includes(newTagInput.trim())) {
                              setEditTags([...editTags, newTagInput.trim()]);
                            }
                            setNewTagInput("");
                          }
                        }}
                        style={{ flex: 1, padding: "5px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                      />
                    </div>
                  </div>

                  {/* Description & Reason to Visit */}
                  <div>
                    <label style={{ display: "block", fontSize: "11px", fontWeight: 700, color: "#475569", marginBottom: "4px" }}>
                      Description:
                    </label>
                    <textarea
                      rows={3}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      data-testid="description-textarea"
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "4px", border: "1px solid #cbd5e1", fontSize: "12px", resize: "vertical" }}
                    />
                  </div>
                </div>

                {/* PINNED FOOTER CONTAINER (FR-003, FR-011) */}
                <div
                  style={{
                    flexShrink: 0,
                    padding: "12px 18px",
                    borderTop: "1px solid #e2e8f0",
                    backgroundColor: "#f8fafc",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    gap: "10px",
                  }}
                  data-testid="candidate-editor-pinned-footer"
                >
                  <button
                    type="button"
                    onClick={() => {
                      if (selectedCandidate) {
                        setEditPoiName(selectedCandidate.poi_name || "");
                        setEditHeroImageUrl(selectedCandidate.hero_image_url || "");
                        showToast("Changes reset", "info");
                      }
                    }}
                    style={{
                      padding: "8px 14px",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      backgroundColor: "#ffffff",
                      fontSize: "12px",
                      fontWeight: 600,
                      color: "#475569",
                      cursor: "pointer",
                    }}
                  >
                    Reset
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveCandidateChanges}
                    disabled={isSavingCandidate}
                    data-testid="save-candidate-changes-btn"
                    style={{
                      padding: "8px 18px",
                      borderRadius: "6px",
                      border: "none",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      fontSize: "13px",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      cursor: isSavingCandidate ? "not-allowed" : "pointer",
                      boxShadow: "0 1px 2px rgba(37,99,235,0.25)",
                    }}
                  >
                    {isSavingCandidate ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    <span>Save Candidate Changes</span>
                  </button>
                </div>
              </>
            ) : (
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#94a3b8",
                  fontSize: "13px",
                }}
              >
                Select a candidate from the table to inspect and edit details.
              </div>
            )}
          </div>
        </div>

        {/* Batch Edit Modal Dialog (FR-024) */}
        {isBatchEditOpen && (
          <Modal
            isOpen={true}
            onClose={() => setIsBatchEditOpen(false)}
            title={`Batch Edit ${selectedCandidateIds.length} Candidate${selectedCandidateIds.length === 1 ? "" : "s"}`}
            maxWidth="480px"
          >
            <form onSubmit={handleApplyBatchEdit} data-testid="batch-edit-form" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <p style={{ fontSize: "12px", color: "#64748b", margin: 0 }}>
                Leave fields blank to keep existing values. Any entered value will be applied across all {selectedCandidateIds.length} selected candidates.
              </p>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>Country:</label>
                <input
                  type="text"
                  value={batchCountry}
                  onChange={(e) => setBatchCountry(e.target.value)}
                  placeholder="e.g. Japan"
                  data-testid="batch-country-input"
                  style={{ width: "100%", padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>State / Province:</label>
                <input
                  type="text"
                  value={batchState}
                  onChange={(e) => setBatchState(e.target.value)}
                  placeholder="e.g. Kansai"
                  data-testid="batch-state-input"
                  style={{ width: "100%", padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>City / Town:</label>
                <input
                  type="text"
                  value={batchCity}
                  onChange={(e) => setBatchCity(e.target.value)}
                  placeholder="e.g. Kyoto"
                  data-testid="batch-city-input"
                  style={{ width: "100%", padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>Date Visited:</label>
                <input
                  type="date"
                  value={batchDateVisited}
                  onChange={(e) => setBatchDateVisited(e.target.value)}
                  data-testid="batch-date-visited-input"
                  style={{ width: "100%", padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "8px" }}>
                <button
                  type="button"
                  onClick={() => setIsBatchEditOpen(false)}
                  style={{ padding: "6px 12px", borderRadius: "6px", border: "1px solid #cbd5e1", background: "#fff", fontSize: "12px", cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isBatchUpdating}
                  data-testid="apply-batch-edit-btn"
                  style={{
                    padding: "6px 16px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: "#2563eb",
                    color: "#fff",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: isBatchUpdating ? "not-allowed" : "pointer",
                  }}
                >
                  {isBatchUpdating ? "Applying..." : "Apply Changes"}
                </button>
              </div>
            </form>
          </Modal>
        )}
      </div>
    </div>
  );
};
