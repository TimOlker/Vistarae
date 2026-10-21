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

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LandingPage } from "../../src/pages/LandingPage";

describe("LandingPage Component", () => {
  it("renders hero section, value metrics, and call-to-action buttons", () => {
    const onNavigateLogin = vi.fn();
    const onNavigateSignUp = vi.fn();

    render(
      <LandingPage
        onNavigateLogin={onNavigateLogin}
        onNavigateSignUp={onNavigateSignUp}
      />,
    );

    // Hero title
    expect(
      screen.getByRole("heading", {
        name: /Capture Every Scenic Overlook, Hidden Trail/i,
      }),
    ).toBeInTheDocument();

    // CTA buttons
    expect(
      screen.getByRole("button", { name: /Get Started Free/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Sign In to Workspace/i }),
    ).toBeInTheDocument();

    // Value metrics
    expect(screen.getByText("Multi-Engine Map Layers")).toBeInTheDocument();
    expect(screen.getByText("Supercluster Engine")).toBeInTheDocument();
    expect(screen.getByText("Canonical WGS-84")).toBeInTheDocument();
    expect(screen.getByText("AI Entity Extraction")).toBeInTheDocument();
  });

  it("navigates to signup when Get Started Free is clicked", () => {
    const onNavigateLogin = vi.fn();
    const onNavigateSignUp = vi.fn();

    render(
      <LandingPage
        onNavigateLogin={onNavigateLogin}
        onNavigateSignUp={onNavigateSignUp}
      />,
    );

    const getStartedBtn = screen.getByRole("button", {
      name: /Get Started Free/i,
    });
    fireEvent.click(getStartedBtn);

    expect(onNavigateSignUp).toHaveBeenCalledTimes(1);
    expect(onNavigateLogin).not.toHaveBeenCalled();
  });

  it("navigates to login when Sign In is clicked", () => {
    const onNavigateLogin = vi.fn();
    const onNavigateSignUp = vi.fn();

    render(
      <LandingPage
        onNavigateLogin={onNavigateLogin}
        onNavigateSignUp={onNavigateSignUp}
      />,
    );

    const signInBtn = screen.getByRole("button", {
      name: /Sign In to Workspace/i,
    });
    fireEvent.click(signInBtn);

    expect(onNavigateLogin).toHaveBeenCalledTimes(1);
    expect(onNavigateSignUp).not.toHaveBeenCalled();
  });

  it("allows switching interactive workflow tabs", () => {
    const onNavigateLogin = vi.fn();
    const onNavigateSignUp = vi.fn();

    render(
      <LandingPage
        onNavigateLogin={onNavigateLogin}
        onNavigateSignUp={onNavigateSignUp}
      />,
    );

    // Initial tab is Browser Capture
    expect(
      screen.getByText(/Capture Directly From Travel Articles/i),
    ).toBeInTheDocument();

    // Switch to Vector Basemaps tab
    const mapsTabBtn = screen.getByRole("button", { name: /Vector Basemaps/i });
    fireEvent.click(mapsTabBtn);
    expect(
      screen.getByRole("heading", {
        name: /True English Landmark Labels Worldwide/i,
      }),
    ).toBeInTheDocument();

    // Switch to Intelligent Ingestion tab
    const triageTabBtn = screen.getByRole("button", {
      name: /Intelligent Ingestion/i,
    });
    fireEvent.click(triageTabBtn);
    expect(
      screen.getByText(/Bulk CSV Ingest with Intelligent Triage/i),
    ).toBeInTheDocument();
  });

  it("navigates to terms when Terms link is clicked", () => {
    const onNavigateLogin = vi.fn();
    const onNavigateSignUp = vi.fn();
    const onNavigateTerms = vi.fn();

    render(
      <LandingPage
        onNavigateLogin={onNavigateLogin}
        onNavigateSignUp={onNavigateSignUp}
        onNavigateTerms={onNavigateTerms}
      />,
    );

    const termsBtn = screen.getByRole("button", { name: /Terms of Service/i });
    fireEvent.click(termsBtn);

    expect(onNavigateTerms).toHaveBeenCalledTimes(1);
  });
});
