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
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BulkActionsToolbar } from "../../../components/bulk/BulkActionsToolbar";
import { BulkOperationsModal } from "../../../components/bulk/BulkOperationsModal";

describe("BulkActionsToolbar (T-030 / REQ-MAIN-026)", () => {
  it("renders nothing when selectedCount is 0", () => {
    const { container } = render(
      <BulkActionsToolbar
        selectedCount={0}
        onOpenBulkEdit={vi.fn()}
        onOpenBulkDelete={vi.fn()}
        onDeselectAll={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders selected count badge and enables buttons when between 1 and 500", () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const onDeselect = vi.fn();

    render(
      <BulkActionsToolbar
        selectedCount={25}
        onOpenBulkEdit={onEdit}
        onOpenBulkDelete={onDelete}
        onDeselectAll={onDeselect}
      />,
    );

    expect(screen.getByText("25 POIs selected")).toBeDefined();
    expect(screen.queryByTestId("ceiling-exceeded-warning")).toBeNull();

    const editBtn = screen.getByTestId("bulk-edit-btn");
    expect(editBtn).not.toBeDisabled();
    fireEvent.click(editBtn);
    expect(onEdit).toHaveBeenCalledTimes(1);

    const deleteBtn = screen.getByTestId("bulk-delete-btn");
    expect(deleteBtn).not.toBeDisabled();
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledTimes(1);

    const deselectBtn = screen.getByTestId("deselect-all-btn");
    fireEvent.click(deselectBtn);
    expect(onDeselect).toHaveBeenCalledTimes(1);
  });

  it("displays ceiling warning and disables action buttons when selectedCount > 500 (REQ-MAIN-026)", () => {
    render(
      <BulkActionsToolbar
        selectedCount={501}
        onOpenBulkEdit={vi.fn()}
        onOpenBulkDelete={vi.fn()}
        onDeselectAll={vi.fn()}
      />,
    );

    expect(screen.getByTestId("ceiling-exceeded-warning")).toBeDefined();
    expect(
      screen.getByText(/Maximum batch ceiling is 500 POIs/i),
    ).toBeDefined();
    expect(screen.getByTestId("bulk-edit-btn")).toBeDisabled();
    expect(screen.getByTestId("bulk-delete-btn")).toBeDisabled();
  });
});

describe("BulkOperationsModal (T-031 / REQ-MAIN-027 to REQ-MAIN-034)", () => {
  it("renders delete mode with confirmation warning and calls onConfirmDelete", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <BulkOperationsModal
        isOpen={true}
        onClose={onClose}
        selectedPoiIds={["poi-1", "poi-2"]}
        mode="delete"
        onConfirmEdit={vi.fn()}
        onConfirmDelete={onDelete}
      />,
    );

    expect(screen.getByText(/Bulk Delete 2 POIs/i)).toBeDefined();
    expect(screen.getByText(/Permanent Deletion Warning/i)).toBeDefined();

    const confirmBtn = screen.getByTestId("confirm-bulk-action-btn");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it("submits rating edit action", async () => {
    const onEdit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <BulkOperationsModal
        isOpen={true}
        onClose={onClose}
        selectedPoiIds={["poi-1"]}
        mode="edit"
        onConfirmEdit={onEdit}
        onConfirmDelete={vi.fn()}
      />,
    );

    // Default operation is set_rating
    const opt4 = screen.getByTestId("bulk-rating-opt-4");
    fireEvent.click(opt4);

    const submitBtn = screen.getByTestId("confirm-bulk-action-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onEdit).toHaveBeenCalledWith("set_rating", { rating: 4 });
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it("submits address update action with clear_fields", async () => {
    const onEdit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <BulkOperationsModal
        isOpen={true}
        onClose={onClose}
        selectedPoiIds={["poi-1"]}
        mode="edit"
        onConfirmEdit={onEdit}
        onConfirmDelete={vi.fn()}
      />,
    );

    const select = screen.getByTestId("bulk-operation-type-select");
    fireEvent.change(select, { target: { value: "update_address" } });

    const cityInput = screen.getByTestId("bulk-city-input");
    fireEvent.change(cityInput, { target: { value: "Kyoto" } });

    const countryInput = screen.getByTestId("bulk-country-input");
    fireEvent.change(countryInput, { target: { value: "Japan" } });

    const submitBtn = screen.getByTestId("confirm-bulk-action-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onEdit).toHaveBeenCalledWith("update_address", {
        address: {
          city: "Kyoto",
          state_province: null,
          country: "Japan",
          clear_fields: [],
        },
      });
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
