// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  apiFetch,
  ApiError,
  generateTraceparent,
} from "../../src/services/api";

describe("apiClient and W3C Tracing", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("generates a valid W3C traceparent string", () => {
    const { traceparent, traceId, spanId } = generateTraceparent();
    expect(traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
    expect(traceId).toHaveLength(32);
    expect(spanId).toHaveLength(16);
  });

  it("injects W3C traceparent and directional headers on requests", async () => {
    let capturedHeaders: Headers | null = null;

    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = new Headers(init.headers);
      return Promise.resolve(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    });

    await apiFetch("/api/test");

    expect(capturedHeaders).not.toBeNull();
    expect(capturedHeaders!.get("X-Source")).toBe("web-client");
    expect(capturedHeaders!.get("X-Destination")).toBe("backend");
    expect(capturedHeaders!.get("traceparent")).toMatch(
      /^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/,
    );
    expect(capturedHeaders!.get("X-Vistarae-Trace-Id")).toBeTruthy();
  });

  it("injects Idempotency-Key on mutating requests (POST, PATCH, DELETE)", async () => {
    let capturedHeaders: Headers | null = null;

    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedHeaders = new Headers(init.headers);
      return Promise.resolve(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    });

    await apiFetch("/api/pois", {
      method: "POST",
      body: JSON.stringify({ name: "Test" }),
    });

    expect(capturedHeaders!.get("Idempotency-Key")).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  it("parses RFC 7807 ProblemDetails with invalid_params on 400 error", async () => {
    const errorPayload = {
      type: "https://vistarae.com/errors/validation",
      title: "Validation Error",
      status: 400,
      detail: "Request body failed schema validation",
      invalid_params: [
        { name: "name", reason: "Field cannot be empty" },
        { name: "latitude", reason: "Must be between -90 and 90" },
      ],
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), {
        status: 400,
        headers: { "Content-Type": "application/problem+json" },
      }),
    );

    try {
      await apiFetch("/api/pois", { method: "POST", body: JSON.stringify({}) });
      expect.fail("Should have thrown ApiError");
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(400);
      expect(apiErr.problem.title).toBe("Validation Error");
      expect(apiErr.problem.detail).toBe(
        "Request body failed schema validation",
      );
      expect(apiErr.problem.invalid_params).toHaveLength(2);
      expect(apiErr.problem.invalid_params![0].name).toBe("name");
    }
  });

  it("extracts Retry-After header countdown on HTTP 429 Too Many Requests", async () => {
    const errorPayload = {
      title: "Too Many Requests",
      status: 429,
      detail: "Rate limit quota exceeded.",
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(errorPayload), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": "45",
        },
      }),
    );

    try {
      await apiFetch("/api/heavy-query");
      expect.fail("Should have thrown ApiError");
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(429);
      expect(apiErr.problem.retryAfterSeconds).toBe(45);
    }
  });

  it("handles non-JSON error bodies gracefully (e.g. 502 Bad Gateway HTML)", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("<html><body>502 Bad Gateway</body></html>", {
        status: 502,
        statusText: "Bad Gateway",
        headers: { "Content-Type": "text/html" },
      }),
    );

    try {
      await apiFetch("/api/down-service");
      expect.fail("Should have thrown ApiError");
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(502);
      expect(apiErr.problem.title).toBe("Bad Gateway");
      expect(apiErr.problem.detail).toContain("502");
    }
  });

  it("aborts and throws 504 Request Timeout when server hangs beyond timeoutMs", async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      return new Promise((_resolve, reject) => {
        if (init?.signal) {
          init.signal.addEventListener("abort", () => {
            const err = new Error("The operation was aborted");
            err.name = "AbortError";
            reject(err);
          });
        }
      });
    });

    try {
      await apiFetch("/api/hanging-endpoint", { timeoutMs: 50 });
      expect.fail("Should have thrown ApiError on timeout");
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(504);
      expect(apiErr.problem.title).toBe("Request Timeout");
      expect(apiErr.problem.detail).toContain("did not respond");
    }
  });

  it("maps unexpected network failures to 503 Network Error", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch"));

    try {
      await apiFetch("/api/unreachable-endpoint");
      expect.fail("Should have thrown ApiError on network error");
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(503);
      expect(apiErr.problem.title).toBe("Network Error");
      expect(apiErr.problem.detail).toContain("Failed to fetch");
    }
  });
});
