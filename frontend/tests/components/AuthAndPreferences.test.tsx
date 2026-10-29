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

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { LoginPage } from "../../src/pages/LoginPage";
import { SignUpPage } from "../../src/pages/SignUpPage";
import { ForgotPasswordPage } from "../../src/pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../../src/pages/ResetPasswordPage";
import { SettingsPage } from "../../src/pages/SettingsPage";
import { ProfilePage } from "../../src/pages/ProfilePage";
import { ToastProvider } from "../../src/context/ToastContext";
import { ThemeProvider } from "../../src/context/ThemeContext";
import { PreferencesProvider } from "../../src/context/PreferencesContext";
import { AuthProvider } from "../../src/context/AuthContext";
import { authService } from "../../src/services/auth";
import * as AuthContextModule from "../../src/context/AuthContext";
import * as ApiModule from "../../src/services/api";

describe("Cognito Auth Lifecycle Pages (REQ-UI-011, REQ-UI-012, REQ-UI-013, REQ-UI-014)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders login form and invokes authService.login on valid submission", async () => {
    const onSuccess = vi.fn();
    const onNavigateSignUp = vi.fn();
    const onNavigateForgotPassword = vi.fn();

    vi.spyOn(authService, "login").mockResolvedValue({
      tokens: { access_token: "fake-jwt-token" },
      user: {
        id: "usr-123",
        email: "traveler@vistarae.com",
        full_name: "Traveler One",
        is_admin: false,
        tier: "LOW",
      },
    });

    render(
      <ToastProvider>
        <AuthProvider>
          <LoginPage
            onSuccess={onSuccess}
            onNavigateSignUp={onNavigateSignUp}
            onNavigateForgotPassword={onNavigateForgotPassword}
          />
        </AuthProvider>
      </ToastProvider>,
    );

    const emailInput = screen.getByPlaceholderText("traveler@example.com");
    const passwordInput = screen.getByPlaceholderText("••••••••••••");
    const submitBtn = screen.getByRole("button", { name: /sign in/i });

    fireEvent.change(emailInput, {
      target: { value: "traveler@vistarae.com" },
    });
    fireEvent.change(passwordInput, { target: { value: "SecretP@ss123" } });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(authService.login).toHaveBeenCalledWith(
        "traveler@vistarae.com",
        "SecretP@ss123",
      );
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("renders sign up page, registers, and transitions to verification code step", async () => {
    const onSuccess = vi.fn();
    const onNavigateLogin = vi.fn();

    vi.spyOn(authService, "register").mockResolvedValue({
      user_sub: "cognito-sub-123",
      user_confirmed: false,
    });
    vi.spyOn(authService, "confirmSignUp").mockResolvedValue({
      user_id: "usr-new-123",
    });

    render(
      <ToastProvider>
        <SignUpPage onSuccess={onSuccess} onNavigateLogin={onNavigateLogin} />
      </ToastProvider>,
    );

    // Initial Registration Step
    expect(screen.getByText("Create your Account")).toBeInTheDocument();

    const nameInput = screen.getByPlaceholderText("Jane Traveler");
    const emailInput = screen.getByPlaceholderText("traveler@example.com");
    const passwordInput = screen.getByPlaceholderText("••••••••••••");
    const registerBtn = screen.getByRole("button", { name: /continue/i });

    fireEvent.change(nameInput, { target: { value: "Elena Rostova" } });
    fireEvent.change(emailInput, { target: { value: "elena@example.com" } });
    fireEvent.change(passwordInput, { target: { value: "SecurePass!2026" } });

    await act(async () => {
      fireEvent.click(registerBtn);
    });

    await waitFor(() => {
      expect(authService.register).toHaveBeenCalledWith(
        "elena@example.com",
        "SecurePass!2026",
        "Elena Rostova",
      );
      expect(screen.getByText("Verify Email Address")).toBeInTheDocument();
    });

    // Confirmation Step
    const codeInput = screen.getByPlaceholderText("123456");
    const confirmBtn = screen.getByRole("button", {
      name: /verify & complete/i,
    });

    fireEvent.change(codeInput, { target: { value: "654321" } });

    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(authService.confirmSignUp).toHaveBeenCalledWith(
        "elena@example.com",
        "654321",
      );
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("handles forgot password and reset password flow", async () => {
    const onNavigateReset = vi.fn();
    const onNavigateLogin = vi.fn();

    vi.spyOn(authService, "forgotPassword").mockResolvedValue({});
    vi.spyOn(authService, "resetPassword").mockResolvedValue({});

    // Step 1: Request reset code
    render(
      <ToastProvider>
        <ForgotPasswordPage
          onCodeSent={onNavigateReset}
          onNavigateLogin={onNavigateLogin}
        />
      </ToastProvider>,
    );

    const emailInput = screen.getByPlaceholderText("traveler@example.com");
    const submitBtn = screen.getByRole("button", {
      name: /send recovery code/i,
    });

    fireEvent.change(emailInput, { target: { value: "traveler@example.com" } });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(authService.forgotPassword).toHaveBeenCalledWith(
        "traveler@example.com",
      );
      expect(onNavigateReset).toHaveBeenCalledWith("traveler@example.com");
    });

    // Step 2: Confirm new password
    render(
      <ToastProvider>
        <ResetPasswordPage
          email="traveler@example.com"
          onSuccess={onNavigateLogin}
        />
      </ToastProvider>,
    );

    const codeInput = screen.getByPlaceholderText("123456");
    const newPasswordInput = screen.getByPlaceholderText("••••••••••••");
    const resetBtn = screen.getByRole("button", { name: /save new password/i });

    fireEvent.change(codeInput, { target: { value: "112233" } });
    fireEvent.change(newPasswordInput, {
      target: { value: "NewSuperSecret!2026" },
    });

    await act(async () => {
      fireEvent.click(resetBtn);
    });

    await waitFor(() => {
      expect(authService.resetPassword).toHaveBeenCalledWith(
        "traveler@example.com",
        "112233",
        "NewSuperSecret!2026",
      );
      expect(onNavigateLogin).toHaveBeenCalled();
    });
  });
});

describe("Preferences & Settings Tabs (REQ-UI-016, REQ-UI-017)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.spyOn(ApiModule, "apiFetch").mockImplementation(async (url: string) => {
      if (url === "/api/users/me/preferences") {
        return {
          ui: {
            theme: "dark",
            email_notifications: true,
            push_notifications: false,
            marketing_emails: false,
          },
          poi: {
            clustering_enabled: true,
            clustering_radius_meters: 60,
            default_map_layer: "osm",
            geoproximity_scope_km: 15.0,
            pin_color_presets: {
              not_visited: "#2563eb",
              visited_return: "#16a34a",
              visited_do_not_return: "#dc2626",
            },
          },
          planner: {
            pacing_mode: "BALANCED",
            meal_interval_hours: 4.0,
            pack_lunch_preference: false,
            default_transit_mode: "TRANSIT",
            max_daily_activity_hours: 8.0,
            preferred_currency: "EUR",
          },
        };
      }
      return null;
    });
  });

  it("renders tab navigation across Account/UI, POI, and Planner", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <ThemeProvider>
            <AuthProvider>
              <PreferencesProvider>
                <SettingsPage />
              </PreferencesProvider>
            </AuthProvider>
          </ThemeProvider>
        </ToastProvider>,
      );
    });

    expect(screen.getByText("Account & UI")).toBeInTheDocument();
    expect(screen.getByText("POI Mode")).toBeInTheDocument();
    expect(screen.getByText("Planner Mode")).toBeInTheDocument();

    // Switch to POI Tab
    const poiTabBtn = screen.getByText("POI Mode");
    fireEvent.click(poiTabBtn);

    expect(screen.getByText(/Clustering Radius:/i)).toBeInTheDocument();
    expect(screen.getByText(/Geoproximity Scope:/i)).toBeInTheDocument();

    // Switch to Planner Tab
    const plannerTabBtn = screen.getByText("Planner Mode");
    fireEvent.click(plannerTabBtn);

    expect(screen.getByText(/Trip Pacing Mode/i)).toBeInTheDocument();
    expect(screen.getByText(/Meal Interval:/i)).toBeInTheDocument();
    expect(screen.getByText(/Preferred Currency/i)).toBeInTheDocument();
  });
});

describe("User Profile & GDPR Account Deletion (REQ-UI-015)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders user details, quota usage cards, and confirms account deletion", async () => {
    const onAccountDeleted = vi.fn();

    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        id: "usr-gdpr-1",
        email: "privacy@vistarae.com",
        full_name: "Privacy Advocate",
        is_admin: false,
        tier: "HIGH",
        created_at: "2026-02-14T10:00:00Z",
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      isOnboardingModalOpen: false,
      closeOnboardingModal: vi.fn(),
    });

    vi.spyOn(authService, "deleteAccount").mockResolvedValue(undefined);

    await act(async () => {
      render(
        <ToastProvider>
          <ProfilePage onAccountDeleted={onAccountDeleted} />
        </ToastProvider>,
      );
    });

    expect(screen.getByText("Privacy Advocate")).toBeInTheDocument();
    expect(screen.getByText("privacy@vistarae.com")).toBeInTheDocument();
    expect(screen.getByText("HIGH TIER")).toBeInTheDocument();

    // Open Delete Account modal
    const deleteBtn = screen.getByRole("button", { name: /delete account/i });
    fireEvent.click(deleteBtn);

    expect(screen.getByText("Confirm Permanent Deletion")).toBeInTheDocument();

    const confirmInput = screen.getByPlaceholderText("Type DELETE");
    fireEvent.change(confirmInput, { target: { value: "DELETE" } });

    const finalConfirmBtn = screen.getByRole("button", {
      name: /permanently delete/i,
    });
    await act(async () => {
      fireEvent.click(finalConfirmBtn);
    });

    await waitFor(() => {
      expect(authService.deleteAccount).toHaveBeenCalled();
      expect(onAccountDeleted).toHaveBeenCalled();
    });
  });
});
