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

import { apiFetch } from "./api";
import type { components } from "../types/api";

export type CandidateItem = Omit<
  components["schemas"]["CandidateItemResponse"],
  | "no_websites"
  | "is_user_overridden"
  | "is_duplicate"
  | "created_at"
  | "updated_at"
  | "update_coordinates"
  | "is_skipped"
  | "country_code"
> & {
  country_code?: string | null;
  no_websites?: boolean;
  is_user_overridden?: boolean;
  is_duplicate?: boolean;
  created_at?: string;
  updated_at?: string;
  update_coordinates?: boolean;
  is_skipped?: boolean;
  hero_image_urls?: string[];
  [key: string]: any;
};
export type CandidateUpdateRequest =
  components["schemas"]["CandidateUpdateRequest"];

export interface CandidateListFilterParams {
  completeness?:
    | "all"
    | "complete"
    | "incomplete"
    | "missing_photo"
    | "missing_location"
    | "missing_websites";
  disposition?: string;
  search?: string;
  phase?: "phase_1_triage" | "phase_2_enriched";
}

export interface BatchEditCandidatesPayload {
  candidate_ids: string[];
  country?: string | null;
  state_province?: string | null;
  city?: string | null;
  date_visited?: string | null;
  add_tag?: string | null;
  remove_tag?: string | null;
  no_address?: boolean | null;
  no_websites?: boolean | null;
}

export interface CandidateListResult {
  job_id: string;
  total_candidates: number;
  candidates: CandidateItem[];
}

export interface PhaseTransitionResult {
  job_id: string;
  message: string;
  advanced_count: number;
  ignored_count: number;
}

export interface CommitSummaryResult {
  job_id: string;
  committed_count: number;
  created_pois: string[];
  merged_pois: string[];
  message: string;
}

export interface JobCancellationResult {
  job_id: string;
  purged_count: number;
  message: string;
}

export interface ActiveSessionResult {
  has_active_session: boolean;
  job_id: string | null;
  phase_state: "phase_1_triage" | "phase_2_enriched" | null;
  total_candidates: number;
  created_at: string | null;
  target_list_id?: string | null;
  target_list_name?: string | null;
}

export interface Phase2ProgressResult {
  job_id: string;
  total_count: number;
  enriched_count: number;
  is_complete: boolean;
  percent_complete: number;
  status_message: string;
}

export type BulkEnrichmentStatus =
  | "QUEUED"
  | "CANARY_DISPATCH"
  | "ACTIVE"
  | "DRAINING"
  | "CANCELLED"
  | "COMPLETED"
  | "BLOCKED"
  | "FAILED";

export interface BulkEnrichmentInitiatePayload {
  candidate_ids?: string[];
  force_refresh?: boolean;
  all_eligible?: boolean;
}

export interface BulkEnrichmentInitiateResult {
  session_id: string;
  job_id: string;
  total_enqueued: number;
  status: BulkEnrichmentStatus;
  message: string;
}

export interface BulkEnrichmentProgressResult {
  session_id: string;
  job_id: string;
  status: BulkEnrichmentStatus;
  total_count: number;
  completed_count: number;
  success_count: number;
  skipped_count?: number;
  issue_count: number;
  remaining_count: number;
  in_flight_count: number;
  percent_complete: number;
  elapsed_seconds: number;
  average_duration_ms?: number | null;
  can_cancel: boolean;
  status_message: string;
}

export interface BulkEnrichmentCancelResult {
  session_id: string;
  status: BulkEnrichmentStatus;
  message: string;
}

export interface BulkEnrichmentHeartbeatResult {
  session_id: string;
  acknowledged: boolean;
  is_active: boolean;
}

export interface CandidateIssueDetail {
  candidate_id: string;
  poi_name: string;
  row_index: number;
  category:
    | "RESOURCE_EXHAUSTION"
    | "INPUT_DATA_ISSUE"
    | "TEMPORARY_FAILURE"
    | "INTERRUPTED"
    | string;
  severity: "blocking" | "warning" | "info" | string;
  error_type: string;
  reason: string;
  suggested_action: string;
  is_retryable: boolean;
}

export interface BulkEnrichmentSummaryResult {
  session_id: string;
  job_id: string;
  status: BulkEnrichmentStatus;
  total_candidates: number;
  succeeded_count: number;
  skipped_count?: number;
  temporary_error_count: number;
  blocking_error_count: number;
  internal_error_count: number;
  unprocessed_count: number;
  total_duration_ms: number;
  average_duration_ms: number;
  total_resources_used: number;
  termination_reason: string;
  candidate_issues?: CandidateIssueDetail[];
  created_at: string;
}

export interface BulkEnrichmentRecoveryResult {
  result_id: string;
  job_id: string;
  session_id: string;
  status: BulkEnrichmentStatus;
  failed_at: string;
  unprocessed_count: number;
  failure_count: number;
  total_candidates: number;
  termination_reason: string;
}

export interface BulkEnrichmentRecoveryActionPayload {
  result_id: string;
  action: "resume" | "dismiss" | "cancel";
}

export interface BulkEnrichmentRecoveryActionResult {
  acknowledged: boolean;
  job_id: string;
  initial_filter?: string | null;
}

export const ingestApi = {
  async listStagingCandidates(
    jobId: string,
    filters?: CandidateListFilterParams,
  ): Promise<CandidateListResult> {
    const params = new URLSearchParams();
    if (filters?.completeness && filters.completeness !== "all") {
      params.append("completeness", filters.completeness);
    }
    if (filters?.disposition) {
      params.append("disposition", filters.disposition);
    }
    if (filters?.search) {
      params.append("search", filters.search);
    }
    if (filters?.phase) {
      params.append("phase", filters.phase);
    }
    const qs = params.toString();
    const url = qs
      ? `/api/ingest/jobs/${jobId}/candidates?${qs}`
      : `/api/ingest/jobs/${jobId}/candidates`;
    return apiFetch<CandidateListResult>(url, { method: "GET" });
  },

  async updateStagingCandidate(
    jobId: string,
    candidateId: string,
    update: CandidateUpdateRequest,
  ): Promise<CandidateItem> {
    return apiFetch<CandidateItem>(
      `/api/ingest/jobs/${jobId}/candidates/${candidateId}`,
      {
        method: "PUT",
        body: JSON.stringify(update),
      },
    );
  },

  async enrichSingleCandidate(
    jobId: string,
    candidateId: string,
    forceRefresh?: boolean,
  ): Promise<CandidateItem> {
    const query = forceRefresh ? "?force_refresh=true" : "";
    return apiFetch<CandidateItem>(
      `/api/ingest/jobs/${jobId}/candidates/${candidateId}/enrich${query}`,
      {
        method: "POST",
        timeoutMs: 60000,
      },
    );
  },

  async enrichAllCandidates(
    jobId: string,
    forceRefresh?: boolean,
  ): Promise<{ job_id: string; message: string; enqueued_count: number }> {
    const query = forceRefresh ? "?force_refresh=true" : "";
    return apiFetch<{
      job_id: string;
      message: string;
      enqueued_count: number;
    }>(`/api/ingest/jobs/${jobId}/enrich-all${query}`, {
      method: "POST",
      timeoutMs: 30000,
    });
  },

  async batchEditCandidates(
    jobId: string,
    payload: BatchEditCandidatesPayload,
  ): Promise<{ updated_count: number }> {
    return apiFetch<{ updated_count: number }>(
      `/api/ingest/jobs/${jobId}/candidates/batch-edit`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  async commitWorkbenchJob(jobId: string): Promise<CommitSummaryResult> {
    return apiFetch<CommitSummaryResult>(`/api/ingest/jobs/${jobId}/commit`, {
      method: "POST",
    });
  },

  async getJobCandidates(
    jobId: string,
    phase?: "phase_1_triage" | "phase_2_enriched",
  ): Promise<CandidateListResult> {
    const url = phase
      ? `/api/ingest/jobs/${jobId}/candidates?phase=${phase}`
      : `/api/ingest/jobs/${jobId}/candidates`;
    return apiFetch<CandidateListResult>(url, { method: "GET" });
  },

  async updateCandidate(
    jobId: string,
    candidateId: string,
    update: CandidateUpdateRequest,
  ): Promise<CandidateItem> {
    return apiFetch<CandidateItem>(
      `/api/ingest/jobs/${jobId}/candidates/${candidateId}`,
      {
        method: "PATCH",
        body: JSON.stringify(update),
      },
    );
  },

  async proceedPhase1(jobId: string): Promise<PhaseTransitionResult> {
    return apiFetch<PhaseTransitionResult>(
      `/api/ingest/jobs/${jobId}/phase1/proceed`,
      {
        method: "POST",
      },
    );
  },

  async cancelPhase1(jobId: string): Promise<JobCancellationResult> {
    return apiFetch<JobCancellationResult>(
      `/api/ingest/jobs/${jobId}/phase1/cancel`,
      {
        method: "POST",
      },
    );
  },

  async commitPhase2(jobId: string): Promise<CommitSummaryResult> {
    return apiFetch<CommitSummaryResult>(
      `/api/ingest/jobs/${jobId}/phase2/commit`,
      {
        method: "POST",
      },
    );
  },

  async cancelPhase2(jobId: string): Promise<JobCancellationResult> {
    return apiFetch<JobCancellationResult>(
      `/api/ingest/jobs/${jobId}/phase2/cancel`,
      {
        method: "POST",
      },
    );
  },

  async enrichPhase2(jobId: string): Promise<PhaseTransitionResult> {
    return apiFetch<PhaseTransitionResult>(
      `/api/ingest/jobs/${jobId}/phase2/enrich`,
      {
        method: "POST",
      },
    );
  },

  async getPhase2Progress(jobId: string): Promise<Phase2ProgressResult> {
    return apiFetch<Phase2ProgressResult>(
      `/api/ingest/jobs/${jobId}/phase2/progress`,
      {
        method: "GET",
      },
    );
  },

  async backToPhase1(jobId: string): Promise<PhaseTransitionResult> {
    return apiFetch<PhaseTransitionResult>(
      `/api/ingest/jobs/${jobId}/phase2/back-to-phase1`,
      {
        method: "POST",
      },
    );
  },

  async getActiveSession(): Promise<ActiveSessionResult> {
    return apiFetch<ActiveSessionResult>("/api/ingest/active-session", {
      method: "GET",
    });
  },

  async wipeActiveSession(): Promise<JobCancellationResult> {
    return apiFetch<JobCancellationResult>("/api/ingest/active-session", {
      method: "DELETE",
    });
  },

  async startBulkEnrichment(
    jobId: string,
    payload: BulkEnrichmentInitiatePayload,
  ): Promise<BulkEnrichmentInitiateResult> {
    return apiFetch<BulkEnrichmentInitiateResult>(
      `/api/ingest/jobs/${jobId}/bulk-enrichment/start`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  async getBulkEnrichmentProgress(
    jobId: string,
  ): Promise<BulkEnrichmentProgressResult> {
    return apiFetch<BulkEnrichmentProgressResult>(
      `/api/ingest/jobs/${jobId}/bulk-enrichment/progress`,
      {
        method: "GET",
      },
    );
  },

  async cancelBulkEnrichment(
    jobId: string,
  ): Promise<BulkEnrichmentCancelResult> {
    return apiFetch<BulkEnrichmentCancelResult>(
      `/api/ingest/jobs/${jobId}/bulk-enrichment/cancel`,
      {
        method: "POST",
      },
    );
  },

  async heartbeatBulkEnrichment(
    jobId: string,
  ): Promise<BulkEnrichmentHeartbeatResult> {
    return apiFetch<BulkEnrichmentHeartbeatResult>(
      `/api/ingest/jobs/${jobId}/bulk-enrichment/heartbeat`,
      {
        method: "POST",
      },
    );
  },

  async getBulkEnrichmentSummary(
    jobId: string,
  ): Promise<BulkEnrichmentSummaryResult> {
    return apiFetch<BulkEnrichmentSummaryResult>(
      `/api/ingest/jobs/${jobId}/bulk-enrichment/summary`,
      {
        method: "GET",
      },
    );
  },

  async checkBulkEnrichmentRecovery(): Promise<BulkEnrichmentRecoveryResult | null> {
    return apiFetch<BulkEnrichmentRecoveryResult | null>(
      "/api/ingest/bulk-enrichment/recovery",
      {
        method: "GET",
      },
    );
  },

  async respondBulkEnrichmentRecovery(
    payload: BulkEnrichmentRecoveryActionPayload,
  ): Promise<BulkEnrichmentRecoveryActionResult> {
    return apiFetch<BulkEnrichmentRecoveryActionResult>(
      "/api/ingest/bulk-enrichment/recovery/respond",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
};
