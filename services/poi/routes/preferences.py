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

"""Scraping sources preferences routes (REQ-EXT-019, T-014).

Implements:
- GET /api/user/preferences/scraping-sources: Retrieve authorized secondary domains
- PUT /api/user/preferences/scraping-sources: Update authorized secondary domains
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import IScrapingPreferencesRepository
from vistarae_core.schemas.scraping import (
    ScrapingSourcesResponse,
    ScrapingSourcesUpdateRequest,
)

from services.poi.dependencies import get_current_user

router = APIRouter(tags=["preferences"])

DEFAULT_DOMAINS = [
    "wikipedia.org",
    "tripadvisor.com",
    "atlasobscura.com",
    "google.com/maps",
    "roadtrippers.com",
]


class SqlAlchemyScrapingPreferencesRepository(IScrapingPreferencesRepository):
    """PostgreSQL adapter for secondary scraping source preferences."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes with database session."""
        self._session = session

    async def get_scraping_domains(self, user_id: UUID) -> list[str]:
        """Retrieves authorized secondary scraping domains for the user."""
        stmt = select(UserPreferencesTable.valid_scraping_domains).where(
            UserPreferencesTable.user_id == user_id
        )
        res = await self._session.execute(stmt)
        domains = res.scalar_one_or_none()
        if not domains:
            return list(DEFAULT_DOMAINS)
        return list(domains)

    async def update_scraping_domains(
        self,
        user_id: UUID,
        domains: list[str],
    ) -> list[str]:
        """Updates authorized secondary scraping domains for the user."""
        stmt = (
            update(UserPreferencesTable)
            .where(UserPreferencesTable.user_id == user_id)
            .values(valid_scraping_domains=domains)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return domains


async def get_scraping_preferences_repo(
    session: AsyncSession = Depends(get_db_session),
) -> IScrapingPreferencesRepository:
    """Dependency provider for scraping preferences repository."""
    return SqlAlchemyScrapingPreferencesRepository(session)


@router.get(
    "/user/preferences/scraping-sources",
    response_model=ScrapingSourcesResponse,
)
@router.get(
    "/preferences/scraping-sources",
    response_model=ScrapingSourcesResponse,
    include_in_schema=False,
)
async def get_scraping_sources(
    current_user: User = Depends(get_current_user),
    repo: IScrapingPreferencesRepository = Depends(get_scraping_preferences_repo),
) -> ScrapingSourcesResponse:
    """Retrieves the list of authorized secondary scraping domains."""
    domains = await repo.get_scraping_domains(current_user.id)
    return ScrapingSourcesResponse(valid_scraping_domains=domains)


@router.put(
    "/user/preferences/scraping-sources",
    response_model=ScrapingSourcesResponse,
)
@router.put(
    "/preferences/scraping-sources",
    response_model=ScrapingSourcesResponse,
    include_in_schema=False,
)
async def update_scraping_sources(
    req: ScrapingSourcesUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: IScrapingPreferencesRepository = Depends(get_scraping_preferences_repo),
) -> ScrapingSourcesResponse:
    """Updates the list of authorized secondary scraping domains."""
    updated = await repo.update_scraping_domains(current_user.id, req.valid_scraping_domains)
    return ScrapingSourcesResponse(valid_scraping_domains=updated)
