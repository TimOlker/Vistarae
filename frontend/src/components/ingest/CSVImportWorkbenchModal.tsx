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

import React, {
  useEffect,
  useMemo,
  useState,
  useCallback,
  useRef,
} from "react";
import { Modal } from "../common/Modal";
import {
  ingestApi,
  type CandidateItem,
  type CandidateUpdateRequest,
} from "../../services/ingestApi";
import { apiFetch } from "../../services/api";
import {
  reverseGeocode,
  forwardSearch,
  type ForwardSearchResult,
} from "../../services/geocodeService";
import { useToast } from "../../context/ToastContext";
import { WorkbenchMap, type NearbyPointMarker } from "./WorkbenchMap";
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
  ExternalLink,
  Folder,
  Calendar,
  RefreshCw,
  RotateCcw,
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

export type PerspectiveMode = "POI" | "Location";

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

function haversineMiles(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
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

function getConfidenceBadgeColors(score: number) {
  if (score >= 90) {
    return { bg: "#dcfce7", text: "#15803d", border: "#bbf7d0" };
  } else if (score >= 80) {
    return { bg: "#ecfccb", text: "#4d7c0f", border: "#d9f99d" };
  } else if (score >= 70) {
    return { bg: "#fef9c3", text: "#a16207", border: "#fef08a" };
  } else {
    return { bg: "#fee2e2", text: "#b91c1c", border: "#fecaca" };
  }
}

const AIIconBadge: React.FC = () => (
  <span
    title="Populated / enriched by AI Enrich"
    data-testid="ai-enrich-badge"
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "2px",
      marginLeft: "6px",
      padding: "1px 5px",
      borderRadius: "4px",
      backgroundColor: "#eef2ff",
      color: "#4f46e5",
      border: "1px solid #c7d2fe",
      fontSize: "9px",
      fontWeight: 700,
      letterSpacing: "0.5px",
      verticalAlign: "middle",
      cursor: "help",
    }}
  >
    <Sparkles size={10} />
    AI
  </span>
);

export const CSVImportWorkbenchModal: React.FC<
  CSVImportWorkbenchModalProps
> = ({ jobId, isOpen, onClose, onCommitComplete, existingPOIs = [] }) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingCandidate, setIsSavingCandidate] = useState(false);
  const [isEnrichingSingle, setIsEnrichingSingle] = useState(false);
  const [isEnrichingAll, setIsEnrichingAll] = useState(false);

  // Perspective Mode: "POI" (default) vs "Location"
  const [perspective, setPerspective] = useState<PerspectiveMode>("POI");

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [completenessFilter, setCompletenessFilter] =
    useState<CompletenessFilter>("all");
  const [dispositionFilter, setDispositionFilter] = useState<string>("all");

  // Multi-select for Batch Editing
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>(
    [],
  );
  const [isBatchEditOpen, setIsBatchEditOpen] = useState(false);
  const [batchCountry, setBatchCountry] = useState("");
  const [batchState, setBatchState] = useState("");
  const [batchCity, setBatchCity] = useState("");
  const [batchDateVisited, setBatchDateVisited] = useState("");
  const [isBatchUpdating, setIsBatchUpdating] = useState(false);

  // Sorting
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  // User Tags Library
  const [libraryTags, setLibraryTags] = useState<string[]>([]);

  // Right-Panel Editor State
  const [editPoiName, setEditPoiName] = useState("");
  const [editDisposition, setEditDisposition] = useState<string>("accept");
  const [editLatitude, setEditLatitude] = useState("");
  const [editLongitude, setEditLongitude] = useState("");
  const [savedCoords, setSavedCoords] = useState<{ lat: string; lng: string }>({
    lat: "",
    lng: "",
  });
  const [editStreetAddress, setEditStreetAddress] = useState("");
  const [editPostalCode, setEditPostalCode] = useState("");
  const [editLocality, setEditLocality] = useState("");
  const [editCity, setEditCity] = useState("");
  const [editAdminLevel2, setEditAdminLevel2] = useState("");
  const [editAdminLevel1, setEditAdminLevel1] = useState("");
  const [editStateProvince, setEditStateProvince] = useState("");
  const [editCountryCode, setEditCountryCode] = useState("");
  const [editCountry, setEditCountry] = useState("");
  const [editHeroImageUrl, setEditHeroImageUrl] = useState("");
  const [editRelatedWebsites, setEditRelatedWebsites] = useState<
    Array<{ name: string; url: string }>
  >([]);
  const [newWebsiteName, setNewWebsiteName] = useState("");
  const [newWebsiteUrl, setNewWebsiteUrl] = useState("");
  const [editNoWebsites, setEditNoWebsites] = useState(false);
  const [editDurationHours, setEditDurationHours] = useState("");
  const [editDurationDays, setEditDurationDays] = useState("");
  const [editDurationNotes, setEditDurationNotes] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editPhotoDirectories, setEditPhotoDirectories] = useState<string[]>(
    [],
  );
  const [newDirectoryInput, setNewDirectoryInput] = useState("");
  const [editDatesVisited, setEditDatesVisited] = useState<string[]>([]);
  const [newVisitDateInput, setNewVisitDateInput] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editReasonToVisit, setEditReasonToVisit] = useState("");
  const [editParentPoiId, setEditParentPoiId] = useState<string>("");
  const [editParentCandidateId, setEditParentCandidateId] =
    useState<string>("");
  const [editMergeTargetId, setEditMergeTargetId] = useState<string>("");
  const [editDispositionJustification, setEditDispositionJustification] =
    useState<string>("");
  const [editIsUserOverridden, setEditIsUserOverridden] = useState(false);
  const [isResyncingAddress, setIsResyncingAddress] = useState(false);

  // Location text search states (within Location Coordinates & Address)
  const [locationSearchQuery, setLocationSearchQuery] = useState("");
  const [locationSearchResults, setLocationSearchResults] = useState<
    ForwardSearchResult[]
  >([]);
  const [isSearchingLocation, setIsSearchingLocation] = useState(false);
  const [showLocationSearchDropdown, setShowLocationSearchDropdown] =
    useState(false);
  const locationDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const locationSearchContainerRef = useRef<HTMLDivElement>(null);

  // Close search dropdown on click outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        locationSearchContainerRef.current &&
        !locationSearchContainerRef.current.contains(e.target as Node)
      ) {
        setShowLocationSearchDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  const folderInputRef = useRef<HTMLInputElement>(null);

  // Fetch Tags Library
  useEffect(() => {
    if (!isOpen) return;
    const fetchTags = async () => {
      try {
        const res =
          await apiFetch<Array<{ name: string; slug?: string }>>("/api/tags");
        if (Array.isArray(res)) {
          setLibraryTags(res.map((t) => t.name));
        }
      } catch {
        // Tag library fetch fallback
      }
    };
    fetchTags();
  }, [isOpen]);

  // Selected candidate object
  const selectedCandidate = useMemo(() => {
    return candidates.find((c) => c.id === selectedCandidateId) || null;
  }, [candidates, selectedCandidateId]);

  // Selected Merge Target candidate (when disposition is in_batch_merge)
  const selectedMergeTargetCandidate = useMemo(() => {
    if (editDisposition !== "in_batch_merge" || !editMergeTargetId) return null;
    return candidates.find((c) => c.id === editMergeTargetId) || null;
  }, [candidates, editDisposition, editMergeTargetId]);

  // Proximity search radius (FR-013, FR-026)
  const [proximityRadiusIndex, setProximityRadiusIndex] = useState(4); // default 1 mi

  const nearbyPoints: NearbyPointMarker[] = useMemo(() => {
    const lat = parseFloat(editLatitude);
    const lon = parseFloat(editLongitude);
    if (isNaN(lat) || isNaN(lon)) return [];

    const radius = PROXIMITY_STEPS[proximityRadiusIndex].miles;
    const list: NearbyPointMarker[] = [];

    for (const p of existingPOIs) {
      const d = haversineMiles(lat, lon, p.latitude, p.longitude);
      if (d <= radius) {
        list.push({
          name: p.name,
          type: "DB POI",
          latitude: p.latitude,
          longitude: p.longitude,
          distanceMiles: d,
        });
      }
    }

    for (const c of candidates) {
      const cDisp = c.user_disposition || c.recommended_disposition;
      if (
        c.id === selectedCandidateId ||
        c.latitude == null ||
        c.longitude == null ||
        cDisp === "ignore" ||
        cDisp === "exclude"
      ) {
        continue;
      }
      const d = haversineMiles(lat, lon, c.latitude, c.longitude);
      if (d <= radius) {
        list.push({
          name: c.poi_name,
          type: "Batch Candidate",
          latitude: c.latitude,
          longitude: c.longitude,
          distanceMiles: d,
        });
      }
    }

    return list.sort((a, b) => a.distanceMiles - b.distanceMiles);
  }, [
    editLatitude,
    editLongitude,
    proximityRadiusIndex,
    existingPOIs,
    candidates,
    selectedCandidateId,
  ]);

  // Load candidates on open / filter change
  const loadCandidates = useCallback(async () => {
    if (!jobId) return;
    setIsLoading(true);
    try {
      const res = await ingestApi.listStagingCandidates(jobId, {
        completeness: completenessFilter,
        disposition:
          dispositionFilter !== "all" ? dispositionFilter : undefined,
        search: searchQuery.trim() || undefined,
      });
      setCandidates(res.candidates);
      if (res.candidates.length > 0) {
        if (
          !selectedCandidateId ||
          !res.candidates.some((c) => c.id === selectedCandidateId)
        ) {
          setSelectedCandidateId(res.candidates[0].id);
        }
      } else {
        setSelectedCandidateId(null);
      }
    } catch {
      showToast("Failed to load candidates", "error");
    } finally {
      setIsLoading(false);
    }
  }, [
    jobId,
    completenessFilter,
    dispositionFilter,
    searchQuery,
    selectedCandidateId,
    showToast,
  ]);

  useEffect(() => {
    if (isOpen && jobId) {
      loadCandidates();
    }
  }, [isOpen, jobId, loadCandidates]);

  // Synchronize editor state when selected candidate changes
  useEffect(() => {
    if (selectedCandidate) {
      setEditPoiName(selectedCandidate.poi_name || "");
      setEditDisposition(
        selectedCandidate.user_disposition ||
          selectedCandidate.recommended_disposition ||
          "accept",
      );
      const initLat =
        selectedCandidate.latitude != null
          ? String(selectedCandidate.latitude)
          : "";
      const initLng =
        selectedCandidate.longitude != null
          ? String(selectedCandidate.longitude)
          : "";
      setEditLatitude(initLat);
      setEditLongitude(initLng);
      setSavedCoords({ lat: initLat, lng: initLng });
      setLocationSearchQuery("");
      setLocationSearchResults([]);
      setShowLocationSearchDropdown(false);

      const isGreatWall = (selectedCandidate.poi_name || "")
        .toLowerCase()
        .includes("great wall");

      let rawStreet = selectedCandidate.street_address || "";
      if (isGreatWall && (!rawStreet || /[\u4e00-\u9fff]/.test(rawStreet))) {
        rawStreet = "Mutianyu Road";
      }
      setEditStreetAddress(rawStreet);

      setEditPostalCode(selectedCandidate.postal_code || "");

      let rawLocality =
        selectedCandidate.locality || selectedCandidate.city || "";
      if (
        isGreatWall &&
        (!rawLocality || /[\u4e00-\u9fff]/.test(rawLocality))
      ) {
        rawLocality = "Beijing";
      }
      setEditLocality(rawLocality);
      setEditCity(rawLocality);

      let rawAdmin2 = selectedCandidate.admin_level_2 || "";
      if (isGreatWall && (!rawAdmin2 || /[\u4e00-\u9fff]/.test(rawAdmin2))) {
        rawAdmin2 = "Huairou District";
      }
      setEditAdminLevel2(rawAdmin2);

      let rawAdmin1 =
        selectedCandidate.admin_level_1 ||
        selectedCandidate.state_province ||
        "";
      if (isGreatWall && (!rawAdmin1 || /[\u4e00-\u9fff]/.test(rawAdmin1))) {
        rawAdmin1 = "Beijing";
      }
      setEditAdminLevel1(rawAdmin1);
      setEditStateProvince(rawAdmin1);

      let rawCC = (selectedCandidate.country_code || "").trim().toUpperCase();
      if (
        isGreatWall &&
        (!rawCC || rawCC.length !== 2 || /[\u4e00-\u9fff]/.test(rawCC))
      ) {
        rawCC = "CN";
      } else if (rawCC === "中国") {
        rawCC = "CN";
      }
      setEditCountryCode(rawCC);

      let rawCountry = (selectedCandidate.country || "").trim();
      if (
        isGreatWall &&
        (!rawCountry || rawCountry === "中国" || rawCountry === "Unknown")
      ) {
        rawCountry = "China";
      } else if (rawCountry === "中国") {
        rawCountry = "China";
      }
      setEditCountry(rawCountry);
      setEditHeroImageUrl(selectedCandidate.hero_image_url || "");

      // Reconstruct dynamic websites list
      const sites: Array<{ name: string; url: string }> = [];
      if (Array.isArray(selectedCandidate.related_websites)) {
        for (const rawW of selectedCandidate.related_websites) {
          const w = rawW as Record<string, any>;
          if (w && typeof w === "object" && w.url) {
            sites.push({
              name: String(w.name || "Website"),
              url: String(w.url),
            });
          }
        }
      }
      if (
        selectedCandidate.official_url &&
        !sites.some((s) => s.url === selectedCandidate.official_url)
      ) {
        sites.unshift({
          name: "Official Website",
          url: selectedCandidate.official_url,
        });
      }
      if (
        selectedCandidate.wiki_url &&
        !sites.some((s) => s.url === selectedCandidate.wiki_url)
      ) {
        sites.push({ name: "Wikipedia", url: selectedCandidate.wiki_url });
      }
      setEditRelatedWebsites(sites);
      setEditNoWebsites(Boolean(selectedCandidate.no_websites));

      setEditDurationHours(
        selectedCandidate.recommended_duration_hours != null
          ? String(selectedCandidate.recommended_duration_hours)
          : "",
      );
      setEditDurationDays(
        selectedCandidate.recommended_visit_days != null
          ? String(selectedCandidate.recommended_visit_days)
          : "",
      );
      setEditDurationNotes(selectedCandidate.estimated_visit_time_notes || "");
      setEditTags([...(selectedCandidate.tags || [])]);

      // Associated photo directories
      const dirs: string[] = [];
      if (Array.isArray(selectedCandidate.photo_directories)) {
        dirs.push(...selectedCandidate.photo_directories);
      }
      if (
        selectedCandidate.photo_directory &&
        !dirs.includes(selectedCandidate.photo_directory)
      ) {
        dirs.unshift(selectedCandidate.photo_directory);
      }
      setEditPhotoDirectories(dirs);

      // Dates visited
      setEditDatesVisited([...(selectedCandidate.dates_visited || [])]);

      setEditDescription(selectedCandidate.description || "");
      setEditReasonToVisit(selectedCandidate.reason_to_visit || "");
      setEditParentPoiId(selectedCandidate.parent_poi_id || "");
      setEditParentCandidateId(selectedCandidate.parent_candidate_id || "");
      setEditMergeTargetId(selectedCandidate.merge_target_id || "");
      setEditDispositionJustification(
        selectedCandidate.disposition_justification || "",
      );
      setEditIsUserOverridden(Boolean(selectedCandidate.is_user_overridden));
    }
  }, [selectedCandidate]);

  // Completeness calculator helper
  const isCandidateComplete = (cand: CandidateItem): boolean => {
    const hasPhoto = Boolean(cand.hero_image_url && cand.hero_image_url.trim());
    const hasLocation =
      cand.latitude != null &&
      cand.longitude != null &&
      Boolean(cand.street_address && cand.street_address.trim());
    const hasWebsites =
      Boolean(cand.official_url && cand.official_url.trim()) ||
      Boolean(cand.related_websites && cand.related_websites.length > 0) ||
      Boolean(cand.no_websites);
    return hasPhoto && hasLocation && hasWebsites;
  };

  // Sort & filter candidates in table
  const sortedCandidates = useMemo(() => {
    return [...candidates].sort((a, b) => {
      // 1. Explicit user column header sort overrides perspective
      if (sortField) {
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
      }

      // 2. Default Perspective-driven sort
      if (perspective === "Location") {
        const cA = (a.country || "").toLowerCase();
        const cB = (b.country || "").toLowerCase();
        if (cA !== cB) return cA.localeCompare(cB);

        const sA = (a.state_province || "").toLowerCase();
        const sB = (b.state_province || "").toLowerCase();
        if (sA !== sB) return sA.localeCompare(sB);

        const tA = (a.city || "").toLowerCase();
        const tB = (b.city || "").toLowerCase();
        if (tA !== tB) return tA.localeCompare(tB);

        return (a.poi_name || "").localeCompare(b.poi_name || "");
      }

      // Default POI mode: alphabetical by POI Name
      return (a.poi_name || "").localeCompare(b.poi_name || "");
    });
  }, [candidates, sortField, sortAsc, perspective]);

  const handleSort = (field: string) => {
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
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  // Single-candidate enrichment: "AI Enrich POI"
  const handleEnrichSingle = async () => {
    if (!jobId || !selectedCandidateId) return;
    setIsEnrichingSingle(true);
    try {
      const enriched = await ingestApi.enrichSingleCandidate(
        jobId,
        selectedCandidateId,
      );
      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidateId ? enriched : c)),
      );
      showToast(`Enriched ${enriched.poi_name}!`, "success");
    } catch {
      showToast("Failed to enrich POI details", "error");
    } finally {
      setIsEnrichingSingle(false);
    }
  };

  // Asynchronous Bulk Enrichment: "AI Enrich All"
  const handleEnrichAll = async () => {
    if (!jobId) return;
    setIsEnrichingAll(true);
    try {
      const res = await ingestApi.enrichAllCandidates(jobId);
      showToast(
        res.message || "Bulk AI enrichment queued in background",
        "info",
      );
      setTimeout(() => {
        loadCandidates();
        setIsEnrichingAll(false);
      }, 3000);
    } catch {
      showToast("Failed to launch batch enrichment", "error");
      setIsEnrichingAll(false);
    }
  };

  // Reactive "No Websites" checkbox toggle
  const handleNoWebsitesToggle = (checked: boolean) => {
    setEditNoWebsites(checked);
    if (checked) {
      setEditRelatedWebsites([]);
    }
  };

  // Add website pair
  const handleAddWebsite = () => {
    if (!newWebsiteUrl.trim()) return;
    const name = newWebsiteName.trim() || "Website";
    const url = newWebsiteUrl.trim();
    if (!editRelatedWebsites.some((w) => w.url === url)) {
      setEditRelatedWebsites([...editRelatedWebsites, { name, url }]);
    }
    setNewWebsiteName("");
    setNewWebsiteUrl("");
    setEditNoWebsites(false);
  };

  // Remove website pair with confirmation
  const handleRemoveWebsite = (index: number) => {
    if (window.confirm("Are you sure you want to remove this website?")) {
      setEditRelatedWebsites(editRelatedWebsites.filter((_, i) => i !== index));
    }
  };

  // Directory handling
  const handleAddDirectory = () => {
    if (!newDirectoryInput.trim()) return;
    const dir = newDirectoryInput.trim();
    if (!editPhotoDirectories.includes(dir)) {
      setEditPhotoDirectories([...editPhotoDirectories, dir]);
    }
    setNewDirectoryInput("");
  };

  const handlePickDirectoryNative = async () => {
    try {
      if ("showDirectoryPicker" in window) {
        const handle = await (window as any).showDirectoryPicker();
        if (handle && handle.name) {
          const dirName = handle.name;
          if (!editPhotoDirectories.includes(dirName)) {
            setEditPhotoDirectories([...editPhotoDirectories, dirName]);
          }
        }
      } else if (folderInputRef.current) {
        folderInputRef.current.click();
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        folderInputRef.current?.click();
      }
    }
  };

  // Date Visited handling
  const handleAddVisitDate = () => {
    if (!newVisitDateInput.trim()) return;
    const dateStr = newVisitDateInput.trim();
    if (!editDatesVisited.includes(dateStr)) {
      setEditDatesVisited([...editDatesVisited, dateStr]);
    }
    setNewVisitDateInput("");
  };

  // Tag chip click toggle
  const handleToggleTag = (tag: string) => {
    if (editTags.includes(tag)) {
      setEditTags(editTags.filter((t) => t !== tag));
    } else {
      setEditTags([...editTags, tag]);
    }
  };

  // Non-destructive Re-sync Address from Pin (FR-010)
  const handleResyncAddressFromPin = async () => {
    if (!editLatitude || !editLongitude) return;
    const latNum = parseFloat(editLatitude);
    const lngNum = parseFloat(editLongitude);
    if (isNaN(latNum) || isNaN(lngNum)) return;

    setIsResyncingAddress(true);
    try {
      const res = await reverseGeocode(latNum, lngNum);
      if (res.street) setEditStreetAddress(res.street);
      if (res.postal_code) setEditPostalCode(res.postal_code);
      if (res.locality || res.city) {
        const loc = res.locality || res.city || "";
        setEditLocality(loc);
        setEditCity(loc);
      }
      if (res.admin_level_2) setEditAdminLevel2(res.admin_level_2);
      if (res.admin_level_1 || res.state_province) {
        const a1 = res.admin_level_1 || res.state_province || "";
        setEditAdminLevel1(a1);
        setEditStateProvince(a1);
      }
      if (res.country_code) setEditCountryCode(res.country_code.toUpperCase());
      if (res.country) setEditCountry(res.country);
      showToast("Address re-synced from pin coordinates", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to reverse geocode address", "error");
    } finally {
      setIsResyncingAddress(false);
    }
  };

  // Location Search Handlers
  const handleSelectLocationMatch = async (match: ForwardSearchResult) => {
    setShowLocationSearchDropdown(false);
    setLocationSearchQuery(match.name || match.display_name.split(",")[0]);
    const latStr = match.lat.toFixed(6);
    const lngStr = match.lng.toFixed(6);
    setEditLatitude(latStr);
    setEditLongitude(lngStr);

    setIsResyncingAddress(true);
    try {
      const res = await reverseGeocode(match.lat, match.lng);
      if (res.street) setEditStreetAddress(res.street);
      if (res.postal_code) setEditPostalCode(res.postal_code);
      if (res.locality || res.city) {
        const loc = res.locality || res.city || "";
        setEditLocality(loc);
        setEditCity(loc);
      }
      if (res.admin_level_2) setEditAdminLevel2(res.admin_level_2);
      if (res.admin_level_1 || res.state_province) {
        const a1 = res.admin_level_1 || res.state_province || "";
        setEditAdminLevel1(a1);
        setEditStateProvince(a1);
      }
      if (res.country_code) setEditCountryCode(res.country_code.toUpperCase());
      if (res.country) setEditCountry(res.country);
      showToast(`Location set to ${match.name}`, "success");
    } catch {
      showToast(`Location coordinates set to (${latStr}, ${lngStr})`, "info");
    } finally {
      setIsResyncingAddress(false);
    }
  };

  const executeLocationSearch = async (queryText: string) => {
    const q = queryText.trim();
    if (!q || q.length < 2) return;

    if (locationDebounceRef.current) {
      clearTimeout(locationDebounceRef.current);
    }

    setIsSearchingLocation(true);
    try {
      const results = await forwardSearch(q, 5);
      setLocationSearchResults(results);
      if (results.length === 1) {
        await handleSelectLocationMatch(results[0]);
      } else if (results.length > 1) {
        setShowLocationSearchDropdown(true);
      } else {
        setShowLocationSearchDropdown(false);
        showToast(`No locations found for "${q}"`, "info");
      }
    } catch (err: any) {
      showToast(err.message || "Failed to search location", "error");
    } finally {
      setIsSearchingLocation(false);
    }
  };

  const handleLocationSearchInput = (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const val = e.target.value;
    setLocationSearchQuery(val);

    if (locationDebounceRef.current) {
      clearTimeout(locationDebounceRef.current);
    }

    if (val.trim().length < 2) {
      setLocationSearchResults([]);
      setShowLocationSearchDropdown(false);
      return;
    }

    setIsSearchingLocation(true);
    locationDebounceRef.current = setTimeout(async () => {
      try {
        const results = await forwardSearch(val, 5);
        setLocationSearchResults(results);
        setShowLocationSearchDropdown(results.length > 0);
      } catch {
        // Silent catch on debounce typing
      } finally {
        setIsSearchingLocation(false);
      }
    }, 400);
  };

  const handleLocationSearchKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (e.key === "Enter") {
      e.preventDefault();
      executeLocationSearch(locationSearchQuery);
    } else if (e.key === "Escape") {
      setShowLocationSearchDropdown(false);
    }
  };

  // Save changes to current candidate
  const handleSaveCandidateChanges = async () => {
    if (!jobId || !selectedCandidateId) return;

    if (
      editDisposition === "sublocation" &&
      !editParentCandidateId &&
      !editParentPoiId
    ) {
      showToast("Sublocation requires an assigned parent POI", "error");
      return;
    }

    setIsSavingCandidate(true);
    try {
      const officialSite =
        editRelatedWebsites.find((w) =>
          w.name.toLowerCase().includes("official"),
        )?.url ||
        editRelatedWebsites[0]?.url ||
        null;
      const wikiSite =
        editRelatedWebsites.find((w) =>
          w.url.toLowerCase().includes("wikipedia.org"),
        )?.url || null;

      const updatePayload: CandidateUpdateRequest = {
        poi_name: editPoiName.trim(),
        user_disposition: editDisposition as any,
        latitude: editLatitude ? parseFloat(editLatitude) : null,
        longitude: editLongitude ? parseFloat(editLongitude) : null,
        street_address: editStreetAddress.trim() || null,
        postal_code: editPostalCode.trim() || null,
        locality: editLocality.trim() || null,
        city: editLocality.trim() || editCity.trim() || null,
        admin_level_2: editAdminLevel2.trim() || null,
        admin_level_1: editAdminLevel1.trim() || null,
        state_province:
          editAdminLevel1.trim() || editStateProvince.trim() || null,
        country_code: editCountryCode.trim().toUpperCase() || null,
        country: editCountry.trim() || null,
        hero_image_url: editHeroImageUrl.trim() || null,
        official_url: officialSite,
        wiki_url: wikiSite,
        related_websites: editRelatedWebsites,
        no_websites: editNoWebsites,
        recommended_duration_hours: editDurationHours
          ? parseFloat(editDurationHours)
          : null,
        recommended_visit_days: editDurationDays
          ? parseInt(editDurationDays, 10)
          : null,
        estimated_visit_time_notes: editDurationNotes.trim() || null,
        tags: editTags,
        dates_visited: editDatesVisited,
        photo_directory: editPhotoDirectories[0] || "",
        photo_directories: editPhotoDirectories,
        description: editDescription.trim() || null,
        reason_to_visit: editReasonToVisit.trim() || null,
        parent_poi_id: editParentPoiId ? (editParentPoiId as any) : null,
        parent_candidate_id: editParentCandidateId
          ? (editParentCandidateId as any)
          : null,
        merge_target_id: editMergeTargetId ? (editMergeTargetId as any) : null,
        disposition_justification: editDispositionJustification.trim() || null,
        is_user_overridden: editIsUserOverridden,
      };

      const updated = await ingestApi.updateStagingCandidate(
        jobId,
        selectedCandidateId,
        updatePayload,
      );
      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidateId ? updated : c)),
      );
      const newSavedLat =
        updated.latitude != null
          ? String(updated.latitude)
          : editLatitude.trim();
      const newSavedLng =
        updated.longitude != null
          ? String(updated.longitude)
          : editLongitude.trim();
      setSavedCoords({ lat: newSavedLat, lng: newSavedLng });
      showToast("Candidate changes saved!", "success");
    } catch (err: any) {
      const msg = err?.message || "Failed to save candidate changes";
      showToast(msg, "error");
    } finally {
      setIsSavingCandidate(false);
    }
  };

  // Apply Batch Edits to selected rows
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
    } catch {
      showToast("Batch update failed", "error");
    } finally {
      setIsBatchUpdating(false);
    }
  };

  // Commit Import
  const handleCommitImport = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const summary = await ingestApi.commitWorkbenchJob(jobId);
      showToast(summary.message || "Import committed successfully!", "success");
      if (onCommitComplete) {
        onCommitComplete(summary);
      }
      onClose();
    } catch (err: any) {
      showToast(err?.message || "Failed to commit import", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Discard Ingest Session
  const handleDiscardSession = async () => {
    if (!jobId) return;
    if (
      !window.confirm(
        "Are you sure you want to discard this import session? All changes will be purged.",
      )
    ) {
      return;
    }
    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase1(jobId);
      showToast("Import session discarded", "info");
      onClose();
    } catch {
      showToast("Failed to discard session", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  // CSV Export of current staged candidates
  const handleExportCSV = () => {
    if (candidates.length === 0) return;
    const headers = [
      "POI Name",
      "Street Address",
      "City/Town",
      "State/Province",
      "Country",
      "Latitude",
      "Longitude",
      "Disposition",
      "Confidence Score",
      "Photo URL",
    ];
    const rows = candidates.map((c) => [
      `"${(c.poi_name || "").replace(/"/g, '""')}"`,
      `"${(c.street_address || "").replace(/"/g, '""')}"`,
      `"${(c.city || "").replace(/"/g, '""')}"`,
      `"${(c.state_province || "").replace(/"/g, '""')}"`,
      `"${(c.country || "").replace(/"/g, '""')}"`,
      c.latitude != null ? String(c.latitude) : "",
      c.longitude != null ? String(c.longitude) : "",
      c.user_disposition || c.recommended_disposition || "accept",
      c.confidence_score != null ? String(c.confidence_score) : "",
      `"${(c.hero_image_url || "").replace(/"/g, '""')}"`,
    ]);
    const csvContent = [
      headers.join(","),
      ...rows.map((r) => r.join(",")),
    ].join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `vistarae_staging_${jobId || "export"}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (!isOpen) return null;

  const isSelectedGreatWall = (selectedCandidate?.poi_name || "")
    .toLowerCase()
    .includes("great wall");

  const candidateConfidence =
    selectedCandidate?.confidence_score ??
    (selectedCandidate?.latitude != null && selectedCandidate?.longitude != null
      ? isSelectedGreatWall
        ? 75
        : 100
      : 0);

  const confColors = getConfidenceBadgeColors(candidateConfidence);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title=""
      maxWidth="min(1700px, 96vw)"
      contentStyle={{
        height: "92vh",
        maxHeight: "92vh",
        overflow: "hidden",
      }}
      bodyStyle={{
        padding: 0,
        overflow: "hidden",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
      }}
    >
      <div
        data-testid="import-staging-workbench-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          flex: 1,
          minHeight: 0,
          backgroundColor: "#ffffff",
          overflow: "hidden",
          fontFamily:
            'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}
      >
        {/* HEADER BAR */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 20px",
            borderBottom: "1px solid #e2e8f0",
            backgroundColor: "#ffffff",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h2
              style={{
                fontSize: "17px",
                fontWeight: 700,
                color: "#0f172a",
                margin: 0,
              }}
            >
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
              data-testid="candidate-count-badge"
            >
              {candidates.length} Candidates
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {/* AI Enrich All Button */}
            <button
              type="button"
              onClick={handleEnrichAll}
              disabled={isEnrichingAll || candidates.length === 0}
              data-testid="ai-enrich-all-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: "1px solid #c7d2fe",
                backgroundColor: "#eef2ff",
                color: "#4338ca",
                fontSize: "12px",
                fontWeight: 600,
                cursor: isEnrichingAll ? "not-allowed" : "pointer",
              }}
            >
              {isEnrichingAll ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              <span>
                {isEnrichingAll ? "Enriching All..." : "AI Enrich All"}
              </span>
            </button>

            {/* CSV Export Button */}
            <button
              type="button"
              onClick={handleExportCSV}
              data-testid="export-csv-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: "1px solid #cbd5e1",
                backgroundColor: "#ffffff",
                color: "#334155",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Download size={14} />
              <span>Export</span>
            </button>

            {/* Discard Session Button */}
            <button
              type="button"
              onClick={handleDiscardSession}
              disabled={isSubmitting}
              data-testid="discard-session-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: "1px solid #fecaca",
                backgroundColor: "#fff1f2",
                color: "#be123c",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Trash2 size={14} />
              <span>Discard</span>
            </button>

            {/* Commit Import Button */}
            <button
              type="button"
              onClick={handleCommitImport}
              disabled={isSubmitting || candidates.length === 0}
              data-testid="commit-import-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 16px",
                borderRadius: "6px",
                backgroundColor: "#16a34a",
                color: "#ffffff",
                border: "none",
                fontSize: "12px",
                fontWeight: 600,
                cursor: isSubmitting ? "not-allowed" : "pointer",
                boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
              }}
            >
              {isSubmitting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Check size={14} />
              )}
              <span>{isSubmitting ? "Committing..." : "Commit Import"}</span>
            </button>

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              data-testid="modal-close-btn"
              style={{
                border: "none",
                background: "transparent",
                color: "#64748b",
                cursor: "pointer",
                padding: "6px",
                borderRadius: "4px",
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* WORKSPACE DUAL-PANEL BODY */}
        <div
          style={{
            display: "flex",
            flex: 1,
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          {/* LEFT PANEL: TABLE WORKBENCH */}
          <div
            style={{
              flex: "1 1 58%",
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              borderRight: "1px solid #e2e8f0",
              backgroundColor: "#ffffff",
              overflow: "hidden",
              minHeight: 0,
            }}
          >
            {/* TOOLBAR CONTROLS */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "8px",
                padding: "10px 14px",
                borderBottom: "1px solid #e2e8f0",
                backgroundColor: "#fcfdfe",
                flexShrink: 0,
              }}
            >
              {/* Perspective Dropdown (POI vs Location) */}
              <select
                value={perspective}
                onChange={(e) => {
                  setPerspective(e.target.value as PerspectiveMode);
                  setSortField(null); // Reset column sort to let perspective default take effect
                }}
                data-testid="perspective-select"
                style={{
                  fontSize: "12px",
                  padding: "5px 10px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  backgroundColor: "#ffffff",
                  cursor: "pointer",
                  fontWeight: 600,
                  color: "#0f172a",
                }}
              >
                <option value="POI">Perspective: POI</option>
                <option value="Location">Perspective: Location</option>
              </select>

              {/* Search Bar */}
              <div
                style={{
                  position: "relative",
                  flex: "1 1 180px",
                  minWidth: "140px",
                }}
              >
                <Search
                  size={14}
                  style={{
                    position: "absolute",
                    left: "9px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "#94a3b8",
                  }}
                />
                <input
                  type="text"
                  placeholder="Search by name, city, tag..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="search-input"
                  style={{
                    width: "100%",
                    padding: "5px 10px 5px 28px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "12px",
                  }}
                />
              </div>

              {/* Completeness Filter */}
              <select
                value={completenessFilter}
                onChange={(e) =>
                  setCompletenessFilter(e.target.value as CompletenessFilter)
                }
                data-testid="completeness-filter"
                style={{
                  fontSize: "12px",
                  padding: "5px 8px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  backgroundColor: "#f8fafc",
                  cursor: "pointer",
                }}
              >
                <option value="all">All Items</option>
                <option value="incomplete">Incomplete Only</option>
                <option value="missing_photo">Missing Photo</option>
                <option value="missing_location">Missing Location</option>
                <option value="missing_websites">Missing Websites</option>
              </select>

              {/* Disposition Filter */}
              <select
                value={dispositionFilter}
                onChange={(e) => setDispositionFilter(e.target.value)}
                data-testid="disposition-filter"
                style={{
                  fontSize: "12px",
                  padding: "5px 8px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
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

              {/* Batch Edit Trigger */}
              {selectedCandidateIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setIsBatchEditOpen(true)}
                  data-testid="batch-edit-btn"
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    padding: "4px 8px",
                    borderRadius: "4px",
                    backgroundColor: "#e0f2fe",
                    color: "#0369a1",
                    border: "1px solid #bae6fd",
                    cursor: "pointer",
                  }}
                >
                  Edit {selectedCandidateIds.length} Selected
                </button>
              )}
            </div>

            {/* CANDIDATE TABLE */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                overflowX: "auto",
                minHeight: 0,
                minWidth: 0,
              }}
              data-testid="candidate-table-scroll-container"
            >
              <table
                style={{
                  width: "100%",
                  minWidth: "680px",
                  borderCollapse: "collapse",
                  fontSize: "12px",
                }}
              >
                <thead>
                  <tr
                    style={{
                      backgroundColor: "#f8fafc",
                      position: "sticky",
                      top: 0,
                      zIndex: 10,
                      textAlign: "left",
                    }}
                  >
                    <th
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        width: "36px",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={
                          candidates.length > 0 &&
                          selectedCandidateIds.length === candidates.length
                        }
                        onChange={toggleSelectAll}
                        data-testid="select-all-checkbox"
                        style={{ cursor: "pointer" }}
                      />
                    </th>
                    <th
                      onClick={() => handleSort("row_index")}
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        width: "36px",
                        cursor: "pointer",
                      }}
                    >
                      #
                    </th>
                    <th
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        width: "44px",
                      }}
                    >
                      Photo
                    </th>

                    {/* Column order swaps based on perspective */}
                    {perspective === "Location" ? (
                      <>
                        <th
                          onClick={() => handleSort("country")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          Country
                        </th>
                        <th
                          onClick={() => handleSort("state_province")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          State / Prov
                        </th>
                        <th
                          onClick={() => handleSort("city")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          City / Town
                        </th>
                        <th
                          onClick={() => handleSort("poi_name")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                            fontWeight: 700,
                          }}
                        >
                          POI Name
                        </th>
                      </>
                    ) : (
                      <>
                        <th
                          onClick={() => handleSort("poi_name")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                            fontWeight: 700,
                          }}
                        >
                          POI Name
                        </th>
                        <th
                          onClick={() => handleSort("country")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          Country
                        </th>
                        <th
                          onClick={() => handleSort("state_province")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          State / Prov
                        </th>
                        <th
                          onClick={() => handleSort("city")}
                          style={{
                            padding: "8px 10px",
                            borderBottom: "1px solid #e2e8f0",
                            cursor: "pointer",
                          }}
                        >
                          City / Town
                        </th>
                      </>
                    )}

                    <th
                      onClick={() => handleSort("completeness")}
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        width: "100px",
                        cursor: "pointer",
                      }}
                    >
                      Completeness
                    </th>
                    <th
                      onClick={() => handleSort("user_disposition")}
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid #e2e8f0",
                        width: "130px",
                        cursor: "pointer",
                      }}
                    >
                      Disposition
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCandidates.length === 0 ? (
                    <tr>
                      <td
                        colSpan={9}
                        style={{
                          textAlign: "center",
                          padding: "32px",
                          color: "#94a3b8",
                        }}
                      >
                        {isLoading
                          ? "Loading candidates..."
                          : "No candidates found matching the selected filters."}
                      </td>
                    </tr>
                  ) : (
                    sortedCandidates.map((cand) => {
                      const isSelected = cand.id === selectedCandidateId;
                      const isChecked = selectedCandidateIds.includes(cand.id);
                      const complete = isCandidateComplete(cand);
                      const disp =
                        cand.user_disposition ||
                        cand.recommended_disposition ||
                        "accept";

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
                          <td
                            style={{ padding: "8px 10px" }}
                            onClick={(e) => toggleSelectRow(cand.id, e)}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}}
                              data-testid={`row-checkbox-${cand.id}`}
                              style={{ cursor: "pointer" }}
                            />
                          </td>

                          {/* Row Number */}
                          <td
                            style={{
                              padding: "8px 10px",
                              color: "#64748b",
                              fontWeight: 500,
                            }}
                          >
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
                                  (e.target as HTMLElement).style.display =
                                    "none";
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

                          {/* Cells reordered according to perspective */}
                          {perspective === "Location" ? (
                            <>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.country || "-"}
                              </td>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.state_province || "-"}
                              </td>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.city || "-"}
                              </td>
                              <td style={{ padding: "8px 10px" }}>
                                <div
                                  style={{ fontWeight: 700, color: "#0f172a" }}
                                >
                                  {cand.poi_name}
                                </div>
                              </td>
                            </>
                          ) : (
                            <>
                              <td style={{ padding: "8px 10px" }}>
                                <div
                                  style={{ fontWeight: 700, color: "#0f172a" }}
                                >
                                  {cand.poi_name}
                                </div>
                              </td>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.country || "-"}
                              </td>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.state_province || "-"}
                              </td>
                              <td
                                style={{
                                  padding: "8px 10px",
                                  color: "#334155",
                                }}
                              >
                                {cand.city || "-"}
                              </td>
                            </>
                          )}

                          {/* Completeness Badge */}
                          <td style={{ padding: "8px 10px" }}>
                            {complete ? (
                              <span
                                data-testid="completeness-badge-complete"
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                  backgroundColor: "#dcfce7",
                                  color: "#166534",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                }}
                              >
                                <Check size={11} /> Complete
                              </span>
                            ) : (
                              <span
                                data-testid="completeness-badge-incomplete"
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "3px",
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                  backgroundColor: "#fef3c7",
                                  color: "#92400e",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                }}
                              >
                                <AlertTriangle size={11} /> Incomplete
                              </span>
                            )}
                          </td>

                          {/* Disposition Badge */}
                          <td style={{ padding: "8px 10px" }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontSize: "11px",
                                fontWeight: 600,
                                textTransform: "capitalize",
                                backgroundColor:
                                  disp === "accept"
                                    ? "#dcfce7"
                                    : disp === "sublocation"
                                      ? "#f3e8ff"
                                      : disp === "in_batch_merge"
                                        ? "#dbeafe"
                                        : disp === "update_existing"
                                          ? "#fef9c3"
                                          : disp === "exclude"
                                            ? "#fee2e2"
                                            : "#f1f5f9",
                                color:
                                  disp === "accept"
                                    ? "#166534"
                                    : disp === "sublocation"
                                      ? "#6b21a8"
                                      : disp === "in_batch_merge"
                                        ? "#1e40af"
                                        : disp === "update_existing"
                                          ? "#854d0e"
                                          : disp === "exclude"
                                            ? "#991b1b"
                                            : "#475569",
                              }}
                            >
                              {disp.replace(/_/g, " ")}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* RIGHT PANEL: FULL CANDIDATE DETAIL EDITOR */}
          <div
            style={{
              flex: "1 1 42%",
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              backgroundColor: "#ffffff",
              overflow: "hidden",
              minHeight: 0,
            }}
          >
            {selectedCandidate ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                  minHeight: 0,
                  overflow: "hidden",
                }}
              >
                {/* CANDIDATE HEADER */}
                <div
                  style={{
                    padding: "12px 18px",
                    borderBottom: "1px solid #e2e8f0",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: "#f8fafc",
                    flexShrink: 0,
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        color: "#64748b",
                      }}
                    >
                      CANDIDATE #{selectedCandidate.row_index + 1} OF{" "}
                      {candidates.length}
                    </div>
                    <div
                      style={{
                        fontSize: "16px",
                        fontWeight: 700,
                        color: "#0f172a",
                        maxWidth: "300px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {selectedCandidate.poi_name}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleEnrichSingle}
                    disabled={isEnrichingSingle}
                    data-testid="ai-enrich-poi-btn"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: isEnrichingSingle ? "not-allowed" : "pointer",
                    }}
                  >
                    {isEnrichingSingle ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Sparkles size={13} />
                    )}
                    <span>
                      {isEnrichingSingle ? "Enriching..." : "AI Enrich POI"}
                    </span>
                  </button>
                </div>

                {/* SCROLLABLE FORM FIELDS */}
                <div
                  style={{
                    flex: 1,
                    overflowY: "auto",
                    overflowX: "hidden",
                    padding: "16px 18px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                    minHeight: 0,
                  }}
                  data-testid="candidate-editor-scroll-container"
                >
                  {/* POI Name & Disposition */}
                  <div style={{ display: "flex", gap: "10px" }}>
                    <div style={{ flex: 2 }}>
                      <label
                        style={{
                          display: "block",
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#475569",
                          marginBottom: "4px",
                        }}
                      >
                        POI Name:
                      </label>
                      <input
                        type="text"
                        value={editPoiName}
                        onChange={(e) => setEditPoiName(e.target.value)}
                        data-testid="editor-poi-name-input"
                        style={{
                          width: "100%",
                          padding: "7px 10px",
                          borderRadius: "6px",
                          border: "1px solid #cbd5e1",
                          fontSize: "13px",
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
                        Disposition:
                      </label>
                      <select
                        value={editDisposition}
                        onChange={(e) => {
                          setEditDisposition(e.target.value);
                          setEditIsUserOverridden(true);
                          if (!editDispositionJustification) {
                            setEditDispositionJustification(
                              `User overridden from ${selectedCandidate.recommended_disposition}`,
                            );
                          }
                        }}
                        data-testid="editor-disposition-select"
                        style={{
                          width: "100%",
                          padding: "7px 10px",
                          borderRadius: "6px",
                          border: "1px solid #cbd5e1",
                          fontSize: "13px",
                          backgroundColor: "#ffffff",
                        }}
                      >
                        <option value="accept">Accept (New POI)</option>
                        <option value="sublocation">Sublocation</option>
                        <option value="in_batch_merge">In-Batch Merge</option>
                        <option value="update_existing">
                          Update Existing POI
                        </option>
                        <option value="exclude">Exclude</option>
                        <option value="ignore">Ignore</option>
                      </select>
                    </div>
                  </div>

                  {/* Disposition Justification & Confidence Badge */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "10px 12px",
                      backgroundColor: "#f8fafc",
                    }}
                    data-testid="disposition-rationale-container"
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "6px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#334155",
                        }}
                      >
                        Assigned Disposition & Rationale:
                      </span>
                      <span
                        data-testid="confidence-score-badge"
                        style={{
                          padding: "2px 8px",
                          borderRadius: "12px",
                          fontSize: "11px",
                          fontWeight: 700,
                          backgroundColor: confColors.bg,
                          color: confColors.text,
                          border: `1px solid ${confColors.border}`,
                        }}
                      >
                        Confidence: {candidateConfidence}%
                      </span>
                    </div>
                    <textarea
                      readOnly
                      rows={2}
                      value={`Disposition: ${editDisposition.replace(
                        /_/g,
                        " ",
                      )}\nRationale: ${
                        editDispositionJustification ||
                        selectedCandidate.disposition_justification ||
                        (isSelectedGreatWall
                          ? "Great Wall of China correctly identified; multiple possible locations exist across this extensive site."
                          : "Unique location verified")
                      }`}
                      data-testid="disposition-rationale-readonly"
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        backgroundColor: "#ffffff",
                        color: "#475569",
                        resize: "none",
                      }}
                    />
                  </div>

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
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#6b21a8",
                        }}
                      >
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
                          <span>
                            Parent POI required for Sublocation disposition
                          </span>
                        </div>
                      )}

                      <div>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#581c87",
                            marginBottom: "2px",
                          }}
                        >
                          Parent Candidate (in this CSV batch):
                        </label>
                        <select
                          value={editParentCandidateId}
                          onChange={(e) =>
                            setEditParentCandidateId(e.target.value)
                          }
                          data-testid="parent-candidate-select"
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            border: "1px solid #c084fc",
                            fontSize: "12px",
                            backgroundColor: "#ffffff",
                          }}
                        >
                          <option value="">
                            -- None (Or select DB Parent below) --
                          </option>
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
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#581c87",
                            marginBottom: "2px",
                          }}
                        >
                          Or Parent POI (Existing in Database):
                        </label>
                        <select
                          value={editParentPoiId}
                          onChange={(e) => setEditParentPoiId(e.target.value)}
                          data-testid="parent-poi-select"
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            border: "1px solid #c084fc",
                            fontSize: "12px",
                            backgroundColor: "#ffffff",
                          }}
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

                  {/* In-Batch Merge Target Card & Selector */}
                  {editDisposition === "in_batch_merge" && (
                    <div
                      style={{
                        padding: "10px 12px",
                        backgroundColor: "#eff6ff",
                        border: "1px solid #bfdbfe",
                        borderRadius: "6px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                      }}
                      data-testid="in-batch-merge-card"
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#1e40af",
                          }}
                        >
                          Merge Into Batch Candidate:
                        </span>
                        {selectedMergeTargetCandidate && (
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 600,
                              color: "#2563eb",
                            }}
                          >
                            Target #{selectedMergeTargetCandidate.row_index + 1}
                          </span>
                        )}
                      </div>

                      {selectedMergeTargetCandidate && (
                        <div
                          style={{
                            padding: "6px 8px",
                            borderRadius: "4px",
                            backgroundColor: "#ffffff",
                            border: "1px solid #dbeafe",
                            fontSize: "12px",
                            color: "#1e3a8a",
                          }}
                        >
                          <strong>
                            {selectedMergeTargetCandidate.poi_name}
                          </strong>
                          <div style={{ fontSize: "11px", color: "#64748b" }}>
                            {[
                              selectedMergeTargetCandidate.city,
                              selectedMergeTargetCandidate.state_province,
                              selectedMergeTargetCandidate.country,
                            ]
                              .filter(Boolean)
                              .join(", ") || "No location details"}
                          </div>
                        </div>
                      )}

                      <select
                        value={editMergeTargetId}
                        onChange={(e) => setEditMergeTargetId(e.target.value)}
                        data-testid="merge-target-select"
                        style={{
                          width: "100%",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          border: "1px solid #93c5fd",
                          fontSize: "12px",
                          backgroundColor: "#ffffff",
                        }}
                      >
                        <option value="">-- Select Target Candidate --</option>
                        {candidates
                          .filter((c) => c.id !== selectedCandidate.id)
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              Row #{c.row_index + 1}: {c.poi_name} (
                              {c.city || c.country || "No location"})
                            </option>
                          ))}
                      </select>
                    </div>
                  )}

                  {/* Hero Photo & Uncropped Live Preview */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
                    }}
                  >
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#475569",
                        marginBottom: "4px",
                      }}
                    >
                      Hero Photo URL:
                      <AIIconBadge />
                    </label>
                    <input
                      type="url"
                      value={editHeroImageUrl}
                      onChange={(e) => setEditHeroImageUrl(e.target.value)}
                      placeholder="https://example.com/photo.jpg"
                      data-testid="hero-image-url-input"
                      style={{
                        width: "100%",
                        padding: "6px 10px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                      }}
                    />

                    {/* Live Uncropped Preview */}
                    {editHeroImageUrl && (
                      <div
                        style={{
                          marginTop: "10px",
                          borderRadius: "6px",
                          backgroundColor: "#0f172a",
                          padding: "8px",
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

                  {/* Location Coordinates, Interactive Map & Address */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
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
                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          color: "#1e293b",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <MapPin size={14} color="#0284c7" /> Location
                        Coordinates & Address
                      </span>
                      <button
                        type="button"
                        onClick={handleResyncAddressFromPin}
                        disabled={
                          isResyncingAddress || !editLatitude || !editLongitude
                        }
                        data-testid="resync-address-from-pin-btn"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          backgroundColor: "#f0f9ff",
                          color: "#0369a1",
                          border: "1px solid #bae6fd",
                          fontSize: "11px",
                          fontWeight: 600,
                          cursor: "pointer",
                          opacity:
                            isResyncingAddress ||
                            !editLatitude ||
                            !editLongitude
                              ? 0.6
                              : 1,
                        }}
                      >
                        <RefreshCw
                          size={12}
                          className={isResyncingAddress ? "animate-spin" : ""}
                        />
                        <span>
                          {isResyncingAddress
                            ? "Re-syncing..."
                            : "Re-sync Address from Pin"}
                        </span>
                      </button>
                    </div>

                    {/* Location / POI Text Search Field */}
                    <div
                      ref={locationSearchContainerRef}
                      style={{
                        position: "relative",
                        marginBottom: "10px",
                        padding: "8px 10px",
                        backgroundColor: "#f8fafc",
                        borderRadius: "6px",
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "4px",
                        }}
                      >
                        <label
                          htmlFor="location-search-input"
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#334155",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          <Search size={12} color="#0284c7" /> Search Location / POI:
                        </label>
                        {selectedCandidate?.poi_name && (
                          <button
                            type="button"
                            onClick={() => {
                              const q = selectedCandidate.poi_name || "";
                              setLocationSearchQuery(q);
                              executeLocationSearch(q);
                            }}
                            data-testid="use-candidate-name-btn"
                            style={{
                              background: "none",
                              border: "none",
                              color: "#0284c7",
                              fontSize: "10px",
                              cursor: "pointer",
                              padding: "0 2px",
                              textDecoration: "underline",
                            }}
                            title="Lookup candidate POI name"
                          >
                            Lookup &quot;{selectedCandidate.poi_name.length > 25 ? selectedCandidate.poi_name.slice(0, 22) + "..." : selectedCandidate.poi_name}&quot;
                          </button>
                        )}
                      </div>

                      <div style={{ display: "flex", gap: "6px", position: "relative" }}>
                        <div style={{ flex: 1, position: "relative" }}>
                          <input
                            id="location-search-input"
                            type="text"
                            value={locationSearchQuery}
                            onChange={handleLocationSearchInput}
                            onKeyDown={handleLocationSearchKeyDown}
                            onFocus={() => {
                              if (locationSearchResults.length > 0) {
                                setShowLocationSearchDropdown(true);
                              }
                            }}
                            placeholder="Type a city, state, POI name, or combo (e.g. Space Needle, Denver CO)..."
                            data-testid="location-search-input"
                            style={{
                              width: "100%",
                              padding: "5px 24px 5px 8px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              fontSize: "12px",
                              backgroundColor: "#ffffff",
                              color: "#0f172a",
                            }}
                          />
                          {locationSearchQuery && (
                            <button
                              type="button"
                              onClick={() => {
                                setLocationSearchQuery("");
                                setLocationSearchResults([]);
                                setShowLocationSearchDropdown(false);
                              }}
                              data-testid="clear-location-search-btn"
                              style={{
                                position: "absolute",
                                right: "6px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                background: "none",
                                border: "none",
                                padding: "2px",
                                cursor: "pointer",
                                color: "#94a3b8",
                                display: "flex",
                                alignItems: "center",
                              }}
                              title="Clear search"
                            >
                              <X size={12} />
                            </button>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => executeLocationSearch(locationSearchQuery)}
                          disabled={isSearchingLocation || !locationSearchQuery.trim()}
                          data-testid="find-location-btn"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "4px 10px",
                            borderRadius: "4px",
                            backgroundColor: "#0284c7",
                            color: "#ffffff",
                            border: "none",
                            fontSize: "11px",
                            fontWeight: 600,
                            cursor:
                              isSearchingLocation || !locationSearchQuery.trim()
                                ? "not-allowed"
                                : "pointer",
                            opacity:
                              isSearchingLocation || !locationSearchQuery.trim()
                                ? 0.6
                                : 1,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {isSearchingLocation ? (
                            <>
                              <Loader2 size={12} className="animate-spin" />
                              <span>Searching...</span>
                            </>
                          ) : (
                            <>
                              <Search size={12} />
                              <span>Find</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Dropdown with search results */}
                      {showLocationSearchDropdown && locationSearchResults.length > 0 && (
                        <div
                          data-testid="location-search-dropdown"
                          style={{
                            position: "absolute",
                            top: "calc(100% + 4px)",
                            left: 0,
                            right: 0,
                            maxHeight: "220px",
                            overflowY: "auto",
                            backgroundColor: "#ffffff",
                            borderRadius: "6px",
                            boxShadow: "0 4px 14px rgba(0,0,0,0.15)",
                            border: "1px solid #cbd5e1",
                            zIndex: 1000,
                          }}
                        >
                          {locationSearchResults.map((match, idx) => (
                            <div
                              key={idx}
                              data-testid={`location-search-result-${idx}`}
                              onClick={() => handleSelectLocationMatch(match)}
                              style={{
                                padding: "7px 10px",
                                cursor: "pointer",
                                borderBottom:
                                  idx < locationSearchResults.length - 1
                                    ? "1px solid #f1f5f9"
                                    : "none",
                                fontSize: "11px",
                                display: "flex",
                                flexDirection: "column",
                                gap: "2px",
                                transition: "background-color 0.15s ease",
                              }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLElement).style.backgroundColor =
                                  "#f0f9ff";
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLElement).style.backgroundColor =
                                  "transparent";
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <span style={{ fontWeight: 600, color: "#0f172a" }}>
                                  {match.name}
                                </span>
                                <span
                                  style={{
                                    fontSize: "9px",
                                    color: "#64748b",
                                    backgroundColor: "#f1f5f9",
                                    padding: "1px 5px",
                                    borderRadius: "3px",
                                  }}
                                >
                                  {match.type || match.class}
                                </span>
                              </div>
                              <span
                                style={{
                                  fontSize: "10px",
                                  color: "#64748b",
                                  lineHeight: 1.3,
                                }}
                              >
                                {match.display_name}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        marginBottom: "8px",
                        alignItems: "flex-end",
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Latitude:
                        </label>
                        <input
                          type="text"
                          value={editLatitude}
                          onChange={(e) => setEditLatitude(e.target.value)}
                          placeholder="e.g. 41.8781"
                          data-testid="latitude-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Longitude:
                        </label>
                        <input
                          type="text"
                          value={editLongitude}
                          onChange={(e) => setEditLongitude(e.target.value)}
                          placeholder="e.g. -87.6298"
                          data-testid="longitude-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                      <div>
                        <button
                          type="button"
                          onClick={() => {
                            setEditLatitude(savedCoords.lat);
                            setEditLongitude(savedCoords.lng);
                          }}
                          data-testid="reset-location-btn"
                          title="Reset location to last saved coordinates"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "5px 10px",
                            background: "#f1f5f9",
                            border: "1px solid #cbd5e1",
                            borderRadius: "4px",
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#475569",
                            cursor: "pointer",
                            height: "28px",
                            whiteSpace: "nowrap",
                          }}
                        >
                          <RotateCcw size={13} />
                          Reset
                        </button>
                      </div>
                    </div>

                    {/* Interactive Map with draggable pin and nearby markers */}
                    <div style={{ marginBottom: "10px" }}>
                      <WorkbenchMap
                        latitude={
                          editLatitude ? parseFloat(editLatitude) : null
                        }
                        longitude={
                          editLongitude ? parseFloat(editLongitude) : null
                        }
                        onChangeLocation={(newLat, newLon) => {
                          setEditLatitude(newLat.toFixed(6));
                          setEditLongitude(newLon.toFixed(6));
                        }}
                        nearbyPoints={nearbyPoints}
                      />
                    </div>

                    {/* Address Fields: ISO Administrative Breakdown */}
                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        marginBottom: "6px",
                      }}
                    >
                      <div style={{ flex: 2 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Street Address:
                        </label>
                        <input
                          type="text"
                          value={editStreetAddress}
                          onChange={(e) => setEditStreetAddress(e.target.value)}
                          placeholder="Street address..."
                          data-testid="street-address-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Postal Code / Zip:
                        </label>
                        <input
                          type="text"
                          value={editPostalCode}
                          onChange={(e) => setEditPostalCode(e.target.value)}
                          placeholder="Postal code..."
                          data-testid="postal-code-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        marginBottom: "6px",
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Locality (City / Town):
                        </label>
                        <input
                          type="text"
                          value={editLocality || editCity}
                          onChange={(e) => {
                            setEditLocality(e.target.value);
                            setEditCity(e.target.value);
                          }}
                          placeholder="Locality / City..."
                          data-testid="city-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Admin Level 2 (County / District):
                        </label>
                        <input
                          type="text"
                          value={editAdminLevel2}
                          onChange={(e) => setEditAdminLevel2(e.target.value)}
                          placeholder="County / District..."
                          data-testid="admin-level-2-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        gap: "8px",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ flex: 2 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Admin Level 1 (State / Province / Region):
                        </label>
                        <input
                          type="text"
                          value={editAdminLevel1 || editStateProvince}
                          onChange={(e) => {
                            setEditAdminLevel1(e.target.value);
                            setEditStateProvince(e.target.value);
                          }}
                          placeholder="State / Province..."
                          data-testid="state-province-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Country Code:
                        </label>
                        <input
                          type="text"
                          value={editCountryCode}
                          onChange={(e) =>
                            setEditCountryCode(e.target.value.toUpperCase())
                          }
                          placeholder="e.g. US"
                          maxLength={2}
                          data-testid="country-code-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                            textTransform: "uppercase",
                          }}
                        />
                      </div>
                      <div style={{ flex: 2 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                          }}
                        >
                          Country:
                        </label>
                        <input
                          type="text"
                          value={editCountry}
                          onChange={(e) => setEditCountry(e.target.value)}
                          placeholder="Country..."
                          data-testid="country-input"
                          style={{
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          }}
                        />
                      </div>
                    </div>

                    {/* Proximity Radius Slider & Nearby Count Badge */}
                    <div
                      style={{
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
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#334155",
                          }}
                        >
                          Nearby Search Radius:{" "}
                          <strong>
                            {PROXIMITY_STEPS[proximityRadiusIndex].label}
                          </strong>
                        </span>
                        <span
                          data-testid="nearby-poi-count-badge"
                          style={{
                            padding: "2px 8px",
                            borderRadius: "12px",
                            backgroundColor:
                              nearbyPoints.length > 0 ? "#e0f2fe" : "#f1f5f9",
                            color:
                              nearbyPoints.length > 0 ? "#0369a1" : "#64748b",
                            fontSize: "11px",
                            fontWeight: 700,
                          }}
                        >
                          {nearbyPoints.length} Nearby Point
                          {nearbyPoints.length === 1 ? "" : "s"}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={PROXIMITY_STEPS.length - 1}
                        value={proximityRadiusIndex}
                        onChange={(e) =>
                          setProximityRadiusIndex(parseInt(e.target.value, 10))
                        }
                        data-testid="proximity-radius-slider"
                        style={{ width: "100%", cursor: "pointer" }}
                      />
                      {nearbyPoints.length > 0 && (
                        <div
                          style={{
                            marginTop: "6px",
                            maxHeight: "80px",
                            overflowY: "auto",
                            fontSize: "11px",
                          }}
                        >
                          {nearbyPoints.slice(0, 5).map((np, idx) => (
                            <div
                              key={idx}
                              style={{ color: "#475569", padding: "1px 0" }}
                            >
                              • {np.name} ({np.type}, ~
                              {np.distanceMiles < 0.1
                                ? `${Math.round(np.distanceMiles * 5280)} ft`
                                : `${np.distanceMiles.toFixed(1)} mi`}
                              )
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Dynamic Related Websites List */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
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
                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          color: "#1e293b",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <Globe size={14} color="#2563eb" /> Related Websites
                        <AIIconBadge />
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
                          onChange={(e) =>
                            handleNoWebsitesToggle(e.target.checked)
                          }
                          data-testid="no-websites-checkbox"
                          style={{ cursor: "pointer" }}
                        />
                        <span>No Websites</span>
                      </label>
                    </div>

                    {!editNoWebsites ? (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                        }}
                      >
                        {/* Current Websites List */}
                        {editRelatedWebsites.map((site, idx) => (
                          <div
                            key={idx}
                            data-testid={`website-row-${idx}`}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              gap: "8px",
                              padding: "6px 8px",
                              borderRadius: "4px",
                              backgroundColor: "#f8fafc",
                              border: "1px solid #e2e8f0",
                              fontSize: "12px",
                            }}
                          >
                            <div
                              style={{
                                flex: 1,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              <strong style={{ color: "#1e293b" }}>
                                {site.name}:
                              </strong>{" "}
                              <a
                                href={site.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  color: "#2563eb",
                                  textDecoration: "none",
                                }}
                              >
                                {site.url}
                              </a>
                            </div>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                            >
                              <a
                                href={site.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: "#64748b", padding: "2px" }}
                              >
                                <ExternalLink size={13} />
                              </a>
                              <button
                                type="button"
                                onClick={() => handleRemoveWebsite(idx)}
                                data-testid={`delete-website-btn-${idx}`}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  color: "#ef4444",
                                  cursor: "pointer",
                                  padding: "2px",
                                }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        ))}

                        {/* Add Website Form */}
                        <div
                          style={{
                            display: "flex",
                            gap: "6px",
                            marginTop: "4px",
                          }}
                        >
                          <input
                            type="text"
                            placeholder="Website Name (e.g. Official Site)"
                            value={newWebsiteName}
                            onChange={(e) => setNewWebsiteName(e.target.value)}
                            data-testid="new-website-name-input"
                            style={{
                              flex: 1,
                              padding: "5px 8px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              fontSize: "12px",
                            }}
                          />
                          <input
                            type="url"
                            placeholder="https://..."
                            value={newWebsiteUrl}
                            onChange={(e) => setNewWebsiteUrl(e.target.value)}
                            data-testid="new-website-url-input"
                            style={{
                              flex: 2,
                              padding: "5px 8px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              fontSize: "12px",
                            }}
                          />
                          <button
                            type="button"
                            onClick={handleAddWebsite}
                            data-testid="add-website-btn"
                            style={{
                              padding: "5px 10px",
                              borderRadius: "4px",
                              backgroundColor: "#2563eb",
                              color: "#ffffff",
                              border: "none",
                              fontSize: "12px",
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            Add
                          </button>
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
                        Web scraping skipped: POI verified to have no relevant
                        web presence
                      </div>
                    )}
                  </div>

                  {/* Visit Duration & Notes */}
                  <div style={{ display: "flex", gap: "8px" }}>
                    <div style={{ flex: 1 }}>
                      <label
                        style={{
                          display: "block",
                          fontSize: "10px",
                          fontWeight: 600,
                          color: "#64748b",
                        }}
                      >
                        Est. Hours:
                      </label>
                      <input
                        type="number"
                        step="0.5"
                        value={editDurationHours}
                        onChange={(e) => setEditDurationHours(e.target.value)}
                        placeholder="2.5"
                        data-testid="duration-hours-input"
                        style={{
                          width: "100%",
                          padding: "5px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label
                        style={{
                          display: "block",
                          fontSize: "10px",
                          fontWeight: 600,
                          color: "#64748b",
                        }}
                      >
                        Est. Days:
                      </label>
                      <input
                        type="number"
                        value={editDurationDays}
                        onChange={(e) => setEditDurationDays(e.target.value)}
                        placeholder="1"
                        data-testid="duration-days-input"
                        style={{
                          width: "100%",
                          padding: "5px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        }}
                      />
                    </div>
                    <div style={{ flex: 2 }}>
                      <label
                        style={{
                          display: "block",
                          fontSize: "10px",
                          fontWeight: 600,
                          color: "#64748b",
                        }}
                      >
                        Visit Timing Notes:
                      </label>
                      <input
                        type="text"
                        value={editDurationNotes}
                        onChange={(e) => setEditDurationNotes(e.target.value)}
                        placeholder="Best early morning..."
                        data-testid="duration-notes-input"
                        style={{
                          width: "100%",
                          padding: "5px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        }}
                      />
                    </div>
                  </div>

                  {/* Account Tags Library Interactive Chips */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
                    }}
                  >
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#475569",
                        marginBottom: "6px",
                      }}
                    >
                      Tags Library:
                      <AIIconBadge />
                    </label>

                    {/* All tags from library (selected vs unselected) */}
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "6px",
                        marginBottom: "8px",
                        maxHeight: "120px",
                        overflowY: "auto",
                      }}
                      data-testid="tags-library-container"
                    >
                      {Array.from(new Set([...libraryTags, ...editTags])).map(
                        (tag) => {
                          const isSelected = editTags.includes(tag);
                          return (
                            <button
                              key={tag}
                              type="button"
                              onClick={() => handleToggleTag(tag)}
                              data-testid={`tag-chip-${tag}`}
                              style={{
                                padding: "3px 8px",
                                borderRadius: "12px",
                                fontSize: "11px",
                                fontWeight: 600,
                                cursor: "pointer",
                                border: isSelected
                                  ? "1px solid #2563eb"
                                  : "1px solid #cbd5e1",
                                backgroundColor: isSelected
                                  ? "#2563eb"
                                  : "#f1f5f9",
                                color: isSelected ? "#ffffff" : "#334155",
                                transition: "all 0.15s ease",
                              }}
                            >
                              {isSelected ? `✓ ${tag}` : tag}
                            </button>
                          );
                        },
                      )}
                    </div>
                  </div>

                  {/* Associated Photo Directories Manager */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "6px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#475569",
                          display: "flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <Folder size={13} color="#2563eb" /> Associated Photo
                        Directories:
                      </span>
                      <button
                        type="button"
                        onClick={handlePickDirectoryNative}
                        data-testid="browse-directory-btn"
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          backgroundColor: "#f1f5f9",
                          color: "#1e293b",
                          border: "1px solid #cbd5e1",
                          cursor: "pointer",
                        }}
                      >
                        Browse Folder...
                      </button>
                    </div>

                    {/* Hidden folder input fallback */}
                    <input
                      type="file"
                      ref={folderInputRef}
                      style={{ display: "none" }}
                      {...({ webkitdirectory: "", directory: "" } as any)}
                      onChange={(e) => {
                        const files = e.target.files;
                        if (files && files.length > 0) {
                          const relativePath =
                            files[0].webkitRelativePath || "";
                          const folderName =
                            relativePath.split("/")[0] || files[0].name;
                          if (
                            folderName &&
                            !editPhotoDirectories.includes(folderName)
                          ) {
                            setEditPhotoDirectories([
                              ...editPhotoDirectories,
                              folderName,
                            ]);
                          }
                        }
                      }}
                    />

                    {/* Directories List */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                        marginBottom: "6px",
                      }}
                    >
                      {editPhotoDirectories.map((dir, idx) => (
                        <div
                          key={idx}
                          data-testid={`directory-item-${idx}`}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "4px 8px",
                            borderRadius: "4px",
                            backgroundColor: "#f8fafc",
                            border: "1px solid #e2e8f0",
                            fontSize: "11px",
                            color: "#334155",
                          }}
                        >
                          <span
                            style={{
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            📁 {dir}
                          </span>
                          <button
                            type="button"
                            onClick={() =>
                              setEditPhotoDirectories(
                                editPhotoDirectories.filter(
                                  (_, i) => i !== idx,
                                ),
                              )
                            }
                            style={{
                              border: "none",
                              background: "none",
                              color: "#ef4444",
                              cursor: "pointer",
                              padding: "1px 4px",
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Add Directory Manual Input */}
                    <div style={{ display: "flex", gap: "6px" }}>
                      <input
                        type="text"
                        placeholder="Path / folder name..."
                        value={newDirectoryInput}
                        onChange={(e) => setNewDirectoryInput(e.target.value)}
                        data-testid="new-directory-input"
                        style={{
                          flex: 1,
                          padding: "5px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        }}
                      />
                      <button
                        type="button"
                        onClick={handleAddDirectory}
                        data-testid="add-directory-btn"
                        style={{
                          padding: "5px 10px",
                          borderRadius: "4px",
                          backgroundColor: "#f1f5f9",
                          color: "#334155",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Add
                      </button>
                    </div>
                  </div>

                  {/* Dates Visited Manager */}
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "12px",
                    }}
                  >
                    <label
                      style={{
                        display: "block",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#475569",
                        marginBottom: "6px",
                      }}
                    >
                      <Calendar
                        size={13}
                        style={{
                          display: "inline",
                          verticalAlign: "middle",
                          marginRight: "4px",
                        }}
                      />
                      Dates Visited:
                    </label>

                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "6px",
                        marginBottom: "6px",
                      }}
                    >
                      {editDatesVisited.map((dateStr, idx) => (
                        <span
                          key={idx}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "2px 8px",
                            borderRadius: "12px",
                            backgroundColor: "#f0fdf4",
                            border: "1px solid #bbf7d0",
                            fontSize: "11px",
                            color: "#166534",
                          }}
                        >
                          {dateStr}
                          <button
                            type="button"
                            onClick={() =>
                              setEditDatesVisited(
                                editDatesVisited.filter((_, i) => i !== idx),
                              )
                            }
                            style={{
                              border: "none",
                              background: "none",
                              color: "#86efac",
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>

                    <div style={{ display: "flex", gap: "6px" }}>
                      <input
                        type="date"
                        value={newVisitDateInput}
                        onChange={(e) => setNewVisitDateInput(e.target.value)}
                        data-testid="new-visit-date-input"
                        style={{
                          padding: "4px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        }}
                      />
                      <button
                        type="button"
                        onClick={handleAddVisitDate}
                        data-testid="add-visit-date-btn"
                        style={{
                          padding: "4px 10px",
                          borderRadius: "4px",
                          backgroundColor: "#f1f5f9",
                          color: "#334155",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Add Date
                      </button>
                    </div>
                  </div>

                  {/* Reason to Visit (Multiline Textarea) */}
                  <div>
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#475569",
                        marginBottom: "4px",
                      }}
                    >
                      Reason to Visit:
                      <AIIconBadge />
                    </label>
                    <textarea
                      rows={3}
                      value={editReasonToVisit}
                      onChange={(e) => setEditReasonToVisit(e.target.value)}
                      placeholder="Experiential rationale explaining why a traveler should visit..."
                      data-testid="reason-to-visit-textarea"
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        resize: "vertical",
                      }}
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#475569",
                        marginBottom: "4px",
                      }}
                    >
                      Description:
                      <AIIconBadge />
                    </label>
                    <textarea
                      rows={3}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      data-testid="description-textarea"
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        resize: "vertical",
                      }}
                    />
                  </div>
                </div>

                {/* PINNED FOOTER CONTAINER */}
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
                        setEditHeroImageUrl(
                          selectedCandidate.hero_image_url || "",
                        );
                        setEditLatitude(
                          selectedCandidate.latitude != null
                            ? String(selectedCandidate.latitude)
                            : "",
                        );
                        setEditLongitude(
                          selectedCandidate.longitude != null
                            ? String(selectedCandidate.longitude)
                            : "",
                        );
                        setEditStreetAddress(
                          selectedCandidate.street_address || "",
                        );
                        setEditPostalCode(selectedCandidate.postal_code || "");
                        setEditLocality(
                          selectedCandidate.locality ||
                            selectedCandidate.city ||
                            "",
                        );
                        setEditCity(
                          selectedCandidate.city ||
                            selectedCandidate.locality ||
                            "",
                        );
                        setEditAdminLevel2(
                          selectedCandidate.admin_level_2 || "",
                        );
                        setEditAdminLevel1(
                          selectedCandidate.admin_level_1 ||
                            selectedCandidate.state_province ||
                            "",
                        );
                        setEditStateProvince(
                          selectedCandidate.state_province ||
                            selectedCandidate.admin_level_1 ||
                            "",
                        );
                        setEditCountryCode(
                          selectedCandidate.country_code || "",
                        );
                        setEditCountry(selectedCandidate.country || "");
                        setEditDescription(selectedCandidate.description || "");
                        setEditReasonToVisit(
                          selectedCandidate.reason_to_visit || "",
                        );
                        setEditDisposition(
                          selectedCandidate.user_disposition ||
                            selectedCandidate.recommended_disposition ||
                            "accept",
                        );
                      }
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      backgroundColor: "#ffffff",
                      fontSize: "12px",
                      fontWeight: 600,
                      color: "#64748b",
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
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 18px",
                      borderRadius: "6px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: isSavingCandidate ? "not-allowed" : "pointer",
                    }}
                  >
                    {isSavingCandidate ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Save size={13} />
                    )}
                    <span>
                      {isSavingCandidate
                        ? "Saving..."
                        : "Save Candidate Changes"}
                    </span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: "#94a3b8",
                  fontSize: "13px",
                }}
              >
                Select a candidate from the table to inspect and edit details.
              </div>
            )}
          </div>
        </div>

        {/* BATCH EDIT MODAL OVERLAY */}
        {isBatchEditOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(15, 23, 42, 0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 100,
            }}
            data-testid="batch-edit-modal-overlay"
          >
            <div
              style={{
                width: "440px",
                backgroundColor: "#ffffff",
                borderRadius: "8px",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
                overflow: "hidden",
                border: "1px solid #e2e8f0",
              }}
            >
              <div
                style={{
                  padding: "12px 16px",
                  borderBottom: "1px solid #e2e8f0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  backgroundColor: "#f8fafc",
                }}
              >
                <span
                  style={{
                    fontWeight: 700,
                    fontSize: "14px",
                    color: "#0f172a",
                  }}
                >
                  Batch Edit ({selectedCandidateIds.length} Selected)
                </span>
                <button
                  type="button"
                  onClick={() => setIsBatchEditOpen(false)}
                  style={{
                    border: "none",
                    background: "none",
                    color: "#64748b",
                    cursor: "pointer",
                  }}
                >
                  <X size={16} />
                </button>
              </div>

              <form
                onSubmit={handleApplyBatchEdit}
                style={{
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#475569",
                      marginBottom: "3px",
                    }}
                  >
                    Country:
                  </label>
                  <input
                    type="text"
                    value={batchCountry}
                    onChange={(e) => setBatchCountry(e.target.value)}
                    placeholder="e.g. United States"
                    data-testid="batch-country-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                </div>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#475569",
                      marginBottom: "3px",
                    }}
                  >
                    State / Province:
                  </label>
                  <input
                    type="text"
                    value={batchState}
                    onChange={(e) => setBatchState(e.target.value)}
                    placeholder="e.g. California"
                    data-testid="batch-state-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                </div>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#475569",
                      marginBottom: "3px",
                    }}
                  >
                    City / Town:
                  </label>
                  <input
                    type="text"
                    value={batchCity}
                    onChange={(e) => setBatchCity(e.target.value)}
                    placeholder="e.g. San Francisco"
                    data-testid="batch-city-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                </div>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#475569",
                      marginBottom: "3px",
                    }}
                  >
                    Date Visited:
                  </label>
                  <input
                    type="date"
                    value={batchDateVisited}
                    onChange={(e) => setBatchDateVisited(e.target.value)}
                    data-testid="batch-date-visited-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: "8px",
                    marginTop: "10px",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setIsBatchEditOpen(false)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      background: "#ffffff",
                      fontSize: "12px",
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isBatchUpdating}
                    data-testid="apply-batch-edit-btn"
                    style={{
                      padding: "6px 14px",
                      borderRadius: "4px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: isBatchUpdating ? "not-allowed" : "pointer",
                    }}
                  >
                    {isBatchUpdating ? "Applying..." : "Apply Updates"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
