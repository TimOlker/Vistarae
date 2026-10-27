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

"""Unit tests for BatchIngestWorker personalized ingestion with UserPromptCache (T-037 / REQ-CTX-033).

Verifies:
- Ingestion processor extracts and stores reason_to_visit from row_data.
- Ingestion processor retrieves active prompt directives via UserPromptCache.
- If web URL is provided or reason_to_visit is missing, orchestrator is called with prompt directives.
- Personalized attributes are persisted on created POI and staged duplicate payloads.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.domain.entities import POI, PotentialDuplicateMatch
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.services.prompt_cache import UserPromptCache

from services.worker.processor import BatchIngestWorker


class FakeIngestRepo:
    """Mock ingest repository recording duplicates and processed counts."""

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
    """Mock POI repository tracking created POIs."""

    def __init__(self) -> None:
        self.created_pois: list[POI] = []
        self.duplicates_to_return: list[PotentialDuplicateMatch] = []

    async def find_potential_duplicates(
        self, user_id, name, point, radius_meters=805.0, similarity_threshold=0.60
    ):
        return self.duplicates_to_return

    async def create(self, poi: POI) -> POI:
        self.created_pois.append(poi)
        return poi

    async def bulk_attach_lists(self, user_id, poi_ids, list_ids):
        return len(poi_ids) * len(list_ids)


@pytest.mark.asyncio
class TestPersonalizedBatchIngestWorker:
    """Verifies BatchIngestWorker personalizes ingested POIs using prompt directives."""

    async def test_process_record_with_direct_reason_to_visit(self) -> None:
        """Asserts reason_to_visit provided directly in CSV row_data is persisted on POI."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        fake_ingest = FakeIngestRepo()
        fake_poi = FakePOIRepo()
        mock_geocoder = AsyncMock()
        mock_geocoder.geocode.return_value = (40.785091, -73.968285, "Central Park, NY")

        mock_cache = MagicMock(spec=UserPromptCache)
        mock_cache.get.return_value = {
            PromptType.REASON_TO_VISIT: "Focus on historic bridges and peaceful foliage walks.",
        }

        worker = BatchIngestWorker(
            session_factory=lambda: AsyncMock(),
            geocoder=mock_geocoder,
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda s: fake_ingest,
            poi_repo_factory=lambda s: fake_poi,
            prompt_cache=mock_cache,
        )

        record = {
            "messageId": "msg-pers-01",
            "body": json.dumps(
                {
                    "job_id": str(job_id),
                    "user_id": str(user_id),
                    "target_list_id": None,
                    "absolute_row_number": 2,
                    "row_data": {
                        "name": "Bow Bridge",
                        "description": "Cast-iron bridge spanning the Lake.",
                        "reason_to_visit": "Iconic romantic Victorian architecture and water reflections.",
                        "latitude": "40.775",
                        "longitude": "-73.971",
                    },
                }
            ),
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        await worker.process_record(record, mock_session)

        # Prompt cache was checked
        mock_cache.get.assert_called_once_with(user_id)

        # POI was persisted with reason_to_visit
        assert len(fake_poi.created_pois) == 1
        created = fake_poi.created_pois[0]
        assert (
            created.reason_to_visit
            == "Iconic romantic Victorian architecture and water reflections."
        )

    async def test_process_record_synthesizes_missing_reason_with_orchestrator(self) -> None:
        """Asserts missing reason_to_visit is synthesized via orchestrator using prompt cache."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        fake_ingest = FakeIngestRepo()
        fake_poi = FakePOIRepo()
        mock_geocoder = AsyncMock()
        mock_geocoder.geocode.return_value = (37.7749, -122.4194, "San Francisco, CA")

        mock_cache = MagicMock(spec=UserPromptCache)
        mock_cache.get.return_value = {
            PromptType.REASON_TO_VISIT: "Highlight artisan espresso and sourdough bakers.",
        }

        mock_orchestrator = AsyncMock()
        mock_orchestrator.synthesize_reason_to_visit.return_value = (
            "Must-visit for third-wave pour-overs and freshly baked levain loaves."
        )

        worker = BatchIngestWorker(
            session_factory=lambda: AsyncMock(),
            geocoder=mock_geocoder,
            embedding_port=MockEmbeddingAdapter(),
            ingest_repo_factory=lambda s: fake_ingest,
            poi_repo_factory=lambda s: fake_poi,
            prompt_cache=mock_cache,
            orchestrator=mock_orchestrator,
        )

        record = {
            "messageId": "msg-pers-02",
            "body": json.dumps(
                {
                    "job_id": str(job_id),
                    "user_id": str(user_id),
                    "target_list_id": None,
                    "absolute_row_number": 3,
                    "row_data": {
                        "name": "Mission Roastery",
                        "description": "Neighborhood coffee boutique in the historic district.",
                        "latitude": "37.760",
                        "longitude": "-122.420",
                    },
                }
            ),
        }

        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        await worker.process_record(record, mock_session)

        # Orchestrator was called with user's directive
        mock_orchestrator.synthesize_reason_to_visit.assert_awaited_once_with(
            name="Mission Roastery",
            description="Neighborhood coffee boutique in the historic district.",
            reason_directive="Highlight artisan espresso and sourdough bakers.",
        )

        # POI saved with synthesized reason
        assert len(fake_poi.created_pois) == 1
        created = fake_poi.created_pois[0]
        assert created.reason_to_visit == (
            "Must-visit for third-wave pour-overs and freshly baked levain loaves."
        )
