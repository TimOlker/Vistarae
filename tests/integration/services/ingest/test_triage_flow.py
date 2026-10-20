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

"""Integration tests for duplicate candidate triage lifecycle (T-030).

Verifies:
- Retrieval of job progress and staged duplicates via GET /api/ingest/jobs/{job_id}
- Submission of triage decisions via POST /api/ingest/jobs/{job_id}/triage
- POI persistence and list association for COMMITTED decisions
- Candidate discarding for REJECTED decisions
- Job status transition from PARTIAL_SUCCESS to COMPLETED when all items are triaged
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import POI, IngestJob, User
from vistarae_core.domain.value_objects import DuplicateTriageStatus, IngestJobStatus
from vistarae_core.ports.repositories import IIngestJobRepository

from services.ingest.dependencies import get_current_user, get_ingest_repo, get_poi_repo
from services.ingest.main import app


class InMemoryIngestRepo(IIngestJobRepository):
    """In-memory test double of IIngestJobRepository for integration flow."""

    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, IngestJob] = {}

    async def create_job(self, job: IngestJob) -> IngestJob:
        self.jobs[job.id] = job
        return job

    async def get_job_by_id(self, job_id: uuid.UUID, user_id: uuid.UUID) -> IngestJob | None:
        job = self.jobs.get(job_id)
        if job and job.user_id == user_id:
            return job
        return None

    async def increment_processed_rows(
        self, job_id: uuid.UUID, user_id: uuid.UUID, count: int = 1
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if job:
            job.processed_rows += count
        return job

    async def append_duplicate_payload(
        self, job_id: uuid.UUID, user_id: uuid.UUID, duplicate: dict[str, Any]
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if job:
            job.duplicate_payloads.append(duplicate)
        return job

    async def append_error_summary(
        self, job_id: uuid.UUID, user_id: uuid.UUID, error: dict[str, Any]
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if job:
            job.error_summary.append(error)
        return job

    async def update_job_status(
        self, job_id: uuid.UUID, user_id: uuid.UUID, status: IngestJobStatus
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if job:
            job.job_status = status
        return job

    async def get_pending_duplicates(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        job = await self.get_job_by_id(job_id, user_id)
        if not job:
            return []
        return [
            item
            for item in job.duplicate_payloads
            if item.get("triage_status") == DuplicateTriageStatus.PENDING_REVIEW.value
        ]

    async def update_duplicate_triage_decisions(
        self, job_id: uuid.UUID, user_id: uuid.UUID, decisions: list[dict[str, Any]]
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if not job:
            return None

        dec_map = {d["row_number"]: d["decision"] for d in decisions}
        for item in job.duplicate_payloads:
            row_num = item.get("row_number")
            if row_num in dec_map:
                dec = dec_map[row_num]
                item["triage_status"] = dec.value if hasattr(dec, "value") else str(dec)

        return await self.recalculate_job_status(job_id, user_id)

    async def recalculate_job_status(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if not job:
            return None

        has_pending = any(
            item.get("triage_status") == DuplicateTriageStatus.PENDING_REVIEW.value
            for item in job.duplicate_payloads
        )
        if job.processed_rows >= job.total_rows and job.total_rows > 0:
            if has_pending:
                job.job_status = IngestJobStatus.PARTIAL_SUCCESS
            else:
                job.job_status = IngestJobStatus.COMPLETED
        return job


class InMemoryPOIRepo:
    """In-memory test double of IPOIRepository for integration flow."""

    def __init__(self) -> None:
        self.pois: dict[uuid.UUID, POI] = {}
        self.attached_lists: list[tuple[uuid.UUID, list[uuid.UUID], list[uuid.UUID]]] = []

    async def create(self, poi: POI) -> POI:
        self.pois[poi.id] = poi
        return poi

    async def bulk_attach_lists(
        self, user_id: uuid.UUID, poi_ids: list[uuid.UUID], list_ids: list[uuid.UUID]
    ) -> None:
        self.attached_lists.append((user_id, poi_ids, list_ids))


@pytest.mark.asyncio
class TestTriageFlowIntegration:
    """Verifies end-to-end triage lifecycle across poll and triage endpoints."""

    async def test_full_triage_lifecycle(self) -> None:
        """Executes full polling, committing one duplicate and rejecting the other."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        target_list_id = uuid.uuid4()

        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
            full_name="Alex Traveler",
        )

        staged_items = [
            {
                "row_number": 1,
                "raw_name": "Tunnel View Point",
                "candidate_poi_id": str(uuid.uuid4()),
                "match_type": "POTENTIAL_DUPLICATE",
                "similarity_score": 0.88,
                "distance_meters": 35.0,
                "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                "staged_poi_data": {
                    "name": "Tunnel View Point",
                    "latitude": 37.7156,
                    "longitude": -119.6775,
                    "address": "Wawona Rd",
                    "city": "Yosemite National Park",
                    "states": ["California"],
                    "countries": ["United States"],
                    "visited_date": "2026-06-15",
                },
            },
            {
                "row_number": 2,
                "raw_name": "Bridalveil Fall Trail",
                "candidate_poi_id": str(uuid.uuid4()),
                "match_type": "POTENTIAL_DUPLICATE",
                "similarity_score": 0.75,
                "distance_meters": 80.0,
                "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                "staged_poi_data": {
                    "name": "Bridalveil Fall Trail",
                    "latitude": 37.7167,
                    "longitude": -119.6465,
                },
            },
        ]

        initial_job = IngestJob(
            id=job_id,
            user_id=user_id,
            job_status=IngestJobStatus.PARTIAL_SUCCESS,
            total_rows=2,
            processed_rows=2,
            duplicate_payloads=staged_items,
            target_list_id=target_list_id,
            error_summary=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        mock_ingest_repo = InMemoryIngestRepo()
        await mock_ingest_repo.create_job(initial_job)

        mock_poi_repo = InMemoryPOIRepo()

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_ingest_repo
        app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # 1. Poll progress endpoint
                get_resp = await client.get(f"/jobs/{job_id}")
                assert get_resp.status_code == 200
                progress = get_resp.json()
                assert progress["job_status"] == "PARTIAL_SUCCESS"
                assert progress["total_rows"] == 2
                assert progress["processed_rows"] == 2
                assert progress["percent_complete"] == 100.0
                assert len(progress["duplicate_payloads"]) == 2

                # 2. Submit partial triage (commit row 1)
                triage_resp_1 = await client.post(
                    f"/jobs/{job_id}/triage",
                    json={"decisions": [{"row_number": 1, "decision": "COMMITTED"}]},
                )
                assert triage_resp_1.status_code == 200
                res1 = triage_resp_1.json()
                # Status remains PARTIAL_SUCCESS because row 2 is still PENDING_REVIEW
                assert res1["job_status"] == "PARTIAL_SUCCESS"
                # Check POI was created
                assert len(mock_poi_repo.pois) == 1
                created_poi = list(mock_poi_repo.pois.values())[0]
                assert created_poi.name == "Tunnel View Point"
                assert created_poi.geom.lat == 37.7156
                assert len(mock_poi_repo.attached_lists) == 1
                assert mock_poi_repo.attached_lists[0][2] == [target_list_id]

                # 3. Submit remaining triage (reject row 2)
                triage_resp_2 = await client.post(
                    f"/jobs/{job_id}/triage",
                    json={"decisions": [{"row_number": 2, "decision": "REJECTED"}]},
                )
                assert triage_resp_2.status_code == 200
                res2 = triage_resp_2.json()
                # All duplicates resolved! Status transitions to COMPLETED
                assert res2["job_status"] == "COMPLETED"
                # No additional POI created for rejected candidate
                assert len(mock_poi_repo.pois) == 1
        finally:
            app.dependency_overrides.clear()
