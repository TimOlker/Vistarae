/*
 * Copyright (c) 2026 Tim Olker
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TagValidationWarningModal } from "../../components/ingest/TagValidationWarningModal";

describe("TagValidationWarningModal", () => {
  const unapprovedTags = {
    Ramen: 8,
    Onsen: 5,
  };

  it("renders unapproved tags with occurrence counts", () => {
    render(
      <TagValidationWarningModal
        isOpen={true}
        unapprovedTags={unapprovedTags}
        onApproveAll={vi.fn()}
        onStripUnapproved={vi.fn()}
        onAbort={vi.fn()}
      />
    );

    expect(screen.getByText("Unapproved Tags Detected")).toBeInTheDocument();
    expect(screen.getByText(/Found 2 tags not in your library/i)).toBeInTheDocument();
    expect(screen.getByText("Ramen (8)")).toBeInTheDocument();
    expect(screen.getByText("Onsen (5)")).toBeInTheDocument();
  });

  it("dispatches onApproveAll when Approve & Add All is clicked", () => {
    const handleApprove = vi.fn();
    render(
      <TagValidationWarningModal
        isOpen={true}
        unapprovedTags={unapprovedTags}
        onApproveAll={handleApprove}
        onStripUnapproved={vi.fn()}
        onAbort={vi.fn()}
      />
    );

    const approveButton = screen.getByRole("button", {
      name: /approve & add all to library/i,
    });
    fireEvent.click(approveButton);
    expect(handleApprove).toHaveBeenCalledTimes(1);
  });

  it("dispatches onStripUnapproved when Strip Unapproved Tags is clicked", () => {
    const handleStrip = vi.fn();
    render(
      <TagValidationWarningModal
        isOpen={true}
        unapprovedTags={unapprovedTags}
        onApproveAll={vi.fn()}
        onStripUnapproved={handleStrip}
        onAbort={vi.fn()}
      />
    );

    const stripButton = screen.getByRole("button", {
      name: /strip unapproved tags/i,
    });
    fireEvent.click(stripButton);
    expect(handleStrip).toHaveBeenCalledTimes(1);
  });

  it("dispatches onAbort when Abort Import is clicked", () => {
    const handleAbort = vi.fn();
    render(
      <TagValidationWarningModal
        isOpen={true}
        unapprovedTags={unapprovedTags}
        onApproveAll={vi.fn()}
        onStripUnapproved={vi.fn()}
        onAbort={handleAbort}
      />
    );

    const abortButton = screen.getByRole("button", {
      name: /abort import/i,
    });
    fireEvent.click(abortButton);
    expect(handleAbort).toHaveBeenCalledTimes(1);
  });
});

