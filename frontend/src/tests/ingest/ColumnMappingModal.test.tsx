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
import { ColumnMappingModal } from "../../components/ingest/ColumnMappingModal";

describe("ColumnMappingModal", () => {
  const sampleRows = [
    { column: "Waypoint", sample_values: ["Old Faithful", "Grand Prismatic", "Mammoth"] },
    { column: "Elevation", sample_values: ["7349", "7200", "6700"] },
  ];
  const targetFields = ["poi_name", "latitude", "longitude", "ai_description"];

  it("renders unmapped column names and sample previews", () => {
    render(
      <ColumnMappingModal
        isOpen={true}
        unmappedColumns={["Waypoint", "Elevation"]}
        sampleRows={sampleRows}
        targetFields={targetFields}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText("Align Unmapped Columns")).toBeInTheDocument();
    expect(screen.getByText("Waypoint")).toBeInTheDocument();
    expect(screen.getByText("Old Faithful, Grand Prismatic, Mammoth")).toBeInTheDocument();
    expect(screen.getByText("Elevation")).toBeInTheDocument();
    expect(screen.getByText("7349, 7200, 6700")).toBeInTheDocument();
  });

  it("allows selecting target fields and ignoring columns", () => {
    const handleConfirm = vi.fn();
    render(
      <ColumnMappingModal
        isOpen={true}
        unmappedColumns={["Waypoint", "Elevation"]}
        sampleRows={sampleRows}
        targetFields={targetFields}
        onConfirm={handleConfirm}
        onCancel={vi.fn()}
      />
    );

    const waypointSelect = screen.getByLabelText(/map waypoint/i) as HTMLSelectElement;
    fireEvent.change(waypointSelect, { target: { value: "poi_name" } });
    expect(waypointSelect.value).toBe("poi_name");

    const elevationSelect = screen.getByLabelText(/map elevation/i) as HTMLSelectElement;
    fireEvent.change(elevationSelect, { target: { value: "[Ignore]" } });
    expect(elevationSelect.value).toBe("[Ignore]");

    const applyButton = screen.getByRole("button", { name: /apply column mappings/i });
    fireEvent.click(applyButton);

    expect(handleConfirm).toHaveBeenCalledWith({
      Waypoint: "poi_name",
      Elevation: "[Ignore]",
    });
  });

  it("calls onCancel when cancel button is clicked", () => {
    const handleCancel = vi.fn();
    render(
      <ColumnMappingModal
        isOpen={true}
        unmappedColumns={["Waypoint"]}
        sampleRows={sampleRows}
        targetFields={targetFields}
        onConfirm={vi.fn()}
        onCancel={handleCancel}
      />
    );

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    fireEvent.click(cancelButton);
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });
});

