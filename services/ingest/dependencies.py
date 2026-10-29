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

"""FastAPI dependency injection providers for the ingestion service."""

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.queue.mock import MockQueueAdapter
from vistarae_core.adapters.queue.sqs import SQSQueueAdapter
from vistarae_core.adapters.repositories.ingest_candidate_repo import (
    SqlAlchemyIngestCandidateRepository,
)
from vistarae_core.adapters.repositories.ingest_repo import IngestJobRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.ports.queue import IQueuePort
from vistarae_core.ports.repositories import (
    IIngestCandidateRepository,
    IIngestJobRepository,
    IPOIRepository,
)

from services.ingest.services.staging_service import StagingService
from services.user.dependencies import get_current_user

__all__ = [
    "get_candidate_repo",
    "get_current_user",
    "get_ingest_repo",
    "get_poi_repo",
    "get_queue_port",
    "get_staging_service",
]

# Global queue adapter instance
_mock_queue_adapter = MockQueueAdapter()
_sqs_queue_adapter: SQSQueueAdapter | None = None


def get_queue_port() -> IQueuePort:
    """Returns the stage-appropriate queue adapter.

    Returns:
        MockQueueAdapter when STAGE is 'testing', SQSQueueAdapter otherwise.
    """
    global _sqs_queue_adapter
    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local")).lower()
    if stage == "testing":
        return _mock_queue_adapter

    if _sqs_queue_adapter is None:
        _sqs_queue_adapter = SQSQueueAdapter()
    return _sqs_queue_adapter


def get_ingest_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IIngestJobRepository:
    """Provides an active IngestJobRepository instance."""
    return IngestJobRepository(session)


def get_poi_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IPOIRepository:
    """Provides an active POI repository instance."""
    return SqlAlchemyPOIRepository(session)


def get_candidate_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IIngestCandidateRepository:
    """Provides an active IngestCandidateRepository instance."""
    return SqlAlchemyIngestCandidateRepository(session)


def get_staging_service(
    candidate_repo: IIngestCandidateRepository = Depends(get_candidate_repo),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> StagingService:
    """Provides an active StagingService instance."""
    return StagingService(
        candidate_repo=candidate_repo,
        poi_repo=poi_repo,
    )
