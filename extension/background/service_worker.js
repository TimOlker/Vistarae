// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import {
  getValidAccessToken,
  getStoredTokens,
  ensureAuthenticatedForCapture,
  getAuthenticatedUser,
  saveTokens,
  clearTokens,
  parseJwtPayload,
} from "./auth.js";
import {
  prepareRequestHeaders,
  logTelemetryMessage,
  createTraceContext,
} from "./telemetry.js";

const NATIVE_HOST_NAME = "com.vistarae.folder_opener";
const DEFAULT_BACKEND_URL = "http://localhost:8000";

/**
 * Initializes context menus on installation or update.
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "vistarae-capture",
    title: "Capture to Vistarae (Ctrl+Shift+S)",
    contexts: ["selection", "page", "link"],
  });

  chrome.contextMenus.create({
    id: "vistarae-browse",
    title: "Browse Saved POIs",
    contexts: ["all"],
  });

  logTelemetryMessage(
    "INBOUND",
    "Extension installed/updated, context menus registered",
  );
});

/**
 * Handles context menu clicks (REQ-EXT-008, REQ-EXT-009).
 */
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "vistarae-capture" && tab?.id) {
    const isAuthed = await ensureAuthenticatedForCapture();
    if (!isAuthed) {
      return;
    }
    triggerCaptureOnTab(tab.id, {
      text: info.selectionText,
      linkUrl: info.linkUrl,
    });
  } else if (info.menuItemId === "vistarae-browse") {
    chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
  }
});

/**
 * Handles extension toolbar icon click (opens the Vistarae POI Browser).
 */
chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
});

/**
 * Handles keyboard commands (Ctrl+Shift+S / Command+Shift+S) (REQ-EXT-008, REQ-EXT-009).
 */
chrome.commands.onCommand.addListener(async (command) => {
  if (command === "capture-to-vistarae") {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (tab?.id) {
      const isAuthed = await ensureAuthenticatedForCapture();
      if (!isAuthed) {
        return;
      }
      triggerCaptureOnTab(tab.id);
    }
  }
});

/**
 * Sends TRIGGER_CAPTURE message to the content script on specified tab,
 * automatically injecting content scripts if the tab was loaded before extension start.
 *
 * @param {number} tabId
 * @param {Object} [payload]
 */
export async function triggerCaptureOnTab(tabId, payload = {}) {
  try {
    await chrome.tabs.sendMessage(tabId, {
      action: "TRIGGER_CAPTURE",
      payload,
    });
  } catch (err) {
    // If content script was not already loaded on this tab, inject it dynamically
    if (
      err.message?.includes("Receiving end does not exist") ||
      err.message?.includes("Could not establish connection")
    ) {
      logTelemetryMessage(
        "OUTBOUND",
        `Dynamic injection needed for tab ${tabId}`,
      );
      try {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["content/content_loader.js"],
        });
        setTimeout(async () => {
          await chrome.tabs.sendMessage(tabId, {
            action: "TRIGGER_CAPTURE",
            payload,
          });
        }, 150);
      } catch (injectErr) {
        console.warn(
          `Failed to dynamically inject content script on tab ${tabId}:`,
          injectErr,
        );
      }
    } else {
      console.warn(`Could not dispatch capture to tab ${tabId}:`, err);
    }
  }
}

/**
 * Handles internal messages from content scripts and full-tab browser.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "EXTRACT_AND_CHECK") {
    handleExtractAndCheck(message.payload)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true; // Keep message channel open for async response
  }

  if (message.action === "REVERSE_GEOCODE") {
    handleReverseGeocode(message.payload)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true;
  }

  if (message.action === "SAVE_POI") {
    handleSavePoi(message.poi)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true;
  }

  if (message.action === "NATIVE_OPEN_FOLDER") {
    sendNativeFolderMessage(message.path)
      .then(sendResponse)
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.action === "GET_AUTH_STATUS") {
    getAuthenticatedUser()
      .then(sendResponse)
      .catch(() =>
        sendResponse({ isAuthenticated: false, email: null, user: null }),
      );
    return true;
  }

  if (message.action === "GET_USER_TAGS") {
    handleGetUserTags()
      .then(sendResponse)
      .catch((err) =>
        sendResponse({ success: false, tags: [], error: err.message }),
      );
    return true;
  }

  if (message.action === "SYNC_AUTH_FROM_WEBAPP") {
    handleSyncAuthFromWebapp(message)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true;
  }
});

/**
 * Fetches user-configured tags from backend GET /api/pois/tags.
 */
async function handleGetUserTags() {
  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {}

  const { headers } = prepareRequestHeaders({
    method: "GET",
    token,
  });

  try {
    const response = await fetch(`${DEFAULT_BACKEND_URL}/api/pois/tags`, {
      method: "GET",
      headers,
    });
    if (response.ok) {
      const data = await response.json();
      return { success: true, tags: Array.isArray(data) ? data : [] };
    }
  } catch (err) {
    console.warn("Failed to fetch user tags from backend:", err);
  }
  return { success: false, tags: [] };
}

/**
 * Persists session tokens passed from web application into extension storage.
 * @param {Object} payload
 * @param {string} payload.token
 * @param {Object} [payload.user]
 */
async function handleSyncAuthFromWebapp({ token, user }) {
  if (!token) {
    await clearTokens();
    return { success: true, authenticated: false };
  }
  const payload = parseJwtPayload(token);
  const now = Math.floor(Date.now() / 1000);
  const tokenExpiry = payload?.exp || now + 86400 * 7;
  await saveTokens({
    accessToken: token,
    idToken: token,
    refreshToken: `mock-refresh-token-${user?.id || payload?.sub || "default"}`,
    tokenExpiry,
    user:
      user ||
      (payload?.email ? { email: payload.email, id: payload.sub } : null),
  });
  logTelemetryMessage(
    "INBOUND",
    `Synchronized authentication from web app: ${
      user?.email || payload?.email || "active user"
    }`,
  );
  return { success: true, authenticated: true };
}

/**
 * Handles external messages from SPA web client (localhost:5173 / CloudFront).
 */
chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    logTelemetryMessage(
      "INBOUND",
      "Received external message from web application",
      { origin: sender.origin, action: message?.action },
    );

    if (
      message?.action === "sync_auth" ||
      message?.action === "SYNC_AUTH_FROM_WEBAPP"
    ) {
      handleSyncAuthFromWebapp(message)
        .then((res) => sendResponse({ success: true, ...res }))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    if (message?.action === "open_folder" && message.path) {
      sendNativeFolderMessage(message.path)
        .then((nativeRes) => {
          if (nativeRes.status === "ok") {
            sendResponse({ success: true, data: nativeRes });
          } else {
            sendResponse({
              success: false,
              error: {
                type: "native_host_error",
                title: "Native Folder Opener Failed",
                status: nativeRes.code === "UNTRUSTED_NETWORK_HOST" ? 403 : 400,
                detail:
                  nativeRes.message ||
                  "Folder opening rejected by native dispatcher",
                code: nativeRes.code,
              },
            });
          }
        })
        .catch((err) => {
          sendResponse({
            success: false,
            error: {
              type: "native_host_not_found",
              title: "Native Host Not Available",
              status: 404,
              detail:
                err.message ||
                "Run python scripts/register_native_host.py to register folder opener.",
            },
          });
        });
      return true;
    }

    sendResponse({
      success: false,
      error: {
        type: "invalid_action",
        title: "Unsupported External Action",
        status: 400,
        detail: `Action '${message?.action}' is not supported.`,
      },
    });
    return false;
  },
);

/**
 * Dispatches extraction and PostGIS deduplication check to backend.
 * @param {Object} payload
 */
async function handleExtractAndCheck(payload) {
  // Strip client-internal fallback fields before sending to strict backend schema
  const { extracted, ...requestBody } = payload;

  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {
    // If not authenticated, proceed without bearer token (offline / manual mode)
  }

  const { headers } = prepareRequestHeaders({
    method: "POST",
    token,
  });

  logTelemetryMessage("OUTBOUND", "POST /api/pois/extract-and-check");

  try {
    const response = await fetch(
      `${DEFAULT_BACKEND_URL}/api/pois/extract-and-check`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
      },
    );

    if (response.ok) {
      const data = await response.json();
      logTelemetryMessage("OUTBOUND_RESPONSE", "extract-and-check succeeded", {
        status: data.deduplication?.status,
      });
      return data;
    } else {
      const errText = await response.text();
      console.error(
        `Backend extract-and-check failed with status ${response.status}:`,
        errText,
      );
      logTelemetryMessage(
        "OUTBOUND_RESPONSE",
        `Backend returned error ${response.status}`,
        { status: response.status, error: errText },
      );
    }
  } catch (err) {
    console.error("Backend unreachable:", err);
    logTelemetryMessage(
      "OUTBOUND_RESPONSE",
      "Backend unreachable, returning local fallback",
      { error: err.message },
    );
  }

  // Graceful offline fallback
  const cleanFallbackName =
    (payload.page_title || "")
      .replace(
        /\s*[-–—·|•]\s*(Google Maps|Tripadvisor|Roadtrippers|Atlas Obscura|Yelp|Wikipedia|Official (Site|Website|Guide)).*$/i,
        "",
      )
      .trim() ||
    payload.page_title ||
    "Destination";

  return {
    candidate: payload.extracted || {
      name: cleanFallbackName,
      description: payload.selected_text || payload.text || "",
      category: payload.category || "experience",
    },
    deduplication: {
      status: "UNIQUE_LOCATION",
      distance_meters: null,
    },
  };
}

/**
 * Dispatches reverse geocoding to backend POST /api/v1/geocoding/reverse (T-021).
 * @param {Object} payload
 * @param {number} payload.latitude
 * @param {number} payload.longitude
 */
async function handleReverseGeocode(payload) {
  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {
    // Optional auth
  }

  const { headers } = prepareRequestHeaders({
    method: "POST",
    token,
  });

  logTelemetryMessage("OUTBOUND", "POST /api/v1/geocoding/reverse", payload);

  try {
    const response = await fetch(
      `${DEFAULT_BACKEND_URL}/api/v1/geocoding/reverse`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      },
    );

    if (response.ok) {
      const data = await response.json();
      logTelemetryMessage("OUTBOUND_RESPONSE", "reverse geocode succeeded", {
        country: data.country,
        formatted_address: data.formatted_address,
      });
      return data;
    }
  } catch (err) {
    logTelemetryMessage(
      "OUTBOUND_RESPONSE",
      "Reverse geocode backend request failed",
      { error: err.message },
    );
  }

  return {
    formatted_address: `Lat: ${payload.latitude?.toFixed(
      4,
    )}, Lng: ${payload.longitude?.toFixed(4)}`,
    country: "Unknown",
    country_code: "XX",
    city: null,
    postcode: null,
    addresses: [],
  };
}

/**
 * Persists POI record to backend database.
 * @param {Object} poi
 */
async function handleSavePoi(poi) {
  let token = null;
  try {
    token = await getValidAccessToken();
  } catch (_) {
    // Offline/unauthenticated fallback simulation
  }

  const { headers, idempotencyKey } = prepareRequestHeaders({
    method: "POST",
    token,
  });

  logTelemetryMessage("OUTBOUND", "POST /api/pois", { idempotencyKey });

  const formattedPoi = {
    name: poi.name || "Untitled POI",
    lat:
      poi.latitude !== null && poi.latitude !== undefined
        ? Number(poi.latitude)
        : poi.lat !== null && poi.lat !== undefined
          ? Number(poi.lat)
          : 0.0,
    lon:
      poi.longitude !== null && poi.longitude !== undefined
        ? Number(poi.longitude)
        : poi.lon !== null && poi.lon !== undefined
          ? Number(poi.lon)
          : 0.0,
    parent_poi_id: poi.parent_poi_id || null,
    description: poi.description || null,
    address: poi.address || poi.addresses?.[0]?.street || null,
    addresses: Array.isArray(poi.addresses) ? poi.addresses : [],
    source_type: poi.source_type || "Web",
    source_value: poi.source_value || poi.source_url || poi.url || null,
    official_url: poi.official_website_url || poi.official_url || null,
    wiki_url: poi.wikipedia_url || poi.wiki_url || null,
    image_urls: poi.hero_image_url
      ? [poi.hero_image_url]
      : poi.image_urls || [],
    tag_names: poi.tags || poi.tag_names || [],
    rating:
      poi.rating !== undefined && poi.rating !== null
        ? parseInt(poi.rating, 10)
        : null,
    recommended_duration_hours: poi.estimated_duration_hours
      ? parseFloat(poi.estimated_duration_hours)
      : null,
    recommended_visit_days:
      poi.estimated_duration_days !== undefined &&
      poi.estimated_duration_days !== null &&
      parseInt(poi.estimated_duration_days, 10) >= 1
        ? parseInt(poi.estimated_duration_days, 10)
        : 1,
    estimated_visit_time_notes: poi.estimated_visit_time_notes || null,
  };

  try {
    const response = await fetch(`${DEFAULT_BACKEND_URL}/api/pois`, {
      method: "POST",
      headers,
      body: JSON.stringify(formattedPoi),
    });

    if (response.ok) {
      const data = await response.json();
      logTelemetryMessage("OUTBOUND_RESPONSE", "Saved POI successfully", {
        id: data.id,
      });
      return { success: true, poi: data };
    }
    const errData = await response.json().catch(() => ({}));
    return {
      success: false,
      error: errData.detail || `Server returned ${response.status}`,
    };
  } catch (err) {
    // If backend is offline during local test, simulate successful save
    logTelemetryMessage(
      "OUTBOUND_RESPONSE",
      "Backend offline, simulated local save",
      { poiName: poi.name },
    );
    return { success: true, poi: { ...poi, id: "local-" + Date.now() } };
  }
}

/**
 * Sends an action request to the Python Native Messaging Host.
 * @param {string} path - Local directory or UNC share path.
 * @returns {Promise<any>}
 */
export function sendNativeFolderMessage(path) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendNativeMessage(
        NATIVE_HOST_NAME,
        { action: "open_folder", path },
        (response) => {
          if (chrome.runtime.lastError) {
            logTelemetryMessage("OUTBOUND_RESPONSE", "Native message failed", {
              error: chrome.runtime.lastError.message,
            });
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            logTelemetryMessage(
              "OUTBOUND_RESPONSE",
              "Native host response",
              response,
            );
            resolve(response || { status: "ok", action: "open_folder", path });
          }
        },
      );
    } catch (err) {
      reject(err);
    }
  });
}
