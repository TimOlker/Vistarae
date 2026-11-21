# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic v2 boundary schemas for bulk AI enrichment workflows.

Enforces Constitution Principle 5: StrictBaseModel with extra='forbid',
validate_assignment=True, and str_strip_whitespace=True.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.enums import BulkEnrichmentStatus, RecoveryPromptAction
from vistarae_core.schemas.base import StrictBaseModel

__all__ = [
    "BulkEnrichmentCancelResponse",
    "BulkEnrichmentHeartbeatResponse",
    "BulkEnrichmentInitiateRequest",
    "BulkEnrichmentInitiateResponse",
    "BulkEnrichmentProgressResponse",
    "BulkEnrichmentRecoveryActionRequest",
    "BulkEnrichmentRecoveryResponse",
    "BulkEnrichmentSummaryResponse",
    "CandidateIssueDetail",
]


class BulkEnrichmentInitiateRequest(StrictBaseModel):
    """Payload to initiate a canary-gated bulk AI enrichment session."""

    candidate_ids: list[UUID] | None = Field(
        default=None,
        description="Explicit candidate IDs to enrich. If empty or None, all eligible candidates are targeted.",
    )
    force_refresh: bool = Field(
        default=False,
        description="If True, recomputes all target fields regardless of pre-existing data, preserving user overrides.",
    )
    all_eligible: bool = Field(
        default=False,
        description="Explicit confirmation flag when candidate_ids is empty, confirming all eligible POIs should be enqueued.",
    )


class BulkEnrichmentInitiateResponse(StrictBaseModel):
    """Response returned upon successful initiation and canary dispatch."""

    session_id: UUID = Field(description="Unique UUIDv4 session identifier.")
    job_id: UUID = Field(description="Associated staging import job UUID.")
    total_enqueued: int = Field(description="Total number of candidates placed in queue.")
    status: BulkEnrichmentStatus = Field(description="Initial lifecycle status of the session.")
    message: str = Field(description="Human-readable informational message.")


class BulkEnrichmentProgressResponse(StrictBaseModel):
    """Real-time progress metrics for active enrichment polling."""

    session_id: UUID = Field(description="Unique UUIDv4 session identifier.")
    job_id: UUID = Field(description="Associated staging import job UUID.")
    status: BulkEnrichmentStatus = Field(description="Current lifecycle status of the session.")
    total_count: int = Field(description="Total candidates queued.")
    completed_count: int = Field(description="Count of candidates completed so far.")
    success_count: int = Field(description="Count of candidates successfully enriched.")
    skipped_count: int = Field(
        default=0,
        description="Count of candidates skipped from AI re-examination (e.g. already complete or pre-existing).",
    )
    issue_count: int = Field(description="Count of candidates encountering errors.")
    remaining_count: int = Field(description="Count of candidates remaining in queue.")
    in_flight_count: int = Field(description="Count of workers currently active.")
    percent_complete: int = Field(description="Integer percentage of completion (0-100).")
    elapsed_seconds: int = Field(description="Total seconds elapsed since session start.")
    average_duration_ms: int | None = Field(
        default=None,
        description="Average execution duration per completed POI in milliseconds.",
    )
    can_cancel: bool = Field(
        default=True,
        description="Whether the active session accepts graceful cancellation.",
    )
    status_message: str = Field(description="Descriptive status indicator text.")


class BulkEnrichmentCancelResponse(StrictBaseModel):
    """Response returned upon requesting graceful session cancellation."""

    session_id: UUID = Field(description="Unique UUIDv4 session identifier.")
    status: BulkEnrichmentStatus = Field(
        description="Updated session status (DRAINING or CANCELLED)."
    )
    message: str = Field(description="Cancellation confirmation message.")


class BulkEnrichmentHeartbeatResponse(StrictBaseModel):
    """Response acknowledging client heartbeat signal."""

    session_id: UUID = Field(description="Unique UUIDv4 session identifier.")
    acknowledged: bool = Field(default=True, description="True if heartbeat was recorded.")
    is_active: bool = Field(description="True if session remains active.")


class CandidateIssueDetail(StrictBaseModel):
    """Diagnostic details for a candidate that failed or was left incomplete/unprocessed."""

    candidate_id: UUID = Field(description="UUID of the affected candidate.")
    poi_name: str = Field(description="POI title/name of the candidate.")
    row_index: int = Field(default=0, description="Row index in the staging batch.")
    category: str = Field(
        description="Category: 'RESOURCE_EXHAUSTION', 'INPUT_DATA_ISSUE', 'TEMPORARY_FAILURE', or 'INTERRUPTED'."
    )
    severity: str = Field(
        default="warning",
        description="Issue severity: 'blocking', 'warning', or 'info'."
    )
    error_type: str = Field(
        default="GENERAL_ISSUE",
        description="Specific error code e.g. MISSING_COORDINATES, NO_PHOTOS_FOUND, QUOTA_EXHAUSTED."
    )
    reason: str = Field(
        description="Human-readable explanation of why this candidate had an issue or was not enriched."
    )
    suggested_action: str = Field(
        description="Actionable guidance for the traveler (e.g. edit POI, retry, check credits)."
    )
    is_retryable: bool = Field(
        default=True,
        description="Whether immediate retry is safe without changing data."
    )


class BulkEnrichmentSummaryResponse(StrictBaseModel):
    """Comprehensive post-run summary window statistics."""

    session_id: UUID = Field(description="Unique UUIDv4 session identifier.")
    job_id: UUID = Field(description="Associated staging import job UUID.")
    status: BulkEnrichmentStatus = Field(description="Final terminal status.")
    total_candidates: int = Field(description="Total candidates queued.")
    succeeded_count: int = Field(description="Count of candidates successfully enriched.")
    skipped_count: int = Field(
        default=0,
        description="Count of candidates skipped from AI re-examination.",
    )
    temporary_error_count: int = Field(description="Count of non-fatal external issue candidates.")
    blocking_error_count: int = Field(description="Count of blocking circuit-break errors.")
    internal_error_count: int = Field(description="Count of unexpected system errors.")
    unprocessed_count: int = Field(description="Count of candidates left unprocessed in queue.")
    total_duration_ms: int = Field(description="Total wall-clock duration in milliseconds.")
    average_duration_ms: int = Field(description="Mean candidate execution time in milliseconds.")
    total_resources_used: int = Field(description="Total API calls and token units consumed.")
    termination_reason: str = Field(
        description="Descriptive explanation of how/why session concluded."
    )
    candidate_issues: list[CandidateIssueDetail] = Field(
        default_factory=list,
        description="Itemized list of candidates that encountered issues or were left unprocessed.",
    )
    created_at: datetime = Field(description="Timestamp when audit summary was recorded.")


class BulkEnrichmentRecoveryResponse(StrictBaseModel):
    """Details of the most recent unacknowledged failed or blocked enrichment run."""

    result_id: UUID = Field(description="Audit record UUID in bulk_enrichment_results.")
    job_id: UUID = Field(description="Associated staging import job UUID.")
    session_id: UUID = Field(description="Enrichment session UUID.")
    status: BulkEnrichmentStatus = Field(description="Failure status (BLOCKED or FAILED).")
    failed_at: datetime = Field(description="Timestamp when the run concluded.")
    unprocessed_count: int = Field(description="Number of remaining candidates left unenriched.")
    failure_count: int = Field(description="Number of candidates that encountered errors.")
    total_candidates: int = Field(description="Total candidates in the original queue.")
    termination_reason: str = Field(description="Explanation of why processing was halted.")


class BulkEnrichmentRecoveryActionRequest(StrictBaseModel):
    """Traveler action in response to the login recovery prompt."""

    result_id: UUID = Field(description="Target audit record UUID.")
    action: RecoveryPromptAction = Field(description="User response: resume, dismiss, or cancel.")
