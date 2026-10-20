// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "../../src/App";
import { authService } from "../../src/services/auth";

// Mock MapLibre
vi.mock("maplibre-gl", () => ({
  default: {
    Map: vi.fn().mockImplementation(() => ({
      addControl: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      getSource: vi.fn(),
      getLayer: vi.fn(),
      getBounds: vi.fn().mockReturnValue({
        getWest: () => 0,
        getSouth: () => 0,
        getEast: () => 0,
        getNorth: () => 0,
      }),
      getZoom: vi.fn().mockReturnValue(1),
      getCanvas: vi.fn().mockReturnValue({ style: {} }),
      on: vi.fn(),
      remove: vi.fn(),
      flyTo: vi.fn(),
      easeTo: vi.fn(),
      isStyleLoaded: vi.fn().mockReturnValue(true),
      queryRenderedFeatures: vi.fn().mockReturnValue([]),
    })),
    NavigationControl: vi.fn(),
  },
}));

describe("App Authentication & Landing Page Boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders LandingPage and guest Navbar when user is not authenticated", async () => {
    vi.spyOn(authService, "getStoredToken").mockReturnValue(null);
    vi.spyOn(authService, "getStoredUser").mockReturnValue(null);

    render(<App />);

    // Should display Landing Page hero
    expect(
      await screen.findByRole("heading", {
        name: /Capture Every Scenic Overlook, Hidden Trail/i,
      }),
    ).toBeInTheDocument();

    // Guest Navbar and CTA links
    expect(
      screen.getByRole("button", { name: /Features/i }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /Sign In/i }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("button", { name: /Sign Up/i }).length,
    ).toBeGreaterThan(0);

    // Functional app actions should NOT be in the navbar for guests
    expect(
      screen.queryByRole("button", { name: /^Explorer$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Add POI/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Import CSV/i }),
    ).not.toBeInTheDocument();
  });

  it("renders HomePage and full functionality in Navbar when user is authenticated", async () => {
    vi.spyOn(authService, "getStoredToken").mockReturnValue("mock-valid-token");
    vi.spyOn(authService, "getStoredUser").mockReturnValue({
      id: "usr-auth-123",
      email: "explorer@vistarae.com",
      full_name: "Alice Explorer",
      is_admin: false,
      tier: "HIGH",
    });
    vi.spyOn(authService, "fetchCurrentUser").mockResolvedValue({
      id: "usr-auth-123",
      email: "explorer@vistarae.com",
      full_name: "Alice Explorer",
      is_admin: false,
      tier: "HIGH",
    });

    render(<App />);

    // Should display Explorer navigation
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^Explorer$/i }),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole("button", { name: /Add POI/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Import CSV/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Preferences/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Alice Explorer")).toBeInTheDocument();
  });
});
