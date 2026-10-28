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

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ColumnConfigModal, ALL_COLUMNS } from "../ColumnConfigModal";
import type { TableConfig } from "../../../types/filter";

describe("ColumnConfigModal", () => {
  const baseConfig: TableConfig = {
    visible_columns: ["name", "city", "rating"],
    column_order: ALL_COLUMNS.map((c) => c.id),
    sort: {
      column: "name",
      direction: "asc",
    },
  };

  it("renders all available columns including Description, Reason to Visit, Duration, Itinerary Days, Visit Pending, Visited Date", () => {
    render(
      <ColumnConfigModal
        isOpen={true}
        onClose={vi.fn()}
        config={baseConfig}
        onApply={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Description")).toBeDefined();
    expect(screen.getByLabelText("Reason to Visit")).toBeDefined();
    expect(screen.getByLabelText("Duration (Hours)")).toBeDefined();
    expect(screen.getByLabelText("Itinerary Days")).toBeDefined();
    expect(screen.getByLabelText("Visit Pending")).toBeDefined();
    expect(screen.getByLabelText("Visited Date")).toBeDefined();
  });

  it("adds Visited Date to the sorting options only when Visited Date is selected", () => {
    render(
      <ColumnConfigModal
        isOpen={true}
        onClose={vi.fn()}
        config={baseConfig} // visited_date is not in visible_columns
        onApply={vi.fn()}
      />,
    );

    const sortSelect = screen.getByRole("combobox", { name: "Sort column" });
    const getOptionValues = () =>
      Array.from(sortSelect.querySelectorAll("option")).map((o) => o.value);

    // Initially visited_date is not selected, so not in sort options
    expect(getOptionValues()).not.toContain("visited_date");

    // Click checkbox to select Visited Date
    const visitedDateCheckbox = screen.getByLabelText("Visited Date");
    fireEvent.click(visitedDateCheckbox);

    // Visited Date should now be in sort options
    expect(getOptionValues()).toContain("visited_date");

    // Click again to unselect Visited Date
    fireEvent.click(visitedDateCheckbox);
    expect(getOptionValues()).not.toContain("visited_date");
  });

  it("applies updated columns and sorting configuration on apply click", () => {
    const handleApply = vi.fn();
    render(
      <ColumnConfigModal
        isOpen={true}
        onClose={vi.fn()}
        config={{
          ...baseConfig,
          visible_columns: ["name", "visited_date"],
        }}
        onApply={handleApply}
      />,
    );

    const sortSelect = screen.getByRole("combobox", { name: "Sort column" });
    fireEvent.change(sortSelect, { target: { value: "visited_date" } });

    const applyBtn = screen.getByTestId("apply-column-config-btn");
    fireEvent.click(applyBtn);

    expect(handleApply).toHaveBeenCalledWith(
      expect.objectContaining({
        visible_columns: expect.arrayContaining(["name", "visited_date"]),
        sort: {
          column: "visited_date",
          direction: "asc",
        },
      }),
    );
  });
});
