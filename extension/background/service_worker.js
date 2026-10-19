/**
 * Vistarae Chrome Extension Background Service Worker (Manifest V3)
 * Implements W3C Distributed Tracing, JWT Authentication, Context Menu, Hotkeys, and API dispatching.
 */

const DEFAULT_BACKEND_URL = "http://localhost:8030";

// Messaging tags protocol
const TAG_INBOUND_MSG = "->|  ";
const TAG_RESPONSE_MSG = "<-|  ";
const TAG_OUTBOUND_MSG = "  |->";
const TAG_OUTBOUND_RESP = "  |<-";

function logMsg(tag, detail) {
  console.log(`MSG ${tag}${detail}`);
}

/**
 * Generates random hexadecimal string for W3C Trace Context.
 */
function randomHex(length) {
  const bytes = new Uint8Array(length / 2);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Creates W3C Trace Context headers.
 */
function createTraceHeaders(targetUrl) {
  const traceId = randomHex(32);
  const spanId = randomHex(16);
  return {
    traceparent: `00-${traceId}-${spanId}-01`,
    "X-Source": "extension",
    "X-Destination": "backend",
    traceId,
    spanId,
  };
}

/**
 * Setup Context Menu on extension install.
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "vistarae-capture-selection",
    title: "Capture to Vistarae (Ctrl+Shift+S)",
    contexts: ["selection", "page", "link"],
  });
  chrome.contextMenus.create({
    id: "vistarae-browse-pois",
    title: "Browse Saved POIs",
    contexts: ["all"],
  });
  console.log("Vistarae extension installed. Context menu registered.");
});

/**
 * Extension Action Icon Click Listener (toolbar icon opens browser tab).
 */
chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
});

/**
 * Safely dispatches a message to a content script tab.
 * If the tab was loaded before extension install/reload, dynamically injects content_script.js.
 */
async function sendMessageToTab(tabId, message) {
  try {
    await chrome.tabs.sendMessage(tabId, message);
  } catch (err) {
    if (
      err.message?.includes("Receiving end does not exist") ||
      err.message?.includes("Could not establish connection")
    ) {
      logMsg(TAG_INBOUND_MSG, `[SW] Content script missing on tab ${tabId}. Dynamically injecting content_script.js...`);
      try {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["content/content_script.js"],
        });
        // Wait briefly for listener initialization
        setTimeout(() => {
          chrome.tabs.sendMessage(tabId, message).catch((retryErr) => {
            console.warn("[SW] Retry message failed:", retryErr.message);
          });
        }, 150);
      } catch (injectErr) {
        console.warn(`[SW] Could not dynamically inject script into tab ${tabId}:`, injectErr.message);
      }
    } else {
      console.warn(`[SW] Error dispatching message to tab ${tabId}:`, err.message);
    }
  }
}

/**
 * Context Menu Click Listener.
 */
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "vistarae-browse-pois") {
    chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
  } else if (info.menuItemId === "vistarae-capture-selection" && tab?.id) {
    logMsg(TAG_INBOUND_MSG, `[SW] Context menu capture triggered on tab ${tab.id}`);
    const captureText = info.linkUrl || info.selectionText || null;
    sendMessageToTab(tab.id, { action: "TRIGGER_CAPTURE", text: captureText });
  }
});

/**
 * Keyboard Command Listener (Ctrl+Shift+S / Cmd+Shift+S).
 */
chrome.commands.onCommand.addListener((command) => {
  if (command === "capture-to-vistarae") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        logMsg(TAG_INBOUND_MSG, `[SW] Keyboard shortcut triggered capture on tab ${tabs[0].id}`);
        sendMessageToTab(tabs[0].id, { action: "TRIGGER_CAPTURE" });
      }
    });
  }
});


/**
 * API Dispatcher with W3C Tracing and Bearer Token Injection.
 */
async function dispatchApiRequest(endpoint, method, body = null) {
  const settings = await chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND_URL });
  const backendUrl = settings.backendUrl.replace(/\/$/, "");
  const targetUrl = `${backendUrl}${endpoint}`;

  // Retrieve stored JWT token
  const authData = await chrome.storage.local.get(["auth_token", "user"]);
  const token = authData.auth_token;

  const traceInfo = createTraceHeaders(targetUrl);
  const headers = {
    "Content-Type": "application/json",
    traceparent: traceInfo.traceparent,
    "X-Source": "extension",
    "X-Destination": "backend",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  logMsg(
    TAG_OUTBOUND_MSG,
    `[SW] HTTP ${method} ${targetUrl} | TraceID=${traceInfo.traceId} SpanID=${traceInfo.spanId}`
  );

  const fetchOptions = {
    method,
    headers,
    cache: "no-store",
  };
  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(targetUrl, fetchOptions);

    const currentSpanId = response.headers.get("X-Current-Span-ID") || "unknown";
    logMsg(
      TAG_OUTBOUND_RESP,
      `[SW] HTTP ${response.status} ${targetUrl} | TraceID=${traceInfo.traceId} ServerSpanID=${currentSpanId}`
    );

    if (response.status === 204) {
      return { success: true, data: null };
    }

    let responseData = null;
    const text = await response.text();
    if (text) {
      try {
        responseData = JSON.parse(text);
      } catch (parseErr) {
        responseData = { detail: text };
      }
    }

    if (response.status === 401) {
      return { success: false, unauthorized: true, error: responseData?.detail || "Authentication required." };
    }

    if (!response.ok) {
      throw new Error(responseData?.detail || `API error: ${response.status}`);
    }

    return { success: true, data: responseData };
  } catch (error) {
    logMsg(
      TAG_OUTBOUND_RESP,
      `[SW] HTTP ERROR ${targetUrl} | Error=${error.message}`
    );
    return { success: false, error: error.message };
  }
}

/**
 * Handle incoming messages from Content Script.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  logMsg(TAG_INBOUND_MSG, `[SW] Received message action: ${message.action}`);

  // 1. Authentication Handlers
  if (message.action === "LOGIN") {
    dispatchApiRequest("/api/v1/auth/login", "POST", message.payload)
      .then(async (res) => {
        if (res.success && res.data?.access_token) {
          await chrome.storage.local.set({
            auth_token: res.data.access_token,
            user: res.data.user,
          });
        }
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "REGISTER") {
    dispatchApiRequest("/api/v1/auth/register", "POST", message.payload)
      .then(async (res) => {
        if (res.success && res.data?.access_token) {
          await chrome.storage.local.set({
            auth_token: res.data.access_token,
            user: res.data.user,
          });
        }
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "GET_AUTH") {
    chrome.storage.local.get(["auth_token", "user"]).then((data) => {
      sendResponse({
        isAuthenticated: !!data.auth_token,
        user: data.user || null,
      });
    });
    return true;
  }

  if (message.action === "LOGOUT") {
    chrome.storage.local.remove(["auth_token", "user"]).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }

  // 2. Data & Capture Handlers
  if (message.action === "EXTRACT_AND_CHECK") {
    dispatchApiRequest("/api/v1/extract-and-check", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending EXTRACT_AND_CHECK response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "SAVE_POI") {
    dispatchApiRequest("/api/v1/pois", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending SAVE_POI response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "CREATE_LIST") {
    dispatchApiRequest("/api/v1/lists", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending CREATE_LIST response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "GET_LISTS") {
    dispatchApiRequest("/api/v1/lists", "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending GET_LISTS response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "GET_TAGS") {
    dispatchApiRequest("/api/v1/tags", "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending GET_TAGS response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "CREATE_TAG") {
    dispatchApiRequest("/api/v1/tags", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending CREATE_TAG response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  // 3. POI Browser Handlers
  if (message.action === "OPEN_BROWSER") {
    chrome.tabs.create({ url: chrome.runtime.getURL("browser/browser.html") });
    sendResponse({ success: true });
    return true;
  }

  if (message.action === "OPEN_TAB") {
    chrome.tabs.create({ url: message.url });
    sendResponse({ success: true });
    return true;
  }

  if (message.action === "GET_POIS") {
    const params = new URLSearchParams();
    if (message.payload) {
      for (const [key, value] of Object.entries(message.payload)) {
        if (value !== undefined && value !== null && value !== "") {
          params.append(key, value);
        }
      }
    }
    const qs = params.toString() ? `?${params.toString()}` : "";
    dispatchApiRequest(`/api/v1/pois${qs}`, "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending GET_POIS response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "GET_POI") {
    dispatchApiRequest(`/api/v1/pois/${message.payload.id}`, "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending GET_POI response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "UPDATE_POI") {
    dispatchApiRequest(`/api/v1/pois/${message.payload.id}`, "PUT", message.payload.data)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending UPDATE_POI response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "DELETE_POI") {
    dispatchApiRequest(`/api/v1/pois/${message.payload.id}`, "DELETE")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending DELETE_POI response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "BULK_DELETE_POIS") {
    dispatchApiRequest("/api/v1/pois/bulk-delete", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending BULK_DELETE_POIS response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "BULK_UPDATE_POIS") {
    dispatchApiRequest("/api/v1/pois/bulk-update", "POST", message.payload)
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending BULK_UPDATE_POIS response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  // 4. Geocoding Handlers
  if (message.action === "REVERSE_GEOCODE") {
    const lat = message.payload?.latitude;
    const lng = message.payload?.longitude;
    dispatchApiRequest(`/api/v1/reverse-geocode?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lng)}`, "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending REVERSE_GEOCODE response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  if (message.action === "GEOCODE_QUERY") {
    const query = message.payload?.query || "";
    dispatchApiRequest(`/api/v1/geocode?query=${encodeURIComponent(query)}`, "GET")
      .then((res) => {
        logMsg(TAG_RESPONSE_MSG, `[SW] Sending GEOCODE_QUERY response (success=${res.success})`);
        sendResponse(res);
      });
    return true;
  }

  return false;
});

