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
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { ProfilePage } from "../ProfilePage";
import { userContextService } from "../../services/userContextService";

// Mock AuthContext
const mockUser = {
  id: "usr-123",
  email: "traveler@example.com",
  full_name: "Jane Traveler",
  tier: "STANDARD",
  is_admin: false,
};

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

// Mock ToastContext
const mockShowToast = vi.fn();
vi.mock("../../context/ToastContext", () => ({
  useToast: () => ({
    showToast: mockShowToast,
  }),
}));

// Mock userContextService
vi.mock("../../services/userContextService", () => ({
  userContextService: {
    getTravelStyle: vi.fn(),
    updateTravelStyle: vi.fn(),
    clearTravelStyle: vi.fn(),
  },
}));

describe("ProfilePage Travel Style & Prompt Directives (T-014 / REQ-CTX-002, REQ-CTX-007)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders travel style card and fetches initial travel style", async () => {
    vi.mocked(userContextService.getTravelStyle).mockResolvedValue({
      travel_style_description: "Passionate about historic walking tours and artisan bakeries.",
      prompts: [
        {
          prompt_type: "description",
          prompt_text: "Highlight historic architecture.",
          updated_at: new Date().toISOString(),
        },
        {
          prompt_type: "reason_to_visit",
          prompt_text: "Emphasize walking ambiance and heritage.",
          updated_at: new Date().toISOString(),
        },
      ],
    });

    render(<ProfilePage onAccountDeleted={vi.fn()} />);

    expect(screen.getByText("Travel Style & AI Context")).toBeDefined();

    await waitFor(() => {
      const textarea = screen.getByTestId("travel-style-textarea") as HTMLTextAreaElement;
      expect(textarea.value).toBe(
        "Passionate about historic walking tours and artisan bakeries.",
      );
    });

    expect(screen.getByTestId("prompt-directives-section")).toBeDefined();
    expect(screen.getByTestId("prompt-card-description")).toBeDefined();
    expect(screen.getByTestId("prompt-card-reason_to_visit")).toBeDefined();
  });

  it("enables save button upon narrative edit and updates directives on save", async () => {
    vi.mocked(userContextService.getTravelStyle).mockResolvedValue({
      travel_style_description: null,
      prompts: [],
    });

    vi.mocked(userContextService.updateTravelStyle).mockResolvedValue({
      travel_style_description: "Focus on mountain biking and trail running.",
      prompts: [
        {
          prompt_type: "description",
          prompt_text: "Highlight trail difficulty and elevation gain.",
          updated_at: new Date().toISOString(),
        },
      ],
    });

    render(<ProfilePage onAccountDeleted={vi.fn()} />);

    await waitFor(() => {
      const textarea = screen.getByTestId("travel-style-textarea") as HTMLTextAreaElement;
      expect(textarea.disabled).toBe(false);
    });

    const saveBtn = screen.getByTestId("save-travel-style-btn");
    expect(saveBtn).toBeDisabled();

    const textarea = screen.getByTestId("travel-style-textarea");
    fireEvent.change(textarea, {
      target: { value: "Focus on mountain biking and trail running." },
    });

    expect(saveBtn).not.toBeDisabled();

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(userContextService.updateTravelStyle).toHaveBeenCalledWith(
        "Focus on mountain biking and trail running.",
      );
    });

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Travel style saved and prompt directives synthesized.",
        "success",
      );
    });

    expect(screen.getByTestId("prompt-card-description")).toBeDefined();
  });

  it("clears travel style and removes directives when clicking Clear Style", async () => {
    vi.mocked(userContextService.getTravelStyle).mockResolvedValue({
      travel_style_description: "Existing travel narrative",
      prompts: [
        {
          prompt_type: "time_spent",
          prompt_text: "Budget 2 hours per attraction.",
          updated_at: new Date().toISOString(),
        },
      ],
    });

    vi.mocked(userContextService.clearTravelStyle).mockResolvedValue({
      travel_style_description: null,
      prompts: [],
    });

    render(<ProfilePage onAccountDeleted={vi.fn()} />);

    await waitFor(() => {
      const textarea = screen.getByTestId("travel-style-textarea") as HTMLTextAreaElement;
      expect(textarea.value).toBe("Existing travel narrative");
    });

    const clearBtn = screen.getByTestId("clear-travel-style-btn");
    fireEvent.click(clearBtn);

    await waitFor(() => {
      expect(userContextService.clearTravelStyle).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      const textarea = screen.getByTestId("travel-style-textarea") as HTMLTextAreaElement;
      expect(textarea.value).toBe("");
    });

    expect(screen.queryByTestId("prompt-directives-section")).toBeNull();
    expect(mockShowToast).toHaveBeenCalledWith(
      "Travel style cleared. Reverted to standard extraction prompts.",
      "info",
    );
  });
});
