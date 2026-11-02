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
import { ImportValidationErrorModal } from "../../components/ingest/ImportValidationErrorModal";

describe("ImportValidationErrorModal", () => {
  const sampleIssues = [
    {
      row_number: 2,
      column: "latitude",
      raw_value: "invalid_lat",
      message: "Latitude must be a valid float between -90 and 90.",
    },
    {
      row_number: 5,
      column: "longitude",
      raw_value: "200.5",
      message: "Longitude must be a valid float between -180 and 180.",
    },
  ];

  it("renders validation issues with row numbers and invalid values", () => {
    render(
      <ImportValidationErrorModal
        isOpen={true}
        issues={sampleIssues}
        totalRows={10}
        invalidRowCount={2}
        onSkipAndContinue={vi.fn()}
        onAbort={vi.fn()}
      />
    );

    expect(screen.getByText("Import Validation Issues Detected")).toBeInTheDocument();
    expect(screen.getByText(/2 of 10 rows contain invalid or unparseable data/i)).toBeInTheDocument();
    expect(screen.getByText("Row 2")).toBeInTheDocument();
    expect(screen.getByText("latitude")).toBeInTheDocument();
    expect(screen.getByText("invalid_lat")).toBeInTheDocument();
    expect(screen.getByText("Row 5")).toBeInTheDocument();
    expect(screen.getByText("longitude")).toBeInTheDocument();
    expect(screen.getByText("200.5")).toBeInTheDocument();
  });

  it("calls onSkipAndContinue when Skip button is clicked", () => {
    const handleSkip = vi.fn();
    render(
      <ImportValidationErrorModal
        isOpen={true}
        issues={sampleIssues}
        totalRows={10}
        invalidRowCount={2}
        onSkipAndContinue={handleSkip}
        onAbort={vi.fn()}
      />
    );

    const skipButton = screen.getByRole("button", {
      name: /skip 2 invalid rows & continue/i,
    });
    fireEvent.click(skipButton);
    expect(handleSkip).toHaveBeenCalledTimes(1);
  });

  it("calls onAbort when Abort button is clicked", () => {
    const handleAbort = vi.fn();
    render(
      <ImportValidationErrorModal
        isOpen={true}
        issues={sampleIssues}
        totalRows={10}
        invalidRowCount={2}
        onSkipAndContinue={vi.fn()}
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

