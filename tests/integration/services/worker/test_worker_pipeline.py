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

"""Integration tests for worker batch processing pipeline (T-022).

Verifies:
- SQS consumer processing batches of messages
- Isolation of failing items via batchItemFailures
- Successful persistence of valid POI records
- Integration with lambda_handler entrypoint
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.domain.entities import POI

from services.worker.main import lambda_handler
from services.worker.processor import BatchIngestWorker


class InMemoryIngestRepo:
    """Mock repository for worker pipeline integration test."""

    def __init__(self) -> None:
        self.duplicates = []
        self.errors = []
        self.processed = 0

    async def append_duplicate_payload(self, job_id, user_id, duplicate):
        self.duplicates.append(duplicate)
        return None

    async def append_error_summary(self, job_id, user_id, error):
        self.errors.append(error)
        return None

    async def increment_processed_rows(self, job_id, user_id, count=1):
        self.processed += count
        return None


class InMemoryPOIRepo:
    """Mock POI repository for worker pipeline integration test."""

    def __init__(self) -> None:
        self.pois: list[POI] = []

    async def find_potential_duplicates(self, user_id, name, point, radius_meters=805.0, similarity_threshold=0.60):
        return []

    async def create(self, poi: POI) -> POI:
        self.pois.append(poi)
        return poi

    async def bulk_attach_lists(self, user_id, poi_ids, list_ids):
        return len(poi_ids) * len(list_ids)


@pytest.mark.asyncio
class TestWorkerPipelineIntegration:
    """Verifies end-to-end batch processing pipeline with error isolation."""

    async def test_worker_processes_batch_with_partial_failure(self) -> None:
        """Processes 5 records (4 valid, 1 malformed) and verifies 4 succeed and 1 returns in failures."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        in_memory_ingest = InMemoryIngestRepo()
        in_memory_poi = InMemoryPOIRepo()

        mock_geocoder = AsyncMock()
        mock_geocoder.geocode.return_value = (37.7749, -122.4194, "San Francisco, CA")

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_trans = AsyncMock()
        mock_trans.__aenter__.return_value = mock_trans
        mock_trans.__aexit__.return_value = None
        mock_session.begin = MagicMock(return_value=mock_trans)

        # Mock claim_row_idempotency: True
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = uuid.uuid4()
        mock_session.execute.return_value = mock_exec_result

        worker = BatchIngestWorker(
            session_factory=lambda: mock_session,
            geocoder=mock_geocoder,
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda s: in_memory_ingest,
            poi_repo_factory=lambda s: in_memory_poi,
        )

        records = []
        for i in range(1, 5):
            records.append({
                "messageId": f"msg-valid-{i}",
                "body": json.dumps({
                    "job_id": str(job_id),
                    "user_id": str(user_id),
                    "absolute_row_number": i + 1,
                    "row_data": {
                        "name": f"Valid Place {i}",
                        "latitude": f"37.{i}",
                        "longitude": f"-122.{i}",
                    },
                }),
                "messageAttributes": {"traceparent": {"stringValue": f"00-trace-{i}-01"}},
            })

        # Add 1 malformed record with corrupt JSON body
        records.append({
            "messageId": "msg-malformed-5",
            "body": "not-valid-json{{{",
        })

        result = await worker.process_batch(records)
        failures = result.get("batchItemFailures", [])

        # Only the 1 malformed message should fail
        assert len(failures) == 1
        assert failures[0]["itemIdentifier"] == "msg-malformed-5"

        # The 4 valid records should have succeeded and created POIs
        assert len(in_memory_poi.pois) == 4
        assert in_memory_ingest.processed == 4

    async def test_lambda_handler_invocation(self) -> None:
        """Verifies synchronous lambda_handler wraps asyncio and extracts records."""
        event = {
            "Records": [
                {
                    "messageId": "lambda-msg-1",
                    "body": json.dumps({
                        "job_id": str(uuid.uuid4()),
                        "user_id": str(uuid.uuid4()),
                        "absolute_row_number": 2,
                        "row_data": {"name": "Golden Gate Bridge", "latitude": "37.819", "longitude": "-122.478"},
                    }),
                }
            ]
        }

        with patch("services.worker.main.get_worker") as mock_get_worker:
            mock_worker_inst = AsyncMock()
            mock_worker_inst.process_batch.return_value = {"batchItemFailures": []}
            mock_get_worker.return_value = mock_worker_inst

            response = lambda_handler(event, None)
            assert response == {"batchItemFailures": []}
            mock_worker_inst.process_batch.assert_called_once_with(event["Records"])
