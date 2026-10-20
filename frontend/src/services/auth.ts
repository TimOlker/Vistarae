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
}

export interface AuthTokens {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  token_type?: string;
}

const TOKEN_KEY = "vistarae_auth_token";
const USER_KEY = "vistarae_user_profile";

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
    const user = await apiFetch<UserSession>("/api/users/me");
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
    const user = await apiFetch<UserSession>("/api/users/me");
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  },

  async deleteAccount() {
    await apiFetch("/api/users/me", { method: "DELETE" });
    authService.clearSession();
  },
};
