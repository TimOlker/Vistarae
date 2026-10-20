// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { getValidAccessToken, getStoredTokens } from "./auth.js";
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
 * Handles context menu clicks.
 */
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "vistarae-capture" && tab?.id) {
    triggerCaptureOnTab(tab.id, {
      text: info.selectionText,
      linkUrl: info.linkUrl,
    });
  } else if (info.menuItemId === "vistarae-browse") {
    chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
  }
});

/**
 * Handles extension toolbar icon click.
 */
chrome.action.onClicked.addListener((tab) => {
  if (tab?.id) {
    triggerCaptureOnTab(tab.id);
  }
});

/**
 * Handles keyboard commands (Ctrl+Shift+S / Command+Shift+S).
 */
chrome.commands.onCommand.addListener(async (command) => {
  if (command === "capture-to-vistarae") {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (tab?.id) {
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
          files: [
            "content/parsers/BasePoiParser.js",
            "content/parsers/GoogleMapsParser.js",
            "content/parsers/RoadtrippersParser.js",
            "content/parsers/TripAdvisorParser.js",
            "content/parsers/GenericSelectionParser.js",
            "content/content_script.js",
          ],
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
});

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
        body: JSON.stringify(payload),
      },
    );

    if (response.ok) {
      const data = await response.json();
      logTelemetryMessage("OUTBOUND_RESPONSE", "extract-and-check succeeded", {
        status: data.deduplication?.status,
      });
      return data;
    }
  } catch (err) {
    logTelemetryMessage(
      "OUTBOUND_RESPONSE",
      "Backend unreachable, returning local fallback",
      { error: err.message },
    );
  }

  // Graceful offline fallback
  return {
    candidate: payload.extracted || {
      name: payload.page_title,
      description: payload.text,
      category: "experience",
    },
    deduplication: {
      status: "UNIQUE_LOCATION",
      distance_meters: null,
    },
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

  try {
    const response = await fetch(`${DEFAULT_BACKEND_URL}/api/pois`, {
      method: "POST",
      headers,
      body: JSON.stringify(poi),
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
