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

"""Unit tests for ingestion dependency providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from vistarae_core.adapters.queue.mock import MockQueueAdapter
from vistarae_core.adapters.queue.sqs import SQSQueueAdapter
from vistarae_core.adapters.repositories.ingest_repo import IngestJobRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository

from services.ingest.dependencies import (
    get_candidate_repo,
    get_duplicate_service,
    get_geocache_repo,
    get_geocoding_service,
    get_ingest_repo,
    get_poi_repo,
    get_queue_port,
    get_staging_service,
)
from vistarae_core.adapters.repositories.geocache_repo import SqlAlchemyGeocodingCacheRepository
from vistarae_core.adapters.repositories.ingest_candidate_repo import SqlAlchemyIngestCandidateRepository
from services.poi.services.duplicate_service import DuplicateTriageService
from services.poi.services.geocoding_service import GeocodingService
from services.ingest.services.staging_service import StagingService



def test_get_queue_port_testing_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts testing stage returns MockQueueAdapter."""
    monkeypatch.setenv("STAGE", "testing")
    adapter = get_queue_port()
    assert isinstance(adapter, MockQueueAdapter)


def test_get_queue_port_sqs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserts non-testing stage provides SQSQueueAdapter."""
    monkeypatch.setenv("STAGE", "local")
    with patch("services.ingest.dependencies.SQSQueueAdapter", spec=SQSQueueAdapter):
        import services.ingest.dependencies as deps

        deps._sqs_queue_adapter = None
        adapter = get_queue_port()
        assert adapter is not None


def test_get_ingest_repo() -> None:
    """Asserts get_ingest_repo returns IngestJobRepository."""
    mock_session = AsyncMock()
    repo = get_ingest_repo(mock_session)
    assert isinstance(repo, IngestJobRepository)


def test_get_poi_repo() -> None:
    """Asserts get_poi_repo returns SqlAlchemyPOIRepository."""
    mock_session = AsyncMock()
    repo = get_poi_repo(mock_session)
    assert isinstance(repo, SqlAlchemyPOIRepository)


def test_get_candidate_repo() -> None:
    mock_session = AsyncMock()
    repo = get_candidate_repo(mock_session)
    assert isinstance(repo, SqlAlchemyIngestCandidateRepository)


def test_get_geocache_repo() -> None:
    mock_session = AsyncMock()
    repo = get_geocache_repo(mock_session)
    assert isinstance(repo, SqlAlchemyGeocodingCacheRepository)


def test_get_geocoding_service() -> None:
    mock_cache_repo = AsyncMock()
    service = get_geocoding_service(mock_cache_repo)
    assert isinstance(service, GeocodingService)


def test_get_duplicate_service() -> None:
    mock_session = AsyncMock()
    service = get_duplicate_service(mock_session)
    assert isinstance(service, DuplicateTriageService)


def test_get_staging_service() -> None:
    mock_cand_repo = AsyncMock()
    mock_poi_repo = AsyncMock()
    mock_geo_svc = AsyncMock()
    mock_dup_svc = AsyncMock()
    svc = get_staging_service(mock_cand_repo, mock_poi_repo, mock_geo_svc, mock_dup_svc)
    assert isinstance(svc, StagingService)
