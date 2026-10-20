// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { getValidAccessToken } from "../background/auth.js";
import {
  prepareRequestHeaders,
  logTelemetryMessage,
} from "../background/telemetry.js";

const BACKEND_URL = "http://localhost:8000";

let state = {
  pois: [],
  filteredPois: [],
  selectedIds: new Set(),
  searchQuery: "",
  selectedCategory: "ALL",
  sortBy: "name_asc",
  userLocation: null,
  proximityEnabled: false,
};

// --- Haversine Geolocation Distance Calculation ---
function calculateDistanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // Earth radius in km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// --- CSV Formula Injection Sanitization (RFC 4180) ---
export function sanitizeCsvField(val) {
  if (val === null || val === undefined) return "";
  const str = String(val);

  // Neutralize formula injection triggers: =, +, -, @, or tabs
  let safeStr = str;
  if (/^[=+\-@\t\r]/.test(safeStr)) {
    safeStr = "'" + safeStr;
  }

  // RFC 4180 wrapping if field contains commas, double quotes, or newlines
  if (/[",\n\r]/.test(safeStr)) {
    safeStr = `"${safeStr.replace(/"/g, '""')}"`;
  }

  return safeStr;
}

export function generateCsv(records) {
  const headers = [
    "Name",
    "Category",
    "Address",
    "City",
    "State",
    "Country",
    "Latitude",
    "Longitude",
    "Rating",
    "Source URL",
    "Photo Directory",
    "Tags",
  ];

  const lines = [headers.map(sanitizeCsvField).join(",")];

  for (const poi of records) {
    const row = [
      poi.name,
      poi.category,
      poi.address,
      poi.city,
      poi.state,
      poi.country,
      poi.latitude,
      poi.longitude,
      poi.rating,
      poi.source_url,
      poi.local_photo_dir || "",
      Array.isArray(poi.tags) ? poi.tags.join("; ") : poi.tags,
    ];
    lines.push(row.map(sanitizeCsvField).join(","));
  }

  return lines.join("\r\n");
}

// --- DOM Rendering ---
function renderTable() {
  const tbody = document.getElementById("poi-tbody");
  const countBadge = document.getElementById("record-count");
  const bulkActions = document.getElementById("bulk-actions");
  const selectedCount = document.getElementById("selected-count");

  if (!tbody) return;

  tbody.innerHTML = "";
  countBadge.textContent = `${state.filteredPois.length} destinations found`;

  if (state.selectedIds.size > 0) {
    bulkActions.classList.remove("hidden");
    selectedCount.textContent = `${state.selectedIds.size} selected`;
  } else {
    bulkActions.classList.add("hidden");
  }

  if (state.filteredPois.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-muted);">
          No matching travel destinations found. Try clearing filters or capturing new places!
        </td>
      </tr>
    `;
    return;
  }

  for (const poi of state.filteredPois) {
    const tr = document.createElement("tr");

    const isChecked = state.selectedIds.has(poi.id);
    let distanceStr = "";
    if (
      state.proximityEnabled &&
      state.userLocation &&
      poi.latitude &&
      poi.longitude
    ) {
      const dist = calculateDistanceKm(
        state.userLocation.lat,
        state.userLocation.lng,
        poi.latitude,
        poi.longitude,
      );
      distanceStr = ` <span style="font-size: 0.75rem; color: #10b981;">(${Math.round(
        dist,
      )} km away)</span>`;
    }

    const photoDirHtml = poi.local_photo_dir
      ? `<button class="btn btn-secondary btn-sm btn-reveal-folder" data-path="${escapeAttr(
          poi.local_photo_dir,
        )}">
           📂 Reveal Folder
         </button>`
      : `<span style="color: var(--text-muted); font-size: 0.8rem;">None</span>`;

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="row-checkbox" data-id="${poi.id}" ${
          isChecked ? "checked" : ""
        } />
      </td>
      <td>
        <span class="poi-name">${escapeHtml(poi.name)}${distanceStr}</span>
        <span class="poi-desc">${escapeHtml(
          poi.description || poi.address || "",
        )}</span>
      </td>
      <td>
        <span class="badge-category">${escapeHtml(
          poi.category || "experience",
        )}</span>
      </td>
      <td>
        ${escapeHtml(
          [poi.city, poi.country].filter(Boolean).join(", ") || "Global",
        )}
      </td>
      <td>
        ${poi.rating ? "★".repeat(poi.rating) : "—"}
      </td>
      <td>
        ${photoDirHtml}
      </td>
      <td>
        <button class="btn btn-secondary btn-sm btn-delete" data-id="${
          poi.id
        }">Delete</button>
      </td>
    `;

    tbody.appendChild(tr);
  }

  // Bind row events
  tbody.querySelectorAll(".row-checkbox").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      const id = e.target.getAttribute("data-id");
      if (e.target.checked) state.selectedIds.add(id);
      else state.selectedIds.delete(id);
      renderTable();
    });
  });

  tbody.querySelectorAll(".btn-reveal-folder").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const path = e.currentTarget.getAttribute("data-path");
      showToast(`Opening local folder: ${path}...`);
      try {
        const response = await chrome.runtime.sendMessage({
          action: "NATIVE_OPEN_FOLDER",
          path,
        });
        if (response?.status === "ok") {
          showToast(`✓ Opened folder in OS Explorer`);
        } else {
          showToast(`⚠ Error: ${response?.message || "Folder opener failed"}`);
        }
      } catch (err) {
        showToast(`⚠ Native host error: ${err.message}`);
      }
    });
  });

  tbody.querySelectorAll(".btn-delete").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const id = e.currentTarget.getAttribute("data-id");
      if (confirm("Delete this destination?")) {
        await deletePoi(id);
      }
    });
  });
}

function applyFiltersAndSort() {
  let list = [...state.pois];

  // Category filter
  if (state.selectedCategory !== "ALL") {
    list = list.filter(
      (p) => p.category?.toLowerCase() === state.selectedCategory.toLowerCase(),
    );
  }

  // Keyword search
  if (state.searchQuery.trim()) {
    const q = state.searchQuery.toLowerCase();
    list = list.filter((p) => {
      const name = (p.name || "").toLowerCase();
      const desc = (p.description || "").toLowerCase();
      const addr = (p.address || "").toLowerCase();
      const city = (p.city || "").toLowerCase();
      const tags = Array.isArray(p.tags) ? p.tags.join(" ").toLowerCase() : "";
      return (
        name.includes(q) ||
        desc.includes(q) ||
        addr.includes(q) ||
        city.includes(q) ||
        tags.includes(q)
      );
    });
  }

  // Sorting
  list.sort((a, b) => {
    if (state.sortBy === "name_asc")
      return (a.name || "").localeCompare(b.name || "");
    if (state.sortBy === "name_desc")
      return (b.name || "").localeCompare(a.name || "");
    if (state.sortBy === "rating_desc")
      return (b.rating || 0) - (a.rating || 0);
    if (state.sortBy === "distance_asc" && state.userLocation) {
      const distA =
        a.latitude && a.longitude
          ? calculateDistanceKm(
              state.userLocation.lat,
              state.userLocation.lng,
              a.latitude,
              a.longitude,
            )
          : 999999;
      const distB =
        b.latitude && b.longitude
          ? calculateDistanceKm(
              state.userLocation.lat,
              state.userLocation.lng,
              b.latitude,
              b.longitude,
            )
          : 999999;
      return distA - distB;
    }
    return 0;
  });

  state.filteredPois = list;
  renderTable();
}

// --- Backend API Operations ---
async function fetchPois() {
  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {
    // Unauthenticated mode
  }

  const { headers } = prepareRequestHeaders({ method: "GET", token });
  logTelemetryMessage("OUTBOUND", "GET /api/pois");

  try {
    const response = await fetch(`${BACKEND_URL}/api/pois`, {
      method: "GET",
      headers,
    });

    if (response.ok) {
      const data = await response.json();
      state.pois = Array.isArray(data) ? data : data.items || [];
      applyFiltersAndSort();
      return;
    }
  } catch (err) {
    logTelemetryMessage(
      "OUTBOUND_RESPONSE",
      "Backend offline, loaded fallback samples",
      { error: err.message },
    );
  }

  // Fallback demo POIs if backend is offline
  state.pois = [
    {
      id: "demo-1",
      name: "Glacier Point Overlook",
      category: "viewpoint",
      address: "Glacier Point Rd, Yosemite National Park, CA",
      city: "Yosemite Valley",
      country: "USA",
      latitude: 37.7303,
      longitude: -119.5736,
      rating: 5,
      local_photo_dir: "C:\\Photos\\Yosemite\\GlacierPoint",
      tags: ["nps", "scenic", "sunset"],
    },
    {
      id: "demo-2",
      name: "Mist Trail to Vernal Fall",
      category: "trail",
      address: "Happy Isles, Yosemite National Park, CA",
      city: "Yosemite Valley",
      country: "USA",
      latitude: 37.7327,
      longitude: -119.5577,
      rating: 5,
      local_photo_dir: "C:\\Photos\\Yosemite\\MistTrail",
      tags: ["waterfall", "hike"],
    },
  ];
  applyFiltersAndSort();
}

async function deletePoi(id) {
  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {}

  const { headers, idempotencyKey } = prepareRequestHeaders({
    method: "DELETE",
    token,
  });
  logTelemetryMessage("OUTBOUND", `DELETE /api/pois/${id}`, { idempotencyKey });

  try {
    await fetch(`${BACKEND_URL}/api/pois/${id}`, {
      method: "DELETE",
      headers,
    });
  } catch (_) {}

  state.pois = state.pois.filter((p) => p.id !== id);
  state.selectedIds.delete(id);
  applyFiltersAndSort();
  showToast("Destination deleted");
}

// --- Toast Banner Utility ---
function showToast(msg) {
  const banner = document.getElementById("toast-banner");
  if (!banner) return;
  banner.textContent = msg;
  banner.classList.remove("hidden");
  setTimeout(() => {
    banner.classList.add("hidden");
  }, 3000);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  if (!str) return "";
  return String(str).replace(/"/g, "&quot;");
}

// --- Initialization & Event Bindings ---
document.addEventListener("DOMContentLoaded", () => {
  fetchPois();

  // Search input with instant filter
  const searchInput = document.getElementById("input-search");
  searchInput?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    applyFiltersAndSort();
  });

  // Category filter
  const categorySelect = document.getElementById("select-category");
  categorySelect?.addEventListener("change", (e) => {
    state.selectedCategory = e.target.value;
    applyFiltersAndSort();
  });

  // Sort order
  const sortSelect = document.getElementById("select-sort");
  sortSelect?.addEventListener("change", (e) => {
    state.sortBy = e.target.value;
    applyFiltersAndSort();
  });

  // Proximity toggle
  const proximityBtn = document.getElementById("btn-proximity");
  const proximityStatus = document.getElementById("proximity-status");
  proximityBtn?.addEventListener("click", () => {
    if (state.proximityEnabled) {
      state.proximityEnabled = false;
      proximityBtn.classList.remove("active");
      proximityStatus.textContent = "Enable Proximity";
      applyFiltersAndSort();
    } else {
      if (navigator.geolocation) {
        proximityStatus.textContent = "Acquiring GPS...";
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            state.userLocation = {
              lat: pos.coords.latitude,
              lng: pos.coords.longitude,
            };
            state.proximityEnabled = true;
            proximityBtn.classList.add("active");
            proximityStatus.textContent = "Proximity Active";
            state.sortBy = "distance_asc";
            sortSelect.value = "distance_asc";
            applyFiltersAndSort();
          },
          (err) => {
            showToast(`Geolocation error: ${err.message}`);
            proximityStatus.textContent = "Enable Proximity";
          },
        );
      }
    }
  });

  // Check all checkbox
  const checkAll = document.getElementById("th-check-all");
  checkAll?.addEventListener("change", (e) => {
    if (e.target.checked) {
      state.filteredPois.forEach((p) => state.selectedIds.add(p.id));
    } else {
      state.selectedIds.clear();
    }
    renderTable();
  });

  // Export to CSV
  const exportBtn = document.getElementById("btn-export-csv");
  exportBtn?.addEventListener("click", () => {
    const recordsToExport =
      state.selectedIds.size > 0
        ? state.pois.filter((p) => state.selectedIds.has(p.id))
        : state.filteredPois;

    if (recordsToExport.length === 0) {
      showToast("No destinations to export.");
      return;
    }

    const csvContent = generateCsv(recordsToExport);
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vistarae_pois_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`✓ Exported ${recordsToExport.length} destinations to CSV`);
  });

  // Refresh
  const refreshBtn = document.getElementById("btn-refresh");
  refreshBtn?.addEventListener("click", () => {
    fetchPois();
    showToast("Refreshing catalog...");
  });

  // Bulk Delete
  const bulkDeleteBtn = document.getElementById("btn-bulk-delete");
  bulkDeleteBtn?.addEventListener("click", async () => {
    if (confirm(`Delete ${state.selectedIds.size} selected destinations?`)) {
      for (const id of state.selectedIds) {
        await deletePoi(id);
      }
      state.selectedIds.clear();
      showToast("Selected destinations deleted");
    }
  });
});
