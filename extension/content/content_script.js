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
 * Mounts or reveals the isolated Shadow DOM capture overlay.
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
          <span>Vistarae Capture</span>
        </div>
        <button class="vistarae-close-btn" id="vistarae-close-btn" title="Close (Escape)">✕</button>
      </div>

      <div class="vistarae-body" id="vistarae-body">
        <div class="vistarae-status-banner vistarae-status-unique" id="vistarae-status">
          <span class="vistarae-spinner" id="vistarae-spinner"></span>
          <span id="vistarae-status-text">Analyzing page with Gemini & verifying spatial uniqueness...</span>
        </div>

        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-name-input">Destination / POI Name</label>
          <input class="vistarae-input" id="vistarae-name-input" type="text" value="${escapeHtml(
            scrapedPoi.name,
          )}" required />
        </div>

        <div class="vistarae-grid-2">
          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-category-select">Category</label>
            <select class="vistarae-select" id="vistarae-category-select">
              <option value="viewpoint" ${
                scrapedPoi.category === "viewpoint" ? "selected" : ""
              }>Scenic Viewpoint</option>
              <option value="trail" ${
                scrapedPoi.category === "trail" ? "selected" : ""
              }>Trail / Hike</option>
              <option value="landmark" ${
                scrapedPoi.category === "landmark" ? "selected" : ""
              }>Historic Landmark</option>
              <option value="campground" ${
                scrapedPoi.category === "campground" ? "selected" : ""
              }>Campground</option>
              <option value="dining" ${
                scrapedPoi.category === "dining" ? "selected" : ""
              }>Dining / Food</option>
              <option value="experience" ${
                ![
                  "viewpoint",
                  "trail",
                  "landmark",
                  "campground",
                  "dining",
                ].includes(scrapedPoi.category)
                  ? "selected"
                  : ""
              }>Travel Experience</option>
            </select>
          </div>

          <div class="vistarae-form-group">
            <label class="vistarae-label" for="vistarae-address-input">Address / Region</label>
            <input class="vistarae-input" id="vistarae-address-input" type="text" value="${escapeHtml(
              scrapedPoi.address || "",
            )}" placeholder="City, State, Country" />
          </div>
        </div>

        <div class="vistarae-form-group">
          <label class="vistarae-label" for="vistarae-desc-input">Notes & Descriptions</label>
          <textarea class="vistarae-textarea" id="vistarae-desc-input" rows="3">${escapeHtml(
            scrapedPoi.description || "",
          )}</textarea>
        </div>

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

  // Save handler
  const save = async () => {
    const saveBtn = shadow.querySelector("#vistarae-save-btn");
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    const name = shadow.querySelector("#vistarae-name-input").value.trim();
    const category = shadow.querySelector("#vistarae-category-select").value;
    const address = shadow
      .querySelector("#vistarae-address-input")
      .value.trim();
    const description = shadow
      .querySelector("#vistarae-desc-input")
      .value.trim();

    try {
      const response = await chrome.runtime.sendMessage({
        action: "SAVE_POI",
        poi: {
          name,
          category,
          address,
          description,
          latitude: scrapedPoi.latitude,
          longitude: scrapedPoi.longitude,
          rating: scrapedPoi.rating,
          source_url: window.location.href,
          tags: scrapedPoi.tags,
        },
      });

      if (response?.success) {
        saveBtn.textContent = "Saved!";
        setTimeout(close, 400);
      } else {
        alert(response?.error || "Failed to save POI");
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

  // 5. Dispatch background extraction and deduplication check
  try {
    const checkResponse = await chrome.runtime.sendMessage({
      action: "EXTRACT_AND_CHECK",
      payload: {
        text: selectionText || scrapedPoi.name,
        source_url: window.location.href,
        page_title: document.title,
        extracted: scrapedPoi,
      },
    });

    const statusEl = shadow.querySelector("#vistarae-status");
    const statusText = shadow.querySelector("#vistarae-status-text");
    const spinner = shadow.querySelector("#vistarae-spinner");
    spinner?.remove();

    if (checkResponse?.candidate) {
      const c = checkResponse.candidate;
      if (c.name) shadow.querySelector("#vistarae-name-input").value = c.name;
      if (c.address)
        shadow.querySelector("#vistarae-address-input").value = c.address;
      if (c.category)
        shadow.querySelector("#vistarae-category-select").value = c.category;
    }

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
          <div style="font-weight: 600; color: #b45309;">Existing POI Match: "${escapeHtml(
            dedup.existing_poi?.name || "Existing",
          )}"</div>
          <div style="font-size: 0.85rem; color: #78350f;">
            Distance: ${Math.round(
              dedup.distance_meters || 0,
            )}m | Similarity: ${Math.round(
              (dedup.similarity_score || 0) * 100,
            )}%
          </div>
          <div style="display: flex; gap: 8px; margin-top: 6px;">
            <button class="vistarae-btn vistarae-btn-secondary" style="font-size: 0.8rem; padding: 6px 12px;" id="vistarae-keep-both">Keep Both</button>
            <button class="vistarae-btn vistarae-btn-secondary" style="font-size: 0.8rem; padding: 6px 12px;" id="vistarae-overwrite">Update Existing</button>
          </div>
        </div>
      `;
    } else if (dedup.status === "NEARBY_PARENT") {
      statusEl.className = "vistarae-status-banner vistarae-status-parent";
      statusText.textContent = `ℹ Located within parent destination "${escapeHtml(
        dedup.existing_poi?.name || "Macro-Site",
      )}"`;
    }
  } catch (err) {
    const statusText = shadow.querySelector("#vistarae-status-text");
    if (statusText)
      statusText.textContent = "Ready to save (Offline/Manual Mode)";
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
