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

"""Contract and boundary validation tests for bulk AI enrichment schemas and endpoints (REQ-ENR-020, REQ-ENR-022, REQ-ENR-032).

Validates:
- All bulk enrichment boundary models strictly inherit StrictBaseModel with extra="forbid"
- Unrecognized or forbidden fields are rejected with ValidationError
- Requests and responses match the OpenAPI contract in specs/018-bulk-ai-enrich/contracts/bulk_enrichment_api.yaml
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from vistarae_core.domain.enums import BulkEnrichmentStatus
from vistarae_core.schemas.bulk_enrichment import (
    BulkEnrichmentInitiateRequest,
    BulkEnrichmentInitiateResponse,
    BulkEnrichmentProgressResponse,
    BulkEnrichmentRecoveryActionRequest,
    BulkEnrichmentRecoveryResponse,
    BulkEnrichmentSummaryResponse,
)


class TestBulkEnrichmentSchemaContracts:
    """Verifies that all bulk enrichment schemas enforce strict boundaries (extra='forbid')."""

    def test_initiate_request_extra_forbid(self) -> None:
        """BulkEnrichmentInitiateRequest rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            BulkEnrichmentInitiateRequest.model_validate(
                {"candidate_ids": [str(uuid4())], "unknown_field": "disallowed"}
            )
        assert any(e["type"] == "extra_forbidden" for e in exc_info.value.errors())

    def test_recovery_action_request_extra_forbid(self) -> None:
        """BulkEnrichmentRecoveryActionRequest rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            BulkEnrichmentRecoveryActionRequest.model_validate(
                {
                    "result_id": str(uuid4()),
                    "action": "resume",
                    "invalid_flag": True,
                }
            )
        assert any(e["type"] == "extra_forbidden" for e in exc_info.value.errors())

    def test_recovery_action_invalid_enum(self) -> None:
        """BulkEnrichmentRecoveryActionRequest rejects invalid action values."""
        with pytest.raises(ValidationError) as exc_info:
            BulkEnrichmentRecoveryActionRequest.model_validate(
                {
                    "result_id": str(uuid4()),
                    "action": "invalid_action_value",
                }
            )
        assert any(e["type"] == "enum" for e in exc_info.value.errors())

    def test_initiate_response_schema_fields(self) -> None:
        """BulkEnrichmentInitiateResponse validates compliant payload."""
        resp = BulkEnrichmentInitiateResponse(
            session_id=uuid4(),
            job_id=uuid4(),
            total_enqueued=5,
            status=BulkEnrichmentStatus.CANARY_DISPATCH,
            message="Canary dispatched",
        )
        assert resp.total_enqueued == 5
        assert resp.status == BulkEnrichmentStatus.CANARY_DISPATCH

    def test_progress_response_schema_fields(self) -> None:
        """BulkEnrichmentProgressResponse validates compliant telemetry."""
        resp = BulkEnrichmentProgressResponse(
            session_id=uuid4(),
            job_id=uuid4(),
            status=BulkEnrichmentStatus.ACTIVE,
            total_count=10,
            completed_count=5,
            success_count=4,
            issue_count=1,
            remaining_count=5,
            in_flight_count=3,
            percent_complete=50,
            elapsed_seconds=15,
            average_duration_ms=3000,
            can_cancel=True,
            status_message="Processing candidates",
        )
        assert resp.percent_complete == 50
        assert resp.average_duration_ms == 3000

    def test_summary_response_schema_fields(self) -> None:
        """BulkEnrichmentSummaryResponse validates post-run statistics."""
        summary = BulkEnrichmentSummaryResponse(
            session_id=uuid4(),
            job_id=uuid4(),
            status=BulkEnrichmentStatus.COMPLETED,
            total_candidates=10,
            succeeded_count=9,
            temporary_error_count=1,
            blocking_error_count=0,
            internal_error_count=0,
            unprocessed_count=0,
            total_duration_ms=15000,
            average_duration_ms=1500,
            total_resources_used=10,
            termination_reason="Success",
            created_at=datetime.now(UTC),
        )
        assert summary.succeeded_count == 9
        assert summary.unprocessed_count == 0

    def test_recovery_response_schema_fields(self) -> None:
        """BulkEnrichmentRecoveryResponse validates unacknowledged run representation."""
        recovery = BulkEnrichmentRecoveryResponse(
            result_id=uuid4(),
            job_id=uuid4(),
            session_id=uuid4(),
            status=BulkEnrichmentStatus.BLOCKED,
            failed_at=datetime.now(UTC),
            unprocessed_count=8,
            failure_count=1,
            total_candidates=10,
            termination_reason="HTTP 402 Payment Required",
        )
        assert recovery.status == BulkEnrichmentStatus.BLOCKED
        assert recovery.unprocessed_count == 8
