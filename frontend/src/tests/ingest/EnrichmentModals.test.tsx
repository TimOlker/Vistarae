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
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CSVEnrichmentSummaryModal } from "../../components/ingest/CSVEnrichmentSummaryModal";
import { BulkEnrichmentRecoveryModal } from "../../components/common/BulkEnrichmentRecoveryModal";
import {
  ingestApi,
  type BulkEnrichmentRecoveryResult,
} from "../../services/ingestApi";

vi.mock("../../services/ingestApi", () => ({
  ingestApi: {
    getBulkEnrichmentSummary: vi.fn(),
    respondBulkEnrichmentRecovery: vi.fn(),
  },
}));

describe("EnrichmentModals", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("CSVEnrichmentSummaryModal", () => {
    it("renders post-run statistics and handles filter incomplete action", async () => {
      (ingestApi.getBulkEnrichmentSummary as any).mockResolvedValue({
        session_id: "sess-123",
        job_id: "job-123",
        status: "COMPLETED",
        total_candidates: 10,
        succeeded_count: 8,
        temporary_error_count: 1,
        blocking_error_count: 0,
        internal_error_count: 1,
        unprocessed_count: 0,
        total_duration_ms: 12000,
        average_duration_ms: 1200,
        total_resources_used: 10,
        termination_reason: "All candidates processed.",
        created_at: new Date().toISOString(),
      });

      const onFilterIncomplete = vi.fn();
      const onClose = vi.fn();

      render(
        <CSVEnrichmentSummaryModal
          jobId="job-123"
          isOpen={true}
          onClose={onClose}
          onFilterIncomplete={onFilterIncomplete}
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("enrichment-summary-modal"),
        ).toBeInTheDocument();
        expect(screen.getByText("Total Enqueued")).toBeInTheDocument();
        expect(screen.getByText("10")).toBeInTheDocument();
        expect(screen.getByText("8")).toBeInTheDocument();
        expect(screen.getByText("Review Incomplete POIs")).toBeInTheDocument();
      });

      const filterBtn = screen.getByTestId("filter-incomplete-button");
      fireEvent.click(filterBtn);
      expect(onFilterIncomplete).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe("BulkEnrichmentRecoveryModal", () => {
    const mockRun: BulkEnrichmentRecoveryResult = {
      result_id: "res-123",
      job_id: "job-123",
      session_id: "sess-123",
      status: "BLOCKED",
      failed_at: new Date().toISOString(),
      unprocessed_count: 9,
      failure_count: 1,
      total_candidates: 10,
      termination_reason: "HTTP 402 Resource Exhausted",
    };

    it("handles resume action", async () => {
      (ingestApi.respondBulkEnrichmentRecovery as any).mockResolvedValue({
        acknowledged: true,
        job_id: "job-123",
        initial_filter: "incomplete",
      });

      const onResume = vi.fn();
      const onDismiss = vi.fn();
      const onClose = vi.fn();

      render(
        <BulkEnrichmentRecoveryModal
          isOpen={true}
          recoveryRun={mockRun}
          onResume={onResume}
          onDismiss={onDismiss}
          onClose={onClose}
        />,
      );

      expect(
        screen.getByTestId("bulk-enrichment-recovery-modal"),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/HTTP 402 Resource Exhausted/),
      ).toBeInTheDocument();
      expect(screen.getByText(/9 of 10/)).toBeInTheDocument();

      const resumeBtn = screen.getByTestId("recovery-resume-button");
      fireEvent.click(resumeBtn);

      await waitFor(() => {
        expect(ingestApi.respondBulkEnrichmentRecovery).toHaveBeenCalledWith({
          result_id: "res-123",
          action: "resume",
        });
        expect(onResume).toHaveBeenCalledWith("job-123", "incomplete");
      });
    });

    it("handles dismiss action", async () => {
      (ingestApi.respondBulkEnrichmentRecovery as any).mockResolvedValue({
        acknowledged: true,
        job_id: "job-123",
        initial_filter: null,
      });

      const onResume = vi.fn();
      const onDismiss = vi.fn();
      const onClose = vi.fn();

      render(
        <BulkEnrichmentRecoveryModal
          isOpen={true}
          recoveryRun={mockRun}
          onResume={onResume}
          onDismiss={onDismiss}
          onClose={onClose}
        />,
      );

      const dismissBtn = screen.getByTestId("recovery-dismiss-button");
      fireEvent.click(dismissBtn);

      await waitFor(() => {
        expect(ingestApi.respondBulkEnrichmentRecovery).toHaveBeenCalledWith({
          result_id: "res-123",
          action: "dismiss",
        });
        expect(onDismiss).toHaveBeenCalled();
      });
    });
  });
});
