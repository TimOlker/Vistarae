// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

/**
 * Generates a random hexadecimal string of specified byte length.
 * @param {number} bytes - Number of bytes to generate.
 * @returns {string} Hexadecimal string representation.
 */
export function generateHex(bytes) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Generates a standard RFC 4122 version 4 UUID.
 * @returns {string} UUIDv4 string.
 */
export function generateUuidV4() {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const hex = generateHex(16);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(
    13,
    16,
  )}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

/**
 * Creates standard W3C distributed tracing context headers.
 * Format: 00-{trace_id}-{client_span_id}-01
 *
 * @param {string} [existingTraceId] - Optional parent trace ID to correlate with.
 * @returns {{ traceId: string, spanId: string, headers: Record<string, string> }}
 */
export function createTraceContext(existingTraceId) {
  const traceId = existingTraceId || generateHex(16);
  const spanId = generateHex(8);
  const traceparent = `00-${traceId}-${spanId}-01`;

  return {
    traceId,
    spanId,
    headers: {
      traceparent,
      "X-Source": "extension",
      "X-Destination": "backend",
    },
  };
}

/**
 * Prepares HTTP request headers with W3C tracing, tenant authorization, and idempotency keys.
 *
 * @param {Object} options
 * @param {string} options.method - HTTP method (GET, POST, etc.)
 * @param {string} [options.token] - Bearer access token
 * @param {string} [options.traceId] - Existing trace ID
 * @param {string} [options.idempotencyKey] - Custom idempotency key (auto-generated if mutating)
 * @param {Record<string, string>} [options.customHeaders] - Additional custom headers
 * @returns {{ headers: Headers, traceId: string, spanId: string, idempotencyKey?: string }}
 */
export function prepareRequestHeaders({
  method = "GET",
  token,
  traceId,
  idempotencyKey,
  customHeaders = {},
}) {
  const ctx = createTraceContext(traceId);
  const headers = new Headers({
    ...ctx.headers,
    "Content-Type": "application/json",
    Accept: "application/json",
    ...customHeaders,
  });

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const isMutating = ["POST", "PUT", "PATCH", "DELETE"].includes(
    method.toUpperCase(),
  );
  let finalIdempotencyKey;
  if (isMutating) {
    finalIdempotencyKey = idempotencyKey || generateUuidV4();
    headers.set("Idempotency-Key", finalIdempotencyKey);
  }

  return {
    headers,
    traceId: ctx.traceId,
    spanId: ctx.spanId,
    idempotencyKey: finalIdempotencyKey,
  };
}

/**
 * Logs a message according to the Vistarae standard messaging protocol.
 * - Outbound message sent: MSG   |->
 * - Response received from outbound: MSG   |<-
 * - Inbound message received: MSG ->|
 * - Response sent to inbound: MSG <-|
 *
 * @param {'OUTBOUND' | 'OUTBOUND_RESPONSE' | 'INBOUND' | 'INBOUND_RESPONSE'} direction
 * @param {string} summary
 * @param {Object} [details]
 */
export function logTelemetryMessage(direction, summary, details = {}) {
  let tag;
  switch (direction) {
    case "OUTBOUND":
      tag = "MSG   |->";
      break;
    case "OUTBOUND_RESPONSE":
      tag = "MSG   |<-";
      break;
    case "INBOUND":
      tag = "MSG ->|  ";
      break;
    case "INBOUND_RESPONSE":
      tag = "MSG <-|  ";
      break;
    default:
      tag = "MSG |";
  }

  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${tag} ${summary}`, details);
}
