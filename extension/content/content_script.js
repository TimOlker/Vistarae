// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { findParserForUrl } from "./parsers/BasePoiParser.js";
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
        name: document.title,
        description: selectionText,
        category: "experience",
        source_url: window.location.href,
      };

  // State for selected tags and addresses
  let selectedTags = new Set();
  let currentAddresses = scrapedPoi.address
    ? [{ country: "United States", city: scrapedPoi.address }]
    : [];
  let parentPoiId = null;
  let parentPoiName = null;

  // 2. Create custom element container
  const container = document.createElement("vistarae-capture-root");
  const shadow = container.attachShadow({ mode: "open" });
  activeCaptureRoot = container;

  // 3. Attach scoped stylesheet
  const styleLink = document.createElement("link");
  styleLink.rel = "stylesheet";
  styleLink.href = chrome.runtime.getURL("content/overlay.css");
  shadow.appendChild(styleLink);

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
          <label class="vistarae-label" for="vistarae-desc-input">Summary Description</label>
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

        <!-- URLs -->
        <div class="vistarae-grid-2">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-official-url-input">Official Website</label>
            <input class="vistarae-input" id="vistarae-official-url-input" type="url" value="${escapeHtml(
              scrapedPoi.official_website_url || "",
            )}" placeholder="https://..." />
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-wikipedia-url-input">Wikipedia Article</label>
            <input class="vistarae-input" id="vistarae-wikipedia-url-input" type="url" value="${escapeHtml(
              scrapedPoi.wikipedia_url || "",
            )}" placeholder="https://en.wikipedia.org/..." />
          </div>
        </div>

        <!-- Hero Image -->
        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-hero-image-input">Hero Image URL</label>
          <input class="vistarae-input" id="vistarae-hero-image-input" type="url" value="${escapeHtml(
            scrapedPoi.hero_image_url || "",
          )}" placeholder="https://..." />
        </div>

        <!-- Duration & Rating -->
        <div class="vistarae-grid-3">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-duration-hours-input">Duration (Hours)</label>
            <input class="vistarae-input" id="vistarae-duration-hours-input" type="number" step="0.5" min="0" value="${
              scrapedPoi.estimated_duration_hours || ""
            }" placeholder="e.g. 2.5" />
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-duration-days-input">Duration (Days)</label>
            <input class="vistarae-input" id="vistarae-duration-days-input" type="number" step="1" min="0" value="${
              scrapedPoi.estimated_duration_days || ""
            }" placeholder="e.g. 0" />
          </div>
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-rating-input">Star Rating (0-5)</label>
            <input class="vistarae-input" id="vistarae-rating-input" type="number" min="0" max="5" step="1" value="" placeholder="Unassigned" />
          </div>
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

        <!-- Vetted Tags -->
        <div class="vistarae-form-group" id="vistarae-tags-container">
          <label class="vistarae-label">Vetted Tags</label>
          <div id="vistarae-tag-pills" class="vistarae-tag-pills">
            <span class="vistarae-text-muted">Loading tag recommendations...</span>
          </div>
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
        const parts = [
          a.street,
          a.city,
          a.state || a.state_province,
          a.country,
          a.postal_code,
        ].filter(Boolean);
        return `<div class="vistarae-address-chip">${escapeHtml(
          parts.join(", "),
        )}</div>`;
      })
      .join("");
  };

  // Render tags helper (REQ-EXT-029)
  const renderTags = (availableTags, recommended) => {
    const pillsContainer = shadow.querySelector("#vistarae-tag-pills");
    if (!pillsContainer) return;

    if (recommended && recommended.length > 0) {
      recommended.forEach((t) => selectedTags.add(t));
    }

    const tagsToShow =
      availableTags && availableTags.length > 0
        ? availableTags
        : Array.from(selectedTags).map((slug) => ({ slug, name: slug }));

    pillsContainer.innerHTML = "";
    tagsToShow.forEach((tag) => {
      const isSelected = selectedTags.has(tag.slug);
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = `vistarae-tag-pill ${isSelected ? "active" : ""}`;
      pill.textContent = tag.name || tag.slug;
      pill.addEventListener("click", () => {
        if (selectedTags.has(tag.slug)) {
          selectedTags.delete(tag.slug);
          pill.classList.remove("active");
        } else {
          selectedTags.add(tag.slug);
          pill.classList.add("active");
        }
      });
      pillsContainer.appendChild(pill);
    });
  };

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
      estimated_duration_days: daysVal ? parseInt(daysVal, 10) : null,
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

  // 5. Dispatch background extraction, multi-source scraping, and triage check
  try {
    const checkResponse = await chrome.runtime.sendMessage({
      action: "EXTRACT_AND_CHECK",
      payload: {
        source_url: window.location.href,
        page_title: document.title,
        selected_text: selectionText || scrapedPoi.description,
      },
    });

    const statusEl = shadow.querySelector("#vistarae-status");
    const statusText = shadow.querySelector("#vistarae-status-text");
    const spinner = shadow.querySelector("#vistarae-spinner");
    spinner?.remove();

    if (checkResponse?.candidate) {
      const c = checkResponse.candidate;
      if (c.name) shadow.querySelector("#vistarae-name-input").value = c.name;
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
      }
      if (c.wikipedia_url) {
        shadow.querySelector("#vistarae-wikipedia-url-input").value =
          c.wikipedia_url;
      }
      if (c.hero_image_url) {
        shadow.querySelector("#vistarae-hero-image-input").value =
          c.hero_image_url;
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
          c.estimated_duration_days;
      }
      if (c.addresses && c.addresses.length > 0) {
        currentAddresses = c.addresses;
      }
    }

    renderAddresses(currentAddresses);
    renderTags([], checkResponse?.recommended_tags || []);

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
    renderAddresses(currentAddresses);
    renderTags([], []);
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
