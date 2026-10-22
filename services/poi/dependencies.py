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

"""FastAPI dependencies for POI domain and geospatial engine (T-024).

Provides dependency injection for:
- Authenticated user context (delegated to services.user.dependencies.get_current_user)
- Database session and repository adapters (POIRepository, ListRepository, TagRepository)
- Geocoding port adapter (Mapbox with fallback to Mock)
- Vector embedding port adapter (Gemini with fallback to Mock)
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.embedding.gemini import GeminiEmbeddingAdapter
from vistarae_core.adapters.embedding.mock import MockEmbeddingAdapter
from vistarae_core.adapters.geocoding.mapbox import MapboxGeocodingAdapter
from vistarae_core.adapters.geocoding.mock import MockGeocodingAdapter
from vistarae_core.adapters.repositories.filter_rule_repo import (
    SqlAlchemyFilterRuleRepository,
)
from vistarae_core.adapters.repositories.geocache_repo import SqlAlchemyGeocodingCacheRepository
from vistarae_core.adapters.repositories.itinerary_repo import SqlAlchemyItineraryRepository
from vistarae_core.adapters.repositories.list_repo import SqlAlchemyListRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.geocoding import IGeocodingPort
from vistarae_core.ports.itinerary_repo import IItineraryRepository
from vistarae_core.ports.repositories import (
    IFilterRuleRepository,
    IGeocodingCacheRepository,
    IListRepository,
    IPOIRepository,
    ITagRepository,
)

from services.user.dependencies import get_current_user

# Global mock adapters for local/testing stages
_mock_geocoder = MockGeocodingAdapter()
_mock_embedder = MockEmbeddingAdapter()


def get_poi_repo(session: AsyncSession = Depends(get_db_session)) -> IPOIRepository:
    """Dependency that provides an active POI repository instance."""
    return SqlAlchemyPOIRepository(session)


def get_list_repo(session: AsyncSession = Depends(get_db_session)) -> IListRepository:
    """Dependency that provides an active Curated List repository instance."""
    return SqlAlchemyListRepository(session)


def get_tag_repo(session: AsyncSession = Depends(get_db_session)) -> ITagRepository:
    """Dependency that provides an active Taxonomy Tag repository instance."""
    return SqlAlchemyTagRepository(session)


def get_filter_rule_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IFilterRuleRepository:
    """Dependency that provides an active Filter Rule repository instance."""
    return SqlAlchemyFilterRuleRepository(session)


def get_geocache_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IGeocodingCacheRepository:
    """Dependency that provides an active Geocoding cache repository instance."""
    return SqlAlchemyGeocodingCacheRepository(session)


def get_geocoding_port(
    cache_repo: IGeocodingCacheRepository = Depends(get_geocache_repo),
) -> IGeocodingPort:
    """Dependency that provides stage-aware geocoding port adapter."""
    mapbox_key = os.getenv("MAPBOX_API_KEY", "")
    force_mock = os.getenv("MOCK_GEOCODING", "0") == "1"

    if force_mock or not mapbox_key:
        return _mock_geocoder
    return MapboxGeocodingAdapter(cache_repo=cache_repo, api_key=mapbox_key)


def get_embedding_port() -> IEmbeddingPort:
    """Dependency that provides stage-aware embedding port adapter."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    force_mock = os.getenv("MOCK_EMBEDDING", "0") == "1"

    if force_mock or not gemini_key:
        return _mock_embedder
    return GeminiEmbeddingAdapter(api_key=gemini_key)


def get_itinerary_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IItineraryRepository:
    """Dependency that provides an active Itinerary repository instance."""
    return SqlAlchemyItineraryRepository(session)


def get_planner_service(
    itinerary_repo: IItineraryRepository = Depends(get_itinerary_repo),
    embedding_port: IEmbeddingPort = Depends(get_embedding_port),
) -> Any:
    """Dependency that provides an active PlannerService instance."""
    from services.poi.services.planner import PlannerService

    return PlannerService(itinerary_repo=itinerary_repo, embedding_port=embedding_port)


__all__ = [
    "get_current_user",
    "get_embedding_port",
    "get_filter_rule_repo",
    "get_geocache_repo",
    "get_geocoding_port",
    "get_itinerary_repo",
    "get_list_repo",
    "get_planner_service",
    "get_poi_repo",
    "get_tag_repo",
]
