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

import { ApiError, generateTraceparent, type ProblemDetails } from "./api";

export type ExportFormat = "csv" | "json" | "yaml";

export interface ExportPOIsPayload {
  poi_ids: string[];
  format: ExportFormat;
}

export interface ExportCandidatesPayload {
  job_id: string;
  candidate_ids: string[];
  format: ExportFormat;
}

/**
 * Triggers browser download of a Blob file.
 */
export function triggerFileDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.style.display = "none";
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 1000);
}

/**
 * Helper to fetch a streaming file download endpoint and trigger browser save.
 */
async function fetchAndDownloadBlob(
  endpoint: string,
  body: unknown,
  fallbackFilename: string,
): Promise<void> {
  const { traceparent, traceId } = generateTraceparent();
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  headers.set("X-Source", "web-client");
  headers.set("X-Destination", "backend");
  headers.set("traceparent", traceparent);
  headers.set("X-Vistarae-Trace-Id", traceId);

  const token = localStorage.getItem("vistarae_auth_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const mockUserId = localStorage.getItem("vistarae_mock_user_id");
  if (mockUserId) {
    headers.set("X-Mock-User-Id", mockUserId);
    const mockTier = localStorage.getItem("vistarae_mock_user_tier") || "LOW";
    headers.set("X-Mock-User-Tier", mockTier);
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let problem: ProblemDetails;
    try {
      problem = (await response.json()) as ProblemDetails;
    } catch {
      problem = {
        title: "Export Failed",
        status: response.status,
        detail: `Export failed with HTTP status ${response.status}`,
      };
    }
    throw new ApiError(problem);
  }

  // Extract filename from Content-Disposition header if present
  let filename = fallbackFilename;
  const disposition = response.headers.get("Content-Disposition");
  if (disposition) {
    const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1];
    }
  }

  const blob = await response.blob();
  triggerFileDownload(blob, filename);
}

/**
 * Export selected committed POIs from Vistarae Explorer.
 */
export async function exportExplorerPOIs(
  poiIds: string[],
  format: ExportFormat = "csv",
): Promise<void> {
  if (!poiIds || poiIds.length === 0) {
    throw new Error(
      "No records selected. Please select at least one record to export.",
    );
  }
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `vistarae_pois_${dateStr}.${format}`;
  await fetchAndDownloadBlob(
    "/api/v1/export/pois",
    { poi_ids: poiIds, format },
    filename,
  );
}

/**
 * Export selected candidate POIs from Phase 1 Triage.
 */
export async function exportPhase1Candidates(
  jobId: string,
  candidateIds: string[],
  format: ExportFormat = "csv",
): Promise<void> {
  if (!candidateIds || candidateIds.length === 0) {
    throw new Error(
      "No records selected. Please select at least one record to export.",
    );
  }
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `vistarae_phase1_candidates_${dateStr}.${format}`;
  await fetchAndDownloadBlob(
    "/api/v1/export/candidates/phase1",
    { job_id: jobId, candidate_ids: candidateIds, format },
    filename,
  );
}

/**
 * Export selected candidate POIs from Phase 2 Review.
 */
export async function exportPhase2Candidates(
  jobId: string,
  candidateIds: string[],
  format: ExportFormat = "csv",
): Promise<void> {
  if (!candidateIds || candidateIds.length === 0) {
    throw new Error(
      "No records selected. Please select at least one record to export.",
    );
  }
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `vistarae_phase2_candidates_${dateStr}.${format}`;
  await fetchAndDownloadBlob(
    "/api/v1/export/candidates/phase2",
    { job_id: jobId, candidate_ids: candidateIds, format },
    filename,
  );
}
