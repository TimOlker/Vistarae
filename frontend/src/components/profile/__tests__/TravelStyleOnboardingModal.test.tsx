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

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TravelStyleOnboardingModal } from "../TravelStyleOnboardingModal";

describe("TravelStyleOnboardingModal", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("does not render modal contents when isOpen is false", () => {
    render(
      <TravelStyleOnboardingModal
        isOpen={false}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByTestId("travel-style-onboarding-modal")).toBeNull();
  });

  it("renders modal with headline and explanation when isOpen is true (REQ-CTX-010)", () => {
    render(
      <TravelStyleOnboardingModal
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("travel-style-onboarding-modal")).toBeInTheDocument();
    expect(screen.getByText("Personalize Your Travel Experience")).toBeInTheDocument();
    expect(screen.getByText("Make Vistarae Truly Yours")).toBeInTheDocument();
    expect(screen.getByTestId("travel-style-modal-setup-btn")).toBeInTheDocument();
    expect(screen.getByTestId("travel-style-modal-remind-btn")).toBeInTheDocument();
  });

  it("navigates to profile and closes modal when CTA is clicked (REQ-CTX-011, SC-006)", () => {
    const handleClose = vi.fn();
    const handleSetUp = vi.fn();

    render(
      <TravelStyleOnboardingModal
        isOpen={true}
        onClose={handleClose}
        onSetUp={handleSetUp}
      />
    );

    const setupBtn = screen.getByTestId("travel-style-modal-setup-btn");
    fireEvent.click(setupBtn);

    expect(handleSetUp).toHaveBeenCalledTimes(1);
    expect(handleClose).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("vistarae_travel_style_dismissed")).toBe("true");
  });

  it("dismisses modal and stores session dismissal on 'Remind Me Later' click (REQ-CTX-012)", () => {
    const handleClose = vi.fn();

    render(
      <TravelStyleOnboardingModal
        isOpen={true}
        onClose={handleClose}
      />
    );

    const remindBtn = screen.getByTestId("travel-style-modal-remind-btn");
    fireEvent.click(remindBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("vistarae_travel_style_dismissed")).toBe("true");
  });

  it("handles escape key to close modal", () => {
    const handleClose = vi.fn();

    render(
      <TravelStyleOnboardingModal
        isOpen={true}
        onClose={handleClose}
      />
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
