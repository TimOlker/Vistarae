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
  forwardGeocode,
  extractCoordinatesFromUrl,
  type ForwardSearchResult,
  type ReverseGeocodeResponse,
} from "../../services/geocodeService";
import { useToast } from "../../context/ToastContext";
import {
  normalizeUrl,
  reconstructWebsitesList,
} from "../../utils/websiteInference";
import {
  parseGoogleMapsUrl,
  isGoogleMapsUrl,
  isGeohackUrl,
  parseGeohackUrl,
  isWebpageUrl,
  countryNameToIsoCode,
} from "../../utils/coordinates";
import * as csvExport from "../../utils/csvExport";
import { getDisplayCandidateCity } from "../../utils/candidateUtils";
import { WorkbenchMap, type NearbyPointMarker } from "./WorkbenchMap";
import {
  POINameRecommendationsModal,
  extractNameRecommendations,
} from "./POINameRecommendationsModal";

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
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
} from "lucide-react";

export interface ExistingPOIMarker {
  id: string;
  name: string;
  latitude?: number;
  longitude?: number;
  canonical_lat?: number;
  canonical_lng?: number;
  render_lat?: number;
  render_lng?: number;
  tags?: string[];
  address?: string;
  street_address?: string;
  city?: string;
  locality?: string;
  state?: string;
  admin_level_1?: string;
  admin_level_2?: string;
  state_province?: string;
  postal_code?: string;
  country?: string;
  country_code?: string;
  addresses?: any[];
  image_urls?: string[];
  hero_image_url?: string;
  visited_dates?: string[];
  dates_visited?: string[];
  photo_directory?: string;
  photo_directories?: string[];
  directory_paths?: string[];
  description?: string;
  reason_to_visit?: string;
  official_url?: string;
  wiki_url?: string;
  related_websites?: Array<{ name: string; url: string }>;
  recommended_duration_hours?: number | null;
  recommended_visit_days?: number | null;
  estimated_visit_time_notes?: string | null;
  [key: string]: any;
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
  | "complete"
  | "incomplete"
  | "missing_photo"
  | "missing_location"
  | "missing_websites";

export type PerspectiveMode = "POI" | "Location";

const SESSION_KEY_WORKBENCH_PERSPECTIVE = "vistarae_workbench_perspective";
const SESSION_KEY_WORKBENCH_DISPOSITIONS = "vistarae_workbench_dispositions";

interface WorkbenchDispositionOption {
  key: string;
  label: string;
}

const ALL_WORKBENCH_DISPOSITIONS: WorkbenchDispositionOption[] = [
  { key: "accept", label: "Accept (New POI)" },
  { key: "sublocation", label: "Sublocation" },
  { key: "in_batch_merge", label: "In-Batch Merge" },
  { key: "update_existing", label: "Update Existing POI" },
  { key: "existing", label: "Existing" },
  { key: "exclude", label: "Exclude" },
  { key: "ignore", label: "Ignore" },
];

const DEFAULT_WORKBENCH_DISPOSITIONS = ALL_WORKBENCH_DISPOSITIONS.map(
  (d) => d.key,
);

/**
 * Calculates which completeness criteria are missing for a staged candidate.
 */
function getCandidateMissingFields(cand: {
  hero_image_url?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  street_address?: string | null;
  official_url?: string | null;
  related_websites?: any[] | null;
  no_websites?: boolean | null;
}): string[] {
  const missing: string[] = [];
  const hasPhoto = Boolean(cand.hero_image_url && cand.hero_image_url.trim());
  if (!hasPhoto) missing.push("Photo");

  const hasCoords = cand.latitude != null && cand.longitude != null;
  if (!hasCoords) missing.push("Coordinates");

  const hasStreet = Boolean(cand.street_address && cand.street_address.trim());
  if (!hasStreet) missing.push("Street Address");

  const hasWebsites =
    Boolean(cand.official_url && cand.official_url.trim()) ||
    Boolean(cand.related_websites && cand.related_websites.length > 0) ||
    Boolean(cand.no_websites);
  if (!hasWebsites) missing.push("Websites");

  return missing;
}

function isCandidateComplete(cand: CandidateItem): boolean {
  return getCandidateMissingFields(cand).length === 0;
}

const PROXIMITY_STEPS = [
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

const cleanReasonToVisit = (raw?: string | null): string => {
  if (!raw) return "";
  let cleaned = raw.replace(/\*\*([^*]+)\*\*/g, "$1");
  cleaned = cleaned.replace(/__([^_]+)__/g, "$1");
  cleaned = cleaned.replace(/(?<!\w)\*([^*]+)\*(?!\w)/g, "$1");
  const lines = cleaned
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => l.replace(/^[\s•*+\-–—·]+\s*/, ""))
    .filter(Boolean)
    .map((l) => `- ${l}`);
  return lines.length > 0 ? lines.join("\n") + "\n" : "";
};

export const CSVImportWorkbenchModal: React.FC<
  CSVImportWorkbenchModalProps
> = ({ jobId, isOpen, onClose, onCommitComplete, existingPOIs = [] }) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  // POI Name Change Recommendations & Prompt States
  const [nameChangePrompt, setNameChangePrompt] = useState<{
    currentName: string;
    recommendedName: string;
  } | null>(null);
  const [showNameRecommendationsModal, setShowNameRecommendationsModal] =
    useState(false);
  const [hasAutoShownRecommendations, setHasAutoShownRecommendations] =
    useState(false);

  const nameRecommendationsCount = useMemo(
    () => extractNameRecommendations(candidates).length,
    [candidates],
  );

  const checkAndPromptNameChange = (
    recommendedName: string | null | undefined,
  ) => {
    if (!recommendedName) return;
    const rec = recommendedName.trim();
    const current = (editPoiName || selectedCandidate?.poi_name || "").trim();
    if (rec && current && rec.toLowerCase() !== current.toLowerCase()) {
      setNameChangePrompt({
        currentName: current,
        recommendedName: rec,
      });
    }
  };

  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSavingCandidate, setIsSavingCandidate] = useState(false);
  const [isEnrichingSingle, setIsEnrichingSingle] = useState(false);
  const [isEnrichingAll, setIsEnrichingAll] = useState(false);

  // Perspective Mode: "POI" (default) vs "Location", restored from session data
  const [perspective, setPerspective] = useState<PerspectiveMode>(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY_WORKBENCH_PERSPECTIVE);
      if (saved === "Location" || saved === "POI") {
        return saved;
      }
    } catch {
      // sessionStorage unavailable
    }
    return "POI";
  });

  // Save perspective to session data whenever updated
  useEffect(() => {
    try {
      sessionStorage.setItem(SESSION_KEY_WORKBENCH_PERSPECTIVE, perspective);
    } catch {
      // Ignore sessionStorage errors
    }
  }, [perspective]);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [completenessFilter, setCompletenessFilter] =
    useState<CompletenessFilter>("all");

  // Multi-select disposition filter, restored from session data (defaults to all)
  const [selectedDispositions, setSelectedDispositions] = useState<string[]>(
    () => {
      try {
        const saved = sessionStorage.getItem(
          SESSION_KEY_WORKBENCH_DISPOSITIONS,
        );
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            const validKeys = ALL_WORKBENCH_DISPOSITIONS.map((d) => d.key);
            const filtered = parsed.filter(
              (k) => typeof k === "string" && validKeys.includes(k),
            );
            return filtered;
          }
        }
      } catch {
        // sessionStorage unavailable
      }
      return DEFAULT_WORKBENCH_DISPOSITIONS;
    },
  );

  const [isDispositionDropdownOpen, setIsDispositionDropdownOpen] =
    useState(false);
  const dispositionDropdownRef = useRef<HTMLDivElement>(null);

  // Save selected dispositions to session data whenever updated
  useEffect(() => {
    try {
      sessionStorage.setItem(
        SESSION_KEY_WORKBENCH_DISPOSITIONS,
        JSON.stringify(selectedDispositions),
      );
    } catch {
      // Ignore sessionStorage errors
    }
  }, [selectedDispositions]);

  // Close disposition dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (
        dispositionDropdownRef.current &&
        !dispositionDropdownRef.current.contains(e.target as Node)
      ) {
        setIsDispositionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  const handleSelectAllDispositions = () => {
    setSelectedDispositions(DEFAULT_WORKBENCH_DISPOSITIONS);
  };

  const handleDeselectAllDispositions = () => {
    setSelectedDispositions([]);
  };

  const handleToggleDisposition = (key: string) => {
    setSelectedDispositions((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const dispositionButtonLabel = useMemo(() => {
    if (selectedDispositions.length === ALL_WORKBENCH_DISPOSITIONS.length) {
      return "All Dispositions";
    }
    if (selectedDispositions.length === 0) {
      return "0 Dispositions Selected";
    }
    if (selectedDispositions.length === 1) {
      const match = ALL_WORKBENCH_DISPOSITIONS.find(
        (d) => d.key === selectedDispositions[0],
      );
      return match ? match.label : "1 Disposition";
    }
    return `Dispositions (${selectedDispositions.length}/${ALL_WORKBENCH_DISPOSITIONS.length})`;
  }, [selectedDispositions]);

  const dispositionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const d of ALL_WORKBENCH_DISPOSITIONS) {
      counts[d.key] = 0;
    }
    for (const c of candidates) {
      const disp = (
        c.user_disposition ||
        c.recommended_disposition ||
        ""
      ).toLowerCase();
      if (counts[disp] !== undefined) {
        counts[disp] += 1;
      }
    }
    return counts;
  }, [candidates]);

  // Multi-select for Batch Editing
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>(
    [],
  );
  const [isBatchEditOpen, setIsBatchEditOpen] = useState(false);
  const [batchCountry, setBatchCountry] = useState("");
  const [batchState, setBatchState] = useState("");
  const [batchCity, setBatchCity] = useState("");
  const [batchDateVisited, setBatchDateVisited] = useState("");
  const [batchAddTag, setBatchAddTag] = useState("");
  const [batchRemoveTag, setBatchRemoveTag] = useState("");
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
  const [availableHeroImageUrls, setAvailableHeroImageUrls] = useState<
    string[]
  >([]);
  const [currentHeroImageIndex, setCurrentHeroImageIndex] = useState(0);
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
  const [editMatchedExistingPoiId, setEditMatchedExistingPoiId] =
    useState<string>("");
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
  const locationDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
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
      const pLat = p.latitude ?? p.canonical_lat ?? p.render_lat;
      const pLon = p.longitude ?? p.canonical_lng ?? p.render_lng;
      if (pLat == null || pLon == null) continue;
      const d = haversineMiles(lat, lon, pLat, pLon);
      if (d <= radius) {
        list.push({
          name: p.name,
          type: "DB POI",
          latitude: pLat,
          longitude: pLon,
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
        cDisp === "exclude" ||
        cDisp === "existing"
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
      const dispParam =
        selectedDispositions.length === ALL_WORKBENCH_DISPOSITIONS.length
          ? undefined
          : selectedDispositions.length === 0
            ? "none"
            : selectedDispositions.join(",");
      const res = await ingestApi.listStagingCandidates(jobId, {
        completeness: completenessFilter,
        disposition: dispParam,
        search: searchQuery.trim() || undefined,
      });
      setCandidates(res.candidates);
      if (res.candidates.length > 0) {
        const recs = extractNameRecommendations(res.candidates);
        if (recs.length > 0 && !hasAutoShownRecommendations) {
          setShowNameRecommendationsModal(true);
          setHasAutoShownRecommendations(true);
        }
      }
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
    selectedDispositions,
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

      const poiLower = (selectedCandidate.poi_name || "").toLowerCase();
      const isGreatWall =
        poiLower.includes("great wall") || poiLower.includes("长城");
      const isSummerPalace =
        poiLower.includes("summer palace") || poiLower.includes("颐和园");

      let rawStreet = selectedCandidate.street_address || "";
      let rawLocality =
        selectedCandidate.locality || selectedCandidate.city || "";
      let rawAdmin2 = selectedCandidate.admin_level_2 || "";
      let rawAdmin1 =
        selectedCandidate.admin_level_1 ||
        selectedCandidate.state_province ||
        "";
      let rawCountry = (selectedCandidate.country || "").trim();
      let rawCC = (selectedCandidate.country_code || "").trim().toUpperCase();

      const isChina =
        rawCountry === "China" ||
        rawCountry === "中国" ||
        rawCC === "CN" ||
        (selectedCandidate.country || "").toLowerCase() === "china";

      if (isChina) {
        rawCountry = "China";
        rawCC = "CN";

        const isChineseDistrict = (
          name: string | null | undefined,
        ): boolean => {
          if (!name) return false;
          const nl = name.trim().toLowerCase();
          return (
            nl.includes("district") ||
            nl.includes("subdistrict") ||
            nl === "pudong" ||
            nl === "pudong new area" ||
            (/[\u4e00-\u9fff]/.test(name) &&
              (name.includes("区") ||
                name.includes("街道") ||
                name.includes("旗")))
          );
        };

        if (isChineseDistrict(rawLocality)) {
          if (!rawAdmin2 || !isChineseDistrict(rawAdmin2)) {
            rawAdmin2 = rawLocality;
          }
          rawLocality = "";
        }

        const isHongKong =
          rawCountry?.toLowerCase() === "hong kong" ||
          rawCC === "HK" ||
          [
            "hong kong",
            "kowloon",
            "new territories",
            "hong kong island",
          ].includes(rawAdmin1.toLowerCase()) ||
          poiLower.includes("hong kong") ||
          rawLocality?.toLowerCase().includes("mong kok") ||
          rawLocality?.toLowerCase().includes("tsim sha tsui") ||
          rawLocality?.toLowerCase().includes("fife street");

        const isDirectMunicipality =
          rawAdmin1 === "Beijing" ||
          rawAdmin1 === "Shanghai" ||
          rawAdmin1 === "Tianjin" ||
          rawAdmin1 === "Chongqing" ||
          isGreatWall ||
          isSummerPalace ||
          poiLower.includes("jade buddha") ||
          poiLower.includes("bund");

        if (isHongKong) {
          rawAdmin1 = "Hong Kong";
          rawLocality = "Hong Kong";
          rawCountry = "China";
          rawCC = "CN";
          if (!rawAdmin2) {
            const rawGeo = (selectedCandidate?.raw_geocoding || {}) as Record<
              string,
              any
            >;
            const disp = String(rawGeo.display_name || "");
            const hkDistricts = [
              "Yau Tsim Mong",
              "Central and Western",
              "Wan Chai",
              "Eastern",
              "Southern",
              "Sham Shui Po",
              "Kowloon City",
              "Wong Tai Sin",
              "Kwun Tong",
              "Kwai Tsing",
              "Tsuen Wan",
              "Tuen Mun",
              "Yuen Long",
              "North",
              "Tai Po",
              "Sha Tin",
              "Sai Kung",
              "Islands",
            ];
            const dispLower = disp.toLowerCase();
            for (const d of hkDistricts) {
              if (dispLower.includes(d.toLowerCase())) {
                rawAdmin2 = `${d} District`;
                break;
              }
            }
            if (!rawAdmin2) {
              const checkStr = `${dispLower} ${selectedCandidate?.city || ""} ${
                selectedCandidate?.poi_name || ""
              }`.toLowerCase();
              if (
                /mong kok|tsim sha tsui|yau ma tei|jordan|fife street/.test(
                  checkStr,
                )
              ) {
                rawAdmin2 = "Yau Tsim Mong District";
              } else if (/central|admiralty|sheung wan/.test(checkStr)) {
                rawAdmin2 = "Central and Western District";
              } else if (/causeway bay|wan chai/.test(checkStr)) {
                rawAdmin2 = "Wan Chai District";
              }
            }
          }
        } else if (isDirectMunicipality) {
          if (!rawAdmin1 || isGreatWall || isSummerPalace) {
            rawAdmin1 =
              poiLower.includes("jade buddha") || poiLower.includes("bund")
                ? "Shanghai"
                : "Beijing";
          }
          rawLocality = rawAdmin1;
          if (isGreatWall) {
            if (!rawStreet || /[\u4e00-\u9fff]/.test(rawStreet))
              rawStreet = "Mutianyu Road";
            if (!rawAdmin2 || /[\u4e00-\u9fff]/.test(rawAdmin2))
              rawAdmin2 = "Huairou District";
          } else if (isSummerPalace) {
            if (
              !rawStreet ||
              rawStreet === "Road" ||
              rawStreet === "19 Road" ||
              /[\u4e00-\u9fff]/.test(rawStreet) ||
              (rawStreet.toLowerCase().includes("road") &&
                !rawStreet.toLowerCase().includes("xinjiangongmen"))
            ) {
              rawStreet = "19 Xinjiangongmen Road";
            }
            if (!rawAdmin2 || /[\u4e00-\u9fff]/.test(rawAdmin2))
              rawAdmin2 = "Haidian District";
          } else if (poiLower.includes("jade buddha")) {
            if (!rawAdmin2) rawAdmin2 = "Jing'an District";
          } else if (poiLower.includes("bund")) {
            if (!rawAdmin2) rawAdmin2 = "Huangpu District";
          } else if (poiLower.includes("pudong")) {
            if (!rawAdmin2) rawAdmin2 = "Pudong New Area";
          }
          if (!rawAdmin2 && selectedCandidate?.raw_geocoding) {
            const rawGeo = (selectedCandidate.raw_geocoding || {}) as Record<
              string,
              any
            >;
            const disp = String(rawGeo.display_name || "");
            if (disp) {
              const parts = disp
                .split(",")
                .map((p) => p.trim())
                .filter(Boolean);
              for (let i = parts.length - 1; i >= 0; i--) {
                if (
                  parts[i].toLowerCase().endsWith("district") ||
                  parts[i].endsWith("区")
                ) {
                  rawAdmin2 = parts[i];
                  break;
                }
              }
            }
          }
        } else {
          // Other Chinese provinces (Shaanxi, Xizang, Henan, Sichuan, Yunnan, etc.)
          const rawGeo = (selectedCandidate.raw_geocoding || {}) as Record<
            string,
            any
          >;
          const disp = String(rawGeo.display_name || "");
          if (disp) {
            const parts = disp
              .split(",")
              .map((p) => p.trim())
              .filter(Boolean);
            let admin1Idx = -1;
            for (let i = 0; i < parts.length; i++) {
              if (
                rawAdmin1 &&
                (rawAdmin1.toLowerCase() === parts[i].toLowerCase() ||
                  parts[i].toLowerCase().startsWith(rawAdmin1.toLowerCase()))
              ) {
                admin1Idx = i;
                break;
              }
            }
            if (admin1Idx > 0) {
              for (let i = admin1Idx - 1; i >= 0; i--) {
                const seg = parts[i];
                if (/^\d+$/.test(seg)) continue;
                if (isChineseDistrict(seg)) {
                  if (!rawAdmin2) rawAdmin2 = seg;
                  continue;
                }
                rawLocality = seg.replace(/\s+Prefecture$/, "");
                break;
              }
            }
          }
          if (!rawLocality) {
            if (
              poiLower.includes("wild goose") ||
              poiLower.includes("terra cotta") ||
              poiLower.includes("terracotta")
            ) {
              rawLocality = "Xi'an";
              if (!rawAdmin2)
                rawAdmin2 = poiLower.includes("wild goose")
                  ? "Yanta District"
                  : "Lintong District";
            } else if (
              poiLower.includes("jokhang") ||
              poiLower.includes("potala") ||
              poiLower.includes("sera")
            ) {
              rawLocality = "Lhasa";
              if (!rawAdmin2) rawAdmin2 = "Chengguan District";
            } else if (poiLower.includes("longmen")) {
              rawLocality = "Luoyang";
              if (!rawAdmin2) rawAdmin2 = "Luolong District";
            } else if (poiLower.includes("leshan")) {
              rawLocality = "Leshan";
              if (!rawAdmin2) rawAdmin2 = "Shizhong District";
            }
          }
        }

        if (rawAdmin2 === "怀柔区") rawAdmin2 = "Huairou District";
        if (rawAdmin2 === "海淀区") rawAdmin2 = "Haidian District";
        if (rawAdmin2 === "雁塔区") rawAdmin2 = "Yanta District";
        if (rawAdmin2 === "临潼区") rawAdmin2 = "Lintong District";
        if (rawAdmin2 === "城关区") rawAdmin2 = "Chengguan District";
        if (rawAdmin2 === "静安区") rawAdmin2 = "Jing'an District";
        if (rawAdmin2 === "洛龙区") rawAdmin2 = "Luolong District";
        if (rawAdmin2?.toLowerCase() === "pudong")
          rawAdmin2 = "Pudong New Area";
      } else if (rawCountry === "中国") {
        rawCountry = "China";
        rawCC = "CN";
      } else if (
        (!rawCC ||
          (rawCC === "US" &&
            rawCountry &&
            !["united states", "usa", "us"].includes(
              rawCountry.toLowerCase(),
            ))) &&
        rawCountry
      ) {
        const mapped = countryNameToIsoCode(rawCountry);
        if (mapped) {
          rawCC = mapped;
        }
      }

      setEditStreetAddress(rawStreet);
      setEditPostalCode(selectedCandidate.postal_code || "");
      setEditLocality(rawLocality);
      setEditCity(rawLocality);
      setEditAdminLevel2(rawAdmin2);
      setEditAdminLevel1(rawAdmin1);
      setEditStateProvince(rawAdmin1);
      setEditCountry(rawCountry);
      setEditCountryCode(rawCC);

      // Hero photos: accumulate all candidate images and default to the first found image
      const seenHeroKeys = new Set<string>();
      const allHeroImgs: string[] = [];
      const addHeroImg = (raw: string | null | undefined) => {
        if (!raw || typeof raw !== "string") return;
        const u = raw.trim();
        if (!u) return;
        let key = u.split("?")[0].toLowerCase();
        if (key.includes("/thumb/")) {
          const parts = key.split("/");
          if (parts.length >= 2) key = parts[parts.length - 2];
        } else {
          const parts = key.split("/");
          key = parts[parts.length - 1] || key;
        }
        if (!seenHeroKeys.has(key)) {
          seenHeroKeys.add(key);
          allHeroImgs.push(u);
        }
      };

      if (selectedCandidate.hero_image_url) {
        addHeroImg(selectedCandidate.hero_image_url);
      }
      if (Array.isArray(selectedCandidate.hero_image_urls)) {
        for (const u of selectedCandidate.hero_image_urls) {
          addHeroImg(u);
        }
      }
      setAvailableHeroImageUrls(allHeroImgs);
      const initialHero =
        allHeroImgs.length > 0
          ? allHeroImgs[0]
          : selectedCandidate.hero_image_url || "";
      setEditHeroImageUrl(initialHero);
      setCurrentHeroImageIndex(0);

      // Reconstruct dynamic websites list (excluding third-party map providers)
      const sites = reconstructWebsitesList(selectedCandidate);
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
      setEditReasonToVisit(
        cleanReasonToVisit(selectedCandidate.reason_to_visit),
      );
      setEditParentPoiId(selectedCandidate.parent_poi_id || "");
      setEditParentCandidateId(selectedCandidate.parent_candidate_id || "");
      setEditMergeTargetId(selectedCandidate.merge_target_id || "");
      setEditMatchedExistingPoiId(
        selectedCandidate.matched_existing_poi_id || "",
      );
      setEditDispositionJustification(
        selectedCandidate.disposition_justification || "",
      );
      setEditIsUserOverridden(Boolean(selectedCandidate.is_user_overridden));
    }
  }, [selectedCandidate]);

  // Active missing fields for currently selected candidate in detail editor
  const editorCandidateMissingFields = useMemo(() => {
    if (!selectedCandidate) return [];
    const lat =
      editLatitude && editLatitude.trim()
        ? parseFloat(editLatitude)
        : selectedCandidate.latitude;
    const lng =
      editLongitude && editLongitude.trim()
        ? parseFloat(editLongitude)
        : selectedCandidate.longitude;
    return getCandidateMissingFields({
      hero_image_url: editHeroImageUrl,
      latitude: lat,
      longitude: lng,
      street_address: editStreetAddress,
      official_url: selectedCandidate.official_url,
      related_websites: editRelatedWebsites,
      no_websites: editNoWebsites,
    });
  }, [
    selectedCandidate,
    editHeroImageUrl,
    editLatitude,
    editLongitude,
    editStreetAddress,
    editRelatedWebsites,
    editNoWebsites,
  ]);

  // Map of existing DB POIs by ID
  const dbPOIsMap = useMemo(() => {
    const map = new Map<string, ExistingPOIMarker>();
    for (const p of existingPOIs) {
      if (p.id) map.set(p.id, p);
    }
    return map;
  }, [existingPOIs]);

  // Associated target POI: either existing DB POI or another candidate in current batch
  const associatedTarget = useMemo(() => {
    if (!selectedCandidate) return null;
    const disp = (
      editDisposition ||
      selectedCandidate.recommended_disposition ||
      ""
    ).toLowerCase();
    const isAssociatedWithDb =
      editMatchedExistingPoiId ||
      selectedCandidate.matched_existing_poi_id ||
      ((disp === "update_existing" || disp === "existing") &&
        (editParentPoiId || selectedCandidate.parent_poi_id));

    if (isAssociatedWithDb) {
      const dbId =
        editMatchedExistingPoiId ||
        selectedCandidate.matched_existing_poi_id ||
        editParentPoiId ||
        selectedCandidate.parent_poi_id;
      if (dbId && dbPOIsMap.has(dbId)) {
        return { type: "db", data: dbPOIsMap.get(dbId)! };
      }
    }

    if (
      disp === "in_batch_merge" ||
      selectedCandidate.recommended_disposition === "in_batch_merge"
    ) {
      const targetId = editMergeTargetId || selectedCandidate.merge_target_id;
      if (targetId) {
        const targetCand = candidates.find((c) => c.id === targetId);
        if (targetCand) {
          return { type: "candidate", data: targetCand };
        }
      }
    }

    return null;
  }, [
    selectedCandidate,
    editDisposition,
    editMatchedExistingPoiId,
    editParentPoiId,
    editMergeTargetId,
    dbPOIsMap,
    candidates,
  ]);

  // Helper determining if an edited field will result in no change against associated target
  const isFieldNoChange = useCallback(
    (fieldName: string): boolean => {
      if (!associatedTarget) return false;
      const target = associatedTarget.data;
      if (!target) return false;

      const isBlank = (s: unknown) =>
        s == null || (typeof s === "string" && s.trim().length === 0);

      switch (fieldName) {
        case "poi_name": {
          if (isBlank(editPoiName)) return true;
          const targetName = target.name || target.poi_name || "";
          return (
            editPoiName.trim().toLowerCase() === targetName.trim().toLowerCase()
          );
        }
        case "hero_image_url": {
          if (isBlank(editHeroImageUrl)) return true;
          const targetHero =
            target.hero_image_url ||
            (target.image_urls && target.image_urls[0]) ||
            "";
          return editHeroImageUrl.trim() === targetHero.trim();
        }
        case "latitude": {
          if (isBlank(editLatitude)) return true;
          const candLat = parseFloat(editLatitude);
          if (isNaN(candLat)) return true;
          const targetLat =
            target.latitude ?? target.canonical_lat ?? target.render_lat;
          if (targetLat == null) return false;
          return Math.abs(candLat - Number(targetLat)) < 0.0001;
        }
        case "longitude": {
          if (isBlank(editLongitude)) return true;
          const candLon = parseFloat(editLongitude);
          if (isNaN(candLon)) return true;
          const targetLon =
            target.longitude ?? target.canonical_lng ?? target.render_lng;
          if (targetLon == null) return false;
          return Math.abs(candLon - Number(targetLon)) < 0.0001;
        }
        case "street_address": {
          if (isBlank(editStreetAddress)) return true;
          const targetStreet = target.street_address || target.address || "";
          return (
            editStreetAddress.trim().toLowerCase() ===
            targetStreet.trim().toLowerCase()
          );
        }
        case "postal_code": {
          if (isBlank(editPostalCode)) return true;
          const targetZip = target.postal_code || target.zip_code || "";
          return (
            editPostalCode.trim().toLowerCase() ===
            targetZip.trim().toLowerCase()
          );
        }
        case "city": {
          if (isBlank(editCity)) return true;
          const targetCity = target.city || target.locality || "";
          return (
            editCity.trim().toLowerCase() === targetCity.trim().toLowerCase()
          );
        }
        case "admin_level_2": {
          if (isBlank(editAdminLevel2)) return true;
          const targetAdmin2 = target.admin_level_2 || "";
          return (
            editAdminLevel2.trim().toLowerCase() ===
            targetAdmin2.trim().toLowerCase()
          );
        }
        case "state_province": {
          if (isBlank(editStateProvince)) return true;
          const targetState =
            target.state_province || target.state || target.admin_level_1 || "";
          return (
            editStateProvince.trim().toLowerCase() ===
            targetState.trim().toLowerCase()
          );
        }
        case "country_code": {
          if (isBlank(editCountryCode)) return true;
          const targetCountryCode = target.country_code || "";
          return (
            editCountryCode.trim().toUpperCase() ===
            targetCountryCode.trim().toUpperCase()
          );
        }
        case "country": {
          if (isBlank(editCountry)) return true;
          const targetCountry = target.country || "";
          return (
            editCountry.trim().toLowerCase() ===
            targetCountry.trim().toLowerCase()
          );
        }
        case "duration_hours": {
          if (isBlank(editDurationHours)) return true;
          const candHours = parseFloat(editDurationHours);
          if (isNaN(candHours)) return true;
          const targetHours = target.recommended_duration_hours;
          if (targetHours == null) return false;
          return Math.abs(candHours - Number(targetHours)) < 0.01;
        }
        case "duration_days": {
          if (isBlank(editDurationDays)) return true;
          const candDays = parseInt(editDurationDays, 10);
          if (isNaN(candDays)) return true;
          const targetDays = target.recommended_visit_days;
          if (targetDays == null) return false;
          return candDays === Number(targetDays);
        }
        case "duration_notes": {
          if (isBlank(editDurationNotes)) return true;
          const targetNotes = target.estimated_visit_time_notes || "";
          return (
            editDurationNotes.trim().toLowerCase() ===
            targetNotes.trim().toLowerCase()
          );
        }
        case "reason_to_visit": {
          if (isBlank(editReasonToVisit)) return true;
          const targetReason = target.reason_to_visit || "";
          return (
            cleanReasonToVisit(editReasonToVisit).trim().toLowerCase() ===
            cleanReasonToVisit(targetReason).trim().toLowerCase()
          );
        }
        case "description": {
          if (isBlank(editDescription)) return true;
          const targetDesc = target.description || "";
          return (
            editDescription.trim().toLowerCase() ===
            targetDesc.trim().toLowerCase()
          );
        }
        case "tags": {
          if (!editTags || editTags.length === 0) return true;
          const targetTags = new Set(
            (target.tags || []).map((t: string) => t.trim().toLowerCase()),
          );
          return editTags.every((t) => targetTags.has(t.trim().toLowerCase()));
        }
        case "dates_visited": {
          if (!editDatesVisited || editDatesVisited.length === 0) return true;
          const targetDates = new Set(
            (target.dates_visited || target.visited_dates || []).map(
              (d: string) => d.trim(),
            ),
          );
          return editDatesVisited.every((d) => targetDates.has(d.trim()));
        }
        case "photo_directories": {
          if (!editPhotoDirectories || editPhotoDirectories.length === 0)
            return true;
          const targetDirs = new Set(
            (
              target.photo_directories ||
              (target.photo_directory ? [target.photo_directory] : [])
            ).map((p: string) => p.trim()),
          );
          return editPhotoDirectories.every((p) => targetDirs.has(p.trim()));
        }
        case "related_websites": {
          if (!editRelatedWebsites || editRelatedWebsites.length === 0)
            return true;
          const targetWebsites = new Set(
            (target.related_websites || []).map((w: any) =>
              (typeof w === "string" ? w : w.url || "").trim().toLowerCase(),
            ),
          );
          return editRelatedWebsites.every((w) =>
            targetWebsites.has((w.url || "").trim().toLowerCase()),
          );
        }
        default:
          return false;
      }
    },
    [
      associatedTarget,
      editPoiName,
      editHeroImageUrl,
      editLatitude,
      editLongitude,
      editStreetAddress,
      editPostalCode,
      editCity,
      editAdminLevel2,
      editStateProvince,
      editCountryCode,
      editCountry,
      editDurationHours,
      editDurationDays,
      editDurationNotes,
      editReasonToVisit,
      editDescription,
      editTags,
      editDatesVisited,
      editPhotoDirectories,
      editRelatedWebsites,
    ],
  );

  const NO_CHANGE_BG = "#f0fdf4";
  const NO_CHANGE_BORDER = "#86efac";
  const CHANGE_DIFF_BG = "#fefce8";
  const CHANGE_DIFF_BORDER = "#fde047";

  const getFieldInputStyle = (
    fieldName: string,
    baseStyle: React.CSSProperties = {},
  ): React.CSSProperties => {
    if (!associatedTarget) {
      return baseStyle;
    }
    if (isFieldNoChange(fieldName)) {
      return {
        ...baseStyle,
        backgroundColor: NO_CHANGE_BG,
        border: `1px solid ${NO_CHANGE_BORDER}`,
      };
    }
    return {
      ...baseStyle,
      backgroundColor: CHANGE_DIFF_BG,
      border: `1px solid ${CHANGE_DIFF_BORDER}`,
    };
  };

  const getFieldCurrentValue = useCallback(
    (fieldName: string): string | null => {
      if (!associatedTarget) return null;
      const target = associatedTarget.data;
      if (!target) return null;

      switch (fieldName) {
        case "poi_name": {
          const v = target.name || target.poi_name;
          return v ? String(v).trim() : "None";
        }
        case "hero_image_url": {
          const v =
            target.hero_image_url ||
            (target.image_urls && target.image_urls[0]);
          return v ? String(v).trim() : "None";
        }
        case "latitude": {
          const v =
            target.latitude ?? target.canonical_lat ?? target.render_lat;
          return v != null ? String(v) : "None";
        }
        case "longitude": {
          const v =
            target.longitude ?? target.canonical_lng ?? target.render_lng;
          return v != null ? String(v) : "None";
        }
        case "street_address": {
          const v = target.street_address || target.address;
          return v ? String(v).trim() : "None";
        }
        case "postal_code": {
          const v = target.postal_code || target.zip_code;
          return v ? String(v).trim() : "None";
        }
        case "city": {
          const v = target.city || target.locality;
          return v ? String(v).trim() : "None";
        }
        case "admin_level_2": {
          const v = target.admin_level_2;
          return v ? String(v).trim() : "None";
        }
        case "state_province": {
          const v =
            target.state_province || target.state || target.admin_level_1;
          return v ? String(v).trim() : "None";
        }
        case "country_code": {
          const v = target.country_code;
          return v ? String(v).trim().toUpperCase() : "None";
        }
        case "country": {
          const v = target.country;
          return v ? String(v).trim() : "None";
        }
        case "duration_hours": {
          const v = target.recommended_duration_hours;
          return v != null ? `${v}h` : "None";
        }
        case "duration_days": {
          const v = target.recommended_visit_days;
          return v != null ? `${v}d` : "None";
        }
        case "duration_notes": {
          const v = target.estimated_visit_time_notes;
          return v ? String(v).trim() : "None";
        }
        case "reason_to_visit": {
          const v = target.reason_to_visit;
          return v ? String(v).trim() : "None";
        }
        case "description": {
          const v = target.description;
          return v ? String(v).trim() : "None";
        }
        case "tags": {
          const list = target.tags || [];
          return list.length > 0 ? list.join(", ") : "None";
        }
        case "photo_directories": {
          const list =
            target.photo_directories ||
            (target.photo_directory ? [target.photo_directory] : []);
          return list.length > 0 ? list.join(", ") : "None";
        }
        case "dates_visited": {
          const list = target.dates_visited || target.visited_dates || [];
          return list.length > 0 ? list.join(", ") : "None";
        }
        case "related_websites": {
          const list = target.related_websites || [];
          return list.length > 0
            ? list
                .map((w: any) =>
                  typeof w === "string" ? w : w.url || w.name || "",
                )
                .filter(Boolean)
                .join(", ")
            : "None";
        }
        default:
          return null;
      }
    },
    [associatedTarget],
  );

  const renderFieldLabelText = (
    baseLabel: string,
    fieldName: string,
  ): React.ReactNode => {
    if (associatedTarget && !isFieldNoChange(fieldName)) {
      const orig = getFieldCurrentValue(fieldName);
      if (orig) {
        const displayOrig = orig.length > 40 ? `${orig.slice(0, 37)}...` : orig;
        return (
          <span>
            {baseLabel}{" "}
            <span
              data-testid={`field-diff-current-value-${fieldName}`}
              style={{
                fontWeight: 600,
                fontSize: "10px",
                color: "#b45309",
              }}
            >
              (Current: {displayOrig})
            </span>
          </span>
        );
      }
    }
    return baseLabel;
  };

  // Sort & filter candidates in table
  const sortedCandidates = useMemo(() => {
    let list = [...candidates];
    if (selectedDispositions.length < ALL_WORKBENCH_DISPOSITIONS.length) {
      list = list.filter((c) => {
        const d = (
          c.user_disposition ||
          c.recommended_disposition ||
          ""
        ).toLowerCase();
        return selectedDispositions.includes(d);
      });
    }
    if (completenessFilter === "complete") {
      list = list.filter(isCandidateComplete);
    } else if (completenessFilter === "incomplete") {
      list = list.filter((c) => !isCandidateComplete(c));
    }

    return list.sort((a, b) => {
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
  }, [
    candidates,
    selectedDispositions,
    completenessFilter,
    sortField,
    sortAsc,
    perspective,
  ]);

  // Keep selected candidate synced with visible candidate list
  useEffect(() => {
    if (sortedCandidates.length > 0) {
      if (
        !selectedCandidateId ||
        !sortedCandidates.some((c) => c.id === selectedCandidateId)
      ) {
        setSelectedCandidateId(sortedCandidates[0].id);
      }
    } else {
      setSelectedCandidateId(null);
    }
  }, [sortedCandidates, selectedCandidateId]);

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
    if (
      sortedCandidates.length > 0 &&
      selectedCandidateIds.length === sortedCandidates.length
    ) {
      setSelectedCandidateIds([]);
    } else {
      setSelectedCandidateIds(sortedCandidates.map((c) => c.id));
    }
  };

  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedCandidateIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  // Single-candidate enrichment: "AI Enrich POI" (cached) or "Recalculate / Force Refresh" (bypasses cache)
  const handleEnrichSingle = async (forceRefresh: boolean = false) => {
    if (!jobId || !selectedCandidateId) return;
    setIsEnrichingSingle(true);
    try {
      // If user cleared reason_to_visit or description in the UI, persist that clearing before enrichment
      if (selectedCandidate) {
        const patch: Record<string, any> = {};
        if (!editReasonToVisit.trim() && selectedCandidate.reason_to_visit) {
          patch.reason_to_visit = null;
        }
        if (!editDescription.trim() && selectedCandidate.description) {
          patch.description = null;
        }
        if (Object.keys(patch).length > 0) {
          await ingestApi.updateStagingCandidate(
            jobId,
            selectedCandidateId,
            patch,
          );
        }
      }

      const enriched = await ingestApi.enrichSingleCandidate(
        jobId,
        selectedCandidateId,
        forceRefresh,
      );
      setCandidates((prev) =>
        prev.map((c) => (c.id === selectedCandidateId ? enriched : c)),
      );
      setEditReasonToVisit(cleanReasonToVisit(enriched.reason_to_visit));
      setEditDescription(enriched.description || "");
      if (enriched.recommended_duration_hours != null) {
        setEditDurationHours(String(enriched.recommended_duration_hours));
      }
      if (enriched.recommended_visit_days != null) {
        setEditDurationDays(String(enriched.recommended_visit_days));
      }
      if (enriched.estimated_visit_time_notes) {
        setEditDurationNotes(enriched.estimated_visit_time_notes);
      }
      const refreshedSites = reconstructWebsitesList(enriched);
      setEditRelatedWebsites(refreshedSites);
      setEditNoWebsites(Boolean(enriched.no_websites));
      if (enriched.hero_image_url) {
        setEditHeroImageUrl(enriched.hero_image_url);
      }
      showToast(
        forceRefresh
          ? `Recalculated & refreshed ${enriched.poi_name}!`
          : `Enriched ${enriched.poi_name}!`,
        "success",
      );
    } catch (err: any) {
      console.error("Enrichment failed:", err);
      const detail =
        err?.problem?.detail ||
        err?.message ||
        (forceRefresh
          ? "Failed to refresh POI details"
          : "Failed to enrich POI details");
      showToast(detail, "error");
    } finally {
      setIsEnrichingSingle(false);
    }
  };

  // Asynchronous Bulk Enrichment: "AI Enrich All"
  const handleEnrichAll = async (forceRefresh: boolean = false) => {
    if (!jobId) return;
    setIsEnrichingAll(true);
    try {
      const res = await ingestApi.enrichAllCandidates(jobId, forceRefresh);
      showToast(
        res.message ||
          (forceRefresh
            ? "Bulk recalculation queued in background"
            : "Bulk AI enrichment queued in background"),
        "info",
      );
      setTimeout(() => {
        loadCandidates();
        setIsEnrichingAll(false);
      }, 3000);
    } catch (err: any) {
      console.error("Batch enrichment failed:", err);
      const detail =
        err?.problem?.detail ||
        err?.message ||
        "Failed to launch batch enrichment";
      showToast(detail, "error");
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
    const url = normalizeUrl(newWebsiteUrl);
    const key = url.toLowerCase();
    if (
      !editRelatedWebsites.some(
        (w) => normalizeUrl(w.url).toLowerCase() === key,
      )
    ) {
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

  // Helper to apply reverse geocoding result across address fields
  // Ensures all unused fields are cleared and populated fields are set correctly
  const applyReverseGeocodeResult = (
    res: ReverseGeocodeResponse,
    poiContextName?: string,
  ) => {
    const rawGeo = (res.raw_geocoding || {}) as Record<string, any>;
    const addr = (rawGeo.address || {}) as Record<string, any>;
    const displayName = String(rawGeo.display_name || "");

    let street = res.street || "";
    let postal = res.postal_code || addr.postcode || "";
    let admin2 = res.admin_level_2 || addr.county || addr.district || "";
    let admin1 =
      res.admin_level_1 ||
      res.state_province ||
      addr.state ||
      addr.province ||
      addr.region ||
      "";
    let locality =
      res.locality ||
      res.city ||
      addr.city ||
      addr.town ||
      addr.municipality ||
      addr.village ||
      "";
    let countryCode = res.country_code
      ? res.country_code.toUpperCase()
      : addr.country_code
        ? String(addr.country_code).toUpperCase()
        : "";
    let country = res.country || addr.country || "";

    if (!countryCode && country) {
      const mapped = countryNameToIsoCode(country);
      if (mapped) countryCode = mapped;
    }

    const isIsoChina =
      typeof addr["ISO3166-2-lvl4"] === "string" &&
      addr["ISO3166-2-lvl4"].toUpperCase().startsWith("CN-");
    const isIsoHongKongOrMacau =
      (typeof addr["ISO3166-2-lvl3"] === "string" &&
        ["CN-HK", "CN-MO"].includes(addr["ISO3166-2-lvl3"].toUpperCase())) ||
      (typeof addr["ISO3166-2-lvl4"] === "string" &&
        ["CN-HK", "CN-MO"].includes(addr["ISO3166-2-lvl4"].toUpperCase()));

    // Resolve China direct-administered municipalities and provinces
    if (
      countryCode === "CN" ||
      country.toLowerCase() === "china" ||
      country === "中国" ||
      isIsoChina ||
      isIsoHongKongOrMacau
    ) {
      const poiLower = (
        poiContextName ||
        editPoiName ||
        selectedCandidate?.poi_name ||
        ""
      ).toLowerCase();
      const isBeijing =
        displayName.toLowerCase().includes("beijing") ||
        displayName.includes("北京") ||
        addr["ISO3166-2-lvl4"] === "CN-BJ" ||
        poiLower.includes("summer palace") ||
        poiLower.includes("great wall") ||
        admin2.toLowerCase().includes("haidian") ||
        admin2.includes("海淀");
      const isShanghai =
        displayName.toLowerCase().includes("shanghai") ||
        displayName.includes("上海") ||
        addr["ISO3166-2-lvl4"] === "CN-SH";
      const isTianjin =
        displayName.toLowerCase().includes("tianjin") ||
        displayName.includes("天津") ||
        addr["ISO3166-2-lvl4"] === "CN-TJ";
      const isChongqing =
        displayName.toLowerCase().includes("chongqing") ||
        displayName.includes("重庆") ||
        addr["ISO3166-2-lvl4"] === "CN-CQ";
      const isHongKong =
        displayName.toLowerCase().includes("hong kong") ||
        displayName.includes("香港") ||
        addr["ISO3166-2-lvl3"] === "CN-HK" ||
        addr["ISO3166-2-lvl4"] === "CN-HK" ||
        countryCode === "HK" ||
        country.toLowerCase() === "hong kong" ||
        poiLower.includes("hong kong") ||
        [
          "kowloon",
          "new territories",
          "hong kong island",
          "hong kong",
        ].includes(admin1.toLowerCase());
      const isMacau =
        displayName.toLowerCase().includes("macau") ||
        displayName.toLowerCase().includes("macao") ||
        displayName.includes("澳门") ||
        displayName.includes("澳門") ||
        addr["ISO3166-2-lvl3"] === "CN-MO" ||
        addr["ISO3166-2-lvl4"] === "CN-MO" ||
        countryCode === "MO" ||
        ["macau", "macao"].includes(admin1.toLowerCase());

      if (isHongKong) {
        locality = "Hong Kong";
        admin1 = "Hong Kong";
        country = "China";
        countryCode = "CN";
        const hkDistricts = [
          "Yau Tsim Mong",
          "Central and Western",
          "Wan Chai",
          "Eastern",
          "Southern",
          "Sham Shui Po",
          "Kowloon City",
          "Wong Tai Sin",
          "Kwun Tong",
          "Kwai Tsing",
          "Tsuen Wan",
          "Tuen Mun",
          "Yuen Long",
          "North",
          "Tai Po",
          "Sha Tin",
          "Sai Kung",
          "Islands",
        ];
        const dispLower = displayName.toLowerCase();
        for (const d of hkDistricts) {
          if (dispLower.includes(d.toLowerCase())) {
            admin2 = `${d} District`;
            break;
          }
        }
        if (!admin2) {
          if (
            /mong kok|tsim sha tsui|yau ma tei|jordan|fife street/.test(
              dispLower,
            ) ||
            /mong kok|tsim sha tsui/.test(poiLower)
          ) {
            admin2 = "Yau Tsim Mong District";
          } else if (/central|admiralty|sheung wan/.test(dispLower)) {
            admin2 = "Central and Western District";
          } else if (/causeway bay|wan chai/.test(dispLower)) {
            admin2 = "Wan Chai District";
          }
        }
      } else if (isMacau) {
        locality = "Macau";
        admin1 = "Macau";
        country = "China";
        countryCode = "CN";
      } else if (isBeijing) {
        if (
          !locality ||
          locality.includes("District") ||
          /[\u4e00-\u9fff]/.test(locality)
        ) {
          if (locality && locality.includes("District") && !admin2) {
            admin2 = locality;
          }
          locality = "Beijing";
        }
        if (!admin1 || /[\u4e00-\u9fff]/.test(admin1)) {
          admin1 = "Beijing";
        }
        if (!admin2 && addr.city && addr.city.includes("District")) {
          admin2 = addr.city;
        }
        if (poiLower.includes("summer palace") || poiLower.includes("颐和园")) {
          if (
            !street ||
            street === "Road" ||
            street === "19 Road" ||
            /[\u4e00-\u9fff]/.test(street) ||
            (street.toLowerCase().includes("road") &&
              !street.toLowerCase().includes("xinjiangongmen"))
          ) {
            street = "19 Xinjiangongmen Road";
          }
          if (!admin2 || /[\u4e00-\u9fff]/.test(admin2))
            admin2 = "Haidian District";
        } else if (
          poiLower.includes("great wall") ||
          poiLower.includes("长城")
        ) {
          if (!street || /[\u4e00-\u9fff]/.test(street)) {
            street = "Mutianyu Road";
          }
          if (!admin2 || /[\u4e00-\u9fff]/.test(admin2))
            admin2 = "Huairou District";
        }
        if (admin2 === "怀柔区") admin2 = "Huairou District";
        if (admin2 === "海淀区") admin2 = "Haidian District";
      } else if (isShanghai) {
        if (
          !locality ||
          locality.includes("District") ||
          /[\u4e00-\u9fff]/.test(locality)
        ) {
          if (locality && locality.includes("District") && !admin2) {
            admin2 = locality;
          }
          locality = "Shanghai";
        }
        if (!admin1 || /[\u4e00-\u9fff]/.test(admin1)) {
          admin1 = "Shanghai";
        }
        if (!admin2 && displayName) {
          const parts = displayName
            .split(",")
            .map((p) => p.trim())
            .filter(Boolean);
          for (let i = parts.length - 1; i >= 0; i--) {
            if (
              parts[i].toLowerCase().endsWith("district") ||
              parts[i].endsWith("区")
            ) {
              admin2 = parts[i];
              break;
            }
          }
        }
        if (!admin2) {
          if (poiLower.includes("bund")) admin2 = "Huangpu District";
          else if (poiLower.includes("jade buddha"))
            admin2 = "Jing'an District";
          else if (poiLower.includes("pudong")) admin2 = "Pudong New Area";
        }
      } else if (isTianjin) {
        if (
          !locality ||
          locality.includes("District") ||
          /[\u4e00-\u9fff]/.test(locality)
        ) {
          if (locality && locality.includes("District") && !admin2) {
            admin2 = locality;
          }
          locality = "Tianjin";
        }
        if (!admin1 || /[\u4e00-\u9fff]/.test(admin1)) {
          admin1 = "Tianjin";
        }
      } else if (isChongqing) {
        if (
          !locality ||
          locality.includes("District") ||
          /[\u4e00-\u9fff]/.test(locality)
        ) {
          if (locality && locality.includes("District") && !admin2) {
            admin2 = locality;
          }
          locality = "Chongqing";
        }
        if (!admin1 || /[\u4e00-\u9fff]/.test(admin1)) {
          admin1 = "Chongqing";
        }
      } else {
        const isChineseDistrict = (
          name: string | null | undefined,
        ): boolean => {
          if (!name) return false;
          const nl = name.trim().toLowerCase();
          return (
            nl.includes("district") ||
            nl.includes("subdistrict") ||
            nl === "pudong" ||
            nl === "pudong new area" ||
            (/[\u4e00-\u9fff]/.test(name) &&
              (name.includes("区") ||
                name.includes("街道") ||
                name.includes("旗")))
          );
        };

        if (isChineseDistrict(locality)) {
          if (!admin2 || !isChineseDistrict(admin2)) {
            admin2 = locality;
          }
          locality = "";
        }

        const parts = displayName
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean);
        let admin1Idx = -1;
        for (let i = 0; i < parts.length; i++) {
          if (
            admin1 &&
            (admin1.toLowerCase() === parts[i].toLowerCase() ||
              parts[i].toLowerCase().startsWith(admin1.toLowerCase()))
          ) {
            admin1Idx = i;
            break;
          }
        }

        if (admin1Idx > 0) {
          for (let i = admin1Idx - 1; i >= 0; i--) {
            const seg = parts[i];
            if (/^\d+$/.test(seg)) continue;
            if (isChineseDistrict(seg)) {
              if (!admin2) admin2 = seg;
              continue;
            }
            locality = seg.replace(/\s+Prefecture$/, "");
            break;
          }
        }

        if (!locality) {
          if (
            poiLower.includes("wild goose") ||
            poiLower.includes("terra cotta") ||
            poiLower.includes("terracotta")
          ) {
            locality = "Xi'an";
            if (!admin2)
              admin2 = poiLower.includes("wild goose")
                ? "Yanta District"
                : "Lintong District";
          } else if (
            poiLower.includes("jokhang") ||
            poiLower.includes("potala") ||
            poiLower.includes("sera")
          ) {
            locality = "Lhasa";
            if (!admin2) admin2 = "Chengguan District";
          } else if (poiLower.includes("longmen")) {
            locality = "Luoyang";
            if (!admin2) admin2 = "Luolong District";
          } else if (poiLower.includes("leshan")) {
            locality = "Leshan";
            if (!admin2) admin2 = "Shizhong District";
          }
        }
      }

      if (admin2 === "怀柔区") admin2 = "Huairou District";
      if (admin2 === "海淀区") admin2 = "Haidian District";
      if (admin2 === "雁塔区") admin2 = "Yanta District";
      if (admin2 === "临潼区") admin2 = "Lintong District";
      if (admin2 === "城关区") admin2 = "Chengguan District";
      if (admin2 === "静安区") admin2 = "Jing'an District";
      if (admin2 === "洛龙区") admin2 = "Luolong District";
      if (admin2?.toLowerCase() === "pudong") admin2 = "Pudong New Area";
    }

    // Explicitly update every field so unused fields are cleared and used fields are populated
    setEditStreetAddress(street);
    setEditPostalCode(postal);
    setEditLocality(locality);
    setEditCity(locality);
    setEditAdminLevel2(admin2);
    setEditAdminLevel1(admin1);
    setEditStateProvince(admin1);
    setEditCountryCode(countryCode);
    setEditCountry(country);
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
      applyReverseGeocodeResult(res, editPoiName);
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
    const matchName = match.name || match.display_name.split(",")[0];
    setLocationSearchQuery(matchName);
    const latStr = match.lat.toFixed(6);
    const lngStr = match.lng.toFixed(6);
    setEditLatitude(latStr);
    setEditLongitude(lngStr);

    setIsResyncingAddress(true);
    try {
      const res = await reverseGeocode(match.lat, match.lng);
      applyReverseGeocodeResult(res, matchName);
      showToast(`Location set to ${match.name}`, "success");
      checkAndPromptNameChange(matchName);
    } catch {
      showToast(`Location coordinates set to (${latStr}, ${lngStr})`, "info");
    } finally {
      setIsResyncingAddress(false);
    }
  };

  const executeLocationSearch = async (queryText: string) => {
    let q = queryText.trim();
    if (!q || q.length < 2) return;

    if (locationDebounceRef.current) {
      clearTimeout(locationDebounceRef.current);
    }

    // Detect if text contains a Google Maps URL
    if (isGoogleMapsUrl(q)) {
      const gmapsResult = parseGoogleMapsUrl(q);
      if (gmapsResult && !isNaN(gmapsResult.lat) && !isNaN(gmapsResult.lng)) {
        setIsSearchingLocation(true);
        setShowLocationSearchDropdown(false);
        if (gmapsResult.placeName) {
          setLocationSearchQuery(gmapsResult.placeName);
          checkAndPromptNameChange(gmapsResult.placeName);
        }
        const latStr = gmapsResult.lat.toFixed(6);
        const lngStr = gmapsResult.lng.toFixed(6);
        setEditLatitude(latStr);
        setEditLongitude(lngStr);

        setIsResyncingAddress(true);
        try {
          const res = await reverseGeocode(gmapsResult.lat, gmapsResult.lng);
          applyReverseGeocodeResult(res, gmapsResult.placeName);
          const label =
            gmapsResult.placeName ||
            res.locality ||
            res.city ||
            `${latStr}, ${lngStr}`;
          showToast(`Location set from Google Maps URL: ${label}`, "success");
        } catch {
          showToast(
            `Coordinates set to (${latStr}, ${lngStr}) from Google Maps URL`,
            "info",
          );
        } finally {
          setIsResyncingAddress(false);
          setIsSearchingLocation(false);
        }
        return;
      } else if (gmapsResult?.placeName) {
        // Fallback: Use extracted place name for text search
        q = gmapsResult.placeName;
        setLocationSearchQuery(q);
      } else {
        showToast(
          "Google Maps URL detected but coordinates could not be parsed",
          "error",
        );
        return;
      }
    }

    // Detect if text contains a GeoHack URL (e.g. Wikipedia coordinate links)
    if (isGeohackUrl(q)) {
      const ghResult = parseGeohackUrl(q);
      if (ghResult && !isNaN(ghResult.lat) && !isNaN(ghResult.lng)) {
        setIsSearchingLocation(true);
        setShowLocationSearchDropdown(false);
        if (ghResult.placeName) {
          setLocationSearchQuery(ghResult.placeName);
          checkAndPromptNameChange(ghResult.placeName);
        }
        const latStr = ghResult.lat.toFixed(6);
        const lngStr = ghResult.lng.toFixed(6);
        setEditLatitude(latStr);
        setEditLongitude(lngStr);

        setIsResyncingAddress(true);
        try {
          const res = await reverseGeocode(ghResult.lat, ghResult.lng);
          applyReverseGeocodeResult(res, ghResult.placeName);
          const label =
            ghResult.placeName ||
            res.locality ||
            res.city ||
            `${latStr}, ${lngStr}`;
          showToast(`Location set from GeoHack URL: ${label}`, "success");
        } catch {
          showToast(
            `Coordinates set to (${latStr}, ${lngStr}) from GeoHack URL`,
            "info",
          );
        } finally {
          setIsResyncingAddress(false);
          setIsSearchingLocation(false);
        }
        return;
      } else if (ghResult?.placeName) {
        q = ghResult.placeName;
        setLocationSearchQuery(q);
      } else {
        showToast(
          "GeoHack URL detected but coordinates could not be parsed",
          "error",
        );
        return;
      }
    }

    // Detect if text contains a webpage URL (e.g. Wikipedia, TripAdvisor, etc.)
    if (isWebpageUrl(q)) {
      setIsSearchingLocation(true);
      setShowLocationSearchDropdown(false);
      try {
        const res = await extractCoordinatesFromUrl(q);
        if (res.latitude != null && res.longitude != null) {
          const latStr = res.latitude.toFixed(6);
          const lngStr = res.longitude.toFixed(6);
          setEditLatitude(latStr);
          setEditLongitude(lngStr);
          if (res.place_name) {
            setLocationSearchQuery(res.place_name);
            checkAndPromptNameChange(res.place_name);
            if (!editPoiName) {
              setEditPoiName(res.place_name);
            }
          }
          applyReverseGeocodeResult(res as any, res.place_name || undefined);
          const label = res.place_name || res.city || `${latStr}, ${lngStr}`;
          showToast(`Location extracted from webpage: ${label}`, "success");
          return;
        } else if (res.place_name) {
          // Fallback to text search on extracted place name
          q = res.place_name;
          setLocationSearchQuery(q);
        } else {
          showToast(
            "Webpage detected but no coordinates could be found in page body",
            "error",
          );
          return;
        }
      } catch (err: any) {
        showToast(
          err.message || "Failed to extract coordinates from webpage",
          "error",
        );
        return;
      } finally {
        setIsSearchingLocation(false);
      }
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
        // Fallback to backend enhanced forward geocode (Wikipedia / Wikidata / Gemini cascade)
        try {
          const countryHint = editCountry?.trim() || undefined;
          const enhanced = await forwardGeocode(q, countryHint);
          if (enhanced.latitude != null && enhanced.longitude != null) {
            const latStr = enhanced.latitude.toFixed(6);
            const lngStr = enhanced.longitude.toFixed(6);
            setEditLatitude(latStr);
            setEditLongitude(lngStr);
            if (enhanced.resolved_name) {
              setLocationSearchQuery(enhanced.resolved_name);
              checkAndPromptNameChange(enhanced.resolved_name);
            }
            applyReverseGeocodeResult(
              enhanced as any,
              enhanced.resolved_name || undefined,
            );
            setShowLocationSearchDropdown(false);
            const label = enhanced.resolved_name
              ? `${enhanced.resolved_name} (from "${q}")`
              : enhanced.city || `${latStr}, ${lngStr}`;
            showToast(
              `Location resolved via enhanced search: ${label}`,
              "success",
            );
            return;
          }
        } catch (fwdErr) {
          console.warn("Enhanced location resolution failed:", fwdErr);
        }
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

    // Do not trigger live forward geocode if user is pasting/typing a URL (Google Maps, GeoHack, or webpage);
    // user will press "Find" to parse or extract coordinates
    if (isGoogleMapsUrl(val) || isGeohackUrl(val) || isWebpageUrl(val)) {
      setLocationSearchResults([]);
      setShowLocationSearchDropdown(false);
      return;
    }

    locationDebounceRef.current = setTimeout(async () => {
      setIsSearchingLocation(true);
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
        matched_existing_poi_id:
          editMatchedExistingPoiId ||
          selectedCandidate?.matched_existing_poi_id ||
          null,
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
        add_tag: batchAddTag.trim() || undefined,
        remove_tag: batchRemoveTag.trim() || undefined,
      });
      showToast(`Updated ${res.updated_count} candidates!`, "success");
      setIsBatchEditOpen(false);
      setSelectedCandidateIds([]);
      setBatchAddTag("");
      setBatchRemoveTag("");
      loadCandidates();
    } catch {
      showToast("Batch update failed", "error");
    } finally {
      setIsBatchUpdating(false);
    }
  };

  // Handler for applying accepted POI name recommendations
  const handleAcceptNameChanges = async (
    acceptedUpdates: Array<{ candidateId: string; newName: string }>,
  ) => {
    if (acceptedUpdates.length === 0) return;
    setIsSubmitting(true);
    try {
      for (const update of acceptedUpdates) {
        if (jobId) {
          await ingestApi.updateStagingCandidate(jobId, update.candidateId, {
            poi_name: update.newName,
          });
        }
      }
      setCandidates((prev) =>
        prev.map((c) => {
          const matching = acceptedUpdates.find((u) => u.candidateId === c.id);
          return matching ? { ...c, poi_name: matching.newName } : c;
        }),
      );
      if (selectedCandidateId) {
        const matching = acceptedUpdates.find(
          (u) => u.candidateId === selectedCandidateId,
        );
        if (matching) {
          setEditPoiName(matching.newName);
        }
      }
      showToast(
        `Successfully updated ${acceptedUpdates.length} POI name(s) to recommended values!`,
        "success",
      );
    } catch (err: any) {
      showToast(err?.message || "Failed to update some POI names", "error");
    } finally {
      setIsSubmitting(false);
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

  // CSV Export of current staged candidates (Full-Fidelity 017-export)
  const handleExportCSV = () => {
    if (candidates.length === 0) {
      showToast("No candidates available to export.", "warning");
      return;
    }

    try {
      // Flush active candidate detail editor state
      const activeEditorCandidate = selectedCandidateId
        ? {
            id: selectedCandidateId,
            candidate_id: selectedCandidateId,
            poi_name: editPoiName.trim(),
            user_disposition: editDisposition,
            latitude: editLatitude ? parseFloat(editLatitude) : null,
            longitude: editLongitude ? parseFloat(editLongitude) : null,
            street_address: editStreetAddress.trim() || null,
            postal_code: editPostalCode.trim() || null,
            locality: editLocality.trim() || null,
            city: editLocality.trim() || editCity.trim() || null,
            admin_level_2: editAdminLevel2.trim() || null,
            admin_level_1: editAdminLevel1.trim() || null,
            state_province:
              editStateProvince.trim() || editAdminLevel1.trim() || null,
            country: editCountry.trim() || null,
            country_code: editCountryCode.trim() || null,
            description: editDescription.trim() || null,
            reason_to_visit: editReasonToVisit.trim() || null,
            hero_image_url: editHeroImageUrl.trim() || null,
            official_url:
              editRelatedWebsites.find((w) =>
                w.name.toLowerCase().includes("official"),
              )?.url ||
              editRelatedWebsites[0]?.url ||
              null,
            wiki_url:
              editRelatedWebsites.find((w) =>
                w.url.toLowerCase().includes("wikipedia.org"),
              )?.url || null,
            related_websites: editRelatedWebsites,
            no_websites: editNoWebsites,
            tags: editTags,
            photo_directories: editPhotoDirectories,
            photo_directory: editPhotoDirectories[0] || null,
            dates_visited: editDatesVisited,
            recommended_duration_hours: editDurationHours
              ? parseFloat(editDurationHours)
              : null,
            recommended_visit_days: editDurationDays
              ? parseFloat(editDurationDays)
              : null,
            estimated_visit_time_notes: editDurationNotes.trim() || null,
            parent_poi_id: editParentPoiId.trim() || null,
            parent_candidate_id: editParentCandidateId.trim() || null,
            merge_target_id: editMergeTargetId.trim() || null,
            matched_existing_poi_id: editMatchedExistingPoiId.trim() || null,
            disposition_justification:
              editDispositionJustification.trim() || null,
            is_user_overridden: true,
          }
        : null;

      const result = csvExport.exportWorkbenchCandidatesToCsv(candidates, {
        jobId,
        selectedCandidateIds:
          selectedCandidateIds.length > 0
            ? new Set(selectedCandidateIds)
            : undefined,
        activeEditorCandidate,
        triggerDownload: true,
      });

      showToast(
        `Successfully exported ${result.exportedCount} candidate(s) to ${result.filename}`,
        "success",
      );
    } catch (err: any) {
      showToast(err?.message || "Failed to export candidates", "error");
    }
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
      closeOnBackdropClick={false}
      closeOnEscape={false}
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
              onClick={() => handleEnrichAll(false)}
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

            {/* POI Name Recommendations Button */}
            {nameRecommendationsCount > 0 && (
              <button
                type="button"
                onClick={() => setShowNameRecommendationsModal(true)}
                data-testid="open-name-recommendations-btn"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "6px 12px",
                  borderRadius: "6px",
                  backgroundColor: "#f0f9ff",
                  border: "1px solid #bae6fd",
                  color: "#0369a1",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
                title="Review POI Name Recommendations"
              >
                <Sparkles size={14} color="#0284c7" />
                <span>Name Recommendations ({nameRecommendationsCount})</span>
              </button>
            )}

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
                <option value="complete">Completed Only</option>
                <option value="incomplete">Incomplete Only</option>
                <option value="missing_photo">Missing Photo</option>
                <option value="missing_location">Missing Location</option>
                <option value="missing_websites">Missing Websites</option>
              </select>

              {/* Disposition Multi-Select Filter */}
              <div
                style={{ position: "relative" }}
                ref={dispositionDropdownRef}
                data-testid="disposition-filter"
              >
                <button
                  type="button"
                  onClick={() => setIsDispositionDropdownOpen((prev) => !prev)}
                  data-testid="disposition-filter-button"
                  style={{
                    fontSize: "12px",
                    padding: "5px 10px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    backgroundColor: "#f8fafc",
                    color: "#0f172a",
                    fontWeight: 500,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    height: "30px",
                  }}
                >
                  <span>{dispositionButtonLabel}</span>
                  <ChevronDown size={13} color="#64748b" />
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
                      boxShadow:
                        "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)",
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
                      <span style={{ fontWeight: 600, color: "#64748b" }}>
                        Filter Dispositions
                      </span>
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

                    {ALL_WORKBENCH_DISPOSITIONS.map((disp) => {
                      const isChecked = selectedDispositions.includes(disp.key);
                      const count = dispositionCounts[disp.key] || 0;

                      return (
                        <label
                          key={disp.key}
                          data-testid={`disposition-option-${disp.key}`}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            cursor: "pointer",
                            backgroundColor: isChecked
                              ? "#f8fafc"
                              : "transparent",
                            fontSize: "12px",
                            color: "#334155",
                            userSelect: "none",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <input
                              type="checkbox"
                              data-testid={`disposition-checkbox-${disp.key}`}
                              checked={isChecked}
                              onChange={() => handleToggleDisposition(disp.key)}
                              style={{ cursor: "pointer" }}
                            />
                            <span style={{ fontWeight: isChecked ? 600 : 400 }}>
                              {disp.label}
                            </span>
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

              {/* Batch Edit Trigger */}
              {selectedCandidateIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setBatchCountry("");
                    setBatchState("");
                    setBatchCity("");
                    setBatchDateVisited("");
                    setBatchAddTag("");
                    setBatchRemoveTag("");
                    setIsBatchEditOpen(true);
                  }}
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
                                {getDisplayCandidateCity(cand)}
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
                                {getDisplayCandidateCity(cand)}
                              </td>
                            </>
                          )}

                          {/* Completeness Badge */}
                          <td style={{ padding: "8px 10px" }}>
                            {complete ? (
                              <span
                                data-testid="completeness-badge-complete"
                                title="All completeness criteria satisfied (Photo, Location & Address, Websites)"
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
                                title={`Missing: ${getCandidateMissingFields(
                                  cand,
                                ).join(", ")}`}
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
                                          : disp === "existing"
                                            ? "#e2e8f0"
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
                                          : disp === "existing"
                                            ? "#475569"
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

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => handleEnrichSingle(false)}
                      disabled={isEnrichingSingle}
                      data-testid="ai-enrich-poi-btn"
                      title="Enrich POI details using cached search results where available"
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

                    <button
                      type="button"
                      onClick={() => handleEnrichSingle(true)}
                      disabled={isEnrichingSingle}
                      data-testid="recalculate-force-refresh-btn"
                      title="Bypass search cache and recalculate all fields with fresh web and AI data"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "6px 12px",
                        borderRadius: "6px",
                        backgroundColor: "#ffffff",
                        color: "#475569",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: isEnrichingSingle ? "not-allowed" : "pointer",
                      }}
                    >
                      <RefreshCw
                        size={12}
                        className={isEnrichingSingle ? "animate-spin" : ""}
                      />
                      <span>Recalculate / Force Refresh</span>
                    </button>
                  </div>
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
                        {renderFieldLabelText("POI Name:", "poi_name")}
                      </label>
                      <input
                        type="text"
                        value={editPoiName}
                        onChange={(e) => setEditPoiName(e.target.value)}
                        data-testid="editor-poi-name-input"
                        style={getFieldInputStyle("poi_name", {
                          width: "100%",
                          padding: "7px 10px",
                          borderRadius: "6px",
                          border: "1px solid #cbd5e1",
                          fontSize: "13px",
                        })}
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
                        <option value="existing">Existing</option>
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
                      rows={editorCandidateMissingFields.length > 0 ? 3 : 2}
                      value={`Disposition: ${editDisposition.replace(
                        /_/g,
                        " ",
                      )}\nRationale: ${
                        editDispositionJustification ||
                        selectedCandidate.disposition_justification ||
                        (isSelectedGreatWall
                          ? "Great Wall of China correctly identified; multiple possible locations exist across this extensive site."
                          : "Unique location verified")
                      }${
                        editorCandidateMissingFields.length > 0
                          ? `\nMissing: ${editorCandidateMissingFields.join(
                              ", ",
                            )}`
                          : ""
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

                  {/* Matched Database POI Info Card */}
                  {associatedTarget?.type === "db" && (
                    <div
                      data-testid="matched-existing-poi-card"
                      style={{
                        padding: "10px 12px",
                        backgroundColor: "#f0fdf4",
                        border: "1px solid #86efac",
                        borderRadius: "6px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                      }}
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
                            color: "#166534",
                          }}
                        >
                          Matched Database POI (
                          {editDisposition === "existing"
                            ? "Identical / No Changes"
                            : "Update Target"}
                          ):
                        </span>
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#15803d",
                            backgroundColor: "#dcfce7",
                            padding: "2px 6px",
                            borderRadius: "4px",
                          }}
                        >
                          Green = no change / no data • Yellow = difference
                        </span>
                      </div>
                      <div
                        style={{
                          padding: "6px 8px",
                          borderRadius: "4px",
                          backgroundColor: "#ffffff",
                          border: "1px solid #bbf7d0",
                          fontSize: "12px",
                          color: "#14532d",
                        }}
                      >
                        <strong>
                          {associatedTarget.data.name ||
                            associatedTarget.data.poi_name}
                        </strong>
                        <div style={{ fontSize: "11px", color: "#4b5563" }}>
                          {[
                            associatedTarget.data.street_address ||
                              associatedTarget.data.address,
                            associatedTarget.data.city ||
                              associatedTarget.data.locality,
                            associatedTarget.data.state_province ||
                              associatedTarget.data.state,
                            associatedTarget.data.country,
                          ]
                            .filter(Boolean)
                            .join(", ") || "No address in DB"}
                        </div>
                      </div>
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
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "4px",
                      }}
                    >
                      <label
                        style={{
                          display: "flex",
                          alignItems: "center",
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#475569",
                        }}
                      >
                        {renderFieldLabelText(
                          "Hero Photo URL:",
                          "hero_image_url",
                        )}
                        <AIIconBadge />
                      </label>
                      {availableHeroImageUrls.length > 1 && (
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <span
                            data-testid="hero-image-count-badge"
                            style={{
                              fontSize: "10px",
                              color: "#64748b",
                              fontWeight: 600,
                            }}
                          >
                            Photo {currentHeroImageIndex + 1} of{" "}
                            {availableHeroImageUrls.length}
                          </span>
                          <button
                            type="button"
                            title="Previous image"
                            data-testid="hero-image-prev-btn"
                            onClick={() => {
                              if (availableHeroImageUrls.length <= 1) return;
                              const prevIdx =
                                (currentHeroImageIndex -
                                  1 +
                                  availableHeroImageUrls.length) %
                                availableHeroImageUrls.length;
                              setCurrentHeroImageIndex(prevIdx);
                              setEditHeroImageUrl(
                                availableHeroImageUrls[prevIdx],
                              );
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              width: "22px",
                              height: "22px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              backgroundColor: "#f8fafc",
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            <ChevronLeft size={13} color="#475569" />
                          </button>
                          <button
                            type="button"
                            title="Next image"
                            data-testid="hero-image-next-btn"
                            onClick={() => {
                              if (availableHeroImageUrls.length <= 1) return;
                              const nextIdx =
                                (currentHeroImageIndex + 1) %
                                availableHeroImageUrls.length;
                              setCurrentHeroImageIndex(nextIdx);
                              setEditHeroImageUrl(
                                availableHeroImageUrls[nextIdx],
                              );
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              width: "22px",
                              height: "22px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              backgroundColor: "#f8fafc",
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            <ChevronRight size={13} color="#475569" />
                          </button>
                        </div>
                      )}
                    </div>
                    <input
                      type="url"
                      value={editHeroImageUrl}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditHeroImageUrl(val);
                        const foundIdx = availableHeroImageUrls.findIndex(
                          (u) => u.trim() === val.trim(),
                        );
                        if (foundIdx >= 0) {
                          setCurrentHeroImageIndex(foundIdx);
                        }
                      }}
                      placeholder="https://example.com/photo.jpg"
                      data-testid="hero-image-url-input"
                      style={getFieldInputStyle("hero_image_url", {
                        width: "100%",
                        padding: "6px 10px",
                        borderRadius: "6px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                      })}
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
                          position: "relative",
                        }}
                      >
                        <img
                          key={editHeroImageUrl}
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
                        {availableHeroImageUrls.length > 1 && (
                          <div
                            style={{
                              marginTop: "6px",
                              display: "flex",
                              justifyContent: "center",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <button
                              type="button"
                              data-testid="hero-image-rotate-btn"
                              onClick={() => {
                                if (availableHeroImageUrls.length <= 1) return;
                                const nextIdx =
                                  (currentHeroImageIndex + 1) %
                                  availableHeroImageUrls.length;
                                setCurrentHeroImageIndex(nextIdx);
                                setEditHeroImageUrl(
                                  availableHeroImageUrls[nextIdx],
                                );
                              }}
                              style={{
                                background: "rgba(255, 255, 255, 0.15)",
                                border: "1px solid rgba(255, 255, 255, 0.25)",
                                borderRadius: "4px",
                                color: "#ffffff",
                                fontSize: "11px",
                                padding: "3px 8px",
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                              title="Rotate to next candidate image"
                            >
                              <RefreshCw size={11} /> Rotate Image (
                              {availableHeroImageUrls.length} available)
                            </button>
                          </div>
                        )}
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
                          <Search size={12} color="#0284c7" /> Search Location /
                          POI:
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
                            Lookup &quot;
                            {selectedCandidate.poi_name.length > 25
                              ? selectedCandidate.poi_name.slice(0, 22) + "..."
                              : selectedCandidate.poi_name}
                            &quot;
                          </button>
                        )}
                      </div>

                      <div
                        style={{
                          display: "flex",
                          gap: "6px",
                          position: "relative",
                        }}
                      >
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
                            placeholder="Type a location or paste a Google Maps, GeoHack, or webpage URL..."
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
                          onClick={() =>
                            executeLocationSearch(locationSearchQuery)
                          }
                          disabled={
                            isSearchingLocation || !locationSearchQuery.trim()
                          }
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
                      {showLocationSearchDropdown &&
                        locationSearchResults.length > 0 && (
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
                                  (
                                    e.currentTarget as HTMLElement
                                  ).style.backgroundColor = "#f0f9ff";
                                }}
                                onMouseLeave={(e) => {
                                  (
                                    e.currentTarget as HTMLElement
                                  ).style.backgroundColor = "transparent";
                                }}
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
                                      fontWeight: 600,
                                      color: "#0f172a",
                                    }}
                                  >
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
                          {renderFieldLabelText("Latitude:", "latitude")}
                        </label>
                        <input
                          type="text"
                          value={editLatitude}
                          onChange={(e) => setEditLatitude(e.target.value)}
                          placeholder="e.g. 41.8781"
                          data-testid="latitude-input"
                          style={getFieldInputStyle("latitude", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText("Longitude:", "longitude")}
                        </label>
                        <input
                          type="text"
                          value={editLongitude}
                          onChange={(e) => setEditLongitude(e.target.value)}
                          placeholder="e.g. -87.6298"
                          data-testid="longitude-input"
                          style={getFieldInputStyle("longitude", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Street Address:",
                            "street_address",
                          )}
                        </label>
                        <input
                          type="text"
                          value={editStreetAddress}
                          onChange={(e) => setEditStreetAddress(e.target.value)}
                          placeholder="Street address..."
                          data-testid="street-address-input"
                          style={getFieldInputStyle("street_address", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Postal Code / Zip:",
                            "postal_code",
                          )}
                        </label>
                        <input
                          type="text"
                          value={editPostalCode}
                          onChange={(e) => setEditPostalCode(e.target.value)}
                          placeholder="Postal code..."
                          data-testid="postal-code-input"
                          style={getFieldInputStyle("postal_code", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Locality (City / Town):",
                            "city",
                          )}
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
                          style={getFieldInputStyle("city", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Admin Level 2 (County / District):",
                            "admin_level_2",
                          )}
                        </label>
                        <input
                          type="text"
                          value={editAdminLevel2}
                          onChange={(e) => setEditAdminLevel2(e.target.value)}
                          placeholder="County / District..."
                          data-testid="admin-level-2-input"
                          style={getFieldInputStyle("admin_level_2", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Admin Level 1 (State / Province / Region):",
                            "state_province",
                          )}
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
                          style={getFieldInputStyle("state_province", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
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
                          {renderFieldLabelText(
                            "Country Code:",
                            "country_code",
                          )}
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
                          style={getFieldInputStyle("country_code", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                            textTransform: "uppercase",
                          })}
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
                          {renderFieldLabelText("Country:", "country")}
                        </label>
                        <input
                          type="text"
                          value={editCountry}
                          onChange={(e) => {
                            const val = e.target.value;
                            setEditCountry(val);
                            const mapped = countryNameToIsoCode(val);
                            if (
                              mapped &&
                              (editCountryCode === "US" || !editCountryCode)
                            ) {
                              setEditCountryCode(mapped);
                            }
                          }}
                          placeholder="Country..."
                          data-testid="country-input"
                          style={getFieldInputStyle("country", {
                            width: "100%",
                            padding: "5px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Nearby Search Radius and POIs */}
                  <div
                    data-testid="proximity-search-container"
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
                      {renderFieldLabelText("Description:", "description")}
                      <AIIconBadge />
                    </label>
                    <textarea
                      rows={5}
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      placeholder="Detailed overview and background of the location..."
                      data-testid="description-textarea"
                      style={getFieldInputStyle("description", {
                        width: "100%",
                        padding: "8px 10px",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        resize: "vertical",
                        minHeight: "100px",
                        lineHeight: 1.45,
                      })}
                    />
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
                      {renderFieldLabelText(
                        "Reason to Visit:",
                        "reason_to_visit",
                      )}
                      <AIIconBadge />
                    </label>
                    <textarea
                      rows={5}
                      value={editReasonToVisit}
                      onChange={(e) => setEditReasonToVisit(e.target.value)}
                      placeholder="- Key Highlight: Direct experiential reason why a traveler should visit..."
                      data-testid="reason-to-visit-textarea"
                      style={getFieldInputStyle("reason_to_visit", {
                        width: "100%",
                        padding: "8px 10px",
                        borderRadius: "4px",
                        border: "1px solid #cbd5e1",
                        fontSize: "12px",
                        resize: "vertical",
                        minHeight: "100px",
                        lineHeight: 1.45,
                      })}
                    />
                  </div>

                  {/* Visit Details Section */}
                  <div
                    data-testid="visit-details-section"
                    style={{
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
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "#1e293b",
                      }}
                    >
                      <Clock size={14} color="#2563eb" />
                      <span>Visit Details</span>
                    </div>

                    {/* Row 1: Estimated hours & Estimated Days */}
                    <div style={{ display: "flex", gap: "12px" }}>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                            marginBottom: "4px",
                          }}
                        >
                          {renderFieldLabelText(
                            "Estimated Hours:",
                            "duration_hours",
                          )}
                        </label>
                        <input
                          type="number"
                          step="0.5"
                          value={editDurationHours}
                          onChange={(e) => setEditDurationHours(e.target.value)}
                          placeholder="2.5"
                          data-testid="duration-hours-input"
                          style={getFieldInputStyle("duration_hours", {
                            width: "100%",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <label
                          style={{
                            display: "block",
                            fontSize: "10px",
                            fontWeight: 600,
                            color: "#64748b",
                            marginBottom: "4px",
                          }}
                        >
                          {renderFieldLabelText(
                            "Estimated Days:",
                            "duration_days",
                          )}
                        </label>
                        <input
                          type="number"
                          value={editDurationDays}
                          onChange={(e) => setEditDurationDays(e.target.value)}
                          placeholder="1"
                          data-testid="duration-days-input"
                          style={getFieldInputStyle("duration_days", {
                            width: "100%",
                            padding: "6px 8px",
                            borderRadius: "4px",
                            border: "1px solid #cbd5e1",
                            fontSize: "12px",
                          })}
                        />
                      </div>
                    </div>

                    {/* Row 2: Visit Timing Notes (multiline textbox) */}
                    <div>
                      <label
                        style={{
                          display: "block",
                          fontSize: "10px",
                          fontWeight: 600,
                          color: "#64748b",
                          marginBottom: "4px",
                        }}
                      >
                        {renderFieldLabelText(
                          "Visit Timing Notes:",
                          "duration_notes",
                        )}
                      </label>
                      <textarea
                        rows={3}
                        value={editDurationNotes}
                        onChange={(e) => setEditDurationNotes(e.target.value)}
                        placeholder="Best early morning or sunset..."
                        data-testid="duration-notes-input"
                        style={getFieldInputStyle("duration_notes", {
                          width: "100%",
                          padding: "6px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                          resize: "vertical",
                        })}
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
                      {renderFieldLabelText("Tags Library:", "tags")}
                      <AIIconBadge />
                    </label>

                    {/* All tags from library (selected vs unselected) */}
                    <div
                      style={getFieldInputStyle("tags", {
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "6px",
                        marginBottom: "8px",
                        maxHeight: "120px",
                        overflowY: "auto",
                        padding: "6px",
                        borderRadius: "6px",
                        border: "1px solid transparent",
                      })}
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
                      {renderFieldLabelText("Dates Visited:", "dates_visited")}
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
                        style={getFieldInputStyle("dates_visited", {
                          padding: "4px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        })}
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
                        <Folder size={13} color="#2563eb" />{" "}
                        {renderFieldLabelText(
                          "Associated Photo Directories:",
                          "photo_directories",
                        )}
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
                        style={getFieldInputStyle("photo_directories", {
                          flex: 1,
                          padding: "5px 8px",
                          borderRadius: "4px",
                          border: "1px solid #cbd5e1",
                          fontSize: "12px",
                        })}
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
                        <Globe size={14} color="#2563eb" />{" "}
                        {renderFieldLabelText(
                          "Related Websites",
                          "related_websites",
                        )}
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
                            style={getFieldInputStyle("related_websites", {
                              flex: 2,
                              padding: "5px 8px",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              fontSize: "12px",
                            })}
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
                          cleanReasonToVisit(selectedCandidate.reason_to_visit),
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
                    Add Tag (to all selected):
                  </label>
                  <input
                    type="text"
                    list="batch-add-tag-datalist"
                    value={batchAddTag}
                    onChange={(e) => setBatchAddTag(e.target.value)}
                    placeholder="e.g. World Wonder"
                    data-testid="batch-add-tag-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                  <datalist id="batch-add-tag-datalist">
                    {libraryTags.map((tag) => (
                      <option key={`add-${tag}`} value={tag} />
                    ))}
                  </datalist>
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
                    Remove Tag (from all selected):
                  </label>
                  <input
                    type="text"
                    list="batch-remove-tag-datalist"
                    value={batchRemoveTag}
                    onChange={(e) => setBatchRemoveTag(e.target.value)}
                    placeholder="e.g. ObsoleteTag"
                    data-testid="batch-remove-tag-input"
                    style={{
                      width: "100%",
                      padding: "6px 8px",
                      borderRadius: "4px",
                      border: "1px solid #cbd5e1",
                      fontSize: "12px",
                    }}
                  />
                  <datalist id="batch-remove-tag-datalist">
                    {Array.from(
                      new Set([
                        ...libraryTags,
                        ...candidates.flatMap((c) => c.tags || []),
                      ]),
                    ).map((tag) => (
                      <option key={`rem-${tag}`} value={tag} />
                    ))}
                  </datalist>
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
        {/* Name Change Confirmation Prompt Modal (when Find detects a different name) */}
        {nameChangePrompt && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(15, 23, 42, 0.6)",
              zIndex: 10000,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "16px",
            }}
            data-testid="name-change-prompt-modal"
          >
            <div
              style={{
                backgroundColor: "#ffffff",
                borderRadius: "10px",
                padding: "24px",
                maxWidth: "480px",
                width: "100%",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.15)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  marginBottom: "14px",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "50%",
                    backgroundColor: "#e0f2fe",
                    color: "#0284c7",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Sparkles size={20} />
                </div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "16px",
                    fontWeight: 700,
                    color: "#0f172a",
                  }}
                >
                  Update POI Name?
                </h3>
              </div>

              <p
                style={{
                  fontSize: "13px",
                  color: "#475569",
                  lineHeight: "1.5",
                  margin: "0 0 16px 0",
                }}
              >
                A more appropriate name was found for this location:
              </p>

              <div
                style={{
                  backgroundColor: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "12px 16px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    fontSize: "11px",
                    color: "#64748b",
                    textTransform: "uppercase",
                    fontWeight: 600,
                  }}
                >
                  Recommended Name
                </div>
                <div
                  style={{
                    fontSize: "15px",
                    fontWeight: 700,
                    color: "#0284c7",
                    marginTop: "2px",
                  }}
                  data-testid="recommended-name-display"
                >
                  {nameChangePrompt.recommendedName}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "#94a3b8",
                    marginTop: "4px",
                  }}
                >
                  Current:{" "}
                  <span style={{ color: "#64748b" }}>
                    {nameChangePrompt.currentName}
                  </span>
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: "10px",
                }}
              >
                <button
                  type="button"
                  onClick={() => setNameChangePrompt(null)}
                  data-testid="name-change-no-btn"
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    backgroundColor: "#ffffff",
                    color: "#334155",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  No, Keep Current Name
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    const newName = nameChangePrompt.recommendedName;
                    setEditPoiName(newName);
                    if (selectedCandidate) {
                      setCandidates((prev) =>
                        prev.map((c) =>
                          c.id === selectedCandidate.id
                            ? { ...c, poi_name: newName }
                            : c,
                        ),
                      );
                      if (jobId) {
                        try {
                          await ingestApi.updateStagingCandidate(
                            jobId,
                            selectedCandidate.id,
                            {
                              poi_name: newName,
                            },
                          );
                        } catch (err) {
                          console.error(
                            "Failed to update candidate name on backend:",
                            err,
                          );
                        }
                      }
                    }
                    showToast(`POI name updated to "${newName}"`, "success");
                    setNameChangePrompt(null);
                  }}
                  data-testid="name-change-yes-btn"
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: "#0284c7",
                    color: "#ffffff",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Yes, Update Name
                </button>
              </div>
            </div>
          </div>
        )}

        {/* POI Name Recommendations Review Modal */}
        <POINameRecommendationsModal
          isOpen={showNameRecommendationsModal}
          onClose={() => setShowNameRecommendationsModal(false)}
          candidates={candidates}
          onAcceptChanges={handleAcceptNameChanges}
        />
      </div>
    </Modal>
  );
};
