/**
 * Vistarae Chrome Extension Background Service Worker (Manifest V3)
 * Implements W3C Distributed Tracing, JWT Authentication, Context Menu, Hotkeys, and API dispatching.
 */

const DEFAULT_BACKEND_URL = "http://localhost:8000";

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
    "X-Source": "chrome-extension://vistarae",
    "X-Destination": targetUrl,
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
    title: "Capture to Vistarae",
    contexts: ["selection"],
  });
  console.log("Vistarae extension installed. Context menu registered.");
});

/**
 * Context Menu Click Listener.
 */
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "vistarae-capture-selection" && tab?.id) {
    logMsg(TAG_INBOUND_MSG, `[SW] Context menu capture triggered on tab ${tab.id}`);
    chrome.tabs.sendMessage(tab.id, { action: "TRIGGER_CAPTURE", text: info.selectionText });
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
        chrome.tabs.sendMessage(tabs[0].id, { action: "TRIGGER_CAPTURE" });
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
    "X-Source": traceInfo["X-Source"],
    "X-Destination": traceInfo["X-Destination"],
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
  };
  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(targetUrl, fetchOptions);
    const responseData = await response.json();

    const currentSpanId = response.headers.get("X-Current-Span-ID") || "unknown";
    logMsg(
      TAG_OUTBOUND_RESP,
      `[SW] HTTP ${response.status} ${targetUrl} | TraceID=${traceInfo.traceId} ServerSpanID=${currentSpanId}`
    );

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

  return false;
});
