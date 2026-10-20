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
    get_ingest_repo,
    get_poi_repo,
    get_queue_port,
)


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
