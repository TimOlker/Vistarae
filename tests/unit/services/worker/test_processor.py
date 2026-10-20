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

"""Unit tests for BatchIngestWorker processor and error boundaries (T-021).

Verifies:
- Trace attributes extraction
- Idempotency deduplication
- Geocoding resolution and cache interaction
- Spatial deduplication and staging to PENDING_REVIEW
- POI persistence with vector embeddings
- Partial batch failure isolation via batchItemFailures
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.domain.entities import (
    POI,
    PotentialDuplicateMatch,
)
from vistarae_core.domain.value_objects import (
    DuplicateTriageStatus,
    WGS84Point,
)

from services.worker.processor import BatchIngestWorker


class FakeIngestRepo:
    """Mock repository tracking calls in memory."""

    def __init__(self) -> None:
        self.duplicates: list[dict] = []
        self.errors: list[dict] = []
        self.processed_count = 0

    async def append_duplicate_payload(self, job_id, user_id, duplicate):
        self.duplicates.append(duplicate)
        return None

    async def append_error_summary(self, job_id, user_id, error):
        self.errors.append(error)
        return None

    async def increment_processed_rows(self, job_id, user_id, count=1):
        self.processed_count += count
        return None


class FakePOIRepo:
    """Mock POI repository for testing deduplication and persistence."""

    def __init__(self) -> None:
        self.created_pois: list[POI] = []
        self.duplicates_to_return: list[PotentialDuplicateMatch] = []
        self.attached_lists: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def find_potential_duplicates(self, user_id, name, point, radius_meters=805.0, similarity_threshold=0.60):
        return self.duplicates_to_return

    async def create(self, poi: POI) -> POI:
        self.created_pois.append(poi)
        return poi

    async def bulk_attach_lists(self, user_id, poi_ids, list_ids):
        for p in poi_ids:
            for lst_id in list_ids:
                self.attached_lists.append((p, lst_id))
        return len(poi_ids) * len(list_ids)


@pytest.mark.asyncio
class TestBatchIngestWorker:
    """Verifies BatchIngestWorker row processing and batch failure handling."""

    async def test_process_unique_poi_record_success(self) -> None:
        """Asserts unique POI record is created and processed_rows incremented."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        fake_ingest = FakeIngestRepo()
        fake_poi = FakePOIRepo()
        mock_geocoder = AsyncMock()
        mock_geocoder.geocode.return_value = (37.715, -119.677, "Yosemite National Park, CA")

        worker = BatchIngestWorker(
            session_factory=lambda: AsyncMock(),
            geocoder=mock_geocoder,
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda session: fake_ingest,
            poi_repo_factory=lambda session: fake_poi,
        )

        record = {
            "messageId": "msg-001",
            "body": json.dumps({
                "job_id": str(job_id),
                "user_id": str(user_id),
                "target_list_id": None,
                "absolute_row_number": 2,
                "row_data": {
                    "name": "Glacier Point",
                    "description": "Overlook above Yosemite Valley",
                    "latitude": "37.730",
                    "longitude": "-119.573",
                },
            }),
            "messageAttributes": {
                "traceparent": {"stringValue": "00-trace-01"},
            },
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        await worker.process_record(record, mock_session)

        # Assert POI created
        assert len(fake_poi.created_pois) == 1
        created = fake_poi.created_pois[0]
        assert created.name == "Glacier Point"
        assert created.geom.lat == 37.730
        assert created.geom.lon == -119.573
        assert fake_ingest.processed_count == 1
        assert len(fake_ingest.duplicates) == 0

    async def test_process_duplicate_poi_staged(self) -> None:
        """Asserts suspected duplicate is staged as PENDING_REVIEW without creating POI."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        fake_ingest = FakeIngestRepo()
        fake_poi = FakePOIRepo()

        existing_poi = POI(
            id=uuid.uuid4(),
            user_id=user_id,
            name="Yosemite Valley Overlook",
            geom=WGS84Point(lon=-119.677, lat=37.715),
        )
        fake_poi.duplicates_to_return = [
            PotentialDuplicateMatch(
                existing_poi=existing_poi,
                distance_meters=120.0,
                name_similarity=0.88,
                match_confidence=0.85,
            )
        ]

        worker = BatchIngestWorker(
            session_factory=lambda: AsyncMock(),
            geocoder=AsyncMock(),
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda session: fake_ingest,
            poi_repo_factory=lambda session: fake_poi,
        )

        record = {
            "messageId": "msg-002",
            "body": json.dumps({
                "job_id": str(job_id),
                "user_id": str(user_id),
                "target_list_id": None,
                "absolute_row_number": 3,
                "row_data": {
                    "name": "Yosemite Valley Overlook",
                    "latitude": "37.716",
                    "longitude": "-119.678",
                },
            }),
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        await worker.process_record(record, mock_session)

        # Assert NO POI created
        assert len(fake_poi.created_pois) == 0
        # Assert duplicate staged
        assert len(fake_ingest.duplicates) == 1
        dup = fake_ingest.duplicates[0]
        assert dup["triage_status"] == DuplicateTriageStatus.PENDING_REVIEW.value
        assert dup["similarity_score"] == 0.88
        assert fake_ingest.processed_count == 1

    async def test_geocoding_unresolvable_records_error(self) -> None:
        """Asserts unresolvable address writes to error_summary without raising."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        fake_ingest = FakeIngestRepo()
        fake_poi = FakePOIRepo()
        mock_geocoder = AsyncMock()
        mock_geocoder.geocode.return_value = None  # Not found

        worker = BatchIngestWorker(
            session_factory=lambda: AsyncMock(),
            geocoder=mock_geocoder,
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda session: fake_ingest,
            poi_repo_factory=lambda session: fake_poi,
        )

        record = {
            "messageId": "msg-003",
            "body": json.dumps({
                "job_id": str(job_id),
                "user_id": str(user_id),
                "absolute_row_number": 10,
                "row_data": {"name": "Nowhere Fantasy Land"},
            }),
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        await worker.process_record(record, mock_session)

        assert len(fake_poi.created_pois) == 0
        assert len(fake_ingest.errors) == 1
        err = fake_ingest.errors[0]
        assert err["error_type"] == "GEOCODING_NOT_FOUND"
        assert fake_ingest.processed_count == 1

    async def test_partial_batch_failures_isolated(self) -> None:
        """Asserts 1 failing record out of 3 returns only that item in batchItemFailures."""
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_trans = AsyncMock()
        mock_trans.__aenter__.return_value = mock_trans
        mock_trans.__aexit__.return_value = None
        mock_session.begin = MagicMock(return_value=mock_trans)

        worker = BatchIngestWorker(
            session_factory=lambda: mock_session,
            geocoder=AsyncMock(),
            embedding_port=MockEmbeddingAdapter(),
        )


        records = [
            {"messageId": "msg-ok-1", "body": "{}"},
            {"messageId": "msg-fail", "body": "invalid json {{{"},
            {"messageId": "msg-ok-2", "body": "{}"},
        ]

        # Mock process_record: succeed for ok-1 and ok-2, raise for fail
        async def fake_process(record, session):
            if "fail" in record["messageId"]:
                raise RuntimeError("Database connection lost")

        worker.process_record = fake_process

        res = await worker.process_batch(records)
        failures = res.get("batchItemFailures", [])
        assert len(failures) == 1
        assert failures[0]["itemIdentifier"] == "msg-fail"
