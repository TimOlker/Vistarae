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
  ensureAuthenticatedForCapture,
  getAuthenticatedUser,
} from "../background/auth.js";

describe("Extension Pre-Capture Auth Gate & User Context (REQ-EXT-008, REQ-EXT-009, REQ-EXT-010)", () => {
  let mockStorage = {};
  let createdTabs = [];

  beforeEach(() => {
    mockStorage = {};
    createdTabs = [];
    vi.restoreAllMocks();

    // Mock chrome APIs
    globalThis.chrome = {
      storage: {
        local: {
          get: vi.fn(async (keys) => {
            const res = {};
            for (const k of keys) {
              if (mockStorage[k] !== undefined) res[k] = mockStorage[k];
            }
            return res;
          }),
          set: vi.fn(async (obj) => {
            Object.assign(mockStorage, obj);
          }),
          remove: vi.fn(async (keys) => {
            for (const k of keys) delete mockStorage[k];
          }),
        },
      },
      tabs: {
        create: vi.fn(async (opts) => {
          createdTabs.push(opts);
          return { id: 999, ...opts };
        }),
      },
      runtime: {
        sendMessage: vi.fn(async () => {}),
      },
    };
  });

  it("aborts capture and opens login tab when unauthenticated (REQ-EXT-008, REQ-EXT-009)", async () => {
    mockStorage = {}; // No tokens in storage

    const isAllowed = await ensureAuthenticatedForCapture();

    expect(isAllowed).toBe(false);
    expect(chrome.tabs.create).toHaveBeenCalledTimes(1);
    expect(createdTabs[0].url).toContain("/login?return_to=extension");
  });

  it("permits capture without opening tab when user has active valid token (REQ-EXT-008)", async () => {
    const futureExp = Math.floor(Date.now() / 1000) + 1800; // 30 min in future
    mockStorage = {
      accessToken: "valid.jwt.token",
      refreshToken: "refresh.token",
      tokenExpiry: futureExp,
      user: { email: "traveler@vistarae.com" },
    };

    const isAllowed = await ensureAuthenticatedForCapture();

    expect(isAllowed).toBe(true);
    expect(chrome.tabs.create).not.toHaveBeenCalled();
  });

  it("extracts authenticated user email from storage or JWT payload (REQ-EXT-010)", async () => {
    const futureExp = Math.floor(Date.now() / 1000) + 1800;
    const header = btoa(JSON.stringify({ alg: "none" })).replace(/=/g, "");
    const payload = btoa(
      JSON.stringify({
        sub: "user-456",
        email: "adventurer@vistarae.com",
        exp: futureExp,
      }),
    ).replace(/=/g, "");
    const jwt = `${header}.${payload}.sig`;

    mockStorage = {
      accessToken: jwt,
      tokenExpiry: futureExp,
    };

    const authContext = await getAuthenticatedUser();
    expect(authContext.isAuthenticated).toBe(true);
    expect(authContext.email).toBe("adventurer@vistarae.com");
  });

  it("returns unauthenticated state with null email when no credentials exist", async () => {
    mockStorage = {};

    const authContext = await getAuthenticatedUser();
    expect(authContext.isAuthenticated).toBe(false);
    expect(authContext.email).toBeNull();
  });
});
