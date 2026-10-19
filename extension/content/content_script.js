/**
 * Vistarae Content Script
 * Captures webpage selection, enforces user authentication, and injects Shadow DOM editor.
 */

let hostElement = null;
let shadowRoot = null;

/**
 * Ensures clean Shadow DOM host element.
 */
function getOrCreateShadowRoot() {
  if (hostElement && shadowRoot) {
    return shadowRoot;
  }

  hostElement = document.createElement("vistarae-capture-root");
  hostElement.id = "vistarae-capture-host";
  document.body.appendChild(hostElement);

  shadowRoot = hostElement.attachShadow({ mode: "open" });

  // Inject scoped stylesheet
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = chrome.runtime.getURL("content/overlay.css");
  shadowRoot.appendChild(link);

  return shadowRoot;
}

function removeModal() {
  if (hostElement) {
    hostElement.remove();
    hostElement = null;
    shadowRoot = null;
  }
}

/**
 * Displays a toast notification.
 */
function showToast(message, isError = false) {
  const root = getOrCreateShadowRoot();
  const toast = document.createElement("div");
  toast.className = "vistarae-toast";
  toast.style.borderLeft = isError ? "4px solid #ef4444" : "4px solid #10b981";
  toast.innerHTML = `
    <span>${isError ? "⚠️" : "✨"}</span>
    <span>${escapeHtml(message)}</span>
  `;
  root.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => {
      toast.remove();
      if (!root.querySelector(".vistarae-modal")) {
        removeModal();
      }
    }, 300);
  }, 3500);
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

/**
 * Renders the loading modal state.
 */
function showLoadingModal() {
  const root = getOrCreateShadowRoot();

  // Clear previous modal
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";
  backdrop.innerHTML = `
    <div class="vistarae-modal" style="max-width: 420px;">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <h2 class="vistarae-title">Vistarae Ingestion</h2>
        </div>
        <button class="vistarae-close-btn" id="vistarae-cancel-load">&times;</button>
      </div>
      <div class="vistarae-loading-center">
        <div class="vistarae-spinner"></div>
        <p style="font-size: 14px; color: #475569; margin: 0;">Extracting POI entities & geocoding...</p>
      </div>
    </div>
  `;

  root.appendChild(backdrop);
  backdrop.querySelector("#vistarae-cancel-load").addEventListener("click", removeModal);
}

/**
 * Renders the Authentication Modal (Login & Register).
 */
function renderAuthModal(pendingPayload = null) {
  const root = getOrCreateShadowRoot();
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  let activeMode = "login"; // "login" | "register"

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";
  backdrop.innerHTML = `
    <div class="vistarae-modal" style="max-width: 440px;">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <h2 class="vistarae-title">Vistarae Account</h2>
        </div>
        <button class="vistarae-close-btn" id="vistarae-auth-close">&times;</button>
      </div>

      <div class="vistarae-auth-tabs">
        <button class="vistarae-auth-tab active" id="tab-login">Sign In</button>
        <button class="vistarae-auth-tab" id="tab-register">Create Account</button>
      </div>

      <div class="vistarae-body" style="padding-top: 16px;">
        <div class="vistarae-auth-error" id="v-auth-error"></div>

        <div class="vistarae-field-group" id="group-fullname" style="display: none;">
          <label class="vistarae-label">Full Name</label>
          <input type="text" class="vistarae-input" id="v-fullname" placeholder="Alex Traveler" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Email Address</label>
          <input type="email" class="vistarae-input" id="v-email" placeholder="traveler@example.com" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Password</label>
          <input type="password" class="vistarae-input" id="v-password" placeholder="••••••••" />
        </div>
      </div>

      <div class="vistarae-footer">
        <button class="vistarae-btn vistarae-btn-secondary" id="vistarae-auth-cancel">Cancel</button>
        <button class="vistarae-btn vistarae-btn-primary" id="vistarae-auth-submit">Sign In</button>
      </div>
    </div>
  `;

  root.appendChild(backdrop);

  const errorBox = backdrop.querySelector("#v-auth-error");
  const tabLogin = backdrop.querySelector("#tab-login");
  const tabRegister = backdrop.querySelector("#tab-register");
  const groupFullname = backdrop.querySelector("#group-fullname");
  const submitBtn = backdrop.querySelector("#vistarae-auth-submit");

  backdrop.querySelector("#vistarae-auth-close").addEventListener("click", removeModal);
  backdrop.querySelector("#vistarae-auth-cancel").addEventListener("click", removeModal);

  tabLogin.addEventListener("click", () => {
    activeMode = "login";
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    groupFullname.style.display = "none";
    submitBtn.textContent = "Sign In";
    errorBox.style.display = "none";
  });

  tabRegister.addEventListener("click", () => {
    activeMode = "register";
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    groupFullname.style.display = "flex";
    submitBtn.textContent = "Create Account";
    errorBox.style.display = "none";
  });

  submitBtn.addEventListener("click", () => {
    const email = backdrop.querySelector("#v-email").value.trim();
    const password = backdrop.querySelector("#v-password").value;
    const fullName = backdrop.querySelector("#v-fullname").value.trim();

    if (!email || !password) {
      errorBox.textContent = "Please provide both email and password.";
      errorBox.style.display = "block";
      return;
    }

    if (activeMode === "register" && password.length < 6) {
      errorBox.textContent = "Password must be at least 6 characters long.";
      errorBox.style.display = "block";
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Please wait...";
    errorBox.style.display = "none";

    const action = activeMode === "register" ? "REGISTER" : "LOGIN";
    const payload = activeMode === "register"
      ? { email, password, full_name: fullName || null }
      : { email, password };

    chrome.runtime.sendMessage({ action, payload }, (res) => {
      submitBtn.disabled = false;
      submitBtn.textContent = activeMode === "register" ? "Create Account" : "Sign In";

      if (res && res.success) {
        showToast(`Welcome back, ${res.data?.user?.full_name || email}!`);
        if (pendingPayload) {
          executeExtractionAndCheck(pendingPayload, res.data?.user);
        } else {
          removeModal();
        }
      } else {
        errorBox.textContent = res?.error || "Authentication failed. Please check your credentials.";
        errorBox.style.display = "block";
      }
    });
  });
}

/**
 * Primary capture orchestration triggered by shortcut or context menu.
 */
async function initiateCapture(initialText = null) {
  const selection = initialText || window.getSelection().toString().trim();
  const title = document.title || "";
  const url = window.location.href;
  const ogImageMeta = document.querySelector('meta[property="og:image"]');
  const ogImageUrl = ogImageMeta ? ogImageMeta.getAttribute("content") : null;

  if (!selection) {
    showToast("Please highlight text about a place or activity before capturing!", true);
    return;
  }

  const payload = {
    selected_text: selection,
    page_title: title,
    page_url: url,
    og_image_url: ogImageUrl,
  };

  // Check auth first
  chrome.runtime.sendMessage({ action: "GET_AUTH" }, (auth) => {
    if (!auth || !auth.isAuthenticated) {
      renderAuthModal(payload);
    } else {
      executeExtractionAndCheck(payload, auth.user);
    }
  });
}

/**
 * Calls backend /extract-and-check with error & auth recovery.
 */
function executeExtractionAndCheck(payload, currentUser) {
  showLoadingModal();

  chrome.runtime.sendMessage(
    { action: "EXTRACT_AND_CHECK", payload },
    (response) => {
      if (chrome.runtime.lastError || !response || !response.success) {
        if (response?.unauthorized) {
          showToast("Session expired. Please sign in again.", true);
          renderAuthModal(payload);
          return;
        }
        const errorMsg = response?.error || chrome.runtime.lastError?.message || "Failed to reach Vistarae backend";
        showToast(errorMsg, true);
        removeModal();
        return;
      }
      renderCaptureEditor(response.data, payload, currentUser);
    }
  );
}

/**
 * Renders the interactive editor modal.
 */
function renderCaptureEditor(data, originalRequest, currentUser = null) {
  const root = getOrCreateShadowRoot();
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  const cand = data.candidate || {};
  let currentRating = cand.personal_rating || 3;
  let selectedListIds = new Set();
  let parentPoiId = data.nearby_parent?.id || null;

  // Collision Banner Construction
  let bannerClass = "status-unique";
  let bannerIcon = "🟢";
  let bannerText = "Unique Location — No collision detected within 500ft in your collection.";
  let diffHtml = "";

  if (data.collision_status === "POTENTIAL_DUPLICATE" && data.matched_poi) {
    bannerClass = "status-duplicate";
    bannerIcon = "🟡";
    bannerText = `Potential Duplicate: "${escapeHtml(data.matched_poi.name)}" is in your records ${data.matched_poi.distance_meters}m away (${Math.round(data.matched_poi.name_similarity * 100)}% similarity).`;
    diffHtml = `
      <div class="vistarae-diff-card">
        <strong>Existing Record:</strong> ${escapeHtml(data.matched_poi.name)} (${escapeHtml(data.matched_poi.poi_type)})<br/>
        <span style="color: #64748b;">${escapeHtml(data.matched_poi.description || "No description")}</span>
      </div>
    `;
  } else if (data.collision_status === "NEARBY_PARENT" && data.nearby_parent) {
    bannerClass = "status-parent";
    bannerIcon = "🔵";
    bannerText = `Nearby Macro-Site: Found "${escapeHtml(data.nearby_parent.name)}" in your collection. Suggest nesting as child POI.`;
  }

  const userGreeting = currentUser?.email ? escapeHtml(currentUser.email) : "My Collection";

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";

  backdrop.innerHTML = `
    <div class="vistarae-modal">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <div>
            <h2 class="vistarae-title">Capture to Vistarae</h2>
            <div class="vistarae-user-pill">
              <span>👤 ${userGreeting}</span>
              <button class="vistarae-logout-btn" id="vistarae-logout">Sign Out</button>
            </div>
          </div>
        </div>
        <button class="vistarae-close-btn" id="vistarae-modal-close">&times;</button>
      </div>

      <div class="vistarae-status-banner ${bannerClass}">
        <span>${bannerIcon}</span>
        <span>${bannerText}</span>
      </div>
      ${diffHtml}

      <div class="vistarae-body">
        <div class="vistarae-field-group">
          <label class="vistarae-label">Point of Interest Name</label>
          <input type="text" class="vistarae-input" id="v-name" value="${escapeHtml(cand.name || "")}" />
        </div>

        <div class="vistarae-grid-2">
          <div class="vistarae-field-group">
            <label class="vistarae-label">POI Type</label>
            <select class="vistarae-select" id="v-type">
              <option value="photo location" ${cand.poi_type === "photo location" ? "selected" : ""}>Photo Location</option>
              <option value="site to see" ${cand.poi_type === "site to see" ? "selected" : ""}>Site to See</option>
              <option value="experience" ${cand.poi_type === "experience" ? "selected" : ""}>Experience</option>
              <option value="food/drink" ${cand.poi_type === "food/drink" ? "selected" : ""}>Food / Drink</option>
              <option value="lodging" ${cand.poi_type === "lodging" ? "selected" : ""}>Lodging</option>
              <option value="transit" ${cand.poi_type === "transit" ? "selected" : ""}>Transit</option>
            </select>
          </div>

          <div class="vistarae-field-group">
            <label class="vistarae-label">Personal Rating</label>
            <div class="vistarae-rating-stars" id="v-stars">
              ${[1, 2, 3, 4, 5].map((num) => `
                <span class="vistarae-star ${num <= currentRating ? "active" : ""}" data-val="${num}">★</span>
              `).join("")}
            </div>
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Description & Highlights</label>
          <textarea class="vistarae-textarea" id="v-desc">${escapeHtml(cand.description || "")}</textarea>
        </div>

        <div class="vistarae-grid-3">
          <div class="vistarae-field-group">
            <label class="vistarae-label">Physical Effort</label>
            <input type="text" class="vistarae-input" id="v-effort" value="${escapeHtml(cand.physical_effort || "drive-up")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Environment</label>
            <select class="vistarae-select" id="v-indoor">
              <option value="Outdoor" ${cand.indoor_outdoor === "Outdoor" ? "selected" : ""}>Outdoor</option>
              <option value="Indoor" ${cand.indoor_outdoor === "Indoor" ? "selected" : ""}>Indoor</option>
              <option value="Mixed" ${cand.indoor_outdoor === "Mixed" ? "selected" : ""}>Mixed</option>
            </select>
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Lead Time</label>
            <input type="text" class="vistarae-input" id="v-lead" value="${escapeHtml(cand.booking_lead_time || "walk-in ok")}" />
          </div>
        </div>

        <div class="vistarae-grid-3">
          <div class="vistarae-field-group">
            <label class="vistarae-label">Estimated Duration</label>
            <input type="text" class="vistarae-input" id="v-duration" value="${escapeHtml(cand.estimated_duration || "1-2 hours")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Cost Tier</label>
            <input type="text" class="vistarae-input" id="v-cost" value="${escapeHtml(cand.cost_tier || "Free")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Best Time to Visit</label>
            <input type="text" class="vistarae-input" id="v-best-time" value="${escapeHtml(cand.best_time_to_visit || "Golden Hour")}" />
          </div>
        </div>

        <div class="vistarae-grid-3">
          <div class="vistarae-field-group">
            <label class="vistarae-label">City / Town</label>
            <input type="text" class="vistarae-input" id="v-city" value="${escapeHtml(cand.iptc_city || "")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">State / Province</label>
            <input type="text" class="vistarae-input" id="v-state" value="${escapeHtml(cand.iptc_province_state || "")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Country Code</label>
            <input type="text" class="vistarae-input" id="v-country" maxlength="2" value="${escapeHtml(cand.iptc_country_code || "US")}" />
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Category Tags (comma-separated)</label>
          <input type="text" class="vistarae-input" id="v-tags" value="${escapeHtml((cand.category_tags || []).join(", "))}" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Add to My Lists</label>
          <div class="vistarae-lists-container" id="v-lists-list">
            ${(data.available_lists || []).map((lst) => `
              <div class="vistarae-list-tag" data-id="${lst.id}">
                <span>+</span> <span>${escapeHtml(lst.title)}</span>
              </div>
            `).join("")}
          </div>
          <div class="vistarae-add-list-row">
            <input type="text" class="vistarae-input" id="v-new-list-title" placeholder="+ Create new list..." />
            <button type="button" class="vistarae-btn vistarae-btn-secondary" id="v-add-list-btn">Add</button>
          </div>
        </div>
      </div>

      <div class="vistarae-footer">
        <button class="vistarae-btn vistarae-btn-secondary" id="vistarae-cancel-btn">Cancel</button>
        <button class="vistarae-btn vistarae-btn-primary" id="vistarae-save-btn">Save to Vistarae</button>
      </div>
    </div>
  `;

  root.appendChild(backdrop);

  // Close & Cancel listeners
  backdrop.querySelector("#vistarae-modal-close").addEventListener("click", removeModal);
  backdrop.querySelector("#vistarae-cancel-btn").addEventListener("click", removeModal);

  // Logout listener
  const logoutBtn = backdrop.querySelector("#vistarae-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "LOGOUT" }, () => {
        removeModal();
        showToast("Signed out successfully.");
      });
    });
  }

  // Star rating click handler
  const starContainer = backdrop.querySelector("#v-stars");
  starContainer.addEventListener("click", (e) => {
    const star = e.target.closest(".vistarae-star");
    if (star) {
      currentRating = parseInt(star.getAttribute("data-val"), 10);
      starContainer.querySelectorAll(".vistarae-star").forEach((s) => {
        const val = parseInt(s.getAttribute("data-val"), 10);
        s.classList.toggle("active", val <= currentRating);
      });
    }
  });

  // List tags click handler
  const listContainer = backdrop.querySelector("#v-lists-list");
  listContainer.addEventListener("click", (e) => {
    const tag = e.target.closest(".vistarae-list-tag");
    if (tag) {
      const listId = tag.getAttribute("data-id");
      if (selectedListIds.has(listId)) {
        selectedListIds.delete(listId);
        tag.classList.remove("selected");
        tag.querySelector("span:first-child").textContent = "+";
      } else {
        selectedListIds.add(listId);
        tag.classList.add("selected");
        tag.querySelector("span:first-child").textContent = "✓";
      }
    }
  });

  // Create new list dynamically
  const newListInput = backdrop.querySelector("#v-new-list-title");
  const addListBtn = backdrop.querySelector("#v-add-list-btn");
  addListBtn.addEventListener("click", () => {
    const title = newListInput.value.trim();
    if (!title) return;

    chrome.runtime.sendMessage(
      { action: "CREATE_LIST", payload: { title, is_trip: false } },
      (res) => {
        if (res && res.success && res.data) {
          const newList = res.data;
          const tag = document.createElement("div");
          tag.className = "vistarae-list-tag selected";
          tag.setAttribute("data-id", newList.id);
          tag.innerHTML = `<span>✓</span> <span>${escapeHtml(newList.title)}</span>`;
          listContainer.appendChild(tag);
          selectedListIds.add(newList.id);
          newListInput.value = "";
        } else {
          showToast(res?.error || "Failed to create list", true);
        }
      }
    );
  });

  // Save handler
  const saveBtn = backdrop.querySelector("#vistarae-save-btn");
  saveBtn.addEventListener("click", () => {
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    const tagsInput = backdrop.querySelector("#v-tags").value;
    const categoryTags = tagsInput ? tagsInput.split(",").map((s) => s.trim()).filter(Boolean) : [];

    const savePayload = {
      name: backdrop.querySelector("#v-name").value.trim(),
      name_aliases: cand.name_aliases || [],
      poi_type: backdrop.querySelector("#v-type").value,
      personal_rating: currentRating,
      description: backdrop.querySelector("#v-desc").value.trim(),
      category_tags: categoryTags,
      visited: false,
      latitude: data.latitude,
      longitude: data.longitude,
      geofence_radius_ft: 500,
      parent_poi_id: parentPoiId,
      physical_effort: backdrop.querySelector("#v-effort").value.trim(),
      booking_lead_time: backdrop.querySelector("#v-lead").value.trim(),
      indoor_outdoor: backdrop.querySelector("#v-indoor").value,
      estimated_duration: backdrop.querySelector("#v-duration").value.trim(),
      cost_tier: backdrop.querySelector("#v-cost").value.trim(),
      hours_seasonality: cand.hours_seasonality || null,
      best_time_to_visit: backdrop.querySelector("#v-best-time").value.trim(),
      website_official: cand.website_official || originalRequest.page_url,
      primary_image_url: originalRequest.og_image_url || null,
      source_url: originalRequest.page_url,
      source_type: "Web Selection",
      raw_selected_text: originalRequest.selected_text,
      iptc_sublocation: cand.iptc_sublocation || null,
      iptc_city: backdrop.querySelector("#v-city").value.trim() || null,
      iptc_province_state: backdrop.querySelector("#v-state").value.trim() || null,
      iptc_country_code: backdrop.querySelector("#v-country").value.trim().toUpperCase() || "US",
      list_ids: Array.from(selectedListIds),
      access_points: [],
    };

    chrome.runtime.sendMessage(
      { action: "SAVE_POI", payload: savePayload },
      (saveRes) => {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save to Vistarae";

        if (saveRes && saveRes.success) {
          removeModal();
          showToast(`Successfully saved "${savePayload.name}" to your collection!`);
        } else {
          showToast(saveRes?.error || "Failed to commit POI", true);
        }
      }
    );
  });
}

/**
 * Message listener from background worker.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "TRIGGER_CAPTURE") {
    initiateCapture(request.text || null);
    sendResponse({ received: true });
  }
});
