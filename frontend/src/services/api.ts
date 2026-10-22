// Copyright (c) 2026 Tim Olker
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

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
  timeoutMs?: number;
}

/**
 * Typed HTTP fetch wrapper enforcing W3C tracing, idempotency keys, request timeouts, and RFC 7807 ProblemDetails mapping.
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

  const timeoutMs = options.timeoutMs ?? 15000;
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => {
    timeoutController.abort(
      new Error(`Request timed out after ${timeoutMs}ms`),
    );
  }, timeoutMs);

  if (options.signal) {
    if (options.signal.aborted) {
      timeoutController.abort(options.signal.reason);
    } else {
      options.signal.addEventListener("abort", () => {
        timeoutController.abort(options.signal?.reason);
      });
    }
  }

  let response: Response;
  try {
    response = await fetch(endpoint, {
      ...options,
      headers,
      signal: timeoutController.signal,
    });
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }

    const isTimeout =
      (err as Error)?.name === "AbortError" ||
      (err as Error)?.message?.includes("timed out");

    const problem: ProblemDetails = {
      type: isTimeout
        ? "https://errors.vistarae.com/gateway-timeout"
        : "https://errors.vistarae.com/network-error",
      title: isTimeout ? "Request Timeout" : "Network Error",
      status: isTimeout ? 504 : 503,
      detail: isTimeout
        ? `The backend server did not respond within ${
            timeoutMs / 1000
          } seconds. Please verify the backend service is running.`
        : (err as Error)?.message ||
          "Failed to communicate with the backend server.",
    };
    throw new ApiError(problem);
  } finally {
    clearTimeout(timeoutId);
  }

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
