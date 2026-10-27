// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import {
  findParserForUrl,
  sanitizeDestinationTitle,
} from "./parsers/BasePoiParser.js";
import "./parsers/GoogleMapsParser.js";
import "./parsers/RoadtrippersParser.js";
import "./parsers/TripAdvisorParser.js";
import "./parsers/GenericSelectionParser.js";

let activeCaptureRoot = null;

/**
 * Closes and removes the active capture overlay if present.
 */
export function closeCaptureOverlay() {
  if (activeCaptureRoot) {
    activeCaptureRoot.remove();
    activeCaptureRoot = null;
  }
}

/**
 * Mounts or reveals the isolated Shadow DOM capture overlay with 1:1 schema parity (REQ-EXT-014 to REQ-EXT-016).
 * @param {Object} [payload] - Optional contextual payload from service worker.
 */
export async function openCaptureOverlay(payload = {}) {
  // If overlay is already active and connected, focus and do not duplicate
  if (activeCaptureRoot && activeCaptureRoot.isConnected) {
    const existingInput = activeCaptureRoot.shadowRoot?.querySelector(
      "#vistarae-name-input",
    );
    existingInput?.focus();
    return;
  }

  // 1. Execute scraper on active document
  const selectionText = payload.text || window.getSelection()?.toString() || "";
  const parser = findParserForUrl(window.location.href, document);
  const scrapedPoi = parser
    ? parser.parse(document, selectionText, window.location.href)
    : {
        name: sanitizeDestinationTitle(document.title) || document.title,
        description: selectionText,
        category: "experience",
        source_url: window.location.href,
      };
  scrapedPoi.name =
    sanitizeDestinationTitle(scrapedPoi.name) || scrapedPoi.name;

  // State for selected tags and addresses
  let selectedTags = new Set();
  let currentAddresses = scrapedPoi.address
    ? [{ street: scrapedPoi.address, raw: scrapedPoi.address }]
    : [];
  let parentPoiId = null;
  let parentPoiName = null;

  // 2. Create custom element container
  const container = document.createElement("vistarae-capture-root");
  const shadow = container.attachShadow({ mode: "open" });
  activeCaptureRoot = container;

  // 3. Attach scoped stylesheets (overlay.css & leaflet.css)
  const styleLink = document.createElement("link");
  styleLink.rel = "stylesheet";
  styleLink.href = chrome.runtime.getURL("content/overlay.css");
  shadow.appendChild(styleLink);

  const leafletStyleLink = document.createElement("link");
  leafletStyleLink.rel = "stylesheet";
  leafletStyleLink.href = chrome.runtime.getURL(
    "content/vendor/leaflet/leaflet.css",
  );
  shadow.appendChild(leafletStyleLink);

  // 4. Render modal template
  const modalWrapper = document.createElement("div");
  modalWrapper.innerHTML = `
    <div class="vistarae-backdrop" id="vistarae-backdrop"></div>
    <div class="vistarae-modal-container" role="dialog" aria-modal="true" aria-labelledby="vistarae-title">
      <div class="vistarae-header">
        <div class="vistarae-brand">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
          </svg>
          <span id="vistarae-title">Vistarae Capture</span>
        </div>
        <div class="vistarae-user-context" id="vistarae-user-context">
          <span class="vistarae-user-email" id="vistarae-user-email">Loading user...</span>
          <span class="vistarae-badge vistarae-badge-neutral" id="vistarae-user-badge">Checking...</span>
        </div>
        <button class="vistarae-close-btn" id="vistarae-close-btn" title="Close (Escape)">✕</button>
      </div>

      <div class="vistarae-body" id="vistarae-body">
        <div class="vistarae-status-banner vistarae-status-unique" id="vistarae-status">
          <span class="vistarae-spinner" id="vistarae-spinner"></span>
          <span id="vistarae-status-text">Analyzing page with Gemini & checking spatial uniqueness...</span>
        </div>

        <!-- POI Name -->
        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-name-input">Destination / POI Name</label>
          <input class="vistarae-input" id="vistarae-name-input" type="text" value="${escapeHtml(
            scrapedPoi.name,
          )}" required />
        </div>

        <!-- Description -->
        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-desc-input">
            Summary Description
            <span class="vistarae-field-spinner" id="vistarae-desc-spinner" title="Enriching description..."></span>
          </label>
          <textarea class="vistarae-textarea" id="vistarae-desc-input" rows="3">${escapeHtml(
            scrapedPoi.description || "",
          )}</textarea>
        </div>

        <!-- Coordinates -->
        <div class="vistarae-grid-2">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-lat-input">Latitude</label>
            <input class="vistarae-input" id="vistarae-lat-input" type="number" step="any" value="${
              scrapedPoi.latitude !== undefined && scrapedPoi.latitude !== null
                ? scrapedPoi.latitude
                : ""
            }" placeholder="e.g. 55.6089" />
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-lng-input">Longitude</label>
            <input class="vistarae-input" id="vistarae-lng-input" type="number" step="any" value="${
              scrapedPoi.longitude !== undefined &&
              scrapedPoi.longitude !== null
                ? scrapedPoi.longitude
                : ""
            }" placeholder="e.g. -1.7099" />
          </div>
        </div>

        <!-- Interactive Mini-Map Container -->
        <div class="vistarae-minimap-wrapper" id="vistarae-minimap-wrapper">
          <div id="vistarae-minimap"></div>
          <div class="vistarae-minimap-bar">
            <span class="vistarae-minimap-hint" id="vistarae-minimap-hint">Pin marks plotted location</span>
            <button type="button" class="vistarae-btn-mini" id="vistarae-reselect-map-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              Reselect Location
            </button>
          </div>
        </div>

        <!-- URLs -->
        <div class="vistarae-grid-2">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-official-url-input">Official Website</label>
            <div class="vistarae-input-with-button">
              <input class="vistarae-input" id="vistarae-official-url-input" type="url" value="${escapeHtml(
                scrapedPoi.official_website_url || "",
              )}" placeholder="https://..." />
              <button type="button" class="vistarae-btn-mini" id="vistarae-view-official-btn" title="Open official website in new tab" ${
                scrapedPoi.official_website_url ? "" : "disabled"
              }>View ↗</button>
            </div>
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-wikipedia-url-input">
              Wikipedia Article
              <span class="vistarae-field-spinner" id="vistarae-wiki-spinner" title="Resolving Wikipedia..."></span>
            </label>
            <div class="vistarae-input-with-button">
              <input class="vistarae-input" id="vistarae-wikipedia-url-input" type="url" value="${escapeHtml(
                scrapedPoi.wikipedia_url || "",
              )}" placeholder="https://en.wikipedia.org/..." />
              <button type="button" class="vistarae-btn-mini" id="vistarae-view-wiki-btn" title="Open Wikipedia article in new tab" ${
                scrapedPoi.wikipedia_url ? "" : "disabled"
              }>View ↗</button>
            </div>
          </div>
        </div>

        <!-- Hero Image -->
        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-hero-image-input">
            Hero Image URL
            <span class="vistarae-field-spinner" id="vistarae-hero-spinner" title="Extracting hero image..."></span>
          </label>
          <div class="vistarae-input-with-button">
            <input class="vistarae-input" id="vistarae-hero-image-input" type="url" value="${escapeHtml(
              scrapedPoi.hero_image_url || "",
            )}" placeholder="https://..." />
            <button type="button" class="vistarae-btn-mini" id="vistarae-hero-reload-btn" title="Reload and preview hero image">Preview</button>
          </div>
          <div class="vistarae-hero-preview-card" id="vistarae-hero-preview-card">
            <div class="vistarae-hero-placeholder" id="vistarae-hero-placeholder">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              <span>No image preview available</span>
            </div>
            <img id="vistarae-hero-img-preview" alt="Destination Preview" style="display: none;" />
          </div>
          <div class="vistarae-inline-warning" id="vistarae-hero-warning" style="display: none;"></div>
        </div>

        <!-- Duration & Rating -->
        <div class="vistarae-grid-3">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-duration-hours-input">
              Duration (Hours)
              <span class="vistarae-field-spinner" id="vistarae-dur-spinner" title="Inferring duration..."></span>
            </label>
            <input class="vistarae-input" id="vistarae-duration-hours-input" type="number" step="0.5" min="0" value="${
              scrapedPoi.estimated_duration_hours || ""
            }" placeholder="e.g. 2.5" />
            <span class="vistarae-field-hint" style="font-size: 10px; color: #64748b; display: block; margin-top: 3px;">Activity time per visit (e.g. 2.5h)</span>
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-duration-days-input">Itinerary Days</label>
            <input class="vistarae-input" id="vistarae-duration-days-input" type="number" step="1" min="1" value="${
              scrapedPoi.estimated_duration_days && scrapedPoi.estimated_duration_days >= 1
                ? scrapedPoi.estimated_duration_days
                : 1
            }" placeholder="e.g. 1" />
            <span class="vistarae-field-hint" style="font-size: 10px; color: #64748b; display: block; margin-top: 3px;">Days allocated (1 = single-day)</span>
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-rating-input">Star Rating (0-5)</label>
            <input class="vistarae-input" id="vistarae-rating-input" type="number" min="0" max="5" step="1" value="" placeholder="Unassigned" />
            <span class="vistarae-field-hint" style="font-size: 10px; color: #64748b; display: block; margin-top: 3px;">Optional traveler rating</span>
          </div>
        </div>

        <!-- Visit Duration Notes / Reasoning -->
        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-duration-notes-input">
            Estimated Visit Time Notes
          </label>
          <textarea class="vistarae-textarea" id="vistarae-duration-notes-input" rows="2" placeholder="Reasoning for visit duration (e.g. 45-min tour, 30-min grounds walk)...">${
            scrapedPoi.estimated_visit_time_notes || ""
          }</textarea>
        </div>

        <!-- Addresses -->
        <div class="vistarae-form-group" id="vistarae-addresses-container">
          <label class="vistarae-label">Resolved Addresses</label>
          <div id="vistarae-address-list" class="vistarae-address-list">
            <span class="vistarae-text-muted">Resolving geographic address...</span>
          </div>
        </div>

        <!-- Parent POI -->
        <div class="vistarae-form-group" id="vistarae-parent-container">
          <label class="vistarae-label">Parent Destination (Hierarchical Nesting)</label>
          <input type="hidden" id="vistarae-parent-id" value="" />
          <input class="vistarae-input" id="vistarae-parent-name" type="text" placeholder="None (Root Destination)" readonly />
        </div>

        <!-- Configured Tags -->
        <div class="vistarae-form-group" id="vistarae-tags-container">
          <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <label class="vistarae-label">Tags</label>
            <span class="vistarae-text-muted" style="font-size: 0.75rem;">Auto-detected from scraped sites · Click to add or remove</span>
          </div>
          <div id="vistarae-tag-pills" class="vistarae-tag-pills"></div>
        </div>

        <!-- Triage / Deduplication Banner Container -->
        <div id="vistarae-dedup-container"></div>
      </div>

      <div class="vistarae-actions">
        <button class="vistarae-btn vistarae-btn-secondary" id="vistarae-cancel-btn">Cancel</button>
        <button class="vistarae-btn vistarae-btn-primary" id="vistarae-save-btn">Save to Vistarae</button>
      </div>
    </div>
  `;
  shadow.appendChild(modalWrapper);

  // Mount to top level
  (
    document.fullscreenElement ||
    document.body ||
    document.documentElement
  ).appendChild(container);

  // Bind close and keyboard traps
  const close = () => {
    if (activeCaptureRoot) {
      activeCaptureRoot.remove();
      activeCaptureRoot = null;
    }
    document.removeEventListener("keydown", handleKeydown);
  };

  const handleKeydown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      save();
    }
  };
  document.addEventListener("keydown", handleKeydown);

  shadow.querySelector("#vistarae-close-btn").addEventListener("click", close);
  shadow.querySelector("#vistarae-cancel-btn").addEventListener("click", close);
  shadow.querySelector("#vistarae-backdrop").addEventListener("click", close);

  // Async user context lookup (REQ-EXT-010)
  chrome.runtime
    .sendMessage({ action: "GET_AUTH_STATUS" })
    .then((auth) => {
      const emailEl = shadow.querySelector("#vistarae-user-email");
      const badgeEl = shadow.querySelector("#vistarae-user-badge");
      if (auth?.isAuthenticated && auth?.email) {
        if (emailEl) emailEl.textContent = auth.email;
        if (badgeEl) {
          badgeEl.textContent = "Authenticated";
          badgeEl.className = "vistarae-badge vistarae-badge-success";
        }
      } else {
        if (emailEl) emailEl.textContent = "Guest";
        if (badgeEl) {
          badgeEl.textContent = "Guest";
          badgeEl.className = "vistarae-badge vistarae-badge-neutral";
        }
      }
    })
    .catch(() => {});

  // ── View Buttons & URL Input Watchers (REQ-FR-004, REQ-FR-005, REQ-FR-006) ──
  const officialInput = shadow.querySelector("#vistarae-official-url-input");
  const officialBtn = shadow.querySelector("#vistarae-view-official-btn");
  const wikiInput = shadow.querySelector("#vistarae-wikipedia-url-input");
  const wikiBtn = shadow.querySelector("#vistarae-view-wiki-btn");

  const syncViewBtnState = (input, btn) => {
    if (!input || !btn) return;
    const url = input.value.trim();
    btn.disabled = !url;
  };

  const openUrlInNewTab = (rawUrl) => {
    const trimmed = (rawUrl || "").trim();
    if (!trimmed) return;
    let target = trimmed;
    if (!/^https?:\/\//i.test(target)) {
      target = `https://${target}`;
    }
    try {
      window.open(target, "_blank", "noopener,noreferrer");
    } catch (_) {}
  };

  officialInput?.addEventListener("input", () =>
    syncViewBtnState(officialInput, officialBtn),
  );
  officialBtn?.addEventListener("click", () =>
    openUrlInNewTab(officialInput?.value),
  );

  wikiInput?.addEventListener("input", () =>
    syncViewBtnState(wikiInput, wikiBtn),
  );
  wikiBtn?.addEventListener("click", () => openUrlInNewTab(wikiInput?.value));

  // ── Hero Image Preview Probe (REQ-FR-007, REQ-FR-008, REQ-FR-009, REQ-FR-010) ──
  const heroInput = shadow.querySelector("#vistarae-hero-image-input");
  const heroReloadBtn = shadow.querySelector("#vistarae-hero-reload-btn");
  const heroImgPreview = shadow.querySelector("#vistarae-hero-img-preview");
  const heroPlaceholder = shadow.querySelector("#vistarae-hero-placeholder");
  const heroWarning = shadow.querySelector("#vistarae-hero-warning");

  const updateHeroPreview = (urlToProbe) => {
    const url = (urlToProbe || "").trim();
    if (heroWarning) {
      heroWarning.style.display = "none";
      heroWarning.textContent = "";
    }

    if (!url) {
      if (heroImgPreview) heroImgPreview.style.display = "none";
      if (heroPlaceholder) heroPlaceholder.style.display = "flex";
      return;
    }

    // In-memory preflight probe
    const probe = new Image();
    probe.onload = () => {
      if (heroImgPreview) {
        heroImgPreview.src = url;
        heroImgPreview.style.display = "block";
      }
      if (heroPlaceholder) heroPlaceholder.style.display = "none";
    };
    probe.onerror = () => {
      if (heroImgPreview) heroImgPreview.style.display = "none";
      if (heroPlaceholder) heroPlaceholder.style.display = "flex";
      if (heroWarning) {
        heroWarning.textContent =
          "⚠ Image failed to load (check URL or CORS).";
        heroWarning.style.display = "flex";
      }
    };
    probe.src = url;
  };

  if (heroInput?.value) {
    updateHeroPreview(heroInput.value);
  }
  heroReloadBtn?.addEventListener("click", () => {
    updateHeroPreview(heroInput?.value);
  });
  heroInput?.addEventListener("change", () => {
    updateHeroPreview(heroInput?.value);
  });

  // ── Interactive Leaflet Mini-Map (REQ-FR-011, REQ-FR-012, REQ-FR-013) ──
  const minimapEl = shadow.querySelector("#vistarae-minimap");
  const reselectBtn = shadow.querySelector("#vistarae-reselect-map-btn");
  const minimapHint = shadow.querySelector("#vistarae-minimap-hint");
  const latInput = shadow.querySelector("#vistarae-lat-input");
  const lngInput = shadow.querySelector("#vistarae-lng-input");

  let leafletMap = null;
  let leafletMarker = null;
  let isReselecting = false;

  const initMiniMap = async (lat, lng) => {
    if (!minimapEl) return;
    const initialLat =
      lat !== undefined && lat !== null && !isNaN(lat) ? parseFloat(lat) : null;
    const initialLng =
      lng !== undefined && lng !== null && !isNaN(lng) ? parseFloat(lng) : null;

    if (initialLat === null || initialLng === null) {
      minimapEl.style.display = "none";
      if (reselectBtn) reselectBtn.disabled = true;
      return;
    }
    minimapEl.style.display = "block";
    if (reselectBtn) reselectBtn.disabled = false;

    // Load Leaflet dynamically if not already present on window or global
    if (
      typeof window.L === "undefined" &&
      typeof globalThis.L === "undefined"
    ) {
      try {
        const leafletModuleUrl = chrome.runtime.getURL(
          "content/vendor/leaflet/leaflet.js",
        );
        await import(leafletModuleUrl);
      } catch (err) {
        console.warn("Vistarae: Leaflet failed to load:", err);
        return;
      }
    }

    const L = window.L || globalThis.L;
    if (!L || typeof L.map !== "function") return;

    if (leafletMap) {
      leafletMap.setView([initialLat, initialLng], 14);
      if (leafletMarker) {
        leafletMarker.setLatLng([initialLat, initialLng]);
      }
      return;
    }

    try {
      leafletMap = L.map(minimapEl, {
        center: [initialLat, initialLng],
        zoom: 14,
        zoomControl: true,
        attributionControl: false,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png", {
        subdomains: "abc",
        maxZoom: 19,
      }).addTo(leafletMap);

      // SVG DivIcon avoids broken PNG assets inside extension Shadow DOM
      const pinIcon = L.divIcon({
        className: "vistarae-map-pin",
        html: `
          <div style="transform: translate(-12px, -24px);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="#4f46e5" stroke="#ffffff" stroke-width="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
              <circle cx="12" cy="10" r="3" fill="#ffffff"></circle>
            </svg>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 24],
      });

      leafletMarker = L.marker([initialLat, initialLng], {
        icon: pinIcon,
        draggable: false,
      }).addTo(leafletMap);

      const onCoordinatesSelected = async (newLat, newLng) => {
        const roundedLat = parseFloat(newLat.toFixed(6));
        const roundedLng = parseFloat(newLng.toFixed(6));
        if (latInput) latInput.value = roundedLat;
        if (lngInput) lngInput.value = roundedLng;
        if (leafletMarker) leafletMarker.setLatLng([roundedLat, roundedLng]);

        // Dispatch reverse geocoding to update address chips (REQ-FR-013)
        try {
          const listEl = shadow.querySelector("#vistarae-address-list");
          if (listEl) {
            listEl.innerHTML =
              '<span class="vistarae-text-muted">Reverse-geocoding selected location...</span>';
          }
          const revResp = await chrome.runtime.sendMessage({
            action: "REVERSE_GEOCODE",
            latitude: roundedLat,
            longitude: roundedLng,
          });
          if (revResp?.addresses && revResp.addresses.length > 0) {
            currentAddresses = revResp.addresses;
            renderAddresses(currentAddresses);
          } else if (revResp?.formatted_address) {
            currentAddresses = [
              {
                street: revResp.formatted_address,
                city: revResp.city,
                country: revResp.country,
                postal_code: revResp.postcode,
              },
            ];
            renderAddresses(currentAddresses);
          } else {
            const listEl = shadow.querySelector("#vistarae-address-list");
            if (listEl) {
              listEl.innerHTML =
                '<span class="vistarae-text-muted">No address resolved.</span>';
            }
          }
        } catch (_) {
          const listEl = shadow.querySelector("#vistarae-address-list");
          if (listEl) {
            listEl.innerHTML =
              '<span class="vistarae-text-muted">No address resolved.</span>';
          }
        }
      };

      // Canvas click-to-place
      leafletMap.on("click", (e) => {
        if (!isReselecting) return;
        onCoordinatesSelected(e.latlng.lat, e.latlng.lng);
      });

      // Pin dragend
      leafletMarker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        onCoordinatesSelected(pos.lat, pos.lng);
      });

      // Invalidate size once rendered
      setTimeout(() => {
        leafletMap?.invalidateSize();
      }, 200);
    } catch (err) {
      console.warn("Vistarae: Mini-map initialization error:", err);
    }
  };

  const toggleReselect = () => {
    isReselecting = !isReselecting;
    if (reselectBtn) {
      if (isReselecting) {
        reselectBtn.classList.add("active");
        reselectBtn.textContent = "Done Reselecting";
        if (minimapHint)
          minimapHint.textContent =
            "Click map or drag pin to reselect location";
        minimapEl?.classList.add("vistarae-minimap-reselecting");
      } else {
        reselectBtn.classList.remove("active");
        reselectBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          Reselect Location
        `;
        if (minimapHint) minimapHint.textContent = "Pin marks plotted location";
        minimapEl?.classList.remove("vistarae-minimap-reselecting");
      }
    }
    if (leafletMarker) {
      if (isReselecting && leafletMarker.dragging) {
        leafletMarker.dragging.enable();
      } else if (leafletMarker.dragging) {
        leafletMarker.dragging.disable();
      }
    }
  };
  reselectBtn?.addEventListener("click", toggleReselect);

  // Initial mini-map mount
  if (
    scrapedPoi.latitude !== undefined &&
    scrapedPoi.latitude !== null &&
    scrapedPoi.longitude !== undefined &&
    scrapedPoi.longitude !== null
  ) {
    initMiniMap(scrapedPoi.latitude, scrapedPoi.longitude);
  }

  // Render addresses helper
  const renderAddresses = (addresses) => {
    const listEl = shadow.querySelector("#vistarae-address-list");
    if (!listEl) return;
    if (!addresses || addresses.length === 0) {
      listEl.innerHTML =
        '<span class="vistarae-text-muted">No address resolved.</span>';
      return;
    }
    listEl.innerHTML = addresses
      .map((a) => {

        const parts = [];
        let streetVal = a.street ? a.street.trim() : "";
        const countryVal = (a.country || "").trim();
        if (
          streetVal &&
          countryVal &&
          countryVal.toLowerCase() !== "unknown" &&
          streetVal.toLowerCase().endsWith(countryVal.toLowerCase())
        ) {
          streetVal = streetVal
            .slice(0, -countryVal.length)
            .replace(/[,\s]+$/, "")
            .trim();
        }
        if (streetVal) parts.push(streetVal);
        if (
          a.city &&
          a.city.trim() &&
          !parts.some((p) => p.toLowerCase().includes(a.city.trim().toLowerCase()))
        ) {
          parts.push(a.city.trim());
        }
        const stateVal = (a.state || a.state_province || "").trim();
        if (
          stateVal &&
          !parts.some((p) => p.toLowerCase().includes(stateVal.toLowerCase()))
        ) {
          parts.push(stateVal);
        }
        if (
          countryVal &&
          countryVal.toLowerCase() !== "unknown" &&
          !parts.some((p) => p.toLowerCase().includes(countryVal.toLowerCase()))
        ) {
          parts.push(countryVal);
        }
        if (
          a.postal_code &&
          a.postal_code.trim() &&
          !parts.some((p) =>
            p.toLowerCase().includes(a.postal_code.trim().toLowerCase()),
          )
        ) {
          parts.push(a.postal_code.trim());
        }
        const text = parts.length > 0 ? parts.join(", ") : a.raw || "";
        return `<div class="vistarae-address-chip">${escapeHtml(text)}</div>`;
      })
      .join("");
  };

  renderAddresses(currentAddresses);

  // State for user configured tags loaded from backend
  let userTags = [];

  // Render tags helper (REQ-EXT-029)
  const renderTags = (availableTags = userTags, recommended = []) => {
    const pillsContainer = shadow.querySelector("#vistarae-tag-pills");
    if (!pillsContainer) return;

    if (recommended && recommended.length > 0) {
      recommended.forEach((t) => {
        const slug = typeof t === "string" ? t : t?.slug;
        if (slug) selectedTags.add(slug);
      });
    }

    if (availableTags && availableTags.length > 0) {
      userTags = availableTags;
    }

    pillsContainer.innerHTML = "";
    if (!userTags || userTags.length === 0) {
      pillsContainer.innerHTML =
        '<span class="vistarae-text-muted">Loading your configured tags...</span>';
      return;
    }

    userTags.forEach((tag) => {
      const isSelected =
        selectedTags.has(tag.slug) ||
        (tag.name && selectedTags.has(tag.name.toLowerCase()));
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = `vistarae-tag-pill ${isSelected ? "active" : ""}`;
      const rawText = tag.name || tag.slug.replace(/_/g, " ");
      const formattedName = rawText.charAt(0).toUpperCase() + rawText.slice(1);
      pill.textContent = isSelected ? `✓ ${formattedName}` : formattedName;

      pill.addEventListener("click", () => {
        if (
          selectedTags.has(tag.slug) ||
          (tag.name && selectedTags.has(tag.name.toLowerCase()))
        ) {
          selectedTags.delete(tag.slug);
          if (tag.name) selectedTags.delete(tag.name.toLowerCase());
          pill.classList.remove("active");
          pill.textContent = formattedName;
        } else {
          selectedTags.add(tag.slug);
          pill.classList.add("active");
          pill.textContent = `✓ ${formattedName}`;
        }
      });
      pillsContainer.appendChild(pill);
    });
  };

  // Query backend server for user's configured tags immediately
  chrome.runtime
    .sendMessage({ action: "GET_USER_TAGS" })
    .then((resp) => {
      if (resp?.tags && resp.tags.length > 0) {
        renderTags(resp.tags);
      } else if (userTags.length === 0) {
        const pillsContainer = shadow.querySelector("#vistarae-tag-pills");
        if (pillsContainer && userTags.length === 0) {
          pillsContainer.innerHTML =
            '<span class="vistarae-text-muted">No configured tags found in your Vistarae library.</span>';
        }
      }
    })
    .catch(() => {});

  // Save handler
  const save = async () => {
    const saveBtn = shadow.querySelector("#vistarae-save-btn");
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    const name = shadow.querySelector("#vistarae-name-input").value.trim();
    const description = shadow
      .querySelector("#vistarae-desc-input")
      .value.trim();
    const latVal = shadow.querySelector("#vistarae-lat-input").value;
    const lngVal = shadow.querySelector("#vistarae-lng-input").value;
    const officialUrl = shadow
      .querySelector("#vistarae-official-url-input")
      .value.trim();
    const wikipediaUrl = shadow
      .querySelector("#vistarae-wikipedia-url-input")
      .value.trim();
    const heroImageUrl = shadow
      .querySelector("#vistarae-hero-image-input")
      .value.trim();
    const hoursVal = shadow.querySelector(
      "#vistarae-duration-hours-input",
    ).value;
    const daysVal = shadow.querySelector("#vistarae-duration-days-input").value;
    const ratingVal = shadow.querySelector("#vistarae-rating-input").value;
    const notesVal = shadow.querySelector("#vistarae-duration-notes-input")?.value?.trim() || null;

    const payloadPoi = {
      name,
      description,
      addresses: currentAddresses,
      latitude: latVal ? parseFloat(latVal) : null,
      longitude: lngVal ? parseFloat(lngVal) : null,
      official_website_url: officialUrl || null,
      wikipedia_url: wikipediaUrl || null,
      hero_image_url: heroImageUrl || null,
      estimated_duration_hours: hoursVal ? parseFloat(hoursVal) : null,
      estimated_duration_days: daysVal ? parseInt(daysVal, 10) : 1,
      estimated_visit_time_notes: notesVal,
      rating: ratingVal ? parseInt(ratingVal, 10) : null, // REQ-EXT-016
      parent_poi_id: parentPoiId,
      parent_poi_name: parentPoiName,
      tags: Array.from(selectedTags),
      source_type: "Web",
      source_value: window.location.href,
    };

    try {
      const response = await chrome.runtime.sendMessage({
        action: "SAVE_POI",
        poi: payloadPoi,
      });

      if (response?.success) {
        saveBtn.textContent = "Saved!";
        setTimeout(close, 400);
      } else {
        alert(response?.error || "Failed to save destination");
        saveBtn.disabled = false;
        saveBtn.textContent = "Save to Vistarae";
      }
    } catch (err) {
      alert(`Save error: ${err.message}`);
      saveBtn.disabled = false;
      saveBtn.textContent = "Save to Vistarae";
    }
  };
  shadow.querySelector("#vistarae-save-btn").addEventListener("click", save);

  // Helpers to dismiss spinners
  const dismissSpinners = () => {
    shadow.querySelector("#vistarae-desc-spinner")?.remove();
    shadow.querySelector("#vistarae-wiki-spinner")?.remove();
    shadow.querySelector("#vistarae-hero-spinner")?.remove();
    shadow.querySelector("#vistarae-dur-spinner")?.remove();
  };

  // 5. Dispatch background extraction, multi-source scraping, and triage check
  try {
    const checkResponse = await chrome.runtime.sendMessage({
      action: "EXTRACT_AND_CHECK",
      payload: {
        source_url: window.location.href,
        page_title:
          scrapedPoi.name ||
          sanitizeDestinationTitle(document.title) ||
          document.title,
        selected_text: selectionText || scrapedPoi.description,
        extracted: scrapedPoi,
        latitude:
          scrapedPoi.latitude !== undefined && scrapedPoi.latitude !== null
            ? scrapedPoi.latitude
            : null,
        longitude:
          scrapedPoi.longitude !== undefined && scrapedPoi.longitude !== null
            ? scrapedPoi.longitude
            : null,
        raw_address: scrapedPoi.address || null,
        category: scrapedPoi.category || null,
      },
    });

    const statusEl = shadow.querySelector("#vistarae-status");
    const statusText = shadow.querySelector("#vistarae-status-text");
    const spinner = shadow.querySelector("#vistarae-spinner");
    spinner?.remove();
    dismissSpinners();

    if (checkResponse?.candidate) {
      const c = checkResponse.candidate;
      if (c.name)
        shadow.querySelector("#vistarae-name-input").value =
          sanitizeDestinationTitle(c.name) || c.name;
      if (c.description)
        shadow.querySelector("#vistarae-desc-input").value = c.description;
      if (c.latitude !== undefined && c.latitude !== null) {
        shadow.querySelector("#vistarae-lat-input").value = c.latitude;
      }
      if (c.longitude !== undefined && c.longitude !== null) {
        shadow.querySelector("#vistarae-lng-input").value = c.longitude;
      }
      if (c.official_website_url) {
        shadow.querySelector("#vistarae-official-url-input").value =
          c.official_website_url;
        syncViewBtnState(officialInput, officialBtn);
      }
      if (c.wikipedia_url) {
        shadow.querySelector("#vistarae-wikipedia-url-input").value =
          c.wikipedia_url;
        syncViewBtnState(wikiInput, wikiBtn);
      }
      if (c.hero_image_url) {
        shadow.querySelector("#vistarae-hero-image-input").value =
          c.hero_image_url;
        updateHeroPreview(c.hero_image_url);
      }
      if (
        c.estimated_duration_hours !== undefined &&
        c.estimated_duration_hours !== null
      ) {
        shadow.querySelector("#vistarae-duration-hours-input").value =
          c.estimated_duration_hours;
      }
      if (
        c.estimated_duration_days !== undefined &&
        c.estimated_duration_days !== null
      ) {
        shadow.querySelector("#vistarae-duration-days-input").value =
          c.estimated_duration_days >= 1 ? c.estimated_duration_days : 1;
      }
      if (
        c.estimated_visit_time_notes !== undefined &&
        c.estimated_visit_time_notes !== null
      ) {
        const notesEl = shadow.querySelector("#vistarae-duration-notes-input");
        if (notesEl) notesEl.value = c.estimated_visit_time_notes;
      }
      if (c.addresses && c.addresses.length > 0) {
        currentAddresses = c.addresses;
      }

      // Update mini-map if coordinates are available or refreshed
      const effectiveLat =
        c.latitude !== undefined && c.latitude !== null
          ? c.latitude
          : scrapedPoi.latitude;
      const effectiveLng =
        c.longitude !== undefined && c.longitude !== null
          ? c.longitude
          : scrapedPoi.longitude;
      if (
        effectiveLat !== undefined &&
        effectiveLat !== null &&
        effectiveLng !== undefined &&
        effectiveLng !== null
      ) {
        initMiniMap(effectiveLat, effectiveLng);
      }
    }

    renderAddresses(currentAddresses);
    const allAvailable =
      checkResponse?.available_tags && checkResponse.available_tags.length > 0
        ? checkResponse.available_tags
        : userTags;
    renderTags(allAvailable, checkResponse?.recommended_tags || []);

    const dedup = checkResponse?.deduplication;
    const dedupContainer = shadow.querySelector("#vistarae-dedup-container");

    if (!dedup || dedup.status === "UNIQUE_LOCATION") {
      statusEl.className = "vistarae-status-banner vistarae-status-unique";
      statusText.textContent = "✓ Unique destination — Ready to save!";
    } else if (dedup.status === "POTENTIAL_DUPLICATE") {
      statusEl.className = "vistarae-status-banner vistarae-status-duplicate";
      statusText.textContent = `⚠ Potential duplicate located within ${Math.round(
        dedup.distance_meters || 0,
      )}m!`;

      dedupContainer.innerHTML = `
        <div class="vistarae-dedup-card">
          <div style="font-weight: 700; color: #b45309;">
            Existing Match: "${escapeHtml(
              dedup.existing_poi_name || "Existing POI",
            )}"
          </div>
          <div style="font-size: 0.85rem; color: #78350f; margin-top: 4px;">
            Distance: ${Math.round(
              dedup.distance_meters || 0,
            )}m | Similarity: ${Math.round(
              (dedup.similarity_score || 0) * 100,
            )}%
          </div>
          <div class="vistarae-triage-actions" style="display: flex; gap: 8px; margin-top: 10px;">
            <button class="vistarae-btn vistarae-btn-sm vistarae-btn-secondary" id="vistarae-triage-proceed">Proceed</button>
            <button class="vistarae-btn vistarae-btn-sm vistarae-btn-primary" id="vistarae-triage-abort">Abort</button>
          </div>
        </div>
      `;

      shadow
        .querySelector("#vistarae-triage-abort")
        ?.addEventListener("click", close);
      shadow
        .querySelector("#vistarae-triage-proceed")
        ?.addEventListener("click", () => {
          dedupContainer.innerHTML = "";
          statusEl.className = "vistarae-status-banner vistarae-status-unique";
          statusText.textContent = "Proceeding with new standalone POI.";
        });
    } else if (dedup.status === "NEARBY_PARENT") {
      statusEl.className = "vistarae-status-banner vistarae-status-parent";
      statusText.textContent = `ℹ Located within parent destination "${escapeHtml(
        dedup.existing_poi_name || "Macro-Site",
      )}"`;

      dedupContainer.innerHTML = `
        <div class="vistarae-dedup-card" style="background: rgba(37, 99, 235, 0.08); border-color: rgba(37, 99, 235, 0.2);">
          <div style="font-weight: 700; color: #1d4ed8;">
            Discovered existing location: "${escapeHtml(
              dedup.existing_poi_name || "Macro Destination",
            )}" (${Math.round(dedup.distance_meters || 0)}m away)
          </div>
          <div style="font-size: 0.85rem; color: #1e40af; margin-top: 4px;">
            Distance: ${Math.round(dedup.distance_meters || 0)}m | Scale: ${
              dedup.scale_classification || "macro"
            }
          </div>
          <div class="vistarae-triage-actions" style="display: flex; gap: 8px; margin-top: 10px;">
            <button class="vistarae-btn vistarae-btn-sm vistarae-btn-primary" id="vistarae-triage-make-child">Make Child (Recommended)</button>
            <button class="vistarae-btn vistarae-btn-sm vistarae-btn-secondary" id="vistarae-triage-proceed">Proceed</button>
            <button class="vistarae-btn vistarae-btn-sm vistarae-btn-secondary" id="vistarae-triage-abort">Abort</button>
          </div>
        </div>
      `;

      shadow
        .querySelector("#vistarae-triage-make-child")
        ?.addEventListener("click", () => {
          parentPoiId = dedup.existing_poi_id;
          parentPoiName = dedup.existing_poi_name;
          shadow.querySelector("#vistarae-parent-id").value = parentPoiId || "";
          shadow.querySelector("#vistarae-parent-name").value =
            parentPoiName || "";
          dedupContainer.innerHTML = "";
          statusEl.className = "vistarae-status-banner vistarae-status-unique";
          statusText.textContent = `✓ Set parent to "${escapeHtml(
            parentPoiName,
          )}"`;
        });

      shadow
        .querySelector("#vistarae-triage-proceed")
        ?.addEventListener("click", () => {
          dedupContainer.innerHTML = "";
          statusEl.className = "vistarae-status-banner vistarae-status-unique";
          statusText.textContent = "Proceeding with new standalone POI.";
        });

      shadow
        .querySelector("#vistarae-triage-abort")
        ?.addEventListener("click", close);
    }
  } catch (err) {
    const statusText = shadow.querySelector("#vistarae-status-text");
    if (statusText)
      statusText.textContent = "Ready to save (Offline/Manual Mode)";
    dismissSpinners();
    renderAddresses(currentAddresses);
    renderTags(userTags, []);
  }

  // Focus destination title
  setTimeout(() => {
    shadow.querySelector("#vistarae-name-input")?.focus();
  }, 100);
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

// Listen for messages from background service worker
if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "TRIGGER_CAPTURE") {
      openCaptureOverlay(message.payload);
      sendResponse({ success: true });
    }
  });
}

/**
 * Synchronizes web application authentication state with extension storage.
 */
function syncAuthFromWebapp() {
  try {
    const isVistaraeOrigin =
      window.location.hostname === "localhost" ||
      window.location.hostname.endsWith("cloudfront.net") ||
      window.location.hostname.endsWith("vistarae.com") ||
      window.location.hostname === "127.0.0.1";

    if (!isVistaraeOrigin) return;

    const token = localStorage.getItem("vistarae_auth_token");
    const userRaw = localStorage.getItem("vistarae_user_profile");
    let user = null;
    if (userRaw) {
      try {
        user = JSON.parse(userRaw);
      } catch (_) {}
    }

    if (token && typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
      chrome.runtime.sendMessage({
        action: "SYNC_AUTH_FROM_WEBAPP",
        token,
        user,
      });
    }
  } catch (_) {
    // Cross-origin storage access safely ignored
  }
}

// Initial sync on script load & event listeners
if (typeof window !== "undefined") {
  syncAuthFromWebapp();
  window.addEventListener("storage", (e) => {
    if (e.key === "vistarae_auth_token" || e.key === "vistarae_user_profile") {
      syncAuthFromWebapp();
    }
  });
  window.addEventListener("vistarae_auth_sync", () => {
    syncAuthFromWebapp();
  });
}
