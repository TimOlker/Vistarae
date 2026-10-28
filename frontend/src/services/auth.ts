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

import { apiFetch } from "./api";

export interface UserSession {
  id: string;
  email: string;
  full_name: string;
  is_admin: boolean;
  tier: string;
  created_at?: string;
  travel_style_description?: string | null;
}

export interface AuthTokens {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  token_type?: string;
}

const TOKEN_KEY = "vistarae_auth_token";
const USER_KEY = "vistarae_user_profile";

function normalizeUserSession(raw: unknown): UserSession {
  const data = raw as {
    user?: {
      id: string;
      email: string;
      full_name?: string | null;
      is_admin?: boolean;
      created_at?: string;
    };
    preferences?: {
      travel_style_description?: string | null;
    };
    quotas?: {
      tier?: string;
    };
    id?: string;
    email?: string;
    full_name?: string | null;
    is_admin?: boolean;
    tier?: string;
    created_at?: string;
    travel_style_description?: string | null;
  };

  const travelStyle =
    data?.preferences?.travel_style_description ??
    data?.travel_style_description ??
    null;

  if (data?.user) {
    const tier = (data.quotas?.tier || "LOW").toUpperCase();
    return {
      id: data.user.id,
      email: data.user.email,
      full_name: data.user.full_name || "",
      is_admin:
        data.user.is_admin ??
        (tier === "ADMIN" || data.user.email.includes("admin")),
      tier,
      created_at: data.user.created_at,
      travel_style_description: travelStyle,
    };
  }

  return {
    id: data?.id || "",
    email: data?.email || "",
    full_name: data?.full_name || "",
    is_admin: Boolean(data?.is_admin),
    tier: (data?.tier || "LOW").toUpperCase(),
    created_at: data?.created_at,
    travel_style_description: travelStyle,
  };
}

export const authService = {
  getStoredToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  getStoredUser(): UserSession | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  setSession(tokens: AuthTokens, user?: UserSession) {
    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  },

  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  async register(email: string, password: string, fullName: string) {
    return apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
      skipAuth: true,
    });
  },

  async confirmSignUp(email: string, code: string) {
    return apiFetch("/api/auth/confirm-signup", {
      method: "POST",
      body: JSON.stringify({ email, confirmation_code: code }),
      skipAuth: true,
    });
  },

  async login(
    email: string,
    password: string,
  ): Promise<{ tokens: AuthTokens; user: UserSession }> {
    const tokens = await apiFetch<AuthTokens>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      skipAuth: true,
    });

    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    const rawUser = await apiFetch<unknown>("/api/users/me");
    const user = normalizeUserSession(rawUser);
    authService.setSession(tokens, user);
    return { tokens, user };
  },

  async forgotPassword(email: string) {
    return apiFetch("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
      skipAuth: true,
    });
  },

  async resetPassword(email: string, code: string, newPassword: string) {
    return apiFetch("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        email,
        confirmation_code: code,
        new_password: newPassword,
      }),
      skipAuth: true,
    });
  },

  async logout() {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore network errors on logout
    } finally {
      authService.clearSession();
    }
  },

  async fetchCurrentUser(): Promise<UserSession> {
    const rawUser = await apiFetch<unknown>("/api/users/me");
    const user = normalizeUserSession(rawUser);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  },

  async deleteAccount() {
    await apiFetch("/api/users/me", { method: "DELETE" });
    authService.clearSession();
  },
};
