// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { getAuthenticatedUser, DEFAULT_CONFIG } from "../background/auth.js";
import { logTelemetryMessage } from "../background/telemetry.js";

const BACKEND_URL = DEFAULT_CONFIG.backendUrl || "http://localhost:8000";
const WEBAPP_URL = DEFAULT_CONFIG.webappUrl || "http://localhost:5173";

/**
 * Updates UI with current authentication context (REQ-EXT-010).
 */
async function updateAuthContext() {
  const userEmailEl = document.getElementById("user-email");
  const userStatusBadge = document.getElementById("user-status-badge");
  const authStatusBadge = document.getElementById("auth-status-badge");

  try {
    const authContext = await getAuthenticatedUser();
    if (authContext.isAuthenticated && authContext.email) {
      if (userEmailEl) userEmailEl.textContent = authContext.email;
      if (userStatusBadge) {
        userStatusBadge.textContent = "Authenticated";
        userStatusBadge.className = "badge badge-success";
      }
      if (authStatusBadge) {
        authStatusBadge.textContent = "Signed In";
        authStatusBadge.className = "badge badge-success";
      }
    } else {
      if (userEmailEl) userEmailEl.textContent = "Not logged in";
      if (userStatusBadge) {
        userStatusBadge.textContent = "Guest";
        userStatusBadge.className = "badge badge-neutral";
      }
      if (authStatusBadge) {
        authStatusBadge.textContent = "Not Authenticated";
        authStatusBadge.className = "badge badge-warning";
      }
    }
  } catch (err) {
    if (userEmailEl) userEmailEl.textContent = "Guest Session";
    if (userStatusBadge) {
      userStatusBadge.textContent = "Offline";
      userStatusBadge.className = "badge badge-neutral";
    }
  }
}

/**
 * Checks backend API connectivity (REQ-EXT-013).
 */
async function checkBackendStatus() {
  const serverStatus = document.getElementById("server-status");
  if (!serverStatus) return;

  try {
    const res = await fetch(`${BACKEND_URL}/health/live`, { method: "GET" });
    if (res.ok) {
      serverStatus.textContent = "Connected";
      serverStatus.className = "badge badge-success";
    } else {
      serverStatus.textContent = "Degraded";
      serverStatus.className = "badge badge-warning";
    }
  } catch (err) {
    serverStatus.textContent = "Offline";
    serverStatus.className = "badge badge-danger";
  }
}

/**
 * Opens the Vistarae Web App in a new browser tab (REQ-EXT-013).
 */
function openWebApp() {
  if (typeof chrome !== "undefined" && chrome.tabs?.create) {
    chrome.tabs.create({ url: WEBAPP_URL });
  } else {
    window.open(WEBAPP_URL, "_blank");
  }
}

// --- Initialization & Event Bindings ---
document.addEventListener("DOMContentLoaded", () => {
  updateAuthContext();
  checkBackendStatus();

  const openWebAppBtn = document.getElementById("btn-open-webapp");
  openWebAppBtn?.addEventListener("click", openWebApp);
});
