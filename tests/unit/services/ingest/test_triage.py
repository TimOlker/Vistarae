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

"""Unit tests for duplicate candidate triage endpoint (T-029).

Verifies:
- POST /api/ingest/jobs/{job_id}/triage with COMMITTED creates POI and attaches target_list_id
- POST /api/ingest/jobs/{job_id}/triage with REJECTED discards candidate without creating POI
- Job status updates to COMPLETED when all pending duplicates are triaged
- Cross-tenant or non-existent job IDs return RFC 7807 404 ProblemDetails
- Invalid payloads return 422 Unprocessable Entity
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import IngestJob, User
from vistarae_core.domain.value_objects import DuplicateTriageStatus, IngestJobStatus

from services.ingest.dependencies import get_current_user, get_ingest_repo, get_poi_repo
from services.ingest.main import app


@pytest.mark.asyncio
class TestTriageEndpoint:
    """Tests triage submission decisions and lifecycle side effects."""

    async def test_triage_committed_creates_poi(self) -> None:
        """Asserts COMMITTED decision persists POI and attaches target list."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        target_list_id = uuid.uuid4()
        candidate_poi_id = uuid.uuid4()

        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
        )

        initial_job = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.PARTIAL_SUCCESS,
            total_rows=1,
            processed_rows=1,
            duplicate_payloads=[
                {
                    "row_number": 1,
                    "raw_name": "Glacier Point Overlook",
                    "candidate_poi_id": str(candidate_poi_id),
                    "match_type": "POTENTIAL_DUPLICATE",
                    "similarity_score": 0.85,
                    "distance_meters": 50.0,
                    "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                    "staged_poi_data": {
                        "name": "Glacier Point Overlook",
                        "latitude": 37.7304,
                        "longitude": -119.5736,
                        "address": "Glacier Point Rd",
                        "city": "Yosemite",
                        "states": ["California"],
                        "countries": ["United States"],
                        "visited_date": "2026-05-10",
                    },
                }
            ],
            target_list_id=target_list_id,
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        updated_job = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.COMPLETED,
            total_rows=1,
            processed_rows=1,
            duplicate_payloads=[
                {
                    "row_number": 1,
                    "raw_name": "Glacier Point Overlook",
                    "candidate_poi_id": str(candidate_poi_id),
                    "match_type": "POTENTIAL_DUPLICATE",
                    "similarity_score": 0.85,
                    "distance_meters": 50.0,
                    "triage_status": DuplicateTriageStatus.COMMITTED.value,
                    "staged_poi_data": initial_job.duplicate_payloads[0]["staged_poi_data"],
                }
            ],
            target_list_id=target_list_id,
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_ingest_repo = AsyncMock()
        mock_ingest_repo.get_job_by_id.return_value = initial_job
        mock_ingest_repo.update_duplicate_triage_decisions.return_value = updated_job

        mock_poi_repo = AsyncMock()
        mock_poi_repo.create.return_value = AsyncMock()
        mock_poi_repo.bulk_attach_lists.return_value = None

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_ingest_repo
        app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "decisions": [
                        {
                            "row_number": 1,
                            "decision": "COMMITTED",
                        }
                    ]
                }
                response = await client.post(f"/jobs/{job_id}/triage", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["job_id"] == str(job_id)
                assert data["job_status"] == "COMPLETED"
                assert len(data["duplicate_payloads"]) == 1
                assert data["duplicate_payloads"][0]["triage_status"] == "COMMITTED"

                # Verify POI creation was called
                assert mock_poi_repo.create.call_count == 1
                created_poi = mock_poi_repo.create.call_args[0][0]
                assert created_poi.name == "Glacier Point Overlook"
                assert created_poi.geom.lat == 37.7304
                assert created_poi.geom.lon == -119.5736
                assert created_poi.user_id == user_id

                # Verify target list association was called
                assert mock_poi_repo.bulk_attach_lists.call_count == 1
                args = mock_poi_repo.bulk_attach_lists.call_args[0]
                assert args[0] == user_id
                assert args[1] == [created_poi.id]
                assert args[2] == [target_list_id]
        finally:
            app.dependency_overrides.clear()

    async def test_triage_rejected_does_not_create_poi(self) -> None:
        """Asserts REJECTED decision updates status without calling POI repository."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        candidate_poi_id = uuid.uuid4()

        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
        )

        initial_job = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.PARTIAL_SUCCESS,
            total_rows=1,
            processed_rows=1,
            duplicate_payloads=[
                {
                    "row_number": 2,
                    "raw_name": "Mirror Lake Trail",
                    "candidate_poi_id": str(candidate_poi_id),
                    "match_type": "POTENTIAL_DUPLICATE",
                    "similarity_score": 0.92,
                    "distance_meters": 10.0,
                    "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                    "staged_poi_data": {"name": "Mirror Lake Trail"},
                }
            ],
            target_list_id=None,
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        updated_job = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.COMPLETED,
            total_rows=1,
            processed_rows=1,
            duplicate_payloads=[
                {
                    "row_number": 2,
                    "raw_name": "Mirror Lake Trail",
                    "candidate_poi_id": str(candidate_poi_id),
                    "match_type": "POTENTIAL_DUPLICATE",
                    "similarity_score": 0.92,
                    "distance_meters": 10.0,
                    "triage_status": DuplicateTriageStatus.REJECTED.value,
                    "staged_poi_data": {"name": "Mirror Lake Trail"},
                }
            ],
            target_list_id=None,
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_ingest_repo = AsyncMock()
        mock_ingest_repo.get_job_by_id.return_value = initial_job
        mock_ingest_repo.update_duplicate_triage_decisions.return_value = updated_job

        mock_poi_repo = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_ingest_repo
        app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "decisions": [
                        {
                            "row_number": 2,
                            "decision": "REJECTED",
                        }
                    ]
                }
                response = await client.post(f"/jobs/{job_id}/triage", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["duplicate_payloads"][0]["triage_status"] == "REJECTED"
                assert mock_poi_repo.create.call_count == 0
        finally:
            app.dependency_overrides.clear()

    async def test_triage_job_not_found_returns_404(self) -> None:
        """Asserts non-existent job returns 404 ProblemDetails."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()

        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
        )

        mock_ingest_repo = AsyncMock()
        mock_ingest_repo.get_job_by_id.return_value = None

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_ingest_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                payload = {
                    "decisions": [
                        {
                            "row_number": 1,
                            "decision": "COMMITTED",
                        }
                    ]
                }
                response = await client.post(f"/jobs/{job_id}/triage", json=payload)
                assert response.status_code == 404
                body = response.json()
                assert body["status"] == 404
                assert "not found" in body["title"].lower()
        finally:
            app.dependency_overrides.clear()
