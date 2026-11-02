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
import { POIFilterBar } from "../../components/poi/POIFilterBar";

describe("POIFilterBar", () => {
  it("renders Date Added presets and dispatches selection", () => {
    const handleDateChange = vi.fn();
    render(
      <POIFilterBar
        dateAddedFilter={{ preset: "ALL_TIME" }}
        onDateAddedChange={handleDateChange}
      />
    );

    expect(screen.getByText("Date Added:")).toBeInTheDocument();
    const select = screen.getByLabelText(/date added/i) as HTMLSelectElement;
    expect(select).toBeInTheDocument();

    // Select "Today"
    fireEvent.change(select, { target: { value: "TODAY" } });
    expect(handleDateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        preset: "TODAY",
      })
    );

    // Select "Last 7 Days"
    fireEvent.change(select, { target: { value: "LAST_7_DAYS" } });
    expect(handleDateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        preset: "LAST_7_DAYS",
      })
    );

    // Select "Last 30 Days"
    fireEvent.change(select, { target: { value: "LAST_30_DAYS" } });
    expect(handleDateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        preset: "LAST_30_DAYS",
      })
    );
  });

  it("shows custom date inputs when CUSTOM preset is selected", () => {
    const handleDateChange = vi.fn();
    render(
      <POIFilterBar
        dateAddedFilter={{
          preset: "CUSTOM",
          startDate: "2026-10-01",
          endDate: "2026-10-31",
        }}
        onDateAddedChange={handleDateChange}
      />
    );

    const startDateInput = screen.getByLabelText(/start date/i) as HTMLInputElement;
    const endDateInput = screen.getByLabelText(/end date/i) as HTMLInputElement;

    expect(startDateInput).toBeInTheDocument();
    expect(endDateInput).toBeInTheDocument();
    expect(startDateInput.value).toBe("2026-10-01");
    expect(endDateInput.value).toBe("2026-10-31");

    fireEvent.change(startDateInput, { target: { value: "2026-10-15" } });
    expect(handleDateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        preset: "CUSTOM",
        startDate: "2026-10-15",
      })
    );
  });
});

