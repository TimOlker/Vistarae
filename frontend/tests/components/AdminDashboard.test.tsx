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
import { AdminRoute } from "../../src/components/common/AdminRoute";
import { AdminDashboardPage } from "../../src/pages/AdminDashboardPage";
import { ToastProvider } from "../../src/context/ToastContext";
import * as AuthContextModule from "../../src/context/AuthContext";
import * as ApiModule from "../../src/services/api";

describe("AdminRoute Component (REQ-UI-019)", () => {
  const onUnauthorizedRedirect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthorized non-admin user and triggers 403 error toast", () => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        id: "usr-regular-1",
        email: "regular@example.com",
        full_name: "Regular Traveler",
        is_admin: false,
        tier: "LOW",
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      isOnboardingModalOpen: false,
      closeOnboardingModal: vi.fn(),
    });

    render(
      <ToastProvider>
        <AdminRoute onUnauthorizedRedirect={onUnauthorizedRedirect}>
          <div data-testid="protected-content">Admin Secret</div>
        </AdminRoute>
      </ToastProvider>,
    );

    expect(screen.queryByTestId("protected-content")).toBeNull();
    expect(onUnauthorizedRedirect).toHaveBeenCalledTimes(1);
  });

  it("renders protected admin children when user has is_admin=true", () => {
    vi.spyOn(AuthContextModule, "useAuth").mockReturnValue({
      user: {
        id: "usr-admin-1",
        email: "admin@vistarae.com",
        full_name: "Admin User",
        is_admin: true,
        tier: "HIGH",
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      isOnboardingModalOpen: false,
      closeOnboardingModal: vi.fn(),
    });

    render(
      <ToastProvider>
        <AdminRoute onUnauthorizedRedirect={onUnauthorizedRedirect}>
          <div data-testid="protected-content">Admin Secret</div>
        </AdminRoute>
      </ToastProvider>,
    );

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
    expect(onUnauthorizedRedirect).not.toHaveBeenCalled();
  });
});

describe("AdminDashboardPage Component (REQ-UI-018)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(ApiModule, "apiFetch").mockImplementation(
      async (endpoint: string) => {
        if (endpoint === "/api/admin/metrics") {
          return {
            total_users: 1500,
            active_sessions: 90,
            monthly_token_budget_used: 500000,
            monthly_token_budget_max: 1000000,
            sqs_queue_depth: 0,
            sqs_avg_latency_ms: 125,
          };
        }
        return null;
      },
    );
  });

  it("renders platform metrics and system control cards", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <AdminDashboardPage />
        </ToastProvider>,
      );
    });

    expect(screen.getByText("Administrative Governance")).toBeInTheDocument();
    expect(screen.getByText("Total Registered")).toBeInTheDocument();
    expect(screen.getByText("Active Sessions")).toBeInTheDocument();
    expect(screen.getByText("Token Budget")).toBeInTheDocument();
    expect(screen.getByText("SQS Ingestion Queue")).toBeInTheDocument();
    expect(
      screen.getByText("Platform System Controls & Feature Flags"),
    ).toBeInTheDocument();
  });

  it("filters user accounts by search query", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <AdminDashboardPage />
        </ToastProvider>,
      );
    });

    expect(screen.getByText("Elena Rostova")).toBeInTheDocument();
    expect(screen.getByText("Marcus Chen")).toBeInTheDocument();

    const searchInput = screen.getByPlaceholderText("Search user or email...");
    fireEvent.change(searchInput, { target: { value: "Chen" } });

    expect(screen.getByText("Marcus Chen")).toBeInTheDocument();
    expect(screen.queryByText("Elena Rostova")).toBeNull();
  });

  it("toggles user tier on tier badge click", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <AdminDashboardPage />
        </ToastProvider>,
      );
    });

    const userRow = screen.getByText("Marcus Chen").closest("tr");
    expect(userRow).not.toBeNull();

    // Initially LOW tier
    const tierButton = userRow!.querySelector(
      'button[title="Click to toggle tier"]',
    );
    expect(tierButton).not.toBeNull();
    expect(tierButton!.textContent).toContain("LOW");

    fireEvent.click(tierButton!);

    // Should toggle to HIGH
    await waitFor(() => {
      expect(tierButton!.textContent).toContain("HIGH");
    });
  });

  it("toggles user status between active and suspended", async () => {
    await act(async () => {
      render(
        <ToastProvider>
          <AdminDashboardPage />
        </ToastProvider>,
      );
    });

    const userRow = screen.getByText("Elena Rostova").closest("tr");
    expect(userRow).not.toBeNull();
    expect(userRow!.textContent).toContain("Active");

    const suspendBtn = Array.from(userRow!.querySelectorAll("button")).find(
      (btn) => btn.textContent === "Suspend",
    );
    expect(suspendBtn).toBeDefined();

    fireEvent.click(suspendBtn!);

    await waitFor(() => {
      expect(userRow!.textContent).toContain("Suspended");
      expect(suspendBtn!.textContent).toBe("Activate");
    });
  });
});
