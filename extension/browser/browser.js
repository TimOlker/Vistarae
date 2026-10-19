/**
 * Vistarae POI Explorer & Database Browser Controller
 */

// State
let allPois = [];
let filteredPois = [];
let availableLists = [];
let availableTags = [];
let currentEditingPoi = null;
let currentDeletingPoiId = null;
let selectedPoiIds = new Set();
let currentSort = { column: "created_at", direction: "desc" };

// DOM Elements
const userDisplay = document.getElementById("user-display");
const keywordSearch = document.getElementById("keyword-search");
const clearSearchBtn = document.getElementById("clear-search-btn");
const refreshBtn = document.getElementById("refresh-btn");
const resetFiltersBtn = document.getElementById("reset-filters-btn");
const resultsCountText = document.getElementById("results-count-text");
const activeFilterBadge = document.getElementById("active-filter-badge");
const activeFiltersChipsBar = document.getElementById("active-filters-chips-bar");
const exportCsvBtn = document.getElementById("export-csv-btn");
const visualizeGmapsBtn = document.getElementById("visualize-gmaps-btn");
const visualizeBtnLabel = document.getElementById("visualize-btn-label");
const mapContainerCard = document.getElementById("map-container-card");
const mapStatusPill = document.getElementById("map-status-pill");
const mapRecenterBtn = document.getElementById("map-recenter-btn");
const exportKmlBtn = document.getElementById("export-kml-btn");
const mapCloseBtn = document.getElementById("map-close-btn");
const filterMapBoundsBtn = document.getElementById("filter-map-bounds-btn");
const useMapBoundsBtn = document.getElementById("use-map-bounds-btn");
const mapFilterViewBtn = document.getElementById("map-filter-view-btn");
const mapSyncViewCheckbox = document.getElementById("map-sync-view-checkbox");
const mapClusterToggle = document.getElementById("map-cluster-toggle");
const pageClusterToggle = document.getElementById("page-cluster-toggle");
const clusterAutoBadge = document.getElementById("cluster-auto-badge");
const mapPinColorsBtn = document.getElementById("map-pin-colors-btn");
const mapPinColorsBadge = document.getElementById("map-pin-colors-badge");
const mapClearPinColorsBtn = document.getElementById("map-clear-pin-colors-btn");
let activePinColorScheme = null;
let savedPinSchemes = [];
const MAX_UNCLUSTERED_POIS = 100;
let userExplicitlyToggledCluster = false;
const mapTileProviderSelect = document.getElementById("map-tile-provider-select");
let leafletMap = null;
let leafletMarkersLayer = null;
let poiMarkersMap = new Map();
let mapBoundsFilter = null; // { north, south, east, west }
let isMapSyncBound = false;
let mapMoveDebounceTimer = null;
let currentTileLayer = null;
let selectedTileProvider = "google-roadmap";

const MAP_TILE_PROVIDERS = {
  "google-roadmap": {
    name: "Google Maps (English & Global Deep Zoom)",
    url: "https://mt{s}.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}",
    options: {
      maxZoom: 20,
      subdomains: ["0", "1", "2", "3"],
      attribution: '&copy; Google Maps',
    },
  },
  "google-hybrid": {
    name: "Google Hybrid (Satellite + English Labels)",
    url: "https://mt{s}.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
    options: {
      maxZoom: 20,
      subdomains: ["0", "1", "2", "3"],
      attribution: '&copy; Google Maps',
    },
  },
  "google-terrain": {
    name: "Google Terrain (English Contours)",
    url: "https://mt{s}.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
    options: {
      maxZoom: 20,
      subdomains: ["0", "1", "2", "3"],
      attribution: '&copy; Google Maps',
    },
  },
  "osm-standard": {
    name: "OpenStreetMap (Global Deep Zoom / Local Names)",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  "osm-hot": {
    name: "OpenStreetMap Humanitarian (Deep Zoom)",
    url: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    options: {
      maxZoom: 19,
      subdomains: ["a", "b", "c"],
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Humanitarian OpenStreetMap Team',
    },
  },
  "esri-street": {
    name: "Esri World Street (English)",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    options: {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, TomTom',
    },
  },
  "esri-imagery": {
    name: "Esri Satellite (Photographic)",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP',
    },
  },
};

// Comprehensive Country Name -> ISO Alpha-2 lookup dictionary
const COUNTRY_NAME_TO_ALPHA2 = {
  // Popular & East Asia
  "china": "CN",
  "peoples republic of china": "CN",
  "people's republic of china": "CN",
  "prc": "CN",
  "japan": "JP",
  "nippon": "JP",
  "nihon": "JP",
  "south korea": "KR",
  "korea": "KR",
  "republic of korea": "KR",
  "north korea": "KP",
  "taiwan": "TW",
  "hong kong": "HK",
  "macau": "MO",
  "macao": "MO",
  "mongolia": "MN",

  // North America
  "united states": "US",
  "united states of america": "US",
  "usa": "US",
  "america": "US",
  "canada": "CA",
  "mexico": "MX",

  // Europe
  "united kingdom": "GB",
  "great britain": "GB",
  "britain": "GB",
  "uk": "GB",
  "england": "GB",
  "scotland": "GB",
  "wales": "GB",
  "northern ireland": "GB",
  "france": "FR",
  "germany": "DE",
  "deutschland": "DE",
  "italy": "IT",
  "italia": "IT",
  "spain": "ES",
  "espana": "ES",
  "portugal": "PT",
  "switzerland": "CH",
  "schweiz": "CH",
  "suisse": "CH",
  "austria": "AT",
  "osterreich": "AT",
  "netherlands": "NL",
  "holland": "NL",
  "belgium": "BE",
  "ireland": "IE",
  "republic of ireland": "IE",
  "iceland": "IS",
  "norway": "NO",
  "sweden": "SE",
  "finland": "FI",
  "denmark": "DK",
  "greece": "GR",
  "hellas": "GR",
  "turkey": "TR",
  "turkiye": "TR",
  "cyprus": "CY",
  "malta": "MT",
  "russia": "RU",
  "russian federation": "RU",
  "ukraine": "UA",
  "poland": "PL",
  "polska": "PL",
  "czech republic": "CZ",
  "czechia": "CZ",
  "slovakia": "SK",
  "slovak republic": "SK",
  "hungary": "HU",
  "romania": "RO",
  "bulgaria": "BG",
  "croatia": "HR",
  "slovenia": "SI",
  "serbia": "RS",
  "bosnia": "BA",
  "bosnia and herzegovina": "BA",
  "montenegro": "ME",
  "north macedonia": "MK",
  "macedonia": "MK",
  "albania": "AL",
  "estonia": "EE",
  "latvia": "LV",
  "lithuania": "LT",
  "belarus": "BY",
  "moldova": "MD",
  "georgia": "GE",
  "armenia": "AM",
  "azerbaijan": "AZ",

  // Oceania
  "australia": "AU",
  "new zealand": "NZ",
  "fiji": "FJ",
  "papua new guinea": "PG",

  // South & Central America, Caribbean
  "argentina": "AR",
  "brazil": "BR",
  "brasil": "BR",
  "chile": "CL",
  "peru": "PE",
  "colombia": "CO",
  "ecuador": "EC",
  "bolivia": "BO",
  "paraguay": "PY",
  "uruguay": "UY",
  "venezuela": "VE",
  "guyana": "GY",
  "suriname": "SR",
  "costa rica": "CR",
  "panama": "PA",
  "guatemala": "GT",
  "belize": "BZ",
  "honduras": "HN",
  "el salvador": "SV",
  "nicaragua": "NI",
  "cuba": "CU",
  "bahamas": "BS",
  "jamaica": "JM",
  "haiti": "HT",
  "dominican republic": "DO",
  "puerto rico": "PR",
  "trinidad and tobago": "TT",
  "barbados": "BB",
  "saint lucia": "LC",

  // Middle East & Africa
  "egypt": "EG",
  "morocco": "MA",
  "algeria": "DZ",
  "tunisia": "TN",
  "south africa": "ZA",
  "kenya": "KE",
  "tanzania": "TZ",
  "uganda": "UG",
  "rwanda": "RW",
  "ethiopia": "ET",
  "ghana": "GH",
  "nigeria": "NG",
  "senegal": "SN",
  "namibia": "NA",
  "botswana": "BW",
  "zimbabwe": "ZW",
  "zambia": "ZM",
  "madagascar": "MG",
  "mauritius": "MU",
  "seychelles": "SC",
  "israel": "IL",
  "jordan": "JO",
  "lebanon": "LB",
  "saudi arabia": "SA",
  "united arab emirates": "AE",
  "uae": "AE",
  "dubai": "AE",
  "qatar": "QA",
  "oman": "OM",
  "kuwait": "KW",
  "bahrain": "BH",

  // South & Southeast & Central Asia
  "india": "IN",
  "pakistan": "PK",
  "bangladesh": "BD",
  "sri lanka": "LK",
  "nepal": "NP",
  "bhutan": "BT",
  "maldives": "MV",
  "thailand": "TH",
  "vietnam": "VN",
  "viet nam": "VN",
  "cambodia": "KH",
  "laos": "LA",
  "myanmar": "MM",
  "burma": "MM",
  "malaysia": "MY",
  "singapore": "SG",
  "indonesia": "ID",
  "philippines": "PH",
  "brunei": "BN",
  "kazakhstan": "KZ",
  "uzbekistan": "UZ",
  "kyrgyzstan": "KG",
  "tajikistan": "TJ",
  "turkmenistan": "TM",
};

/**
 * Attempts to map any country name, alias, or spelling to a 2-letter ISO 3166-1 alpha-2 code.
 * E.g. "China" -> "CN", "china" -> "CN", "United States" -> "US", "cn" -> "CN".
 */
function mapCountryNameToAlpha2(input) {
  if (!input) return null;
  const raw = input.trim();
  if (!raw) return null;
  const norm = raw.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  if (COUNTRY_NAME_TO_ALPHA2[norm]) return COUNTRY_NAME_TO_ALPHA2[norm];
  if (raw.length === 2) return raw.toUpperCase();
  for (const [key, code] of Object.entries(COUNTRY_NAME_TO_ALPHA2)) {
    if (key.length >= 4 && (norm === key || norm.startsWith(key + " ") || norm.endsWith(" " + key))) {
      return code;
    }
  }
  return null;
}

/**
 * Safely validates whether a POI record has real, plottable latitude & longitude numbers.
 * Accurately excludes null, undefined, empty strings, NaN, and (0, 0).
 */
function hasValidCoordinates(p) {
  if (!p) return false;
  if (p.latitude === null || p.latitude === undefined || p.latitude === "") return false;
  if (p.longitude === null || p.longitude === undefined || p.longitude === "") return false;
  const lat = Number(p.latitude);
  const lng = Number(p.longitude);
  if (isNaN(lat) || isNaN(lng)) return false;
  if (lat === 0 && lng === 0) return false;
  return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

const poisTableBody = document.getElementById("pois-table-body");

// Cooperative Filter Elements
const filterCity = document.getElementById("filter-city");
const filterState = document.getElementById("filter-state");
const filterCountry = document.getElementById("filter-country");
const filterTag = document.getElementById("filter-tag");
const availableTagsList = document.getElementById("available-tags-list");
const filterList = document.getElementById("filter-list");
const applyFiltersBtn = document.getElementById("apply-filters-btn");
const toggleCoordsBtn = document.getElementById("toggle-coords-btn");
const clearCoordsBtn = document.getElementById("clear-coords-btn");
const quickTagsBar = document.getElementById("quick-tags-bar");
const paneCoords = document.getElementById("pane-coords");
const filterLat = document.getElementById("filter-lat");
const filterLng = document.getElementById("filter-lng");
const filterRadius = document.getElementById("filter-radius");
const useMyLocBtn = document.getElementById("use-my-loc-btn");

// Bulk Action Toolbar Elements
const selectAllCheckbox = document.getElementById("select-all-checkbox");
const bulkActionsToolbar = document.getElementById("bulk-actions-toolbar");
const bulkSelectedCount = document.getElementById("bulk-selected-count");
const bulkTagsBtn = document.getElementById("bulk-tags-btn");
const bulkLocationBtn = document.getElementById("bulk-location-btn");
const bulkDeleteBtn = document.getElementById("bulk-delete-btn");
const bulkDeselectBtn = document.getElementById("bulk-deselect-btn");

// Bulk Delete Modal
const bulkDeleteModal = document.getElementById("bulk-delete-modal");
const bulkDeleteModalClose = document.getElementById("bulk-delete-modal-close");
const bulkDeleteCancelBtn = document.getElementById("bulk-delete-cancel-btn");
const bulkDeleteConfirmBtn = document.getElementById("bulk-delete-confirm-btn");
const bulkDeleteCountDisplay = document.getElementById("bulk-delete-count-display");
const bulkDeletePreviewList = document.getElementById("bulk-delete-preview-list");

// Bulk Tags Modal
const bulkTagsModal = document.getElementById("bulk-tags-modal");
const bulkTagsModalClose = document.getElementById("bulk-tags-modal-close");
const bulkTagsCancelBtn = document.getElementById("bulk-tags-cancel-btn");
const bulkTagsApplyBtn = document.getElementById("bulk-tags-apply-btn");
const bulkTagsCountDisplay = document.getElementById("bulk-tags-count-display");
const bulkAddTagsInput = document.getElementById("bulk-add-tags-input");
const bulkRemoveTagsInput = document.getElementById("bulk-remove-tags-input");
const bulkPresetTags = document.getElementById("bulk-preset-tags");

const filterLocationStatus = document.getElementById("filter-location-status");
const filterVisitedStatus = document.getElementById("filter-visited-status");

// Bulk Location Modal
const bulkLocationModal = document.getElementById("bulk-location-modal");
const bulkLocationModalClose = document.getElementById("bulk-location-modal-close");
const bulkLocationCancelBtn = document.getElementById("bulk-location-cancel-btn");
const bulkLocationApplyBtn = document.getElementById("bulk-location-apply-btn");
const bulkLocationCountDisplay = document.getElementById("bulk-location-count-display");
const bulkLatInput = document.getElementById("bulk-lat-input");
const bulkLngInput = document.getElementById("bulk-lng-input");
const bulkClearLocationCheckbox = document.getElementById("bulk-clear-location-checkbox");
const bulkCityInput = document.getElementById("bulk-city-input");
const bulkStateInput = document.getElementById("bulk-state-input");
const bulkCountryInput = document.getElementById("bulk-country-input");
const bulkMapStatusHint = document.getElementById("bulk-map-status-hint");
const bulkPickMainMapBtn = document.getElementById("bulk-pick-main-map-btn");
const bulkApplyCoordsCheckbox = document.getElementById("bulk-apply-coords-checkbox");
const bulkApplyCityCheckbox = document.getElementById("bulk-apply-city-checkbox");
const bulkApplyStateCheckbox = document.getElementById("bulk-apply-state-checkbox");
const bulkApplyCountryCheckbox = document.getElementById("bulk-apply-country-checkbox");
const bulkCoordsBox = document.getElementById("bulk-coords-box");
const bulkCoordsBody = document.getElementById("bulk-coords-body");
const bulkCityBox = document.getElementById("bulk-city-box");
const bulkStateBox = document.getElementById("bulk-state-box");
const bulkCountryBox = document.getElementById("bulk-country-box");
const bulkLocationSelectAllBtn = document.getElementById("bulk-location-select-all");
const bulkLocationClearAllBtn = document.getElementById("bulk-location-clear-all");

// Bulk Location Confirmation Modal Elements
const bulkLocationConfirmModal = document.getElementById("bulk-location-confirm-modal");
const bulkLocationConfirmModalClose = document.getElementById("bulk-location-confirm-modal-close");
const bulkLocationConfirmCancelBtn = document.getElementById("bulk-location-confirm-cancel-btn");
const bulkLocationConfirmProceedBtn = document.getElementById("bulk-location-confirm-proceed-btn");
const bulkLocationConfirmCount = document.getElementById("bulk-location-confirm-count");
const bulkLocationConfirmSummary = document.getElementById("bulk-location-confirm-summary");
const bulkLocationConfirmPreviewList = document.getElementById("bulk-location-confirm-preview-list");

// Main Map Picker Banner Elements
const mainMapPickerBanner = document.getElementById("main-map-picker-banner");
const mainMapPickerCount = document.getElementById("main-map-picker-count");
const mainMapPickerCoords = document.getElementById("main-map-picker-coords");
const mainMapPickerDoneBtn = document.getElementById("main-map-picker-done-btn");
const mainMapPickerCancelBtn = document.getElementById("main-map-picker-cancel-btn");

let bulkLocationMap = null;
let bulkLocationMarker = null;
let mainMapPickerMarker = null;
let pendingBulkLocationPayload = null;

// Modals & Action Buttons
const headerAddPoiBtn = document.getElementById("header-add-poi-btn");
const toolbarAddPoiBtn = document.getElementById("toolbar-add-poi-btn");
const editModal = document.getElementById("edit-modal");
const editModalClose = document.getElementById("edit-modal-close");
const editCancelBtn = document.getElementById("edit-cancel-btn");
const editSaveBtn = document.getElementById("edit-save-btn");
const editDeleteBtn = document.getElementById("edit-delete-btn");
const editCloneBtn = document.getElementById("edit-clone-btn");
const editCollisionBanner = document.getElementById("edit-collision-banner");
const editRecalcAddressBtn = document.getElementById("edit-recalc-address-btn");
const editLookupDetailsBtn = document.getElementById("edit-lookup-details-btn");
const editClearLocationBtn = document.getElementById("edit-clear-location-btn");
const editUseGpsBtn = document.getElementById("edit-use-gps-btn");
const editForm = document.getElementById("edit-poi-form");
const editViewGmapsLink = document.getElementById("edit-view-gmaps-link");

const deleteModal = document.getElementById("delete-modal");
const deleteModalClose = document.getElementById("delete-modal-close");
const deleteCancelBtn = document.getElementById("delete-cancel-btn");
const deleteConfirmBtn = document.getElementById("delete-confirm-btn");
const deletePoiName = document.getElementById("delete-poi-name");

const toastContainer = document.getElementById("toast-container");

// Auth Controls & Modal
const authStatusDot = document.getElementById("auth-status-dot");
const authActionBtn = document.getElementById("auth-action-btn");
const authModal = document.getElementById("auth-modal");
const authModalTitle = document.getElementById("auth-modal-title");
const authModalClose = document.getElementById("auth-modal-close");
const authForm = document.getElementById("auth-form");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authErrorMsg = document.getElementById("auth-error-msg");
const authToggleMode = document.getElementById("auth-toggle-mode");
const authSubmitBtn = document.getElementById("auth-submit-btn");
let isAuthRegisterMode = false;

// Tags Editor in Modal
const editTagsContainer = document.getElementById("edit-tags-container");
const newTagInput = document.getElementById("new-tag-input");
const addTagBtn = document.getElementById("add-tag-btn");
const editPresetTags = document.getElementById("edit-preset-tags");
const editListsContainer = document.getElementById("edit-lists-container");

let editingTagsList = [];

/**
 * Robustly opens a URL in a new Chrome tab without popup blocker interference.
 */
function openUrlInNewTab(url) {
  if (chrome?.tabs?.create) {
    chrome.tabs.create({ url });
  } else {
    chrome.runtime.sendMessage({ action: "OPEN_TAB", url }, (res) => {
      if (!res?.success) window.open(url, "_blank");
    });
  }
}

/**
 * Unified API fetch helper with W3C Distributed Tracing and Bearer Token Injection.
 */
async function apiFetch(endpoint, options = {}) {
  const syncSettings = await chrome.storage.sync.get({ backendUrl: "http://localhost:8030" });
  const backendUrl = (syncSettings.backendUrl || "http://localhost:8030").replace(/\/$/, "");
  const targetUrl = endpoint.startsWith("http") ? endpoint : `${backendUrl}${endpoint}`;

  const authData = await chrome.storage.local.get(["auth_token", "user"]);
  const token = authData.auth_token;

  // Generate W3C Traceparent
  const traceId = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
  const spanId = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");

  const headers = {
    "X-Source": "extension",
    "X-Destination": "backend",
    "traceparent": `00-${traceId}-${spanId}-01`,
    ...(options.headers || {})
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && !headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const method = options.method || "GET";
  console.log(`MSG   |-> [Extension Browser] HTTP ${method} ${targetUrl} | TraceID=${traceId} SpanID=${spanId}`);

  try {
    const response = await fetch(targetUrl, {
      cache: "no-store",
      ...options,
      headers
    });

    const serverSpanId = response.headers.get("X-Current-Span-ID") || "unknown";
    console.log(`MSG   |<- [Extension Browser] HTTP ${response.status} ${targetUrl} | TraceID=${traceId} ServerSpanID=${serverSpanId}`);

    if (response.status === 401) {
      console.warn("[apiFetch] Unauthorized (401) on", targetUrl);
    }

    return response;
  } catch (err) {
    console.error(`MSG   |<- [Extension Browser] HTTP ERROR ${targetUrl} | Error=${err.message}`);
    throw err;
  }
}

// Alias loadPois to fetchPois for backward compatibility
const loadPois = async (...args) => fetchPois(...args);

// ==========================================
// Initialization
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  chrome.storage.local.get([
    "map_tile_provider",
    "map_cluster_enabled",
    "assign_map_tile_provider",
    "vistarae_active_pin_scheme",
    "vistarae_saved_pin_schemes"
  ], (data) => {
    if (data?.map_tile_provider && MAP_TILE_PROVIDERS[data.map_tile_provider]) {
      selectedTileProvider = data.map_tile_provider;
    } else {
      selectedTileProvider = "google-roadmap";
    }
    if (mapTileProviderSelect) {
      mapTileProviderSelect.value = selectedTileProvider;
    }
    if (data?.assign_map_tile_provider && MAP_TILE_PROVIDERS[data.assign_map_tile_provider]) {
      assignSelectedTileProvider = data.assign_map_tile_provider;
    } else {
      assignSelectedTileProvider = "google-hybrid";
    }
    if (typeof assignMapTileProviderSelect !== "undefined" && assignMapTileProviderSelect) {
      assignMapTileProviderSelect.value = assignSelectedTileProvider;
    }
    if (data?.map_cluster_enabled !== undefined) {
      userExplicitlyToggledCluster = true;
      const isClustered = Boolean(data.map_cluster_enabled);
      if (mapClusterToggle) mapClusterToggle.checked = isClustered;
      if (pageClusterToggle) pageClusterToggle.checked = isClustered;
    }
    if (data?.vistarae_active_pin_scheme) {
      activePinColorScheme = data.vistarae_active_pin_scheme;
      updatePinColorToolbarUI();
    }
    if (Array.isArray(data?.vistarae_saved_pin_schemes)) {
      savedPinSchemes = data.vistarae_saved_pin_schemes;
    }
  });
  await checkAuth();
  await loadLists();
  await loadTags();
  await fetchPois();
  // Asynchronously load folder counts so tab badge shows actual count
  updateFolderStatusCounts();
});

// Toast notification helper
function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast ${isError ? "toast-error" : "toast-success"}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Check Auth & Display
async function checkAuth() {
  chrome.runtime.sendMessage({ action: "GET_AUTH" }, (response) => {
    if (response?.isAuthenticated && response.user?.email) {
      if (authStatusDot) authStatusDot.className = "status-dot online";
      userDisplay.textContent = response.user.email;
      if (authActionBtn) {
        authActionBtn.textContent = "Sign Out";
        authActionBtn.style.display = "inline-block";
        authActionBtn.onclick = handleSignOut;
      }
    } else {
      if (authStatusDot) authStatusDot.className = "status-dot offline";
      userDisplay.textContent = "Not signed in";
      if (authActionBtn) {
        authActionBtn.textContent = "Sign In";
        authActionBtn.style.display = "inline-block";
        authActionBtn.onclick = () => openAuthModal("login");
      }
    }
  });
}

function openAuthModal(mode = "login") {
  isAuthRegisterMode = mode === "register";
  if (authModalTitle) {
    authModalTitle.textContent = isAuthRegisterMode ? "Create a Vistarae Account" : "Sign In to Vistarae";
  }
  if (authSubmitBtn) {
    authSubmitBtn.textContent = isAuthRegisterMode ? "Register" : "Sign In";
  }
  if (authToggleMode) {
    authToggleMode.textContent = isAuthRegisterMode ? "Already have an account? Sign In" : "Need an account? Register";
  }
  if (authErrorMsg) authErrorMsg.style.display = "none";
  if (authModal) authModal.style.display = "flex";
  if (authEmail) authEmail.focus();
}

function closeAuthModal() {
  if (authModal) authModal.style.display = "none";
  if (authErrorMsg) authErrorMsg.style.display = "none";
}

function handleSignOut() {
  chrome.storage.local.remove(["auth_token", "user"], () => {
    showToast("Signed out successfully.");
    checkAuth();
    fetchPois();
  });
}

// Setup Event Listeners
function setupEventListeners() {
  // Delegated click listener for all .folder-open-link elements
  document.addEventListener("click", (e) => {
    const link = e.target.closest(".folder-open-link");
    if (!link) return;
    const rawPath = link.dataset.path || link.getAttribute("data-path");
    if (rawPath) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(rawPath);
        }
      } catch (err) {}
      showToast("Opening folder in File Explorer...", true);
    }
  });

  // Dynamic open button update for edit-source-url input
  const editSourceUrlInput = document.getElementById("edit-source-url");
  const editSourceTypeInput = document.getElementById("edit-source-type");
  const editSourceUrlOpenBtn = document.getElementById("edit-source-url-open-btn");

  window.autoResizeSourceUrl = function() {
    const el = document.getElementById("edit-source-url");
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.max(el.scrollHeight + 2, 44);
    el.style.height = newHeight + "px";
  };

  function syncEditSourceUrlBtn() {
    window.autoResizeSourceUrl();
    if (!editSourceUrlOpenBtn || !editSourceUrlInput) return;
    const val = editSourceUrlInput.value.trim();
    const stVal = (editSourceTypeInput ? editSourceTypeInput.value.trim() : "").toLowerCase();
    if (val && (stVal === "photo" || isLocalOrUncPath(val))) {
      editSourceUrlOpenBtn.style.display = "inline-flex";
      editSourceUrlOpenBtn.href = getFolderProtocolUrl(val);
      editSourceUrlOpenBtn.setAttribute("data-path", val);
    } else {
      editSourceUrlOpenBtn.style.display = "none";
    }
  }
  if (editSourceUrlInput) editSourceUrlInput.addEventListener("input", syncEditSourceUrlBtn);
  if (editSourceTypeInput) editSourceTypeInput.addEventListener("input", syncEditSourceUrlBtn);

  // Search input with debounce
  let searchDebounce = null;
  keywordSearch.addEventListener("input", () => {
    clearSearchBtn.style.display = keywordSearch.value ? "block" : "none";
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      fetchPois();
    }, 300);
  });

  clearSearchBtn.addEventListener("click", () => {
    keywordSearch.value = "";
    clearSearchBtn.style.display = "none";
    fetchPois(true);
  });

  refreshBtn.addEventListener("click", () => {
    fetchPois(true);
  });

  resetFiltersBtn.addEventListener("click", () => {
    resetAllFilters();
  });

  // Searchable Parent POI Combobox initialization
  setupParentPoiCombobox();

  // Cooperative Filter Buttons & Inputs
  if (applyFiltersBtn) applyFiltersBtn.addEventListener("click", () => fetchPois(true));
  if (toggleCoordsBtn) {
    toggleCoordsBtn.addEventListener("click", () => {
      const isHidden = paneCoords.style.display === "none";
      paneCoords.style.display = isHidden ? "block" : "none";
      toggleCoordsBtn.classList.toggle("active", isHidden);
    });
  }
  if (filterMapBoundsBtn) {
    filterMapBoundsBtn.addEventListener("click", () => filterToCurrentMapBounds(true));
  }
  if (useMapBoundsBtn) {
    useMapBoundsBtn.addEventListener("click", () => filterToCurrentMapBounds(true));
  }
  if (clearCoordsBtn) {
    clearCoordsBtn.addEventListener("click", () => {
      filterLat.value = "";
      filterLng.value = "";
      fetchPois(true);
    });
  }

  // Enter key submits filters
  [filterCity, filterState, filterCountry, filterTag, filterLat, filterLng].forEach((inp) => {
    if (inp) {
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") fetchPois();
      });
    }
  });
  if (filterCountry) {
    filterCountry.addEventListener("blur", () => {
      const raw = filterCountry.value.trim();
      if (raw.length > 2) {
        const mapped = mapCountryNameToAlpha2(raw);
        if (mapped) {
          filterCountry.value = mapped;
        }
      }
    });
  }
  if (filterList) {
    filterList.addEventListener("change", () => fetchPois());
  }
  if (filterLocationStatus) {
    filterLocationStatus.addEventListener("change", () => fetchPois());
  }
  if (filterVisitedStatus) {
    filterVisitedStatus.addEventListener("change", () => fetchPois());
  }
  if (bulkClearLocationCheckbox) {
    bulkClearLocationCheckbox.addEventListener("change", () => {
      if (bulkApplyCoordsCheckbox && !bulkApplyCoordsCheckbox.checked) {
        bulkApplyCoordsCheckbox.checked = true;
      }
      syncBulkLocationFieldStates();
    });
  }
  if (editClearLocationBtn) {
    editClearLocationBtn.addEventListener("click", () => {
      document.getElementById("edit-lat").value = "";
      document.getElementById("edit-lng").value = "";
      showToast("Location coordinates cleared. Click 'Save Changes' to update.");
    });
  }

  // Bulk Actions Toolbar
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", (e) => {
      handleToggleSelectAll(e.target.checked);
    });
  }
  if (bulkTagsBtn) bulkTagsBtn.addEventListener("click", openBulkTagsModal);
  if (bulkLocationBtn) bulkLocationBtn.addEventListener("click", openBulkLocationModal);
  if (bulkDeleteBtn) bulkDeleteBtn.addEventListener("click", openBulkDeleteModal);
  if (bulkDeselectBtn) bulkDeselectBtn.addEventListener("click", handleClearSelection);

  // Bulk Delete Modal events
  if (bulkDeleteModalClose) bulkDeleteModalClose.addEventListener("click", closeBulkDeleteModal);
  if (bulkDeleteCancelBtn) bulkDeleteCancelBtn.addEventListener("click", closeBulkDeleteModal);
  if (bulkDeleteConfirmBtn) bulkDeleteConfirmBtn.addEventListener("click", handleConfirmBulkDelete);

  // Bulk Tags Modal events
  if (bulkTagsModalClose) bulkTagsModalClose.addEventListener("click", closeBulkTagsModal);
  if (bulkTagsCancelBtn) bulkTagsCancelBtn.addEventListener("click", closeBulkTagsModal);
  if (bulkTagsApplyBtn) bulkTagsApplyBtn.addEventListener("click", handleApplyBulkTags);
  if (bulkPresetTags) {
    bulkPresetTags.querySelectorAll(".tag-pill-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tag = btn.dataset.tag;
        const current = bulkAddTagsInput.value.trim();
        bulkAddTagsInput.value = current ? `${current}, ${tag}` : tag;
      });
    });
  }

  // Bulk Location Modal events
  if (bulkLocationModalClose) bulkLocationModalClose.addEventListener("click", closeBulkLocationModal);
  if (bulkLocationCancelBtn) bulkLocationCancelBtn.addEventListener("click", closeBulkLocationModal);
  if (bulkLocationApplyBtn) bulkLocationApplyBtn.addEventListener("click", handleApplyBulkLocation);
  if (bulkPickMainMapBtn) bulkPickMainMapBtn.addEventListener("click", startMainMapPicking);

  // Bulk Location Checkboxes & Quick Select/Clear All
  if (bulkLocationSelectAllBtn) {
    bulkLocationSelectAllBtn.addEventListener("click", () => {
      if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = true;
      if (bulkApplyCityCheckbox) bulkApplyCityCheckbox.checked = true;
      if (bulkApplyStateCheckbox) bulkApplyStateCheckbox.checked = true;
      if (bulkApplyCountryCheckbox) bulkApplyCountryCheckbox.checked = true;
      syncBulkLocationFieldStates();
      if (bulkLocationMap) setTimeout(() => bulkLocationMap.invalidateSize(), 100);
    });
  }
  if (bulkLocationClearAllBtn) {
    bulkLocationClearAllBtn.addEventListener("click", () => {
      if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = false;
      if (bulkApplyCityCheckbox) bulkApplyCityCheckbox.checked = false;
      if (bulkApplyStateCheckbox) bulkApplyStateCheckbox.checked = false;
      if (bulkApplyCountryCheckbox) bulkApplyCountryCheckbox.checked = false;
      syncBulkLocationFieldStates();
    });
  }

  [bulkApplyCoordsCheckbox, bulkApplyCityCheckbox, bulkApplyStateCheckbox, bulkApplyCountryCheckbox].forEach((cb) => {
    if (cb) {
      cb.addEventListener("change", () => {
        syncBulkLocationFieldStates();
        if (cb === bulkApplyCoordsCheckbox && cb.checked && bulkLocationMap) {
          setTimeout(() => bulkLocationMap.invalidateSize(), 100);
        }
      });
    }
  });

  // Auto-activate corresponding checkbox when typing or focusing text inputs
  if (bulkCityInput) {
    const activateCity = () => {
      if (bulkApplyCityCheckbox && !bulkApplyCityCheckbox.checked) {
        bulkApplyCityCheckbox.checked = true;
        syncBulkLocationFieldStates();
      }
    };
    bulkCityInput.addEventListener("input", activateCity);
    bulkCityInput.addEventListener("focus", activateCity);
  }
  if (bulkStateInput) {
    const activateState = () => {
      if (bulkApplyStateCheckbox && !bulkApplyStateCheckbox.checked) {
        bulkApplyStateCheckbox.checked = true;
        syncBulkLocationFieldStates();
      }
    };
    bulkStateInput.addEventListener("input", activateState);
    bulkStateInput.addEventListener("focus", activateState);
  }
  if (bulkCountryInput) {
    const activateCountry = () => {
      if (bulkApplyCountryCheckbox && !bulkApplyCountryCheckbox.checked) {
        bulkApplyCountryCheckbox.checked = true;
        syncBulkLocationFieldStates();
      }
    };
    bulkCountryInput.addEventListener("input", activateCountry);
    bulkCountryInput.addEventListener("focus", activateCountry);
  }

  // Bulk Location Confirmation Modal events
  if (bulkLocationConfirmModalClose) bulkLocationConfirmModalClose.addEventListener("click", closeBulkLocationConfirmModal);
  if (bulkLocationConfirmCancelBtn) bulkLocationConfirmCancelBtn.addEventListener("click", closeBulkLocationConfirmModal);
  if (bulkLocationConfirmProceedBtn) bulkLocationConfirmProceedBtn.addEventListener("click", handleConfirmBulkLocationProceed);

  // Main Map Picker Banner events
  if (mainMapPickerDoneBtn) mainMapPickerDoneBtn.addEventListener("click", () => finishMainMapPicking(true));
  if (mainMapPickerCancelBtn) mainMapPickerCancelBtn.addEventListener("click", () => finishMainMapPicking(false));

  // Sortable main table headers
  document.querySelectorAll(".sortable-th:not(.import-sortable-th)").forEach((th) => {
    th.addEventListener("click", () => handleHeaderSort(th.dataset.sort));
  });

  // Sortable Bulk Import preview table headers
  document.querySelectorAll(".import-sortable-th").forEach((th) => {
    th.addEventListener("click", () => handleImportHeaderSort(th.dataset.sort));
  });

  // Use Current Location
  useMyLocBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showToast("Geolocation is not supported by your browser.", true);
      return;
    }
    useMyLocBtn.textContent = "Locating...";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        filterLat.value = pos.coords.latitude.toFixed(6);
        filterLng.value = pos.coords.longitude.toFixed(6);
        useMyLocBtn.textContent = "📍 Use Current Location";
        showToast("Location acquired!");
      },
      (err) => {
        useMyLocBtn.textContent = "📍 Use Current Location";
        showToast(`Could not acquire location: ${err.message}`, true);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  });

  // CSV Export & Interactive Map
  exportCsvBtn.addEventListener("click", exportPoisToCsv);
  visualizeGmapsBtn.addEventListener("click", togglePlacesMap);
  const importBtn = document.getElementById("import-pois-btn");
  if (importBtn) {
    importBtn.addEventListener("click", () => {
      if (typeof window.openImportModal === "function") {
        window.openImportModal();
      }
    });
  }
  if (mapRecenterBtn) mapRecenterBtn.addEventListener("click", fitMapToAllPlaces);
  if (exportKmlBtn) exportKmlBtn.addEventListener("click", exportPoisToKml);
  if (mapCloseBtn) mapCloseBtn.addEventListener("click", closePlacesMap);
  if (mapFilterViewBtn) mapFilterViewBtn.addEventListener("click", () => filterToCurrentMapBounds(true));
  if (mapPinColorsBtn) mapPinColorsBtn.addEventListener("click", openPinColorsModal);
  if (mapClearPinColorsBtn) mapClearPinColorsBtn.addEventListener("click", clearPinColorScheme);
  if (mapSyncViewCheckbox) mapSyncViewCheckbox.addEventListener("change", handleMapSyncToggle);
  if (mapClusterToggle) {
    mapClusterToggle.addEventListener("change", (e) => {
      handleMapClusterToggle(e.target.checked);
    });
  }
  if (pageClusterToggle) {
    pageClusterToggle.addEventListener("change", (e) => {
      handleMapClusterToggle(e.target.checked);
    });
  }
  if (mapTileProviderSelect) {
    mapTileProviderSelect.addEventListener("change", (e) => {
      setMapTileProvider(e.target.value);
    });
  }

  // Add POI Buttons
  if (headerAddPoiBtn) headerAddPoiBtn.addEventListener("click", openCreatePoiModal);
  if (toolbarAddPoiBtn) toolbarAddPoiBtn.addEventListener("click", openCreatePoiModal);

  // Edit / Create Modal Event Listeners
  if (editRecalcAddressBtn) {
    editRecalcAddressBtn.addEventListener("click", () => {
      const latVal = parseFloat(document.getElementById("edit-lat").value);
      const lngVal = parseFloat(document.getElementById("edit-lng").value);
      const hasCoords = !isNaN(latVal) && !isNaN(lngVal) && (latVal !== 0 || lngVal !== 0);

      const originalBtnText = editRecalcAddressBtn.innerHTML;

      if (hasCoords) {
        editRecalcAddressBtn.disabled = true;
        editRecalcAddressBtn.textContent = "Calculating...";
        chrome.runtime.sendMessage(
          {
            action: "REVERSE_GEOCODE",
            payload: { latitude: latVal, longitude: lngVal },
          },
          (response) => {
            editRecalcAddressBtn.disabled = false;
            editRecalcAddressBtn.innerHTML = originalBtnText;

            if (response?.success && response.data) {
              const data = response.data;
              const updatedFields = [];
              if (data.sublocation) {
                const subLocEl = document.getElementById("edit-sublocation");
                if (subLocEl) subLocEl.value = data.sublocation;
                updatedFields.push(`Street: ${data.sublocation}`);
              }
              if (data.city) {
                document.getElementById("edit-city").value = data.city;
                updatedFields.push(`City: ${data.city}`);
              }
              if (data.state) {
                document.getElementById("edit-state").value = data.state;
                updatedFields.push(`State: ${data.state}`);
              }
              if (data.country_code) {
                document.getElementById("edit-country").value = data.country_code;
                updatedFields.push(`Country: ${data.country_code}`);
              }
              if (data.postcode) {
                const zipEl = document.getElementById("edit-zip-code");
                if (zipEl) zipEl.value = data.postcode;
                updatedFields.push(`Zip: ${data.postcode}`);
              }
              if (updatedFields.length > 0) {
                showToast(`Address recalculated! Updated: ${updatedFields.join(", ")}`);
              } else {
                showToast("Reverse geocoding returned no address details for these coordinates.", true);
              }
            } else {
              showToast(response?.error || "Could not recalculate address from coordinates.", true);
            }
          }
        );
      } else {
        const poiName = document.getElementById("edit-name").value.trim();
        if (!poiName) {
          showToast("Please enter coordinates or a place name to recalculate address.", true);
          return;
        }

        editRecalcAddressBtn.disabled = true;
        editRecalcAddressBtn.textContent = "Geocoding...";
        chrome.runtime.sendMessage(
          {
            action: "GEOCODE_QUERY",
            payload: { query: poiName },
          },
          (response) => {
            editRecalcAddressBtn.disabled = false;
            editRecalcAddressBtn.innerHTML = originalBtnText;

            if (response?.success && response.data) {
              const data = response.data;
              const updatedFields = [];
              if (data.latitude !== null && data.latitude !== undefined && data.longitude !== null && data.longitude !== undefined) {
                document.getElementById("edit-lat").value = Number(data.latitude).toFixed(6);
                document.getElementById("edit-lng").value = Number(data.longitude).toFixed(6);
                updatedFields.push(`Coords (${Number(data.latitude).toFixed(4)}, ${Number(data.longitude).toFixed(4)})`);
              }
              if (data.sublocation) {
                const subLocEl = document.getElementById("edit-sublocation");
                if (subLocEl) subLocEl.value = data.sublocation;
                updatedFields.push(`Street: ${data.sublocation}`);
              }
              if (data.city) {
                document.getElementById("edit-city").value = data.city;
                updatedFields.push(`City: ${data.city}`);
              }
              if (data.state) {
                document.getElementById("edit-state").value = data.state;
                updatedFields.push(`State: ${data.state}`);
              }
              if (data.country_code) {
                document.getElementById("edit-country").value = data.country_code;
                updatedFields.push(`Country: ${data.country_code}`);
              }
              if (data.postcode) {
                const zipEl = document.getElementById("edit-zip-code");
                if (zipEl) zipEl.value = data.postcode;
                updatedFields.push(`Zip: ${data.postcode}`);
              }
              if (updatedFields.length > 0) {
                showToast(`Address & location resolved for "${poiName}"! Updated: ${updatedFields.join(", ")}`);
              } else {
                showToast(`No address found for "${poiName}".`, true);
              }
            } else {
              showToast(response?.error || `Could not geocode "${poiName}".`, true);
            }
          }
        );
      }
    });
  }

  if (editUseGpsBtn) {
    editUseGpsBtn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        showToast("Geolocation is not supported by your browser.", true);
        return;
      }
      editUseGpsBtn.textContent = "Locating...";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          editUseGpsBtn.textContent = "📍 Current GPS";
          document.getElementById("edit-lat").value = pos.coords.latitude.toFixed(6);
          document.getElementById("edit-lng").value = pos.coords.longitude.toFixed(6);
          showToast("Location coordinates captured from GPS!");
        },
        (err) => {
          editUseGpsBtn.textContent = "📍 Current GPS";
          showToast(`Could not acquire GPS location: ${err.message}`, true);
        },
        { timeout: 10000, enableHighAccuracy: true }
      );
    });
  }

  editModalClose.addEventListener("click", closeEditModal);
  editCancelBtn.addEventListener("click", closeEditModal);
  editSaveBtn.addEventListener("click", handleSavePoi);
  if (editDeleteBtn) editDeleteBtn.addEventListener("click", handleDeleteFromEditModal);
  if (editCloneBtn) editCloneBtn.addEventListener("click", handleClonePoi);
  const editPoiMergeFromBtn = document.getElementById("edit-poi-merge-from-btn");
  if (editPoiMergeFromBtn) {
    editPoiMergeFromBtn.addEventListener("click", () => {
      if (currentEditingPoi) openPoiMergeModal({ role: "keep", poi: currentEditingPoi });
    });
  }
  const editPoiMergeToBtn = document.getElementById("edit-poi-merge-to-btn");
  if (editPoiMergeToBtn) {
    editPoiMergeToBtn.addEventListener("click", () => {
      if (currentEditingPoi) openPoiMergeModal({ role: "delete", poi: currentEditingPoi });
    });
  }

  // Live duplicate checking on draft entries
  ["edit-name", "edit-lat", "edit-lng"].forEach((id) => {
    const inputEl = document.getElementById(id);
    if (inputEl) {
      inputEl.addEventListener("input", () => {
        if (!currentEditingPoi) {
          clearTimeout(duplicateCheckTimeout);
          duplicateCheckTimeout = setTimeout(() => {
            runDuplicateCheckOnCurrentDraft();
          }, 450);
        }
      });
    }
  });

  // Tags in Edit Modal
  addTagBtn.addEventListener("click", handleAddNewTagToModal);
  newTagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddNewTagToModal();
    }
  });

  editPresetTags.addEventListener("click", (e) => {
    const btn = e.target.closest(".tag-pill-btn");
    if (btn && btn.dataset.tag) {
      addTagToEditingList(btn.dataset.tag);
    }
  });

  // Delete Modal Event Listeners
  deleteModalClose.addEventListener("click", closeDeleteModal);
  deleteCancelBtn.addEventListener("click", closeDeleteModal);
  deleteConfirmBtn.addEventListener("click", handleConfirmDelete);

  // Auth Modal Event Listeners
  if (authModalClose) authModalClose.addEventListener("click", closeAuthModal);
  if (authModal) {
    authModal.addEventListener("click", (e) => {
      if (e.target === authModal) closeAuthModal();
    });
  }
  if (authToggleMode) {
    authToggleMode.addEventListener("click", () => {
      openAuthModal(isAuthRegisterMode ? "login" : "register");
    });
  }
  if (authForm) {
    authForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = authEmail.value.trim();
      const password = authPassword.value;
      if (!email || !password) return;

      authSubmitBtn.disabled = true;
      authSubmitBtn.textContent = isAuthRegisterMode ? "Registering..." : "Signing in...";
      if (authErrorMsg) authErrorMsg.style.display = "none";

      const action = isAuthRegisterMode ? "REGISTER" : "LOGIN";
      chrome.runtime.sendMessage({ action, payload: { email, password } }, (res) => {
        authSubmitBtn.disabled = false;
        authSubmitBtn.textContent = isAuthRegisterMode ? "Register" : "Sign In";

        if (res?.success) {
          closeAuthModal();
          showToast(`Welcome, ${email}!`);
          checkAuth();
          fetchPois();
          loadLists();
          loadTags();
        } else {
          if (authErrorMsg) {
            authErrorMsg.textContent = res?.error || "Authentication failed. Check your credentials.";
            authErrorMsg.style.display = "block";
          }
        }
      });
    });
  }

  initPinColorsModalListeners();
}

function resetAllFilters() {
  keywordSearch.value = "";
  clearSearchBtn.style.display = "none";
  filterCity.value = "";
  filterState.value = "";
  filterCountry.value = "";
  filterTag.value = "";
  filterList.value = "";
  if (filterLocationStatus) filterLocationStatus.value = "";
  if (filterVisitedStatus) filterVisitedStatus.value = "";
  filterLat.value = "";
  filterLng.value = "";
  filterRadius.value = "25";
  if (paneCoords) paneCoords.style.display = "none";
  if (toggleCoordsBtn) toggleCoordsBtn.classList.remove("active");
  clearMapBoundsFilter(false);
  selectedPoiIds.clear();
  fetchPois(true);
  showToast("All filters and map scope reset.");
}

// ==========================================
// API Calls via Service Worker
// ==========================================
async function loadLists() {
  chrome.runtime.sendMessage({ action: "GET_LISTS" }, (response) => {
    if (response?.success && Array.isArray(response.data)) {
      availableLists = response.data;
      filterList.innerHTML = '<option value="">-- All Lists --</option>';
      availableLists.forEach((lst) => {
        const opt = document.createElement("option");
        opt.value = lst.id;
        opt.textContent = `${lst.title} ${lst.is_trip ? "✈️" : "📁"}`;
        filterList.appendChild(opt);
      });
    }
  });
}

async function loadTags() {
  chrome.runtime.sendMessage({ action: "GET_TAGS" }, (response) => {
    if (response?.success && Array.isArray(response.data)) {
      availableTags = response.data.map((t) => t.name || t);
      availableTagsList.innerHTML = "";
      quickTagsBar.innerHTML = '<span class="quick-tag-label">Quick tag:</span>';

      availableTags.forEach((tagName) => {
        const opt = document.createElement("option");
        opt.value = tagName;
        availableTagsList.appendChild(opt);

        // First 8 tags as quick chips
        if (quickTagsBar.children.length < 10) {
          const chip = document.createElement("span");
          chip.className = "quick-tag-chip";
          chip.textContent = tagName;
          chip.addEventListener("click", () => {
            filterTag.value = tagName;
            fetchPois();
          });
          quickTagsBar.appendChild(chip);
        }
      });
    }
  });
}

async function fetchPois(preserveMapView = false) {
  poisTableBody.innerHTML = '<tr><td colspan="10" class="loading-state">Querying database...</td></tr>';
  resultsCountText.textContent = "Loading...";

  const payload = { limit: 5000 };

  // Search keyword
  const searchVal = keywordSearch.value.trim();
  if (searchVal) {
    payload.search = searchVal;
  }

  // Cooperative filters
  if (filterCity.value.trim()) payload.city = filterCity.value.trim();
  if (filterState.value.trim()) payload.state = filterState.value.trim();
  if (filterCountry.value.trim()) {
    const rawC = filterCountry.value.trim();
    const mappedC = mapCountryNameToAlpha2(rawC);
    const resolvedC = mappedC || rawC;
    payload.country = resolvedC;
    if (mappedC && filterCountry.value !== mappedC) {
      filterCountry.value = mappedC;
    }
  }
  if (filterTag.value.trim()) payload.tag = filterTag.value.trim();
  if (filterList.value) payload.list_id = filterList.value;

  if (filterLocationStatus && filterLocationStatus.value) {
    if (filterLocationStatus.value === "with_location") {
      payload.has_location = true;
    } else if (filterLocationStatus.value === "without_location") {
      payload.has_location = false;
    }
  }

  if (filterVisitedStatus && filterVisitedStatus.value) {
    payload.visited_status = filterVisitedStatus.value;
  }

  const lat = parseFloat(filterLat.value);
  const lng = parseFloat(filterLng.value);
  const radius = parseFloat(filterRadius.value) || 25;
  if (!isNaN(lat) && !isNaN(lng)) {
    payload.lat = lat;
    payload.lng = lng;
    payload.radius_miles = radius;
  }

  // Map view bounding box filter
  if (mapBoundsFilter) {
    payload.min_lat = Number(mapBoundsFilter.south.toFixed(6));
    payload.max_lat = Number(mapBoundsFilter.north.toFixed(6));
    payload.min_lng = Number(mapBoundsFilter.west.toFixed(6));
    payload.max_lng = Number(mapBoundsFilter.east.toFixed(6));
  }

  updateActiveFilterChips(payload);

  chrome.runtime.sendMessage({ action: "GET_POIS", payload }, (response) => {
    if (response?.success && Array.isArray(response.data)) {
      allPois = response.data;
      applySort();

      // Client-side bounding box safety check if map bounds filter is active
      if (mapBoundsFilter) {
        filteredPois = allPois.filter((p) => {
          if (!hasValidCoordinates(p)) return false;
          const lat = Number(p.latitude);
          const lng = Number(p.longitude);
          const inLat = lat >= mapBoundsFilter.south && lat <= mapBoundsFilter.north;
          let inLng = false;
          if (mapBoundsFilter.west <= mapBoundsFilter.east) {
            inLng = lng >= mapBoundsFilter.west && lng <= mapBoundsFilter.east;
          } else {
            inLng = lng >= mapBoundsFilter.west || lng <= mapBoundsFilter.east;
          }
          return inLat && inLng;
        });
      } else {
        filteredPois = allPois;
      }

      // Client-side safety check for visit status
      if (filterVisitedStatus && filterVisitedStatus.value) {
        const vs = filterVisitedStatus.value;
        filteredPois = filteredPois.filter((p) => {
          const hasDate = Boolean(p.visit_date || (Array.isArray(p.visit_dates) && p.visit_dates.length > 0));
          if (vs === "visited") return hasDate;
          if (vs === "not_visited") return !hasDate;
          if (vs === "to_see") return !hasDate || Boolean(p.visit_again);
          return true;
        });
      }

      // Synchronize selection: prune selectedPoiIds so only places currently visible in the filtered/zoomed view remain selected
      const visibleIds = new Set(filteredPois.map((p) => p.id));
      for (const id of Array.from(selectedPoiIds)) {
        if (!visibleIds.has(id)) {
          selectedPoiIds.delete(id);
        }
      }

      renderTable(filteredPois);
      updateSelectionToolbar();
      const scopeSuffix = mapBoundsFilter ? " (in map view)" : "";
      resultsCountText.textContent = `${filteredPois.length} place${filteredPois.length === 1 ? "" : "s"} found${scopeSuffix}`;
      if (poisBadgeCount) poisBadgeCount.textContent = allPois.length;
      checkAndApplyAutoClustering(filteredPois);
      if (mapContainerCard && mapContainerCard.style.display !== "none") {
        plotPlacesOnMap(preserveMapView || !!mapBoundsFilter);
      }
    } else {
      const isUnauth = response?.unauthorized || (response?.error && response.error.toLowerCase().includes("auth"));
      if (isUnauth) {
        poisTableBody.innerHTML = `
          <tr><td colspan="10" class="empty-state" style="padding: 40px 20px;">
            <div style="font-size: 24px; margin-bottom: 8px;">🔐</div>
            <div style="font-weight: 700; font-size: 16px; margin-bottom: 6px; color: #1e293b;">Sign In Required</div>
            <div style="color: #64748b; font-size: 13px; margin-bottom: 16px; max-width: 400px; margin-left: auto; margin-right: auto;">
              Sign in with your Vistarae account to view and visualize your saved places and photo locations.
            </div>
            <button type="button" class="btn btn-primary" id="empty-state-signin-btn">Sign In to Vistarae</button>
          </td></tr>
        `;
        const signInBtn = document.getElementById("empty-state-signin-btn");
        if (signInBtn) signInBtn.onclick = () => openAuthModal("login");
      } else {
        poisTableBody.innerHTML = `<tr><td colspan="10" class="empty-state">Error fetching places: ${response?.error || "Backend unreachable"}</td></tr>`;
      }
      resultsCountText.textContent = "0 places found";
      if (poisBadgeCount) poisBadgeCount.textContent = "0";
      showToast(response?.error || "Failed to load POIs", true);
    }
  });
}

function updateActiveFilterChips(payload) {
  if (!activeFiltersChipsBar) return;
  activeFiltersChipsBar.innerHTML = "";

  const chips = [];
  if (payload.search) {
    chips.push({
      label: `Search: "${payload.search}"`,
      clear: () => { keywordSearch.value = ""; clearSearchBtn.style.display = "none"; fetchPois(true); },
    });
  }
  if (payload.city) {
    chips.push({
      label: `City: ${payload.city}`,
      clear: () => { filterCity.value = ""; fetchPois(true); },
    });
  }
  if (payload.state) {
    chips.push({
      label: `State: ${payload.state}`,
      clear: () => { filterState.value = ""; fetchPois(true); },
    });
  }
  if (payload.country) {
    chips.push({
      label: `Country: ${payload.country}`,
      clear: () => { filterCountry.value = ""; fetchPois(true); },
    });
  }
  if (payload.tag) {
    chips.push({
      label: `Tag: ${payload.tag}`,
      clear: () => { filterTag.value = ""; fetchPois(true); },
    });
  }
  if (payload.list_id) {
    const listObj = availableLists.find((l) => l.id === payload.list_id);
    chips.push({
      label: `List: ${listObj ? listObj.title : payload.list_id}`,
      clear: () => { filterList.value = ""; fetchPois(true); },
    });
  }
  if (filterLocationStatus && filterLocationStatus.value) {
    const isWith = filterLocationStatus.value === "with_location";
    chips.push({
      label: `Status: ${isWith ? "With Location" : "Without Location"}`,
      clear: () => { filterLocationStatus.value = ""; fetchPois(true); },
    });
  }
  if (filterVisitedStatus && filterVisitedStatus.value) {
    const val = filterVisitedStatus.value;
    const labelMap = {
      visited: "Visited",
      not_visited: "Not Visited",
      to_see: "To See"
    };
    chips.push({
      label: `Visit: ${labelMap[val] || val}`,
      clear: () => { filterVisitedStatus.value = ""; fetchPois(true); },
    });
  }
  if (payload.lat !== undefined && payload.lng !== undefined) {
    chips.push({
      label: `Near (${payload.lat}, ${payload.lng}) ±${payload.radius_miles}mi`,
      clear: () => { filterLat.value = ""; filterLng.value = ""; fetchPois(true); },
    });
  }
  if (mapBoundsFilter) {
    const latSpan = `${mapBoundsFilter.south.toFixed(2)}° to ${mapBoundsFilter.north.toFixed(2)}°`;
    const lngSpan = `${mapBoundsFilter.west.toFixed(2)}° to ${mapBoundsFilter.east.toFixed(2)}°`;
    chips.push({
      label: `Map View Scope: [${latSpan}, ${lngSpan}]`,
      clear: () => {
        clearMapBoundsFilter(true);
      },
    });
  }

  if (chips.length > 0) {
    activeFiltersChipsBar.style.display = "flex";
    const labelSpan = document.createElement("span");
    labelSpan.style.fontSize = "12px";
    labelSpan.style.fontWeight = "600";
    labelSpan.style.color = "var(--text-muted)";
    labelSpan.textContent = "Active Filters:";
    activeFiltersChipsBar.appendChild(labelSpan);

    chips.forEach((c) => {
      const chip = document.createElement("span");
      chip.className = "filter-chip";
      chip.innerHTML = `<span>${escapeHtml(c.label)}</span><button type="button" class="filter-chip-remove" title="Remove filter">&times;</button>`;
      chip.querySelector(".filter-chip-remove").addEventListener("click", c.clear);
      activeFiltersChipsBar.appendChild(chip);
    });

    if (activeFilterBadge) {
      activeFilterBadge.style.display = "inline-block";
      activeFilterBadge.textContent = `${chips.length} filter${chips.length === 1 ? "" : "s"} applied`;
    }
  } else {
    activeFiltersChipsBar.style.display = "none";
    if (activeFilterBadge) activeFilterBadge.style.display = "none";
  }
}

// ==========================================
// Sorting Logic
// ==========================================
function applySort() {
  const { column, direction } = currentSort;
  allPois.sort((a, b) => {
    let valA = a[column];
    let valB = b[column];

    if (column === "location") {
      valA = [a.iptc_city, a.iptc_province_state, a.iptc_country_code].filter(Boolean).join(", ");
      valB = [b.iptc_city, b.iptc_province_state, b.iptc_country_code].filter(Boolean).join(", ");
    } else if (column === "coords") {
      valA = a.latitude !== undefined ? a.latitude : -999;
      valB = b.latitude !== undefined ? b.latitude : -999;
    } else if (column === "rating") {
      valA = a.personal_rating || 0;
      valB = b.personal_rating || 0;
    } else if (column === "visited") {
      valA = a.visited ? (a.visit_date || "9999") : "";
      valB = b.visited ? (b.visit_date || "9999") : "";
    }

    if (valA === null || valA === undefined) valA = "";
    if (valB === null || valB === undefined) valB = "";

    let comp = 0;
    if (typeof valA === "number" && typeof valB === "number") {
      comp = valA - valB;
    } else if (column === "created_at") {
      comp = new Date(valA || 0).getTime() - new Date(valB || 0).getTime();
    } else {
      comp = String(valA).localeCompare(String(valB), undefined, { sensitivity: "base", numeric: true });
    }

    return direction === "asc" ? comp : -comp;
  });
  filteredPois = allPois;
  updateSortHeaderIndicators();
}

function handleHeaderSort(column) {
  if (!column) return;
  if (currentSort.column === column) {
    currentSort.direction = currentSort.direction === "asc" ? "desc" : "asc";
  } else {
    currentSort.column = column;
    currentSort.direction = (column === "created_at" || column === "rating") ? "desc" : "asc";
  }
  applySort();
  renderTable(filteredPois);
}

function updateSortHeaderIndicators() {
  document.querySelectorAll(".sortable-th:not(.import-sortable-th)").forEach((th) => {
    const col = th.dataset.sort;
    const indicator = th.querySelector(".sort-indicator");
    if (col === currentSort.column) {
      th.classList.add("sorted");
      if (indicator) indicator.textContent = currentSort.direction === "asc" ? "▲" : "▼";
    } else {
      th.classList.remove("sorted");
      if (indicator) indicator.textContent = "⇅";
    }
  });
}

// ==========================================
// Bulk Selection & Actions Logic
// ==========================================
function updateSelectionToolbar() {
  const count = selectedPoiIds.size;
  if (bulkSelectedCount) bulkSelectedCount.textContent = count;

  if (bulkActionsToolbar) {
    bulkActionsToolbar.style.display = count > 0 ? "flex" : "none";
  }

  if (selectAllCheckbox) {
    const visibleCount = filteredPois.length;
    if (visibleCount > 0 && count === visibleCount) {
      selectAllCheckbox.checked = true;
      selectAllCheckbox.indeterminate = false;
    } else if (count > 0 && count < visibleCount) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = true;
    } else {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    }
  }
}

function handleToggleSelectAll(isChecked) {
  if (isChecked) {
    filteredPois.forEach((p) => selectedPoiIds.add(p.id));
  } else {
    selectedPoiIds.clear();
  }
  renderTable(filteredPois);
  updateSelectionToolbar();
}

function handleClearSelection() {
  selectedPoiIds.clear();
  renderTable(filteredPois);
  updateSelectionToolbar();
}

// 1. Bulk Delete Modal
function openBulkDeleteModal() {
  if (selectedPoiIds.size === 0) return;
  if (bulkDeleteCountDisplay) bulkDeleteCountDisplay.textContent = selectedPoiIds.size;
  if (bulkDeletePreviewList) {
    const selectedList = filteredPois.filter((p) => selectedPoiIds.has(p.id));
    const previewNames = selectedList.slice(0, 6).map((p) => `• ${escapeHtml(p.name)}`);
    if (selectedList.length > 6) {
      previewNames.push(`... and ${selectedList.length - 6} more`);
    }
    bulkDeletePreviewList.innerHTML = previewNames.join("<br>");
  }
  if (bulkDeleteModal) bulkDeleteModal.style.display = "flex";
}

function closeBulkDeleteModal() {
  if (bulkDeleteModal) bulkDeleteModal.style.display = "none";
}

async function handleConfirmBulkDelete() {
  if (selectedPoiIds.size === 0) return;
  bulkDeleteConfirmBtn.disabled = true;
  bulkDeleteConfirmBtn.textContent = "Deleting...";

  chrome.runtime.sendMessage(
    {
      action: "BULK_DELETE_POIS",
      payload: { poi_ids: Array.from(selectedPoiIds) },
    },
    (res) => {
      bulkDeleteConfirmBtn.disabled = false;
      bulkDeleteConfirmBtn.textContent = "Delete Selected Places";
      closeBulkDeleteModal();

      if (res?.success) {
        showToast(`Successfully deleted ${res.data?.affected_count || selectedPoiIds.size} places.`);
        selectedPoiIds.clear();
        fetchPois();
      } else {
        showToast(`Failed to delete places: ${res?.error || "Unknown error"}`, true);
      }
    }
  );
}

// 2. Bulk Tags Modal
function openBulkTagsModal() {
  if (selectedPoiIds.size === 0) return;
  if (bulkTagsCountDisplay) bulkTagsCountDisplay.textContent = selectedPoiIds.size;
  if (bulkAddTagsInput) bulkAddTagsInput.value = "";
  if (bulkRemoveTagsInput) bulkRemoveTagsInput.value = "";
  if (bulkTagsModal) bulkTagsModal.style.display = "flex";
}

function closeBulkTagsModal() {
  if (bulkTagsModal) bulkTagsModal.style.display = "none";
}

async function handleApplyBulkTags() {
  if (selectedPoiIds.size === 0) return;

  const addRaw = bulkAddTagsInput.value;
  const removeRaw = bulkRemoveTagsInput.value;

  const add_tags = addRaw.split(",").map((t) => t.trim()).filter(Boolean);
  const remove_tags = removeRaw.split(",").map((t) => t.trim()).filter(Boolean);

  if (add_tags.length === 0 && remove_tags.length === 0) {
    showToast("Please enter at least one tag to add or remove.", true);
    return;
  }

  bulkTagsApplyBtn.disabled = true;
  bulkTagsApplyBtn.textContent = "Applying...";

  chrome.runtime.sendMessage(
    {
      action: "BULK_UPDATE_POIS",
      payload: {
        poi_ids: Array.from(selectedPoiIds),
        add_tags,
        remove_tags,
      },
    },
    (res) => {
      bulkTagsApplyBtn.disabled = false;
      bulkTagsApplyBtn.textContent = "Apply Tags";
      closeBulkTagsModal();

      if (res?.success) {
        showToast(`Updated tags on ${res.data?.affected_count || selectedPoiIds.size} places.`);
        selectedPoiIds.clear();
        fetchPois(true);
      } else {
        showToast(`Failed to update tags: ${res?.error || "Unknown error"}`, true);
      }
    }
  );
}

// 3. Bulk Location Modal & Drag-and-Drop Map Picker
function createDraggablePinIcon(label = "Drag to Position") {
  return L.divIcon({
    className: "bulk-drag-pin-container",
    html: `
      <div style="display: flex; flex-direction: column; align-items: center; cursor: grab;" title="Drag & drop to set location">
        <span class="bulk-drag-pin-badge">${escapeHtml(label)}</span>
        <svg width="34" height="34" viewBox="0 0 24 24" fill="#0d9488">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
        </svg>
      </div>
    `,
    iconSize: [80, 52],
    iconAnchor: [40, 48],
  });
}

function syncBulkLocationFieldStates() {
  // 1. Coordinates
  const coordsActive = !!bulkApplyCoordsCheckbox?.checked;
  if (bulkCoordsBox) bulkCoordsBox.classList.toggle("active", coordsActive);
  if (bulkCoordsBody) {
    bulkCoordsBody.style.opacity = coordsActive ? "1.0" : "0.55";
  }
  if (bulkLatInput) bulkLatInput.disabled = !coordsActive || !!bulkClearLocationCheckbox?.checked;
  if (bulkLngInput) bulkLngInput.disabled = !coordsActive || !!bulkClearLocationCheckbox?.checked;
  if (bulkClearLocationCheckbox) bulkClearLocationCheckbox.disabled = !coordsActive;

  const lat = parseFloat(bulkLatInput?.value);
  const lng = parseFloat(bulkLngInput?.value);
  updateBulkMapStatusHint(lat, lng);

  // 2. City
  const cityActive = !!bulkApplyCityCheckbox?.checked;
  if (bulkCityBox) bulkCityBox.classList.toggle("active", cityActive);
  if (bulkCityInput) {
    bulkCityInput.style.opacity = cityActive ? "1.0" : "0.75";
  }

  // 3. State
  const stateActive = !!bulkApplyStateCheckbox?.checked;
  if (bulkStateBox) bulkStateBox.classList.toggle("active", stateActive);
  if (bulkStateInput) {
    bulkStateInput.style.opacity = stateActive ? "1.0" : "0.75";
  }

  // 4. Country
  const countryActive = !!bulkApplyCountryCheckbox?.checked;
  if (bulkCountryBox) bulkCountryBox.classList.toggle("active", countryActive);
  if (bulkCountryInput) {
    bulkCountryInput.style.opacity = countryActive ? "1.0" : "0.75";
  }
}

function openBulkLocationModal() {
  if (selectedPoiIds.size === 0) return;
  if (bulkLocationCountDisplay) bulkLocationCountDisplay.textContent = selectedPoiIds.size;
  if (bulkLatInput) {
    bulkLatInput.value = "";
  }
  if (bulkLngInput) {
    bulkLngInput.value = "";
  }
  if (bulkClearLocationCheckbox) {
    bulkClearLocationCheckbox.checked = false;
  }
  if (bulkCityInput) bulkCityInput.value = "";
  if (bulkStateInput) bulkStateInput.value = "";
  if (bulkCountryInput) bulkCountryInput.value = "";

  // Reset checkboxes of what to apply - unchecked by default so existing attributes are preserved
  if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = false;
  if (bulkApplyCityCheckbox) bulkApplyCityCheckbox.checked = false;
  if (bulkApplyStateCheckbox) bulkApplyStateCheckbox.checked = false;
  if (bulkApplyCountryCheckbox) bulkApplyCountryCheckbox.checked = false;

  syncBulkLocationFieldStates();

  if (bulkLocationModal) bulkLocationModal.style.display = "flex";

  setupBulkLocationMap();
}

function closeBulkLocationModal() {
  if (bulkLocationModal) bulkLocationModal.style.display = "none";
}

function setupBulkLocationMap() {
  const selectedPois = filteredPois.filter((p) => selectedPoiIds.has(p.id));
  const poiWithCoords = selectedPois.find(hasValidCoordinates);

  let initialLat = 39.8283;
  let initialLng = -98.5795;
  let initialZoom = 4;
  let hasValidCoords = false;

  if (poiWithCoords) {
    initialLat = poiWithCoords.latitude;
    initialLng = poiWithCoords.longitude;
    initialZoom = 13;
    hasValidCoords = true;
  } else if (leafletMap && typeof leafletMap.getCenter === "function") {
    const c = leafletMap.getCenter();
    initialLat = c.lat;
    initialLng = c.lng;
    initialZoom = leafletMap.getZoom() || 11;
  }

  const mapContainer = document.getElementById("bulk-location-map");
  if (!mapContainer || typeof L === "undefined") return;

  if (!bulkLocationMap) {
    bulkLocationMap = L.map("bulk-location-map", {
      zoomControl: true,
      scrollWheelZoom: true,
    });

    const provider = MAP_TILE_PROVIDERS[selectedTileProvider] || MAP_TILE_PROVIDERS["google-roadmap"];
    L.tileLayer(provider.url, provider.options).addTo(bulkLocationMap);

    bulkLocationMarker = L.marker([initialLat, initialLng], {
      draggable: true,
      icon: createDraggablePinIcon("Drag to Position"),
    }).addTo(bulkLocationMap);

    bulkLocationMarker.on("dragend", () => {
      const pos = bulkLocationMarker.getLatLng();
      if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = true;
      applyCoordsToBulkInputs(pos.lat, pos.lng);
    });

    bulkLocationMap.on("click", (e) => {
      if (bulkClearLocationCheckbox?.checked) return;
      if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = true;
      bulkLocationMarker.setLatLng(e.latlng);
      applyCoordsToBulkInputs(e.latlng.lat, e.latlng.lng);
    });

    const onManualCoordInput = () => {
      if (bulkClearLocationCheckbox?.checked) return;
      if (bulkApplyCoordsCheckbox && !bulkApplyCoordsCheckbox.checked) {
        bulkApplyCoordsCheckbox.checked = true;
      }
      const lat = parseFloat(bulkLatInput.value);
      const lng = parseFloat(bulkLngInput.value);
      if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
        bulkLocationMarker.setLatLng([lat, lng]);
        bulkLocationMap.panTo([lat, lng]);
      }
      syncBulkLocationFieldStates();
    };
    if (bulkLatInput) bulkLatInput.addEventListener("input", onManualCoordInput);
    if (bulkLngInput) bulkLngInput.addEventListener("input", onManualCoordInput);
  } else {
    if (bulkLocationMarker) {
      bulkLocationMarker.setOpacity(1.0);
      bulkLocationMarker.setLatLng([initialLat, initialLng]);
    }
  }

  if (hasValidCoords) {
    applyCoordsToBulkInputs(initialLat, initialLng);
  } else {
    syncBulkLocationFieldStates();
  }

  bulkLocationMap.setView([initialLat, initialLng], initialZoom);

  setTimeout(() => {
    if (bulkLocationMap) bulkLocationMap.invalidateSize();
  }, 150);
}

function applyCoordsToBulkInputs(lat, lng) {
  if (bulkLatInput) {
    bulkLatInput.value = Number(lat).toFixed(6);
  }
  if (bulkLngInput) {
    bulkLngInput.value = Number(lng).toFixed(6);
  }
  if (bulkClearLocationCheckbox) {
    bulkClearLocationCheckbox.checked = false;
  }
  if (bulkLocationMarker) {
    bulkLocationMarker.setOpacity(1.0);
  }
  syncBulkLocationFieldStates();
}

function updateBulkMapStatusHint(lat, lng) {
  if (!bulkMapStatusHint) return;
  if (!bulkApplyCoordsCheckbox?.checked) {
    bulkMapStatusHint.textContent = "Unchecked (will keep existing coordinates)";
    bulkMapStatusHint.style.color = "var(--text-muted)";
  } else if (bulkClearLocationCheckbox?.checked) {
    bulkMapStatusHint.textContent = "Coordinates will be cleared";
    bulkMapStatusHint.style.color = "#ef4444";
  } else if (lat !== null && lng !== null && !isNaN(lat) && !isNaN(lng)) {
    bulkMapStatusHint.textContent = `📍 ${Number(lat).toFixed(4)}, ${Number(lng).toFixed(4)}`;
    bulkMapStatusHint.style.color = "#0d9488";
  } else {
    bulkMapStatusHint.textContent = "Drag pin or click map to set location";
    bulkMapStatusHint.style.color = "#0d9488";
  }
}

function startMainMapPicking() {
  if (selectedPoiIds.size === 0) return;
  closeBulkLocationModal();

  if (mapContainerCard && mapContainerCard.style.display === "none") {
    mapContainerCard.style.display = "block";
    visualizeBtnLabel.textContent = "Hide Map";
    initLeafletMapIfNeeded();
    plotPlacesOnMap(false);
  } else {
    initLeafletMapIfNeeded();
  }

  mapContainerCard.scrollIntoView({ behavior: "smooth", block: "start" });

  if (mainMapPickerBanner) {
    mainMapPickerBanner.style.display = "flex";
    if (mainMapPickerCount) mainMapPickerCount.textContent = selectedPoiIds.size;
  }

  let center = leafletMap.getCenter();
  const currentLat = parseFloat(bulkLatInput.value);
  const currentLng = parseFloat(bulkLngInput.value);
  if (!isNaN(currentLat) && !isNaN(currentLng)) {
    center = [currentLat, currentLng];
    leafletMap.setView(center, Math.max(leafletMap.getZoom(), 12));
  }

  if (mainMapPickerMarker) {
    leafletMap.removeLayer(mainMapPickerMarker);
  }

  mainMapPickerMarker = L.marker(center, {
    draggable: true,
    icon: createDraggablePinIcon("Drag to Position"),
    zIndexOffset: 1000,
  }).addTo(leafletMap);

  const updateBannerCoords = (lat, lng) => {
    if (mainMapPickerCoords) {
      mainMapPickerCoords.textContent = `${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}`;
    }
  };
  updateBannerCoords(center.lat || center[0], center.lng || center[1]);

  mainMapPickerMarker.on("dragend", () => {
    const pos = mainMapPickerMarker.getLatLng();
    updateBannerCoords(pos.lat, pos.lng);
  });

  const onMainMapClickPick = (e) => {
    mainMapPickerMarker.setLatLng(e.latlng);
    updateBannerCoords(e.latlng.lat, e.latlng.lng);
  };
  leafletMap.on("click", onMainMapClickPick);

  mainMapPickerMarker._cleanupListener = () => {
    leafletMap.off("click", onMainMapClickPick);
  };
}

function finishMainMapPicking(apply) {
  if (mainMapPickerMarker) {
    if (typeof mainMapPickerMarker._cleanupListener === "function") {
      mainMapPickerMarker._cleanupListener();
    }
    if (apply) {
      const pos = mainMapPickerMarker.getLatLng();
      if (bulkApplyCoordsCheckbox) bulkApplyCoordsCheckbox.checked = true;
      applyCoordsToBulkInputs(pos.lat, pos.lng);
      if (bulkLocationMap) {
        bulkLocationMap.setView(pos, 13);
        if (bulkLocationMarker) bulkLocationMarker.setLatLng(pos);
      }
      syncBulkLocationFieldStates();
    }
    leafletMap.removeLayer(mainMapPickerMarker);
    mainMapPickerMarker = null;
  }

  if (mainMapPickerBanner) {
    mainMapPickerBanner.style.display = "none";
  }

  if (bulkLocationModal) {
    bulkLocationModal.style.display = "flex";
    setTimeout(() => {
      if (bulkLocationMap) bulkLocationMap.invalidateSize();
    }, 150);
  }
}

async function handleApplyBulkLocation() {
  if (selectedPoiIds.size === 0) return;

  const applyCoords = !!bulkApplyCoordsCheckbox?.checked;
  const applyCity = !!bulkApplyCityCheckbox?.checked;
  const applyState = !!bulkApplyStateCheckbox?.checked;
  const applyCountry = !!bulkApplyCountryCheckbox?.checked;

  if (!applyCoords && !applyCity && !applyState && !applyCountry) {
    showToast("Please check at least one field checkbox to apply.", true);
    return;
  }

  const payload = {
    poi_ids: Array.from(selectedPoiIds),
  };

  if (applyCoords) {
    const isClearLoc = bulkClearLocationCheckbox?.checked;
    if (isClearLoc) {
      payload.clear_location = true;
    } else {
      const latStr = bulkLatInput?.value.trim() || "";
      const lngStr = bulkLngInput?.value.trim() || "";
      if (!latStr || !lngStr) {
        showToast("Please provide both latitude and longitude, or check 'Clear coordinates'.", true);
        return;
      }
      const latVal = parseFloat(latStr);
      const lngVal = parseFloat(lngStr);
      if (isNaN(latVal) || isNaN(lngVal)) {
        showToast("Latitude and longitude must be valid numbers.", true);
        return;
      }
      payload.latitude = latVal;
      payload.longitude = lngVal;
    }
  }

  if (applyCity) {
    payload.iptc_city = bulkCityInput.value.trim();
  }

  if (applyState) {
    payload.iptc_province_state = bulkStateInput.value.trim();
  }

  if (applyCountry) {
    const rawCountry = bulkCountryInput.value.trim();
    const mappedCountry = mapCountryNameToAlpha2(rawCountry);
    payload.iptc_country_code = rawCountry ? (mappedCountry || rawCountry).toUpperCase() : "";
  }

  // Prompt the user if they are sure they want to proceed before updating DB records
  openBulkLocationConfirmModal(payload);
}

function openBulkLocationConfirmModal(payload) {
  pendingBulkLocationPayload = payload;

  const count = payload.poi_ids.length;
  if (bulkLocationConfirmCount) bulkLocationConfirmCount.textContent = count;

  let summaryHtml = '<ul style="margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px;">';
  
  if (payload.clear_location) {
    summaryHtml += '<li style="color: #b91c1c; font-weight: 600;">⚠️ <strong>Coordinates:</strong> Clear coordinates (all coordinates removed)</li>';
  } else if (payload.latitude !== undefined && payload.longitude !== undefined) {
    summaryHtml += `<li>📍 <strong>Coordinates:</strong> ${payload.latitude.toFixed(6)}, ${payload.longitude.toFixed(6)}</li>`;
  } else {
    summaryHtml += '<li style="color: #64748b;">📍 <strong>Coordinates:</strong> <em>Unchanged (preserved on all places)</em></li>';
  }

  if (payload.iptc_city !== undefined) {
    if (payload.iptc_city) {
      summaryHtml += `<li>🏙️ <strong>City:</strong> ${escapeHtml(payload.iptc_city)}</li>`;
    } else {
      summaryHtml += '<li style="color: #b91c1c;">🏙️ <strong>City:</strong> <em>Cleared (empty)</em></li>';
    }
  } else {
    summaryHtml += '<li style="color: #64748b;">🏙️ <strong>City:</strong> <em>Unchanged</em></li>';
  }

  if (payload.iptc_province_state !== undefined) {
    if (payload.iptc_province_state) {
      summaryHtml += `<li>🏛️ <strong>State / Province:</strong> ${escapeHtml(payload.iptc_province_state)}</li>`;
    } else {
      summaryHtml += '<li style="color: #b91c1c;">🏛️ <strong>State / Province:</strong> <em>Cleared (empty)</em></li>';
    }
  } else {
    summaryHtml += '<li style="color: #64748b;">🏛️ <strong>State / Province:</strong> <em>Unchanged</em></li>';
  }

  if (payload.iptc_country_code !== undefined) {
    if (payload.iptc_country_code) {
      summaryHtml += `<li>🌍 <strong>Country Code:</strong> ${escapeHtml(payload.iptc_country_code)}</li>`;
    } else {
      summaryHtml += '<li style="color: #b91c1c;">🌍 <strong>Country Code:</strong> <em>Cleared (empty)</em></li>';
    }
  } else {
    summaryHtml += '<li style="color: #64748b;">🌍 <strong>Country Code:</strong> <em>Unchanged</em></li>';
  }
  summaryHtml += '</ul>';

  if (bulkLocationConfirmSummary) {
    bulkLocationConfirmSummary.innerHTML = summaryHtml;
  }

  if (bulkLocationConfirmPreviewList) {
    const selectedPois = filteredPois.filter((p) => selectedPoiIds.has(p.id));
    const items = selectedPois.slice(0, 6).map((p) => `<div style="padding: 2px 0;">• <strong>${escapeHtml(p.name)}</strong></div>`);
    if (selectedPois.length > 6) {
      items.push(`<div style="padding: 2px 0; color: #64748b; font-style: italic;">... and ${selectedPois.length - 6} more place${selectedPois.length - 6 === 1 ? "" : "s"}</div>`);
    }
    bulkLocationConfirmPreviewList.innerHTML = items.join("");
  }

  if (bulkLocationConfirmModal) {
    bulkLocationConfirmModal.style.display = "flex";
  }
}

function closeBulkLocationConfirmModal() {
  if (bulkLocationConfirmModal) {
    bulkLocationConfirmModal.style.display = "none";
  }
  pendingBulkLocationPayload = null;
}

function handleConfirmBulkLocationProceed() {
  if (!pendingBulkLocationPayload) return;

  bulkLocationConfirmProceedBtn.disabled = true;
  bulkLocationConfirmProceedBtn.textContent = "Updating DB...";

  chrome.runtime.sendMessage(
    {
      action: "BULK_UPDATE_POIS",
      payload: pendingBulkLocationPayload,
    },
    (res) => {
      bulkLocationConfirmProceedBtn.disabled = false;
      bulkLocationConfirmProceedBtn.textContent = "Yes, Update Records";
      closeBulkLocationConfirmModal();
      closeBulkLocationModal();

      if (res?.success) {
        showToast(`Successfully updated location on ${res.data?.affected_count || selectedPoiIds.size} places.`);
        selectedPoiIds.clear();
        fetchPois(true);
      } else {
        showToast(`Failed to update location: ${res?.error || "Unknown error"}`, true);
      }
    }
  );
}

// ==========================================
// Table Rendering
// ==========================================
function renderTable(pois) {
  poisTableBody.innerHTML = "";
  if (poisBadgeCount) poisBadgeCount.textContent = allPois.length;

  if (pois.length === 0) {
    poisTableBody.innerHTML = `
      <tr>
        <td colspan="10" class="empty-state" style="padding: 36px 16px; text-align: center;">
          <div style="font-size: 13.5px; color: var(--text-muted); margin-bottom: 10px;">No points of interest match the selected filter criteria.</div>
          <button type="button" class="btn btn-secondary btn-sm" id="empty-state-add-btn" style="margin: 0 auto; display: inline-flex; align-items: center; gap: 6px;">
            <svg viewBox="0 0 24 24" width="13" height="13"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
            Add a New Point of Interest
          </button>
        </td>
      </tr>`;
    document.getElementById("empty-state-add-btn")?.addEventListener("click", openCreatePoiModal);
    return;
  }

  pois.forEach((poi) => {
    const tr = document.createElement("tr");

    // 0. Checkbox
    const tdSelect = document.createElement("td");
    tdSelect.style.textAlign = "center";
    const isSelected = selectedPoiIds.has(poi.id);
    tdSelect.innerHTML = `<input type="checkbox" class="poi-select-checkbox" data-id="${poi.id}" ${isSelected ? "checked" : ""}>`;
    tdSelect.querySelector(".poi-select-checkbox").addEventListener("change", (e) => {
      e.stopPropagation();
      if (e.target.checked) {
        selectedPoiIds.add(poi.id);
        tr.classList.add("row-selected");
      } else {
        selectedPoiIds.delete(poi.id);
        tr.classList.remove("row-selected");
      }
      updateSelectionToolbar();
    });
    tr.appendChild(tdSelect);
    if (isSelected) tr.classList.add("row-selected");

    // 1. Photo
    const tdPhoto = document.createElement("td");
    tdPhoto.className = "poi-thumb-cell";
    const hasCoords = hasValidCoordinates(poi);
    const photoTitleText = hasCoords ? `Zoom to "${poi.name || ""}" on map` : (poi.name || "");

    if (poi.primary_image_url) {
      const img = document.createElement("img");
      img.src = poi.primary_image_url;
      img.className = "poi-thumb";
      img.alt = "Photo";
      img.title = photoTitleText;
      img.onerror = () => {
        const placeholder = document.createElement("div");
        placeholder.className = "poi-thumb-placeholder";
        placeholder.title = photoTitleText;
        placeholder.textContent = "📍";
        if (img.parentNode) {
          img.parentNode.replaceChild(placeholder, img);
        }
      };
      tdPhoto.appendChild(img);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "poi-thumb-placeholder";
      placeholder.title = photoTitleText;
      placeholder.textContent = "📍";
      tdPhoto.appendChild(placeholder);
    }

    tdPhoto.addEventListener("click", () => {
      if (hasCoords) {
        zoomMapToPoiIfDisplayed(poi);
      } else {
        showToast("No coordinates recorded for this place.", false);
      }
    });
    tr.appendChild(tdPhoto);

    // 2. Name & POI Link
    const tdName = document.createElement("td");
    const linkUrl = poi.website_official || poi.source_url || "#";
    const isPhotoSource = poi.source_type && poi.source_type.toLowerCase() === "photo";
    const isFolderUrl = poi.source_url && (isPhotoSource || isLocalOrUncPath(poi.source_url));
    const folderUri = isFolderUrl ? getFolderProtocolUrl(poi.source_url) : "";

    const sourceTypeHtml = poi.source_type
      ? `<span class="source-type-pill source-${escapeHtml(poi.source_type.toLowerCase())}" title="Source: ${escapeHtml(poi.source_type)}">${escapeHtml(poi.source_type)}</span>`
      : "";

    let nameHtml = "";
    if (isFolderUrl) {
      nameHtml = `<a href="${folderUri}" class="poi-name-title poi-name-folder folder-open-link" data-path="${escapeHtml(poi.source_url)}" title="Open folder in File Explorer: ${escapeHtml(poi.source_url)}">${escapeHtml(poi.name)}</a>`;
    } else if (isPhotoSource) {
      nameHtml = `<span class="poi-name-title" title="${escapeHtml(poi.name)}" style="font-weight: 600; color: var(--text-color); cursor: default;">${escapeHtml(poi.name)}</span>`;
    } else {
      nameHtml = `<a href="${escapeHtml(linkUrl)}" target="_blank" class="poi-name-title" title="${escapeHtml(poi.name)}">${escapeHtml(poi.name)}</a>`;
    }

    const folderChipHtml = isFolderUrl
      ? `<a href="${folderUri}" class="folder-chip-link folder-open-link" data-path="${escapeHtml(poi.source_url)}" title="Open photos folder in File Explorer: ${escapeHtml(poi.source_url)}">
          <svg viewBox="0 0 24 24" width="12" height="12"><path fill="currentColor" d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
          <span>Open Photos</span>
        </a>`
      : "";

    const parentPoi = poi.parent_poi_id ? allPois.find(p => p.id === poi.parent_poi_id) : null;
    const parentHtml = parentPoi
      ? `<span class="parent-poi-indicator" style="font-size: 11px; color: #0d9488; font-weight: 500;" title="Parent Macro-Site: ${escapeHtml(parentPoi.name)}">↳ Part of: ${escapeHtml(parentPoi.name)}</span>`
      : "";

    tdName.innerHTML = `
      <div class="poi-name-cell">
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
          ${nameHtml}
          ${sourceTypeHtml}
          ${folderChipHtml}
          ${poi.has_folder_conflict ? `<span class="status-pill status-pill-conflict" style="font-size: 10.5px; padding: 1px 6px;" title="This place has a photo folder conflict with another place">⚠️ Folder Conflict</span>` : ""}
        </div>
        ${parentHtml}
        ${poi.description ? `<span style="font-size: 11px; color: #64748b;">${escapeHtml(poi.description.slice(0, 75))}${poi.description.length > 75 ? "..." : ""}</span>` : ""}
      </div>
    `;
    tr.appendChild(tdName);

    // 3. Type
    const tdType = document.createElement("td");
    const typeClass = `type-${(poi.poi_type || "site-to-see").toLowerCase().replace(/[\s/]+/g, "-")}`;
    tdType.innerHTML = `<span class="poi-type-badge ${typeClass}">${escapeHtml(poi.poi_type || "site to see")}</span>`;
    tr.appendChild(tdType);

    // 4. Location (City, State, Country)
    const tdLoc = document.createElement("td");
    const locParts = [poi.iptc_city, poi.iptc_province_state, poi.iptc_country_code].filter(Boolean);
    tdLoc.textContent = locParts.length > 0 ? locParts.join(", ") : "—";
    tr.appendChild(tdLoc);

    // 5. Coordinates
    const tdCoords = document.createElement("td");
    if (hasCoords) {
      const gmapsLink = `https://www.google.com/maps/search/?api=1&query=${poi.latitude},${poi.longitude}`;
      tdCoords.innerHTML = `
        <a href="${gmapsLink}" target="_blank" class="coord-link" title="Open in Google Maps">
          ${Number(poi.latitude).toFixed(4)}, ${Number(poi.longitude).toFixed(4)} ↗
        </a>
      `;
    } else {
      tdCoords.textContent = "—";
    }
    tr.appendChild(tdCoords);

    // 6. Rating & Tags
    const tdRatingTags = document.createElement("td");
    let stars = "";
    if (poi.personal_rating) {
      stars = `<div class="rating-stars">${"★".repeat(poi.personal_rating)}${"☆".repeat(5 - poi.personal_rating)}</div>`;
    }
    let tagsHtml = "";
    if (Array.isArray(poi.category_tags) && poi.category_tags.length > 0) {
      tagsHtml = `<div class="tags-list">` + poi.category_tags.slice(0, 4).map((t) => {
        const isNps = t.toUpperCase() === "NPS";
        return `<span class="tag-badge ${isNps ? "tag-nps" : ""}">${escapeHtml(t)}</span>`;
      }).join("") + (poi.category_tags.length > 4 ? `<span class="tag-badge">+${poi.category_tags.length - 4}</span>` : "") + `</div>`;
    }
    tdRatingTags.innerHTML = stars + tagsHtml;
    tr.appendChild(tdRatingTags);

    // 7. Visit Info
    const tdVisit = document.createElement("td");
    const visitDetails = [];
    if (poi.indoor_outdoor) visitDetails.push(poi.indoor_outdoor);
    if (poi.estimated_duration) visitDetails.push(poi.estimated_duration);
    if (poi.cost_tier) visitDetails.push(poi.cost_tier);
    if (poi.physical_effort) visitDetails.push(poi.physical_effort);

    let visitedBadge = "";
    if (poi.visited || poi.visit_date) {
      const vDateStr = poi.visit_date ? poi.visit_date.slice(0, 10) : "Visited";
      visitedBadge = `<div style="margin-top: 4px;"><span class="badge" style="background:#dcfce7; color:#15803d; font-size:10.5px; font-weight:600;">✓ ${vDateStr}</span></div>`;
    }
    let visitAgainBadge = "";
    if (poi.visit_again) {
      visitAgainBadge = `<div style="margin-top: 4px;"><span class="badge" style="background:#eff6ff; color:#1d4ed8; font-size:10.5px; font-weight:600;">🔄 Visit Again</span></div>`;
    }
    tdVisit.innerHTML = `<div class="visit-info-box">${visitDetails.length > 0 ? visitDetails.join(" • ") : "—"}</div>${visitedBadge}${visitAgainBadge}`;
    tr.appendChild(tdVisit);

    // 8. Date Captured
    const tdDate = document.createElement("td");
    const d = poi.created_at ? new Date(poi.created_at) : null;
    tdDate.textContent = d ? d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—";
    tdDate.style.fontSize = "12px";
    tdDate.style.color = "#64748b";
    tr.appendChild(tdDate);

    // 9. Actions (Edit, Delete, Map)
    const tdActions = document.createElement("td");
    tdActions.className = "action-buttons-cell";

    // Edit button
    const editBtn = document.createElement("button");
    editBtn.className = "action-icon-btn";
    editBtn.title = "Edit Details";
    editBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a.996.996 0 0 0 0-1.41l-2.34-2.34a.996.996 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
    editBtn.addEventListener("click", () => openEditModal(poi));

    // Delete button
    const delBtn = document.createElement("button");
    delBtn.className = "action-icon-btn delete-btn";
    delBtn.title = "Delete Entry";
    delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
    delBtn.addEventListener("click", () => openDeleteModal(poi));

    // Google Maps pin button
    const mapBtn = document.createElement("a");
    mapBtn.className = "action-icon-btn";
    mapBtn.title = "View on Google Maps";
    mapBtn.target = "_blank";
    mapBtn.href = `https://www.google.com/maps/search/?api=1&query=${poi.latitude},${poi.longitude}`;
    mapBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>';

    tdActions.appendChild(editBtn);
    tdActions.appendChild(delBtn);
    tdActions.appendChild(mapBtn);

    if (isFolderUrl) {
      const folderBtn = document.createElement("a");
      folderBtn.className = "action-icon-btn folder-btn folder-open-link";
      folderBtn.title = `Open Photos Folder: ${poi.source_url}`;
      folderBtn.href = folderUri;
      folderBtn.setAttribute("data-path", poi.source_url);
      folderBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>';
      tdActions.appendChild(folderBtn);
    }

    tr.appendChild(tdActions);

    poisTableBody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function isLocalOrUncPath(url) {
  if (!url) return false;
  const s = String(url).trim();
  return s.startsWith("\\\\") || s.startsWith("//") || /^[a-zA-Z]:[\\/]/.test(s) || /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\\/]/.test(s);
}

function getFolderProtocolUrl(path) {
  if (!path) return "#";
  let cleanPath = String(path).trim().replace(/^["']|["']$/g, "");
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\\/]/.test(cleanPath)) {
    cleanPath = "\\\\" + cleanPath;
  }
  return `vistarae-folder://${encodeURIComponent(cleanPath)}`;
}

// ==========================================
// Edit / Create Modal Logic
// ==========================================
let pendingLinkedFolderId = null;
let pendingChildPoiId = null;

function openCreatePoiModal() {
  currentEditingPoi = null;
  initialEditSnapshot = null;
  pendingLinkedFolderId = null;
  pendingChildPoiId = null;
  document.getElementById("edit-poi-id").value = "";
  document.getElementById("edit-modal-id").textContent = "Manual Entry";
  document.getElementById("edit-modal-title").textContent = "Add New Point of Interest";
  editSaveBtn.textContent = "Create Point of Interest";
  if (editDeleteBtn) editDeleteBtn.style.display = "none";
  if (editCloneBtn) editCloneBtn.style.display = "none";
  const mergeFromBtn = document.getElementById("edit-poi-merge-from-btn");
  const mergeToBtn = document.getElementById("edit-poi-merge-to-btn");
  if (mergeFromBtn) mergeFromBtn.style.display = "none";
  if (mergeToBtn) mergeToBtn.style.display = "none";
  if (editCollisionBanner) {
    editCollisionBanner.style.display = "none";
    editCollisionBanner.innerHTML = "";
  }
  const enrichmentBanner = document.getElementById("edit-enrichment-banner");
  if (enrichmentBanner) enrichmentBanner.style.display = "none";
  const photoBadge = document.getElementById("edit-visit-photo-badge");
  if (photoBadge) photoBadge.style.display = "none";
  const dismissEnrichBtn = document.getElementById("edit-enrichment-dismiss-btn");
  if (dismissEnrichBtn) {
    dismissEnrichBtn.onclick = () => {
      if (enrichmentBanner) enrichmentBanner.style.display = "none";
    };
  }

  // Primary
  document.getElementById("edit-name").value = "";
  document.getElementById("edit-poi-type").value = "site to see";
  document.getElementById("edit-personal-rating").value = "3";
  document.getElementById("edit-description").value = "";

  // Location
  document.getElementById("edit-lat").value = "";
  document.getElementById("edit-lng").value = "";
  const editSubLoc = document.getElementById("edit-sublocation");
  if (editSubLoc) editSubLoc.value = "";
  document.getElementById("edit-city").value = "";
  document.getElementById("edit-state").value = "";
  document.getElementById("edit-country").value = "";
  const editZipCode = document.getElementById("edit-zip-code");
  if (editZipCode) editZipCode.value = "";

  editViewGmapsLink.onclick = () => {
    const lat = document.getElementById("edit-lat").value;
    const lng = document.getElementById("edit-lng").value;
    if (lat && lng) {
      openUrlInNewTab(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`);
    } else {
      showToast("No coordinates available for Google Maps search.", true);
    }
  };

  // Visit details
  document.getElementById("edit-effort").value = "";
  document.getElementById("edit-environment").value = "";
  document.getElementById("edit-duration").value = "";
  document.getElementById("edit-cost").value = "";
  document.getElementById("edit-lead-time").value = "";
  document.getElementById("edit-best-time").value = "";

  const visitDateInput = document.getElementById("edit-visit-date");
  visitDateInput.value = "";
  document.getElementById("edit-visit-today-btn").onclick = () => {
    visitDateInput.value = new Date().toISOString().split("T")[0];
  };
  document.getElementById("edit-visit-clear-btn").onclick = () => {
    visitDateInput.value = "";
  };

  const visitAgainCheckbox = document.getElementById("edit-visit-again");
  if (visitAgainCheckbox) visitAgainCheckbox.checked = false;

  // Web & Contact
  document.getElementById("edit-website").value = "";
  document.getElementById("edit-phone").value = "";
  document.getElementById("edit-source-type").value = "manual";
  document.getElementById("edit-source-url").value = "";
  if (typeof window.autoResizeSourceUrl === "function") window.autoResizeSourceUrl();
  const editSourceUrlOpenBtn = document.getElementById("edit-source-url-open-btn");
  if (editSourceUrlOpenBtn) editSourceUrlOpenBtn.style.display = "none";

  // Tags
  editingTagsList = [];
  renderEditingTags();

  // Lists checkboxes
  renderEditingLists([]);

  // Parent POI
  const parentPoiIdInput = document.getElementById("edit-parent-poi-id");
  const parentPoiSearchInput = document.getElementById("edit-parent-poi-search");
  const parentPoiClearBtn = document.getElementById("edit-parent-poi-clear-btn");
  const parentPoiDropdown = document.getElementById("edit-parent-poi-dropdown");
  if (parentPoiIdInput) parentPoiIdInput.value = "";
  if (parentPoiSearchInput) parentPoiSearchInput.value = "";
  if (parentPoiClearBtn) parentPoiClearBtn.style.display = "none";
  if (parentPoiDropdown) parentPoiDropdown.style.display = "none";

  if (editDeleteBtn) editDeleteBtn.style.display = "none";

  // Reset associated photo folders container
  const pathsContainer = document.getElementById("edit-poi-paths-list");
  const pathsCount = document.getElementById("edit-poi-paths-count");
  if (pathsContainer) {
    pathsContainer.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">No associated folders yet. Folders can be linked after creation or via the Scanned Folders tab.</span>';
  }
  if (pathsCount) pathsCount.textContent = "0 folders";

  editModal.style.display = "flex";
  setTimeout(() => {
    document.getElementById("edit-name").focus();
  }, 100);
}

function openCreatePoiFromFolder(folderItem) {
  openCreatePoiModal();
  pendingLinkedFolderId = folderItem.id;
  pendingChildPoiId = null;

  const folderTitle = folderItem.site_name || folderItem.folder_name || "";
  document.getElementById("edit-modal-title").textContent = `Create Place from Folder: "${folderItem.folder_name || folderItem.folder_path}"`;
  document.getElementById("edit-modal-id").textContent = `Folder: ${folderItem.folder_path}`;
  editSaveBtn.textContent = "Create Place & Link Folder";

  // Display this specific folder in the Associated Scanned Folders section as pending link
  const pathsContainer = document.getElementById("edit-poi-paths-list");
  const pathsCount = document.getElementById("edit-poi-paths-count");
  if (pathsCount) pathsCount.textContent = "1 folder (pending link)";
  if (pathsContainer) {
    const statusPillClass = `status-pill-${(folderItem.status || 'unknown').replace(/\s+/g, '-')}`;
    pathsContainer.innerHTML = `
      <div class="associated-folder-row" style="background: #ffffff; border: 1px dashed #0284c7; border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
            <span class="status-pill ${statusPillClass}">${escapeHtml(folderItem.status || 'pending')}</span>
            <strong style="font-size: 12.5px; color: var(--text-main);">${escapeHtml(folderItem.folder_name || folderItem.site_name || 'Folder')}</strong>
            <span style="font-size: 11px; color: var(--text-muted);">(${folderItem.photo_count || 0} photos)</span>
            <span style="font-size: 11px; font-weight: 600; color: #0369a1; background: #e0f2fe; padding: 2px 6px; border-radius: 4px; border: 1px solid #bae6fd;">
              ✨ Will link to this place on save
            </span>
          </div>
          <div class="associated-folder-path" title="${escapeHtml(folderItem.folder_path)}">${escapeHtml(folderItem.folder_path)}</div>
        </div>
        <div>
          <a href="${getFolderProtocolUrl(folderItem.folder_path)}" class="btn btn-secondary btn-sm folder-open-link" data-path="${escapeHtml(folderItem.folder_path)}" style="padding: 3px 8px; font-size: 11px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;" title="Open folder in File Explorer">
            📁 Open
          </a>
        </div>
      </div>
    `;
  }

  document.getElementById("edit-name").value = folderTitle;
  document.getElementById("edit-poi-type").value = "site to see";
  document.getElementById("edit-personal-rating").value = "3";
  document.getElementById("edit-source-type").value = "photo";
  document.getElementById("edit-source-url").value = folderItem.folder_path || "";
  if (typeof window.autoResizeSourceUrl === "function") {
    window.autoResizeSourceUrl();
    setTimeout(window.autoResizeSourceUrl, 50);
  }

  const editSourceUrlOpenBtn = document.getElementById("edit-source-url-open-btn");
  if (editSourceUrlOpenBtn && folderItem.folder_path) {
    editSourceUrlOpenBtn.style.display = "inline-flex";
    editSourceUrlOpenBtn.href = getFolderProtocolUrl(folderItem.folder_path);
    editSourceUrlOpenBtn.setAttribute("data-path", folderItem.folder_path);
  }

  if (folderItem.latitude != null) document.getElementById("edit-lat").value = folderItem.latitude;
  if (folderItem.longitude != null) document.getElementById("edit-lng").value = folderItem.longitude;
  if (folderItem.city) document.getElementById("edit-city").value = folderItem.city;
  if (folderItem.state) document.getElementById("edit-state").value = folderItem.state;
  if (folderItem.country || folderItem.country_code) {
    document.getElementById("edit-country").value = folderItem.country || folderItem.country_code;
  }
  if (folderItem.reasoning) document.getElementById("edit-description").value = folderItem.reasoning;

  const initialPhotoDate = folderItem.earliest_date || folderItem.latest_date;
  if (initialPhotoDate) {
    document.getElementById("edit-visit-date").value = initialPhotoDate.slice(0, 10);
    const photoBadge = document.getElementById("edit-visit-photo-badge");
    if (photoBadge) photoBadge.style.display = "inline-block";
  }

  const visitAgainCheckbox = document.getElementById("edit-visit-again");
  if (visitAgainCheckbox) visitAgainCheckbox.checked = false;

  // Update GMaps link
  if (folderItem.latitude != null && folderItem.longitude != null) {
    editViewGmapsLink.onclick = () => {
      openUrlInNewTab(`https://www.google.com/maps/search/?api=1&query=${folderItem.latitude},${folderItem.longitude}`);
    };
    runDuplicateCheckOnCurrentDraft();
  }

  // Automatic lookup of photo dates, category tags, website, phone, etc.
  enrichPlaceDetailsFromFolder(folderItem);
}

async function enrichPlaceDetailsFromFolder(folderItem) {
  const enrichmentBanner = document.getElementById("edit-enrichment-banner");
  const enrichmentText = document.getElementById("edit-enrichment-text");
  const enrichmentSpinner = document.getElementById("edit-enrichment-spinner");
  const photoBadge = document.getElementById("edit-visit-photo-badge");

  if (enrichmentBanner) {
    enrichmentBanner.style.display = "flex";
    enrichmentBanner.style.background = "#f0fdf4";
    enrichmentBanner.style.borderColor = "#bbf7d0";
    enrichmentBanner.style.color = "#166534";
    if (enrichmentSpinner) enrichmentSpinner.style.display = "inline-block";
    if (enrichmentText) enrichmentText.textContent = "🔍 Looking up photo dates, official website, phone & category tags...";
  }

  try {
    const res = await apiFetch(`/api/v1/scanned-paths/${folderItem.id}/lookup-details`);
    if (!res.ok) throw new Error("Lookup request failed");
    const data = await res.json();

    const fieldsPopulated = [];

    // 1. Visit Date from photo
    if (data.visit_date_formatted) {
      const visitDateInput = document.getElementById("edit-visit-date");
      if (!visitDateInput.value || visitDateInput.value !== data.visit_date_formatted) {
        visitDateInput.value = data.visit_date_formatted;
        fieldsPopulated.push("photo visit date");
      }
      if (photoBadge) photoBadge.style.display = "inline-block";
    }

    // 2. Official Website
    if (data.website_official) {
      const webInput = document.getElementById("edit-website");
      if (!webInput.value) {
        webInput.value = data.website_official;
        fieldsPopulated.push("official website");
      }
    }

    // 3. Phone Number
    if (data.phone_number) {
      const phoneInput = document.getElementById("edit-phone");
      if (!phoneInput.value) {
        phoneInput.value = data.phone_number;
        fieldsPopulated.push("phone number");
      }
    }

    // 4. Category Tags
    if (Array.isArray(data.category_tags) && data.category_tags.length > 0) {
      let tagsAdded = 0;
      data.category_tags.forEach((tag) => {
        const clean = tag.trim().toLowerCase();
        if (clean && !editingTagsList.some((t) => t.toLowerCase() === clean)) {
          editingTagsList.push(tag.trim());
          tagsAdded++;
        }
      });
      if (tagsAdded > 0) {
        renderEditingTags();
        fieldsPopulated.push(`${tagsAdded} category tags`);
      }
    }

    // 5. Description
    if (data.description) {
      const descInput = document.getElementById("edit-description");
      if (!descInput.value || descInput.value === folderItem.reasoning) {
        descInput.value = data.description;
        fieldsPopulated.push("description");
      }
    }

    // 6. POI Type
    if (data.poi_type && data.poi_type !== "site to see") {
      const typeSelect = document.getElementById("edit-poi-type");
      if (typeSelect && typeSelect.value === "site to see") {
        typeSelect.value = data.poi_type;
      }
    }

    // 7. Indoor/Outdoor, Effort, Logistics
    if (data.indoor_outdoor) {
      const envInput = document.getElementById("edit-environment");
      if (envInput && !envInput.value) envInput.value = data.indoor_outdoor;
    }
    if (data.physical_effort) {
      const effortInput = document.getElementById("edit-effort");
      if (effortInput && !effortInput.value) effortInput.value = data.physical_effort;
    }
    if (data.cost_tier) {
      const costInput = document.getElementById("edit-cost");
      if (costInput && !costInput.value) costInput.value = data.cost_tier;
    }
    if (data.estimated_duration) {
      const durInput = document.getElementById("edit-duration");
      if (durInput && !durInput.value) durInput.value = data.estimated_duration;
    }
    if (data.best_time_to_visit) {
      const bestInput = document.getElementById("edit-best-time");
      if (bestInput && !bestInput.value) bestInput.value = data.best_time_to_visit;
    }

    // 8. Coordinates & Address if newly discovered
    let coordsUpdated = false;
    if (data.latitude != null && data.longitude != null) {
      const latInput = document.getElementById("edit-lat");
      const lngInput = document.getElementById("edit-lng");
      if (!latInput.value || !lngInput.value) {
        latInput.value = data.latitude;
        lngInput.value = data.longitude;
        coordsUpdated = true;
        fieldsPopulated.push("coordinates");
      }
    }
    if (data.city && !document.getElementById("edit-city").value) {
      document.getElementById("edit-city").value = data.city;
    }
    if (data.state && !document.getElementById("edit-state").value) {
      document.getElementById("edit-state").value = data.state;
    }
    if ((data.country || data.country_code) && !document.getElementById("edit-country").value) {
      document.getElementById("edit-country").value = data.country_code || data.country;
    }

    if (coordsUpdated) {
      editViewGmapsLink.onclick = () => {
        openUrlInNewTab(`https://www.google.com/maps/search/?api=1&query=${data.latitude},${data.longitude}`);
      };
      runDuplicateCheckOnCurrentDraft();
    }

    if (enrichmentSpinner) enrichmentSpinner.style.display = "none";
    if (enrichmentText) {
      if (fieldsPopulated.length > 0) {
        enrichmentText.innerHTML = `✨ <strong>Enriched place details:</strong> found ${fieldsPopulated.join(", ")}.`;
      } else {
        enrichmentText.textContent = "✓ Lookup complete (no additional online details found).";
      }
    }

    setTimeout(() => {
      if (enrichmentBanner) enrichmentBanner.style.display = "none";
    }, 4500);

  } catch (err) {
    console.debug("Folder details lookup error:", err);
    if (enrichmentSpinner) enrichmentSpinner.style.display = "none";
    if (enrichmentText) enrichmentText.textContent = "Lookup finished without new data.";
    setTimeout(() => {
      if (enrichmentBanner) enrichmentBanner.style.display = "none";
    }, 3000);
  }
}

function handleDeleteFromEditModal() {
  if (!currentEditingPoi) return;
  const poiToDelete = currentEditingPoi;
  closeEditModal();
  openDeleteModal(poiToDelete);
}

function openEditModal(poi) {
  const latestPoi = (poi && poi.id) ? (allPois.find((p) => p.id === poi.id) || poi) : poi;
  currentEditingPoi = latestPoi;
  pendingLinkedFolderId = null;
  pendingChildPoiId = null;
  document.getElementById("edit-poi-id").value = poi.id;
  document.getElementById("edit-modal-id").textContent = `ID: ${poi.id}`;
  document.getElementById("edit-modal-title").textContent = `Edit "${poi.name}"`;
  editSaveBtn.textContent = "Save Changes";
  if (editDeleteBtn) editDeleteBtn.style.display = "inline-flex";
  if (editCloneBtn) editCloneBtn.style.display = "inline-flex";
  const mergeFromBtn = document.getElementById("edit-poi-merge-from-btn");
  const mergeToBtn = document.getElementById("edit-poi-merge-to-btn");
  if (mergeFromBtn) mergeFromBtn.style.display = "inline-flex";
  if (mergeToBtn) mergeToBtn.style.display = "inline-flex";
  if (editCollisionBanner) {
    editCollisionBanner.style.display = "none";
    editCollisionBanner.innerHTML = "";
  }
  const enrichmentBanner = document.getElementById("edit-enrichment-banner");
  if (enrichmentBanner) enrichmentBanner.style.display = "none";
  const photoBadge = document.getElementById("edit-visit-photo-badge");
  if (photoBadge) photoBadge.style.display = "none";

  // Primary
  document.getElementById("edit-name").value = poi.name || "";
  document.getElementById("edit-poi-type").value = poi.poi_type || "site to see";
  document.getElementById("edit-personal-rating").value = String(poi.personal_rating || 3);
  document.getElementById("edit-description").value = poi.description || "";

  // Parent POI
  const editParentIdInput = document.getElementById("edit-parent-poi-id");
  const editParentSearchInput = document.getElementById("edit-parent-poi-search");
  const editParentClearBtn = document.getElementById("edit-parent-poi-clear-btn");
  const editParentDropdown = document.getElementById("edit-parent-poi-dropdown");
  if (editParentDropdown) editParentDropdown.style.display = "none";

  if (editParentIdInput && editParentSearchInput) {
    if (poi.parent_poi_id) {
      editParentIdInput.value = poi.parent_poi_id;
      const parentPoi = allPois.find(p => p.id === poi.parent_poi_id);
      if (parentPoi) {
        editParentSearchInput.value = parentPoi.name;
        if (editParentClearBtn) editParentClearBtn.style.display = "inline-block";
      } else {
        editParentSearchInput.value = "Loading parent place...";
        apiFetch(`/api/v1/pois/${poi.parent_poi_id}`).then(r => r.json()).then(p => {
          if (p?.name) {
            editParentSearchInput.value = p.name;
            if (editParentClearBtn) editParentClearBtn.style.display = "inline-block";
          }
        }).catch(() => {
          editParentSearchInput.value = `Parent ID: ${poi.parent_poi_id.slice(0, 8)}...`;
          if (editParentClearBtn) editParentClearBtn.style.display = "inline-block";
        });
      }
    } else {
      editParentIdInput.value = "";
      editParentSearchInput.value = "";
      if (editParentClearBtn) editParentClearBtn.style.display = "none";
    }
  }

  // Location
  const hasValidCoords = hasValidCoordinates(poi);
  document.getElementById("edit-lat").value = hasValidCoords ? poi.latitude : "";
  document.getElementById("edit-lng").value = hasValidCoords ? poi.longitude : "";
  const editSubLoc = document.getElementById("edit-sublocation");
  if (editSubLoc) editSubLoc.value = poi.iptc_sublocation || "";
  document.getElementById("edit-city").value = poi.iptc_city || "";
  document.getElementById("edit-state").value = poi.iptc_province_state || "";
  document.getElementById("edit-country").value = poi.iptc_country_code || "";
  const editZipCode = document.getElementById("edit-zip-code");
  if (editZipCode) editZipCode.value = poi.iptc_zip_code || "";

  editViewGmapsLink.onclick = () => {
    const lat = document.getElementById("edit-lat").value;
    const lng = document.getElementById("edit-lng").value;
    if (lat && lng) {
      openUrlInNewTab(`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`);
    } else {
      showToast("No coordinates available for Google Maps search.", true);
    }
  };

  // Visit details
  document.getElementById("edit-effort").value = poi.physical_effort || "";
  document.getElementById("edit-environment").value = poi.indoor_outdoor || "";
  document.getElementById("edit-duration").value = poi.estimated_duration || "";
  document.getElementById("edit-cost").value = poi.cost_tier || "";
  document.getElementById("edit-lead-time").value = poi.booking_lead_time || "";
  document.getElementById("edit-best-time").value = poi.best_time_to_visit || "";

  const visitDateInput = document.getElementById("edit-visit-date");
  visitDateInput.value = poi.visit_date ? poi.visit_date.slice(0, 10) : "";
  document.getElementById("edit-visit-today-btn").onclick = () => {
    visitDateInput.value = new Date().toISOString().split("T")[0];
  };
  document.getElementById("edit-visit-clear-btn").onclick = () => {
    visitDateInput.value = "";
  };

  const visitAgainCheckbox = document.getElementById("edit-visit-again");
  if (visitAgainCheckbox) visitAgainCheckbox.checked = Boolean(poi.visit_again);

  // Web & Contact
  document.getElementById("edit-website").value = poi.website_official || "";
  document.getElementById("edit-phone").value = poi.phone_number || "";
  document.getElementById("edit-source-type").value = poi.source_type || "";
  document.getElementById("edit-source-url").value = poi.source_url || "";
  if (typeof window.autoResizeSourceUrl === "function") {
    window.autoResizeSourceUrl();
    setTimeout(window.autoResizeSourceUrl, 50);
  }

  const editSourceUrlOpenBtn = document.getElementById("edit-source-url-open-btn");
  if (editSourceUrlOpenBtn) {
    const isFolder = poi.source_url && ((poi.source_type && poi.source_type.toLowerCase() === "photo") || isLocalOrUncPath(poi.source_url));
    if (isFolder) {
      editSourceUrlOpenBtn.style.display = "inline-flex";
      editSourceUrlOpenBtn.href = getFolderProtocolUrl(poi.source_url);
      editSourceUrlOpenBtn.setAttribute("data-path", poi.source_url);
    } else {
      editSourceUrlOpenBtn.style.display = "none";
    }
  }

  // Tags
  editingTagsList = Array.isArray(poi.category_tags) ? [...poi.category_tags] : [];
  renderEditingTags();

  // Lists checkboxes
  renderEditingLists(poi.list_ids || []);

  // Associated photo folders
  loadPoiAssociatedFolders(poi.id);

  editModal.style.display = "flex";
  initialEditSnapshot = captureEditFormSnapshot();
}

function closeEditModal() {
  editModal.style.display = "none";
  currentEditingPoi = null;
  initialEditSnapshot = null;
  pendingLinkedFolderId = null;
  pendingChildPoiId = null;
  const editSourceUrlOpenBtn = document.getElementById("edit-source-url-open-btn");
  if (editSourceUrlOpenBtn) editSourceUrlOpenBtn.style.display = "none";
  if (editCollisionBanner) {
    editCollisionBanner.style.display = "none";
    editCollisionBanner.innerHTML = "";
  }
  const pathsContainer = document.getElementById("edit-poi-paths-list");
  const pathsCount = document.getElementById("edit-poi-paths-count");
  if (pathsContainer) {
    pathsContainer.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">No associated folders found for this place.</span>';
  }
  if (pathsCount) pathsCount.textContent = "0 folders";
  const addFolderBox = document.getElementById("edit-poi-add-folder-box");
  const folderPathInput = document.getElementById("edit-poi-folder-path-input");
  if (addFolderBox) addFolderBox.style.display = "none";
  if (folderPathInput) folderPathInput.value = "";
  const dupAlert = document.getElementById("edit-poi-folder-duplicate-alert");
  if (dupAlert) dupAlert.style.display = "none";
}

// ==========================================
// POI Clone & Duplicate Check Engine
// ==========================================
let initialEditSnapshot = null;
let duplicateCheckTimeout = null;

function captureEditFormSnapshot() {
  const selectedListCheckboxes = document.querySelectorAll('input[name="edit-list-ids"]:checked');
  const list_ids = Array.from(selectedListCheckboxes).map((cb) => cb.value).sort();
  const sortedTags = [...(editingTagsList || [])].map((t) => t.trim().toLowerCase()).sort();

  return {
    name: (document.getElementById("edit-name")?.value || "").trim(),
    poi_type: document.getElementById("edit-poi-type")?.value || "site to see",
    personal_rating: document.getElementById("edit-personal-rating")?.value || "3",
    description: (document.getElementById("edit-description")?.value || "").trim(),
    parent_poi_id: (document.getElementById("edit-parent-poi-id")?.value || "").trim(),
    lat: (document.getElementById("edit-lat")?.value || "").trim(),
    lng: (document.getElementById("edit-lng")?.value || "").trim(),
    sublocation: (document.getElementById("edit-sublocation")?.value || "").trim(),
    city: (document.getElementById("edit-city")?.value || "").trim(),
    state: (document.getElementById("edit-state")?.value || "").trim(),
    country: (document.getElementById("edit-country")?.value || "").trim(),
    zip: (document.getElementById("edit-zip-code")?.value || "").trim(),
    effort: document.getElementById("edit-effort")?.value || "",
    environment: document.getElementById("edit-environment")?.value || "",
    duration: (document.getElementById("edit-duration")?.value || "").trim(),
    cost: document.getElementById("edit-cost")?.value || "",
    lead_time: (document.getElementById("edit-lead-time")?.value || "").trim(),
    best_time: (document.getElementById("edit-best-time")?.value || "").trim(),
    visit_date: document.getElementById("edit-visit-date")?.value || "",
    visit_again: Boolean(document.getElementById("edit-visit-again")?.checked),
    website: (document.getElementById("edit-website")?.value || "").trim(),
    phone: (document.getElementById("edit-phone")?.value || "").trim(),
    source_type: (document.getElementById("edit-source-type")?.value || "").trim(),
    source_url: (document.getElementById("edit-source-url")?.value || "").trim(),
    tags: JSON.stringify(sortedTags),
    lists: JSON.stringify(list_ids),
  };
}

function hasUnsavedChanges() {
  if (!initialEditSnapshot) return false;
  const current = captureEditFormSnapshot();
  for (const key of Object.keys(initialEditSnapshot)) {
    if (initialEditSnapshot[key] !== current[key]) {
      return true;
    }
  }
  return false;
}

function handleClonePoi() {
  if (!currentEditingPoi) return;

  if (hasUnsavedChanges()) {
    alert(
      "Cannot clone place:\n\n" +
      "You have unsaved changes in this place. Please click 'Save Changes' to commit your edits, or 'Cancel' to discard changes before cloning."
    );
    showToast("Unsaved changes detected! Please save changes or cancel before cloning.", true);
    return;
  }

  const basePoiName = currentEditingPoi.name || "Place";

  // Transition modal to Draft Clone mode
  currentEditingPoi = null;
  initialEditSnapshot = null;

  document.getElementById("edit-poi-id").value = "";
  document.getElementById("edit-modal-id").textContent = "New Draft (Cloned)";
  document.getElementById("edit-modal-title").textContent = `New Place Draft (Cloned from "${basePoiName}")`;
  editSaveBtn.textContent = "Create Point of Interest";
  if (editDeleteBtn) editDeleteBtn.style.display = "none";
  if (editCloneBtn) editCloneBtn.style.display = "none";
  const mergeFromBtn = document.getElementById("edit-poi-merge-from-btn");
  const mergeToBtn = document.getElementById("edit-poi-merge-to-btn");
  if (mergeFromBtn) mergeFromBtn.style.display = "none";
  if (mergeToBtn) mergeToBtn.style.display = "none";

  // Reset associated photo folders for the new draft
  const pathsContainer = document.getElementById("edit-poi-paths-list");
  const pathsCount = document.getElementById("edit-poi-paths-count");
  if (pathsContainer) {
    pathsContainer.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">New clone draft — no associated photo folders linked yet.</span>';
  }
  if (pathsCount) pathsCount.textContent = "0 folders";

  showToast(`Draft clone created for "${basePoiName}". Running duplicate check...`);

  // Run duplicate check on this cloned draft
  runDuplicateCheckOnCurrentDraft();
}

async function runDuplicateCheckOnCurrentDraft() {
  const banner = document.getElementById("edit-collision-banner");
  if (!banner) return;

  const name = (document.getElementById("edit-name")?.value || "").trim();
  const latStr = (document.getElementById("edit-lat")?.value || "").trim();
  const lngStr = (document.getElementById("edit-lng")?.value || "").trim();

  if (!name) {
    banner.style.display = "none";
    banner.innerHTML = "";
    return;
  }

  const lat = parseFloat(latStr);
  const lng = parseFloat(lngStr);
  const hasCoords = !isNaN(lat) && !isNaN(lng) && (lat !== 0 || lng !== 0);

  if (!hasCoords) {
    banner.className = "collision-banner status-parent";
    banner.innerHTML = `
      <div class="collision-banner-header">
        <span>ℹ️</span>
        <span>Draft has no coordinates yet. Duplicate and spatial collision check will run once coordinates are assigned.</span>
      </div>
    `;
    banner.style.display = "flex";
    return;
  }

  banner.className = "collision-banner";
  banner.innerHTML = `
    <div class="collision-banner-header">
      <span>⏳</span>
      <span>Testing for duplicate entries and spatial collisions in your collection...</span>
    </div>
  `;
  banner.style.display = "flex";

  try {
    const res = await apiFetch("/api/v1/pois/check-duplicate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        latitude: lat,
        longitude: lng,
        radius_ft: 500,
      }),
    });

    if (!res.ok) throw new Error("Duplicate check request failed");
    const data = await res.json();

    if (data.collision_status === "POTENTIAL_DUPLICATE" && data.matched_poi) {
      const match = data.matched_poi;
      banner.className = "collision-banner status-duplicate";
      banner.innerHTML = `
        <div class="collision-banner-header">
          <span>🟡</span>
          <span>Potential Duplicate: "${escapeHtml(match.name)}" is in your records ${match.distance_meters}m away (${Math.round(match.name_similarity * 100)}% match).</span>
        </div>
        <div class="collision-diff-card">
          <strong>Existing Record:</strong> ${escapeHtml(match.name)} (${escapeHtml(match.poi_type || "site to see")})<br/>
          <span>${escapeHtml(match.description || "No description")}</span>
        </div>
        <div class="collision-actions-row" id="collision-actions-container"></div>
      `;
      banner.style.display = "flex";
      renderCollisionActionButtons(document.getElementById("collision-actions-container"), match);
    } else if (data.collision_status === "NEARBY_PARENT" && data.nearby_parent) {
      const parentMatch = data.nearby_parent;
      banner.className = "collision-banner status-parent";
      banner.innerHTML = `
        <div class="collision-banner-header">
          <span>🔵</span>
          <span>Nearby Macro-Site: Found "${escapeHtml(parentMatch.name)}" in your collection (${parentMatch.distance_meters}m away). Suggest nesting as child POI.</span>
        </div>
        <div class="collision-actions-row" id="collision-actions-container"></div>
      `;
      banner.style.display = "flex";
      renderCollisionActionButtons(document.getElementById("collision-actions-container"), parentMatch);
    } else {
      banner.className = "collision-banner status-unique";
      banner.innerHTML = `
        <div class="collision-banner-header">
          <span>🟢</span>
          <span>Unique Location — No collision detected within 500ft in your collection.</span>
        </div>
      `;
      banner.style.display = "flex";
    }
  } catch (err) {
    console.warn("[runDuplicateCheckOnCurrentDraft] Error checking duplicate:", err);
    banner.style.display = "none";
  }
}

function renderCollisionActionButtons(container, targetPoi) {
  if (!container || !targetPoi) return;
  container.innerHTML = "";

  const titleSpan = document.createElement("span");
  titleSpan.style.cssText = "font-size: 11px; font-weight: 600; width: 100%; margin-bottom: 2px;";
  titleSpan.textContent = "Recommended Actions:";
  container.appendChild(titleSpan);

  // 1. Make current POI a child of the other POI
  const makeChildBtn = document.createElement("button");
  makeChildBtn.type = "button";
  makeChildBtn.className = "collision-action-btn collision-action-btn-child";
  makeChildBtn.innerHTML = `⬇️ Make Child of "${escapeHtml(targetPoi.name)}"`;
  makeChildBtn.onclick = () => {
    const parentIdInput = document.getElementById("edit-parent-poi-id");
    const parentSearchInput = document.getElementById("edit-parent-poi-search");
    const parentClearBtn = document.getElementById("edit-parent-poi-clear-btn");
    if (parentIdInput) parentIdInput.value = targetPoi.id;
    if (parentSearchInput) parentSearchInput.value = targetPoi.name;
    if (parentClearBtn) parentClearBtn.style.display = "inline-block";

    if (pendingChildPoiId === targetPoi.id) {
      pendingChildPoiId = null;
    }

    makeChildBtn.replaceWith(createAppliedPill(`✓ Child of "${targetPoi.name}" selected`));
    showToast(`Set "${targetPoi.name}" as parent place.`);
  };
  container.appendChild(makeChildBtn);

  // 2. Make current POI the parent of the other POI
  if (!targetPoi.parent_poi_id) {
    const makeParentBtn = document.createElement("button");
    makeParentBtn.type = "button";
    makeParentBtn.className = "collision-action-btn collision-action-btn-parent";
    makeParentBtn.innerHTML = `⬆️ Make Parent of "${escapeHtml(targetPoi.name)}"`;
    makeParentBtn.onclick = () => {
      // Clear parent POI if it was pointing to target
      const parentIdInput = document.getElementById("edit-parent-poi-id");
      if (parentIdInput && parentIdInput.value === targetPoi.id) {
        parentIdInput.value = "";
        const parentSearchInput = document.getElementById("edit-parent-poi-search");
        if (parentSearchInput) parentSearchInput.value = "";
        const parentClearBtn = document.getElementById("edit-parent-poi-clear-btn");
        if (parentClearBtn) parentClearBtn.style.display = "none";
      }

      pendingChildPoiId = targetPoi.id;
      const pill = createAppliedPill(`✓ Will link "${targetPoi.name}" as child on save`, () => {
        pendingChildPoiId = null;
        renderCollisionActionButtons(container, targetPoi);
      });
      makeParentBtn.replaceWith(pill);
      showToast(`"${targetPoi.name}" will be linked as a child once you save.`);
    };
    container.appendChild(makeParentBtn);
  } else {
    const hasParentNote = document.createElement("span");
    hasParentNote.style.cssText = "font-size: 11px; color: var(--text-muted); padding: 4px 6px;";
    hasParentNote.textContent = `(ℹ️ "${targetPoi.name}" already has a parent)`;
    container.appendChild(hasParentNote);
  }

  // 3. Add folder to existing POI (if pendingLinkedFolderId)
  if (pendingLinkedFolderId) {
    const linkFolderBtn = document.createElement("button");
    linkFolderBtn.type = "button";
    linkFolderBtn.className = "collision-action-btn collision-action-btn-link-folder";
    linkFolderBtn.innerHTML = `🔗 Add Folder to "${escapeHtml(targetPoi.name)}" (No Duplicate)`;
    linkFolderBtn.onclick = async () => {
      if (!confirm(`Link this folder to existing place:\n"${targetPoi.name}"\ninstead of creating a duplicate place?`)) return;
      try {
        const res = await apiFetch(`/api/v1/scanned-paths/${pendingLinkedFolderId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            poi_id: targetPoi.id,
            status: "identified"
          })
        });
        if (!res.ok) throw new Error("Failed to link folder to existing place");
        pendingLinkedFolderId = null;
        closeEditModal();
        showToast(`Folder linked to existing place "${targetPoi.name}"!`);
        await loadScannedFolders();
        updateFolderStatusCounts();
        fetchPois(true);
      } catch (err) {
        showToast(err.message, true);
      }
    };
    container.appendChild(linkFolderBtn);
  }

  // 4. View existing POI
  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.className = "collision-action-btn collision-action-btn-view";
  viewBtn.innerHTML = `👁️ View Existing Place`;
  viewBtn.onclick = async () => {
    if (hasUnsavedChanges()) {
      if (!confirm("You have unsaved changes in this draft. Discard and view existing place?")) return;
    }
    const existing = allPois.find(p => p.id === targetPoi.id);
    if (existing) {
      openEditModal(existing);
    } else {
      try {
        const res = await apiFetch(`/api/v1/pois/${targetPoi.id}`);
        if (res.ok) {
          const poiData = await res.json();
          openEditModal(poiData);
        }
      } catch (e) {
        showToast("Could not load existing place details", true);
      }
    }
  };
  container.appendChild(viewBtn);
}

function createAppliedPill(text, onRemove = null) {
  const pill = document.createElement("span");
  pill.className = "collision-action-applied-pill";
  pill.textContent = text;
  if (onRemove) {
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.style.cssText = "background:none;border:none;cursor:pointer;color:#b91c1c;padding:0 2px;font-size:13px;line-height:1;margin-left:4px;";
    removeBtn.innerHTML = "&times;";
    removeBtn.title = "Remove selection";
    removeBtn.onclick = onRemove;
    pill.appendChild(removeBtn);
  }
  return pill;
}

function renderEditingTags() {
  editTagsContainer.innerHTML = "";
  editingTagsList.forEach((tag, idx) => {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.innerHTML = `
      <span>${escapeHtml(tag)}</span>
      <button type="button" class="tag-remove-btn" data-index="${idx}">&times;</button>
    `;
    chip.querySelector(".tag-remove-btn").addEventListener("click", () => {
      editingTagsList.splice(idx, 1);
      renderEditingTags();
    });
    editTagsContainer.appendChild(chip);
  });
}

function addTagToEditingList(tag) {
  const clean = tag.trim().toLowerCase();
  if (clean && !editingTagsList.some((t) => t.toLowerCase() === clean)) {
    editingTagsList.push(tag.trim());
    renderEditingTags();
  }
}

function handleAddNewTagToModal() {
  const val = newTagInput.value.trim();
  if (val) {
    addTagToEditingList(val);
    newTagInput.value = "";
  }
}

function renderEditingLists(selectedListIds) {
  editListsContainer.innerHTML = "";
  if (availableLists.length === 0) {
    editListsContainer.innerHTML = '<span style="color: #64748b; font-size: 12px;">No lists created yet.</span>';
    return;
  }

  availableLists.forEach((lst) => {
    const label = document.createElement("label");
    label.className = "list-checkbox-label";
    const isChecked = selectedListIds.includes(lst.id);
    label.innerHTML = `
      <input type="checkbox" name="edit-list-ids" value="${lst.id}" ${isChecked ? "checked" : ""}>
      <span>${escapeHtml(lst.title)} ${lst.is_trip ? "✈️" : "📁"}</span>
    `;
    editListsContainer.appendChild(label);
  });
}

function setupParentPoiCombobox() {
  const container = document.getElementById("edit-parent-poi-container");
  const searchInput = document.getElementById("edit-parent-poi-search");
  const idInput = document.getElementById("edit-parent-poi-id");
  const dropdown = document.getElementById("edit-parent-poi-dropdown");
  const clearBtn = document.getElementById("edit-parent-poi-clear-btn");
  const toggleBtn = document.getElementById("edit-parent-poi-toggle-btn");

  if (!container || !searchInput || !dropdown) return;

  function renderDropdown(term = "") {
    dropdown.innerHTML = "";
    const cleanTerm = term.trim().toLowerCase();
    const currentId = currentEditingPoi?.id;

    // Filter available POIs (exclude current place to prevent self-parenting)
    let candidates = allPois.filter(p => p.id !== currentId);
    if (cleanTerm) {
      candidates = candidates.filter(p => {
        const nameMatch = p.name && p.name.toLowerCase().includes(cleanTerm);
        const cityMatch = p.iptc_city && p.iptc_city.toLowerCase().includes(cleanTerm);
        const stateMatch = p.iptc_province_state && p.iptc_province_state.toLowerCase().includes(cleanTerm);
        return nameMatch || cityMatch || stateMatch;
      });
      // Prioritize places whose name starts with search term
      candidates.sort((a, b) => {
        const aStarts = (a.name || "").toLowerCase().startsWith(cleanTerm);
        const bStarts = (b.name || "").toLowerCase().startsWith(cleanTerm);
        if (aStarts && !bStarts) return -1;
        if (!aStarts && bStarts) return 1;
        return (a.name || "").localeCompare(b.name || "");
      });
    }

    // Top option: (None / Top-level Place)
    const noneItem = document.createElement("div");
    noneItem.className = "combobox-item combobox-item-none";
    noneItem.innerHTML = `<span>(None / Top-level Place)</span><span class="combobox-item-details">Clear parent</span>`;
    noneItem.onclick = () => {
      idInput.value = "";
      searchInput.value = "";
      if (clearBtn) clearBtn.style.display = "none";
      dropdown.style.display = "none";
    };
    dropdown.appendChild(noneItem);

    const maxResults = 50;
    const displayList = candidates.slice(0, maxResults);

    if (candidates.length === 0 && cleanTerm) {
      const emptyItem = document.createElement("div");
      emptyItem.className = "combobox-empty";
      emptyItem.textContent = `No places found matching "${cleanTerm}"`;
      dropdown.appendChild(emptyItem);
    } else {
      displayList.forEach(p => {
        const item = document.createElement("div");
        item.className = "combobox-item";
        if (idInput.value === p.id) item.classList.add("active");

        const loc = [p.iptc_city, p.iptc_province_state].filter(Boolean).join(", ");
        const detailStr = loc || p.poi_type || "Place";

        item.innerHTML = `
          <span style="font-weight: 500;">📍 ${escapeHtml(p.name)}</span>
          <span class="combobox-item-details">${escapeHtml(detailStr)}</span>
        `;
        item.onclick = () => {
          idInput.value = p.id;
          searchInput.value = p.name;
          if (clearBtn) clearBtn.style.display = "inline-block";
          dropdown.style.display = "none";
        };
        dropdown.appendChild(item);
      });

      if (candidates.length > maxResults) {
        const moreItem = document.createElement("div");
        moreItem.className = "combobox-empty";
        moreItem.style.padding = "6px 12px";
        moreItem.style.fontSize = "11px";
        moreItem.textContent = `Showing top 50 of ${candidates.length} places. Type more letters to refine...`;
        dropdown.appendChild(moreItem);
      }
    }

    dropdown.style.display = "block";
  }

  searchInput.oninput = () => {
    renderDropdown(searchInput.value);
    if (clearBtn) clearBtn.style.display = searchInput.value ? "inline-block" : "none";
  };

  searchInput.onfocus = () => {
    renderDropdown(searchInput.value);
  };

  if (toggleBtn) {
    toggleBtn.onclick = (e) => {
      e.stopPropagation();
      if (dropdown.style.display === "block") {
        dropdown.style.display = "none";
      } else {
        renderDropdown(searchInput.value);
        searchInput.focus();
      }
    };
  }

  if (clearBtn) {
    clearBtn.onclick = (e) => {
      e.stopPropagation();
      idInput.value = "";
      searchInput.value = "";
      clearBtn.style.display = "none";
      dropdown.style.display = "none";
    };
  }

  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) {
      dropdown.style.display = "none";
    }
  });
}

async function handleSavePoi() {
  const isNew = !currentEditingPoi || !currentEditingPoi.id;

  const latStr = document.getElementById("edit-lat").value.trim();
  const lngStr = document.getElementById("edit-lng").value.trim();
  const name = document.getElementById("edit-name").value.trim();

  if (!name) {
    showToast("Point of interest name is required.", true);
    document.getElementById("edit-name").focus();
    return;
  }

  let lat = null;
  let lng = null;
  let clear_location = false;

  if (latStr === "" && lngStr === "") {
    clear_location = true;
  } else if (latStr !== "" && lngStr !== "") {
    lat = parseFloat(latStr);
    lng = parseFloat(lngStr);
    if (isNaN(lat) || isNaN(lng)) {
      showToast("Latitude and longitude must be valid numbers.", true);
      return;
    }
  } else {
    showToast("Please provide both latitude and longitude, or leave both empty.", true);
    return;
  }

  // Gather list checkboxes
  const selectedListCheckboxes = document.querySelectorAll('input[name="edit-list-ids"]:checked');
  const list_ids = Array.from(selectedListCheckboxes).map((cb) => cb.value);

  const parentPoiId = (document.getElementById("edit-parent-poi-id")?.value || "").trim() || null;

  const poiData = {
    name,
    poi_type: document.getElementById("edit-poi-type").value || "site to see",
    personal_rating: parseInt(document.getElementById("edit-personal-rating").value, 10) || 3,
    description: document.getElementById("edit-description").value.trim() || null,
    parent_poi_id: parentPoiId,
    latitude: lat,
    longitude: lng,
    iptc_sublocation: document.getElementById("edit-sublocation")?.value.trim() || null,
    iptc_city: document.getElementById("edit-city").value.trim() || null,
    iptc_province_state: document.getElementById("edit-state").value.trim() || null,
    iptc_zip_code: document.getElementById("edit-zip-code")?.value.trim() || null,
    iptc_country_code: (() => {
      const rawC = document.getElementById("edit-country").value.trim();
      if (!rawC) return null;
      const mapped = mapCountryNameToAlpha2(rawC);
      return (mapped || rawC).toUpperCase();
    })(),
    physical_effort: document.getElementById("edit-effort").value || null,
    indoor_outdoor: document.getElementById("edit-environment").value || null,
    estimated_duration: document.getElementById("edit-duration").value.trim() || null,
    cost_tier: document.getElementById("edit-cost").value || null,
    booking_lead_time: document.getElementById("edit-lead-time").value.trim() || null,
    best_time_to_visit: document.getElementById("edit-best-time").value.trim() || null,
    visited: Boolean(document.getElementById("edit-visit-date").value),
    visit_date: document.getElementById("edit-visit-date").value || null,
    visit_again: Boolean(document.getElementById("edit-visit-again")?.checked),
    website_official: document.getElementById("edit-website").value.trim() || null,
    phone_number: document.getElementById("edit-phone").value.trim() || null,
    source_type: document.getElementById("edit-source-type").value.trim() || (isNew ? "manual" : null),
    source_url: document.getElementById("edit-source-url").value.trim() || "",
    category_tags: editingTagsList,
    list_ids,
  };

  if (!isNew) {
    poiData.clear_location = clear_location;
  }

  editSaveBtn.textContent = isNew ? "Creating..." : "Saving...";
  editSaveBtn.disabled = true;

  if (isNew) {
    chrome.runtime.sendMessage(
      {
        action: "SAVE_POI",
        payload: poiData,
      },
      async (res) => {
        editSaveBtn.textContent = "Create Point of Interest";
        editSaveBtn.disabled = false;

        if (res?.success && res.data) {
          const createdPoi = res.data;

          // 1. Link folder if this POI was created from a folder
          if (pendingLinkedFolderId) {
            try {
              const patchBody = {
                poi_id: createdPoi.id,
                status: "identified"
              };
              if (createdPoi.latitude != null && createdPoi.longitude != null) {
                patchBody.latitude = createdPoi.latitude;
                patchBody.longitude = createdPoi.longitude;
              }
              if (createdPoi.iptc_city) patchBody.city = createdPoi.iptc_city;
              if (createdPoi.iptc_province_state) patchBody.state = createdPoi.iptc_province_state;
              if (createdPoi.iptc_country_code) patchBody.country_code = createdPoi.iptc_country_code;
              await apiFetch(`/api/v1/scanned-paths/${pendingLinkedFolderId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(patchBody)
              });
              loadScannedFolders();
              updateFolderStatusCounts();
            } catch (err) {
              console.error("[handleSavePoi] Failed to link folder to created POI:", err);
            }
            pendingLinkedFolderId = null;
          }

          // 2. Link child POI if one was designated
          if (pendingChildPoiId) {
            try {
              await apiFetch(`/api/v1/pois/${pendingChildPoiId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  parent_poi_id: createdPoi.id
                })
              });
            } catch (err) {
              console.error("[handleSavePoi] Failed to set parent on child POI:", err);
            }
            pendingChildPoiId = null;
          }

          // 3. Auto-link folder if source_url is a local or network folder path
          if (isFolderPath(poiData.source_url)) {
            try {
              await apiFetch(`/api/v1/pois/${createdPoi.id}/photo-folder`, {
                method: "POST",
                body: JSON.stringify({
                  folder_path: poiData.source_url,
                  action: "check"
                })
              });
            } catch (err) {
              console.debug("Auto-linking source_url folder on create:", err);
            }
          }

          poiMergeMasterPois = null;
          showToast(`Successfully created "${name}"!`);
          closeEditModal();
          fetchPois(true); // Preserve map zoom level and viewport!
        } else {
          showToast(`Failed to create place: ${res?.error || "Unknown error"}`, true);
        }
      }
    );
  } else {
    chrome.runtime.sendMessage(
      {
        action: "UPDATE_POI",
        payload: {
          id: currentEditingPoi.id,
          data: poiData,
        },
      },
      async (res) => {
        editSaveBtn.textContent = "Save Changes";
        editSaveBtn.disabled = false;

        if (res?.success && res.data) {
          const updatedPoi = res.data;

          // Immediately update in-memory collections so re-opening or clicking the place reflects changes instantly
          const allIdx = allPois.findIndex((p) => p.id === updatedPoi.id);
          if (allIdx !== -1) {
            allPois[allIdx] = { ...allPois[allIdx], ...updatedPoi };
          }
          const filtIdx = filteredPois.findIndex((p) => p.id === updatedPoi.id);
          if (filtIdx !== -1) {
            filteredPois[filtIdx] = { ...filteredPois[filtIdx], ...updatedPoi };
          }

          // Link child POI if one was designated during edit
          if (pendingChildPoiId) {
            try {
              await apiFetch(`/api/v1/pois/${pendingChildPoiId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  parent_poi_id: updatedPoi.id
                })
              });
            } catch (err) {
              console.error("[handleSavePoi] Failed to set parent on child POI:", err);
            }
            pendingChildPoiId = null;
          }

          // Auto-link folder if source_url is a local or network folder path
          if (isFolderPath(poiData.source_url)) {
            try {
              await apiFetch(`/api/v1/pois/${updatedPoi.id}/photo-folder`, {
                method: "POST",
                body: JSON.stringify({
                  folder_path: poiData.source_url,
                  action: "check"
                })
              });
            } catch (err) {
              console.debug("Auto-linking source_url folder on update:", err);
            }
          }

          poiMergeMasterPois = null;
          showToast("Place updated successfully!");
          closeEditModal();
          renderTable(filteredPois);
          fetchPois(true); // Preserve map zoom level and viewport!
        } else {
          showToast(`Failed to update place: ${res?.error || "Unknown error"}`, true);
        }
      }
    );
  }
}

// ==========================================
// Delete Modal Logic
// ==========================================
function openDeleteModal(poi) {
  currentDeletingPoiId = poi.id;
  deletePoiName.textContent = poi.name;
  deleteModal.style.display = "flex";
}

function closeDeleteModal() {
  deleteModal.style.display = "none";
  currentDeletingPoiId = null;
}

async function handleConfirmDelete() {
  if (!currentDeletingPoiId) return;

  deleteConfirmBtn.textContent = "Deleting...";
  deleteConfirmBtn.disabled = true;

  chrome.runtime.sendMessage(
    {
      action: "DELETE_POI",
      payload: { id: currentDeletingPoiId },
    },
    (res) => {
      deleteConfirmBtn.textContent = "Delete Permanently";
      deleteConfirmBtn.disabled = false;

      if (res?.success) {
        poiMergeMasterPois = null;
        showToast("Place deleted successfully!");
        closeDeleteModal();
        fetchPois(true); // Preserve map zoom level and viewport!
      } else {
        showToast(`Failed to delete place: ${res?.error || "Unknown error"}`, true);
      }
    }
  );
}

// ==========================================
// CSV Export Logic (RFC 4180 compliant)
// ==========================================
function exportPoisToCsv() {
  const targetPois = selectedPoiIds.size > 0
    ? filteredPois.filter((p) => selectedPoiIds.has(p.id))
    : filteredPois;

  if (targetPois.length === 0) {
    showToast("No places to export.", true);
    return;
  }

  const headers = [
    "ID",
    "Name",
    "POI Type",
    "Personal Rating",
    "Latitude",
    "Longitude",
    "City",
    "State / Province",
    "Country",
    "Category Tags",
    "Physical Effort",
    "Estimated Duration",
    "Cost Tier",
    "Environment",
    "Best Time to Visit",
    "Booking Lead Time",
    "Visited",
    "Visit Date",
    "Visit Again",
    "Official Website",
    "Phone Number",
    "Source URL",
    "Source Type",
    "Captured Date",
  ];

  const escapeCsv = (val) => {
    if (val === null || val === undefined) return '""';
    const str = String(val).replace(/"/g, '""');
    return `"${str}"`;
  };

  const rows = [headers.join(",")];

  targetPois.forEach((p) => {
    const row = [
      escapeCsv(p.id),
      escapeCsv(p.name),
      escapeCsv(p.poi_type),
      escapeCsv(p.personal_rating),
      escapeCsv(p.latitude),
      escapeCsv(p.longitude),
      escapeCsv(p.iptc_city),
      escapeCsv(p.iptc_province_state),
      escapeCsv(p.iptc_country_code),
      escapeCsv(Array.isArray(p.category_tags) ? p.category_tags.join("; ") : ""),
      escapeCsv(p.physical_effort),
      escapeCsv(p.estimated_duration),
      escapeCsv(p.cost_tier),
      escapeCsv(p.indoor_outdoor),
      escapeCsv(p.best_time_to_visit),
      escapeCsv(p.booking_lead_time),
      escapeCsv(p.visited ? "Yes" : "No"),
      escapeCsv(p.visit_date),
      escapeCsv(p.visit_again ? "Yes" : "No"),
      escapeCsv(p.website_official),
      escapeCsv(p.phone_number),
      escapeCsv(p.source_url),
      escapeCsv(p.source_type),
      escapeCsv(p.created_at),
    ];
    rows.push(row.join(","));
  });

  const csvContent = "\uFEFF" + rows.join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const dateStr = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vistarae_pois_${dateStr}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(
    selectedPoiIds.size > 0
      ? `Exported ${targetPois.length} selected places to CSV!`
      : `Exported ${targetPois.length} places to CSV!`
  );
}

// ==========================================
// Interactive Map & Multi-Pin Visualization Logic
// ==========================================

function getPoiTypeBadgeClass(poiType) {
  return `type-${(poiType || "site-to-see").toLowerCase().replace(/[\s/]+/g, "-")}`;
}

function togglePlacesMap() {
  if (filteredPois.length === 0) {
    chrome.runtime.sendMessage({ action: "GET_AUTH" }, (auth) => {
      if (!auth?.isAuthenticated) {
        showToast("Please sign in to view and plot your places on a map.", true);
        openAuthModal("login");
      } else {
        showToast("No places currently loaded. Try refreshing or resetting filters.", true);
      }
    });
    return;
  }

  if (!mapContainerCard) return;

  const isHidden = mapContainerCard.style.display === "none" || !mapContainerCard.style.display;
  if (isHidden) {
    mapContainerCard.style.display = "block";
    if (visualizeBtnLabel) visualizeBtnLabel.textContent = "Hide Map";
    plotPlacesOnMap(!!mapBoundsFilter);
    mapContainerCard.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    closePlacesMap();
  }
}

function closePlacesMap() {
  if (mapContainerCard) {
    mapContainerCard.style.display = "none";
  }
  if (visualizeBtnLabel) {
    visualizeBtnLabel.textContent = "Plot Places on Map";
  }
  unbindMapSyncListener();
  if (mapSyncViewCheckbox) mapSyncViewCheckbox.checked = false;
  // Note: We preserve mapBoundsFilter so the user can hide the map without losing their filtered view.
  // The filter is cleared via "Reset All Filters" or clicking (x) on the Map View Scope chip.
}

function filterToCurrentMapBounds(notify = true) {
  const isMapOpen = mapContainerCard && mapContainerCard.style.display !== "none" && leafletMap;
  if (!isMapOpen) {
    togglePlacesMap();
    showToast("Map opened! Pan/zoom to your area of interest, then click 'Filter to This View' or 'Current Map View'.");
    return;
  }

  const rawBounds = leafletMap.getBounds();
  const north = Math.min(85.0511, rawBounds.getNorth());
  const south = Math.max(-85.0511, rawBounds.getSouth());
  let west = rawBounds.getWest();
  let east = rawBounds.getEast();

  // Normalize world wrap
  if (east - west >= 360) {
    west = -180.0;
    east = 180.0;
  } else {
    west = ((((west + 180) % 360) + 360) % 360) - 180;
    east = ((((east + 180) % 360) + 360) % 360) - 180;
  }

  mapBoundsFilter = { north, south, east, west };

  updateMapFilterButtonsState(true);
  fetchPois(true);

  if (notify) {
    showToast("Filtered POIs to current visible map scope.");
  }
}

function clearMapBoundsFilter(fetchAgain = true) {
  mapBoundsFilter = null;
  if (mapSyncViewCheckbox) {
    mapSyncViewCheckbox.checked = false;
    unbindMapSyncListener();
  }
  updateMapFilterButtonsState(false);
  if (fetchAgain) {
    fetchPois(true);
  }
}

function updateMapFilterButtonsState(isActive) {
  if (filterMapBoundsBtn) {
    filterMapBoundsBtn.classList.toggle("btn-map-active", isActive);
    filterMapBoundsBtn.textContent = isActive ? "✓ In Map View" : "🗺️ Current Map View";
  }
  if (useMapBoundsBtn) {
    useMapBoundsBtn.classList.toggle("btn-map-active", isActive);
    useMapBoundsBtn.textContent = isActive ? "✓ In Map View" : "🗺️ Current Map View";
  }
  if (mapFilterViewBtn) {
    mapFilterViewBtn.classList.toggle("btn-map-active", isActive);
    mapFilterViewBtn.textContent = isActive ? "✓ Scope Filtered" : "🔍 Filter List to This View";
  }
}

function handleMapSyncToggle() {
  if (!mapSyncViewCheckbox) return;
  if (mapSyncViewCheckbox.checked) {
    const isMapOpen = mapContainerCard && mapContainerCard.style.display !== "none" && leafletMap;
    if (!isMapOpen) {
      togglePlacesMap();
    }
    bindMapSyncListener();
    filterToCurrentMapBounds(false);
    showToast("Map movement sync activated: list will update as you pan/zoom.");
  } else {
    unbindMapSyncListener();
    showToast("Map movement sync paused.");
  }
}

function bindMapSyncListener() {
  if (!leafletMap || isMapSyncBound) return;
  leafletMap.on("moveend", onMapMoveEndDebounced);
  isMapSyncBound = true;
}

function unbindMapSyncListener() {
  if (!leafletMap || !isMapSyncBound) return;
  leafletMap.off("moveend", onMapMoveEndDebounced);
  isMapSyncBound = false;
}

function onMapMoveEndDebounced() {
  if (mapMoveDebounceTimer) clearTimeout(mapMoveDebounceTimer);
  mapMoveDebounceTimer = setTimeout(() => {
    if (mapSyncViewCheckbox && mapSyncViewCheckbox.checked) {
      filterToCurrentMapBounds(false);
    }
  }, 350);
}

function fitMapToAllPlaces() {
  if (!leafletMap || !leafletMarkersLayer) return;
  const layers = leafletMarkersLayer.getLayers();
  if (layers.length === 0) return;
  if (layers.length === 1) {
    leafletMap.setView(layers[0].getLatLng(), 14);
  } else {
    leafletMap.fitBounds(leafletMarkersLayer.getBounds().pad(0.12));
  }
  showToast("Recentered map on all plotted places.");
}

function setMapTileProvider(providerKey) {
  selectedTileProvider = providerKey;
  chrome.storage.local.set({ map_tile_provider: providerKey });
  if (mapTileProviderSelect) {
    mapTileProviderSelect.value = providerKey;
  }
  if (!leafletMap) return;

  const provider = MAP_TILE_PROVIDERS[providerKey] || MAP_TILE_PROVIDERS["google-roadmap"];
  if (currentTileLayer) {
    leafletMap.removeLayer(currentTileLayer);
  }
  currentTileLayer = L.tileLayer(provider.url, provider.options);
  currentTileLayer.addTo(leafletMap);
  if (leafletMarkersLayer) {
    leafletMarkersLayer.bringToFront();
  }
  showToast(`Switched map labels to ${provider.name}.`);
}

function createMarkersLayer(useClustering = true) {
  if (useClustering && typeof L.markerClusterGroup === "function") {
    return L.markerClusterGroup({
      chunkedLoading: true,
      chunkInterval: 100,
      chunkDelay: 10,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      removeOutsideVisibleBounds: true,
      animate: true,
      disableClusteringAtZoom: 17,
    });
  }
  return L.featureGroup();
}

function setClusterEnabled(enabled, isAutomatic = false) {
  if (!isAutomatic) {
    userExplicitlyToggledCluster = true;
  }
  if (mapClusterToggle) mapClusterToggle.checked = enabled;
  if (pageClusterToggle) pageClusterToggle.checked = enabled;
  if (clusterAutoBadge) {
    clusterAutoBadge.style.display = (isAutomatic && enabled) ? "inline-block" : "none";
  }
  chrome.storage.local.set({ map_cluster_enabled: enabled });
  if (leafletMap) {
    plotPlacesOnMap(true);
  }
  if (isAutomatic && enabled) {
    showToast(`Marker clustering automatically enabled (> ${MAX_UNCLUSTERED_POIS} places plotted).`);
  } else {
    showToast(enabled ? "Marker clustering enabled." : "Marker clustering disabled.");
  }
}

function handleMapClusterToggle(enabled) {
  setClusterEnabled(enabled, false);
}

function checkAndApplyAutoClustering(pois) {
  if (!pois || !Array.isArray(pois)) return;
  const coordsCount = pois.filter(hasValidCoordinates).length;
  const isCurrentlyEnabled = (mapClusterToggle && mapClusterToggle.checked) || (pageClusterToggle && pageClusterToggle.checked);

  if (coordsCount > MAX_UNCLUSTERED_POIS) {
    if (!userExplicitlyToggledCluster && !isCurrentlyEnabled) {
      if (mapClusterToggle) mapClusterToggle.checked = true;
      if (pageClusterToggle) pageClusterToggle.checked = true;
      if (clusterAutoBadge) clusterAutoBadge.style.display = "inline-block";
      chrome.storage.local.set({ map_cluster_enabled: true });
      showToast(`Marker clustering automatically enabled (${coordsCount} places plotted, max unclustered is ${MAX_UNCLUSTERED_POIS}).`);
    } else if (isCurrentlyEnabled && clusterAutoBadge) {
      clusterAutoBadge.style.display = "inline-block";
    }
  } else {
    if (clusterAutoBadge) {
      clusterAutoBadge.style.display = "none";
    }
  }
}

function initLeafletMapIfNeeded() {
  if (typeof L === "undefined") {
    console.error("Leaflet library is not loaded.");
    return false;
  }

  if (leafletMap) return true;

  // Configure local icon paths to bundled assets
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: "vendor/images/marker-icon-2x.png",
    iconUrl: "vendor/images/marker-icon.png",
    shadowUrl: "vendor/images/marker-shadow.png",
  });

  leafletMap = L.map("vistarae-leaflet-map", {
    zoomControl: true,
    scrollWheelZoom: true,
  });

  const provider = MAP_TILE_PROVIDERS[selectedTileProvider] || MAP_TILE_PROVIDERS["google-roadmap"];
  currentTileLayer = L.tileLayer(provider.url, provider.options).addTo(leafletMap);

  const shouldCluster = (mapClusterToggle && mapClusterToggle.checked) || (pageClusterToggle && pageClusterToggle.checked);
  leafletMarkersLayer = createMarkersLayer(shouldCluster).addTo(leafletMap);
  if (mapSyncViewCheckbox && mapSyncViewCheckbox.checked) {
    bindMapSyncListener();
  }
  return true;
}

function plotPlacesOnMap(preserveMapView = false) {
  if (!initLeafletMapIfNeeded()) {
    showToast("Map library loading...", true);
    return;
  }

  const shouldCluster = (mapClusterToggle && mapClusterToggle.checked) || (pageClusterToggle && pageClusterToggle.checked);
  const isCurrentlyClustered = leafletMarkersLayer && typeof leafletMarkersLayer.zoomToShowLayer === "function";

  if (!leafletMarkersLayer || isCurrentlyClustered !== shouldCluster) {
    if (leafletMarkersLayer) {
      leafletMap.removeLayer(leafletMarkersLayer);
    }
    leafletMarkersLayer = createMarkersLayer(shouldCluster).addTo(leafletMap);
  } else {
    leafletMarkersLayer.clearLayers();
  }

  poiMarkersMap.clear();

  const poisWithCoords = filteredPois.filter(hasValidCoordinates);

  if (poisWithCoords.length === 0) {
    if (mapStatusPill) mapStatusPill.textContent = "📍 0 places plotted";
    if (!preserveMapView) {
      leafletMap.setView([39.8283, -98.5795], 4);
    }
    showToast("None of the matching places have valid coordinates to plot.", true);
    return;
  }

  const markersToAdd = [];

  poisWithCoords.forEach((p) => {
    // Custom pin color or visibility rule (only applies to unclustered entries)
    let customPinIcon = null;
    if (!shouldCluster && activePinColorScheme) {
      const evalRes = evaluatePoiColorScheme(p, activePinColorScheme);
      if (evalRes.action === "hide") {
        return; // Place is hidden by custom rule or fallback
      }
      customPinIcon = createColoredPinIcon(evalRes.color);
    }

    const photoHtml = p.primary_image_url
      ? `<img src="${escapeHtml(p.primary_image_url)}" class="map-popup-thumb" alt="${escapeHtml(p.name)}" onerror="this.style.display='none'">`
      : "";
    const sourceTypeHtml = p.source_type
      ? `<span class="source-type-pill source-${escapeHtml(p.source_type.toLowerCase())}">${escapeHtml(p.source_type)}</span>`
      : "";
    const typeClass = `type-${(p.poi_type || "site-to-see").toLowerCase().replace(/[\s/]+/g, "-")}`;
    const typeBadge = `<span class="poi-type-badge ${typeClass}">${escapeHtml(p.poi_type || "site to see")}</span>`;
    const locParts = [p.iptc_city, p.iptc_province_state, p.iptc_country_code].filter(Boolean);
    const locStr = locParts.length > 0 ? locParts.join(", ") : "";
    const ratingStr = p.personal_rating ? `<span style="color:#eab308; font-size:12px; margin-left:6px;">${"★".repeat(p.personal_rating)}${"☆".repeat(5 - p.personal_rating)}</span>` : "";
    
    // Direct Google Maps single pin link (NO ROUTING)
    const singleGmapsUrl = `https://www.google.com/maps/search/?api=1&query=${p.latitude},${p.longitude}`;

    const isPhotoSource = p.source_type && p.source_type.toLowerCase() === "photo";
    const isFolderUrl = p.source_url && (isPhotoSource || isLocalOrUncPath(p.source_url));
    const mapFolderBtn = isFolderUrl
      ? `<a href="${getFolderProtocolUrl(p.source_url)}" class="btn btn-secondary btn-sm folder-open-link" data-path="${escapeHtml(p.source_url)}" style="font-size:11px; padding: 4px 8px; display:inline-flex; align-items:center; gap:4px; text-decoration:none;" title="Open folder in File Explorer">
           <span>📁 Photos</span>
         </a>`
      : "";

    const popupHtml = `
      <div class="map-popup-card">
        ${photoHtml}
        <div class="map-popup-body">
          <div class="map-popup-header-row">
            <span class="map-popup-title" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
            ${sourceTypeHtml}
          </div>
          <div style="display:flex; align-items:center; margin: 4px 0 6px;">
            ${typeBadge}
            ${ratingStr}
          </div>
          ${locStr ? `<div class="map-popup-meta">📍 ${escapeHtml(locStr)}</div>` : ""}
          <div class="map-popup-coords">${Number(p.latitude).toFixed(5)}, ${Number(p.longitude).toFixed(5)}</div>
          ${p.description ? `<div style="font-size:11.5px; color:#475569; margin: 4px 0 8px; line-height:1.35;">${escapeHtml(p.description.slice(0, 110))}${p.description.length > 110 ? "..." : ""}</div>` : ""}
          <div class="map-popup-footer">
            ${mapFolderBtn}
            <button type="button" class="btn btn-primary btn-sm map-gmaps-direct-btn" data-url="${singleGmapsUrl}" style="font-size:11px; padding: 4px 8px; display:inline-flex; align-items:center; gap:4px;">
              <span>Google Maps</span> ↗
            </button>
            <button type="button" class="btn btn-secondary btn-sm map-edit-detail-btn" style="font-size:11px; padding: 4px 8px;">
              Edit Details
            </button>
          </div>
        </div>
      </div>
    `;

    const marker = customPinIcon
      ? L.marker([Number(p.latitude), Number(p.longitude)], { icon: customPinIcon })
      : L.marker([Number(p.latitude), Number(p.longitude)]);
    marker.bindPopup(popupHtml, { maxWidth: 280, minWidth: 220, className: "custom-leaflet-popup" });
    marker.on("popupopen", (e) => {
      const popupEl = e.popup.getElement();
      if (!popupEl) return;
      const gmapsBtn = popupEl.querySelector(".map-gmaps-direct-btn");
      if (gmapsBtn) {
        gmapsBtn.onclick = () => openUrlInNewTab(gmapsBtn.dataset.url);
      }
      const editBtn = popupEl.querySelector(".map-edit-detail-btn");
      if (editBtn) {
        editBtn.onclick = () => openEditModal(p);
      }
    });
    poiMarkersMap.set(p.id, marker);
    markersToAdd.push(marker);
  });

  if (typeof leafletMarkersLayer.addLayers === "function") {
    leafletMarkersLayer.addLayers(markersToAdd);
  } else {
    markersToAdd.forEach((m) => leafletMarkersLayer.addLayer(m));
  }

  if (!preserveMapView) {
    if (markersToAdd.length === 1 && poisWithCoords.length > 0) {
      const singlePoi = poisWithCoords.find((p) => poiMarkersMap.has(p.id));
      if (singlePoi) {
        leafletMap.setView([Number(singlePoi.latitude), Number(singlePoi.longitude)], 14);
      }
    } else if (markersToAdd.length > 1) {
      const bounds = leafletMarkersLayer.getBounds();
      if (bounds && typeof bounds.isValid === "function" && bounds.isValid()) {
        leafletMap.fitBounds(bounds.pad(0.12));
      }
    }
  }

  if (mapStatusPill) {
    const scopeLabel = mapBoundsFilter ? " in map view" : " plotted";
    const clusterLabel = shouldCluster ? " (clustered)" : "";
    if (!shouldCluster && activePinColorScheme) {
      const hiddenCount = poisWithCoords.length - markersToAdd.length;
      const hideNote = hiddenCount > 0 ? ` (${hiddenCount} hidden by rule)` : "";
      const schemeLabel = activePinColorScheme.name ? ` [🎨 ${activePinColorScheme.name}]` : " [🎨 Active]";
      mapStatusPill.textContent = `📍 ${markersToAdd.length} place${markersToAdd.length === 1 ? "" : "s"}${scopeLabel}${schemeLabel}${hideNote}`;
    } else {
      mapStatusPill.textContent = `📍 ${poisWithCoords.length} place${poisWithCoords.length === 1 ? "" : "s"}${scopeLabel}${clusterLabel}`;
    }
  }

  setTimeout(() => {
    if (leafletMap) leafletMap.invalidateSize();
  }, 200);
}

/**
 * When clicking on a photo thumbnail in the table, if the map is displayed,
 * zoom and center the map on that location and open its popup.
 */
function zoomMapToPoiIfDisplayed(poi) {
  const isMapDisplayed = mapContainerCard && mapContainerCard.style.display !== "none" && leafletMap;
  if (!isMapDisplayed) {
    return;
  }

  const hasCoords = hasValidCoordinates(poi);
  if (!hasCoords) {
    showToast(`No coordinates recorded for "${poi.name}".`, true);
    return;
  }

  // Ensure map canvas is updated
  leafletMap.invalidateSize();

  const marker = poiMarkersMap.get(poi.id);
  if (!marker) return;

  // Smoothly scroll map container into view
  mapContainerCard.scrollIntoView({ behavior: "smooth", block: "start" });

  if (leafletMarkersLayer && typeof leafletMarkersLayer.zoomToShowLayer === "function") {
    leafletMarkersLayer.zoomToShowLayer(marker, () => {
      marker.openPopup();
    });
  } else {
    // Smoothly zoom and fly to coordinates (street/landmark level)
    leafletMap.flyTo([poi.latitude, poi.longitude], 16, {
      duration: 0.8,
      easeLinearity: 0.25,
    });

    // Open the marker's popup
    setTimeout(() => {
      marker.openPopup();
    }, 350);
  }
}

// ==========================================
// KML Export Logic (Google My Maps & Earth)
// ==========================================
function exportPoisToKml() {
  const basePois = selectedPoiIds.size > 0
    ? filteredPois.filter((p) => selectedPoiIds.has(p.id))
    : filteredPois;

  const poisWithCoords = basePois.filter(hasValidCoordinates);

  if (poisWithCoords.length === 0) {
    showToast(
      selectedPoiIds.size > 0
        ? "None of the selected places have valid coordinates to export to KML."
        : "No places with valid coordinates to export to KML.",
      true
    );
    return;
  }

  const escapeXml = (unsafe) => {
    if (unsafe === null || unsafe === undefined) return "";
    return String(unsafe)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  };

  const placemarks = poisWithCoords
    .map((p) => {
      const cityState = [p.iptc_city, p.iptc_province_state, p.iptc_country_code].filter(Boolean).join(", ");
      const descLines = [];
      if (p.poi_type) descLines.push(`Type: ${p.poi_type}`);
      if (cityState) descLines.push(`Location: ${cityState}`);
      if (p.personal_rating) descLines.push(`Rating: ${"★".repeat(p.personal_rating)}`);
      if (p.source_type) descLines.push(`Source: ${p.source_type}`);
      if (p.description) descLines.push(`Notes: ${p.description}`);
      if (p.website_official) descLines.push(`Website: ${p.website_official}`);
      if (p.source_url) descLines.push(`Source URL: ${p.source_url}`);

      const desc = escapeXml(descLines.join(" | "));
      return `    <Placemark>
      <name>${escapeXml(p.name)}</name>
      <description>${desc}</description>
      <Point>
        <coordinates>${p.longitude},${p.latitude},0</coordinates>
      </Point>
    </Placemark>`;
    })
    .join("\n");

  const kmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Vistarae Saved Places</name>
    <description>Points of Interest exported from Vistarae</description>
${placemarks}
  </Document>
</kml>`;

  const blob = new Blob([kmlContent], { type: "application/vnd.google-earth.kml+xml;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const dateStr = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `vistarae_places_${dateStr}.kml`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(
    selectedPoiIds.size > 0
      ? `Exported ${poisWithCoords.length} selected places to KML! Ready for Google My Maps import.`
      : `Exported ${poisWithCoords.length} places to KML! Ready for Google My Maps import.`
  );
}

// Modal wiring if gmaps-list-modal is used
const gmapsModal = document.getElementById("gmaps-list-modal");
const gmapsModalClose = document.getElementById("gmaps-modal-close");
const gmapsModalDoneBtn = document.getElementById("gmaps-modal-done-btn");
const gmapsModalPlotBtn = document.getElementById("gmaps-modal-plot-btn");
const gmapsLocationsList = document.getElementById("gmaps-locations-list");
const gmapsModalStats = document.getElementById("gmaps-modal-stats");
const gmapsOpenAllBtn = document.getElementById("gmaps-open-all-btn");

if (gmapsModalClose) gmapsModalClose.onclick = () => (gmapsModal.style.display = "none");
if (gmapsModalDoneBtn) gmapsModalDoneBtn.onclick = () => (gmapsModal.style.display = "none");
if (gmapsModalPlotBtn) {
  gmapsModalPlotBtn.onclick = () => {
    gmapsModal.style.display = "none";
    togglePlacesMap();
  };
}
if (gmapsModal) {
  gmapsModal.addEventListener("click", (e) => {
    if (e.target === gmapsModal) {
      gmapsModal.style.display = "none";
    }
  });
}
if (gmapsOpenAllBtn) {
  gmapsOpenAllBtn.onclick = () => {
    const poisWithCoords = filteredPois.filter(hasValidCoordinates);
    const toOpen = poisWithCoords.slice(0, 10);
    toOpen.forEach((p) => {
      const url = `https://www.google.com/maps/search/?api=1&query=${p.latitude},${p.longitude}`;
      openUrlInNewTab(url);
    });
    if (poisWithCoords.length > 10) {
      showToast(`Opened first 10 locations in individual Google Maps tabs`);
    } else {
      showToast(`Opened ${toOpen.length} locations in Google Maps tabs!`);
    }
  };
}

// ==========================================
// Map Pin Colors & Dynamic Rules Engine
// ==========================================

const PIN_COLOR_PRESETS = {
  preset_star_rating: {
    id: "preset_star_rating",
    name: "Star Rating",
    rules: [
      { field: "personal_rating", operator: "equal", value: "5", action: "color", color: "#eab308" },
      { field: "personal_rating", operator: "equal", value: "4", action: "color", color: "#22c55e" },
      { field: "personal_rating", operator: "equal", value: "3", action: "color", color: "#3b82f6" },
      { field: "personal_rating", operator: "equal", value: "2", action: "color", color: "#f97316" },
      { field: "personal_rating", operator: "equal", value: "1", action: "color", color: "#ef4444" },
    ],
    defaultAction: "color",
    defaultColor: "#94a3b8",
  },
  preset_visited_status: {
    id: "preset_visited_status",
    name: "Visited Status",
    rules: [
      { field: "visited_status", operator: "equal", value: "Visited & Visit Again", action: "color", color: "#8b5cf6" },
      { field: "visited_status", operator: "equal", value: "Visited (No Revisit)", action: "color", color: "#06b6d4" },
      { field: "visited_status", operator: "equal", value: "Unvisited", action: "color", color: "#f43f5e" },
    ],
    defaultAction: "color",
    defaultColor: "#94a3b8",
  },
  preset_cost_tier: {
    id: "preset_cost_tier",
    name: "Cost Tier",
    rules: [
      { field: "cost_tier", operator: "equal", value: "Free", action: "color", color: "#10b981" },
      { field: "cost_tier", operator: "equal", value: "$", action: "color", color: "#3b82f6" },
      { field: "cost_tier", operator: "equal", value: "$$", action: "color", color: "#f59e0b" },
      { field: "cost_tier", operator: "equal", value: "$$$", action: "color", color: "#f97316" },
      { field: "cost_tier", operator: "equal", value: "$$$$", action: "color", color: "#ec4899" },
    ],
    defaultAction: "color",
    defaultColor: "#64748b",
  },
  preset_poi_type: {
    id: "preset_poi_type",
    name: "POI Type",
    rules: [
      { field: "poi_type", operator: "equal", value: "site to see", action: "color", color: "#6366f1" },
      { field: "poi_type", operator: "equal", value: "photo location", action: "color", color: "#a855f7" },
      { field: "poi_type", operator: "equal", value: "scenic overlook", action: "color", color: "#0284c7" },
      { field: "poi_type", operator: "equal", value: "trailhead", action: "color", color: "#16a34a" },
      { field: "poi_type", operator: "equal", value: "campsite", action: "color", color: "#d97706" },
      { field: "poi_type", operator: "equal", value: "museum", action: "color", color: "#dc2626" },
      { field: "poi_type", operator: "equal", value: "historical site", action: "color", color: "#e11d48" },
      { field: "poi_type", operator: "equal", value: "food/drink", action: "color", color: "#ea580c" },
      { field: "poi_type", operator: "equal", value: "lodging", action: "color", color: "#0891b2" },
      { field: "poi_type", operator: "equal", value: "transit", action: "color", color: "#475569" },
      { field: "poi_type", operator: "equal", value: "experience", action: "color", color: "#0d9488" },
    ],
    defaultAction: "color",
    defaultColor: "#64748b",
  },
};

const PIN_RULE_FIELDS = [
  { value: "personal_rating", label: "Star Rating (1-5)" },
  { value: "visited_status", label: "Visited Status (Visited & Revisit, Visited, Unvisited)" },
  { value: "visited", label: "Visited (true / false)" },
  { value: "visit_again", label: "Visit Again (true / false)" },
  { value: "cost_tier", label: "Cost Tier (Free, $, $$, $$$, $$$$)" },
  { value: "poi_type", label: "POI Type" },
  { value: "category_tags", label: "Category Tags" },
  { value: "name", label: "Place Name" },
  { value: "iptc_city", label: "City" },
  { value: "iptc_province_state", label: "State / Province" },
  { value: "iptc_country_code", label: "Country Code" },
  { value: "indoor_outdoor", label: "Indoor / Outdoor" },
  { value: "physical_effort", label: "Physical Effort" },
  { value: "source_type", label: "Source Type" },
  { value: "visit_date", label: "Visit Date (YYYY-MM-DD)" },
  { value: "created_at", label: "Captured Date" },
];

const PIN_RULE_OPERATORS = [
  { value: "equal", label: "equal (=)" },
  { value: "not_equal", label: "not equal (!=)" },
  { value: "greater_than", label: "greater than (>)" },
  { value: "less_than", label: "less than (<)" },
  { value: "greater_equal", label: "greater or equal (>=)" },
  { value: "less_equal", label: "less or equal (<=)" },
  { value: "regex", label: "regex matches" },
  { value: "contains", label: "contains text" },
];

let currentEditingScheme = {
  id: null,
  name: "",
  rules: [],
  defaultAction: "color",
  defaultColor: "#0d9488",
};

function createColoredPinIcon(color = "#0d9488") {
  const safeColor = escapeHtml(color || "#0d9488");
  const svg = `<svg width="26" height="34" viewBox="0 0 26 34" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.38)); display: block;"><path d="M13 0C5.82 0 0 5.82 0 13C0 22.75 13 34 13 34C13 34 26 22.75 26 13C26 5.82 20.18 0 13 0Z" fill="${safeColor}" stroke="#ffffff" stroke-width="1.5"/><circle cx="13" cy="12" r="4.5" fill="#ffffff" opacity="0.95"/></svg>`;
  return L.divIcon({
    className: "vistarae-colored-pin",
    html: `<div style="width:26px; height:34px;">${svg}</div>`,
    iconSize: [26, 34],
    iconAnchor: [13, 34],
    popupAnchor: [0, -32],
  });
}

function getPoiVisitedStatus(poi) {
  if (poi && (poi.visited || poi.visit_date)) {
    if (poi.visit_again) return "Visited & Visit Again";
    return "Visited (No Revisit)";
  }
  return "Unvisited";
}

function evaluateRuleCondition(fieldVal, operator, targetVal, fieldName) {
  if (operator === "regex") {
    try {
      const re = new RegExp(targetVal, "i");
      if (Array.isArray(fieldVal)) {
        return fieldVal.some((v) => re.test(String(v || "")));
      }
      return re.test(String(fieldVal ?? ""));
    } catch {
      return false;
    }
  }

  // Handle category_tags array
  if (Array.isArray(fieldVal)) {
    const tLower = String(targetVal || "").trim().toLowerCase();
    if (operator === "equal") {
      return fieldVal.some((v) => String(v).trim().toLowerCase() === tLower);
    }
    if (operator === "not_equal") {
      return !fieldVal.some((v) => String(v).trim().toLowerCase() === tLower);
    }
    if (operator === "contains") {
      return fieldVal.some((v) => String(v).toLowerCase().includes(tLower));
    }
    return false;
  }

  // Handle booleans
  if (typeof fieldVal === "boolean" || fieldName === "visited" || fieldName === "visit_again") {
    const boolVal = Boolean(fieldVal);
    const targetStr = String(targetVal || "").trim().toLowerCase();
    const targetBool = ["true", "yes", "1", "t", "y"].includes(targetStr);
    if (operator === "equal") return boolVal === targetBool;
    if (operator === "not_equal") return boolVal !== targetBool;
    return false;
  }

  // Handle visited_status virtual field
  if (fieldName === "visited_status") {
    const statusStr = String(fieldVal || "").trim().toLowerCase();
    const targetStr = String(targetVal || "").trim().toLowerCase();
    const match = statusStr === targetStr ||
      (targetStr.includes("revisit") && statusStr.includes("again")) ||
      (targetStr === "visited" && statusStr.startsWith("visited")) ||
      (targetStr === "unvisited" && statusStr === "unvisited");
    if (operator === "equal") return match;
    if (operator === "not_equal") return !match;
    if (operator === "contains") return statusStr.includes(targetStr);
    return false;
  }

  // Handle dates
  const isDateField = ["visit_date", "created_at"].includes(fieldName) ||
    (/^\d{4}-\d{2}-\d{2}/.test(String(fieldVal || "")) && /^\d{4}-\d{2}-\d{2}/.test(String(targetVal || "")));

  if (isDateField) {
    const d1 = fieldVal ? new Date(fieldVal).getTime() : NaN;
    const d2 = targetVal ? new Date(targetVal).getTime() : NaN;
    if (!isNaN(d1) && !isNaN(d2)) {
      if (operator === "equal") {
        const s1 = new Date(fieldVal).toISOString().slice(0, 10);
        const s2 = new Date(targetVal).toISOString().slice(0, 10);
        return s1 === s2;
      }
      if (operator === "not_equal") return d1 !== d2;
      if (operator === "greater_than") return d1 > d2;
      if (operator === "less_than") return d1 < d2;
      if (operator === "greater_equal") return d1 >= d2;
      if (operator === "less_equal") return d1 <= d2;
    }
  }

  // Handle numbers
  const num1 = fieldVal !== null && fieldVal !== undefined && fieldVal !== "" ? Number(fieldVal) : NaN;
  const num2 = targetVal !== null && targetVal !== undefined && targetVal !== "" ? Number(targetVal) : NaN;
  const areBothNumbers = !isNaN(num1) && !isNaN(num2);

  if (areBothNumbers) {
    if (operator === "equal") return num1 === num2;
    if (operator === "not_equal") return num1 !== num2;
    if (operator === "greater_than") return num1 > num2;
    if (operator === "less_than") return num1 < num2;
    if (operator === "greater_equal") return num1 >= num2;
    if (operator === "less_equal") return num1 <= num2;
  }

  // Handle strings
  const str1 = String(fieldVal ?? "").trim().toLowerCase();
  const str2 = String(targetVal ?? "").trim().toLowerCase();

  if (operator === "equal") return str1 === str2;
  if (operator === "not_equal") return str1 !== str2;
  if (operator === "contains") return str1.includes(str2);
  if (operator === "greater_than") return str1 > str2;
  if (operator === "less_than") return str1 < str2;
  if (operator === "greater_equal") return str1 >= str2;
  if (operator === "less_equal") return str1 <= str2;

  return false;
}

function evaluatePoiColorScheme(poi, scheme) {
  if (!scheme || !scheme.rules || scheme.rules.length === 0) {
    return {
      action: scheme?.defaultAction || "color",
      color: scheme?.defaultColor || "#0d9488",
    };
  }

  for (const rule of scheme.rules) {
    let fieldVal;
    if (rule.field === "visited_status") {
      fieldVal = getPoiVisitedStatus(poi);
    } else {
      fieldVal = poi[rule.field];
    }

    const matches = evaluateRuleCondition(fieldVal, rule.operator, rule.value, rule.field);
    if (matches) {
      if (rule.action === "hide") {
        return { action: "hide" };
      }
      return {
        action: "color",
        color: rule.color || "#0d9488",
      };
    }
  }

  if (scheme.defaultAction === "hide") {
    return { action: "hide" };
  }
  return {
    action: "color",
    color: scheme.defaultColor || "#0d9488",
  };
}

function updatePinColorToolbarUI() {
  const badge = document.getElementById("map-pin-colors-badge");
  const clearBtn = document.getElementById("map-clear-pin-colors-btn");
  if (activePinColorScheme) {
    if (badge) {
      badge.style.display = "inline-block";
      badge.textContent = activePinColorScheme.name || "Active";
    }
    if (clearBtn) {
      clearBtn.style.display = "inline-flex";
    }
  } else {
    if (badge) badge.style.display = "none";
    if (clearBtn) clearBtn.style.display = "none";
  }
}

function applyPinColorScheme(scheme) {
  if (!scheme) return;
  activePinColorScheme = JSON.parse(JSON.stringify(scheme));
  chrome.storage.local.set({ vistarae_active_pin_scheme: activePinColorScheme });
  updatePinColorToolbarUI();
  if (mapContainerCard && mapContainerCard.style.display !== "none") {
    plotPlacesOnMap(true);
  }
  showToast(`Applied pin color scheme: "${scheme.name || 'Custom'}"`);
}

function clearPinColorScheme() {
  activePinColorScheme = null;
  chrome.storage.local.remove(["vistarae_active_pin_scheme"]);
  updatePinColorToolbarUI();
  if (mapContainerCard && mapContainerCard.style.display !== "none") {
    plotPlacesOnMap(true);
  }
  closePinColorsModal();
  showToast("Cleared pin coloring scheme. Restored default markers.");
}

function openPinColorsModal() {
  const modal = document.getElementById("pin-colors-modal");
  if (!modal) return;

  // Initialize editing scheme from active or default preset
  if (activePinColorScheme) {
    currentEditingScheme = JSON.parse(JSON.stringify(activePinColorScheme));
  } else if (!currentEditingScheme || !currentEditingScheme.rules || currentEditingScheme.rules.length === 0) {
    currentEditingScheme = JSON.parse(JSON.stringify(PIN_COLOR_PRESETS.preset_star_rating));
  }

  // Update scope notice
  const shouldCluster = (mapClusterToggle && mapClusterToggle.checked) || (pageClusterToggle && pageClusterToggle.checked);
  const clusterWarn = document.getElementById("pin-colors-cluster-warning");
  const toggleClusterBtn = document.getElementById("pin-colors-toggle-cluster-btn");
  if (clusterWarn) clusterWarn.style.display = shouldCluster ? "inline" : "none";
  if (toggleClusterBtn) {
    toggleClusterBtn.textContent = shouldCluster ? "Turn Off Clustering" : "Clustering is OFF (Active)";
    toggleClusterBtn.disabled = !shouldCluster;
  }

  // Update active scheme label
  const activeLabel = document.getElementById("pin-active-scheme-text");
  if (activeLabel) {
    activeLabel.textContent = activePinColorScheme ? (activePinColorScheme.name || "Custom") : "None (Default Pins)";
  }

  // Populate saved schemes dropdown
  refreshSavedSchemesOptgroup();

  // Set scheme name input
  const nameInput = document.getElementById("pin-scheme-name-input");
  if (nameInput) nameInput.value = currentEditingScheme.name || "";

  // Set default fallback inputs
  const defaultActionColor = document.getElementById("pin-default-action-color");
  const defaultActionHide = document.getElementById("pin-default-action-hide");
  const defaultColorPicker = document.getElementById("pin-default-color-picker");
  const defaultColorText = document.getElementById("pin-default-color-text");

  if (currentEditingScheme.defaultAction === "hide") {
    if (defaultActionHide) defaultActionHide.checked = true;
  } else {
    if (defaultActionColor) defaultActionColor.checked = true;
  }
  const defColor = currentEditingScheme.defaultColor || "#0d9488";
  if (defaultColorPicker) defaultColorPicker.value = defColor;
  if (defaultColorText) defaultColorText.value = defColor;

  renderPinRulesList();
  modal.style.display = "flex";
}

function closePinColorsModal() {
  const modal = document.getElementById("pin-colors-modal");
  if (modal) modal.style.display = "none";
}

function refreshSavedSchemesOptgroup() {
  const optgroup = document.getElementById("pin-saved-schemes-optgroup");
  const deleteBtn = document.getElementById("pin-delete-saved-btn");
  if (!optgroup) return;

  optgroup.innerHTML = "";
  if (savedPinSchemes.length === 0) {
    const emptyOpt = document.createElement("option");
    emptyOpt.value = "";
    emptyOpt.textContent = "(No saved custom schemes yet)";
    emptyOpt.disabled = true;
    optgroup.appendChild(emptyOpt);
  } else {
    savedPinSchemes.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `💾 ${s.name} (${s.rules?.length || 0} rules)`;
      optgroup.appendChild(opt);
    });
  }

  // Check if currentEditingScheme is a saved scheme
  const isSaved = currentEditingScheme?.id && savedPinSchemes.some((s) => s.id === currentEditingScheme.id);
  if (deleteBtn) deleteBtn.style.display = isSaved ? "inline-block" : "none";
}

function renderPinRulesList() {
  const container = document.getElementById("pin-rules-list");
  const emptyState = document.getElementById("pin-rules-empty-state");
  if (!container) return;

  container.innerHTML = "";
  const rules = currentEditingScheme.rules || [];

  if (rules.length === 0) {
    if (emptyState) emptyState.style.display = "block";
    return;
  }
  if (emptyState) emptyState.style.display = "none";

  rules.forEach((rule, idx) => {
    const row = document.createElement("div");
    row.className = "pin-rule-row";
    row.dataset.index = idx;

    // 1. Order cell
    const orderCell = document.createElement("div");
    orderCell.className = "rule-order-cell";
    orderCell.innerHTML = `
      <button type="button" class="rule-btn-move rule-btn-up" title="Move Up" ${idx === 0 ? "disabled" : ""}>▲</button>
      <span class="rule-priority-badge">#${idx + 1}</span>
      <button type="button" class="rule-btn-move rule-btn-down" title="Move Down" ${idx === rules.length - 1 ? "disabled" : ""}>▼</button>
    `;

    // 2. Field cell
    const fieldCell = document.createElement("div");
    fieldCell.className = "rule-field-cell";
    const fieldSelect = document.createElement("select");
    fieldSelect.className = "pin-rule-select";
    fieldSelect.style.width = "100%";
    PIN_RULE_FIELDS.forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.value;
      opt.textContent = f.label;
      if (rule.field === f.value) opt.selected = true;
      fieldSelect.appendChild(opt);
    });

    // 3. Operator cell
    const opCell = document.createElement("div");
    opCell.className = "rule-op-cell";
    const opSelect = document.createElement("select");
    opSelect.className = "pin-rule-select";
    opSelect.style.width = "100%";
    PIN_RULE_OPERATORS.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.value;
      opt.textContent = o.label;
      if (rule.operator === o.value) opt.selected = true;
      opSelect.appendChild(opt);
    });

    // 4. Value cell
    const valCell = document.createElement("div");
    valCell.className = "rule-val-cell";
    const valInput = document.createElement("input");
    valInput.type = "text";
    valInput.className = "pin-rule-input";
    valInput.style.width = "100%";
    valInput.value = rule.value ?? "";
    valInput.placeholder = "Match value...";

    // 5. Action cell
    const actionCell = document.createElement("div");
    actionCell.className = "rule-action-cell";
    const actionSelect = document.createElement("select");
    actionSelect.className = "pin-rule-select";
    actionSelect.style.width = "100%";
    const optColor = document.createElement("option");
    optColor.value = "color";
    optColor.textContent = "Color";
    const optHide = document.createElement("option");
    optHide.value = "hide";
    optHide.textContent = "Hide Pin";
    if (rule.action === "hide") optHide.selected = true;
    else optColor.selected = true;
    actionSelect.appendChild(optColor);
    actionSelect.appendChild(optHide);

    // 6. Color cell
    const colorCell = document.createElement("div");
    colorCell.className = "rule-color-cell";
    const colorPicker = document.createElement("input");
    colorPicker.type = "color";
    colorPicker.className = "rule-color-picker";
    colorPicker.value = rule.color || "#0d9488";
    if (rule.action === "hide") colorPicker.style.display = "none";
    colorCell.appendChild(colorPicker);

    // 7. Delete cell
    const delCell = document.createElement("div");
    delCell.className = "rule-delete-cell";
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "rule-btn-delete";
    delBtn.innerHTML = "&times;";
    delBtn.title = "Delete Rule";
    delCell.appendChild(delBtn);

    // Event bindings
    orderCell.querySelector(".rule-btn-up")?.addEventListener("click", () => {
      if (idx > 0) {
        const temp = rules[idx];
        rules[idx] = rules[idx - 1];
        rules[idx - 1] = temp;
        renderPinRulesList();
      }
    });

    orderCell.querySelector(".rule-btn-down")?.addEventListener("click", () => {
      if (idx < rules.length - 1) {
        const temp = rules[idx];
        rules[idx] = rules[idx + 1];
        rules[idx + 1] = temp;
        renderPinRulesList();
      }
    });

    fieldSelect.addEventListener("change", (e) => {
      rule.field = e.target.value;
    });

    opSelect.addEventListener("change", (e) => {
      rule.operator = e.target.value;
    });

    valInput.addEventListener("input", (e) => {
      rule.value = e.target.value;
    });

    actionSelect.addEventListener("change", (e) => {
      rule.action = e.target.value;
      colorPicker.style.display = rule.action === "hide" ? "none" : "block";
    });

    colorPicker.addEventListener("input", (e) => {
      rule.color = e.target.value;
    });

    delBtn.addEventListener("click", () => {
      rules.splice(idx, 1);
      renderPinRulesList();
    });

    row.appendChild(orderCell);
    row.appendChild(fieldCell);
    row.appendChild(opCell);
    row.appendChild(valCell);
    row.appendChild(actionCell);
    row.appendChild(colorCell);
    row.appendChild(delCell);

    container.appendChild(row);
  });
}

function addBlankPinRule() {
  if (!currentEditingScheme.rules) {
    currentEditingScheme.rules = [];
  }
  currentEditingScheme.rules.push({
    field: "personal_rating",
    operator: "equal",
    value: "5",
    action: "color",
    color: "#eab308",
  });
  renderPinRulesList();
  const container = document.getElementById("pin-rules-list");
  if (container) container.scrollTop = container.scrollHeight;
}

function initPinColorsModalListeners() {
  const modal = document.getElementById("pin-colors-modal");
  const closeBtn = document.getElementById("pin-colors-close-btn");
  const cancelBtn = document.getElementById("pin-colors-cancel-btn");
  const applyBtn = document.getElementById("pin-colors-apply-btn");
  const clearBtn = document.getElementById("pin-clear-scheme-btn");
  const addRuleBtn = document.getElementById("pin-add-rule-btn");
  const presetSelect = document.getElementById("pin-preset-select");
  const loadPresetBtn = document.getElementById("pin-load-preset-btn");
  const deleteSavedBtn = document.getElementById("pin-delete-saved-btn");
  const saveSchemeBtn = document.getElementById("pin-save-scheme-btn");
  const schemeNameInput = document.getElementById("pin-scheme-name-input");
  const toggleClusterBtn = document.getElementById("pin-colors-toggle-cluster-btn");

  const defaultActionColor = document.getElementById("pin-default-action-color");
  const defaultActionHide = document.getElementById("pin-default-action-hide");
  const defaultColorPicker = document.getElementById("pin-default-color-picker");
  const defaultColorText = document.getElementById("pin-default-color-text");

  if (closeBtn) closeBtn.addEventListener("click", closePinColorsModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closePinColorsModal);

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closePinColorsModal();
    });
  }

  if (addRuleBtn) addRuleBtn.addEventListener("click", addBlankPinRule);

  if (defaultActionColor) {
    defaultActionColor.addEventListener("change", () => {
      currentEditingScheme.defaultAction = "color";
    });
  }
  if (defaultActionHide) {
    defaultActionHide.addEventListener("change", () => {
      currentEditingScheme.defaultAction = "hide";
    });
  }
  if (defaultColorPicker) {
    defaultColorPicker.addEventListener("input", (e) => {
      currentEditingScheme.defaultColor = e.target.value;
      if (defaultColorText) defaultColorText.value = e.target.value;
    });
  }
  if (defaultColorText) {
    defaultColorText.addEventListener("input", (e) => {
      if (/^#[0-9a-f]{6}$/i.test(e.target.value)) {
        currentEditingScheme.defaultColor = e.target.value;
        if (defaultColorPicker) defaultColorPicker.value = e.target.value;
      }
    });
  }

  if (toggleClusterBtn) {
    toggleClusterBtn.addEventListener("click", () => {
      setClusterEnabled(false, false);
      const clusterWarn = document.getElementById("pin-colors-cluster-warning");
      if (clusterWarn) clusterWarn.style.display = "none";
      toggleClusterBtn.textContent = "Clustering is OFF (Active)";
      toggleClusterBtn.disabled = true;
      showToast("Marker clustering turned off. Individual colored pins are now visible on map.");
    });
  }

  const handleLoadSelected = () => {
    const val = presetSelect?.value;
    if (!val) return;

    if (PIN_COLOR_PRESETS[val]) {
      const preset = PIN_COLOR_PRESETS[val];
      currentEditingScheme = {
        id: preset.id,
        name: preset.name,
        rules: JSON.parse(JSON.stringify(preset.rules)),
        defaultAction: preset.defaultAction || "color",
        defaultColor: preset.defaultColor || "#0d9488",
      };
      if (schemeNameInput) schemeNameInput.value = preset.name;
      if (defaultActionColor) defaultActionColor.checked = currentEditingScheme.defaultAction === "color";
      if (defaultActionHide) defaultActionHide.checked = currentEditingScheme.defaultAction === "hide";
      if (defaultColorPicker) defaultColorPicker.value = currentEditingScheme.defaultColor;
      if (defaultColorText) defaultColorText.value = currentEditingScheme.defaultColor;
      if (deleteSavedBtn) deleteSavedBtn.style.display = "none";
      renderPinRulesList();
      showToast(`Loaded preset "${preset.name}".`);
    } else {
      const saved = savedPinSchemes.find((s) => s.id === val);
      if (saved) {
        currentEditingScheme = JSON.parse(JSON.stringify(saved));
        if (schemeNameInput) schemeNameInput.value = saved.name;
        if (defaultActionColor) defaultActionColor.checked = currentEditingScheme.defaultAction === "color";
        if (defaultActionHide) defaultActionHide.checked = currentEditingScheme.defaultAction === "hide";
        if (defaultColorPicker) defaultColorPicker.value = currentEditingScheme.defaultColor || "#0d9488";
        if (defaultColorText) defaultColorText.value = currentEditingScheme.defaultColor || "#0d9488";
        if (deleteSavedBtn) deleteSavedBtn.style.display = "inline-block";
        renderPinRulesList();
        showToast(`Loaded saved scheme "${saved.name}".`);
      }
    }
  };

  if (loadPresetBtn) loadPresetBtn.addEventListener("click", handleLoadSelected);
  if (presetSelect) presetSelect.addEventListener("change", handleLoadSelected);

  if (saveSchemeBtn) {
    saveSchemeBtn.addEventListener("click", () => {
      const name = (schemeNameInput?.value || "").trim();
      if (!name) {
        showToast("Please enter a name to save this scheme.", true);
        schemeNameInput?.focus();
        return;
      }

      currentEditingScheme.name = name;
      currentEditingScheme.defaultAction = defaultActionHide?.checked ? "hide" : "color";
      currentEditingScheme.defaultColor = defaultColorPicker?.value || "#0d9488";

      const existingIdx = savedPinSchemes.findIndex((s) => s.id === currentEditingScheme.id);
      if (existingIdx !== -1) {
        savedPinSchemes[existingIdx] = JSON.parse(JSON.stringify(currentEditingScheme));
      } else {
        currentEditingScheme.id = "saved_" + Date.now();
        savedPinSchemes.push(JSON.parse(JSON.stringify(currentEditingScheme)));
      }

      chrome.storage.local.set({ vistarae_saved_pin_schemes: savedPinSchemes });
      refreshSavedSchemesOptgroup();
      if (presetSelect) presetSelect.value = currentEditingScheme.id;
      if (deleteSavedBtn) deleteSavedBtn.style.display = "inline-block";
      showToast(`Scheme "${name}" saved successfully!`);
    });
  }

  if (deleteSavedBtn) {
    deleteSavedBtn.addEventListener("click", () => {
      if (!currentEditingScheme.id) return;
      const idx = savedPinSchemes.findIndex((s) => s.id === currentEditingScheme.id);
      if (idx !== -1) {
        const deletedName = savedPinSchemes[idx].name;
        savedPinSchemes.splice(idx, 1);
        chrome.storage.local.set({ vistarae_saved_pin_schemes: savedPinSchemes });
        refreshSavedSchemesOptgroup();
        if (presetSelect) presetSelect.value = "";
        deleteSavedBtn.style.display = "none";
        showToast(`Deleted scheme "${deletedName}".`);
      }
    });
  }

  if (clearBtn) clearBtn.addEventListener("click", clearPinColorScheme);

  if (applyBtn) {
    applyBtn.addEventListener("click", () => {
      currentEditingScheme.name = (schemeNameInput?.value || "").trim() || "Custom Scheme";
      currentEditingScheme.defaultAction = defaultActionHide?.checked ? "hide" : "color";
      currentEditingScheme.defaultColor = defaultColorPicker?.value || "#0d9488";

      applyPinColorScheme(currentEditingScheme);
      closePinColorsModal();
    });
  }
}

// ==========================================
// 1. Associated Photo Folders in POI Edit Modal
// ==========================================

async function loadPoiAssociatedFolders(poiId) {
  const container = document.getElementById("edit-poi-paths-list");
  const countEl = document.getElementById("edit-poi-paths-count");
  if (!container || !poiId) return;

  container.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">Loading associated folders...</span>';
  if (countEl) countEl.textContent = "Loading...";

  try {
    const res = await apiFetch(`/api/v1/scanned-paths?poi_id=${poiId}&limit=100&include_hidden=true`);
    if (!res.ok) throw new Error("Failed to load associated folders");
    const data = await res.json();
    const items = data.items || [];
    if (currentEditingPoi && currentEditingPoi.id === poiId) {
      currentEditingPoi._associatedFolders = items;
    }

    if (countEl) countEl.textContent = `${items.length} folder${items.length === 1 ? '' : 's'}`;

    if (items.length === 0) {
      container.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">No associated folders found for this place.</span>';
      return;
    }

    container.innerHTML = "";
    items.forEach(pathItem => {
      const row = document.createElement("div");
      row.className = "associated-folder-row";
      
      const statusPillClass = `status-pill-${(pathItem.status || 'unknown').replace(/\s+/g, '-')}`;
      const isSkipped = pathItem.status === "skipped";
      const isHidden = pathItem.status === "hidden";
      const hasConflict = Boolean(pathItem.has_conflict);
      const conflictNames = pathItem.conflict_poi_names || [];

      row.innerHTML = `
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
            <span class="status-pill ${statusPillClass}">${escapeHtml(pathItem.status)}</span>
            ${hasConflict ? `<span class="status-pill status-pill-conflict" title="Folder is associated with multiple places">⚠️ Conflict</span>` : ''}
            <strong style="font-size: 12.5px; color: var(--text-main);">${escapeHtml(pathItem.folder_name || 'Folder')}</strong>
            <span style="font-size: 11px; color: var(--text-muted);">(${pathItem.photo_count || 0} photos)</span>
          </div>
          <div class="associated-folder-path" title="${escapeHtml(pathItem.folder_path)}">${escapeHtml(pathItem.folder_path)}</div>
          ${hasConflict ? `
            <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 4px; padding: 6px 10px; margin-top: 6px; font-size: 11.5px; color: #92400e; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <span>⚠️ <strong>Conflict Flagged:</strong> Also linked to <strong>${escapeHtml(conflictNames.join(', ') || 'another place')}</strong>.</span>
              <button type="button" class="btn btn-secondary btn-sm resolve-conflict-btn" style="padding: 2px 8px; font-size: 11px; color: #b45309; border-color: #fde68a; background: #ffffff;">
                Resolve Conflict
              </button>
            </div>
          ` : ''}
        </div>
        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          <a href="${getFolderProtocolUrl(pathItem.folder_path)}" class="btn btn-secondary btn-sm folder-open-link" data-path="${escapeHtml(pathItem.folder_path)}" style="padding: 3px 8px; font-size: 11px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;" title="Open folder in File Explorer">
            📁 Open
          </a>
          ${isSkipped ? `
            <button type="button" class="btn btn-secondary btn-sm toggle-hide-btn" style="padding: 3px 8px; font-size: 11px;" title="Make folder state hidden">
              👁️‍🗨️ Hide
            </button>
          ` : ''}
          ${isHidden ? `
            <button type="button" class="btn btn-secondary btn-sm toggle-unhide-btn" style="padding: 3px 8px; font-size: 11px;" title="Make folder state back to skipped">
              👁️ Unhide
            </button>
          ` : ''}
          <button type="button" class="btn btn-secondary btn-sm disassociate-path-btn" style="padding: 3px 8px; font-size: 11px; color: #dc2626;" title="Remove this folder association from this place">
            ✖ Remove
          </button>
          <button type="button" class="btn btn-secondary btn-sm split-path-btn" style="padding: 3px 8px; font-size: 11px;" title="Disassociate this folder and create a new unlocated POI">
            ⎘ Split to New POI
          </button>
        </div>
      `;

      const resolveBtn = row.querySelector(".resolve-conflict-btn");
      if (resolveBtn) {
        resolveBtn.onclick = async () => {
          try {
            const checkRes = await apiFetch(`/api/v1/pois/${poiId}/photo-folder`, {
              method: "POST",
              body: JSON.stringify({
                folder_path: pathItem.folder_path,
                action: "check"
              })
            });
            if (checkRes.ok) {
              const checkData = await checkRes.json();
              openFolderConflictModal(checkData, poiId, pathItem.folder_path);
            }
          } catch (err) {
            showToast("Error checking folder conflict: " + err.message, true);
          }
        };
      }

      const disassociateBtn = row.querySelector(".disassociate-path-btn");
      if (disassociateBtn) {
        disassociateBtn.onclick = async () => {
          if (!confirm(`Are you sure you want to remove the association with folder:\n"${pathItem.folder_path}"\nfrom this place?`)) {
            return;
          }
          try {
            const disRes = await apiFetch(`/api/v1/scanned-paths/${pathItem.id}/disassociate`, {
              method: "POST",
              body: JSON.stringify({ poi_id: poiId })
            });
            if (!disRes.ok) throw new Error("Failed to disassociate folder");
            showToast("Folder association removed.");
            await loadPoiAssociatedFolders(poiId);
            await fetchPois(true);
            if (foldersViewActive) await loadScannedFolders();
          } catch (err) {
            showToast(err.message, true);
          }
        };
      }

      const toggleHideBtn = row.querySelector(".toggle-hide-btn");
      if (toggleHideBtn) {
        toggleHideBtn.onclick = async () => {
          try {
            const r = await apiFetch(`/api/v1/scanned-paths/${pathItem.id}`, {
              method: "PATCH",
              body: JSON.stringify({ status: "hidden" })
            });
            if (!r.ok) throw new Error("Failed to set folder state to hidden");
            showToast("Folder state changed to hidden");
            await loadPoiAssociatedFolders(poiId);
            if (foldersViewActive) await loadScannedFolders();
          } catch (err) {
            showToast(err.message, true);
          }
        };
      }

      const toggleUnhideBtn = row.querySelector(".toggle-unhide-btn");
      if (toggleUnhideBtn) {
        toggleUnhideBtn.onclick = async () => {
          try {
            const r = await apiFetch(`/api/v1/scanned-paths/${pathItem.id}`, {
              method: "PATCH",
              body: JSON.stringify({ status: "skipped" })
            });
            if (!r.ok) throw new Error("Failed to set folder state back to skipped");
            showToast("Folder state changed back to skipped");
            await loadPoiAssociatedFolders(poiId);
            if (foldersViewActive) await loadScannedFolders();
          } catch (err) {
            showToast(err.message, true);
          }
        };
      }

      row.querySelector(".split-path-btn").onclick = async () => {
        if (!confirm(`Are you sure you want to disassociate this folder:\n"${pathItem.folder_path}"\n\nand split it into its own unlocated POI?`)) {
          return;
        }
        try {
          const splitRes = await apiFetch(`/api/v1/scanned-paths/${pathItem.id}/disassociate-and-split`, {
            method: "POST"
          });
          if (!splitRes.ok) throw new Error("Failed to disassociate and split path");
          const splitData = await splitRes.json();
          showToast(`Successfully split to new POI: "${splitData.new_poi_name}"`);
          await loadPoiAssociatedFolders(poiId);
          await fetchPois(true);
          if (foldersViewActive) await loadScannedFolders();
        } catch (err) {
          showToast(err.message, true);
        }
      };

      container.appendChild(row);
    });

  } catch (err) {
    container.innerHTML = `<span style="font-size: 12px; color: #ef4444;">Error loading folders: ${escapeHtml(err.message)}</span>`;
    if (countEl) countEl.textContent = "Error";
  }
}

// -----------------------------------------------------------------------------
// Photo Folder Attachment & Conflict Resolution Engine
// -----------------------------------------------------------------------------

async function populateScannedFoldersDatalist() {
  const datalist = document.getElementById("all-scanned-folders-datalist");
  if (!datalist) return;
  try {
    const res = await apiFetch("/api/v1/scanned-paths?limit=300&sort_by=folder_path&sort_order=asc");
    if (!res.ok) return;
    const data = await res.json();
    const items = data.items || [];
    datalist.innerHTML = "";
    items.forEach(item => {
      const opt = document.createElement("option");
      opt.value = item.folder_path;
      opt.label = `${item.folder_name || 'Folder'}${item.site_name ? ` (${item.site_name})` : ''}`;
      datalist.appendChild(opt);
    });
  } catch (err) {
    console.warn("Could not populate folders datalist", err);
  }
}

async function handleAttachPhotoFolder() {
  if (!currentEditingPoi) {
    showToast("No active place being edited.", true);
    return;
  }
  const folderPathInput = document.getElementById("edit-poi-folder-path-input");
  const folderAttachBtn = document.getElementById("edit-poi-folder-attach-btn");
  const addFolderBox = document.getElementById("edit-poi-add-folder-box");
  const folderPath = (folderPathInput?.value || "").trim();
  if (!folderPath) {
    showToast("Please enter or select a folder path.", true);
    return;
  }

  if (folderAttachBtn) folderAttachBtn.disabled = true;
  try {
    const res = await apiFetch(`/api/v1/pois/${currentEditingPoi.id}/photo-folder`, {
      method: "POST",
      body: JSON.stringify({
        folder_path: folderPath,
        action: "check"
      })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to attach folder");
    }
    const resData = await res.json();
    if (resData.conflict) {
      openFolderConflictModal(resData, currentEditingPoi.id, folderPath);
    } else {
      showToast(resData.message || "Folder attached successfully!");
      if (addFolderBox) addFolderBox.style.display = "none";
      if (folderPathInput) folderPathInput.value = "";
      await loadPoiAssociatedFolders(currentEditingPoi.id);
      await fetchPois(true);
      if (foldersViewActive) await loadScannedFolders();
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (folderAttachBtn) folderAttachBtn.disabled = false;
  }
}

function openDuplicateAbortModal(data) {
  const modal = document.getElementById("poi-photo-duplicate-abort-modal");
  const folderEl = document.getElementById("duplicate-abort-modal-folder");
  const poisListEl = document.getElementById("duplicate-abort-modal-pois-list");
  const alertBox = document.getElementById("edit-poi-folder-duplicate-alert");
  const alertMsg = document.getElementById("edit-poi-duplicate-alert-msg");
  const alertList = document.getElementById("edit-poi-duplicate-conflicting-pois");

  const folderPath = data.folder_path || "Selected folder";
  const conflictingPois = data.conflicting_pois || [];

  if (folderEl) folderEl.textContent = folderPath;
  if (alertMsg) alertMsg.textContent = `Folder "${folderPath}" is already linked to another place in your database. Association has been aborted.`;

  const renderCards = (container) => {
    if (!container) return;
    container.innerHTML = "";
    conflictingPois.forEach(cp => {
      const card = document.createElement("div");
      card.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: #ffffff; border: 1px solid #fecaca; border-radius: 6px;";
      card.innerHTML = `
        <div>
          <strong style="color: #991b1b; font-size: 12px;">${escapeHtml(cp.name)}</strong>
          <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">(${escapeHtml(cp.poi_type || 'site')})</span>
          ${cp.iptc_city || cp.iptc_country_code ? `<div style="font-size: 11px; color: var(--text-muted);">${escapeHtml([cp.iptc_city, cp.iptc_country_code].filter(Boolean).join(', '))}</div>` : ''}
        </div>
        <button type="button" class="btn btn-secondary btn-sm view-dup-poi-btn" style="padding: 2px 7px; font-size: 10.5px;">
          👁️ View Place
        </button>
      `;
      card.querySelector(".view-dup-poi-btn").onclick = () => {
        if (modal) modal.style.display = "none";
        const found = allPois.find(p => p.id === cp.id);
        if (found) {
          openEditModal(found);
        } else {
          apiFetch(`/api/v1/pois/${cp.id}`).then(r => r.json()).then(p => openEditModal(p));
        }
      };
      container.appendChild(card);
    });
  };

  renderCards(poisListEl);
  renderCards(alertList);

  if (alertBox) alertBox.style.display = "block";
  if (modal) modal.style.display = "flex";
}

let pendingMetadataApplication = null;
let modalPendingTags = [];

function renderModalTags() {
  const tagsCountEl = document.getElementById("meta-tags-count");
  const tagsChipsEl = document.getElementById("meta-tags-chips");
  const selectedCount = modalPendingTags.filter(t => t.checked).length;
  if (tagsCountEl) {
    tagsCountEl.textContent = String(selectedCount);
  }
  if (!tagsChipsEl) return;
  tagsChipsEl.innerHTML = "";

  if (modalPendingTags.length === 0) {
    const emptySpan = document.createElement("span");
    emptySpan.style.cssText = "font-size: 11.5px; color: var(--text-muted); font-style: italic; padding: 4px 0;";
    emptySpan.textContent = "No tags discovered or added yet. Type below to add.";
    tagsChipsEl.appendChild(emptySpan);
    return;
  }

  modalPendingTags.forEach((item, index) => {
    const pill = document.createElement("label");
    pill.className = "meta-tag-pill";
    pill.style.cssText = `display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 12px; font-size: 11.5px; cursor: pointer; user-select: none; transition: all 0.15s ease; background: ${item.checked ? "#ecfdf5" : "#f1f5f9"}; color: ${item.checked ? "#065f46" : "#64748b"}; border: 1px solid ${item.checked ? "#a7f3d0" : "#cbd5e1"};`;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = item.checked;
    cb.style.cssText = "margin: 0; cursor: pointer; accent-color: #059669;";
    cb.onchange = (e) => {
      item.checked = e.target.checked;
      renderModalTags();
    };

    const textSpan = document.createElement("span");
    textSpan.textContent = item.name;

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.innerHTML = "&times;";
    delBtn.title = "Remove tag";
    delBtn.style.cssText = "background: none; border: none; padding: 0 0 0 3px; color: inherit; font-size: 14px; line-height: 1; cursor: pointer; opacity: 0.65;";
    delBtn.onmouseenter = () => { delBtn.style.opacity = "1"; };
    delBtn.onmouseleave = () => { delBtn.style.opacity = "0.65"; };
    delBtn.onclick = (e) => {
      e.stopPropagation();
      e.preventDefault();
      modalPendingTags.splice(index, 1);
      renderModalTags();
    };

    pill.appendChild(cb);
    pill.appendChild(textSpan);
    pill.appendChild(delBtn);
    tagsChipsEl.appendChild(pill);
  });
}

function handleAddManualModalTag() {
  const input = document.getElementById("meta-new-tag-input");
  if (!input) return;
  const raw = input.value.trim();
  if (!raw) return;

  const tagsToAdd = raw.split(",").map(t => t.trim().toLowerCase()).filter(Boolean);
  tagsToAdd.forEach(tag => {
    const existing = modalPendingTags.find(t => t.name.toLowerCase() === tag.toLowerCase());
    if (existing) {
      existing.checked = true;
    } else {
      modalPendingTags.push({ name: tag, checked: true });
    }
  });

  input.value = "";
  input.focus();
  renderModalTags();
}

function isPoiFolderAlreadyAssociated(folderPath) {
  if (!folderPath) return false;
  const norm = folderPath.trim().toLowerCase().replace(/[\\/]+$/, "");
  if (!norm) return false;

  // 1. Check currentEditingPoi source_url
  if (currentEditingPoi?.source_url) {
    const normSource = currentEditingPoi.source_url.trim().toLowerCase().replace(/[\\/]+$/, "");
    if (normSource === norm) return true;
  }

  // 2. Check cached _associatedFolders on currentEditingPoi
  if (Array.isArray(currentEditingPoi?._associatedFolders)) {
    if (currentEditingPoi._associatedFolders.some(f => (f.folder_path || "").trim().toLowerCase().replace(/[\\/]+$/, "") === norm)) {
      return true;
    }
  }

  // 3. Check DOM items in edit-poi-paths-list
  const existingDomPaths = Array.from(document.querySelectorAll("#edit-poi-paths-list .associated-folder-path"))
    .map(el => (el.getAttribute("title") || el.textContent || "").trim().toLowerCase().replace(/[\\/]+$/, ""))
    .filter(Boolean);
  if (existingDomPaths.includes(norm)) {
    return true;
  }

  return false;
}

function updateModalFolderStatus(targetPath, isBackendAlreadyLinked = false) {
  const linkFolderCb = document.getElementById("meta-link-folder-cb");
  const folderBadge = document.getElementById("meta-folder-badge");
  const folderNote = document.getElementById("meta-folder-note");
  const folderPathEl = document.getElementById("meta-folder-path");
  const folderPathDisplay = document.getElementById("meta-folder-path-display");

  const resolved = (targetPath || "").trim();
  if (resolved) {
    if (folderPathEl) folderPathEl.textContent = resolved;
    if (folderPathDisplay) folderPathDisplay.style.display = "block";
  } else {
    if (folderPathDisplay) folderPathDisplay.style.display = "none";
  }

  const isAlreadyAdded = Boolean(isBackendAlreadyLinked || isPoiFolderAlreadyAssociated(resolved));

  if (isAlreadyAdded) {
    if (linkFolderCb) linkFolderCb.checked = false;
    if (folderBadge) {
      folderBadge.style.display = "inline";
      folderBadge.style.color = "#2563eb";
      folderBadge.textContent = "ℹ️ Already linked to this place";
    }
    if (folderNote) {
      folderNote.textContent = "This folder is already associated with this place and will not be re-added.";
      folderNote.style.color = "#2563eb";
    }
  } else {
    // Default enabled, user can choose to disable
    if (linkFolderCb) linkFolderCb.checked = true;
    if (folderBadge) {
      folderBadge.style.display = resolved ? "inline" : "none";
      folderBadge.style.color = "#059669";
      folderBadge.textContent = "✓ Auto-detected";
    }
    if (folderNote) {
      folderNote.textContent = "Links this folder to the place so it appears under 'Associated Scanned Folders'.";
      folderNote.style.color = "var(--text-muted)";
    }
  }
}

function openPhotoMetadataModal(metaData) {
  pendingMetadataApplication = metaData;
  const modal = document.getElementById("poi-photo-metadata-modal");
  if (!modal) return;

  const filenameEl = document.getElementById("meta-modal-filename");
  if (filenameEl) filenameEl.textContent = metaData.file_name || metaData.folder_path || "photo";

  // 1. Coordinates
  const coordsBox = document.getElementById("meta-coords-box");
  const coordsTitle = document.getElementById("meta-coords-title");
  const coordsFound = document.getElementById("meta-coords-found");
  const coordsDesc = document.getElementById("meta-coords-action-desc");
  const applyCoordsCb = document.getElementById("meta-apply-coords-cb");

  const hasGps = metaData.latitude != null && metaData.longitude != null;
  if (!hasGps) {
    if (coordsBox) coordsBox.style.display = "none";
    if (applyCoordsCb) applyCoordsCb.checked = false;
  } else {
    if (coordsBox) coordsBox.style.display = "block";
    if (coordsFound) coordsFound.textContent = `Lat: ${metaData.latitude.toFixed(6)}, Lng: ${metaData.longitude.toFixed(6)}`;

    const curLat = (document.getElementById("edit-lat")?.value || "").trim();
    const curLng = (document.getElementById("edit-lng")?.value || "").trim();
    const hasExistingCoords = Boolean(curLat && curLng);

    if (hasExistingCoords) {
      if (coordsTitle) coordsTitle.textContent = "📍 Replace Existing Coordinates";
      if (coordsDesc) coordsDesc.textContent = `Replace current coordinates (${parseFloat(curLat).toFixed(4)}, ${parseFloat(curLng).toFixed(4)}) with photo GPS coordinates.`;
    } else {
      if (coordsTitle) coordsTitle.textContent = "📍 Set Location Coordinates";
      if (coordsDesc) coordsDesc.textContent = "Place currently has no coordinates recorded. Set coordinates from photo GPS.";
    }
    if (applyCoordsCb) applyCoordsCb.checked = true;
  }

  // 2. Date
  const dateBox = document.getElementById("meta-date-box");
  const dateFound = document.getElementById("meta-date-found");
  const setVisitDateCb = document.getElementById("meta-set-visit-date-cb");
  const setVisitDateLabel = document.getElementById("meta-set-visit-date-label");
  const addVisitDatesCb = document.getElementById("meta-add-visit-dates-cb");
  const markVisitedCb = document.getElementById("meta-mark-visited-cb");

  if (!metaData.date_taken) {
    if (dateBox) dateBox.style.display = "none";
    if (setVisitDateCb) setVisitDateCb.checked = false;
    if (addVisitDatesCb) addVisitDatesCb.checked = false;
    if (markVisitedCb) markVisitedCb.checked = false;
  } else {
    if (dateBox) dateBox.style.display = "block";
    if (dateFound) dateFound.textContent = metaData.date_taken;

    const curVisitDate = (document.getElementById("edit-visit-date")?.value || "").trim();
    if (curVisitDate) {
      if (setVisitDateLabel) setVisitDateLabel.textContent = `Replace primary visit date (${curVisitDate} → ${metaData.date_taken})`;
    } else {
      if (setVisitDateLabel) setVisitDateLabel.textContent = `Set primary visit date to ${metaData.date_taken}`;
    }
    if (setVisitDateCb) setVisitDateCb.checked = true;
    if (addVisitDatesCb) addVisitDatesCb.checked = true;
    if (markVisitedCb) markVisitedCb.checked = true;
  }

  // 3. Tags (Discovered + Manual Selection)
  const tagsBox = document.getElementById("meta-tags-box");
  const newTagInput = document.getElementById("meta-new-tag-input");
  if (newTagInput) newTagInput.value = "";

  const rawTags = (metaData.tags || []).map(t => t.trim().toLowerCase()).filter(Boolean);
  const uniqueTags = Array.from(new Set(rawTags));
  modalPendingTags = uniqueTags.map(name => ({ name, checked: true }));

  if (tagsBox) tagsBox.style.display = "block";
  renderModalTags();

  // 4. Folder
  const folderBox = document.getElementById("meta-folder-box");
  const folderInput = document.getElementById("meta-folder-input");

  if (folderBox) folderBox.style.display = "block";
  const parentFolderInput = document.getElementById("edit-poi-folder-path-input");
  const resolvedPath = metaData.folder_path || (parentFolderInput?.value || "").trim();

  if (folderInput) {
    folderInput.value = resolvedPath;
    if (!folderInput._statusListenerAttached) {
      folderInput._statusListenerAttached = true;
      folderInput.addEventListener("input", (e) => {
        const val = e.target.value.trim();
        const isBackendLinked = Boolean(
          metaData.already_linked &&
          metaData.folder_path &&
          metaData.folder_path.trim().toLowerCase().replace(/[\\/]+$/, "") === val.toLowerCase().replace(/[\\/]+$/, "")
        );
        updateModalFolderStatus(val, isBackendLinked);
      });
    }
  }

  updateModalFolderStatus(resolvedPath, Boolean(metaData.already_linked));

  modal.style.display = "flex";
}

function openNoMetadataModal(fileName) {
  const modal = document.getElementById("poi-photo-no-metadata-modal");
  if (!modal) return;
  const nameEl = document.getElementById("no-meta-modal-filename");
  if (nameEl) nameEl.textContent = fileName || "selected photo";
  modal.style.display = "flex";
}

async function applySelectedPhotoMetadata() {
  if (!pendingMetadataApplication) return;
  const meta = pendingMetadataApplication;
  const modal = document.getElementById("poi-photo-metadata-modal");

  const applyCoords = document.getElementById("meta-apply-coords-cb")?.checked && meta.latitude != null && meta.longitude != null;
  const setVisitDate = document.getElementById("meta-set-visit-date-cb")?.checked && meta.date_taken;
  const addVisitDates = document.getElementById("meta-add-visit-dates-cb")?.checked && meta.date_taken;
  const folderInput = document.getElementById("meta-folder-input");
  const folderToLink = (folderInput?.value || meta.folder_path || "").trim();
  const linkFolder = document.getElementById("meta-link-folder-cb")?.checked && Boolean(folderToLink);

  // 1. Coordinates
  if (applyCoords) {
    const latEl = document.getElementById("edit-lat");
    const lngEl = document.getElementById("edit-lng");
    if (latEl) latEl.value = String(meta.latitude);
    if (lngEl) lngEl.value = String(meta.longitude);
    if (typeof runDuplicateCheckOnCurrentDraft === "function") {
      runDuplicateCheckOnCurrentDraft();
    }
  }

  // 2. Date
  if (setVisitDate) {
    const visitDateEl = document.getElementById("edit-visit-date");
    if (visitDateEl) visitDateEl.value = meta.date_taken;
    const photoBadge = document.getElementById("edit-visit-photo-badge");
    if (photoBadge) photoBadge.style.display = "inline";
  }
  if (addVisitDates && currentEditingPoi) {
    if (!Array.isArray(currentEditingPoi.visit_dates)) {
      currentEditingPoi.visit_dates = [];
    }
    if (!currentEditingPoi.visit_dates.includes(meta.date_taken)) {
      currentEditingPoi.visit_dates.push(meta.date_taken);
      currentEditingPoi.visit_dates.sort();
    }
  }

  // 3. Tags
  const checkedTags = modalPendingTags.filter(t => t.checked).map(t => t.name);
  if (checkedTags.length > 0) {
    checkedTags.forEach(t => {
      if (!editingTagsList.includes(t)) {
        editingTagsList.push(t);
      }
    });
    renderEditingTags();
  }

  // 4. Link Folder
  if (linkFolder && currentEditingPoi) {
    const isAlreadyLinked = Boolean(
      (meta.already_linked && meta.folder_path && meta.folder_path.trim().toLowerCase().replace(/[\\/]+$/, "") === folderToLink.toLowerCase().replace(/[\\/]+$/, "")) ||
      isPoiFolderAlreadyAssociated(folderToLink)
    );

    if (isAlreadyLinked) {
      console.log(`[applySelectedPhotoMetadata] Folder "${folderToLink}" is already linked to place. Skipping addition.`);
    } else {
      try {
        const res = await apiFetch(`/api/v1/pois/${currentEditingPoi.id}/photo-folder`, {
          method: "POST",
          body: JSON.stringify({
            folder_path: folderToLink,
            action: "check"
          })
        });
        if (res.ok) {
          const resData = await res.json();
          if (resData.conflict) {
            openFolderConflictModal(resData, currentEditingPoi.id, folderToLink);
            return;
          }
          await loadPoiAssociatedFolders(currentEditingPoi.id);
          if (foldersViewActive) await loadScannedFolders();
        }
      } catch (err) {
        console.warn("Could not auto-link folder:", err);
      }
    }
  } else if (linkFolder && !currentEditingPoi) {
    const sourceUrlInput = document.getElementById("edit-source-url");
    if (sourceUrlInput && !sourceUrlInput.value) {
      sourceUrlInput.value = folderToLink;
    }
  }

  // Hide modals and add-folder-box
  if (modal) modal.style.display = "none";
  const addFolderBox = document.getElementById("edit-poi-add-folder-box");
  const folderPathInput = document.getElementById("edit-poi-folder-path-input");
  const dupAlert = document.getElementById("edit-poi-folder-duplicate-alert");
  if (addFolderBox) addFolderBox.style.display = "none";
  if (folderPathInput) folderPathInput.value = "";
  if (dupAlert) dupAlert.style.display = "none";

  showToast("Photo metadata successfully applied to place!");
}

async function handleInspectPhotoPath() {
  const folderPathInput = document.getElementById("edit-poi-folder-path-input");
  const inspectBtn = document.getElementById("edit-poi-folder-inspect-btn");
  const path = (folderPathInput?.value || "").trim();
  if (!path) {
    showToast("Please enter a file or folder path.", true);
    return;
  }

  const poiId = currentEditingPoi?.id || "00000000-0000-0000-0000-000000000000";
  if (inspectBtn) inspectBtn.disabled = true;
  try {
    const res = await apiFetch(`/api/v1/pois/${poiId}/inspect-photo-path`, {
      method: "POST",
      body: JSON.stringify({ file_path: path })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to inspect path");
    }
    const data = await res.json();
    console.log("[handleInspectPhotoPath] Inspection result:", data);
    if (data.status === "duplicate_aborted") {
      openDuplicateAbortModal(data);
      return;
    }
    if (data.status === "metadata_found") {
      openPhotoMetadataModal(data);
    } else {
      if (currentEditingPoi) {
        showToast("No EXIF GPS/date metadata found. Attaching folder...");
        await handleAttachPhotoFolder();
      } else {
        openNoMetadataModal(path);
      }
    }
  } catch (err) {
    console.error("[handleInspectPhotoPath] Error:", err);
    showToast(err.message, true);
  } finally {
    if (inspectBtn) inspectBtn.disabled = false;
  }
}

async function handleInspectPhotoUpload(file) {
  if (!file) return;
  const poiId = currentEditingPoi?.id || "00000000-0000-0000-0000-000000000000";
  const browseBtn = document.getElementById("edit-poi-browse-photo-btn");
  if (browseBtn) browseBtn.disabled = true;
  showToast(`Inspecting metadata from "${file.name}"...`);

  try {
    const formData = new FormData();
    formData.append("file", file);
    const enteredPath = (document.getElementById("edit-poi-folder-path-input")?.value || "").trim();
    if (enteredPath) {
      formData.append("folder_path", enteredPath);
    }

    const res = await apiFetch(`/api/v1/pois/${poiId}/inspect-photo-upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to inspect uploaded file");
    }
    const data = await res.json();
    console.log("[handleInspectPhotoUpload] Inspection result:", data);
    if (data.status === "duplicate_aborted") {
      openDuplicateAbortModal(data);
      return;
    }
    if (data.status === "metadata_found") {
      openPhotoMetadataModal(data);
    } else {
      openNoMetadataModal(file.name);
    }
  } catch (err) {
    console.error("[handleInspectPhotoUpload] Error:", err);
    showToast(err.message, true);
  } finally {
    if (browseBtn) browseBtn.disabled = false;
    const filePicker = document.getElementById("edit-poi-photo-file-picker");
    if (filePicker) filePicker.value = "";
  }
}

function openFolderConflictModal(conflictData, poiId, folderPath) {
  const modal = document.getElementById("poi-folder-conflict-modal");
  const pathEl = document.getElementById("conflict-modal-folder-path");
  const poisListEl = document.getElementById("conflict-modal-pois-list");
  const flagBothBtn = document.getElementById("conflict-action-flag-both");
  const reassignBtn = document.getElementById("conflict-action-reassign");
  if (!modal) return;

  if (pathEl) pathEl.textContent = folderPath;
  if (poisListEl) {
    poisListEl.innerHTML = "";
    const pois = conflictData.conflicting_pois || [];
    if (pois.length === 0) {
      poisListEl.innerHTML = `<span style="font-size: 12px; color: var(--text-muted);">(No other places listed)</span>`;
    } else {
      pois.forEach(p => {
        const itemEl = document.createElement("div");
        itemEl.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #ffffff; border: 1px solid var(--border-color); border-radius: 6px;";
        itemEl.innerHTML = `
          <div>
            <strong style="font-size: 12.5px; color: var(--text-main);">${escapeHtml(p.name)}</strong>
            <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">(${escapeHtml(p.poi_type || 'site')})</span>
            ${p.city || p.country ? `<div style="font-size: 11px; color: var(--text-muted);">${escapeHtml([p.city, p.country].filter(Boolean).join(', '))}</div>` : ''}
          </div>
          <button type="button" class="btn btn-secondary btn-sm view-conflict-poi-btn" style="padding: 2px 8px; font-size: 11px;">
            👁️ View Place
          </button>
        `;
        itemEl.querySelector(".view-conflict-poi-btn").onclick = () => {
          modal.style.display = "none";
          const matchPoi = allPois.find(x => x.id === p.id);
          if (matchPoi) {
            openEditModal(matchPoi);
          } else {
            apiFetch(`/api/v1/pois/${p.id}`).then(r => r.json()).then(found => openEditModal(found));
          }
        };
        poisListEl.appendChild(itemEl);
      });
    }
  }

  if (flagBothBtn) {
    flagBothBtn.onclick = async () => {
      try {
        flagBothBtn.disabled = true;
        const res = await apiFetch(`/api/v1/pois/${poiId}/photo-folder`, {
          method: "POST",
          body: JSON.stringify({
            folder_path: folderPath,
            action: "share_and_flag"
          })
        });
        if (!res.ok) throw new Error("Failed to link folder with conflict flag");
        const d = await res.json();
        showToast(d.message || "Folder linked with conflict flag for manual review.");
        modal.style.display = "none";
        const addBox = document.getElementById("edit-poi-add-folder-box");
        const inputEl = document.getElementById("edit-poi-folder-path-input");
        if (addBox) addBox.style.display = "none";
        if (inputEl) inputEl.value = "";
        await loadPoiAssociatedFolders(poiId);
        await fetchPois(true);
        if (foldersViewActive) await loadScannedFolders();
      } catch (err) {
        showToast(err.message, true);
      } finally {
        flagBothBtn.disabled = false;
      }
    };
  }

  if (reassignBtn) {
    reassignBtn.onclick = async () => {
      try {
        reassignBtn.disabled = true;
        const res = await apiFetch(`/api/v1/pois/${poiId}/photo-folder`, {
          method: "POST",
          body: JSON.stringify({
            folder_path: folderPath,
            action: "reassign"
          })
        });
        if (!res.ok) throw new Error("Failed to transfer folder");
        const d = await res.json();
        showToast(d.message || "Folder transferred exclusively to this place.");
        modal.style.display = "none";
        const addBox = document.getElementById("edit-poi-add-folder-box");
        const inputEl = document.getElementById("edit-poi-folder-path-input");
        if (addBox) addBox.style.display = "none";
        if (inputEl) inputEl.value = "";
        await loadPoiAssociatedFolders(poiId);
        await fetchPois(true);
        if (foldersViewActive) await loadScannedFolders();
      } catch (err) {
        showToast(err.message, true);
      } finally {
        reassignBtn.disabled = false;
      }
    };
  }

  modal.style.display = "flex";
}

// Wire Add Folder and Conflict Modal Listeners
document.addEventListener("DOMContentLoaded", () => {
  const addFolderToggleBtn = document.getElementById("edit-poi-add-folder-toggle-btn");
  const addFolderBox = document.getElementById("edit-poi-add-folder-box");
  const folderPathInput = document.getElementById("edit-poi-folder-path-input");
  const folderInspectBtn = document.getElementById("edit-poi-folder-inspect-btn");
  const folderCancelBtn = document.getElementById("edit-poi-folder-cancel-btn");
  const browsePhotoBtn = document.getElementById("edit-poi-browse-photo-btn");
  const photoFilePicker = document.getElementById("edit-poi-photo-file-picker");

  if (addFolderToggleBtn) {
    addFolderToggleBtn.onclick = () => {
      if (!addFolderBox) return;
      const isVisible = addFolderBox.style.display !== "none";
      addFolderBox.style.display = isVisible ? "none" : "block";
      if (!isVisible) {
        populateScannedFoldersDatalist();
        if (folderPathInput) {
          folderPathInput.value = "";
          folderPathInput.focus();
        }
        const dupAlert = document.getElementById("edit-poi-folder-duplicate-alert");
        if (dupAlert) dupAlert.style.display = "none";
      }
    };
  }

  if (folderCancelBtn) {
    folderCancelBtn.onclick = () => {
      if (addFolderBox) addFolderBox.style.display = "none";
      if (folderPathInput) folderPathInput.value = "";
      const dupAlert = document.getElementById("edit-poi-folder-duplicate-alert");
      if (dupAlert) dupAlert.style.display = "none";
    };
  }

  const folderAttachBtn = document.getElementById("edit-poi-folder-attach-btn");
  if (folderAttachBtn) {
    folderAttachBtn.onclick = handleAttachPhotoFolder;
  }

  if (folderInspectBtn) {
    folderInspectBtn.onclick = handleInspectPhotoPath;
  }

  if (browsePhotoBtn && photoFilePicker) {
    browsePhotoBtn.onclick = () => {
      photoFilePicker.click();
    };
    photoFilePicker.onchange = (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        handleInspectPhotoUpload(file);
      }
    };
  }

  if (folderPathInput) {
    folderPathInput.onkeydown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAttachPhotoFolder();
      }
    };
  }

  // Conflict modal
  const conflictModal = document.getElementById("poi-folder-conflict-modal");
  const conflictCloseBtn = document.getElementById("poi-folder-conflict-close");
  const conflictCancelBtn = document.getElementById("conflict-modal-cancel-btn");
  if (conflictCloseBtn) conflictCloseBtn.onclick = () => { if (conflictModal) conflictModal.style.display = "none"; };
  if (conflictCancelBtn) conflictCancelBtn.onclick = () => { if (conflictModal) conflictModal.style.display = "none"; };

  // Duplicate abort modal
  const dupModal = document.getElementById("poi-photo-duplicate-abort-modal");
  const dupCloseBtn = document.getElementById("poi-photo-duplicate-close");
  const dupDismissBtn = document.getElementById("duplicate-abort-modal-dismiss-btn");
  if (dupCloseBtn) dupCloseBtn.onclick = () => { if (dupModal) dupModal.style.display = "none"; };
  if (dupDismissBtn) dupDismissBtn.onclick = () => { if (dupModal) dupModal.style.display = "none"; };

  // Metadata modal
  const metaModal = document.getElementById("poi-photo-metadata-modal");
  const metaCloseBtn = document.getElementById("poi-photo-metadata-close");
  const metaCancelBtn = document.getElementById("meta-modal-cancel-btn");
  const metaApplyBtn = document.getElementById("meta-modal-apply-btn");
  const metaTagsSelectAllBtn = document.getElementById("meta-tags-select-all-btn");
  const metaTagsDeselectAllBtn = document.getElementById("meta-tags-deselect-all-btn");
  const metaAddTagBtn = document.getElementById("meta-add-tag-btn");
  const metaNewTagInput = document.getElementById("meta-new-tag-input");

  if (metaCloseBtn) metaCloseBtn.onclick = () => { if (metaModal) metaModal.style.display = "none"; };
  if (metaCancelBtn) metaCancelBtn.onclick = () => { if (metaModal) metaModal.style.display = "none"; };
  if (metaApplyBtn) metaApplyBtn.onclick = applySelectedPhotoMetadata;
  if (metaTagsSelectAllBtn) {
    metaTagsSelectAllBtn.onclick = () => {
      modalPendingTags.forEach(t => (t.checked = true));
      renderModalTags();
    };
  }
  if (metaTagsDeselectAllBtn) {
    metaTagsDeselectAllBtn.onclick = () => {
      modalPendingTags.forEach(t => (t.checked = false));
      renderModalTags();
    };
  }
  if (metaAddTagBtn) {
    metaAddTagBtn.onclick = handleAddManualModalTag;
  }
  if (metaNewTagInput) {
    metaNewTagInput.onkeydown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddManualModalTag();
      }
    };
  }

  // No metadata info modal
  const noMetaModal = document.getElementById("poi-photo-no-metadata-modal");
  const noMetaCloseBtn = document.getElementById("poi-photo-no-metadata-close");
  const noMetaOkBtn = document.getElementById("no-meta-modal-ok-btn");
  if (noMetaCloseBtn) noMetaCloseBtn.onclick = () => { if (noMetaModal) noMetaModal.style.display = "none"; };
  if (noMetaOkBtn) noMetaOkBtn.onclick = () => { if (noMetaModal) noMetaModal.style.display = "none"; };
});

// ==========================================
// 2. Interactive "Assign Location on Map" Modal
// ==========================================

const assignLocationModal = document.getElementById("assign-location-modal");
const assignLocationClose = document.getElementById("assign-location-modal-close");
const assignLocationCancelBtn = document.getElementById("assign-location-cancel-btn");
const assignLocationApplyBtn = document.getElementById("assign-location-apply-btn");
const assignLatInput = document.getElementById("assign-lat-input");
const assignLngInput = document.getElementById("assign-lng-input");
const assignLocationSearchInput = document.getElementById("assign-location-search-input");
const assignLocationSearchBtn = document.getElementById("assign-location-search-btn");
const assignMapTileProviderSelect = document.getElementById("assign-map-tile-provider-select");
const assignAddressPreview = document.getElementById("assign-address-preview");
const assignLocationAlert = document.getElementById("assign-location-alert");
const assignLocationAlertMsg = document.getElementById("assign-location-alert-msg");
const editAssignLocationBtn = document.getElementById("edit-assign-location-btn");

let assignMap = null;
let assignMarker = null;
let assignTargetMode = "edit-poi"; // "edit-poi" or "scanned-path"
let assignTargetId = null;
let assignBaseLayers = {};
let assignLayerControl = null;
let assignTileLayer = null;
let assignSelectedTileProvider = "google-hybrid";

if (editLookupDetailsBtn) {
  editLookupDetailsBtn.onclick = async () => {
    const name = document.getElementById("edit-name").value.trim();
    if (!name) {
      showToast("Please enter a place name first to lookup details.", true);
      document.getElementById("edit-name").focus();
      return;
    }

    const city = document.getElementById("edit-city").value.trim() || null;
    const state = document.getElementById("edit-state").value.trim() || null;
    const country = document.getElementById("edit-country").value.trim() || null;
    const lat = document.getElementById("edit-lat").value ? parseFloat(document.getElementById("edit-lat").value) : null;
    const lng = document.getElementById("edit-lng").value ? parseFloat(document.getElementById("edit-lng").value) : null;
    const sourceUrl = document.getElementById("edit-source-url")?.value.trim() || null;

    if (pendingLinkedFolderId) {
      enrichPlaceDetailsFromFolder({
        id: pendingLinkedFolderId,
        site_name: name,
        city,
        state,
        country,
        latitude: lat,
        longitude: lng,
        folder_path: sourceUrl,
      });
      return;
    }

    const enrichmentBanner = document.getElementById("edit-enrichment-banner");
    const enrichmentText = document.getElementById("edit-enrichment-text");
    const enrichmentSpinner = document.getElementById("edit-enrichment-spinner");

    if (enrichmentBanner) {
      enrichmentBanner.style.display = "flex";
      enrichmentBanner.style.background = "#faf5ff";
      enrichmentBanner.style.borderColor = "#e9d5ff";
      enrichmentBanner.style.color = "#6b21a8";
      if (enrichmentSpinner) enrichmentSpinner.style.display = "inline-block";
      if (enrichmentText) enrichmentText.textContent = `🔍 Looking up online details for "${name}"...`;
    }

    try {
      const res = await apiFetch("/api/v1/pois/lookup-details", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          place_name: name,
          city,
          state,
          country,
          latitude: lat,
          longitude: lng,
          folder_context: sourceUrl,
        }),
      });
      if (!res.ok) throw new Error("Details lookup failed");
      const data = await res.json();

      const fieldsPopulated = [];

      if (data.website_official && !document.getElementById("edit-website").value) {
        document.getElementById("edit-website").value = data.website_official;
        fieldsPopulated.push("official website");
      }
      if (data.phone_number && !document.getElementById("edit-phone").value) {
        document.getElementById("edit-phone").value = data.phone_number;
        fieldsPopulated.push("phone number");
      }
      if (Array.isArray(data.category_tags) && data.category_tags.length > 0) {
        let added = 0;
        data.category_tags.forEach((tag) => {
          const clean = tag.trim().toLowerCase();
          if (clean && !editingTagsList.some((t) => t.toLowerCase() === clean)) {
            editingTagsList.push(tag.trim());
            added++;
          }
        });
        if (added > 0) {
          renderEditingTags();
          fieldsPopulated.push(`${added} category tags`);
        }
      }
      if (data.description && !document.getElementById("edit-description").value) {
        document.getElementById("edit-description").value = data.description;
        fieldsPopulated.push("description");
      }
      if (data.indoor_outdoor && !document.getElementById("edit-environment").value) {
        document.getElementById("edit-environment").value = data.indoor_outdoor;
      }
      if (data.physical_effort && !document.getElementById("edit-effort").value) {
        document.getElementById("edit-effort").value = data.physical_effort;
      }
      if (data.cost_tier && !document.getElementById("edit-cost").value) {
        document.getElementById("edit-cost").value = data.cost_tier;
      }
      if (data.estimated_duration && !document.getElementById("edit-duration").value) {
        document.getElementById("edit-duration").value = data.estimated_duration;
      }
      if (data.best_time_to_visit && !document.getElementById("edit-best-time").value) {
        document.getElementById("edit-best-time").value = data.best_time_to_visit;
      }

      if (enrichmentSpinner) enrichmentSpinner.style.display = "none";
      if (enrichmentText) {
        if (fieldsPopulated.length > 0) {
          enrichmentText.innerHTML = `✨ <strong>Found:</strong> ${fieldsPopulated.join(", ")}.`;
        } else {
          enrichmentText.textContent = "✓ Lookup complete (no additional details found).";
        }
      }
      setTimeout(() => {
        if (enrichmentBanner) enrichmentBanner.style.display = "none";
      }, 4000);
    } catch (err) {
      if (enrichmentSpinner) enrichmentSpinner.style.display = "none";
      if (enrichmentText) enrichmentText.textContent = "Lookup finished without new data.";
      setTimeout(() => {
        if (enrichmentBanner) enrichmentBanner.style.display = "none";
      }, 3000);
    }
  };
}

if (editAssignLocationBtn) {
  editAssignLocationBtn.onclick = () => {
    const lat = document.getElementById("edit-lat").value;
    const lng = document.getElementById("edit-lng").value;
    const name = document.getElementById("edit-name").value;
    openAssignLocationModal(lat, lng, name, "edit-poi", null);
  };
}

if (assignLocationClose) assignLocationClose.onclick = () => (assignLocationModal.style.display = "none");
if (assignLocationCancelBtn) assignLocationCancelBtn.onclick = () => (assignLocationModal.style.display = "none");

function setAssignMapTileProvider(providerKey, save = true) {
  if (!MAP_TILE_PROVIDERS[providerKey]) {
    providerKey = "google-hybrid";
  }
  assignSelectedTileProvider = providerKey;
  if (save && typeof chrome !== "undefined" && chrome?.storage?.local) {
    chrome.storage.local.set({ assign_map_tile_provider: providerKey });
  }
  if (assignMapTileProviderSelect && assignMapTileProviderSelect.value !== providerKey) {
    assignMapTileProviderSelect.value = providerKey;
  }
  if (!assignMap) return;

  const targetLayer = assignBaseLayers[providerKey];
  if (targetLayer) {
    Object.values(assignBaseLayers).forEach((layer) => {
      if (assignMap.hasLayer(layer) && layer !== targetLayer) {
        assignMap.removeLayer(layer);
      }
    });
    if (!assignMap.hasLayer(targetLayer)) {
      targetLayer.addTo(assignMap);
    }
  } else {
    const provider = MAP_TILE_PROVIDERS[providerKey] || MAP_TILE_PROVIDERS["google-hybrid"];
    if (assignTileLayer) {
      assignMap.removeLayer(assignTileLayer);
    }
    assignTileLayer = L.tileLayer(provider.url, provider.options).addTo(assignMap);
  }

  if (assignMarker) {
    assignMarker.bringToFront();
  }
}

if (assignMapTileProviderSelect) {
  assignMapTileProviderSelect.addEventListener("change", (e) => {
    setAssignMapTileProvider(e.target.value, true);
  });
}

function openAssignLocationModal(initialLat, initialLng, initialName, mode = "edit-poi", targetId = null) {
  assignTargetMode = mode;
  assignTargetId = targetId;
  if (assignLocationAlert) assignLocationAlert.style.display = "none";
  if (assignLocationSearchInput) assignLocationSearchInput.value = initialName || "";
  assignLocationModal.style.display = "flex";

  const defaultLat = 39.8283;
  const defaultLng = -98.5795;
  const hasCoords = initialLat != null && initialLng != null && !isNaN(initialLat) && !isNaN(initialLng) && (Number(initialLat) !== 0 || Number(initialLng) !== 0);
  const lat = hasCoords ? Number(initialLat) : defaultLat;
  const lng = hasCoords ? Number(initialLng) : defaultLng;
  const zoom = hasCoords ? 14 : 4;

  if (assignLatInput) assignLatInput.value = hasCoords ? lat : "";
  if (assignLngInput) assignLngInput.value = hasCoords ? lng : "";

  setTimeout(() => {
    if (!assignMap) {
      assignMap = L.map("assign-location-map").setView([lat, lng], zoom);

      assignBaseLayers = {
        "google-roadmap": L.tileLayer(MAP_TILE_PROVIDERS["google-roadmap"].url, MAP_TILE_PROVIDERS["google-roadmap"].options),
        "google-hybrid": L.tileLayer(MAP_TILE_PROVIDERS["google-hybrid"].url, MAP_TILE_PROVIDERS["google-hybrid"].options),
        "google-terrain": L.tileLayer(MAP_TILE_PROVIDERS["google-terrain"].url, MAP_TILE_PROVIDERS["google-terrain"].options),
        "osm-standard": L.tileLayer(MAP_TILE_PROVIDERS["osm-standard"].url, MAP_TILE_PROVIDERS["osm-standard"].options),
        "osm-hot": L.tileLayer(MAP_TILE_PROVIDERS["osm-hot"].url, MAP_TILE_PROVIDERS["osm-hot"].options),
        "esri-street": L.tileLayer(MAP_TILE_PROVIDERS["esri-street"].url, MAP_TILE_PROVIDERS["esri-street"].options),
        "esri-imagery": L.tileLayer(MAP_TILE_PROVIDERS["esri-imagery"].url, MAP_TILE_PROVIDERS["esri-imagery"].options),
      };

      const controlBaseMaps = {
        "🌐 Google Street": assignBaseLayers["google-roadmap"],
        "🛰️ Google Hybrid": assignBaseLayers["google-hybrid"],
        "🏔️ Google Terrain": assignBaseLayers["google-terrain"],
        "📍 OpenStreetMap": assignBaseLayers["osm-standard"],
        "❤️ OSM Humanitarian": assignBaseLayers["osm-hot"],
        "🗺️ Esri Street": assignBaseLayers["esri-street"],
        "🛰️ Esri Satellite": assignBaseLayers["esri-imagery"],
      };

      assignLayerControl = L.control.layers(controlBaseMaps, null, { position: "topright" }).addTo(assignMap);

      assignMap.on("baselayerchange", (e) => {
        for (const [key, layer] of Object.entries(assignBaseLayers)) {
          if (layer === e.layer) {
            assignSelectedTileProvider = key;
            if (assignMapTileProviderSelect) assignMapTileProviderSelect.value = key;
            if (typeof chrome !== "undefined" && chrome?.storage?.local) {
              chrome.storage.local.set({ assign_map_tile_provider: key });
            }
            break;
          }
        }
        if (assignMarker) assignMarker.bringToFront();
      });

      setAssignMapTileProvider(assignSelectedTileProvider, false);

      assignMap.on("click", (e) => {
        updateAssignMarker(e.latlng.lat, e.latlng.lng, true);
      });
    } else {
      assignMap.invalidateSize();
      assignMap.setView([lat, lng], zoom);
      setAssignMapTileProvider(assignSelectedTileProvider, false);
    }

    if (hasCoords) {
      updateAssignMarker(lat, lng, false);
    } else if (assignMarker) {
      assignMap.removeLayer(assignMarker);
      assignMarker = null;
    }
  }, 150);
}

function updateAssignMarker(lat, lng, doReverseGeocode = true) {
  if (assignLocationAlert) assignLocationAlert.style.display = "none";
  const roundedLat = parseFloat(Number(lat).toFixed(6));
  const roundedLng = parseFloat(Number(lng).toFixed(6));
  if (assignLatInput) assignLatInput.value = roundedLat;
  if (assignLngInput) assignLngInput.value = roundedLng;

  if (!assignMarker) {
    assignMarker = L.marker([roundedLat, roundedLng], { draggable: true }).addTo(assignMap);
    assignMarker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      updateAssignMarker(pos.lat, pos.lng, true);
    });
  } else {
    assignMarker.setLatLng([roundedLat, roundedLng]);
  }

  if (doReverseGeocode) {
    reverseGeocodeAssignLocation(roundedLat, roundedLng);
  }
}

async function reverseGeocodeAssignLocation(lat, lng) {
  if (!assignAddressPreview) return;
  assignAddressPreview.innerHTML = `Address preview: <span style="color: var(--text-muted);">Fetching address...</span>`;
  try {
    const res = await apiFetch(`/api/v1/pois/reverse-geocode?latitude=${lat}&longitude=${lng}`);
    if (res.ok) {
      const data = await res.json();
      assignAddressPreview.innerHTML = `Address preview: <strong style="color: #0d9488;">${escapeHtml(data.display_name || "Location found")}</strong>`;
      assignAddressPreview.dataset.city = data.city || "";
      assignAddressPreview.dataset.state = data.state || "";
      assignAddressPreview.dataset.country = data.country || "";
      assignAddressPreview.dataset.countryCode = data.country_code || "";
      assignAddressPreview.dataset.sublocation = data.sublocation || "";
      assignAddressPreview.dataset.postcode = data.postcode || "";
    } else {
      assignAddressPreview.innerHTML = `Address preview: <span style="color: var(--text-muted);">(${lat}, ${lng})</span>`;
    }
  } catch (e) {
    assignAddressPreview.innerHTML = `Address preview: <span style="color: var(--text-muted);">(${lat}, ${lng})</span>`;
  }
}

if (assignLocationSearchInput) {
  assignLocationSearchInput.onkeydown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (assignLocationSearchBtn) assignLocationSearchBtn.click();
    }
  };
}

if (assignLocationSearchBtn) {
  assignLocationSearchBtn.onclick = async () => {
    const q = (assignLocationSearchInput.value || "").trim();
    if (!q) return;
    if (assignLocationAlert) assignLocationAlert.style.display = "none";

    // Direct coordinates or Google Maps URL quick check
    const coordMatch = q.match(/^\s*\(?\s*(-?\d{1,2}(?:\.\d+)?)\s*[, \t/]+\s*(-?\d{1,3}(?:\.\d+)?)\s*\)?\s*$/);
    const gmapsUrlMatch = q.match(/(?:@|[?&](?:q|ll)=)(-?\d{1,2}\.\d+)[, ]+(-?\d{1,3}\.\d+)/);
    const directLat = coordMatch ? parseFloat(coordMatch[1]) : (gmapsUrlMatch ? parseFloat(gmapsUrlMatch[1]) : null);
    const directLng = coordMatch ? parseFloat(coordMatch[2]) : (gmapsUrlMatch ? parseFloat(gmapsUrlMatch[2]) : null);

    if (directLat !== null && directLng !== null && !isNaN(directLat) && !isNaN(directLng) && directLat >= -90 && directLat <= 90 && directLng >= -180 && directLng <= 180) {
      assignMap.setView([directLat, directLng], 15);
      updateAssignMarker(directLat, directLng, false);
      try {
        const revRes = await apiFetch(`/api/v1/pois/reverse-geocode?lat=${directLat}&lng=${directLng}`);
        if (revRes.ok) {
          const revData = await revRes.json();
          assignAddressPreview.innerHTML = `Address preview: <strong style="color: #0d9488;">${escapeHtml(revData.display_name || q)}</strong>`;
          assignAddressPreview.dataset.city = revData.city || "";
          assignAddressPreview.dataset.state = revData.state || "";
          assignAddressPreview.dataset.country = revData.country || "";
          assignAddressPreview.dataset.countryCode = revData.country_code || "";
          assignAddressPreview.dataset.sublocation = revData.sublocation || "";
          assignAddressPreview.dataset.postcode = revData.postcode || "";
        }
      } catch (err) {}
      return;
    }

    try {
      assignLocationSearchBtn.disabled = true;
      assignLocationSearchBtn.textContent = "Searching...";
      const res = await apiFetch(`/api/v1/pois/geocode?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          assignMap.setView([data.latitude, data.longitude], 14);
          updateAssignMarker(data.latitude, data.longitude, false);
          assignAddressPreview.innerHTML = `Address preview: <strong style="color: #0d9488;">${escapeHtml(data.display_name || q)}</strong>`;
          assignAddressPreview.dataset.city = data.city || "";
          assignAddressPreview.dataset.state = data.state || "";
          assignAddressPreview.dataset.country = data.country || "";
          assignAddressPreview.dataset.countryCode = data.country_code || "";
          assignAddressPreview.dataset.sublocation = data.sublocation || "";
          assignAddressPreview.dataset.postcode = data.postcode || "";
        } else {
          if (assignLocationAlert && assignLocationAlertMsg) {
            assignLocationAlertMsg.textContent = `No coordinates found for "${q}". Try zooming into the map and clicking directly.`;
            assignLocationAlert.style.display = "flex";
          }
          showToast(`No coordinates found for "${q}"`, true);
        }
      }
    } catch (e) {
      if (assignLocationAlert && assignLocationAlertMsg) {
        assignLocationAlertMsg.textContent = e.message || "Failed to geocode address";
        assignLocationAlert.style.display = "flex";
      }
      showToast(e.message, true);
    } finally {
      assignLocationSearchBtn.disabled = false;
      assignLocationSearchBtn.textContent = "🔍 Search";
    }
  };
}

if (assignLocationApplyBtn) {
  assignLocationApplyBtn.onclick = async () => {
    const lat = assignLatInput.value ? parseFloat(assignLatInput.value) : null;
    const lng = assignLngInput.value ? parseFloat(assignLngInput.value) : null;
    if (lat == null || lng == null || isNaN(lat) || isNaN(lng)) {
      if (assignLocationAlert && assignLocationAlertMsg) {
        assignLocationAlertMsg.textContent = "Please drop a marker on the map to choose coordinates";
        assignLocationAlert.style.display = "flex";
      }
      showToast("Please drop a marker on the map to choose coordinates", true);
      return;
    }

    if (assignTargetMode === "edit-poi") {
      document.getElementById("edit-lat").value = lat;
      document.getElementById("edit-lng").value = lng;
      if (assignAddressPreview.dataset.city) {
        document.getElementById("edit-city").value = assignAddressPreview.dataset.city;
      }
      if (assignAddressPreview.dataset.state) {
        document.getElementById("edit-state").value = assignAddressPreview.dataset.state;
      }
      if (assignAddressPreview.dataset.countryCode || assignAddressPreview.dataset.country) {
        document.getElementById("edit-country").value = assignAddressPreview.dataset.countryCode || assignAddressPreview.dataset.country;
      }
      if (assignAddressPreview.dataset.sublocation) {
        const subEl = document.getElementById("edit-sublocation");
        if (subEl) subEl.value = assignAddressPreview.dataset.sublocation;
      }
      if (assignAddressPreview.dataset.postcode) {
        const zipEl = document.getElementById("edit-zip-code");
        if (zipEl) zipEl.value = assignAddressPreview.dataset.postcode;
      }
      assignLocationModal.style.display = "none";
      showToast("Location applied to place form!");
      runDuplicateCheckOnCurrentDraft();
    } else if (assignTargetMode === "scanned-path") {
      try {
        const payload = {
          latitude: lat,
          longitude: lng,
          status: "identified"
        };
        if (assignAddressPreview.dataset.city) payload.city = assignAddressPreview.dataset.city;
        if (assignAddressPreview.dataset.state) payload.state = assignAddressPreview.dataset.state;
        if (assignAddressPreview.dataset.country) payload.country = assignAddressPreview.dataset.country;
        if (assignAddressPreview.dataset.countryCode) payload.country_code = assignAddressPreview.dataset.countryCode;

        const res = await apiFetch(`/api/v1/scanned-paths/${assignTargetId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to update folder location");
        assignLocationModal.style.display = "none";
        showToast("Location applied to folder and place saved!");
        await loadScannedFolders();
        await fetchPois();
      } catch (e) {
        showToast(e.message, true);
      }
    }
  };
}

if (assignLatInput) assignLatInput.oninput = () => { if (assignLocationAlert) assignLocationAlert.style.display = "none"; };
if (assignLngInput) assignLngInput.oninput = () => { if (assignLocationAlert) assignLocationAlert.style.display = "none"; };

// ==========================================
// 3. View Switcher Navigation (Places vs Folders)
// ==========================================

const tabBtnPois = document.getElementById("tab-btn-pois");
const tabBtnFolders = document.getElementById("tab-btn-folders");
const poisViewContainer = document.getElementById("pois-view-container");
const foldersViewContainer = document.getElementById("folders-view-container");
const poisBadgeCount = document.getElementById("pois-badge-count");
const foldersBadgeCount = document.getElementById("folders-badge-count");

let foldersViewActive = false;

if (tabBtnPois) {
  tabBtnPois.onclick = () => {
    foldersViewActive = false;
    tabBtnPois.classList.add("active");
    tabBtnFolders.classList.remove("active");
    poisViewContainer.style.display = "block";
    foldersViewContainer.style.display = "none";
  };
}

if (tabBtnFolders) {
  tabBtnFolders.onclick = () => {
    foldersViewActive = true;
    tabBtnFolders.classList.add("active");
    tabBtnPois.classList.remove("active");
    foldersViewContainer.style.display = "block";
    poisViewContainer.style.display = "none";
    loadScannedFolders();
  };
}

// Sync POI count in tab badge
function syncPoisBadgeCount() {
  if (poisBadgeCount) poisBadgeCount.textContent = allPois.length;
}

// ==========================================
// 4. Scanned Folders Management Controller
// ==========================================

let scannedFolders = [];
let scannedFoldersTotal = 0;
let currentFolderStatusFilter = "all";
let folderSearchKeyword = "";
let folderSortBy = "folder_path";
let folderSortOrder = "asc";
let folderPageOffset = 0;
const folderPageLimit = 50;
let selectedFolderIds = new Set();

const foldersTableBody = document.getElementById("folders-table-body");
const foldersPaginationInfo = document.getElementById("folders-pagination-info");
const foldersPrevPageBtn = document.getElementById("folders-prev-page-btn");
const foldersNextPageBtn = document.getElementById("folders-next-page-btn");
const foldersSearchInput = document.getElementById("folders-search-input");
const foldersRefreshBtn = document.getElementById("folders-refresh-btn");
const foldersSelectAllCheckbox = document.getElementById("folders-select-all-checkbox");
const foldersBulkActionsBar = document.getElementById("folders-bulk-actions-bar");
const foldersBulkSelectedCount = document.getElementById("folders-bulk-selected-count");

// Status filter pills
const folderStatusPills = document.querySelectorAll("#folder-status-pills .status-filter-btn");
folderStatusPills.forEach(btn => {
  btn.onclick = () => {
    folderStatusPills.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFolderStatusFilter = btn.dataset.status;
    folderPageOffset = 0;
    loadScannedFolders();
  };
});

// Show hidden folders checkbox
const foldersShowHiddenCheckbox = document.getElementById("folders-show-hidden-checkbox");
if (foldersShowHiddenCheckbox) {
  foldersShowHiddenCheckbox.onchange = (e) => {
    const isChecked = e.target.checked;
    const hiddenBtn = document.getElementById("btn-status-hidden");
    if (hiddenBtn) {
      hiddenBtn.style.display = isChecked ? "inline-block" : "none";
      if (!isChecked && currentFolderStatusFilter === "hidden") {
        currentFolderStatusFilter = "all";
        folderStatusPills.forEach(b => {
          if (b.dataset.status === "all") b.classList.add("active");
          else b.classList.remove("active");
        });
      }
    }
    folderPageOffset = 0;
    loadScannedFolders();
  };
}

// Search input debounced
let folderSearchTimeout = null;
if (foldersSearchInput) {
  foldersSearchInput.oninput = () => {
    clearTimeout(folderSearchTimeout);
    folderSearchTimeout = setTimeout(() => {
      folderSearchKeyword = foldersSearchInput.value.trim();
      folderPageOffset = 0;
      loadScannedFolders();
    }, 300);
  };
}

if (foldersRefreshBtn) {
  foldersRefreshBtn.onclick = () => loadScannedFolders();
}

// Sorting headers
document.querySelectorAll(".folders-sortable-th").forEach(th => {
  th.onclick = () => {
    const col = th.dataset.sort;
    if (folderSortBy === col) {
      folderSortOrder = folderSortOrder === "asc" ? "desc" : "asc";
    } else {
      folderSortBy = col;
      folderSortOrder = "asc";
    }

    document.querySelectorAll(".folders-sortable-th").forEach(h => {
      h.classList.remove("sort-active");
      const ind = h.querySelector(".sort-indicator");
      if (ind) ind.textContent = "⇅";
    });

    th.classList.add("sort-active");
    const indicator = th.querySelector(".sort-indicator");
    if (indicator) indicator.textContent = folderSortOrder === "asc" ? "↑" : "↓";

    folderPageOffset = 0;
    loadScannedFolders();
  };
});

// Pagination buttons
if (foldersPrevPageBtn) {
  foldersPrevPageBtn.onclick = () => {
    if (folderPageOffset > 0) {
      folderPageOffset = Math.max(0, folderPageOffset - folderPageLimit);
      loadScannedFolders();
    }
  };
}

if (foldersNextPageBtn) {
  foldersNextPageBtn.onclick = () => {
    if (folderPageOffset + folderPageLimit < scannedFoldersTotal) {
      folderPageOffset += folderPageLimit;
      loadScannedFolders();
    }
  };
}

// Select All checkbox
if (foldersSelectAllCheckbox) {
  foldersSelectAllCheckbox.onchange = (e) => {
    const checked = e.target.checked;
    if (checked) {
      scannedFolders.forEach(item => selectedFolderIds.add(item.id));
    } else {
      selectedFolderIds.clear();
    }
    updateFoldersSelectionUi();
  };
}

function updateFoldersSelectionUi() {
  const count = selectedFolderIds.size;
  if (foldersBulkSelectedCount) foldersBulkSelectedCount.textContent = count;
  if (foldersBulkActionsBar) foldersBulkActionsBar.style.display = count > 0 ? "flex" : "none";
  if (foldersSelectAllCheckbox) {
    foldersSelectAllCheckbox.checked = count > 0 && count === scannedFolders.length;
    foldersSelectAllCheckbox.indeterminate = count > 0 && count < scannedFolders.length;
  }

  document.querySelectorAll(".folder-row-checkbox").forEach(cb => {
    const rowId = cb.dataset.id;
    cb.checked = selectedFolderIds.has(rowId);
    const tr = cb.closest("tr");
    if (tr) {
      if (cb.checked) tr.classList.add("selected");
      else tr.classList.remove("selected");
    }
  });
}

const foldersBulkDeselectBtn = document.getElementById("folders-bulk-deselect-btn");
if (foldersBulkDeselectBtn) {
  foldersBulkDeselectBtn.onclick = () => {
    selectedFolderIds.clear();
    updateFoldersSelectionUi();
  };
}

async function loadScannedFolders() {
  if (!foldersTableBody) return;
  foldersTableBody.innerHTML = `<tr><td colspan="11" class="loading-state">Loading scanned photo folders...</td></tr>`;

  try {
    const showHidden = document.getElementById("folders-show-hidden-checkbox")?.checked;
    const params = new URLSearchParams({
      status: currentFolderStatusFilter,
      sort_by: folderSortBy,
      sort_order: folderSortOrder,
      limit: String(folderPageLimit),
      offset: String(folderPageOffset)
    });
    params.set("include_hidden", showHidden ? "true" : "false");
    if (folderSearchKeyword) params.set("search", folderSearchKeyword);

    const res = await apiFetch(`/api/v1/scanned-paths?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to load scanned folders");

    const data = await res.json();
    scannedFolders = data.items || [];
    scannedFoldersTotal = data.total_count || 0;

    if (foldersBadgeCount) foldersBadgeCount.textContent = scannedFoldersTotal;
    updateFolderStatusCounts();
    renderFoldersTable();

  } catch (err) {
    foldersTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: #ef4444; padding: 24px;">Failed to load folders: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function updateFolderStatusCounts() {
  try {
    const showHidden = document.getElementById("folders-show-hidden-checkbox")?.checked;
    const statuses = ["all", "identified", "location unknown", "pending", "skipped", "hidden"];
    const promises = statuses.map(async (st) => {
      try {
        const querySt = st === "all" ? "all" : st;
        const incHiddenParam = (st === "all" && showHidden) || st === "hidden" ? "&include_hidden=true" : "";
        const r = await apiFetch(`/api/v1/scanned-paths?status=${encodeURIComponent(querySt)}&limit=1${incHiddenParam}`);
        if (r.ok) {
          const d = await r.json();
          return [st, d.total_count || 0];
        }
      } catch (err) {
        console.warn(`[updateFolderStatusCounts] Failed count for ${st}:`, err.message);
      }
      return [st, 0];
    });

    const results = await Promise.all(promises);
    const counts = Object.fromEntries(results);

    const countAllEl = document.getElementById("count-status-all");
    const countIdentifiedEl = document.getElementById("count-status-identified");
    const countUnknownEl = document.getElementById("count-status-unknown");
    const countPendingEl = document.getElementById("count-status-pending");
    const countSkippedEl = document.getElementById("count-status-skipped");
    const countHiddenEl = document.getElementById("count-status-hidden");

    if (countAllEl) countAllEl.textContent = counts["all"] || 0;
    if (countIdentifiedEl) countIdentifiedEl.textContent = counts["identified"] || 0;
    if (countUnknownEl) countUnknownEl.textContent = counts["location unknown"] || 0;
    if (countPendingEl) countPendingEl.textContent = counts["pending"] || 0;
    if (countSkippedEl) countSkippedEl.textContent = counts["skipped"] || 0;
    if (countHiddenEl) countHiddenEl.textContent = counts["hidden"] || 0;
    if (foldersBadgeCount) foldersBadgeCount.textContent = counts["all"] || 0;
  } catch (e) {
    console.error("[updateFolderStatusCounts] Error:", e);
  }
}

function renderFoldersTable() {
  if (!foldersTableBody) return;

  if (scannedFolders.length === 0) {
    foldersTableBody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 32px;">No photo folders matching the current filters.</td></tr>`;
    if (foldersPaginationInfo) foldersPaginationInfo.textContent = "Showing 0 of 0 folders";
    if (foldersPrevPageBtn) foldersPrevPageBtn.disabled = true;
    if (foldersNextPageBtn) foldersNextPageBtn.disabled = true;
    return;
  }

  const startIdx = folderPageOffset + 1;
  const endIdx = Math.min(folderPageOffset + scannedFolders.length, scannedFoldersTotal);
  if (foldersPaginationInfo) foldersPaginationInfo.textContent = `Showing ${startIdx}-${endIdx} of ${scannedFoldersTotal} folders`;
  if (foldersPrevPageBtn) foldersPrevPageBtn.disabled = folderPageOffset === 0;
  if (foldersNextPageBtn) foldersNextPageBtn.disabled = endIdx >= scannedFoldersTotal;

  foldersTableBody.innerHTML = "";
  scannedFolders.forEach(item => {
    const tr = document.createElement("tr");
    const statusPillClass = `status-pill-${(item.status || 'unknown').replace(/\s+/g, '-')}`;
    const hasCoords = item.latitude != null && item.longitude != null;
    const coordsStr = hasCoords ? `${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}` : "—";

    tr.innerHTML = `
      <td style="text-align: center;">
        <input type="checkbox" class="folder-row-checkbox" data-id="${item.id}">
      </td>
      <td>
        <span class="path-code" title="${escapeHtml(item.folder_path)}">${escapeHtml(item.folder_path)}</span>
      </td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 4px; align-items: flex-start;">
          <span class="status-pill ${statusPillClass}">${escapeHtml(item.status)}</span>
          ${item.has_conflict ? `<span class="status-pill status-pill-conflict" style="font-size: 10px; padding: 1px 6px;" title="Conflict with places: ${escapeHtml((item.conflict_poi_names || []).join(', ') || item.conflict_note || '')}">⚠️ Conflict</span>` : ''}
        </div>
      </td>
      <td><strong>${escapeHtml(item.site_name || item.folder_name || "—")}</strong></td>
      <td>${escapeHtml(item.city || "—")}</td>
      <td>${escapeHtml(item.state || "—")}</td>
      <td>${escapeHtml(item.country || item.country_code || "—")}</td>
      <td style="text-align: center;">${item.photo_count || 0}</td>
      <td>
        <span class="reasoning-text" title="${escapeHtml(item.reasoning || '')}">${escapeHtml(item.reasoning || "—")}</span>
      </td>
      <td>
        ${item.poi_name ? `<span class="poi-link-badge view-poi-btn" data-poi-id="${item.poi_id}">📍 ${escapeHtml(item.poi_name)}</span>` : '<span style="color: var(--text-muted); font-size: 11px;">(None)</span>'}
        ${item.has_conflict && item.conflict_poi_names && item.conflict_poi_names.length > 0 ? `
          <div style="font-size: 10.5px; color: #b45309; margin-top: 3px;">
            Also: ${item.conflict_poi_names.map(name => `<strong>${escapeHtml(name)}</strong>`).join(', ')}
          </div>
        ` : ''}
      </td>
      <td style="text-align: right; white-space: nowrap;">
        <a href="${getFolderProtocolUrl(item.folder_path)}" class="btn btn-secondary btn-sm folder-open-link" data-path="${escapeHtml(item.folder_path)}" style="padding: 2px 7px; font-size: 11px; text-decoration: none; display: inline-flex; align-items: center; gap: 3px;" title="Open folder in File Explorer">📁 Open</a>
        <button type="button" class="btn btn-secondary btn-sm folder-edit-btn" style="padding: 2px 7px; font-size: 11px;" title="View and edit folder details">✏️ Edit</button>
        <button type="button" class="btn btn-secondary btn-sm folder-assign-btn" style="padding: 2px 7px; font-size: 11px;" title="Assign location / create place">📍 Assign</button>
        ${item.poi_id ? `<button type="button" class="btn btn-secondary btn-sm folder-split-btn" style="padding: 2px 7px; font-size: 11px;" title="Split into new POI">⎘ Split</button>` : `<button type="button" class="btn btn-secondary btn-sm folder-join-btn" style="padding: 2px 7px; font-size: 11px;" title="Link folder to an existing place">🔗 Join</button>`}
        ${item.status === 'skipped' ? `<button type="button" class="btn btn-secondary btn-sm folder-hide-btn" style="padding: 2px 7px; font-size: 11px;" title="Hide folder from default views">👁️‍🗨️ Hide</button>` : ''}
        ${item.status === 'hidden' ? `<button type="button" class="btn btn-secondary btn-sm folder-unhide-btn" style="padding: 2px 7px; font-size: 11px;" title="Unhide folder (set back to skipped)">👁️ Unhide</button>` : ''}
      </td>
    `;

    // Row checkbox
    const cb = tr.querySelector(".folder-row-checkbox");
    cb.onchange = (e) => {
      if (e.target.checked) selectedFolderIds.add(item.id);
      else selectedFolderIds.delete(item.id);
      updateFoldersSelectionUi();
    };

    // View POI click
    const viewPoiBtn = tr.querySelector(".view-poi-btn");
    if (viewPoiBtn) {
      viewPoiBtn.onclick = () => {
        const poi = allPois.find(p => p.id === item.poi_id);
        if (poi) {
          openEditModal(poi);
        } else {
          showToast("Loading place details...");
          apiFetch(`/api/v1/pois/${item.poi_id}`).then(r => r.json()).then(p => openEditModal(p));
        }
      };
    }

    // Row Edit Folder Record
    tr.querySelector(".folder-edit-btn").onclick = () => {
      openEditFolderModal(item);
    };

    // Row Assign Location
    tr.querySelector(".folder-assign-btn").onclick = () => {
      if (!item.poi_id) {
        openCreatePoiFromFolder(item);
      } else {
        openAssignLocationModal(item.latitude, item.longitude, item.site_name || item.folder_name, "scanned-path", item.id);
      }
    };

    // Row Split to new POI (when folder is linked to a POI)
    const splitBtn = tr.querySelector(".folder-split-btn");
    if (splitBtn) {
      splitBtn.onclick = async () => {
        if (!confirm(`Disassociate folder:\n"${item.folder_path}"\nand create a new unlocated POI?`)) return;
        try {
          const r = await apiFetch(`/api/v1/scanned-paths/${item.id}/disassociate-and-split`, { method: "POST" });
          if (!r.ok) throw new Error("Failed to split path");
          const resData = await r.json();
          showToast(`Created new unlocated POI: "${resData.new_poi_name}"`);
          await loadScannedFolders();
          await loadPois();
        } catch (err) {
          showToast(err.message, true);
        }
      };
    }

    // Row Join to existing POI (when folder is unlinked)
    const joinBtn = tr.querySelector(".folder-join-btn");
    if (joinBtn) {
      joinBtn.onclick = () => {
        openJoinFolderModal(item);
      };
    }

    // Row Hide
    const hideBtn = tr.querySelector(".folder-hide-btn");
    if (hideBtn) {
      hideBtn.onclick = async () => {
        try {
          const r = await apiFetch(`/api/v1/scanned-paths/${item.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "hidden" })
          });
          if (!r.ok) throw new Error("Failed to mark folder hidden");
          showToast("Folder marked as hidden");
          await loadScannedFolders();
        } catch (err) {
          showToast(err.message, true);
        }
      };
    }

    // Row Unhide
    const unhideBtn = tr.querySelector(".folder-unhide-btn");
    if (unhideBtn) {
      unhideBtn.onclick = async () => {
        try {
          const r = await apiFetch(`/api/v1/scanned-paths/${item.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "skipped" })
          });
          if (!r.ok) throw new Error("Failed to unhide folder");
          showToast("Folder status set back to skipped");
          await loadScannedFolders();
        } catch (err) {
          showToast(err.message, true);
        }
      };
    }

    foldersTableBody.appendChild(tr);
  });

  updateFoldersSelectionUi();
}

// ==========================================
// 5. Batch Actions for Scanned Folders
// ==========================================

// 5a. Bulk Assign Location (City/State/Country)
const batchFolderLocationModal = document.getElementById("batch-folder-location-modal");
const batchFolderLocationClose = document.getElementById("batch-folder-location-close");
const batchFolderLocationCancelBtn = document.getElementById("batch-folder-location-cancel-btn");
const batchFolderLocationApplyBtn = document.getElementById("batch-folder-location-apply-btn");
const batchFolderCountDisplay = document.getElementById("batch-folder-count-display");
const foldersBulkAssignLocationBtn = document.getElementById("folders-bulk-assign-location-btn");

if (foldersBulkAssignLocationBtn) {
  foldersBulkAssignLocationBtn.onclick = () => {
    if (selectedFolderIds.size === 0) return;
    if (batchFolderCountDisplay) batchFolderCountDisplay.textContent = selectedFolderIds.size;
    document.getElementById("batch-folder-city").value = "";
    document.getElementById("batch-folder-state").value = "";
    document.getElementById("batch-folder-country").value = "";
    batchFolderLocationModal.style.display = "flex";
  };
}

if (batchFolderLocationClose) batchFolderLocationClose.onclick = () => (batchFolderLocationModal.style.display = "none");
if (batchFolderLocationCancelBtn) batchFolderLocationCancelBtn.onclick = () => (batchFolderLocationModal.style.display = "none");

if (batchFolderLocationApplyBtn) {
  batchFolderLocationApplyBtn.onclick = async () => {
    const city = document.getElementById("batch-folder-city").value.trim() || null;
    const state = document.getElementById("batch-folder-state").value.trim() || null;
    const country = document.getElementById("batch-folder-country").value.trim() || null;

    try {
      batchFolderLocationApplyBtn.disabled = true;
      batchFolderLocationApplyBtn.textContent = "Updating...";
      const res = await apiFetch(`/api/v1/scanned-paths/batch-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path_ids: Array.from(selectedFolderIds),
          city: city,
          state: state,
          country: country
        })
      });
      if (!res.ok) throw new Error("Failed to batch update folders");
      const d = await res.json();
      showToast(`Updated location on ${d.updated_count} folders!`);
      batchFolderLocationModal.style.display = "none";
      await loadScannedFolders();
    } catch (e) {
      showToast(e.message, true);
    } finally {
      batchFolderLocationApplyBtn.disabled = false;
      batchFolderLocationApplyBtn.textContent = "Apply to Selected";
    }
  };
}

// 5b. Bulk Mark Skipped
const foldersBulkMarkSkippedBtn = document.getElementById("folders-bulk-mark-skipped-btn");
if (foldersBulkMarkSkippedBtn) {
  foldersBulkMarkSkippedBtn.onclick = async () => {
    if (selectedFolderIds.size === 0) return;
    if (!confirm(`Mark ${selectedFolderIds.size} folders as "skipped"? These will not have POIs created for them.`)) return;

    try {
      const res = await apiFetch(`/api/v1/scanned-paths/batch-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path_ids: Array.from(selectedFolderIds),
          status: "skipped"
        })
      });
      if (!res.ok) throw new Error("Failed to mark folders skipped");
      showToast(`Marked ${selectedFolderIds.size} folders as skipped`);
      selectedFolderIds.clear();
      await loadScannedFolders();
    } catch (e) {
      showToast(e.message, true);
    }
  };
}

// Bulk Mark Hidden
const foldersBulkMarkHiddenBtn = document.getElementById("folders-bulk-mark-hidden-btn");
if (foldersBulkMarkHiddenBtn) {
  foldersBulkMarkHiddenBtn.onclick = async () => {
    if (selectedFolderIds.size === 0) return;
    if (!confirm(`Mark ${selectedFolderIds.size} folders as "hidden"? Hidden folders are excluded by default and can safely be ignored.`)) return;

    try {
      const res = await apiFetch(`/api/v1/scanned-paths/batch-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path_ids: Array.from(selectedFolderIds),
          status: "hidden"
        })
      });
      if (!res.ok) throw new Error("Failed to mark folders hidden");
      showToast(`Marked ${selectedFolderIds.size} folders as hidden`);
      selectedFolderIds.clear();
      await loadScannedFolders();
    } catch (e) {
      showToast(e.message, true);
    }
  };
}

// 5c. Bulk Mark Pending
const foldersBulkMarkPendingBtn = document.getElementById("folders-bulk-mark-pending-btn");
if (foldersBulkMarkPendingBtn) {
  foldersBulkMarkPendingBtn.onclick = async () => {
    if (selectedFolderIds.size === 0) return;
    try {
      const res = await apiFetch(`/api/v1/scanned-paths/batch-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path_ids: Array.from(selectedFolderIds),
          status: "pending"
        })
      });
      if (!res.ok) throw new Error("Failed to reset folders to pending");
      showToast(`Flagged ${selectedFolderIds.size} folders as pending for next photo scan run!`);
      selectedFolderIds.clear();
      await loadScannedFolders();
    } catch (e) {
      showToast(e.message, true);
    }
  };
}

// 5d. Bulk Geocode Preview & Confirmation
const batchGeocodeConfirmModal = document.getElementById("batch-geocode-confirm-modal");
const batchGeocodeConfirmClose = document.getElementById("batch-geocode-confirm-close");
const batchGeocodeCancelBtn = document.getElementById("batch-geocode-cancel-btn");
const batchGeocodeProceedBtn = document.getElementById("batch-geocode-proceed-btn");
const batchGeocodeCandidatesTbody = document.getElementById("batch-geocode-candidates-tbody");
const batchGeocodeSelectAll = document.getElementById("batch-geocode-select-all");
const foldersBulkGeocodeBtn = document.getElementById("folders-bulk-geocode-btn");

let activeGeocodeCandidates = [];

if (batchGeocodeConfirmClose) batchGeocodeConfirmClose.onclick = () => (batchGeocodeConfirmModal.style.display = "none");
if (batchGeocodeCancelBtn) batchGeocodeCancelBtn.onclick = () => (batchGeocodeConfirmModal.style.display = "none");

if (foldersBulkGeocodeBtn) {
  foldersBulkGeocodeBtn.onclick = async () => {
    if (selectedFolderIds.size === 0) return;

    try {
      foldersBulkGeocodeBtn.disabled = true;
      foldersBulkGeocodeBtn.textContent = "Geocoding with OSM...";
      showToast(`Running Nominatim geocoding for ${selectedFolderIds.size} folders...`);

      const res = await apiFetch(`/api/v1/scanned-paths/batch-geocode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path_ids: Array.from(selectedFolderIds) })
      });
      if (!res.ok) throw new Error("Failed to preview batch geocoding");

      const data = await res.json();
      activeGeocodeCandidates = data.candidates || [];

      renderBatchGeocodeCandidates();
      batchGeocodeConfirmModal.style.display = "flex";

    } catch (e) {
      showToast(e.message, true);
    } finally {
      foldersBulkGeocodeBtn.disabled = false;
      foldersBulkGeocodeBtn.textContent = "🗺️ Re-trigger Nominatim Geocode";
    }
  };
}

function renderBatchGeocodeCandidates() {
  if (!batchGeocodeCandidatesTbody) return;
  batchGeocodeCandidatesTbody.innerHTML = "";

  activeGeocodeCandidates.forEach((cand, idx) => {
    const tr = document.createElement("tr");
    const hasCoords = cand.found && cand.latitude != null;
    const actionLabel = cand.action_proposed === "link_poi" 
      ? `Link to existing POI: <strong>${escapeHtml(cand.matched_existing_poi_name || '')}</strong>`
      : (hasCoords ? `<span style="color: #0d9488; font-weight: 600;">Create New POI</span>` : `<span style="color: #ef4444;">No Location Found</span>`);

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="geocode-item-checkbox" data-index="${idx}" ${cand.found ? 'checked' : ''}>
      </td>
      <td>
        <span class="path-code" style="max-width: 200px;" title="${escapeHtml(cand.folder_path)}">${escapeHtml(cand.folder_name)}</span>
      </td>
      <td><span style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(cand.query_used)}</span></td>
      <td>
        ${hasCoords ? `<div>${escapeHtml(cand.display_name || '')}</div><div style="font-size: 11px; color: var(--text-muted);">(${cand.latitude.toFixed(4)}, ${cand.longitude.toFixed(4)})</div>` : '<span style="color: var(--text-muted);">—</span>'}
      </td>
      <td>${actionLabel}</td>
    `;
    batchGeocodeCandidatesTbody.appendChild(tr);
  });

  if (batchGeocodeSelectAll) {
    batchGeocodeSelectAll.onchange = (e) => {
      document.querySelectorAll(".geocode-item-checkbox").forEach(cb => cb.checked = e.target.checked);
    };
  }
}

if (batchGeocodeProceedBtn) {
  batchGeocodeProceedBtn.onclick = async () => {
    const itemsToConfirm = [];
    document.querySelectorAll(".geocode-item-checkbox").forEach(cb => {
      const idx = parseInt(cb.dataset.index, 10);
      const cand = activeGeocodeCandidates[idx];
      if (cand) {
        itemsToConfirm.push({
          path_id: cand.path_id,
          apply: cb.checked,
          create_new_poi: cand.action_proposed !== "link_poi",
          existing_poi_id: cand.matched_existing_poi_id,
          site_name: cand.current_site_name || cand.folder_name,
          latitude: cand.latitude,
          longitude: cand.longitude,
          city: cand.city,
          state: cand.state,
          country: cand.country,
          country_code: cand.country_code
        });
      }
    });

    try {
      batchGeocodeProceedBtn.disabled = true;
      batchGeocodeProceedBtn.textContent = "Applying...";
      const res = await apiFetch(`/api/v1/scanned-paths/batch-confirm-geocode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: itemsToConfirm })
      });
      if (!res.ok) throw new Error("Failed to apply batch geocodes");
      const d = await res.json();
      showToast(`Updated ${d.updated_count} paths (${d.created_poi_count} new POIs, ${d.linked_poi_count} linked)!`);
      batchGeocodeConfirmModal.style.display = "none";
      selectedFolderIds.clear();
      await loadScannedFolders();
      await loadPois();
    } catch (e) {
      showToast(e.message, true);
    } finally {
      batchGeocodeProceedBtn.disabled = false;
      batchGeocodeProceedBtn.textContent = "Confirm & Apply";
    }
  };
}

// ==========================================
// Join Scanned Folder to POI Modal Logic
// ==========================================
let pendingJoinFolderItem = null;
const joinFolderModal = document.getElementById("join-folder-modal");
const joinFolderClose = document.getElementById("join-folder-close");
const joinFolderCancelBtn = document.getElementById("join-folder-cancel-btn");
const joinFolderApplyBtn = document.getElementById("join-folder-apply-btn");
const joinFolderPathDisplay = document.getElementById("join-folder-path-display");
const joinPoiSearchInput = document.getElementById("join-poi-search-input");
const joinPoiId = document.getElementById("join-poi-id");
const joinPoiClearBtn = document.getElementById("join-poi-clear-btn");
const joinPoiToggleBtn = document.getElementById("join-poi-toggle-btn");
const joinPoiDropdown = document.getElementById("join-poi-dropdown");
const joinCopyLocationCheckbox = document.getElementById("join-copy-location-checkbox");

function openJoinFolderModal(folderItem) {
  pendingJoinFolderItem = folderItem;
  if (!joinFolderModal) return;

  if (joinFolderPathDisplay) joinFolderPathDisplay.textContent = folderItem.folder_path;
  if (joinPoiSearchInput) joinPoiSearchInput.value = "";
  if (joinPoiId) joinPoiId.value = "";
  if (joinPoiClearBtn) joinPoiClearBtn.style.display = "none";
  if (joinPoiDropdown) joinPoiDropdown.style.display = "none";
  if (joinFolderApplyBtn) joinFolderApplyBtn.disabled = true;

  joinFolderModal.style.display = "flex";
  setTimeout(() => {
    if (joinPoiSearchInput) joinPoiSearchInput.focus();
  }, 100);
}

function closeJoinFolderModal() {
  if (joinFolderModal) joinFolderModal.style.display = "none";
  pendingJoinFolderItem = null;
  if (joinPoiDropdown) joinPoiDropdown.style.display = "none";
}

if (joinFolderClose) joinFolderClose.onclick = closeJoinFolderModal;
if (joinFolderCancelBtn) joinFolderCancelBtn.onclick = closeJoinFolderModal;

function renderJoinPoiDropdown(searchTerm = "") {
  if (!joinPoiDropdown) return;
  joinPoiDropdown.innerHTML = "";
  const term = searchTerm.toLowerCase().trim();

  const filtered = allPois.filter(p => {
    if (!term) return true;
    const nameMatch = (p.name || "").toLowerCase().includes(term);
    const cityMatch = (p.iptc_city || "").toLowerCase().includes(term);
    const stateMatch = (p.iptc_province_state || "").toLowerCase().includes(term);
    return nameMatch || cityMatch || stateMatch;
  }).slice(0, 30);

  if (filtered.length === 0) {
    joinPoiDropdown.innerHTML = `<div style="padding: 10px; color: var(--text-muted); font-size: 12px; text-align: center;">No matching places found.</div>`;
    joinPoiDropdown.style.display = "block";
    return;
  }

  filtered.forEach(p => {
    const locArr = [];
    if (p.iptc_city) locArr.push(p.iptc_city);
    if (p.iptc_province_state) locArr.push(p.iptc_province_state);
    if (p.iptc_country_code) locArr.push(p.iptc_country_code);
    const locStr = locArr.join(", ");

    const div = document.createElement("div");
    div.className = "combobox-item";
    div.style.cssText = "padding: 8px 10px; cursor: pointer; border-bottom: 1px solid #f1f5f9; font-size: 12.5px;";
    div.innerHTML = `
      <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(p.name)} <span style="font-size: 11px; color: var(--text-muted); font-weight: normal;">(${escapeHtml(p.poi_type || "site to see")})</span></div>
      ${locStr ? `<div style="font-size: 11px; color: #64748b; margin-top: 2px;">📍 ${escapeHtml(locStr)}</div>` : ''}
    `;

    div.addEventListener("click", () => {
      joinPoiId.value = p.id;
      joinPoiSearchInput.value = p.name;
      joinPoiDropdown.style.display = "none";
      if (joinPoiClearBtn) joinPoiClearBtn.style.display = "inline-block";
      if (joinFolderApplyBtn) joinFolderApplyBtn.disabled = false;
    });

    joinPoiDropdown.appendChild(div);
  });

  joinPoiDropdown.style.display = "block";
}

if (joinPoiSearchInput) {
  joinPoiSearchInput.addEventListener("input", (e) => {
    renderJoinPoiDropdown(e.target.value);
  });
  joinPoiSearchInput.addEventListener("focus", () => {
    renderJoinPoiDropdown(joinPoiSearchInput.value);
  });
}

if (joinPoiClearBtn) {
  joinPoiClearBtn.onclick = () => {
    joinPoiId.value = "";
    joinPoiSearchInput.value = "";
    joinPoiClearBtn.style.display = "none";
    if (joinFolderApplyBtn) joinFolderApplyBtn.disabled = true;
    joinPoiDropdown.style.display = "none";
  };
}

if (joinPoiToggleBtn) {
  joinPoiToggleBtn.onclick = () => {
    if (joinPoiDropdown.style.display === "block") {
      joinPoiDropdown.style.display = "none";
    } else {
      renderJoinPoiDropdown(joinPoiSearchInput.value);
    }
  };
}

if (joinFolderApplyBtn) {
  joinFolderApplyBtn.onclick = async () => {
    if (!joinPoiId.value || !pendingJoinFolderItem) {
      showToast("Please choose a place to link this folder to.", true);
      return;
    }
    const targetPoi = allPois.find(p => p.id === joinPoiId.value);
    if (!targetPoi) {
      showToast("Selected place not found.", true);
      return;
    }

    const payload = {
      poi_id: targetPoi.id,
      status: "identified"
    };

    if (joinCopyLocationCheckbox?.checked) {
      if (targetPoi.latitude != null) payload.latitude = targetPoi.latitude;
      if (targetPoi.longitude != null) payload.longitude = targetPoi.longitude;
      if (targetPoi.iptc_city) payload.city = targetPoi.iptc_city;
      if (targetPoi.iptc_province_state) payload.state = targetPoi.iptc_province_state;
      if (targetPoi.iptc_country_code) {
        payload.country_code = targetPoi.iptc_country_code;
        payload.country = targetPoi.iptc_country_code;
      }
    }

    joinFolderApplyBtn.disabled = true;
    joinFolderApplyBtn.textContent = "Linking...";
    try {
      const res = await apiFetch(`/api/v1/scanned-paths/${pendingJoinFolderItem.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to link folder to place");
      showToast(`Folder linked to "${targetPoi.name}"!`);
      closeJoinFolderModal();
      await loadScannedFolders();
      updateFolderStatusCounts();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      joinFolderApplyBtn.disabled = false;
      joinFolderApplyBtn.textContent = "🔗 Link to Selected Place";
    }
  };
}

// ==========================================
// Edit Scanned Folder Record Modal Logic
// ==========================================
let currentEditingFolder = null;
let currentEditingFolderPoi = null;

const editFolderModal = document.getElementById("edit-folder-modal");
const editFolderModalClose = document.getElementById("edit-folder-modal-close");
const editFolderCancelBtn = document.getElementById("edit-folder-cancel-btn");
const editFolderSaveBtn = document.getElementById("edit-folder-save-btn");
const editFolderPathDisplay = document.getElementById("edit-folder-path-display");
const editFolderStatus = document.getElementById("edit-folder-status");
const editFolderPhotoCount = document.getElementById("edit-folder-photo-count");
const editFolderDates = document.getElementById("edit-folder-dates");
const editFolderCoords = document.getElementById("edit-folder-coords");
const editFolderPoiInfoContainer = document.getElementById("edit-folder-poi-info-container");
const editFolderPoiActions = document.getElementById("edit-folder-poi-actions");
const editFolderOtherFoldersBox = document.getElementById("edit-folder-other-folders-box");
const editFolderOtherFoldersTitle = document.getElementById("edit-folder-other-folders-title");
const editFolderOtherFoldersList = document.getElementById("edit-folder-other-folders-list");
const editFolderSyncToolbar = document.getElementById("edit-folder-sync-toolbar");
const editFolderSelectDiffBtn = document.getElementById("edit-folder-select-diff-btn");
const editFolderSyncCheckedBtn = document.getElementById("edit-folder-sync-checked-btn");
const editFolderReasoning = document.getElementById("edit-folder-reasoning");

function closeEditFolderModal() {
  if (editFolderModal) editFolderModal.style.display = "none";
  currentEditingFolder = null;
  currentEditingFolderPoi = null;
  const editFolderOpenBtn = document.getElementById("edit-folder-open-btn");
  if (editFolderOpenBtn) editFolderOpenBtn.style.display = "none";
}

if (editFolderModalClose) editFolderModalClose.onclick = closeEditFolderModal;
if (editFolderCancelBtn) editFolderCancelBtn.onclick = closeEditFolderModal;

async function openEditFolderModal(folderItem) {
  currentEditingFolder = folderItem;
  currentEditingFolderPoi = null;
  if (!editFolderModal) return;

  document.getElementById("edit-folder-id").value = folderItem.id;
  document.getElementById("edit-folder-poi-id").value = folderItem.poi_id || "";
  if (editFolderPathDisplay) editFolderPathDisplay.textContent = folderItem.folder_path;

  const editFolderOpenBtn = document.getElementById("edit-folder-open-btn");
  if (editFolderOpenBtn) {
    if (folderItem.folder_path) {
      editFolderOpenBtn.style.display = "inline-flex";
      editFolderOpenBtn.href = getFolderProtocolUrl(folderItem.folder_path);
      editFolderOpenBtn.setAttribute("data-path", folderItem.folder_path);
    } else {
      editFolderOpenBtn.style.display = "none";
    }
  }

  if (editFolderStatus) editFolderStatus.value = folderItem.status || "identified";
  if (editFolderPhotoCount) editFolderPhotoCount.textContent = folderItem.photo_count || 0;

  // Dates
  const dateParts = [];
  if (folderItem.earliest_date) dateParts.push(folderItem.earliest_date.slice(0, 10));
  if (folderItem.latest_date && folderItem.latest_date !== folderItem.earliest_date) {
    dateParts.push(folderItem.latest_date.slice(0, 10));
  }
  if (editFolderDates) editFolderDates.textContent = dateParts.length > 0 ? dateParts.join(" → ") : "None recorded";

  // Coordinates
  const hasCoords = folderItem.latitude != null && folderItem.longitude != null;
  if (editFolderCoords) {
    editFolderCoords.textContent = hasCoords
      ? `${folderItem.latitude.toFixed(4)}, ${folderItem.longitude.toFixed(4)}`
      : "Not set";
  }

  // Populate inputs
  document.getElementById("edit-folder-site-name").value = folderItem.site_name || "";
  document.getElementById("edit-folder-city").value = folderItem.city || "";
  document.getElementById("edit-folder-state").value = folderItem.state || "";
  document.getElementById("edit-folder-country").value = folderItem.country || folderItem.country_code || "";
  if (editFolderReasoning) editFolderReasoning.value = folderItem.reasoning || "";

  // Reset comparison elements
  ["site-name", "city", "state", "country"].forEach(key => {
    const badge = document.getElementById(`diff-badge-${key}`);
    const poiValEl = document.getElementById(`poi-val-${key}`);
    const cb = document.getElementById(`diff-check-${key}`);
    const row = badge ? badge.closest(".folder-diff-row") : null;
    if (badge) {
      badge.textContent = "—";
      badge.className = "badge";
    }
    if (poiValEl) poiValEl.innerHTML = `POI: <strong style="color: #64748b;">—</strong>`;
    if (cb) {
      cb.checked = false;
      cb.disabled = true;
    }
    if (row) {
      row.classList.remove("diff-active", "diff-synced");
    }
  });

  // Check POI association
  if (folderItem.poi_id) {
    let poi = allPois.find(p => p.id === folderItem.poi_id);
    if (!poi) {
      if (editFolderPoiInfoContainer) {
        editFolderPoiInfoContainer.innerHTML = '<span style="font-size: 12px; color: var(--text-muted);">Loading associated place...</span>';
      }
      try {
        const res = await apiFetch(`/api/v1/pois/${folderItem.poi_id}`);
        if (res.ok) {
          poi = await res.json();
        }
      } catch (e) {
        console.warn("Could not fetch associated POI:", e);
      }
    }

    if (poi) {
      currentEditingFolderPoi = poi;
      renderFolderPoiSection(folderItem, poi);
      loadOtherFoldersForPoi(folderItem.poi_id, folderItem.id);
    } else {
      renderUnlinkedPoiSection(folderItem);
    }
  } else {
    renderUnlinkedPoiSection(folderItem);
  }

  editFolderModal.style.display = "flex";
}

function renderUnlinkedPoiSection(folderItem) {
  if (editFolderPoiActions) editFolderPoiActions.innerHTML = "";
  if (editFolderOtherFoldersBox) editFolderOtherFoldersBox.style.display = "none";
  if (editFolderSyncToolbar) editFolderSyncToolbar.style.display = "none";

  if (editFolderPoiInfoContainer) {
    editFolderPoiInfoContainer.innerHTML = `
      <div style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
        <span style="color: var(--text-muted); font-size: 12px;">This folder is not linked to any Point of Interest.</span>
        <div style="display: flex; gap: 6px;">
          <button type="button" class="btn btn-secondary btn-xs" id="edit-folder-join-btn" style="font-size: 11px; padding: 3px 8px;">🔗 Join Existing Place</button>
          <button type="button" class="btn btn-primary btn-xs" id="edit-folder-assign-btn" style="font-size: 11px; padding: 3px 8px;">📍 Create Place from Folder</button>
        </div>
      </div>
    `;

    const joinBtn = document.getElementById("edit-folder-join-btn");
    if (joinBtn) {
      joinBtn.onclick = () => {
        closeEditFolderModal();
        openJoinFolderModal(folderItem);
      };
    }
    const assignBtn = document.getElementById("edit-folder-assign-btn");
    if (assignBtn) {
      assignBtn.onclick = () => {
        closeEditFolderModal();
        openCreatePoiFromFolder(folderItem);
      };
    }
  }
}

function renderFolderPoiSection(folderItem, poi) {
  if (editFolderSyncToolbar) editFolderSyncToolbar.style.display = "flex";
  if (editFolderPoiActions) editFolderPoiActions.innerHTML = "";

  const locParts = [poi.iptc_city, poi.iptc_province_state, poi.iptc_country_code].filter(Boolean);
  const locStr = locParts.length > 0 ? locParts.join(", ") : "No address specified";

  if (editFolderPoiInfoContainer) {
    editFolderPoiInfoContainer.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px; padding: 8px 12px; flex-wrap: wrap; gap: 8px;">
        <div>
          <strong style="color: #0f766e; font-size: 13px;">📍 ${escapeHtml(poi.name)}</strong>
          <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">(${escapeHtml(poi.poi_type || "site to see")})</span>
          <div style="font-size: 11px; color: #475569; margin-top: 2px;">
            ${escapeHtml(locStr)}
          </div>
        </div>
        <button type="button" class="btn btn-secondary btn-xs" id="edit-folder-view-poi-btn" style="font-size: 11px; padding: 3px 8px;">
          👁️ View / Edit Place
        </button>
      </div>
    `;

    const viewPoiBtn = document.getElementById("edit-folder-view-poi-btn");
    if (viewPoiBtn) {
      viewPoiBtn.onclick = () => {
        closeEditFolderModal();
        openEditModal(poi);
      };
    }
  }

  updateFolderPoiDiffComparison(poi);
}

function updateFolderPoiDiffComparison(poi) {
  if (!poi) return;

  const fieldsConfig = [
    {
      key: "site-name",
      field: "site_name",
      folderInputId: "edit-folder-site-name",
      poiVal: (poi.name || "").trim()
    },
    {
      key: "city",
      field: "city",
      folderInputId: "edit-folder-city",
      poiVal: (poi.iptc_city || "").trim()
    },
    {
      key: "state",
      field: "state",
      folderInputId: "edit-folder-state",
      poiVal: (poi.iptc_province_state || "").trim()
    },
    {
      key: "country",
      field: "country",
      folderInputId: "edit-folder-country",
      poiVal: (poi.iptc_country_code || "").trim()
    }
  ];

  fieldsConfig.forEach(cfg => {
    const folderInput = document.getElementById(cfg.folderInputId);
    const badge = document.getElementById(`diff-badge-${cfg.key}`);
    const poiValEl = document.getElementById(`poi-val-${cfg.key}`);
    const cb = document.getElementById(`diff-check-${cfg.key}`);
    const copyBtn = document.querySelector(`.diff-copy-btn[data-field="${cfg.field}"]`);
    const row = badge ? badge.closest(".folder-diff-row") : null;

    const folderVal = (folderInput ? folderInput.value : "").trim();
    const poiVal = cfg.poiVal;

    if (poiValEl) {
      poiValEl.innerHTML = `POI: <strong style="color: #0f172a;">${escapeHtml(poiVal || "(empty)")}</strong>`;
      poiValEl.title = `POI value: ${poiVal || "None"}`;
    }

    if (cb) {
      cb.dataset.poiVal = poiVal;
      cb.disabled = !poiVal;
    }

    if (copyBtn) {
      copyBtn.dataset.poiVal = poiVal;
      copyBtn.disabled = !poiVal;
      copyBtn.onclick = () => {
        if (folderInput) {
          folderInput.value = poiVal;
          if (cb) cb.checked = true;
          updateFieldDiffStatus(cfg, folderInput.value.trim(), poiVal);
          if (row) {
            row.classList.remove("diff-active");
            row.classList.add("diff-synced");
          }
          showToast(`Copied ${cfg.field} from POI!`);
        }
      };
    }

    // Attach real-time input change
    if (folderInput && !folderInput.dataset.hasDiffListener) {
      folderInput.dataset.hasDiffListener = "true";
      folderInput.addEventListener("input", () => {
        if (currentEditingFolderPoi) {
          const livePoiVal = cfg.field === "site_name" ? (currentEditingFolderPoi.name || "").trim()
            : cfg.field === "city" ? (currentEditingFolderPoi.iptc_city || "").trim()
            : cfg.field === "state" ? (currentEditingFolderPoi.iptc_province_state || "").trim()
            : (currentEditingFolderPoi.iptc_country_code || "").trim();
          updateFieldDiffStatus(cfg, folderInput.value.trim(), livePoiVal);
        }
      });
    }

    updateFieldDiffStatus(cfg, folderVal, poiVal);
  });
}

function updateFieldDiffStatus(cfg, folderVal, poiVal) {
  const badge = document.getElementById(`diff-badge-${cfg.key}`);
  const row = badge ? badge.closest(".folder-diff-row") : null;
  const cb = document.getElementById(`diff-check-${cfg.key}`);

  if (!badge) return;

  const fNorm = (folderVal || "").toLowerCase();
  const pNorm = (poiVal || "").toLowerCase();

  if (!fNorm && !pNorm) {
    badge.textContent = "Empty";
    badge.className = "badge badge-diff-empty";
    if (row) row.classList.remove("diff-active", "diff-synced");
    if (cb) cb.checked = false;
  } else if (fNorm === pNorm) {
    badge.textContent = "✓ Matches POI";
    badge.className = "badge badge-diff-match";
    if (row) row.classList.remove("diff-active");
  } else {
    badge.textContent = "≠ Differs from POI";
    badge.className = "badge badge-diff-mismatch";
    if (row && !row.classList.contains("diff-synced")) {
      row.classList.add("diff-active");
    }
  }
}

// Select All Differing button
if (editFolderSelectDiffBtn) {
  editFolderSelectDiffBtn.onclick = () => {
    if (!currentEditingFolderPoi) return;
    const diffCheckboxes = document.querySelectorAll(".diff-checkbox");
    let count = 0;
    diffCheckboxes.forEach(cb => {
      const field = cb.dataset.field;
      const key = field.replace("_", "-");
      const folderInput = document.getElementById(`edit-folder-${key}`);
      const folderVal = (folderInput ? folderInput.value : "").trim().toLowerCase();
      const poiVal = (cb.dataset.poiVal || "").trim().toLowerCase();
      if (poiVal && folderVal !== poiVal) {
        cb.checked = true;
        count++;
      } else {
        cb.checked = false;
      }
    });
    showToast(`Selected ${count} differing field${count === 1 ? '' : 's'}.`);
  };
}

// Take Checked from POI button
if (editFolderSyncCheckedBtn) {
  editFolderSyncCheckedBtn.onclick = () => {
    if (!currentEditingFolderPoi) return;
    const checkedBoxes = document.querySelectorAll(".diff-checkbox:checked");
    if (checkedBoxes.length === 0) {
      showToast("Please check at least one field to take from the POI.", true);
      return;
    }

    let syncedCount = 0;
    checkedBoxes.forEach(cb => {
      const field = cb.dataset.field;
      const key = field.replace("_", "-");
      const folderInput = document.getElementById(`edit-folder-${key}`);
      const poiVal = cb.dataset.poiVal || "";
      if (folderInput) {
        folderInput.value = poiVal;
        syncedCount++;
        const row = folderInput.closest(".folder-diff-row");
        if (row) {
          row.classList.remove("diff-active");
          row.classList.add("diff-synced");
        }
        const badge = document.getElementById(`diff-badge-${key}`);
        if (badge) {
          badge.textContent = "✓ Matches POI";
          badge.className = "badge badge-diff-match";
        }
      }
    });

    showToast(`Copied ${syncedCount} field value${syncedCount === 1 ? '' : 's'} from POI into folder! Click Save to apply.`);
  };
}

async function loadOtherFoldersForPoi(poiId, currentFolderId) {
  if (!editFolderOtherFoldersBox || !editFolderOtherFoldersList) return;
  editFolderOtherFoldersBox.style.display = "block";
  editFolderOtherFoldersList.innerHTML = '<span style="color: var(--text-muted);">Loading related folders...</span>';

  try {
    const res = await apiFetch(`/api/v1/scanned-paths?poi_id=${poiId}&limit=100&include_hidden=true`);
    if (!res.ok) throw new Error("Failed to load other folders");
    const data = await res.json();
    const items = data.items || [];
    const otherFolders = items.filter(f => f.id !== currentFolderId);

    if (editFolderOtherFoldersTitle) {
      editFolderOtherFoldersTitle.textContent = `Other Folders Linked to this Place (${otherFolders.length}):`;
    }

    if (otherFolders.length === 0) {
      editFolderOtherFoldersList.innerHTML = '<span style="color: var(--text-muted); font-size: 11.5px;">This is the only photo folder linked to this place.</span>';
      return;
    }

    editFolderOtherFoldersList.innerHTML = "";
    otherFolders.forEach(other => {
      const row = document.createElement("div");
      row.style.cssText = "display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; gap: 8px;";
      const statusPillClass = `status-pill-${(other.status || 'unknown').replace(/\s+/g, '-')}`;

      row.innerHTML = `
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="status-pill ${statusPillClass}" style="font-size: 9.5px; padding: 1px 5px;">${escapeHtml(other.status)}</span>
            <strong style="color: var(--text-main); font-size: 11.5px;">${escapeHtml(other.folder_name || 'Folder')}</strong>
            <span style="font-size: 10.5px; color: var(--text-muted);">(${other.photo_count || 0} photos)</span>
          </div>
          <div style="font-family: monospace; font-size: 10.5px; color: var(--text-muted); word-break: break-all; white-space: normal; overflow-wrap: anywhere; line-height: 1.35; margin-top: 2px;" title="${escapeHtml(other.folder_path)}">
            ${escapeHtml(other.folder_path)}
          </div>
        </div>
        <button type="button" class="btn btn-secondary btn-xs switch-other-folder-btn" style="font-size: 10px; padding: 2px 6px;">
          ✏️ Edit
        </button>
      `;

      row.querySelector(".switch-other-folder-btn").onclick = () => {
        openEditFolderModal(other);
      };

      editFolderOtherFoldersList.appendChild(row);
    });
  } catch (err) {
    editFolderOtherFoldersList.innerHTML = `<span style="color: #ef4444; font-size: 11px;">Error loading other folders: ${escapeHtml(err.message)}</span>`;
  }
}

// Save Folder Record button
if (editFolderSaveBtn) {
  editFolderSaveBtn.onclick = async () => {
    if (!currentEditingFolder) return;

    const site_name = (document.getElementById("edit-folder-site-name")?.value || "").trim();
    const city = (document.getElementById("edit-folder-city")?.value || "").trim();
    const state = (document.getElementById("edit-folder-state")?.value || "").trim();
    const rawCountry = (document.getElementById("edit-folder-country")?.value || "").trim();
    const mappedCode = mapCountryNameToAlpha2(rawCountry) || (rawCountry ? rawCountry.toUpperCase() : null);
    const reasoning = (editFolderReasoning?.value || "").trim();
    const status = editFolderStatus?.value || "identified";

    const payload = {
      site_name: site_name || null,
      city: city || null,
      state: state || null,
      country: rawCountry || null,
      country_code: mappedCode || null,
      reasoning: reasoning || null,
      status: status
    };

    editFolderSaveBtn.disabled = true;
    editFolderSaveBtn.textContent = "Saving...";

    try {
      const res = await apiFetch(`/api/v1/scanned-paths/${currentEditingFolder.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to save folder record");
      showToast("Folder record saved successfully!");
      closeEditFolderModal();
      await loadScannedFolders();
      updateFolderStatusCounts();
    } catch (e) {
      showToast(e.message, true);
    } finally {
      editFolderSaveBtn.disabled = false;
      editFolderSaveBtn.textContent = "💾 Save Folder Record";
    }
  };
}

// ==========================================
// Universal Bulk POI Ingestion & Conflict Resolution
// ==========================================

let currentImportState = {
  rawContent: "",
  filename: null,
  formatHint: null,
  parsedData: null,
  appliedTags: [],
  listScope: "both"
};

const importPoisBtn = document.getElementById("import-pois-btn");
const importPoisModal = document.getElementById("import-pois-modal");
const importModalClose = document.getElementById("import-modal-close");
const importModalCancelBtn = document.getElementById("import-modal-cancel-btn");
const importBackBtn = document.getElementById("import-back-btn");
const importParseBtn = document.getElementById("import-parse-btn");
const importCommitBtn = document.getElementById("import-commit-btn");
const importDoneBtn = document.getElementById("import-done-btn");

const importStepInput = document.getElementById("import-step-input");
const importStepPreview = document.getElementById("import-step-preview");
const importStepSuccess = document.getElementById("import-step-success");
const importInputError = document.getElementById("import-input-error");

const importDropzone = document.getElementById("import-dropzone");
const importDropzoneLabel = document.getElementById("import-dropzone-label");
const importFileRemoveBtn = document.getElementById("import-file-remove-btn");
const importFileInput = document.getElementById("import-file-input");
const importRawTextarea = document.getElementById("import-raw-textarea");
const importClearTextBtn = document.getElementById("import-clear-text-btn");
const importDefaultTags = document.getElementById("import-default-tags");
const importTargetList = document.getElementById("import-target-list");
const importNewListTitle = document.getElementById("import-new-list-title");
const importClearNewListBtn = document.getElementById("import-clear-new-list-btn");
const importListScopeNote = document.getElementById("import-list-scope-note");
const importScopeBothBtn = document.getElementById("import-scope-both-btn");
const importScopeNewBtn = document.getElementById("import-scope-new-btn");
const importGeocodeToggle = document.getElementById("import-geocode-toggle");

const previewStatTotal = document.getElementById("preview-stat-total");
const previewStatValid = document.getElementById("preview-stat-valid");
const previewStatFlagged = document.getElementById("preview-stat-flagged");
const previewStatConflicts = document.getElementById("preview-stat-conflicts");
const previewStatList = document.getElementById("preview-stat-list");
const previewBulkConflictSelect = document.getElementById("preview-bulk-conflict-select");
const importPreviewTbody = document.getElementById("import-preview-tbody");
let currentImportSort = { column: null, direction: "asc" };
let hiddenImportActions = new Set();
const ACTION_FILTER_LABELS = {
  CREATE: "Create",
  ADD_TAGS: "Add Tags",
  MERGE: "Merge",
  SKIP: "Skip",
  LINK: "Link",
};

const importProgressContainer = document.getElementById("import-progress-container");
const importProgressStatusText = document.getElementById("import-progress-status-text");
const importProgressTime = document.getElementById("import-progress-time");
const importProgressBar = document.getElementById("import-progress-bar");
const importProgressDetail = document.getElementById("import-progress-detail");

let importProgressTimer = null;
let importProgressStartTime = 0;

function startImportProgress(initialMessage = "Parsing file & analyzing places...") {
  if (importProgressContainer) importProgressContainer.style.display = "block";
  if (importProgressStatusText) importProgressStatusText.textContent = initialMessage;
  if (importProgressBar) {
    importProgressBar.style.width = "25%";
    importProgressBar.classList.add("progress-shimmer");
  }
  if (importProgressDetail) {
    importProgressDetail.textContent = "Validating columns, checking coordinate cache, and scanning duplicate records...";
  }

  importProgressStartTime = Date.now();
  if (importProgressTime) importProgressTime.textContent = "0.0s elapsed";

  clearInterval(importProgressTimer);
  importProgressTimer = setInterval(() => {
    const elapsedSec = ((Date.now() - importProgressStartTime) / 1000).toFixed(1);
    if (importProgressTime) importProgressTime.textContent = `${elapsedSec}s elapsed`;

    const sec = parseFloat(elapsedSec);
    if (importProgressBar) {
      if (sec < 2.0) {
        importProgressBar.style.width = "40%";
        if (importProgressDetail) importProgressDetail.textContent = "Extracting records and mapping columns to standard fields...";
      } else if (sec < 5.0) {
        importProgressBar.style.width = "65%";
        if (importProgressDetail) importProgressDetail.textContent = "Checking spatial coordinates and local PostGIS geocache...";
      } else if (sec < 10.0) {
        importProgressBar.style.width = "85%";
        if (importProgressDetail) importProgressDetail.textContent = "Evaluating collision similarity against your existing places...";
      } else {
        importProgressBar.style.width = "92%";
        if (importProgressDetail) importProgressDetail.textContent = "Processing large dataset — finalizing preview matrix...";
      }
    }
  }, 100);
}

function stopImportProgress() {
  clearInterval(importProgressTimer);
  importProgressTimer = null;
  if (importProgressContainer) importProgressContainer.style.display = "none";
}

function clearUploadedFile() {
  currentImportState.uploadedFile = null;
  currentImportState.fileContent = null;
  currentImportState.filename = null;
  if (importFileInput) importFileInput.value = "";
  if (importDropzoneLabel) importDropzoneLabel.textContent = "Click to choose file or drag & drop here";
  if (importFileRemoveBtn) importFileRemoveBtn.style.display = "none";
}

function updateImportScopeUI(scope) {
  currentImportState.listScope = scope === "new_only" ? "new_only" : "both";
  if (currentImportState.listScope === "new_only") {
    if (importScopeNewBtn) {
      importScopeNewBtn.className = "btn btn-xs btn-primary";
    }
    if (importScopeBothBtn) {
      importScopeBothBtn.className = "btn btn-xs btn-secondary";
    }
    if (importListScopeNote) {
      importListScopeNote.textContent = "Newly created places only (existing matches excluded)";
    }
  } else {
    if (importScopeBothBtn) {
      importScopeBothBtn.className = "btn btn-xs btn-primary";
    }
    if (importScopeNewBtn) {
      importScopeNewBtn.className = "btn btn-xs btn-secondary";
    }
    if (importListScopeNote) {
      importListScopeNote.textContent = "Both newly created & matching existing places";
    }
  }
}

function resetImportModal() {
  stopImportProgress();
  hiddenImportActions.clear();
  currentImportSort = { column: null, direction: "asc" };
  updateImportSortIndicators();
  currentImportState = {
    uploadedFile: null,
    fileContent: null,
    rawContent: "",
    filename: null,
    formatHint: null,
    parsedData: null,
    appliedTags: [],
    listScope: "both"
  };

  clearUploadedFile();
  if (importRawTextarea) importRawTextarea.value = "";
  if (importDefaultTags) importDefaultTags.value = "";
  if (importNewListTitle) importNewListTitle.value = "";
  if (importClearNewListBtn) importClearNewListBtn.style.display = "none";
  updateImportScopeUI("both");
  if (previewStatList) previewStatList.style.display = "none";
  if (importInputError) {
    importInputError.style.display = "none";
    importInputError.textContent = "";
  }

  // Populate lists
  if (importTargetList && typeof availableLists !== "undefined") {
    importTargetList.innerHTML = '<option value="">-- No list assignment --</option>';
    availableLists.forEach((l) => {
      const opt = document.createElement("option");
      opt.value = l.id;
      opt.textContent = `${l.title} ${l.is_trip ? "✈️" : "📁"}`;
      importTargetList.appendChild(opt);
    });
  }

  showImportStep(1);
}

function showImportStep(stepNumber) {
  if (importStepInput) importStepInput.style.display = stepNumber === 1 ? "block" : "none";
  if (importStepPreview) importStepPreview.style.display = stepNumber === 2 ? "block" : "none";
  if (importStepSuccess) importStepSuccess.style.display = stepNumber === 3 ? "block" : "none";

  if (importBackBtn) importBackBtn.style.display = stepNumber === 2 ? "inline-block" : "none";
  if (importParseBtn) importParseBtn.style.display = stepNumber === 1 ? "inline-block" : "none";
  if (importCommitBtn) importCommitBtn.style.display = stepNumber === 2 ? "inline-block" : "none";
  if (importDoneBtn) importDoneBtn.style.display = stepNumber === 3 ? "inline-block" : "none";

  const subtitle = document.getElementById("import-modal-subtitle");
  if (subtitle) {
    if (stepNumber === 1) subtitle.textContent = "Ingest CSV, TSV, JSON, GeoJSON, KML, GPX, XML";
    else if (stepNumber === 2) subtitle.textContent = "Standardized Review: Verify mapped fields, review quality flags, and resolve conflicts";
    else if (stepNumber === 3) subtitle.textContent = "Import complete! Places have been committed to your database";
  }
}

window.openImportModal = function() {
  resetImportModal();
  const modal = document.getElementById("import-pois-modal");
  if (modal) modal.style.display = "flex";
};

if (importPoisBtn) {
  importPoisBtn.addEventListener("click", () => {
    window.openImportModal();
  });
}

// Global delegated fallback for import button
document.addEventListener("click", (e) => {
  const btn = e.target.closest("#import-pois-btn");
  if (btn) {
    window.openImportModal();
  }
});

if (importModalClose) {
  importModalClose.addEventListener("click", () => {
    if (importPoisModal) importPoisModal.style.display = "none";
  });
}

if (importModalCancelBtn) {
  importModalCancelBtn.addEventListener("click", () => {
    if (importPoisModal) importPoisModal.style.display = "none";
  });
}

if (importPoisModal) {
  importPoisModal.addEventListener("click", (e) => {
    if (e.target === importPoisModal) {
      importPoisModal.style.display = "none";
    }
  });
}

if (importBackBtn) {
  importBackBtn.addEventListener("click", () => {
    showImportStep(1);
  });
}

// Clear text button
if (importClearTextBtn) {
  importClearTextBtn.addEventListener("click", () => {
    if (importRawTextarea) importRawTextarea.value = "";
    currentImportState.rawContent = "";
  });
}

// New List Title & Membership Scope Controls
if (importNewListTitle) {
  importNewListTitle.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    if (val) {
      if (importClearNewListBtn) importClearNewListBtn.style.display = "inline-block";
      if (importTargetList) importTargetList.value = "";
    } else {
      if (importClearNewListBtn) importClearNewListBtn.style.display = "none";
    }
  });
}

if (importClearNewListBtn) {
  importClearNewListBtn.addEventListener("click", () => {
    if (importNewListTitle) importNewListTitle.value = "";
    importClearNewListBtn.style.display = "none";
  });
}

if (importTargetList) {
  importTargetList.addEventListener("change", () => {
    if (importTargetList.value) {
      if (importNewListTitle) importNewListTitle.value = "";
      if (importClearNewListBtn) importClearNewListBtn.style.display = "none";
    }
  });
}

if (importScopeBothBtn) {
  importScopeBothBtn.addEventListener("click", () => {
    updateImportScopeUI("both");
  });
}

if (importScopeNewBtn) {
  importScopeNewBtn.addEventListener("click", () => {
    updateImportScopeUI("new_only");
  });
}

// File Dropzone & Input
if (importDropzone && importFileInput) {
  importDropzone.addEventListener("click", (e) => {
    if (e.target.closest("#import-file-remove-btn")) return;
    importFileInput.click();
  });

  importDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    importDropzone.classList.add("dragover");
  });

  importDropzone.addEventListener("dragleave", () => {
    importDropzone.classList.remove("dragover");
  });

  importDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    importDropzone.classList.remove("dragover");
    if (e.dataTransfer?.files?.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  importFileInput.addEventListener("change", (e) => {
    if (e.target.files?.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

if (importFileRemoveBtn) {
  importFileRemoveBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearUploadedFile();
  });
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"));
    reader.readAsText(file);
  });
}

function handleFileSelected(file) {
  if (!file) return;
  currentImportState.uploadedFile = file;
  currentImportState.filename = file.name;
  currentImportState.fileContent = null;

  if (importDropzoneLabel) {
    importDropzoneLabel.innerHTML = `<strong>Selected file:</strong> ${escapeHtml(file.name)} <span style="font-weight: normal; color: #64748b;">(${(file.size / 1024).toFixed(1)} KB)</span>`;
  }
  if (importFileRemoveBtn) {
    importFileRemoveBtn.style.display = "inline-block";
  }

  if (importInputError) {
    importInputError.style.display = "none";
    importInputError.textContent = "";
  }

  // Read full content into memory asynchronously — do NOT paste or truncate inside importRawTextarea!
  const reader = new FileReader();
  reader.onload = (e) => {
    currentImportState.fileContent = e.target.result;
  };
  reader.readAsText(file);
}

// Parse & Review
if (importParseBtn) {
  importParseBtn.addEventListener("click", async () => {
    let rawContent = "";
    let filename = null;

    if (currentImportState.uploadedFile) {
      // 1. If a file is uploaded, use it!
      if (!currentImportState.fileContent) {
        try {
          currentImportState.fileContent = await readFileAsText(currentImportState.uploadedFile);
        } catch (readErr) {
          showToast(`Error reading file: ${readErr.message}`, true);
          return;
        }
      }
      rawContent = currentImportState.fileContent || "";
      filename = currentImportState.filename || currentImportState.uploadedFile.name;
    } else if (importRawTextarea && importRawTextarea.value.trim()) {
      // 2. Otherwise check the "Direct Text" box for content
      rawContent = importRawTextarea.value.trim();
      filename = null;
    }

    // 3. If neither of these are found, display warning popup and abort
    if (!rawContent || !rawContent.trim()) {
      const warnMsg = "Please upload a file or paste data into the Direct Text box before parsing.";
      if (importInputError) {
        importInputError.style.display = "block";
        importInputError.textContent = warnMsg;
      }
      showToast(warnMsg, true);
      return;
    }

    if (importInputError) {
      importInputError.style.display = "none";
      importInputError.textContent = "";
    }

    const defaultTags = (importDefaultTags?.value || "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const newListName = importNewListTitle ? importNewListTitle.value.trim() : "";
    const targetListId = newListName ? null : (importTargetList?.value || null);
    const performGeocoding = importGeocodeToggle ? importGeocodeToggle.checked : true;

    importParseBtn.disabled = true;
    importParseBtn.innerHTML = '<span class="spinner-sm"></span> <span>Parsing & Geocoding...</span>';
    if (importModalCancelBtn) importModalCancelBtn.disabled = true;
    if (importDropzone) importDropzone.style.pointerEvents = "none";
    startImportProgress("Parsing file & analyzing places...");

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      abortController.abort();
    }, 180000); // 180-second safety timeout for large datasets

    try {
      const res = await apiFetch("/api/v1/pois/ingest/parse-and-preview", {
        method: "POST",
        signal: abortController.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: rawContent,
          filename: filename,
          format_hint: currentImportState.formatHint,
          default_tags: defaultTags,
          target_list_id: targetListId,
          perform_geocoding: performGeocoding
        })
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({}));
        const detailMsg = errorJson.detail || `Server returned status ${res.status}`;
        if (importInputError) {
          importInputError.style.display = "block";
          importInputError.innerHTML = `<strong>⚠️ Parsing Failed:</strong> ${escapeHtml(detailMsg)}`;
        }
        showToast(detailMsg, true);
        return;
      }

      const previewData = await res.json();
      currentImportState.parsedData = previewData;
      currentImportState.appliedTags = defaultTags;
      currentImportSort = { column: null, direction: "asc" };
      renderStandardizedPreview(previewData);
      showImportStep(2);
    } catch (err) {
      clearTimeout(timeoutId);
      console.error("[Bulk Import] Error during parse-and-preview:", err);
      let errMsg = err.message || "An unexpected error occurred while parsing places.";
      if (err.name === "AbortError") {
        errMsg = "Request timed out after 3 minutes. The dataset is very large — try unchecking Bi-directional Geocoding for a fast preview.";
      } else if (errMsg.includes("Failed to fetch") || errMsg.includes("NetworkError")) {
        errMsg = "Could not reach the backend server (http://localhost:8030). Please verify your FastAPI backend is running.";
      }

      if (importInputError) {
        importInputError.style.display = "block";
        importInputError.innerHTML = `<strong>⚠️ Parsing Error:</strong> ${escapeHtml(errMsg)}`;
      }
      showToast(`Parse failed: ${errMsg}`, true);
    } finally {
      clearTimeout(timeoutId);
      stopImportProgress();
      importParseBtn.disabled = false;
      importParseBtn.textContent = "Parse & Review Places →";
      if (importModalCancelBtn) importModalCancelBtn.disabled = false;
      if (importDropzone) importDropzone.style.pointerEvents = "auto";
    }
  });
}

function renderActionFilterBar() {
  const container = document.getElementById("import-action-filter-container");
  const summary = document.getElementById("import-action-filter-summary");
  const bar = document.getElementById("import-action-filter-bar");
  if (!container || !currentImportState.parsedData?.items) return;

  const items = currentImportState.parsedData.items;

  // Count occurrences of each action currently configured
  const actionCounts = {};
  items.forEach((item) => {
    const act = item.action || "CREATE";
    actionCounts[act] = (actionCounts[act] || 0) + 1;
  });

  const preferredOrder = ["CREATE", "ADD_TAGS", "MERGE", "SKIP", "LINK"];
  const foundActions = preferredOrder.filter((act) => (actionCounts[act] || 0) > 0);
  Object.keys(actionCounts).forEach((act) => {
    if (!foundActions.includes(act) && actionCounts[act] > 0) {
      foundActions.push(act);
    }
  });

  container.innerHTML = "";

  if (foundActions.length === 0) {
    if (bar) bar.style.display = "none";
    return;
  }
  if (bar) bar.style.display = "flex";

  foundActions.forEach((act) => {
    const count = actionCounts[act] || 0;
    const isChecked = hiddenImportActions.has(act);
    const labelText = ACTION_FILTER_LABELS[act] || act;

    const label = document.createElement("label");
    label.className = "action-hide-checkbox-label";
    label.style.fontSize = "11px";
    label.style.display = "inline-flex";
    label.style.alignItems = "center";
    label.style.gap = "5px";
    label.style.cursor = "pointer";
    label.style.userSelect = "none";
    label.style.borderRadius = "4px";
    label.style.padding = "3px 8px";
    label.style.transition = "all 0.15s ease";
    label.style.border = isChecked ? "1px solid #fca5a5" : "1px solid var(--border-color)";
    label.style.backgroundColor = isChecked ? "#fee2e2" : "#ffffff";
    label.style.color = isChecked ? "#991b1b" : "var(--text-main)";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "hide-action-checkbox";
    input.value = act;
    input.checked = isChecked;
    input.style.margin = "0";
    input.style.cursor = "pointer";

    input.addEventListener("change", (e) => {
      if (e.target.checked) {
        hiddenImportActions.add(act);
      } else {
        hiddenImportActions.delete(act);
      }
      applyActionFiltersToTable();
      renderActionFilterBar();
    });

    const textSpan = document.createElement("span");
    textSpan.innerHTML = `Hide ${escapeHtml(labelText)} <strong style="${isChecked ? 'color: #991b1b;' : 'color: var(--text-muted);'}">(${count})</strong>`;

    label.appendChild(input);
    label.appendChild(textSpan);
    container.appendChild(label);
  });

  // Calculate visible vs hidden
  const total = items.length;
  let hiddenCount = 0;
  items.forEach((item) => {
    if (hiddenImportActions.has(item.action || "CREATE")) {
      hiddenCount++;
    }
  });
  const visibleCount = total - hiddenCount;

  if (summary) {
    if (hiddenCount > 0) {
      summary.innerHTML = `
        <span>Showing <strong>${visibleCount}</strong> of ${total} (${hiddenCount} hidden)</span>
        <button type="button" id="import-clear-action-filters-btn" class="btn btn-secondary btn-sm" style="font-size: 10px; padding: 1px 6px; margin-left: 6px;">Show All</button>
      `;
      const clearBtn = document.getElementById("import-clear-action-filters-btn");
      if (clearBtn) {
        clearBtn.addEventListener("click", () => {
          hiddenImportActions.clear();
          applyActionFiltersToTable();
          renderActionFilterBar();
        });
      }
    } else {
      summary.innerHTML = `<span>Showing all <strong>${total}</strong> places</span>`;
    }
  }
}

function applyActionFiltersToTable() {
  if (!importPreviewTbody || !currentImportState.parsedData?.items) return;

  const rows = importPreviewTbody.querySelectorAll("tr[data-temp-id]");
  let visibleRows = 0;

  rows.forEach((tr) => {
    const tempId = tr.dataset.tempId;
    const item = currentImportState.parsedData.items.find((i) => i.temp_id === tempId);
    const act = item?.action || "CREATE";
    const isHidden = hiddenImportActions.has(act);

    if (isHidden) {
      tr.style.display = "none";
    } else {
      tr.style.display = "";
      visibleRows++;
    }
  });

  // Empty state if all rows are hidden
  let emptyRow = document.getElementById("import-all-hidden-empty-row");
  if (visibleRows === 0 && rows.length > 0) {
    if (!emptyRow) {
      emptyRow = document.createElement("tr");
      emptyRow.id = "import-all-hidden-empty-row";
      emptyRow.innerHTML = `
        <td colspan="7" class="empty-state" style="padding: 30px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 20px; margin-bottom: 6px;">👁️</div>
          <div style="font-weight: 600; font-size: 13px; color: var(--text-main); margin-bottom: 4px;">All rows are hidden by active action filters</div>
          <div style="font-size: 11.5px; margin-bottom: 10px;">Uncheck one of the "Hide" filters above to view rows.</div>
          <button type="button" class="btn btn-secondary btn-sm" id="import-reset-hide-filters-btn">Show All Rows</button>
        </td>
      `;
      importPreviewTbody.appendChild(emptyRow);
      const resetBtn = document.getElementById("import-reset-hide-filters-btn");
      if (resetBtn) {
        resetBtn.addEventListener("click", () => {
          hiddenImportActions.clear();
          applyActionFiltersToTable();
          renderActionFilterBar();
        });
      }
    }
  } else if (emptyRow) {
    emptyRow.remove();
  }
}

function renderStandardizedPreview(data) {
  if (previewStatTotal) previewStatTotal.textContent = `${data.total_records} Total Places (${data.detected_format.toUpperCase()})`;
  if (previewStatValid) previewStatValid.textContent = `${data.valid_records} Valid`;
  if (previewStatFlagged) previewStatFlagged.textContent = `${data.flagged_records} Flagged Records`;
  if (previewStatConflicts) previewStatConflicts.textContent = `${data.conflict_count} Potential Conflicts`;

  const newListName = importNewListTitle ? importNewListTitle.value.trim() : "";
  const existingListId = importTargetList ? importTargetList.value : "";
  if (previewStatList) {
    if (newListName) {
      const scopeNote = currentImportState.listScope === "new_only" ? "New Only" : "Both New & Matching";
      previewStatList.textContent = `📁 List: ${newListName} (${scopeNote})`;
      previewStatList.style.display = "inline-block";
    } else if (existingListId && typeof availableLists !== "undefined") {
      const matched = availableLists.find((l) => l.id === existingListId);
      const title = matched ? matched.title : "Selected List";
      const scopeNote = currentImportState.listScope === "new_only" ? "New Only" : "Both New & Matching";
      previewStatList.textContent = `📁 List: ${title} (${scopeNote})`;
      previewStatList.style.display = "inline-block";
    } else {
      previewStatList.style.display = "none";
    }
  }

  if (!importPreviewTbody) return;
  importPreviewTbody.innerHTML = "";

  data.items.forEach((item) => {
    const tr = document.createElement("tr");
    tr.dataset.tempId = item.temp_id;
    tr.style.borderBottom = "1px solid var(--border-color)";

    const isConflict = item.collision_status && item.collision_status !== "UNIQUE_LOCATION";
    if (isConflict) {
      tr.style.backgroundColor = "#fff1f2";
    }

    // Quality badges
    let qualityHtml = "";
    if (item.quality?.flags?.includes("missing_name")) {
      qualityHtml += `<span class="quality-pill quality-pill-invalid" title="Site name is missing">🔴 Name</span>`;
    } else if (item.quality?.geocoded_coordinates || item.quality?.geocoded_address) {
      qualityHtml += `<span class="quality-pill quality-pill-geocoded" title="Calculated via bi-directional geocoding">🔄 Geocoded</span>`;
    } else if (item.quality?.has_coordinates && item.quality?.has_address) {
      qualityHtml += `<span class="quality-pill quality-pill-complete" title="Complete Record">🟢 Complete</span>`;
    }

    if (item.quality?.flags?.includes("missing_coordinates") && !item.quality?.geocoded_coordinates) {
      qualityHtml += ` <span class="quality-pill quality-pill-missing-coords" title="Missing Coordinates">🟠 Coords</span>`;
    }
    if (item.quality?.flags?.includes("missing_address") && !item.quality?.geocoded_address) {
      qualityHtml += ` <span class="quality-pill quality-pill-missing-addr" title="Missing Address">🟡 Addr</span>`;
    }

    // Coordinates display
    let coordsDisplay = '<span style="color: var(--text-muted); font-style: italic;">No Coords</span>';
    if (item.latitude != null && item.longitude != null) {
      coordsDisplay = `<code>${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)}</code>`;
      if (item.quality?.geocoded_coordinates) {
        coordsDisplay += ` <span title="Calculated from address" style="font-size: 11px;">🔄</span>`;
      }
    }

    // Location / Address
    const addrParts = [item.iptc_city, item.iptc_province_state, item.iptc_country_code || item.iptc_world_region].filter(Boolean);
    let addrDisplay = addrParts.join(", ") || '<span style="color: var(--text-muted); font-style: italic;">No Address</span>';
    if (item.quality?.geocoded_address) {
      addrDisplay += ` <span title="Reverse geocoded from coordinates" style="font-size: 11px;">🔄</span>`;
    }

    // Tags & Visit Again
    const tagsHtml = (item.category_tags || []).slice(0, 3).map((t) => `<span class="tag-badge ${t.toLowerCase() === 'nps' ? 'tag-nps' : ''}" style="font-size: 10px; margin-right: 2px;">${escapeHtml(t)}</span>`).join("");
    const visitAgainHtml = item.visit_again ? `<span title="Visit Again: Yes" style="font-size: 11px; margin-left: 4px;">🔁</span>` : "";

    // Conflict Match Display
    let matchHtml = '<span style="color: #16a34a; font-weight: 500;">✓ Unique Location</span>';
    if (isConflict && item.matched_poi) {
      matchHtml = `
        <div>
          <span class="conflict-pill-dup">${item.collision_status === 'POTENTIAL_DUPLICATE' ? 'Duplicate Warning' : 'Nearby Parent'}</span>
          <div style="font-size: 11px; font-weight: 600; color: var(--text-main);">${escapeHtml(item.matched_poi.name)}</div>
          <div style="font-size: 10.5px; color: var(--text-muted);">
            ${item.matched_poi.distance_meters > 0 ? `${item.matched_poi.distance_meters}m away` : 'Exact/similar title'} · Sim: ${(item.matched_poi.name_similarity * 100).toFixed(0)}%
          </div>
          ${item.missing_tags && item.missing_tags.length > 0 ? `<div style="font-size: 10px; color: #0284c7; margin-top: 3px; font-weight: 500;">🏷️ Missing Tags: <strong>${escapeHtml(item.missing_tags.join(", "))}</strong></div>` : ''}
        </div>
      `;
    }

    // Action Dropdown
    if (!item.action) {
      item.action = isConflict ? "SKIP" : "CREATE";
    }
    const selectedAction = item.action;
    const addTagsLabel = item.missing_tags && item.missing_tags.length > 0
      ? `Add Tags (+${item.missing_tags.length})`
      : 'Add Tags';
    const selectHtml = `
      <select class="form-select item-action-select" data-temp-id="${item.temp_id}" style="font-size: 11px; padding: 4px 6px; width: 100%; min-width: 145px; box-sizing: border-box;">
        <option value="CREATE" ${selectedAction === 'CREATE' ? 'selected' : ''}>Create as New</option>
        <option value="MERGE" ${selectedAction === 'MERGE' ? 'selected' : ''}>Merge Existing</option>
        ${item.missing_tags && item.missing_tags.length > 0 ? `<option value="ADD_TAGS" ${selectedAction === 'ADD_TAGS' ? 'selected' : ''}>${addTagsLabel}</option>` : ''}
        <option value="SKIP" ${selectedAction === 'SKIP' ? 'selected' : ''}>Skip Record</option>
        <option value="LINK" ${selectedAction === 'LINK' ? 'selected' : ''}>Link as Child</option>
      </select>
    `;

    // Apply active filter state immediately on creation
    if (hiddenImportActions.has(item.action)) {
      tr.style.display = "none";
    }

    tr.innerHTML = `
      <td>${qualityHtml}</td>
      <td>
        <strong style="font-size: 12px; color: var(--text-main);">${escapeHtml(item.name)}</strong>
        ${item.website_official ? `<div style="font-size: 10px; color: var(--text-muted);"><a href="${escapeHtml(item.website_official)}" target="_blank" style="color: var(--primary-color);">Link ↗</a></div>` : ''}
        ${item.source_url ? `<div style="font-size: 10px; color: var(--text-muted);" title="Source File">📄 ${escapeHtml(item.source_url)}</div>` : ''}
      </td>
      <td>${coordsDisplay}</td>
      <td style="font-size: 11px;">${addrDisplay}</td>
      <td>${tagsHtml} ${visitAgainHtml}</td>
      <td>${matchHtml}</td>
      <td style="min-width: 155px; width: 160px;">${selectHtml}</td>
    `;

    importPreviewTbody.appendChild(tr);
  });

  updateImportSortIndicators();
  renderActionFilterBar();
  applyActionFiltersToTable();
}

// Keep in-memory items in sync when user manually selects an action
if (importPreviewTbody) {
  importPreviewTbody.addEventListener("change", (e) => {
    const sel = e.target.closest(".item-action-select");
    if (sel && currentImportState.parsedData?.items) {
      const tempId = sel.dataset.tempId;
      const item = currentImportState.parsedData.items.find((i) => i.temp_id === tempId);
      if (item) {
        item.action = sel.value;
        renderActionFilterBar();
        applyActionFiltersToTable();
      }
    }
  });
}

function syncImportActionSelectsToData() {
  if (!currentImportState.parsedData || !currentImportState.parsedData.items) return;
  document.querySelectorAll(".item-action-select").forEach((sel) => {
    const tempId = sel.dataset.tempId;
    const item = currentImportState.parsedData.items.find((i) => i.temp_id === tempId);
    if (item) {
      item.action = sel.value;
    }
  });
}

function getQualityScore(item) {
  if (item.quality?.flags?.includes("missing_name")) return 0;
  const missingCoords = item.quality?.flags?.includes("missing_coordinates") && !item.quality?.geocoded_coordinates;
  const missingAddr = item.quality?.flags?.includes("missing_address") && !item.quality?.geocoded_address;
  const isGeocoded = Boolean(item.quality?.geocoded_coordinates || item.quality?.geocoded_address);

  if (missingCoords && missingAddr) return 1;
  if (missingCoords) return 2;
  if (missingAddr) return 3;
  if (isGeocoded) return 4;
  return 5; // 5 = Complete
}

function applyImportSort() {
  if (!currentImportState.parsedData || !currentImportState.parsedData.items) return;
  const { column, direction } = currentImportSort;
  if (!column) return;

  const items = currentImportState.parsedData.items;

  items.sort((a, b) => {
    let comp = 0;

    if (column === "quality") {
      const scoreA = getQualityScore(a);
      const scoreB = getQualityScore(b);
      comp = scoreA - scoreB;
    } else if (column === "name") {
      comp = String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base", numeric: true });
    } else if (column === "coordinates") {
      const hasCoordsA = a.latitude != null && a.longitude != null;
      const hasCoordsB = b.latitude != null && b.longitude != null;
      if (hasCoordsA && hasCoordsB) {
        comp = a.latitude - b.latitude || a.longitude - b.longitude;
      } else if (hasCoordsA) {
        comp = -1;
      } else if (hasCoordsB) {
        comp = 1;
      } else {
        comp = 0;
      }
    } else if (column === "location") {
      const locA = [a.iptc_city, a.iptc_province_state, a.iptc_country_code || a.iptc_world_region].filter(Boolean).join(", ");
      const locB = [b.iptc_city, b.iptc_province_state, b.iptc_country_code || b.iptc_world_region].filter(Boolean).join(", ");
      if (locA && locB) {
        comp = locA.localeCompare(locB, undefined, { sensitivity: "base", numeric: true });
      } else if (locA) {
        comp = -1;
      } else if (locB) {
        comp = 1;
      } else {
        comp = 0;
      }
    } else if (column === "tags") {
      const tagsA = (a.category_tags || []).join(", ") + (a.visit_again ? " 1" : " 0");
      const tagsB = (b.category_tags || []).join(", ") + (b.visit_again ? " 1" : " 0");
      comp = tagsA.localeCompare(tagsB, undefined, { sensitivity: "base", numeric: true });
    } else if (column === "collision") {
      const severityMap = { POTENTIAL_DUPLICATE: 3, NEARBY_PARENT: 2, UNIQUE_LOCATION: 1 };
      const sevA = severityMap[a.collision_status] || 0;
      const sevB = severityMap[b.collision_status] || 0;
      comp = sevA - sevB;
      if (comp === 0 && a.matched_poi && b.matched_poi) {
        comp = String(a.matched_poi.name || "").localeCompare(String(b.matched_poi.name || ""), undefined, { sensitivity: "base", numeric: true });
      }
    } else if (column === "action") {
      const isConflictA = a.collision_status && a.collision_status !== "UNIQUE_LOCATION";
      const isConflictB = b.collision_status && b.collision_status !== "UNIQUE_LOCATION";
      const actA = a.action || (isConflictA ? "SKIP" : "CREATE");
      const actB = b.action || (isConflictB ? "SKIP" : "CREATE");
      comp = actA.localeCompare(actB);
    }

    return direction === "asc" ? comp : -comp;
  });

  updateImportSortIndicators();
}

function handleImportHeaderSort(column) {
  if (!column || !currentImportState.parsedData || !currentImportState.parsedData.items) return;

  syncImportActionSelectsToData();

  if (currentImportSort.column === column) {
    currentImportSort.direction = currentImportSort.direction === "asc" ? "desc" : "asc";
  } else {
    currentImportSort.column = column;
    currentImportSort.direction = "asc";
  }

  applyImportSort();
  renderStandardizedPreview(currentImportState.parsedData);
}

function updateImportSortIndicators() {
  document.querySelectorAll(".import-sortable-th").forEach((th) => {
    const col = th.dataset.sort;
    const indicator = th.querySelector(".sort-indicator");
    if (col === currentImportSort.column) {
      th.classList.add("sorted");
      if (indicator) indicator.textContent = currentImportSort.direction === "asc" ? "▲" : "▼";
    } else {
      th.classList.remove("sorted");
      if (indicator) indicator.textContent = "⇅";
    }
  });
}

// Bulk conflict action select
if (previewBulkConflictSelect) {
  previewBulkConflictSelect.addEventListener("change", (e) => {
    const val = e.target.value;
    if (!currentImportState.parsedData) return;

    currentImportState.parsedData.items.forEach((item) => {
      const isConflict = item.collision_status && item.collision_status !== "UNIQUE_LOCATION";
      if (isConflict) {
        if (val === "ADD_TAGS" && (!item.missing_tags || item.missing_tags.length === 0)) {
          item.action = "SKIP";
        } else {
          item.action = val;
        }
        const sel = document.querySelector(`.item-action-select[data-temp-id="${item.temp_id}"]`);
        if (sel) sel.value = item.action;
      }
    });
    renderActionFilterBar();
    applyActionFiltersToTable();
  });
}

// Commit Ingested POIs
if (importCommitBtn) {
  importCommitBtn.addEventListener("click", async () => {
    if (!currentImportState.parsedData || !currentImportState.parsedData.items.length) {
      showToast("No places to import", true);
      return;
    }

    const newListName = importNewListTitle ? importNewListTitle.value.trim() : null;
    const targetListId = newListName ? null : (importTargetList?.value || null);
    const listScope = currentImportState.listScope || "both";

    // Sync selected actions from DOM
    const commitItems = currentImportState.parsedData.items.map((item) => {
      const sel = document.querySelector(`.item-action-select[data-temp-id="${item.temp_id}"]`);
      const action = sel ? sel.value : (item.action || "CREATE");
      return {
        temp_id: item.temp_id,
        action: action,
        poi_data: item,
        matched_poi_id: item.matched_poi ? item.matched_poi.id : null,
        target_list_id: targetListId
      };
    });

    importCommitBtn.disabled = true;
    importCommitBtn.textContent = "Committing to DB...";

    try {
      const res = await apiFetch("/api/v1/pois/ingest/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: commitItems,
          default_tags: currentImportState.appliedTags || [],
          target_list_id: targetListId,
          new_list_title: newListName,
          list_membership_scope: listScope
        })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned ${res.status}`);
      }

      const commitResult = await res.json();

      // Show Step 3
      const successStats = document.getElementById("import-success-stats");
      if (successStats) {
        let statsHtml = `
          <span class="active-badge" style="font-size: 13px; padding: 6px 12px;">✅ ${commitResult.created_count} Created</span>
          <span class="tag-badge" style="font-size: 13px; padding: 6px 12px; background: #ecfdf5; color: #166534;">🔄 ${commitResult.merged_count} Merged</span>
          <span class="tag-badge" style="font-size: 13px; padding: 6px 12px; background: #f1f5f9; color: #64748b;">⏭️ ${commitResult.skipped_count} Skipped</span>
          ${commitResult.linked_count > 0 ? `<span class="tag-badge" style="font-size: 13px; padding: 6px 12px; background: #e0f2fe; color: #0369a1;">🔗 ${commitResult.linked_count} Linked</span>` : ''}
        `;
        if (commitResult.target_list_title) {
          const scopeLabel = listScope === "new_only" ? "New POIs only" : "Both new & matching";
          const countInfo = commitResult.enrolled_count !== undefined ? ` · ${commitResult.enrolled_count} places` : '';
          statsHtml += `<span class="tag-badge" style="font-size: 13px; padding: 6px 12px; background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe;">📁 Enrolled in List: "${escapeHtml(commitResult.target_list_title)}" (${scopeLabel}${countInfo})</span>`;
        }
        successStats.innerHTML = statsHtml;
      }

      showToast(`Successfully imported ${commitResult.created_count + commitResult.merged_count} places!`);
      showImportStep(3);

      // Refresh list in background
      await fetchPois(true);
      if (typeof loadLists === "function") {
        await loadLists();
      }
    } catch (err) {
      showToast(`Failed to commit places: ${err.message}`, true);
    } finally {
      importCommitBtn.disabled = false;
      importCommitBtn.textContent = "Confirm & Import Places";
    }
  });
}

// Done button
if (importDoneBtn) {
  importDoneBtn.addEventListener("click", () => {
    if (importPoisModal) importPoisModal.style.display = "none";
    if (currentImportState.appliedTags && currentImportState.appliedTags.length > 0) {
      const primaryTag = currentImportState.appliedTags[0];
      if (filterTag) {
        filterTag.value = primaryTag;
        fetchPois(true);
      }
    }
  });
}

/* ==========================================================================
   POI MERGE CONTROLLER
   ========================================================================== */

const POI_MERGE_SINGLE_FIELDS = [
  { key: "name", label: "Point of Interest Name", format: v => v || "—" },
  { key: "poi_type", label: "POI Type", format: v => v || "—" },
  { key: "personal_rating", label: "Personal Rating", format: v => (v !== null && v !== undefined && v !== "") ? `${"⭐".repeat(Number(v))} (${v})` : "Not rated" },
  { key: "parent_poi_id", label: "Macro Site", format: (v) => {
    if (!v) return "None";
    const p = allPois.find(x => x.id === v);
    return p ? p.name : `Parent ID: ${v.slice(0, 8)}...`;
  }},
  { key: "description", label: "Description", format: v => v ? (v.length > 80 ? v.slice(0, 80) + "..." : v) : "—" },
  { key: "latitude", label: "Latitude", format: v => (v !== null && v !== undefined && v !== "") ? String(v) : "—" },
  { key: "longitude", label: "Longitude", format: v => (v !== null && v !== undefined && v !== "") ? String(v) : "—" },
  { key: "iptc_sublocation", label: "Street Address / Road", format: v => v || "—" },
  { key: "iptc_zip_code", label: "Postal / ZIP Code", format: v => v || "—" },
  { key: "iptc_city", label: "City / Town", format: v => v || "—" },
  { key: "iptc_province_state", label: "State / Province", format: v => v || "—" },
  { key: "iptc_country_code", label: "Country Code", format: v => v || "—" },
  { key: "physical_effort", label: "Physical Effort", format: v => v || "—" },
  { key: "indoor_outdoor", label: "Environment", format: v => v || "—" },
  { key: "estimated_duration", label: "Estimated Duration", format: v => v || "—" },
  { key: "cost_tier", label: "Cost Tier", format: v => v || "—" },
  { key: "booking_lead_time", label: "Booking Lead Time", format: v => v || "—" },
  { key: "visit_again", label: "Visit Again", format: v => v ? "Yes (Checked)" : "No (Unchecked)" },
  { key: "phone_number", label: "Phone Number", format: v => v || "—" },
  { key: "website_official", label: "Official Website", format: v => v || "—" },
  { key: "source_type", label: "Source Type", format: v => v || "—" },
  { key: "source_url", label: "Source URL", format: v => v || "—" },
];

const POI_MERGE_RADIUS_STEPS = [0, 1, 2, 3, 5, 10, 15, 25, 50, 100];

let poiMergeMasterPois = null;
let poiMergeLoadingMaster = false;

let poiMergePickerState = {
  kept: {
    listId: "",
    tags: [],
    tagMode: "any",
    city: "",
    state: "",
    country: "",
    visitedStatus: "",
    radiusStepIndex: 4, // 5 miles default
  },
  deleted: {
    listId: "",
    tags: [],
    tagMode: "any",
    city: "",
    state: "",
    country: "",
    visitedStatus: "",
    radiusStepIndex: 4, // 5 miles default
  }
};

async function ensurePoiMergeMasterPois() {
  if (poiMergeMasterPois && Array.isArray(poiMergeMasterPois) && poiMergeMasterPois.length > 0) {
    return poiMergeMasterPois;
  }
  if (poiMergeLoadingMaster) {
    let attempts = 0;
    while (poiMergeLoadingMaster && attempts < 25) {
      await new Promise(r => setTimeout(r, 100));
      attempts++;
    }
    if (poiMergeMasterPois && Array.isArray(poiMergeMasterPois) && poiMergeMasterPois.length > 0) {
      return poiMergeMasterPois;
    }
  }
  poiMergeLoadingMaster = true;
  try {
    const res = await apiFetch("/api/v1/pois?limit=5000");
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        poiMergeMasterPois = data;
        return poiMergeMasterPois;
      }
    }
  } catch (err) {
    console.warn("[ensurePoiMergeMasterPois] apiFetch failed, trying GET_POIS message:", err);
  } finally {
    poiMergeLoadingMaster = false;
  }

  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: "GET_POIS", payload: { limit: 5000 } }, (response) => {
      if (response?.success && Array.isArray(response.data)) {
        poiMergeMasterPois = response.data;
        resolve(poiMergeMasterPois);
      } else {
        poiMergeMasterPois = allPois;
        resolve(poiMergeMasterPois);
      }
    });
  });
}

function populatePoiMergeListSelects() {
  ["kept", "deleted"].forEach(role => {
    const select = document.getElementById(`poi-merge-${role}-list-select`);
    if (!select) return;
    const currentVal = poiMergePickerState[role]?.listId || "";
    select.innerHTML = '<option value="">-- All Lists (No List Filter) --</option>';
    if (Array.isArray(availableLists)) {
      availableLists.forEach(lst => {
        const opt = document.createElement("option");
        opt.value = lst.id;
        opt.textContent = `${lst.title}${lst.is_trip ? " 🧳" : ""}`;
        select.appendChild(opt);
      });
    }
    select.value = currentVal;
  });
}

function calculateDistanceMiles(lat1, lon1, lat2, lon2) {
  if (lat1 === null || lat1 === undefined || lon1 === null || lon1 === undefined ||
      lat2 === null || lat2 === undefined || lon2 === null || lon2 === undefined) {
    return null;
  }
  const nLat1 = Number(lat1);
  const nLon1 = Number(lon1);
  const nLat2 = Number(lat2);
  const nLon2 = Number(lon2);
  if (isNaN(nLat1) || isNaN(nLon1) || isNaN(nLat2) || isNaN(nLon2)) return null;
  const R = 3958.8; // Radius of Earth in miles
  const dLat = (nLat2 - nLat1) * Math.PI / 180;
  const dLon = (nLon2 - nLon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(nLat1 * Math.PI / 180) * Math.cos(nLat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function areFieldValuesSame(fieldKey, val1, val2, str1, str2) {
  if (val1 === val2) return true;
  if ((val1 === null || val1 === undefined || val1 === "") &&
      (val2 === null || val2 === undefined || val2 === "")) {
    return true;
  }
  if (fieldKey === "visit_again") {
    return Boolean(val1) === Boolean(val2);
  }
  if (fieldKey === "personal_rating") {
    const r1 = (val1 !== null && val1 !== undefined && val1 !== "") ? Number(val1) : null;
    const r2 = (val2 !== null && val2 !== undefined && val2 !== "") ? Number(val2) : null;
    return r1 === r2;
  }
  if (fieldKey === "latitude" || fieldKey === "longitude") {
    const n1 = (val1 !== null && val1 !== undefined && val1 !== "") ? Number(val1) : null;
    const n2 = (val2 !== null && val2 !== undefined && val2 !== "") ? Number(val2) : null;
    if (n1 === null && n2 === null) return true;
    if (n1 !== null && n2 !== null) return Math.abs(n1 - n2) < 0.000001;
    return false;
  }
  if (str1 && str2 && str1 === str2) return true;
  const s1 = String(val1 ?? "").trim();
  const s2 = String(val2 ?? "").trim();
  return s1 === s2;
}

let poiMergeShowAllFields = false;

function updateSingleFieldsVisibility() {
  const showAllToggle = document.getElementById("poi-merge-show-all-fields-toggle");
  const showAll = showAllToggle ? showAllToggle.checked : poiMergeShowAllFields;
  poiMergeShowAllFields = showAll;

  const rows = document.querySelectorAll("#poi-merge-single-fields-tbody tr.poi-merge-field-row");
  let visibleDiffCount = 0;
  rows.forEach(tr => {
    const isSame = tr.dataset.isSame === "true";
    if (!showAll && isSame) {
      tr.style.display = "none";
    } else {
      tr.style.display = "";
      if (!isSame) visibleDiffCount++;
    }
  });

  const noDiffRow = document.getElementById("poi-merge-no-differences-row");
  if (noDiffRow) {
    noDiffRow.style.display = (!showAll && visibleDiffCount === 0) ? "" : "none";
  }
}

let poiMergeState = {
  keptPoi: null,
  deletedPoi: null,
  keptFolders: [],
  deletedFolders: [],
};

const poiMergeModal = document.getElementById("poi-merge-modal");
const poiMergeConfirmModal = document.getElementById("poi-merge-confirm-modal");
const poiMergeCloseBtn = document.getElementById("poi-merge-close-btn");
const poiMergeCancelBtn = document.getElementById("poi-merge-cancel-btn");
const poiMergeProceedBtn = document.getElementById("poi-merge-proceed-btn");
const poiMergeSwapBtn = document.getElementById("poi-merge-swap-btn");

const poiMergeConfirmCloseBtn = document.getElementById("poi-merge-confirm-close-btn");
const poiMergeConfirmBackBtn = document.getElementById("poi-merge-confirm-back-btn");
const poiMergeConfirmSubmitBtn = document.getElementById("poi-merge-confirm-submit-btn");

async function fetchFullPoi(poiId) {
  if (!poiId) return null;
  try {
    const res = await apiFetch(`/api/v1/pois/${poiId}`);
    if (res.ok) return await res.json();
  } catch (err) {
    console.warn("fetchFullPoi error:", err);
  }
  return allPois.find(p => p.id === poiId) || null;
}

async function fetchPoiFolders(poiId) {
  if (!poiId) return [];
  try {
    const res = await apiFetch(`/api/v1/scanned-paths?poi_id=${poiId}&limit=100&include_hidden=true`);
    if (res.ok) {
      const data = await res.json();
      return data.items || [];
    }
  } catch (err) {
    console.warn("fetchPoiFolders error:", err);
  }
  return [];
}

async function openPoiMergeModal({ role, poi }) {
  if (!poi) return;
  if (role === "keep") {
    poiMergeState.keptPoi = poi;
    poiMergeState.deletedPoi = null;
  } else {
    poiMergeState.keptPoi = null;
    poiMergeState.deletedPoi = poi;
  }
  poiMergeState.keptFolders = [];
  poiMergeState.deletedFolders = [];

  // Initialize picker filters from parent page filters as starting point
  const parentListId = filterList?.value || "";
  const parentTag = filterTag?.value ? filterTag.value.trim() : "";
  const parentCity = filterCity?.value ? filterCity.value.trim() : "";
  const parentState = filterState?.value ? filterState.value.trim() : "";
  const parentCountry = filterCountry?.value ? filterCountry.value.trim() : "";
  const parentVisited = filterVisitedStatus?.value || "";
  const parentSearch = keywordSearch?.value ? keywordSearch.value.trim() : "";

  ["kept", "deleted"].forEach(r => {
    poiMergePickerState[r].listId = parentListId;
    poiMergePickerState[r].tags = parentTag ? [parentTag] : [];
    poiMergePickerState[r].tagMode = "any";
    poiMergePickerState[r].city = parentCity;
    poiMergePickerState[r].state = parentState;
    poiMergePickerState[r].country = parentCountry;
    poiMergePickerState[r].visitedStatus = parentVisited;
    poiMergePickerState[r].radiusStepIndex = 4;
  });

  poiMergeShowAllFields = false;
  const showAllToggle = document.getElementById("poi-merge-show-all-fields-toggle");
  if (showAllToggle) showAllToggle.checked = false;

  populatePoiMergeListSelects();

  ["kept", "deleted"].forEach(r => {
    const listSel = document.getElementById(`poi-merge-${r}-list-select`);
    if (listSel) listSel.value = parentListId;

    const cityInp = document.getElementById(`poi-merge-${r}-city-input`);
    if (cityInp) cityInp.value = parentCity;

    const stateInp = document.getElementById(`poi-merge-${r}-state-input`);
    if (stateInp) stateInp.value = parentState;

    const countryInp = document.getElementById(`poi-merge-${r}-country-input`);
    if (countryInp) countryInp.value = parentCountry;

    const visitedSel = document.getElementById(`poi-merge-${r}-visited-status`);
    if (visitedSel) visitedSel.value = parentVisited;

    const searchInp = document.getElementById(`poi-merge-${r}-search-input`);
    if (searchInp) searchInp.value = parentSearch;

    const slider = document.getElementById(`poi-merge-${r}-radius-slider`);
    if (slider) slider.value = "4";

    const tagMode = document.getElementById(`poi-merge-${r}-tag-mode`);
    if (tagMode) tagMode.value = "any";

    const tagInp = document.getElementById(`poi-merge-${r}-tag-input`);
    if (tagInp) tagInp.value = "";

    renderPoiMergeSelectedTags(r);
  });

  if (typeof populatePoiMergeTagsDatalist === "function") {
    populatePoiMergeTagsDatalist();
  }

  if (poiMergeModal) poiMergeModal.style.display = "flex";
  await refreshPoiMergeUi();

  // Prefetch full master POI pool so search is not limited by parent page filters
  ensurePoiMergeMasterPois().then(() => {
    populatePoiMergeTagsDatalist();
    populatePoiMergeListSelects();
    const activeRole = !poiMergeState.keptPoi ? "kept" : (!poiMergeState.deletedPoi ? "deleted" : null);
    if (activeRole) {
      const searchInp = document.getElementById(`poi-merge-${activeRole}-search-input`);
      renderPoiMergeDropdown(activeRole, searchInp ? searchInp.value : "");
    }
  });
}

function closePoiMergeModal() {
  if (poiMergeModal) poiMergeModal.style.display = "none";
  poiMergeState.keptPoi = null;
  poiMergeState.deletedPoi = null;
  poiMergeState.keptFolders = [];
  poiMergeState.deletedFolders = [];
}

function closePoiMergeConfirmModal() {
  if (poiMergeConfirmModal) poiMergeConfirmModal.style.display = "none";
}

async function refreshPoiMergeUi() {
  const kept = poiMergeState.keptPoi;
  const deleted = poiMergeState.deletedPoi;

  // 1. Render Kept Card
  const keptInfo = document.getElementById("poi-merge-kept-info");
  const keptPicker = document.getElementById("poi-merge-kept-picker");
  const keptTypeBadge = document.getElementById("poi-merge-kept-type-badge");
  const keptChangeBtn = document.getElementById("poi-merge-kept-change-btn");

  if (kept) {
    if (keptInfo) keptInfo.style.display = "block";
    if (keptPicker) keptPicker.style.display = "none";
    if (keptTypeBadge) {
      keptTypeBadge.style.display = "inline-block";
      keptTypeBadge.textContent = kept.poi_type || "place";
    }
    const nameEl = document.getElementById("poi-merge-kept-name");
    if (nameEl) nameEl.textContent = kept.name || "Untitled Place";
    const locEl = document.getElementById("poi-merge-kept-loc");
    if (locEl) locEl.textContent = [kept.iptc_city, kept.iptc_province_state, kept.iptc_country_code].filter(Boolean).join(", ") || "No location";
    const idEl = document.getElementById("poi-merge-kept-id");
    if (idEl) idEl.textContent = `ID: ${kept.id}`;
    if (keptChangeBtn) keptChangeBtn.textContent = "Change Place";
  } else {
    if (keptInfo) keptInfo.style.display = "none";
    if (keptPicker) keptPicker.style.display = "block";
    if (keptTypeBadge) keptTypeBadge.style.display = "none";
    if (keptChangeBtn) keptChangeBtn.textContent = "Browse Places";
    populatePoiMergeTagsDatalist();
    populatePoiMergeListSelects();
    renderPoiMergeSelectedTags("kept");
    const searchInp = document.getElementById("poi-merge-kept-search-input");
    renderPoiMergeDropdown("kept", searchInp ? searchInp.value : "");
  }

  // 2. Render Deleted Card
  const deletedInfo = document.getElementById("poi-merge-deleted-info");
  const deletedPicker = document.getElementById("poi-merge-deleted-picker");
  const deletedTypeBadge = document.getElementById("poi-merge-deleted-type-badge");
  const deletedChangeBtn = document.getElementById("poi-merge-deleted-change-btn");

  if (deleted) {
    if (deletedInfo) deletedInfo.style.display = "block";
    if (deletedPicker) deletedPicker.style.display = "none";
    if (deletedTypeBadge) {
      deletedTypeBadge.style.display = "inline-block";
      deletedTypeBadge.textContent = deleted.poi_type || "place";
    }
    const nameEl = document.getElementById("poi-merge-deleted-name");
    if (nameEl) nameEl.textContent = deleted.name || "Untitled Place";
    const locEl = document.getElementById("poi-merge-deleted-loc");
    if (locEl) locEl.textContent = [deleted.iptc_city, deleted.iptc_province_state, deleted.iptc_country_code].filter(Boolean).join(", ") || "No location";
    const idEl = document.getElementById("poi-merge-deleted-id");
    if (idEl) idEl.textContent = `ID: ${deleted.id}`;
    if (deletedChangeBtn) deletedChangeBtn.textContent = "Change Place";
  } else {
    if (deletedInfo) deletedInfo.style.display = "none";
    if (deletedPicker) deletedPicker.style.display = "block";
    if (deletedTypeBadge) deletedTypeBadge.style.display = "none";
    if (deletedChangeBtn) deletedChangeBtn.textContent = "Browse Places";
    populatePoiMergeTagsDatalist();
    populatePoiMergeListSelects();
    renderPoiMergeSelectedTags("deleted");
    const searchInp = document.getElementById("poi-merge-deleted-search-input");
    renderPoiMergeDropdown("deleted", searchInp ? searchInp.value : "");
  }

  const alertBox = document.getElementById("poi-merge-empty-partner-alert");
  const compBox = document.getElementById("poi-merge-comparison-container");

  if (!kept || !deleted) {
    if (alertBox) alertBox.style.display = "block";
    if (compBox) compBox.style.display = "none";
    if (poiMergeProceedBtn) poiMergeProceedBtn.disabled = true;
    return;
  }

  // Both POIs selected
  if (alertBox) alertBox.style.display = "none";
  if (compBox) compBox.style.display = "block";
  if (poiMergeProceedBtn) poiMergeProceedBtn.disabled = false;

  // Load complete details if needed
  if (!kept.visit_dates || !kept.category_tags) {
    poiMergeState.keptPoi = await fetchFullPoi(kept.id);
  }
  if (!deleted.visit_dates || !deleted.category_tags) {
    poiMergeState.deletedPoi = await fetchFullPoi(deleted.id);
  }
  poiMergeState.keptFolders = await fetchPoiFolders(kept.id);
  poiMergeState.deletedFolders = await fetchPoiFolders(deleted.id);

  renderPoiMergeComparisons();
}

function renderPoiMergeComparisons() {
  const kept = poiMergeState.keptPoi;
  const deleted = poiMergeState.deletedPoi;
  if (!kept || !deleted) return;

  // 1. Single fields table
  const tbody = document.getElementById("poi-merge-single-fields-tbody");
  if (tbody) {
    tbody.innerHTML = "";
    POI_MERGE_SINGLE_FIELDS.forEach(field => {
      const keptVal = kept[field.key];
      const deletedVal = deleted[field.key];
      const keptStr = field.format(keptVal, kept);
      const deletedStr = field.format(deletedVal, deleted);
      const isSame = areFieldValuesSame(field.key, keptVal, deletedVal, keptStr, deletedStr);

      const tr = document.createElement("tr");
      tr.className = `poi-merge-field-row ${isSame ? 'poi-merge-field-same' : 'poi-merge-field-diff'}`;
      tr.dataset.isSame = isSame ? "true" : "false";

      const badge = isSame
        ? '<span style="font-size: 10px; font-weight: 600; color: #15803d; background: #dcfce7; border: 1px solid #86efac; border-radius: 4px; padding: 1px 5px; margin-left: 6px;">Same</span>'
        : '<span style="font-size: 10px; font-weight: 600; color: #b45309; background: #fef3c7; border: 1px solid #fde68a; border-radius: 4px; padding: 1px 5px; margin-left: 6px;">Differs</span>';

      tr.innerHTML = `
        <td style="font-weight: 600; color: #334155; vertical-align: middle;">
          ${escapeHtml(field.label)}
          ${badge}
        </td>
        <td class="poi-merge-val-cell poi-merge-val-kept" style="vertical-align: middle;">
          <label class="poi-merge-radio-label">
            <input type="radio" name="merge_single_${field.key}" value="keep" checked>
            <div style="word-break: break-word; font-weight: ${isSame ? '600' : '500'};">
              ${escapeHtml(keptStr)}
            </div>
          </label>
        </td>
        <td class="poi-merge-val-cell poi-merge-val-deleted" style="vertical-align: middle;">
          <label class="poi-merge-radio-label">
            <input type="radio" name="merge_single_${field.key}" value="delete">
            <div style="word-break: break-word; font-weight: ${isSame ? '600' : 'normal'};">
              ${escapeHtml(deletedStr)}
            </div>
          </label>
        </td>
      `;
      tbody.appendChild(tr);
    });

    const noDiffRow = document.createElement("tr");
    noDiffRow.id = "poi-merge-no-differences-row";
    noDiffRow.style.display = "none";
    noDiffRow.innerHTML = `
      <td colspan="3" style="text-align: center; padding: 18px; color: #166534; background: #f0fdf4; font-size: 12.5px; font-weight: 500;">
        ✓ All single value attributes are identical between both places.<br>
        <span style="font-size: 11px; color: #475569; font-weight: normal;">Enable <strong>&ldquo;Show all fields&rdquo;</strong> above to view or change them.</span>
      </td>
    `;
    tbody.appendChild(noDiffRow);

    updateSingleFieldsVisibility();
  }

  // 2. Dates Visited (Multi)
  const datesListEl = document.getElementById("poi-merge-dates-list");
  const datesCountEl = document.getElementById("poi-merge-dates-count");
  if (datesListEl) {
    datesListEl.innerHTML = "";
    const keptDates = (kept.visit_dates || []).map(d => String(d).slice(0, 10));
    if (kept.visit_date) keptDates.push(String(kept.visit_date).slice(0, 10));
    const deletedDates = (deleted.visit_dates || []).map(d => String(d).slice(0, 10));
    if (deleted.visit_date) deletedDates.push(String(deleted.visit_date).slice(0, 10));
    const allDates = Array.from(new Set([...keptDates, ...deletedDates])).filter(Boolean).sort();

    if (datesCountEl) datesCountEl.textContent = `${allDates.length} date${allDates.length === 1 ? '' : 's'}`;

    if (allDates.length === 0) {
      datesListEl.innerHTML = '<span style="font-size: 11.5px; color: var(--text-muted); font-style: italic;">No visit dates recorded</span>';
    } else {
      allDates.forEach(dt => {
        const inKept = keptDates.includes(dt);
        const inDeleted = deletedDates.includes(dt);
        let badgeClass = "poi-merge-badge-source-both";
        let badgeText = "Both";
        if (inKept && !inDeleted) {
          badgeClass = "poi-merge-badge-source-kept";
          badgeText = "From Kept";
        } else if (!inKept && inDeleted) {
          badgeClass = "poi-merge-badge-source-deleted";
          badgeText = "From Deleted";
        }

        const label = document.createElement("label");
        label.style.display = "flex";
        label.style.alignItems = "center";
        label.style.gap = "6px";
        label.style.fontSize = "12px";
        label.style.cursor = "pointer";
        label.innerHTML = `
          <input type="checkbox" name="merge_visit_date" value="${escapeHtml(dt)}" checked>
          <span>${escapeHtml(dt)}</span>
          <span class="poi-merge-badge-source ${badgeClass}">${badgeText}</span>
        `;
        datesListEl.appendChild(label);
      });
    }
  }

  // 3. List Memberships (Multi)
  const listsListEl = document.getElementById("poi-merge-lists-list");
  const listsCountEl = document.getElementById("poi-merge-lists-count");
  if (listsListEl) {
    listsListEl.innerHTML = "";
    const keptListIds = kept.list_ids || [];
    const deletedListIds = deleted.list_ids || [];
    const allListIds = Array.from(new Set([...keptListIds, ...deletedListIds]));

    if (listsCountEl) listsCountEl.textContent = `${allListIds.length} list${allListIds.length === 1 ? '' : 's'}`;

    if (allListIds.length === 0) {
      listsListEl.innerHTML = '<span style="font-size: 11.5px; color: var(--text-muted); font-style: italic;">No list memberships</span>';
    } else {
      allListIds.forEach(lid => {
        const lst = availableLists.find(l => l.id === lid);
        const title = lst ? `${lst.title} ${lst.is_trip ? "✈️" : "📁"}` : `List ${lid.slice(0, 8)}...`;
        const inKept = keptListIds.includes(lid);
        const inDeleted = deletedListIds.includes(lid);
        let badgeClass = "poi-merge-badge-source-both";
        let badgeText = "Both";
        if (inKept && !inDeleted) {
          badgeClass = "poi-merge-badge-source-kept";
          badgeText = "From Kept";
        } else if (!inKept && inDeleted) {
          badgeClass = "poi-merge-badge-source-deleted";
          badgeText = "From Deleted";
        }

        const label = document.createElement("label");
        label.style.display = "flex";
        label.style.alignItems = "center";
        label.style.gap = "6px";
        label.style.fontSize = "12px";
        label.style.cursor = "pointer";
        label.innerHTML = `
          <input type="checkbox" name="merge_list_id" value="${escapeHtml(lid)}" checked>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(title)}</span>
          <span class="poi-merge-badge-source ${badgeClass}">${badgeText}</span>
        `;
        listsListEl.appendChild(label);
      });
    }
  }

  // 4. Associated Scanned Folders (Multi)
  const pathsListEl = document.getElementById("poi-merge-paths-list");
  const pathsCountEl = document.getElementById("poi-merge-paths-count");
  if (pathsListEl) {
    pathsListEl.innerHTML = "";
    const allPathsMap = new Map();
    (poiMergeState.keptFolders || []).forEach(f => {
      allPathsMap.set(f.id, { folder: f, origin: "kept" });
    });
    (poiMergeState.deletedFolders || []).forEach(f => {
      if (allPathsMap.has(f.id)) {
        allPathsMap.get(f.id).origin = "both";
      } else {
        allPathsMap.set(f.id, { folder: f, origin: "deleted" });
      }
    });

    const folderEntries = Array.from(allPathsMap.values());
    if (pathsCountEl) pathsCountEl.textContent = `${folderEntries.length} folder${folderEntries.length === 1 ? '' : 's'}`;

    if (folderEntries.length === 0) {
      pathsListEl.innerHTML = '<span style="font-size: 11.5px; color: var(--text-muted); font-style: italic;">No associated photo folders</span>';
    } else {
      folderEntries.forEach(entry => {
        const f = entry.folder;
        let badgeClass = "poi-merge-badge-source-both";
        let badgeText = "Both";
        if (entry.origin === "kept") {
          badgeClass = "poi-merge-badge-source-kept";
          badgeText = "From Kept";
        } else if (entry.origin === "deleted") {
          badgeClass = "poi-merge-badge-source-deleted";
          badgeText = "From Deleted";
        }

        const label = document.createElement("label");
        label.style.display = "flex";
        label.style.alignItems = "flex-start";
        label.style.gap = "6px";
        label.style.fontSize = "11.5px";
        label.style.cursor = "pointer";
        label.innerHTML = `
          <input type="checkbox" name="merge_scanned_path" value="${escapeHtml(f.id)}" checked style="margin-top: 2px;">
          <div style="flex: 1; min-width: 0;">
            <div style="font-weight: 600; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              ${escapeHtml(f.folder_name || f.folder_path)}
              <span class="poi-merge-badge-source ${badgeClass}">${badgeText}</span>
            </div>
            <div style="font-size: 10.5px; color: #64748b; font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              ${escapeHtml(f.folder_path)}
            </div>
          </div>
        `;
        pathsListEl.appendChild(label);
      });
    }
  }

  // 5. Category Tags (Multi)
  const tagsListEl = document.getElementById("poi-merge-tags-list");
  const tagsCountEl = document.getElementById("poi-merge-tags-count");
  if (tagsListEl) {
    tagsListEl.innerHTML = "";
    const keptTags = kept.category_tags || [];
    const deletedTags = deleted.category_tags || [];
    const allTags = Array.from(new Set([...keptTags, ...deletedTags])).filter(Boolean);

    if (tagsCountEl) tagsCountEl.textContent = `${allTags.length} tag${allTags.length === 1 ? '' : 's'}`;

    if (allTags.length === 0) {
      tagsListEl.innerHTML = '<span style="font-size: 11.5px; color: var(--text-muted); font-style: italic;">No tags</span>';
    } else {
      allTags.forEach(tg => {
        const inKept = keptTags.includes(tg);
        const inDeleted = deletedTags.includes(tg);
        let badgeClass = "poi-merge-badge-source-both";
        let badgeText = "Both";
        if (inKept && !inDeleted) {
          badgeClass = "poi-merge-badge-source-kept";
          badgeText = "From Kept";
        } else if (!inKept && inDeleted) {
          badgeClass = "poi-merge-badge-source-deleted";
          badgeText = "From Deleted";
        }

        const label = document.createElement("label");
        label.style.display = "flex";
        label.style.alignItems = "center";
        label.style.gap = "6px";
        label.style.fontSize = "12px";
        label.style.cursor = "pointer";
        label.innerHTML = `
          <input type="checkbox" name="merge_tag" value="${escapeHtml(tg)}" checked>
          <span style="font-weight: 500; flex: 1;">${escapeHtml(tg)}</span>
          <span class="poi-merge-badge-source ${badgeClass}">${badgeText}</span>
        `;
        tagsListEl.appendChild(label);
      });
    }
  }
}

function populatePoiMergeTagsDatalist() {
  const datalist = document.getElementById("poi-merge-all-tags-datalist");
  if (!datalist) return;
  const tagSet = new Set();
  if (Array.isArray(availableTags)) {
    availableTags.forEach(t => {
      if (t) tagSet.add(String(t).trim());
    });
  }
  const pool = (poiMergeMasterPois && poiMergeMasterPois.length > 0) ? poiMergeMasterPois : allPois;
  if (Array.isArray(pool)) {
    pool.forEach(p => {
      if (Array.isArray(p.category_tags)) {
        p.category_tags.forEach(t => {
          if (t) tagSet.add(String(t).trim());
        });
      } else if (typeof p.category_tags === "string" && p.category_tags) {
        p.category_tags.split(",").forEach(t => {
          const trimmed = t.trim();
          if (trimmed) tagSet.add(trimmed);
        });
      }
    });
  }
  const sortedTags = Array.from(tagSet).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  datalist.innerHTML = sortedTags.map(tag => `<option value="${escapeHtml(tag)}"></option>`).join("");
}

function renderPoiMergeSelectedTags(role) {
  const container = document.getElementById(`poi-merge-${role}-selected-tags`);
  if (!container) return;
  container.innerHTML = "";
  const tags = poiMergePickerState[role]?.tags || [];
  tags.forEach((tag, idx) => {
    const chip = document.createElement("span");
    chip.className = "poi-merge-tag-chip";
    chip.innerHTML = `
      <span>${escapeHtml(tag)}</span>
      <span class="poi-merge-tag-chip-remove" title="Remove tag">&times;</span>
    `;
    const removeBtn = chip.querySelector(".poi-merge-tag-chip-remove");
    if (removeBtn) {
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        poiMergePickerState[role].tags.splice(idx, 1);
        renderPoiMergeSelectedTags(role);
        const searchInput = document.getElementById(`poi-merge-${role}-search-input`);
        renderPoiMergeDropdown(role, searchInput ? searchInput.value : "");
      });
    }
    container.appendChild(chip);
  });
}

function renderPoiMergeDropdown(role, term = "") {
  const dropdown = document.getElementById(`poi-merge-${role}-dropdown`);
  if (!dropdown) return;

  const searchInput = document.getElementById(`poi-merge-${role}-search-input`);
  const effectiveTerm = term !== undefined && term !== null && term !== "" ? term : (searchInput ? searchInput.value : "");
  const query = effectiveTerm.toLowerCase().trim();
  const otherPoi = role === "kept" ? poiMergeState.deletedPoi : poiMergeState.keptPoi;
  const radiusStepIndex = poiMergePickerState[role]?.radiusStepIndex ?? 4;
  const radiusMiles = POI_MERGE_RADIUS_STEPS[radiusStepIndex] ?? 5;

  // Update radius label and helper note
  const radiusDisplay = document.getElementById(`poi-merge-${role}-radius-display`);
  const radiusNote = document.getElementById(`poi-merge-${role}-radius-note`);
  if (radiusDisplay) {
    if (radiusMiles === 0) {
      radiusDisplay.textContent = "Disabled";
      radiusDisplay.style.color = "#94a3b8";
    } else {
      radiusDisplay.textContent = radiusMiles === 1 ? "1 mile" : `${radiusMiles} miles`;
      radiusDisplay.style.color = role === "kept" ? "#16a34a" : "#dc2626";
    }
  }

  const hasRefCoords = Boolean(
    otherPoi &&
    otherPoi.latitude !== null && otherPoi.latitude !== undefined &&
    otherPoi.longitude !== null && otherPoi.longitude !== undefined &&
    !isNaN(Number(otherPoi.latitude)) && !isNaN(Number(otherPoi.longitude))
  );

  if (radiusNote) {
    if (radiusMiles === 0) {
      radiusNote.textContent = "Distance limit disabled. Searching anywhere.";
      radiusNote.style.display = "block";
    } else if (!otherPoi) {
      radiusNote.textContent = "Select other place to filter by distance.";
      radiusNote.style.display = "block";
    } else if (!hasRefCoords) {
      radiusNote.textContent = `"${otherPoi.name || "Other place"}" has no coordinates; distance filter inactive.`;
      radiusNote.style.display = "block";
    } else {
      radiusNote.textContent = `Within ${radiusMiles} mi of "${otherPoi.name || "other place"}".`;
      radiusNote.style.display = "block";
    }
  }

  const listId = poiMergePickerState[role]?.listId || "";
  const selectedTags = (poiMergePickerState[role]?.tags || []).map(t => t.toLowerCase().trim()).filter(Boolean);
  const tagMode = poiMergePickerState[role]?.tagMode || "any";
  const cityFilter = (poiMergePickerState[role]?.city || "").toLowerCase().trim();
  const stateFilter = (poiMergePickerState[role]?.state || "").toLowerCase().trim();
  const countryFilter = (poiMergePickerState[role]?.country || "").toLowerCase().trim();
  const visitedStatus = poiMergePickerState[role]?.visitedStatus || "";

  // Use full master POI pool if available; otherwise fall back to allPois
  const pool = (poiMergeMasterPois && poiMergeMasterPois.length > 0) ? poiMergeMasterPois : allPois;

  const candidates = [];
  for (const p of pool) {
    if (otherPoi && p.id === otherPoi.id) continue;

    // 1. Text search filter
    if (query) {
      const name = (p.name || "").toLowerCase();
      const city = (p.iptc_city || "").toLowerCase();
      const state = (p.iptc_province_state || "").toLowerCase();
      const country = (p.iptc_country_code || "").toLowerCase();
      const subloc = (p.iptc_sublocation || "").toLowerCase();
      const type = (p.poi_type || "").toLowerCase();
      if (!name.includes(query) && !city.includes(query) && !state.includes(query) && !country.includes(query) && !subloc.includes(query) && !type.includes(query)) {
        continue;
      }
    }

    // 2. Travel List filter
    if (listId) {
      const pListIds = (p.list_ids || []).map(String);
      if (!pListIds.includes(String(listId))) {
        continue;
      }
    }

    // 3. Category Tags filter
    if (selectedTags.length > 0) {
      let pTags = [];
      if (Array.isArray(p.category_tags)) {
        pTags = p.category_tags.map(t => String(t).toLowerCase().trim());
      } else if (typeof p.category_tags === "string" && p.category_tags) {
        pTags = p.category_tags.split(",").map(t => t.toLowerCase().trim());
      }
      if (tagMode === "all") {
        const matchAll = selectedTags.every(st => pTags.includes(st));
        if (!matchAll) continue;
      } else {
        const matchAny = selectedTags.some(st => pTags.includes(st));
        if (!matchAny) continue;
      }
    }

    // 4. City filter
    if (cityFilter) {
      const c = (p.iptc_city || "").toLowerCase();
      if (!c.includes(cityFilter)) continue;
    }

    // 5. State filter
    if (stateFilter) {
      const s = (p.iptc_province_state || "").toLowerCase();
      if (!s.includes(stateFilter)) continue;
    }

    // 6. Country filter
    if (countryFilter) {
      const c = (p.iptc_country_code || "").toLowerCase();
      if (!c.includes(countryFilter)) continue;
    }

    // 7. Visited status filter
    if (visitedStatus) {
      const hasDate = Boolean(p.visit_date || (Array.isArray(p.visit_dates) && p.visit_dates.length > 0));
      if (visitedStatus === "visited" && !hasDate) continue;
      if (visitedStatus === "not_visited" && hasDate) continue;
      if (visitedStatus === "to_see" && (hasDate && !p.visit_again)) continue;
    }

    // 8. Distance calculation & Radius filter
    let dist = null;
    if (hasRefCoords) {
      dist = calculateDistanceMiles(otherPoi.latitude, otherPoi.longitude, p.latitude, p.longitude);
    }
    if (radiusMiles > 0 && hasRefCoords) {
      if (dist === null || dist > radiusMiles) {
        continue;
      }
    }

    candidates.push({ poi: p, distance: dist });
  }

  // Sorting: closest first if distance active, else alphabetical by name
  if (hasRefCoords && radiusMiles > 0) {
    candidates.sort((a, b) => {
      if (a.distance === null && b.distance === null) return (a.poi.name || "").localeCompare(b.poi.name || "");
      if (a.distance === null) return 1;
      if (b.distance === null) return -1;
      return a.distance - b.distance;
    });
  } else {
    candidates.sort((a, b) => {
      if (a.distance !== null && b.distance !== null) return a.distance - b.distance;
      return (a.poi.name || "").localeCompare(b.poi.name || "");
    });
  }

  const limitedCandidates = candidates.slice(0, 50);

  dropdown.innerHTML = "";
  if (limitedCandidates.length === 0) {
    dropdown.innerHTML = `
      <div style="padding: 12px; font-size: 12px; color: var(--text-muted); text-align: center; line-height: 1.5;">
        No matching places found within filter criteria.<br>
        <span style="font-size: 11px; color: #64748b;">(Tip: Try switching Travel List to "-- All Lists --", increasing radius, or clicking "🔄 Reset Filters")</span>
      </div>
    `;
    dropdown.style.display = "block";
    return;
  }

  limitedCandidates.forEach(({ poi: cand, distance }) => {
    const item = document.createElement("div");
    item.className = "poi-merge-dropdown-item";
    const locStr = [cand.iptc_city, cand.iptc_province_state, cand.iptc_country_code].filter(Boolean).join(", ");
    const distBadge = (distance !== null)
      ? `<span style="font-size: 10.5px; font-weight: 600; color: #15803d; background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 4px; padding: 1px 5px; margin-left: 6px;">📍 ${distance < 0.1 ? "<0.1" : distance.toFixed(1)} mi</span>`
      : "";

    let listBadge = "";
    if (Array.isArray(cand.list_ids) && cand.list_ids.length > 0 && Array.isArray(availableLists)) {
      const matchLists = availableLists.filter(l => cand.list_ids.map(String).includes(String(l.id)));
      if (matchLists.length > 0) {
        listBadge = `<span style="font-size: 10px; color: #1e40af; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 3px; padding: 0 4px; margin-left: 4px;">📁 ${escapeHtml(matchLists[0].title)}${matchLists.length > 1 ? ` +${matchLists.length - 1}` : ''}</span>`;
      }
    }

    const tagsBadge = Array.isArray(cand.category_tags) && cand.category_tags.length > 0
      ? `<span style="font-size: 10px; color: #64748b; margin-left: 4px;">[${cand.category_tags.slice(0, 2).map(escapeHtml).join(", ")}${cand.category_tags.length > 2 ? "…" : ""}]</span>`
      : "";

    item.innerHTML = `
      <div style="flex: 1; min-width: 0;">
        <div style="font-weight: 600; color: #0f172a; display: flex; align-items: center; flex-wrap: wrap;">
          <span>${escapeHtml(cand.name)}</span>
          ${distBadge}
          ${listBadge}
        </div>
        <div style="font-size: 11px; color: #64748b; margin-top: 1px;">
          ${escapeHtml(locStr || "No address")} &bull; <span style="font-style: italic;">${escapeHtml(cand.poi_type || "place")}</span>
          ${tagsBadge}
        </div>
      </div>
      <button type="button" class="btn btn-xs ${role === "kept" ? "btn-primary" : "btn-danger"}" style="padding: 2px 8px; font-size: 11px; margin-left: 8px; white-space: nowrap;">Select</button>
    `;
    item.onclick = async (e) => {
      e.stopPropagation();
      if (role === "kept") {
        poiMergeState.keptPoi = cand;
      } else {
        poiMergeState.deletedPoi = cand;
      }
      dropdown.style.display = "none";
      await refreshPoiMergeUi();
    };
    dropdown.appendChild(item);
  });
  dropdown.style.display = "block";
}

function setupPoiMergePickers() {
  ["kept", "deleted"].forEach(role => {
    const input = document.getElementById(`poi-merge-${role}-search-input`);
    const dropdown = document.getElementById(`poi-merge-${role}-dropdown`);
    const changeBtn = document.getElementById(`poi-merge-${role}-change-btn`);
    const picker = document.getElementById(`poi-merge-${role}-picker`);
    const info = document.getElementById(`poi-merge-${role}-info`);
    const listSelect = document.getElementById(`poi-merge-${role}-list-select`);
    const cityInput = document.getElementById(`poi-merge-${role}-city-input`);
    const stateInput = document.getElementById(`poi-merge-${role}-state-input`);
    const countryInput = document.getElementById(`poi-merge-${role}-country-input`);
    const visitedStatusSelect = document.getElementById(`poi-merge-${role}-visited-status`);
    const resetBtn = document.getElementById(`poi-merge-${role}-reset-filters-btn`);
    const tagInput = document.getElementById(`poi-merge-${role}-tag-input`);
    const addTagBtn = document.getElementById(`poi-merge-${role}-add-tag-btn`);
    const tagModeSelect = document.getElementById(`poi-merge-${role}-tag-mode`);
    const slider = document.getElementById(`poi-merge-${role}-radius-slider`);

    if (input) {
      input.addEventListener("input", () => {
        renderPoiMergeDropdown(role, input.value);
      });
      input.addEventListener("focus", () => {
        renderPoiMergeDropdown(role, input.value);
      });
    }

    if (listSelect) {
      listSelect.addEventListener("change", () => {
        poiMergePickerState[role].listId = listSelect.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (cityInput) {
      cityInput.addEventListener("input", () => {
        poiMergePickerState[role].city = cityInput.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (stateInput) {
      stateInput.addEventListener("input", () => {
        poiMergePickerState[role].state = stateInput.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (countryInput) {
      countryInput.addEventListener("input", () => {
        poiMergePickerState[role].country = countryInput.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (visitedStatusSelect) {
      visitedStatusSelect.addEventListener("change", () => {
        poiMergePickerState[role].visitedStatus = visitedStatusSelect.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        poiMergePickerState[role].listId = "";
        poiMergePickerState[role].tags = [];
        poiMergePickerState[role].city = "";
        poiMergePickerState[role].state = "";
        poiMergePickerState[role].country = "";
        poiMergePickerState[role].visitedStatus = "";
        poiMergePickerState[role].radiusStepIndex = 0; // Disabled
        if (listSelect) listSelect.value = "";
        if (cityInput) cityInput.value = "";
        if (stateInput) stateInput.value = "";
        if (countryInput) countryInput.value = "";
        if (visitedStatusSelect) visitedStatusSelect.value = "";
        if (input) input.value = "";
        if (slider) slider.value = "0";
        renderPoiMergeSelectedTags(role);
        renderPoiMergeDropdown(role, "");
        showToast("Search filters reset. Showing all places in collection.");
      });
    }

    const handleAddTag = () => {
      if (!tagInput) return;
      const rawTag = tagInput.value.trim();
      if (!rawTag) return;
      const exists = poiMergePickerState[role].tags.some(t => t.toLowerCase() === rawTag.toLowerCase());
      if (!exists) {
        poiMergePickerState[role].tags.push(rawTag);
        renderPoiMergeSelectedTags(role);
        renderPoiMergeDropdown(role, input ? input.value : "");
      }
      tagInput.value = "";
    };

    if (addTagBtn) {
      addTagBtn.addEventListener("click", handleAddTag);
    }
    if (tagInput) {
      tagInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handleAddTag();
        }
      });
    }

    if (tagModeSelect) {
      tagModeSelect.addEventListener("change", () => {
        poiMergePickerState[role].tagMode = tagModeSelect.value;
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (slider) {
      slider.addEventListener("input", () => {
        poiMergePickerState[role].radiusStepIndex = parseInt(slider.value, 10);
        renderPoiMergeDropdown(role, input ? input.value : "");
      });
    }

    if (changeBtn) {
      changeBtn.addEventListener("click", () => {
        if (!picker || !info) return;
        if (picker.style.display === "none") {
          picker.style.display = "block";
          info.style.display = "none";
          populatePoiMergeTagsDatalist();
          populatePoiMergeListSelects();
          renderPoiMergeSelectedTags(role);
          if (input) {
            input.focus();
          }
          renderPoiMergeDropdown(role, input ? input.value : "");
        } else {
          picker.style.display = "none";
          info.style.display = "block";
          if (dropdown) dropdown.style.display = "none";
        }
      });
    }
  });

  // Close dropdowns on outside click
  document.addEventListener("click", (e) => {
    ["kept", "deleted"].forEach(role => {
      const picker = document.getElementById(`poi-merge-${role}-picker`);
      const dropdown = document.getElementById(`poi-merge-${role}-dropdown`);
      if (dropdown && picker && !picker.contains(e.target)) {
        dropdown.style.display = "none";
      }
    });
  });
}

// Swap Roles Button
if (poiMergeSwapBtn) {
  poiMergeSwapBtn.addEventListener("click", async () => {
    const tempPoi = poiMergeState.keptPoi;
    poiMergeState.keptPoi = poiMergeState.deletedPoi;
    poiMergeState.deletedPoi = tempPoi;

    const tempFolders = poiMergeState.keptFolders;
    poiMergeState.keptFolders = poiMergeState.deletedFolders;
    poiMergeState.deletedFolders = tempFolders;

    await refreshPoiMergeUi();
  });
}

// Close & Cancel buttons
if (poiMergeCloseBtn) poiMergeCloseBtn.addEventListener("click", closePoiMergeModal);
if (poiMergeCancelBtn) poiMergeCancelBtn.addEventListener("click", closePoiMergeModal);

// "Show all fields" toggle
const poiMergeShowAllToggle = document.getElementById("poi-merge-show-all-fields-toggle");
if (poiMergeShowAllToggle) {
  poiMergeShowAllToggle.addEventListener("change", () => {
    updateSingleFieldsVisibility();
  });
}

// Proceed button -> Open Confirm Modal
if (poiMergeProceedBtn) {
  poiMergeProceedBtn.addEventListener("click", () => {
    const kept = poiMergeState.keptPoi;
    const deleted = poiMergeState.deletedPoi;
    if (!kept || !deleted) {
      showToast("Please select both places before proceeding with the merge.", true);
      return;
    }

    const confirmKeptName = document.getElementById("poi-merge-confirm-kept-name");
    const confirmKeptId = document.getElementById("poi-merge-confirm-kept-id");
    const confirmDeletedName = document.getElementById("poi-merge-confirm-deleted-name");
    const confirmDeletedId = document.getElementById("poi-merge-confirm-deleted-id");

    if (confirmKeptName) confirmKeptName.textContent = kept.name;
    if (confirmKeptId) confirmKeptId.textContent = `ID: ${kept.id}`;
    if (confirmDeletedName) confirmDeletedName.textContent = deleted.name;
    if (confirmDeletedId) confirmDeletedId.textContent = `ID: ${deleted.id}`;

    if (poiMergeConfirmModal) poiMergeConfirmModal.style.display = "flex";
  });
}

if (poiMergeConfirmCloseBtn) poiMergeConfirmCloseBtn.addEventListener("click", closePoiMergeConfirmModal);
if (poiMergeConfirmBackBtn) poiMergeConfirmBackBtn.addEventListener("click", closePoiMergeConfirmModal);

// Final Execute Merge commit
if (poiMergeConfirmSubmitBtn) {
  poiMergeConfirmSubmitBtn.addEventListener("click", async () => {
    const kept = poiMergeState.keptPoi;
    const deleted = poiMergeState.deletedPoi;
    if (!kept || !deleted) return;

    poiMergeConfirmSubmitBtn.disabled = true;
    poiMergeConfirmSubmitBtn.textContent = "Merging places...";

    try {
      // 1. Collect single-value field selections
      const singleValues = {};
      POI_MERGE_SINGLE_FIELDS.forEach(field => {
        const radio = document.querySelector(`input[name="merge_single_${field.key}"]:checked`);
        const chosenRole = radio ? radio.value : "keep";
        const sourceObj = chosenRole === "keep" ? kept : deleted;
        singleValues[field.key] = sourceObj[field.key];
      });

      // 2. Collect multi-value selections
      const visit_dates = Array.from(document.querySelectorAll('input[name="merge_visit_date"]:checked')).map(cb => cb.value).sort();
      const list_ids = Array.from(document.querySelectorAll('input[name="merge_list_id"]:checked')).map(cb => cb.value);
      const selected_scanned_path_ids = Array.from(document.querySelectorAll('input[name="merge_scanned_path"]:checked')).map(cb => cb.value);
      const category_tags = Array.from(document.querySelectorAll('input[name="merge_tag"]:checked')).map(cb => cb.value);

      const hasCoords = singleValues.latitude !== null && singleValues.latitude !== undefined && singleValues.latitude !== "" &&
                        singleValues.longitude !== null && singleValues.longitude !== undefined && singleValues.longitude !== "";

      const payload = {
        kept_poi_id: kept.id,
        deleted_poi_id: deleted.id,
        name: singleValues.name || kept.name,
        poi_type: singleValues.poi_type || "site to see",
        personal_rating: singleValues.personal_rating !== null && singleValues.personal_rating !== undefined && singleValues.personal_rating !== "" ? Number(singleValues.personal_rating) : null,
        parent_poi_id: singleValues.parent_poi_id || null,
        clear_parent_poi: !singleValues.parent_poi_id,
        description: singleValues.description || null,
        latitude: hasCoords ? parseFloat(singleValues.latitude) : null,
        longitude: hasCoords ? parseFloat(singleValues.longitude) : null,
        clear_location: !hasCoords,
        iptc_sublocation: singleValues.iptc_sublocation || null,
        iptc_zip_code: singleValues.iptc_zip_code || null,
        iptc_city: singleValues.iptc_city || null,
        iptc_province_state: singleValues.iptc_province_state || null,
        iptc_country_code: singleValues.iptc_country_code || null,
        physical_effort: singleValues.physical_effort || null,
        indoor_outdoor: singleValues.indoor_outdoor || null,
        estimated_duration: singleValues.estimated_duration || null,
        cost_tier: singleValues.cost_tier || null,
        booking_lead_time: singleValues.booking_lead_time || null,
        visit_again: Boolean(singleValues.visit_again),
        phone_number: singleValues.phone_number || null,
        website_official: singleValues.website_official || null,
        source_type: singleValues.source_type || null,
        source_url: singleValues.source_url || "",
        visit_dates,
        category_tags,
        list_ids,
        selected_scanned_path_ids,
      };

      const res = await apiFetch("/api/v1/pois/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned ${res.status}`);
      }

      showToast(`Successfully merged "${deleted.name}" into "${kept.name}"!`);
      poiMergeMasterPois = null;
      closePoiMergeConfirmModal();
      closePoiMergeModal();
      closeEditModal();

      await fetchPois(true);
      if (typeof loadScannedFolders === "function") {
        await loadScannedFolders();
      }
    } catch (err) {
      showToast(`Merge failed: ${err.message}`, true);
    } finally {
      poiMergeConfirmSubmitBtn.disabled = false;
      poiMergeConfirmSubmitBtn.textContent = "Confirm & Delete Source POI";
    }
  });
}

// Initialize pickers
setupPoiMergePickers();
