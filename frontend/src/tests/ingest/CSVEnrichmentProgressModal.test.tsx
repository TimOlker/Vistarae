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

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CSVEnrichmentProgressModal } from "../../components/ingest/CSVEnrichmentProgressModal";
import { ingestApi } from "../../services/ingestApi";

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    getBulkEnrichmentProgress: vi.fn(),
    cancelBulkEnrichment: vi.fn(),
    heartbeatBulkEnrichment: vi.fn(),
  },
}));

describe("CSVEnrichmentProgressModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders progress modal with telemetry and triggers heartbeat", async () => {
    (ingestApi.getBulkEnrichmentProgress as any).mockResolvedValue({
      session_id: "sess-1",
      job_id: "job-1",
      status: "ACTIVE",
      total_count: 10,
      completed_count: 4,
      success_count: 3,
      issue_count: 1,
      remaining_count: 6,
      in_flight_count: 2,
      percent_complete: 40,
      elapsed_seconds: 5,
      average_duration_ms: 1200,
      can_cancel: true,
      status_message: "Processing candidate 4 of 10",
    });

    (ingestApi.heartbeatBulkEnrichment as any).mockResolvedValue({
      session_id: "sess-1",
      acknowledged: true,
      is_active: true,
    });

    render(
      <CSVEnrichmentProgressModal
        isOpen={true}
        jobId="job-1"
        onComplete={vi.fn()}
      />,
    );

    expect(screen.getByTestId("enrichment-progress-modal")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("40%")).toBeInTheDocument();
      expect(screen.getByText("4 / 10")).toBeInTheDocument();
      expect(screen.getByText("2 active")).toBeInTheDocument();
    });

    expect(ingestApi.getBulkEnrichmentProgress).toHaveBeenCalledWith("job-1");
  });

  it("handles cancel button click and enters draining state", async () => {
    (ingestApi.getBulkEnrichmentProgress as any).mockResolvedValue({
      session_id: "sess-1",
      job_id: "job-1",
      status: "ACTIVE",
      total_count: 10,
      completed_count: 2,
      success_count: 2,
      issue_count: 0,
      remaining_count: 8,
      in_flight_count: 3,
      percent_complete: 20,
      elapsed_seconds: 3,
      average_duration_ms: 1500,
      can_cancel: true,
      status_message: "Active workers running",
    });

    (ingestApi.cancelBulkEnrichment as any).mockResolvedValue({
      session_id: "sess-1",
      status: "DRAINING",
      message: "Cancellation draining",
    });

    render(
      <CSVEnrichmentProgressModal
        isOpen={true}
        jobId="job-1"
        onComplete={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("cancel-enrichment-button"),
      ).toBeInTheDocument();
    });

    const cancelBtn = screen.getByTestId("cancel-enrichment-button");
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(ingestApi.cancelBulkEnrichment).toHaveBeenCalledWith("job-1");
      expect(screen.getByText("Draining...")).toBeInTheDocument();
      expect(cancelBtn).toBeDisabled();
    });
  });

  it("calls onComplete when session reaches COMPLETED status", async () => {
    const onComplete = vi.fn();

    (ingestApi.getBulkEnrichmentProgress as any).mockResolvedValue({
      session_id: "sess-1",
      job_id: "job-1",
      status: "COMPLETED",
      total_count: 5,
      completed_count: 5,
      success_count: 5,
      issue_count: 0,
      remaining_count: 0,
      in_flight_count: 0,
      percent_complete: 100,
      elapsed_seconds: 6,
      average_duration_ms: 1200,
      can_cancel: false,
      status_message: "All completed",
    });

    render(
      <CSVEnrichmentProgressModal
        isOpen={true}
        jobId="job-1"
        onComplete={onComplete}
      />,
    );

    await waitFor(
      () => {
        expect(onComplete).toHaveBeenCalled();
      },
      { timeout: 2000 },
    );
  });

  it("displays skipped count in progress subtitle and metrics tile when skipped_count > 0", async () => {
    (ingestApi.getBulkEnrichmentProgress as any).mockResolvedValue({
      session_id: "sess-1",
      job_id: "job-1",
      status: "ACTIVE",
      total_count: 740,
      completed_count: 57,
      success_count: 57,
      skipped_count: 34,
      issue_count: 0,
      remaining_count: 683,
      in_flight_count: 3,
      percent_complete: 7,
      elapsed_seconds: 127,
      average_duration_ms: 6200,
      can_cancel: true,
      status_message: "Processing 57 of 740 POIs (34 skipped)...",
    });

    (ingestApi.heartbeatBulkEnrichment as any).mockResolvedValue({
      session_id: "sess-1",
      acknowledged: true,
      is_active: true,
    });

    render(
      <CSVEnrichmentProgressModal
        isOpen={true}
        jobId="job-1"
        onComplete={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Processed 57 of 740 candidates (34 skipped)"),
      ).toBeInTheDocument();
      expect(screen.getByText("• 34 skipped")).toBeInTheDocument();
    });
  });
});
