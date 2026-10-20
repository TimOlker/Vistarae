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

"""Unit tests for job progress polling and tenant boundary isolation (T-028).

Verifies:
- GET /api/ingest/jobs/{job_id} returns 200 OK with progress counters and percent
- Cross-tenant requests return 404 ProblemDetails (REQ-INGEST-015)
- Non-existent job IDs return 404 ProblemDetails
- Staged duplicate candidate items are correctly mapped to response schemas
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import IngestJob, User
from vistarae_core.domain.value_objects import DuplicateTriageStatus, IngestJobStatus

from services.ingest.dependencies import get_current_user, get_ingest_repo
from services.ingest.main import app


@pytest.mark.asyncio
class TestJobProgressEndpoints:
    """Verifies job polling and access control."""

    async def test_get_job_progress_success(self) -> None:
        """Asserts job progress and staged duplicates are returned for tenant owner."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
        )

        mock_repo = AsyncMock()
        mock_repo.get_job_by_id.return_value = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.PROCESSING,
            total_rows=100,
            processed_rows=50,
            duplicate_payloads=[
                {
                    "row_number": 42,
                    "raw_name": "Yosemite Valley Overlook",
                    "candidate_poi_id": str(uuid.uuid4()),
                    "match_type": "POTENTIAL_DUPLICATE",
                    "similarity_score": 0.88,
                    "distance_meters": 120.5,
                    "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                    "staged_poi_data": {"name": "Yosemite Valley Overlook"},
                }
            ],
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/jobs/{job_id}")
                assert response.status_code == 200
                data = response.json()
                assert data["job_id"] == str(job_id)
                assert data["job_status"] == "PROCESSING"
                assert data["total_rows"] == 100
                assert data["processed_rows"] == 50
                assert data["percent_complete"] == 50.0
                assert len(data["duplicate_payloads"]) == 1
                dup = data["duplicate_payloads"][0]
                assert dup["row_number"] == 42
                assert dup["triage_status"] == "PENDING_REVIEW"
        finally:
            app.dependency_overrides.clear()

    async def test_get_job_tenant_boundary_404(self) -> None:
        """Asserts request for another tenant's job returns 404 ProblemDetails."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="attacker@example.com",
        )

        mock_repo = AsyncMock()
        # Returns None because user_id does not match job's user_id in repository
        mock_repo.get_job_by_id.return_value = None

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/jobs/{job_id}")
                assert response.status_code == 404
                assert response.headers["content-type"] == "application/problem+json"
                body = response.json()
                assert body["status"] == 404
                assert "not found" in body["title"].lower()
        finally:
            app.dependency_overrides.clear()
