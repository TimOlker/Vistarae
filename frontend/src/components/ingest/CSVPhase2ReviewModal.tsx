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
 * @deprecated Superseded by CSVImportWorkbenchModal.tsx in 014-unified-import-staging-workbench.
 */

import React, { useEffect, useMemo, useState } from "react";
import { exportPhase2Candidates, type ExportFormat } from "../../services/exportApi";
import { inferWebsiteName } from "../../utils/websiteInference";
import { Modal } from "../common/Modal";
import { ingestApi, type CandidateItem } from "../../services/ingestApi";
import { apiFetch } from "../../services/api";
import { useToast } from "../../context/ToastContext";
import { CSVEnrichmentProgressModal } from "./CSVEnrichmentProgressModal";
import {
  Save,
  X,
  MapPin,
  CheckCircle,
  EyeOff,
  Sparkles,
  ArrowLeft,
  Search,
  Check,
  Loader2,
  RefreshCw,
  Compass,
  ExternalLink,
  Globe,
  Clock,
  Tag as TagIcon,
  Image as ImageIcon,
  Plus,
  Trash2,
  Layers,
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  AlertCircle,
} from "lucide-react";
import { CandidateMiniMap } from "./CSVTriageModal";

export type SortPriority = "poi" | "location";

export type Phase2SortField =
  | "poi_name"
  | "country"
  | "state_province"
  | "city"
  | "status"
  | "disposition"
  | "data_status"
  | "row_index";

export interface CandidateDataStatus {
  isComplete: boolean;
  missingFields: string[];
}

export function getCandidateDataStatus(cand: CandidateItem): CandidateDataStatus {
  const missing: string[] = [];
  if (!cand.hero_image_url || !cand.hero_image_url.trim()) missing.push("Hero Photo");
  const related = (cand as any).related_websites || [];
  const hasOfficial = Boolean(
    (cand.official_url && cand.official_url.trim()) ||
      related.some((s: any) => s.name?.toLowerCase().includes("official"))
  );
  const hasWiki = Boolean(
    (cand.wiki_url && cand.wiki_url.trim()) ||
      related.some((s: any) => s.name?.toLowerCase().includes("wikipedia") || s.url?.toLowerCase().includes("wikipedia.org"))
  );
  if (!hasOfficial) missing.push("Official Website");
  if (!hasWiki) missing.push("Wikipedia");
  if (!cand.description || !cand.description.trim()) missing.push("Description");
  if (!cand.reason_to_visit || !cand.reason_to_visit.trim()) missing.push("Reason to Visit");
  if (!cand.tags || cand.tags.length === 0) missing.push("Tags");
  if (
    (cand.recommended_duration_hours === null || cand.recommended_duration_hours === undefined) &&
    (cand.recommended_visit_days === null || cand.recommended_visit_days === undefined)
  ) {
    missing.push("Duration");
  }
  return {
    isComplete: missing.length === 0,
    missingFields: missing,
  };
}

export interface CSVPhase2ReviewModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onCommitComplete: () => void;
  onBackToPhase1?: (jobId?: string) => void;
}

export const CSVPhase2ReviewModal: React.FC<CSVPhase2ReviewModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onCommitComplete,
  onBackToPhase1,
}) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);

  const [exportFormat, setExportFormat] = useState<ExportFormat>("csv");

  const [isExporting, setIsExporting] = useState(false);



  const handleExportSelected = async () => {

    if (!selectedCandidateIds || selectedCandidateIds.length === 0) {

      showToast("No records selected. Please select at least one record to export.", "warning");

      return;

    }

    if (!jobId) {

      showToast("No active job ID for export.", "error");

      return;

    }

    try {

      setIsExporting(true);

      await exportPhase2Candidates(jobId, selectedCandidateIds, exportFormat);

      showToast(`Successfully exported ${selectedCandidateIds.length} candidate(s)`, "success");

    } catch (err: any) {

      showToast(err.message || "Failed to export candidates", "error");

    } finally {

      setIsExporting(false);

    }

  };
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEnriching, setIsEnriching] = useState(false);
  const [isEnrichProgressOpen, setIsEnrichProgressOpen] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [filterText, setFilterText] = useState("");

  // Sorting state
  const [sortPriority, setSortPriority] = useState<SortPriority>("poi");
  const [sortField, setSortField] = useState<Phase2SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const handleSort = (field: Phase2SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const renderSortIcon = (field: Phase2SortField) => {
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

    if (sortPriority === "poi" && field === "poi_name") {
      return <ArrowUp size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />;
    }
    if (sortPriority === "location" && field === "country") {
      return <ArrowUp size={13} style={{ color: "#2563eb", marginLeft: "4px" }} />;
    }
    return <ArrowUpDown size={13} style={{ opacity: 0.35, marginLeft: "4px" }} />;
  };

  // Approved user tags library
  const [approvedTags, setApprovedTags] = useState<{ id?: string; name: string; slug: string }[]>([]);

  // Right-hand editor form state
  const [editPoiName, setEditPoiName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editReasonToVisit, setEditReasonToVisit] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editStreetAddress, setEditStreetAddress] = useState("");
  const [editCity, setEditCity] = useState("");
  const [editHeroImageUrl, setEditHeroImageUrl] = useState("");
  const [editDurationHours, setEditDurationHours] = useState<string>("");
  const [editDurationDays, setEditDurationDays] = useState<string>("");
  const [editDurationNotes, setEditDurationNotes] = useState("");
  const [editRelatedWebsites, setEditRelatedWebsites] = useState<{ name: string; url: string }[]>([]);
  const [newWebsiteName, setNewWebsiteName] = useState("");
  const [newWebsiteUrl, setNewWebsiteUrl] = useState("");
  const [editUpdateCoordinates, setEditUpdateCoordinates] = useState(false);
  const [isSavingCandidate, setIsSavingCandidate] = useState(false);

  // Normalizes an array of raw tags strictly against the user's configured Tags Library
  const normalizeToApprovedTags = (
    rawTags: string[],
    library: { name: string; slug: string; aliases?: string[] }[],
  ): string[] => {
    if (!library || library.length === 0) return rawTags || [];
    const lookup = new Map<string, string>();
    library.forEach((tag) => {
      lookup.set(tag.name.toLowerCase(), tag.name);
      lookup.set(tag.slug.toLowerCase(), tag.name);
      (tag.aliases || []).forEach((a) => lookup.set(a.toLowerCase(), tag.name));
    });

    const result = new Set<string>();
    (rawTags || []).forEach((t) => {
      const canonical = lookup.get(t.trim().toLowerCase());
      if (canonical) {
        result.add(canonical);
      }
    });
    return Array.from(result);
  };

  // Sync selected candidate fields into the editor state
  const selectedCandidate = useMemo(
    () => candidates.find((c) => c.id === selectedCandidateId) || null,
    [candidates, selectedCandidateId],
  );

  // Compute distinct tags present across all currently selected POIs (strictly filtered to approvedTags)
  const distinctTagsInSelection = useMemo(() => {
    const selectedCands = candidates.filter((c) => selectedCandidateIds.includes(c.id));
    const allTags = selectedCands.flatMap((c) => c.tags || []);
    const normalized = normalizeToApprovedTags(allTags, approvedTags);
    return normalized.sort();
  }, [candidates, selectedCandidateIds, approvedTags]);

  useEffect(() => {
    if (selectedCandidate) {
      setEditPoiName(selectedCandidate.poi_name || "");
      setEditDescription(selectedCandidate.description || "");
      setEditReasonToVisit(selectedCandidate.reason_to_visit || "");
      setEditTags(normalizeToApprovedTags(selectedCandidate.tags || [], approvedTags));
      setEditStreetAddress(selectedCandidate.street_address || "");
      setEditCity(selectedCandidate.city || "");
      const rawRelated = (selectedCandidate as any).related_websites || [];
      const initialSites: { name: string; url: string }[] = [...rawRelated];
      const existingUrls = new Set(initialSites.map((s) => s.url.trim().toLowerCase().replace(/\/$/, "")));
      if (selectedCandidate.official_url && selectedCandidate.official_url.trim()) {
        const norm = selectedCandidate.official_url.trim().toLowerCase().replace(/\/$/, "");
        if (!existingUrls.has(norm)) {
          existingUrls.add(norm);
          initialSites.unshift({ name: "Official Website", url: selectedCandidate.official_url.trim() });
        }
      }
      if (selectedCandidate.wiki_url && selectedCandidate.wiki_url.trim()) {
        const norm = selectedCandidate.wiki_url.trim().toLowerCase().replace(/\/$/, "");
        if (!existingUrls.has(norm)) {
          existingUrls.add(norm);
          initialSites.push({ name: "Wikipedia", url: selectedCandidate.wiki_url.trim() });
        }
      }
      setEditRelatedWebsites(initialSites);
      setNewWebsiteName("");
      setNewWebsiteUrl("");
      setEditHeroImageUrl(selectedCandidate.hero_image_url || "");
      setEditDurationHours(
        selectedCandidate.recommended_duration_hours !== null &&
          selectedCandidate.recommended_duration_hours !== undefined
          ? String(selectedCandidate.recommended_duration_hours)
          : "",
      );
      setEditDurationDays(
        selectedCandidate.recommended_visit_days !== null &&
          selectedCandidate.recommended_visit_days !== undefined &&
          selectedCandidate.recommended_visit_days >= 1
          ? String(selectedCandidate.recommended_visit_days)
          : "1",
      );
      setEditDurationNotes(selectedCandidate.estimated_visit_time_notes || "");
      setEditUpdateCoordinates(Boolean(selectedCandidate.update_coordinates));
    }
  }, [selectedCandidate?.id, approvedTags]);

  // Load approved taxonomy tags from user's configured Tags Library
  useEffect(() => {
    apiFetch<any[]>("/api/pois/tags")
      .catch(() => apiFetch<any[]>("/api/tags"))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const sorted = [...data].sort((a, b) => a.name.localeCompare(b.name));
          setApprovedTags(sorted);
        } else {
          setApprovedTags([
            { name: "Sightseeing", slug: "sightseeing" },
            { name: "Landmark", slug: "landmark" },
            { name: "Museum", slug: "museum" },
            { name: "Historic", slug: "historic" },
            { name: "Nature", slug: "nature" },
            { name: "Park", slug: "park" },
            { name: "Trail", slug: "trail" },
            { name: "Scenic Overlook", slug: "scenic_overlook" },
            { name: "Architecture", slug: "architecture" },
            { name: "Beach", slug: "beach" },
          ]);
        }
      })
      .catch(() => {
        setApprovedTags([
          { name: "Sightseeing", slug: "sightseeing" },
          { name: "Landmark", slug: "landmark" },
          { name: "Museum", slug: "museum" },
          { name: "Historic", slug: "historic" },
          { name: "Nature", slug: "nature" },
          { name: "Park", slug: "park" },
          { name: "Trail", slug: "trail" },
          { name: "Scenic Overlook", slug: "scenic_overlook" },
          { name: "Architecture", slug: "architecture" },
          { name: "Beach", slug: "beach" },
        ]);
      });
  }, []);

  const loadData = async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const res = await ingestApi.getJobCandidates(jobId, "phase_2_enriched");
      const active = (res.candidates || []).filter((c) => {
        const disp = c.user_disposition || c.recommended_disposition;
        return disp !== "ignore" && disp !== "exclude";
      });
      const normalized = active.map((c) => ({
        ...c,
        tags: normalizeToApprovedTags(c.tags || [], approvedTags),
      }));
      setCandidates(normalized);
      if (normalized.length > 0) {
        setSelectedCandidateId(normalized[0].id);
      }
    } catch (err: any) {
      showToast(err?.message || "Failed to load enriched candidates", "error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !jobId) return;
    loadData();
  }, [isOpen, jobId]);

  // Keep candidates normalized whenever approvedTags becomes available
  useEffect(() => {
    if (approvedTags.length > 0 && candidates.length > 0) {
      setCandidates((prev) =>
        prev.map((c) => ({
          ...c,
          tags: normalizeToApprovedTags(c.tags || [], approvedTags),
        })),
      );
    }
  }, [approvedTags]);

  const handleToggleSkip = async (cand: CandidateItem) => {
    const nextSkipped = !cand.is_skipped;
    setCandidates((prev) =>
      prev.map((c) => (c.id === cand.id ? { ...c, is_skipped: nextSkipped } : c)),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, cand.id, {
          is_skipped: nextSkipped,
        });
        showToast(
          nextSkipped ? `Skipped '${cand.poi_name}'` : `Included '${cand.poi_name}'`,
          "info",
        );
      } catch (err: any) {
        showToast(`Failed to toggle skip: ${err.message}`, "error");
      }
    }
  };

  const handleToggleTag = (tagName: string) => {
    // Only allow tags that exist in the user's Tags Library
    const matchedTag = approvedTags.find(
      (t) => t.name.toLowerCase() === tagName.toLowerCase(),
    );
    if (!matchedTag) return;

    setEditTags((prev) => {
      const exists = prev.some((t) => t.toLowerCase() === matchedTag.name.toLowerCase());
      if (exists) {
        return prev.filter((t) => t.toLowerCase() !== matchedTag.name.toLowerCase());
      } else {
        return [...prev, matchedTag.name];
      }
    });
  };

  const handleBulkAddTag = async (tagName: string) => {
    if (!jobId || selectedCandidateIds.length === 0) return;
    setIsBulkUpdating(true);
    let affectedCount = 0;
    try {
      const updatedCandidates = await Promise.all(
        selectedCandidateIds.map(async (cid) => {
          const cand = candidates.find((c) => c.id === cid);
          if (!cand) return null;
          const currentTags = cand.tags || [];
          if (!currentTags.some((t) => t.toLowerCase() === tagName.toLowerCase())) {
            const nextTags = [...currentTags, tagName];
            affectedCount++;
            await ingestApi.updateCandidate(jobId, cid, { tags: nextTags });
            return { id: cid, tags: nextTags };
          }
          return null;
        }),
      );

      const updatesMap = new Map<string, string[]>();
      updatedCandidates.forEach((u) => {
        if (u) updatesMap.set(u.id, u.tags);
      });

      setCandidates((prev) =>
        prev.map((c) => (updatesMap.has(c.id) ? { ...c, tags: updatesMap.get(c.id)! } : c)),
      );

      // If the currently inspected candidate was updated, sync its edit state
      if (selectedCandidateId && updatesMap.has(selectedCandidateId)) {
        setEditTags(updatesMap.get(selectedCandidateId)!);
      }

      if (affectedCount > 0) {
        showToast(`Added tag "${tagName}" to ${affectedCount} selected POI(s)`, "success");
      } else {
        showToast(`Tag "${tagName}" is already present on all selected POIs`, "info");
      }
    } catch (err: any) {
      showToast(`Failed to bulk add tag: ${err.message}`, "error");
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleBulkRemoveTag = async (tagName: string) => {
    if (!jobId || selectedCandidateIds.length === 0) return;
    setIsBulkUpdating(true);
    let affectedCount = 0;
    try {
      const updatedCandidates = await Promise.all(
        selectedCandidateIds.map(async (cid) => {
          const cand = candidates.find((c) => c.id === cid);
          if (!cand) return null;
          const currentTags = cand.tags || [];
          if (currentTags.some((t) => t.toLowerCase() === tagName.toLowerCase())) {
            const nextTags = currentTags.filter((t) => t.toLowerCase() !== tagName.toLowerCase());
            affectedCount++;
            await ingestApi.updateCandidate(jobId, cid, { tags: nextTags });
            return { id: cid, tags: nextTags };
          }
          return null;
        }),
      );

      const updatesMap = new Map<string, string[]>();
      updatedCandidates.forEach((u) => {
        if (u) updatesMap.set(u.id, u.tags);
      });

      setCandidates((prev) =>
        prev.map((c) => (updatesMap.has(c.id) ? { ...c, tags: updatesMap.get(c.id)! } : c)),
      );

      // If the currently inspected candidate was updated, sync its edit state
      if (selectedCandidateId && updatesMap.has(selectedCandidateId)) {
        setEditTags(updatesMap.get(selectedCandidateId)!);
      }

      if (affectedCount > 0) {
        showToast(`Removed tag "${tagName}" from ${affectedCount} selected POI(s)`, "success");
      } else {
        showToast(`Tag "${tagName}" was not present on any selected POI`, "info");
      }
    } catch (err: any) {
      showToast(`Failed to bulk remove tag: ${err.message}`, "error");
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const handleSaveCandidateChanges = async () => {
    if (!selectedCandidate || !jobId) return;

    setIsSavingCandidate(true);
    try {
      const officialSite = editRelatedWebsites.find((s) => s.name.toLowerCase().includes("official"));
      const wikiSite = editRelatedWebsites.find(
        (s) => s.name.toLowerCase().includes("wikipedia") || s.url.toLowerCase().includes("wikipedia.org")
      );
      const derivedOfficialUrl = officialSite ? officialSite.url : null;
      const derivedWikiUrl = wikiSite ? wikiSite.url : null;

      const updated = await ingestApi.updateCandidate(jobId, selectedCandidate.id, {
        poi_name: editPoiName,
        description: editDescription,
        reason_to_visit: editReasonToVisit,
        tags: editTags,
        street_address: editStreetAddress,
        city: editCity,
        official_url: derivedOfficialUrl,
        wiki_url: derivedWikiUrl,
        related_websites: editRelatedWebsites,
        hero_image_url: editHeroImageUrl.trim() || null,
        recommended_duration_hours: editDurationHours ? parseFloat(editDurationHours) : null,
        recommended_visit_days: editDurationDays ? parseInt(editDurationDays, 10) : null,
        estimated_visit_time_notes: editDurationNotes.trim() || null,
        update_coordinates: editUpdateCoordinates,
      });

      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidate.id ? { ...c, ...updated, tags: editTags } : c)),
      );
      showToast(`Saved changes for '${editPoiName}'`, "success");
    } catch (err: any) {
      showToast(`Failed to save changes: ${err.message}`, "error");
    } finally {
      setIsSavingCandidate(false);
    }
  };

  const handleTriggerAIEnrich = async () => {
    if (!jobId) return;
    setIsEnriching(true);
    try {
      await ingestApi.enrichPhase2(jobId);
      setIsEnrichProgressOpen(true);
    } catch (err: any) {
      showToast(`AI enrichment failed: ${err.message}`, "error");
    } finally {
      setIsEnriching(false);
    }
  };

  const handleEnrichmentModalComplete = async () => {
    setIsEnrichProgressOpen(false);
    await loadData();
    showToast("Completed parallel AI & web enrichment!", "success");
  };

  const handleBackToPhase1 = async () => {
    if (!jobId) return;
    setIsReverting(true);
    try {
      await ingestApi.backToPhase1(jobId);
      showToast("Reverted to Phase 1: Validation & Triage", "info");
      if (onBackToPhase1) {
        onBackToPhase1(jobId);
      } else {
        onClose();
      }
    } catch (err: any) {
      showToast(`Failed to return to Phase 1: ${err.message}`, "error");
    } finally {
      setIsReverting(false);
    }
  };

  const handleSaveToDB = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const res = await ingestApi.commitPhase2(jobId);
      showToast(
        `Saved ${res.committed_count} POIs to your map! (${res.created_pois.length} created, ${res.merged_pois.length} merged)`,
        "success",
      );
      onCommitComplete();
    } catch (err: any) {
      showToast(`Database commit failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
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
        if (
          !window.confirm(
            "Permanently discard this import session? All staged progress will be wiped.",
          )
        ) {
          return;
        }
      } catch {
        // Fallback for environments where window.confirm is unavailable
      }
    }

    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase2(jobId);
      showToast("Phase 2 review cancelled; staged records purged.", "info");
      onClose();
    } catch (err: any) {
      showToast(`Cancellation failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filter and sort candidates
  const filteredCandidates = useMemo(() => {
    let result = candidates;
    if (filterText.trim()) {
      const q = filterText.toLowerCase().trim();
      result = result.filter((c) => {
        const name = (c.poi_name || "").toLowerCase();
        const city = (c.city || "").toLowerCase();
        const state = (c.state_province || "").toLowerCase();
        const country = (c.country || "").toLowerCase();
        const desc = (c.description || "").toLowerCase();
        const reason = (c.reason_to_visit || "").toLowerCase();
        const tags = (c.tags || []).join(" ").toLowerCase();
        return (
          name.includes(q) ||
          city.includes(q) ||
          state.includes(q) ||
          country.includes(q) ||
          desc.includes(q) ||
          reason.includes(q) ||
          tags.includes(q)
        );
      });
    }

    const sorted = [...result];
    sorted.sort((a, b) => {
      // 1. Column click overrides default priority sort
      if (sortField) {
        let cmp = 0;
        if (sortField === "poi_name") {
          cmp = (a.poi_name || "").localeCompare(b.poi_name || "");
        } else if (sortField === "country") {
          cmp = (a.country || "").localeCompare(b.country || "");
        } else if (sortField === "state_province") {
          cmp = (a.state_province || "").localeCompare(b.state_province || "");
        } else if (sortField === "city") {
          cmp = (a.city || "").localeCompare(b.city || "");
        } else if (sortField === "status") {
          cmp = (a.is_skipped ? 1 : 0) - (b.is_skipped ? 1 : 0);
        } else if (sortField === "disposition") {
          const da = a.user_disposition || a.recommended_disposition || "";
          const db = b.user_disposition || b.recommended_disposition || "";
          cmp = da.localeCompare(db);
        } else if (sortField === "data_status") {
          const aStat = getCandidateDataStatus(a);
          const bStat = getCandidateDataStatus(b);
          const diff = aStat.missingFields.length - bStat.missingFields.length;
          cmp = diff !== 0 ? diff : (a.poi_name || "").localeCompare(b.poi_name || "");
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

    return sorted;
  }, [candidates, filterText, sortPriority, sortField, sortDirection]);

  const activeCount = candidates.filter((c) => !c.is_skipped).length;
  const skippedCount = candidates.filter((c) => c.is_skipped).length;

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
      <div style={{ fontWeight: 700, fontSize: "13px", color: "#0f172a", marginBottom: "2px" }}>
        {cand.poi_name}
      </div>
      {cand.street_address ? (
        <div
          style={{
            fontSize: "11px",
            color: "#64748b",
            fontWeight: 400,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            maxWidth: "200px",
          }}
        >
          {cand.street_address}
        </div>
      ) : cand.city || cand.state_province || cand.country ? (
        <div
          style={{
            fontSize: "11px",
            color: "#94a3b8",
            fontWeight: 400,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            maxWidth: "200px",
          }}
        >
          {[cand.city, cand.state_province, cand.country].filter(Boolean).join(", ")}
        </div>
      ) : null}
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

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={handleSaveAndClose}
        title="Phase 2: AI Enrichment Review & Commit"
        maxWidth="min(1500px, 96vw)"
      >
        <div
          data-testid="phase2-review-modal"
          style={{
            display: "flex",
            flexDirection: "column",
            height: "78vh",
            minHeight: "560px",
            color: "#1e293b",
          }}
        >
          {isLoading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flex: 1,
                color: "#64748b",
                gap: "8px",
              }}
            >
              <Loader2 size={20} className="animate-spin" />
              <span>Loading enriched candidates...</span>
            </div>
          ) : (
            <>
              {/* Top banner */}
              <div
                style={{
                  padding: "12px 16px",
                  marginBottom: "12px",
                  backgroundColor: "#faf5ff",
                  border: "1px solid #e9d5ff",
                  borderRadius: "8px",
                  fontSize: "13px",
                  color: "#581c87",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}>
                  <Sparkles size={20} color="#9333ea" style={{ flexShrink: 0 }} />
                  <span>
                    Parallel AI workers discovered official websites, Wikipedia articles, uncropped
                    hero photos, visit durations, and approved tags. Review or adjust details in
                    the right panel before saving to your map.
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={handleTriggerAIEnrich}
                    disabled={isEnriching}
                    data-testid="ai-enrich-all-btn"
                    style={{
                      padding: "6px 12px",
                      fontSize: "12px",
                      fontWeight: 600,
                      backgroundColor: "#f3e8ff",
                      color: "#7e22ce",
                      border: "1px solid #d8b4fe",
                      borderRadius: "6px",
                      cursor: isEnriching ? "not-allowed" : "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    {isEnriching ? (
                      <>
                        <Loader2 size={13} className="animate-spin" />
                        <span>Enriching...</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw size={13} />
                        <span>AI Enrich All</span>
                      </>
                    )}
                  </button>
                  <div
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      padding: "6px 12px",
                      backgroundColor: "#e9d5ff",
                      borderRadius: "6px",
                      color: "#3b0764",
                    }}
                  >
                    {activeCount} Ready to Commit
                  </div>
                </div>
              </div>

              {/* Filter toolbar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  marginBottom: "12px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    flex: 1,
                    maxWidth: "480px",
                    position: "relative",
                  }}
                >
                  <Search
                    size={15}
                    color="#94a3b8"
                    style={{ position: "absolute", left: "10px" }}
                  />
                  <input
                    type="text"
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    placeholder="Filter by POI name, locality, or tags..."
                    data-testid="phase2-search-input"
                    style={{
                      width: "100%",
                      padding: "7px 12px 7px 32px",
                      fontSize: "13px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "6px",
                      outline: "none",
                      backgroundColor: "#ffffff",
                      color: "#0f172a",
                    }}
                  />
                  {filterText && (
                    <button
                      type="button"
                      onClick={() => setFilterText("")}
                      style={{
                        position: "absolute",
                        right: "8px",
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        color: "#94a3b8",
                      }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                  <div style={{ fontSize: "12px", color: "#64748b" }}>
                    Showing <strong>{filteredCandidates.length}</strong> of {candidates.length} candidates
                  </div>

                  {/* Sort Priority Dropdown */}
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <label
                      htmlFor="sort-priority-select-phase2"
                      style={{ fontSize: "12px", color: "#64748b", fontWeight: 600, whiteSpace: "nowrap" }}
                    >
                      Sort Priority:
                    </label>
                    <select
                      id="sort-priority-select-phase2"
                      data-testid="sort-priority-select"
                      aria-label="Sort Priority"
                      value={sortPriority}
                      onChange={(e) => {
                        setSortPriority(e.target.value as SortPriority);
                        setSortField(null);
                        setSortDirection("asc");
                      }}
                      style={{
                        padding: "4px 8px",
                        fontSize: "12px",
                        border: "1px solid #cbd5e1",
                        borderRadius: "6px",
                        backgroundColor: "#ffffff",
                        color: "#1e293b",
                        cursor: "pointer",
                        fontWeight: 600,
                        height: "32px",
                      }}
                    >
                      <option value="poi">POI</option>
                      <option value="location">Location</option>
                    </select>
                  </div>

                  {/* Export Phase 2 Candidates */}
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <select
                      value={exportFormat}
                      onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                      data-testid="export-format-select-phase2"
                      aria-label="Export format"
                      style={{
                        padding: "4px 8px",
                        borderRadius: "6px",
                        fontSize: "12px",
                        border: "1px solid #cbd5e1",
                        backgroundColor: "#ffffff",
                        color: "#334155",
                        cursor: "pointer",
                        height: "32px",
                      }}
                    >
                      <option value="csv">CSV</option>
                      <option value="json">JSON</option>
                      <option value="yaml">YAML</option>
                    </select>
                    <button
                      type="button"
                      onClick={handleExportSelected}
                      disabled={isExporting}
                      data-testid="export-selected-phase2-btn"
                      style={{
                        padding: "6px 12px",
                        fontSize: "12px",
                        fontWeight: 600,
                        border: "1px solid #cbd5e1",
                        borderRadius: "6px",
                        backgroundColor: "#ffffff",
                        color: "#334155",
                        cursor: isExporting ? "not-allowed" : "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        height: "32px",
                      }}
                    >
                      <Download size={13} />
                      <span>{isExporting ? "Exporting..." : `Export Selected (${selectedCandidateIds.length})`}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Bulk Actions Toolbar (Active when 1 or more candidates are checked) */}
              {selectedCandidateIds.length > 0 && (
                <div
                  data-testid="bulk-actions-toolbar"
                  style={{
                    padding: "8px 14px",
                    marginBottom: "12px",
                    backgroundColor: "#f5f3ff",
                    border: "1px solid #ddd6fe",
                    borderRadius: "6px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "12px",
                    color: "#5b21b6",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span style={{ fontWeight: 700 }}>
                      {selectedCandidateIds.length} POI(s) selected
                    </span>
                    <button
                      type="button"
                      data-testid="clear-selection-btn"
                      onClick={() => setSelectedCandidateIds([])}
                      style={{
                        border: "none",
                        background: "transparent",
                        color: "#7c3aed",
                        textDecoration: "underline",
                        cursor: "pointer",
                        fontSize: "12px",
                        padding: 0,
                      }}
                    >
                      Clear selection
                    </button>
                  </div>
                  <div style={{ fontSize: "11px", color: "#6d28d9" }}>
                    {selectedCandidateIds.length > 1
                      ? "Manage tags for all selected POIs in the right panel"
                      : "Check multiple POIs to batch add or remove tags"}
                  </div>
                </div>
              )}

              {/* Split view: Left Table (58%) + Right Interactive Panel (42%) */}
              <div
                style={{
                  display: "flex",
                  flex: 1,
                  gap: "16px",
                  overflow: "hidden",
                }}
              >
                {/* Left Candidates Table */}
                <div
                  style={{
                    flex: "1 1 58%",
                    overflowX: "auto",
                    overflowY: "auto",
                    border: "1px solid #e2e8f0",
                    borderRadius: "8px",
                    backgroundColor: "#ffffff",
                  }}
                >
                  <table
                    style={{
                      minWidth: "850px",
                      width: "100%",
                      textAlign: "left",
                      fontSize: "13px",
                      borderCollapse: "separate",
                      borderSpacing: 0,
                    }}
                    data-testid="enriched-candidates-table"
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
                            padding: "10px 12px",
                            fontWeight: 700,
                            width: "36px",
                            textAlign: "center",
                            borderBottom: "1px solid #e2e8f0",
                          }}
                        >
                          <input
                            type="checkbox"
                            data-testid="select-all-phase2-checkbox"
                            aria-label="Select All Candidates"
                            checked={
                              filteredCandidates.length > 0 &&
                              filteredCandidates.every((c) => selectedCandidateIds.includes(c.id))
                            }
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedCandidateIds(filteredCandidates.map((c) => c.id));
                              } else {
                                setSelectedCandidateIds([]);
                              }
                            }}
                            style={{ cursor: "pointer", width: "15px", height: "15px" }}
                            title="Select All"
                          />
                        </th>
                        <th
                          onClick={() => handleSort("status")}
                          style={{
                            padding: "10px 12px",
                            fontWeight: 600,
                            width: "90px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                            userSelect: "none",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center" }}>
                            Status {renderSortIcon("status")}
                          </div>
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
                          style={{
                            padding: "10px 12px",
                            fontWeight: 700,
                            width: "60px",
                            textAlign: "center",
                            borderBottom: "1px solid #e2e8f0",
                          }}
                        >
                          Photo
                        </th>
                        <th
                          onClick={() => handleSort("disposition")}
                          style={{
                            padding: "10px 12px",
                            fontWeight: 600,
                            minWidth: "110px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                            userSelect: "none",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center" }}>
                            Disposition {renderSortIcon("disposition")}
                          </div>
                        </th>
                        <th
                          onClick={() => handleSort("data_status")}
                          style={{
                            padding: "10px 12px",
                            fontWeight: 600,
                            minWidth: "125px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                            userSelect: "none",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center" }}>
                            Data Status {renderSortIcon("data_status")}
                          </div>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCandidates.length === 0 ? (
                        <tr>
                          <td
                            colSpan={9}
                            style={{
                              padding: "32px",
                              textAlign: "center",
                              color: "#94a3b8",
                              fontStyle: "italic",
                            }}
                          >
                            No candidate records match your filter criteria.
                          </td>
                        </tr>
                      ) : (
                        filteredCandidates.map((cand) => {
                          const isSelected = cand.id === selectedCandidateId;
                          const isChecked = selectedCandidateIds.includes(cand.id);
                          const disp =
                            cand.user_disposition || cand.recommended_disposition;

                          let dispBadge = {
                            text: "New POI",
                            bg: "#dcfce7",
                            color: "#166534",
                            border: "#bbf7d0",
                          };
                          if (disp === "sublocation") {
                            dispBadge = {
                              text: "Sublocation",
                              bg: "#e0f2fe",
                              color: "#0369a1",
                              border: "#bae6fd",
                            };
                          } else if (disp === "update_existing") {
                            dispBadge = {
                              text: cand.matched_existing_poi_id
                                ? "Update Existing POI"
                                : "New POI",
                              bg: cand.matched_existing_poi_id
                                ? "#fef3c7"
                                : "#ecfdf5",
                              color: cand.matched_existing_poi_id
                                ? "#b45309"
                                : "#065f46",
                              border: cand.matched_existing_poi_id
                                ? "#fde68a"
                                : "#a7f3d0",
                            };
                          }

                          const dataStatus = getCandidateDataStatus(cand);
                          const isMissingData = !dataStatus.isComplete;

                          return (
                            <tr
                              key={cand.id}
                              onClick={() => setSelectedCandidateId(cand.id)}
                              data-testid={`enriched-row-${cand.id}`}
                              style={{
                                backgroundColor: isSelected
                                  ? "#eff6ff"
                                  : isChecked
                                  ? "#f5f3ff"
                                  : cand.is_skipped
                                  ? "#f8fafc"
                                  : isMissingData
                                  ? "#fffbeb"
                                  : "transparent",
                                opacity: cand.is_skipped ? 0.5 : 1,
                                cursor: "pointer",
                                transition: "background-color 150ms",
                                borderBottom: isMissingData && !isSelected && !isChecked
                                  ? "1px solid #fef3c7"
                                  : "1px solid #f1f5f9",
                                borderLeft: isSelected
                                  ? "3px solid #2563eb"
                                  : isChecked
                                  ? "3px solid #8b5cf6"
                                  : isMissingData
                                  ? "3px solid #f59e0b"
                                  : "3px solid transparent",
                              }}
                            >
                              {/* Row Select Checkbox */}
                              <td
                                style={{ padding: "10px 12px", textAlign: "center" }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <input
                                  type="checkbox"
                                  data-testid={`candidate-checkbox-${cand.id}`}
                                  aria-label={`Select ${cand.poi_name}`}
                                  checked={isChecked}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    if (e.target.checked) {
                                      setSelectedCandidateIds((prev) => [...prev, cand.id]);
                                    } else {
                                      setSelectedCandidateIds((prev) =>
                                        prev.filter((id) => id !== cand.id),
                                      );
                                    }
                                  }}
                                  style={{ cursor: "pointer", width: "15px", height: "15px" }}
                                />
                              </td>

                              {/* Skip / Include Status button */}
                              <td
                                style={{ padding: "10px 12px" }}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <button
                                  type="button"
                                  onClick={() => handleToggleSkip(cand)}
                                  data-testid={`skip-toggle-${cand.id}`}
                                  title={cand.is_skipped ? "Click to Include" : "Click to Skip"}
                                  style={{
                                    padding: "4px 8px",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    borderRadius: "6px",
                                    border: cand.is_skipped
                                      ? "1px solid #cbd5e1"
                                      : "1px solid #86efac",
                                    backgroundColor: cand.is_skipped ? "#ffffff" : "#f0fdf4",
                                    color: cand.is_skipped ? "#64748b" : "#166534",
                                    cursor: "pointer",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {cand.is_skipped ? (
                                    <>
                                      <EyeOff size={13} color="#94a3b8" />
                                      <span>Skip</span>
                                    </>
                                  ) : (
                                    <>
                                      <CheckCircle size={13} color="#16a34a" />
                                      <span>Include</span>
                                    </>
                                  )}
                                </button>
                              </td>

                              {/* Dynamic Columns based on sortPriority */}
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

                              {/* Hero Photo Thumbnail */}
                              <td style={{ padding: "10px 12px", textAlign: "center" }}>
                                {cand.hero_image_url ? (
                                  <img
                                    src={cand.hero_image_url}
                                    alt={cand.poi_name}
                                    style={{
                                      width: "36px",
                                      height: "36px",
                                      objectFit: "cover",
                                      borderRadius: "4px",
                                      border: "1px solid #cbd5e1",
                                      display: "inline-block",
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
                                      border: "1px dashed #cbd5e1",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                    }}
                                  >
                                    <ImageIcon size={14} color="#94a3b8" />
                                  </div>
                                )}
                              </td>

                              {/* Disposition Badge */}
                              <td style={{ padding: "10px 12px" }}>
                                <span
                                  style={{
                                    display: "inline-block",
                                    padding: "2px 8px",
                                    borderRadius: "12px",
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    backgroundColor: dispBadge.bg,
                                    color: dispBadge.color,
                                    border: `1px solid ${dispBadge.border}`,
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {dispBadge.text}
                                </span>
                              </td>

                              {/* Data Status (Completeness) Badge */}
                              <td style={{ padding: "10px 12px" }}>
                                {dataStatus.isComplete ? (
                                  <span
                                    data-testid={`data-status-${cand.id}`}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "4px",
                                      padding: "2px 8px",
                                      borderRadius: "12px",
                                      fontSize: "11px",
                                      fontWeight: 600,
                                      backgroundColor: "#f0fdf4",
                                      color: "#166534",
                                      border: "1px solid #86efac",
                                      whiteSpace: "nowrap",
                                    }}
                                    title="All fields populated"
                                  >
                                    <CheckCircle size={12} color="#16a34a" />
                                    <span>Complete</span>
                                  </span>
                                ) : (
                                  <span
                                    data-testid={`data-status-${cand.id}`}
                                    style={{
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "4px",
                                      padding: "2px 8px",
                                      borderRadius: "12px",
                                      fontSize: "11px",
                                      fontWeight: 600,
                                      backgroundColor: "#fef3c7",
                                      color: "#92400e",
                                      border: "1px solid #fde68a",
                                      whiteSpace: "nowrap",
                                    }}
                                    title={`Missing: ${dataStatus.missingFields.join(", ")}`}
                                  >
                                    <AlertCircle size={12} color="#d97706" />
                                    <span>Incomplete ({dataStatus.missingFields.length})</span>
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

                {/* Right Interactive Detail & Editor Panel */}
                <div
                  data-testid="phase2-map-panel"
                  style={{
                    flex: "0 0 42%",
                    minWidth: "380px",
                    maxWidth: "500px",
                    border: "1px solid #e2e8f0",
                    borderRadius: "8px",
                    backgroundColor: "#f8fafc",
                    display: "flex",
                    flexDirection: "column",
                    height: "100%",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "14px 16px 10px 16px",
                      borderBottom: "1px solid #e2e8f0",
                      backgroundColor: "#f8fafc",
                      flexShrink: 0,
                    }}
                  >
                    <h4
                      style={{
                        margin: 0,
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "#1e293b",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      {selectedCandidateIds.length > 1 ? (
                        <>
                          <Layers size={16} color="#7c3aed" /> Bulk Tag Management
                        </>
                      ) : (
                        <>
                          <MapPin size={16} color="#7c3aed" /> Candidate Details & AI Review
                        </>
                      )}
                    </h4>
                    {selectedCandidateIds.length <= 1 && selectedCandidate && (
                      <span
                        style={{
                          fontSize: "11px",
                          color: "#64748b",
                          fontWeight: 500,
                        }}
                      >
                        Row #{selectedCandidate.row_index + 1}
                      </span>
                    )}
                  </div>

                  {/* Scrollable Container for Details */}
                  <div
                    style={{
                      flex: 1,
                      overflowY: "auto",
                      padding: "14px 16px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                    }}
                  >
                  {selectedCandidateIds.length > 1 ? (
                    <div
                      data-testid="bulk-tag-panel"
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "16px",
                        fontSize: "12px",
                      }}
                    >
                      <div
                        style={{
                          padding: "10px 12px",
                          backgroundColor: "#ede9fe",
                          border: "1px solid #ddd6fe",
                          borderRadius: "6px",
                          color: "#5b21b6",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <Layers size={16} />
                          <strong>{selectedCandidateIds.length} POIs Selected</strong>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedCandidateIds([])}
                          data-testid="bulk-panel-clear-btn"
                          style={{
                            border: "none",
                            background: "transparent",
                            color: "#6d28d9",
                            textDecoration: "underline",
                            cursor: "pointer",
                            fontSize: "11px",
                            fontWeight: 600,
                          }}
                        >
                          Clear Selection
                        </button>
                      </div>

                      {/* Add Tag to All Selected */}
                      <div
                        style={{
                          backgroundColor: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "8px",
                          padding: "12px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 700,
                            color: "#1e293b",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Plus size={14} color="#16a34a" /> Add Tag to All Selected
                        </div>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>
                          Click any approved tag below to apply it to all {selectedCandidateIds.length} selected POIs (if already present, no change).
                        </div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          {approvedTags.map((tag) => (
                            <button
                              key={tag.slug || tag.name}
                              type="button"
                              disabled={isBulkUpdating}
                              onClick={() => handleBulkAddTag(tag.name)}
                              data-testid={`bulk-add-tag-${tag.slug || tag.name}`}
                              style={{
                                padding: "4px 9px",
                                borderRadius: "14px",
                                fontSize: "11px",
                                fontWeight: 600,
                                cursor: isBulkUpdating ? "not-allowed" : "pointer",
                                border: "1px solid #cbd5e1",
                                backgroundColor: "#f8fafc",
                                color: "#334155",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                            >
                              <Plus size={11} color="#16a34a" />
                              <span>{tag.name}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Remove Tag from Selected */}
                      <div
                        style={{
                          backgroundColor: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "8px",
                          padding: "12px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 700,
                            color: "#1e293b",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Trash2 size={14} color="#dc2626" /> Remove Tag from Selected
                        </div>
                        <div style={{ fontSize: "11px", color: "#64748b" }}>
                          Tags currently present on at least one selected POI. Click to remove from all selected.
                        </div>
                        {distinctTagsInSelection.length === 0 ? (
                          <div style={{ fontSize: "11px", color: "#94a3b8", fontStyle: "italic" }}>
                            None of the selected POIs currently have any tags assigned.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                            {distinctTagsInSelection.map((tagName) => (
                              <button
                                key={tagName}
                                type="button"
                                disabled={isBulkUpdating}
                                onClick={() => handleBulkRemoveTag(tagName)}
                                data-testid={`bulk-remove-tag-${tagName.toLowerCase().replace(/\s+/g, "_")}`}
                                style={{
                                  padding: "4px 9px",
                                  borderRadius: "14px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  cursor: isBulkUpdating ? "not-allowed" : "pointer",
                                  border: "1px solid #fecaca",
                                  backgroundColor: "#fff5f5",
                                  color: "#b91c1c",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <X size={11} color="#dc2626" />
                                <span>{tagName}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : selectedCandidate ? (
                    <div
                      data-testid="poi-edit-drawer"
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "12px",
                        fontSize: "12px",
                      }}
                    >
                      {/* POI Name input */}
                      <div>
                        <label
                          style={{
                            display: "block",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          POI Name
                        </label>
                        <input
                          type="text"
                          value={editPoiName}
                          onChange={(e) => setEditPoiName(e.target.value)}
                          data-testid="edit-poi-name-input"
                          style={{
                            width: "100%",
                            padding: "7px 10px",
                            fontSize: "13px",
                            fontWeight: 600,
                            border: "1px solid #cbd5e1",
                            borderRadius: "6px",
                            backgroundColor: "#ffffff",
                            color: "#0f172a",
                          }}
                        />
                      </div>

                      {/* Coordinates & Location info */}
                      <div
                        style={{
                          padding: "8px 10px",
                          backgroundColor: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: "6px",
                          fontSize: "11px",
                          color: "#64748b",
                          display: "flex",
                          flexDirection: "column",
                          gap: "2px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Compass size={13} color="#64748b" />
                          <span style={{ fontWeight: 600, color: "#334155" }}>
                            Coordinates:{" "}
                          </span>
                          <span>
                            {selectedCandidate.latitude != null &&
                            selectedCandidate.longitude != null
                              ? `${Number(selectedCandidate.latitude).toFixed(5)}, ${Number(
                                  selectedCandidate.longitude,
                                ).toFixed(5)}`
                              : "None"}
                          </span>
                        </div>
                        {(selectedCandidate.street_address || selectedCandidate.city) && (
                          <div>
                            <strong>Address: </strong>
                            {[
                              selectedCandidate.street_address,
                              selectedCandidate.city,
                              selectedCandidate.state_province,
                              selectedCandidate.country,
                            ]
                              .filter(Boolean)
                              .join(", ")}
                          </div>
                        )}
                      </div>

                      {/* Hero Image URL & Uncropped Preview */}
                      <div>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <ImageIcon size={13} color="#7c3aed" /> Hero Image URL
                          </span>
                          <span style={{ fontSize: "10px", color: "#64748b" }}>
                            Uncropped preview
                          </span>
                        </label>
                        <input
                          type="url"
                          value={editHeroImageUrl}
                          onChange={(e) => setEditHeroImageUrl(e.target.value)}
                          data-testid="edit-poi-hero-image-input"
                          placeholder="https://upload.wikimedia.org/.../image.jpg"
                          style={{
                            width: "100%",
                            padding: "7px 10px",
                            fontSize: "12px",
                            border: `1px solid ${!editHeroImageUrl.trim() ? "#fcd34d" : "#cbd5e1"}`,
                            borderRadius: "6px",
                            backgroundColor: !editHeroImageUrl.trim() ? "#fffbeb" : "#ffffff",
                            color: "#0f172a",
                          }}
                        />
                        {editHeroImageUrl && (
                          <div
                            style={{
                              marginTop: "8px",
                              padding: "6px",
                              backgroundColor: "#0f172a",
                              borderRadius: "6px",
                              border: "1px solid #cbd5e1",
                              textAlign: "center",
                            }}
                          >
                            <img
                              src={editHeroImageUrl}
                              alt={editPoiName}
                              data-testid="hero-image-preview"
                              style={{
                                maxHeight: "180px",
                                maxWidth: "100%",
                                width: "auto",
                                height: "auto",
                                objectFit: "contain",
                                borderRadius: "4px",
                                display: "inline-block",
                              }}
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                          </div>
                        )}
                      </div>

                      {/* Related Websites & Research */}
                      <div
                        data-testid="related-websites-section"
                        style={{
                          padding: "10px",
                          borderRadius: "8px",
                          background: "#f8fafc",
                          border: "1px solid #e2e8f0",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: "12px", fontWeight: 700, color: "#334155", display: "flex", alignItems: "center", gap: "6px" }}>
                            <Globe size={13} style={{ color: "#2563eb" }} />
                            Related Websites & Research ({editRelatedWebsites.length})
                          </span>
                        </div>

                        {editRelatedWebsites.length === 0 ? (
                          <div style={{ fontSize: "11px", color: "#94a3b8", fontStyle: "italic" }}>
                            No related websites identified yet. Add custom links below.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                            {editRelatedWebsites.map((site, idx) => (
                              <div
                                key={`${site.url}-${idx}`}
                                data-testid={`related-website-row-${idx}`}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  padding: "6px 10px",
                                  borderRadius: "6px",
                                  background: "#ffffff",
                                  border: "1px solid #e2e8f0",
                                  fontSize: "12px",
                                }}
                              >
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden", flex: 1, minWidth: 0 }}>
                                  <span style={{ fontWeight: 600, color: "#1e293b", minWidth: "90px" }}>{site.name}:</span>
                                  <a
                                    href={site.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      color: "#2563eb",
                                      textDecoration: "none",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "3px",
                                    }}
                                    title={site.url}
                                  >
                                    {site.url} <ExternalLink size={11} />
                                  </a>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditRelatedWebsites(editRelatedWebsites.filter((_, i) => i !== idx));
                                  }}
                                  style={{
                                    border: "none",
                                    background: "transparent",
                                    color: "#94a3b8",
                                    cursor: "pointer",
                                    padding: "2px",
                                  }}
                                  title="Remove website link"
                                  data-testid={`remove-website-button-${idx}`}
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}

                        <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                          <input
                            type="text"
                            placeholder="Site Name (optional - auto-inferred)"
                            value={newWebsiteName}
                            onChange={(e) => setNewWebsiteName(e.target.value)}
                            style={{
                              flex: "0 0 140px",
                              padding: "6px 8px",
                              fontSize: "11px",
                              borderRadius: "6px",
                              border: "1px solid #cbd5e1",
                            }}
                          />
                          <input
                            type="url"
                            placeholder="https://..."
                            value={newWebsiteUrl}
                            onChange={(e) => setNewWebsiteUrl(e.target.value)}
                            style={{
                              flex: 1,
                              padding: "6px 8px",
                              fontSize: "11px",
                              borderRadius: "6px",
                              border: "1px solid #cbd5e1",
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => {
                              const trimmedUrl = newWebsiteUrl.trim();
                              if (trimmedUrl) {
                                const name = newWebsiteName.trim() || inferWebsiteName(trimmedUrl);
                                setEditRelatedWebsites([...editRelatedWebsites, { name, url: trimmedUrl }]);
                                setNewWebsiteName("");
                                setNewWebsiteUrl("");
                              }
                            }}
                            style={{
                              padding: "6px 12px",
                              fontSize: "11px",
                              fontWeight: 600,
                              borderRadius: "6px",
                              background: "#2563eb",
                              color: "#ffffff",
                              border: "none",
                              cursor: "pointer",
                              whiteSpace: "nowrap",
                            }}
                          >
                            + Add Link
                          </button>
                        </div>
                      </div>

                      {/* Recommended Duration & Itinerary Days */}
                      <div style={{ display: "flex", gap: "8px" }}>
                        <div style={{ flex: 1 }}>
                          <label
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                              fontSize: "11px",
                              fontWeight: 700,
                              color: "#475569",
                              marginBottom: "4px",
                            }}
                          >
                            <Clock size={12} color="#0284c7" /> Recommended Duration (hours)
                          </label>
                          <input
                            type="number"
                            step="0.5"
                            min="0.1"
                            value={editDurationHours}
                            onChange={(e) => setEditDurationHours(e.target.value)}
                            data-testid="edit-poi-duration-hours-input"
                            placeholder="2.5"
                            style={{
                              width: "100%",
                              padding: "7px 10px",
                              fontSize: "12px",
                              border: `1px solid ${!editDurationHours.trim() ? "#fcd34d" : "#cbd5e1"}`,
                              borderRadius: "6px",
                              backgroundColor: !editDurationHours.trim() ? "#fffbeb" : "#ffffff",
                              color: "#0f172a",
                            }}
                          />
                        </div>

                        <div style={{ flex: 1 }}>
                          <label
                            style={{
                              display: "block",
                              fontSize: "11px",
                              fontWeight: 700,
                              color: "#475569",
                              marginBottom: "4px",
                            }}
                          >
                            Itinerary Days
                          </label>
                          <input
                            type="number"
                            step="1"
                            min="0"
                            value={editDurationDays}
                            onChange={(e) => setEditDurationDays(e.target.value)}
                            data-testid="edit-poi-duration-days-input"
                            placeholder="0"
                            style={{
                              width: "100%",
                              padding: "7px 10px",
                              fontSize: "12px",
                              border: "1px solid #cbd5e1",
                              borderRadius: "6px",
                              backgroundColor: "#ffffff",
                              color: "#0f172a",
                            }}
                          />
                        </div>
                      </div>

                      {/* Duration Reasoning Notes */}
                      <div>
                        <label
                          style={{
                            display: "block",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          Duration Reasoning Notes
                        </label>
                        <textarea
                          rows={2}
                          value={editDurationNotes}
                          onChange={(e) => setEditDurationNotes(e.target.value)}
                          data-testid="edit-poi-duration-notes-input"
                          placeholder="Explanation of duration factors (queue time, guided tour, walking pace)..."
                          style={{
                            width: "100%",
                            padding: "7px 10px",
                            fontSize: "12px",
                            border: `1px solid ${!editDurationNotes.trim() ? "#fcd34d" : "#cbd5e1"}`,
                            borderRadius: "6px",
                            backgroundColor: !editDurationNotes.trim() ? "#fffbeb" : "#ffffff",
                            color: "#0f172a",
                            resize: "vertical",
                            lineHeight: "1.4",
                          }}
                        />
                      </div>

                      {/* AI Description */}
                      <div>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          <span>AI Synthesized Description</span>
                          <span style={{ fontSize: "10px", color: "#9333ea" }}>
                            ✦ Generated by AI
                          </span>
                        </label>
                        <textarea
                          rows={3}
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                          data-testid="edit-poi-description-input"
                          placeholder="Detailed synthesis of history, highlights, and atmosphere..."
                          style={{
                            width: "100%",
                            padding: "8px 10px",
                            fontSize: "12px",
                            border: `1px solid ${!editDescription.trim() ? "#fcd34d" : "#cbd5e1"}`,
                            borderRadius: "6px",
                            backgroundColor: !editDescription.trim() ? "#fffbeb" : "#ffffff",
                            color: "#0f172a",
                            resize: "vertical",
                            lineHeight: "1.4",
                          }}
                        />
                      </div>

                      {/* Reason to Visit */}
                      <div>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          <span>Personalized Reason to Visit</span>
                          <span style={{ fontSize: "10px", color: "#9333ea" }}>
                            ✦ Customized to You
                          </span>
                        </label>
                        <textarea
                          rows={3}
                          value={editReasonToVisit}
                          onChange={(e) => setEditReasonToVisit(e.target.value)}
                          data-testid="edit-poi-reason-input"
                          placeholder="Why this destination matters based on your travel interests..."
                          style={{
                            width: "100%",
                            padding: "8px 10px",
                            fontSize: "12px",
                            border: `1px solid ${!editReasonToVisit.trim() ? "#fcd34d" : "#cbd5e1"}`,
                            borderRadius: "6px",
                            backgroundColor: !editReasonToVisit.trim() ? "#fffbeb" : "#ffffff",
                            color: "#0f172a",
                            resize: "vertical",
                            lineHeight: "1.4",
                          }}
                        />
                      </div>

                      {/* Approved Taxonomy Tags (Strictly from User's Tags Library) */}
                      <div>
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            marginBottom: "4px",
                          }}
                        >
                          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <TagIcon size={12} color="#7c3aed" /> Tags Library
                          </span>
                          <span style={{ fontSize: "10px", color: "#64748b" }}>
                            Click to toggle
                          </span>
                        </label>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "5px",
                            marginBottom: "6px",
                            padding: editTags.length === 0 ? "8px" : undefined,
                            backgroundColor: editTags.length === 0 ? "#fffbeb" : undefined,
                            border: editTags.length === 0 ? "1px dashed #fcd34d" : undefined,
                            borderRadius: "6px",
                          }}
                        >
                          {approvedTags.map((tag) => {
                            const isSelected = editTags.some(
                              (t) => t.toLowerCase() === tag.name.toLowerCase(),
                            );
                            const tagSlug = tag.slug || tag.name.toLowerCase().replace(/\s+/g, "_");

                            return (
                              <button
                                key={tag.slug || tag.name}
                                type="button"
                                onClick={() => handleToggleTag(tag.name)}
                                data-testid={`approved-tag-${tagSlug}`}
                                style={{
                                  padding: "3px 8px",
                                  borderRadius: "14px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                  border: isSelected ? "1px solid #7c3aed" : "1px solid #cbd5e1",
                                  backgroundColor: isSelected ? "#f3e8ff" : "#ffffff",
                                  color: isSelected ? "#6b21a8" : "#475569",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                {isSelected && <Check size={11} color="#6b21a8" />}
                                <span>{tag.name}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* If update_existing matching an actual DB POI, show toggle for updating coordinates */}
                      {(selectedCandidate.user_disposition ||
                        selectedCandidate.recommended_disposition) === "update_existing" &&
                        Boolean(selectedCandidate.matched_existing_poi_id) && (
                        <div
                          style={{
                            padding: "10px 12px",
                            backgroundColor: "#fef3c7",
                            border: "1px solid #fde68a",
                            borderRadius: "6px",
                          }}
                        >
                          <label
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              fontSize: "12px",
                              fontWeight: 600,
                              color: "#92400e",
                              cursor: "pointer",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={editUpdateCoordinates}
                              onChange={(e) => setEditUpdateCoordinates(e.target.checked)}
                              data-testid="edit-update-coordinates-toggle"
                              style={{ cursor: "pointer", width: "15px", height: "15px" }}
                            />
                            <span>Update Existing POI Coordinates</span>
                          </label>
                          <div
                            style={{
                              fontSize: "11px",
                              color: "#b45309",
                              marginTop: "4px",
                              lineHeight: "1.3",
                            }}
                          >
                            If checked, the existing POI on your map will have its coordinates
                            overwritten with this CSV entry. If unchecked, its current coordinates
                            will be preserved.
                          </div>
                        </div>
                      )}



                      {/* POI Location Map */}
                      <div
                        data-testid="poi-location-map-container"
                        style={{
                          marginTop: "8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "6px",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#475569",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                            <MapPin size={13} color="#2563eb" /> Location Map
                          </span>
                          {selectedCandidate.latitude != null &&
                            selectedCandidate.longitude != null && (
                              <span style={{ fontSize: "10px", color: "#64748b" }}>
                                {Number(selectedCandidate.latitude).toFixed(5)},{" "}
                                {Number(selectedCandidate.longitude).toFixed(5)}
                              </span>
                            )}
                        </div>

                        {selectedCandidate.latitude != null &&
                        selectedCandidate.longitude != null &&
                        !isNaN(Number(selectedCandidate.latitude)) &&
                        !isNaN(Number(selectedCandidate.longitude)) ? (
                          <CandidateMiniMap
                            latitude={Number(selectedCandidate.latitude)}
                            longitude={Number(selectedCandidate.longitude)}
                            poiName={selectedCandidate.poi_name}
                          />
                        ) : (
                          <div
                            style={{
                              padding: "16px",
                              textAlign: "center",
                              backgroundColor: "#f8fafc",
                              border: "1px dashed #cbd5e1",
                              borderRadius: "8px",
                              color: "#94a3b8",
                              fontSize: "11px",
                              fontStyle: "italic",
                            }}
                          >
                            No coordinates available for this location.
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        textAlign: "center",
                        color: "#94a3b8",
                        fontSize: "12px",
                        fontStyle: "italic",
                        marginTop: "32px",
                      }}
                    >
                      Select a POI from the left table to inspect and edit its details.
                    </div>
                  )}

                  </div>

                  {/* Pinned Bottom Footer with Save Button (outside vertical scroll) */}
                  {selectedCandidateIds.length <= 1 && selectedCandidate && (
                    <div
                      style={{
                        flexShrink: 0,
                        padding: "12px 16px",
                        backgroundColor: "#ffffff",
                        borderTop: "1px solid #e2e8f0",
                      }}
                    >
                      <button
                        type="button"
                        onClick={handleSaveCandidateChanges}
                        disabled={isSavingCandidate}
                        data-testid="save-edit-button"
                        style={{
                          width: "100%",
                          padding: "8px 14px",
                          backgroundColor: "#2563eb",
                          color: "#ffffff",
                          fontSize: "12px",
                          fontWeight: 600,
                          borderRadius: "6px",
                          border: "none",
                          cursor: isSavingCandidate ? "not-allowed" : "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "6px",
                          boxShadow: "0 1px 2px rgba(37,99,235,0.2)",
                        }}
                      >
                        {isSavingCandidate ? (
                          <>
                            <Loader2 size={13} className="animate-spin" />
                            <span>Saving...</span>
                          </>
                        ) : (
                          <>
                            <Check size={14} />
                            <span>Save Candidate Changes</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  <div
                    style={{
                      flexShrink: 0,
                      padding: "8px 16px",
                      backgroundColor: "#f8fafc",
                      borderTop: "1px solid #e2e8f0",
                      fontSize: "11px",
                      color: "#64748b",
                      lineHeight: "1.4",
                    }}
                  >
                    Skipped items will be discarded and not added to your permanent map.
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingTop: "14px",
                  borderTop: "1px solid #e2e8f0",
                  marginTop: "12px",
                  flexWrap: "wrap",
                  gap: "10px",
                }}
              >
                {/* Left actions: Discard & Back to Phase 1 */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={handleDiscard}
                    disabled={isSubmitting}
                    data-testid="cancel-phase2-button"
                    style={{
                      padding: "9px 14px",
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

                  <button
                    type="button"
                    onClick={handleBackToPhase1}
                    disabled={isReverting || isSubmitting}
                    data-testid="back-to-phase1-button"
                    style={{
                      padding: "9px 14px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      backgroundColor: "#ffffff",
                      color: "#334155",
                      fontSize: "13px",
                      fontWeight: 600,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      cursor: isReverting || isSubmitting ? "not-allowed" : "pointer",
                    }}
                  >
                    {isReverting ? (
                      <Loader2 size={15} className="animate-spin" />
                    ) : (
                      <ArrowLeft size={15} color="#475569" />
                    )}
                    <span>Back to Phase 1</span>
                  </button>
                </div>

                {/* Tally Indicator */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    fontSize: "12px",
                    color: "#475569",
                    fontWeight: 500,
                  }}
                >
                  <span>
                    <strong style={{ color: "#16a34a" }}>{activeCount}</strong> to Add/Merge
                  </span>
                  <span>•</span>
                  <span>
                    <strong style={{ color: "#b91c1c" }}>{skippedCount}</strong> Skipped
                  </span>
                  <span>•</span>
                  <span>
                    <strong>{candidates.length}</strong> Total
                  </span>
                </div>

                {/* Right actions: Save & Close, Save to DB */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <button
                    type="button"
                    onClick={handleSaveAndClose}
                    disabled={isSubmitting}
                    data-testid="save-close-phase2-button"
                    style={{
                      padding: "9px 16px",
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      backgroundColor: "#ffffff",
                      color: "#334155",
                      fontSize: "13px",
                      fontWeight: 600,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      cursor: "pointer",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                    }}
                  >
                    <Save size={15} color="#64748b" />
                    <span>Save & Close</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveToDB}
                    disabled={isSubmitting || activeCount === 0}
                    data-testid="save-to-db-button"
                    style={{
                      padding: "9px 20px",
                      backgroundColor:
                        isSubmitting || activeCount === 0 ? "#86efac" : "#16a34a",
                      color: "#ffffff",
                      borderRadius: "8px",
                      fontSize: "13px",
                      fontWeight: 600,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "8px",
                      cursor: isSubmitting || activeCount === 0 ? "not-allowed" : "pointer",
                      boxShadow: "0 2px 4px rgba(22,163,74,0.25)",
                      border: "none",
                    }}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 size={15} className="animate-spin" />
                        <span>Saving to DB...</span>
                      </>
                    ) : (
                      <>
                        <Save size={15} />
                        <span>Save {activeCount} POI(s) to DB</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Background Parallel Enrichment Progress Modal */}
      <CSVEnrichmentProgressModal
        jobId={jobId}
        isOpen={isEnrichProgressOpen}
        onComplete={handleEnrichmentModalComplete}
        onCancel={() => setIsEnrichProgressOpen(false)}
      />
    </>
  );
};
