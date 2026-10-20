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

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  parseJwtPayload,
  getValidAccessToken,
  executeCognitoRefresh,
  clearTokens,
  saveTokens,
} from "../../../../extension/background/auth.js";

describe("Extension Auth & Silent Refresh Middleware", () => {
  let mockStorage: Record<string, any> = {};

  beforeEach(() => {
    mockStorage = {};
    vi.restoreAllMocks();

    // Mock chrome.storage.local
    // @ts-ignore
    globalThis.chrome = {
      storage: {
        local: {
          get: vi.fn(async (keys: string[]) => {
            const res: Record<string, any> = {};
            for (const k of keys) {
              if (mockStorage[k] !== undefined) res[k] = mockStorage[k];
            }
            return res;
          }),
          set: vi.fn(async (obj: Record<string, any>) => {
            Object.assign(mockStorage, obj);
          }),
          remove: vi.fn(async (keys: string[]) => {
            for (const k of keys) delete mockStorage[k];
          }),
        },
      },
      runtime: {
        sendMessage: vi.fn(async () => {}),
      },
    };
  });

  it("parses JWT payload successfully without external dependencies", () => {
    // Header: {"alg":"none"}, Payload: {"sub":"user123","exp":1800000000,"email":"test@vistarae.com"}
    const header = btoa(JSON.stringify({ alg: "none" })).replace(/=/g, "");
    const payload = btoa(
      JSON.stringify({
        sub: "user123",
        exp: 1800000000,
        email: "test@vistarae.com",
      }),
    ).replace(/=/g, "");
    const testJwt = `${header}.${payload}.sig`;

    const parsed = parseJwtPayload(testJwt);
    expect(parsed).not.toBeNull();
    expect(parsed?.sub).toBe("user123");
    expect(parsed?.email).toBe("test@vistarae.com");
    expect(parsed?.exp).toBe(1800000000);
  });

  it("returns active access token without refreshing when remaining time is > 5 minutes", async () => {
    const futureExp = Math.floor(Date.now() / 1000) + 1200; // 20 min in future
    mockStorage = {
      accessToken: "valid.access.token",
      refreshToken: "valid.refresh.token",
      tokenExpiry: futureExp,
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const token = await getValidAccessToken();

    expect(token).toBe("valid.access.token");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("deduplicates simultaneous token refreshes using single-flight promise mutex", async () => {
    const expiringExp = Math.floor(Date.now() / 1000) + 100; // 100s remaining <= 300s margin
    mockStorage = {
      accessToken: "expiring.access.token",
      refreshToken: "valid.refresh.token",
      tokenExpiry: expiringExp,
    };

    let fetchCallCount = 0;
    // @ts-ignore
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      fetchCallCount++;
      // Simulate minor network delay
      await new Promise((r) => setTimeout(r, 50));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          AuthenticationResult: {
            AccessToken: "refreshed.access.token.new",
            ExpiresIn: 3600,
            IdToken: "refreshed.id.token.new",
          },
        }),
      } as any;
    });

    // Fire 3 concurrent getValidAccessToken calls
    const [token1, token2, token3] = await Promise.all([
      getValidAccessToken(),
      getValidAccessToken(),
      getValidAccessToken(),
    ]);

    expect(token1).toBe("refreshed.access.token.new");
    expect(token2).toBe("refreshed.access.token.new");
    expect(token3).toBe("refreshed.access.token.new");

    // Crucial: Single-flight mutex guarantees exactly 1 fetch call to Cognito
    expect(fetchCallCount).toBe(1);
    expect(mockStorage.accessToken).toBe("refreshed.access.token.new");
  });

  it("clears credentials and throws TOKEN_REVOKED on permanent Cognito rejection (HTTP 400)", async () => {
    mockStorage = {
      accessToken: "expired.token",
      refreshToken: "revoked.refresh.token",
      tokenExpiry: 0,
    };

    // @ts-ignore
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        __type: "NotAuthorizedException",
        message: "Refresh Token has been revoked",
      }),
    } as any);

    await expect(getValidAccessToken()).rejects.toThrow("TOKEN_REVOKED");
    expect(mockStorage.accessToken).toBeUndefined();
    expect(mockStorage.refreshToken).toBeUndefined();
  });
});
