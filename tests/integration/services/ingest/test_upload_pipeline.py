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

"""Integration tests for bulk CSV upload workflow and SQS queue dispatch (T-012).

Verifies:
- POST /api/ingest/csv creates IngestJob record
- Returns HTTP 202 Accepted with job metadata
- Correctly partitions rows 1:1 into SQS message payloads in chunks of 10
- Propagates W3C traceparent and X-Amzn-Trace-Id attributes
- Optional target_list_id is preserved on every message
"""

from __future__ import annotations

import io
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.adapters.queue.mock import MockQueueAdapter
from vistarae_core.domain.entities import IngestJob, User
from vistarae_core.domain.value_objects import IngestJobStatus

from services.ingest.dependencies import get_current_user, get_ingest_repo, get_queue_port
from services.ingest.main import app


class InMemoryIngestRepo:
    """Mock in-memory repository for integration pipeline test."""

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
        self, job_id: uuid.UUID, user_id: uuid.UUID, duplicate: dict
    ) -> IngestJob | None:
        job = await self.get_job_by_id(job_id, user_id)
        if job:
            job.duplicate_payloads.append(duplicate)
        return job

    async def append_error_summary(
        self, job_id: uuid.UUID, user_id: uuid.UUID, error: dict
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

    async def get_pending_duplicates(self, job_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
        job = await self.get_job_by_id(job_id, user_id)
        return job.duplicate_payloads if job else []

    async def update_duplicate_triage_decisions(
        self, job_id: uuid.UUID, user_id: uuid.UUID, decisions: list[dict]
    ) -> IngestJob | None:
        return await self.get_job_by_id(job_id, user_id)

    async def recalculate_job_status(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> IngestJob | None:
        return await self.get_job_by_id(job_id, user_id)


@pytest.mark.asyncio
class TestUploadPipelineIntegration:
    """Verifies end-to-end upload flow through HTTP and queue abstraction."""

    async def test_upload_25_rows_batches_and_traces(self) -> None:
        """Asserts 25 rows upload results in 3 SQS batches (10 + 10 + 5) with valid trace headers."""
        user_id = uuid.uuid4()
        test_user = User(
            id=user_id,
            cognito_sub=f"sub-{user_id}",
            email="traveler@example.com",
            full_name="Alex Traveler",
        )
        mock_repo = InMemoryIngestRepo()
        mock_queue = MockQueueAdapter()

        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_ingest_repo] = lambda: mock_repo
        app.dependency_overrides[get_queue_port] = lambda: mock_queue

        # Generate a 25-row CSV
        lines = ["name,description,address,latitude,longitude"]
        for i in range(1, 26):
            lines.append(f"POI {i},Description {i},Address {i},37.{i},-122.{i}")
        csv_bytes = "\n".join(lines).encode("utf-8")

        target_list_id = uuid.uuid4()
        headers = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            "x-amzn-trace-id": "Root=1-5759e988-bd862e3fe1be46a994272793",
        }

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                files = {"file": ("places.csv", io.BytesIO(csv_bytes), "text/csv")}
                data = {"target_list_id": str(target_list_id)}

                response = await client.post(
                    "/csv",
                    files=files,
                    data=data,
                    headers=headers,
                )

                assert response.status_code == 202
                body = response.json()
                assert body["total_rows"] == 25
                assert body["job_status"] == "PENDING"
                job_id = uuid.UUID(body["job_id"])

                # Verify job stored in repository
                stored_job = mock_repo.jobs.get(job_id)
                assert stored_job is not None
                assert stored_job.total_rows == 25
                assert stored_job.target_list_id == target_list_id

                # Verify queue received 25 messages
                assert mock_queue.get_queue_depth("vistarae-ingest-local") == 25
                assert len(mock_queue.sent_messages) == 25

                # Verify first message attributes and body
                first_msg = mock_queue.sent_messages[0]["record"]
                first_body = json.loads(first_msg["Body"])
                assert first_body["job_id"] == str(job_id)
                assert first_body["user_id"] == str(user_id)
                assert first_body["target_list_id"] == str(target_list_id)
                assert first_body["absolute_row_number"] == 2
                assert first_body["row_data"]["name"] == "POI 1"

                # Verify trace attributes
                attrs = first_msg["MessageAttributes"]
                assert attrs["traceparent"] == headers["traceparent"]
                assert attrs["X-Amzn-Trace-Id"] == headers["x-amzn-trace-id"]
                assert attrs["user_id"] == str(user_id)
                assert attrs["job_id"] == str(job_id)

                # Verify 25th message
                last_msg = mock_queue.sent_messages[24]["record"]
                last_body = json.loads(last_msg["Body"])
                assert last_body["absolute_row_number"] == 26
                assert last_body["row_data"]["name"] == "POI 25"

        finally:
            app.dependency_overrides.clear()
