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
import type { components } from "../types/ingest-staging-api";

export type CandidateItem = components["schemas"]["CandidateItemResponse"];
export type CandidateUpdateRequest = components["schemas"]["CandidateUpdateRequest"];

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

export const ingestApi = {
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
};

