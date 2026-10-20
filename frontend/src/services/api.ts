// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

export interface ProblemDetails {
  type?: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  invalid_params?: Array<{
    name: string;
    reason: string;
  }>;
  retryAfterSeconds?: number;
}

export class ApiError extends Error {
  public problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || `API Error (${problem.status})`);
    this.name = "ApiError";
    this.problem = problem;
  }
}

/**
 * Generates a standard W3C traceparent header value.
 * Format: 00-{trace_id_32_hex}-{span_id_16_hex}-01
 */
export function generateTraceparent(): {
  traceparent: string;
  traceId: string;
  spanId: string;
} {
  const randomHex = (bytes: number) => {
    const arr = new Uint8Array(bytes);
    crypto.getRandomValues(arr);
    return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
  };

  const traceId = randomHex(16); // 32 hex chars
  const spanId = randomHex(8); // 16 hex chars
  const traceparent = `00-${traceId}-${spanId}-01`;

  return { traceparent, traceId, spanId };
}

export interface ApiRequestOptions extends RequestInit {
  idempotencyKey?: string;
  skipAuth?: boolean;
}

/**
 * Typed HTTP fetch wrapper enforcing W3C tracing, idempotency keys, and RFC 7807 ProblemDetails mapping.
 */
export async function apiFetch<T = unknown>(
  endpoint: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { traceparent, traceId } = generateTraceparent();

  const headers = new Headers(options.headers || {});
  headers.set("X-Source", "web-client");
  headers.set("X-Destination", "backend");
  headers.set("traceparent", traceparent);
  headers.set("X-Vistarae-Trace-Id", traceId);

  // Inject Authorization Bearer token or local mock user headers
  const token = localStorage.getItem("vistarae_auth_token");
  if (token && !options.skipAuth) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const mockUserId = localStorage.getItem("vistarae_mock_user_id");
  if (mockUserId && !options.skipAuth) {
    headers.set("X-Mock-User-Id", mockUserId);
    const mockTier = localStorage.getItem("vistarae_mock_user_tier") || "LOW";
    headers.set("X-Mock-User-Tier", mockTier);
  }

  // Idempotency key on mutating requests
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    if (!headers.has("Idempotency-Key")) {
      headers.set(
        "Idempotency-Key",
        options.idempotencyKey || crypto.randomUUID(),
      );
    }
  }

  if (
    !headers.has("Content-Type") &&
    options.body &&
    !(options.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let problem: ProblemDetails;
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfterSeconds = retryAfterHeader
      ? parseInt(retryAfterHeader, 10)
      : undefined;

    try {
      const data = await response.json();
      problem = {
        type: data.type || "about:blank",
        title: data.title || response.statusText || "Error",
        status: data.status || response.status,
        detail: data.detail || "An unexpected error occurred.",
        instance: data.instance,
        invalid_params: data.invalid_params,
        retryAfterSeconds,
      };
    } catch {
      // Non-JSON fallback (e.g. 502/504 HTML error from reverse proxy)
      problem = {
        type: "about:blank",
        title: response.statusText || "HTTP Error",
        status: response.status,
        detail: `Server returned an error status ${response.status} (${response.statusText}).`,
        retryAfterSeconds,
      };
    }

    throw new ApiError(problem);
  }

  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json() as Promise<T>;
}
