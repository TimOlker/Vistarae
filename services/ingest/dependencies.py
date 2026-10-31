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
from vistarae_core.adapters.repositories.geocache_repo import (
    SqlAlchemyGeocodingCacheRepository,
)
from vistarae_core.adapters.repositories.list_repo import (
    SqlAlchemyListRepository,
)
from vistarae_core.adapters.repositories.tag_repo import (
    SqlAlchemyTagRepository,
)
from vistarae_core.ports.repositories import (
    IGeocodingCacheRepository,
    IIngestCandidateRepository,
    IIngestJobRepository,
    IListRepository,
    IPOIRepository,
    ITagRepository,
    IUserExclusionZoneRepository,
)
from vistarae_core.adapters.repositories.exclusion_zone_repo import (
    SqlAlchemyUserExclusionZoneRepository,
)
from services.poi.scraping.orchestrator import ScrapingOrchestrator
from services.poi.services.duplicate_service import DuplicateTriageService
from services.poi.services.geocoding_service import GeocodingService

from services.ingest.services.staging_service import StagingService
from services.user.dependencies import get_current_user

__all__ = [
    "get_candidate_repo",
    "get_current_user",
    "get_ingest_repo",
    "get_poi_repo",
    "get_queue_port",
    "get_staging_service",
    "get_geocache_repo",
    "get_geocoding_service",
    "get_duplicate_service",
    "get_list_repo",
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


def get_geocache_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IGeocodingCacheRepository:
    """Provides an active Geocoding cache repository instance."""
    return SqlAlchemyGeocodingCacheRepository(session)


def get_geocoding_service(
    cache_repo: IGeocodingCacheRepository = Depends(get_geocache_repo),
) -> GeocodingService:
    """Provides an active GeocodingService instance."""
    return GeocodingService(cache_repo=cache_repo)


def get_duplicate_service(
    session: AsyncSession = Depends(get_db_session),
) -> DuplicateTriageService:
    """Provides an active DuplicateTriageService instance."""
    return DuplicateTriageService(session=session)


def get_list_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IListRepository:
    """Provides an active List repository instance."""
    return SqlAlchemyListRepository(session)


def get_exclusion_zone_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IUserExclusionZoneRepository:
    """Provides an active User Exclusion Zone repository instance."""
    return SqlAlchemyUserExclusionZoneRepository(session)


def get_tag_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ITagRepository:
    """Provides an active Tag repository instance."""
    return SqlAlchemyTagRepository(session)


def get_staging_service(
    candidate_repo: IIngestCandidateRepository = Depends(get_candidate_repo),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    geocoding_service: GeocodingService = Depends(get_geocoding_service),
    duplicate_service: DuplicateTriageService = Depends(get_duplicate_service),
    ingest_repo: IIngestJobRepository = Depends(get_ingest_repo),
    exclusion_zone_repo: IUserExclusionZoneRepository = Depends(get_exclusion_zone_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> StagingService:
    """Provides an active StagingService instance with geocoding, deduplication, and exclusion zones."""
    orchestrator = ScrapingOrchestrator(geocoding_service=geocoding_service)
    return StagingService(
        candidate_repo=candidate_repo,
        poi_repo=poi_repo,
        geocoding_service=geocoding_service,
        duplicate_service=duplicate_service,
        orchestrator=orchestrator,
        ingest_repo=ingest_repo,
        exclusion_zone_repo=exclusion_zone_repo,
        tag_repo=tag_repo,
    )
