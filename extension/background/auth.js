// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

import { logTelemetryMessage } from "./telemetry.js";

// Default configuration constants (can be overridden via chrome.storage.sync)
export const DEFAULT_CONFIG = {
  cognitoRegion: "us-east-1",
  cognitoClientId: "1exampleclientidforvistarae",
  backendUrl: "http://localhost:8000",
  refreshMarginSeconds: 300, // 5 minutes pre-flight window
};

/**
 * In-memory single-flight mutex promise for concurrent token refreshes.
 * Shared across all simultaneous requests within this Service Worker lifecycle.
 * @type {Promise<string> | null}
 */
let refreshPromise = null;

/**
 * Parses JWT payload without external library dependencies.
 * @param {string} token - Encoded JWT string.
 * @returns {Record<string, any> | null} Decoded payload or null if invalid.
 */
export function parseJwtPayload(token) {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    );
    return JSON.parse(jsonPayload);
  } catch (err) {
    console.warn("Failed to parse JWT payload", err);
    return null;
  }
}

/**
 * Retrieves active authentication credentials from chrome.storage.local.
 * @returns {Promise<{ accessToken?: string, idToken?: string, refreshToken?: string, tokenExpiry?: number, user?: any }>}
 */
export async function getStoredTokens() {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    const data = await chrome.storage.local.get([
      "accessToken",
      "idToken",
      "refreshToken",
      "tokenExpiry",
      "user",
    ]);
    return data || {};
  }
  return {};
}

/**
 * Persists updated tokens to chrome.storage.local.
 * @param {Object} tokens
 * @param {string} tokens.accessToken
 * @param {string} tokens.idToken
 * @param {string} [tokens.refreshToken]
 * @param {number} tokens.tokenExpiry
 * @param {Object} [tokens.user]
 */
export async function saveTokens(tokens) {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    await chrome.storage.local.set(tokens);
    broadcastAuthState({ isAuthenticated: true, user: tokens.user });
  }
}

/**
 * Clears stored tokens on explicit logout or permanent revocation.
 */
export async function clearTokens() {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    await chrome.storage.local.remove([
      "accessToken",
      "idToken",
      "refreshToken",
      "tokenExpiry",
      "user",
    ]);
    broadcastAuthState({ isAuthenticated: false, user: null });
  }
}

/**
 * Broadcasts authentication state changes to other extension contexts (popups, side panels, tabs).
 * @param {{ isAuthenticated: boolean, user: any }} state
 */
export function broadcastAuthState(state) {
  if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
    try {
      chrome.runtime
        .sendMessage({
          action: "AUTH_STATE_CHANGED",
          ...state,
        })
        .catch(() => {
          // Ignored if no receiver is active
        });
    } catch (_) {
      // Runtime context might not be available in unit tests
    }
  }
}

/**
 * Retrieves the current active access token, executing a single-flight silent refresh
 * if the token is within 5 minutes of expiration or already expired.
 *
 * @param {Object} [overrideConfig]
 * @returns {Promise<string>} Valid JWT Access Token
 */
export async function getValidAccessToken(overrideConfig = {}) {
  const config = { ...DEFAULT_CONFIG, ...overrideConfig };
  const tokens = await getStoredTokens();

  if (!tokens.accessToken || !tokens.refreshToken) {
    throw new Error("NO_STORED_CREDENTIALS");
  }

  // Pre-flight check: evaluate exp claim against current time + margin
  const now = Math.floor(Date.now() / 1000);
  const expiry =
    tokens.tokenExpiry || parseJwtPayload(tokens.accessToken)?.exp || 0;
  const isExpiringSoon = now >= expiry - config.refreshMarginSeconds;

  if (!isExpiringSoon) {
    return tokens.accessToken;
  }

  // If a refresh is already in-flight, await the identical promise (single-flight mutex)
  if (refreshPromise) {
    logTelemetryMessage(
      "INBOUND",
      "Awaiting existing in-flight token refresh promise",
    );
    return refreshPromise;
  }

  // Initiate single-flight refresh operation
  logTelemetryMessage(
    "OUTBOUND",
    "Initiating silent token refresh via Cognito REFRESH_TOKEN_AUTH",
  );
  refreshPromise = (async () => {
    try {
      const newAccessToken = await executeCognitoRefresh(
        tokens.refreshToken,
        config,
      );
      return newAccessToken;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Performs Cognito InitiateAuth network request with REFRESH_TOKEN_AUTH.
 * Handles transient network retries and permanent revocation.
 *
 * @param {string} refreshToken
 * @param {typeof DEFAULT_CONFIG} config
 * @returns {Promise<string>} Fresh access token
 */
export async function executeCognitoRefresh(refreshToken, config) {
  const endpoint = `https://cognito-idp.${config.cognitoRegion}.amazonaws.com/`;
  const payload = {
    AuthFlow: "REFRESH_TOKEN_AUTH",
    ClientId: config.cognitoClientId,
    AuthParameters: {
      REFRESH_TOKEN: refreshToken,
    },
  };

  let attempts = 0;
  const maxAttempts = 3;

  while (attempts < maxAttempts) {
    attempts++;
    try {
      logTelemetryMessage(
        "OUTBOUND",
        `Cognito InitiateAuth attempt ${attempts}/${maxAttempts}`,
      );
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-amz-json-1.1",
          "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        const result = data.AuthenticationResult;
        if (!result?.AccessToken) {
          throw new Error("MALFORMED_AUTH_RESPONSE");
        }

        const expiresIn = result.ExpiresIn || 3600;
        const now = Math.floor(Date.now() / 1000);
        const tokenExpiry = now + expiresIn;

        const updatedTokens = {
          accessToken: result.AccessToken,
          idToken: result.IdToken || (await getStoredTokens()).idToken,
          refreshToken: result.RefreshToken || refreshToken, // RefreshToken may be rotated
          tokenExpiry,
        };

        await saveTokens(updatedTokens);
        logTelemetryMessage(
          "OUTBOUND_RESPONSE",
          "Silent token refresh succeeded",
          { expiresIn },
        );
        return result.AccessToken;
      }

      // Check for permanent 400 errors (token revoked / expired)
      if (response.status === 400) {
        const errorData = await response.json().catch(() => ({}));
        logTelemetryMessage(
          "OUTBOUND_RESPONSE",
          "Cognito rejected refresh token (permanent)",
          errorData,
        );
        await clearTokens();
        throw new Error("TOKEN_REVOKED");
      }

      // Transient 5xx or rate limit: wait and retry
      logTelemetryMessage(
        "OUTBOUND_RESPONSE",
        `Cognito returned HTTP ${response.status}, retrying...`,
      );
      if (attempts >= maxAttempts) {
        throw new Error(`COGNITO_ERROR_${response.status}`);
      }
      await new Promise((r) => setTimeout(r, Math.pow(2, attempts) * 300));
    } catch (err) {
      if (err.message === "TOKEN_REVOKED") {
        throw err;
      }
      if (attempts >= maxAttempts) {
        logTelemetryMessage(
          "OUTBOUND_RESPONSE",
          "Silent token refresh failed after retries (transient network error)",
          { error: err.message },
        );
        throw err;
      }
      await new Promise((r) => setTimeout(r, Math.pow(2, attempts) * 300));
    }
  }

  throw new Error("TOKEN_REFRESH_MAX_RETRIES_EXCEEDED");
}
