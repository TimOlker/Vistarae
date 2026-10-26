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

"""FastAPI router for web scraping extraction and early duplicate triage (T-035).

Implements:
- POST /pois/extract-and-check (and /api/pois/extract-and-check): Full-spectrum extraction,
  authorized secondary source augmentation, tag matching, and scale-aware duplicate/nesting triage.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import IGeocodingCacheRepository, ITagRepository
from vistarae_core.schemas.scraping import (
    ExtractAndCheckRequest,
    ExtractAndCheckResponse,
)

from services.poi.dependencies import (
    get_current_user,
    get_geocache_repo,
    get_tag_repo,
)
from services.poi.routes.preferences import DEFAULT_DOMAINS
from services.poi.scraping.orchestrator import ScrapingOrchestrator
from services.poi.scraping.tag_matcher import TagMatcher
from services.poi.services.duplicate_service import DuplicateTriageService
from services.poi.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["triage"])


@router.post(
    "/pois/extract-and-check",
    response_model=ExtractAndCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract destination details from webpage and evaluate duplicate/nesting triage",
)
async def extract_and_check(
    req: ExtractAndCheckRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    tag_repo: ITagRepository = Depends(get_tag_repo),
    geocache_repo: IGeocodingCacheRepository = Depends(get_geocache_repo),
) -> ExtractAndCheckResponse:
    """Performs multi-source scraping, geocoding, tag recommendation, and duplicate triage.

    Enforces:
    - REQ-EXT-017 (Standard English location name normalization)
    - REQ-EXT-018 (Query only authorized user_preferences.valid_scraping_domains)
    - REQ-EXT-020 (3.0s timeout ceiling with graceful partial fallback)
    - REQ-EXT-022 to REQ-EXT-027 (PostGIS SHA-256 caching & 1 req/sec rate limit)
    - REQ-EXT-028 (Gemini Flash-Lite summary synthesis)
    - REQ-EXT-029 (Tag matching against user's vetted taxonomy)
    - REQ-EXT-030 to REQ-EXT-032 (Scale-aware early duplicate and parent-child triage)
    """
    logger.info(
        "MSG   |-> POST /pois/extract-and-check: user=%s url='%s'",
        current_user.id,
        req.source_url,
    )

    # 1. Fetch user authorized secondary scraping domains
    stmt = select(UserPreferencesTable.valid_scraping_domains).where(
        UserPreferencesTable.user_id == current_user.id
    )
    result = await session.execute(stmt)
    domains_row = result.scalar_one_or_none()
    valid_domains = domains_row if domains_row else DEFAULT_DOMAINS

    # 2. Build geocoding service and scraping orchestrator
    geocoding_service = GeocodingService(cache_repo=geocache_repo)
    orchestrator = ScrapingOrchestrator(
        valid_domains=valid_domains,
        geocoding_service=geocoding_service,
    )

    # 3. Extract POI candidate attributes
    candidate = await orchestrator.extract(
        source_url=req.source_url,
        page_title=req.page_title,
        selected_text=req.selected_text,
    )

    # 4. Match vetted taxonomy tags
    user_tags = await tag_repo.list_by_user(current_user.id)
    text_to_match = (
        f"{candidate.name} {candidate.description} {req.page_title or ''} {req.selected_text or ''}"
    )
    recommended_tags = TagMatcher(user_tags).match_tags(text_to_match)

    # 5. Evaluate early scale-aware duplicate & parent-child nesting triage
    triage_service = DuplicateTriageService(session=session)
    verdict = await triage_service.evaluate_candidate(
        user_id=current_user.id,
        name=candidate.name,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        description=candidate.description,
        tags=recommended_tags,
    )

    logger.info(
        "MSG   |<- Extraction and triage complete for '%s': verdict=%s recommended_action=%s",
        candidate.name,
        verdict.status,
        verdict.recommended_action,
    )

    return ExtractAndCheckResponse(
        candidate=candidate,
        recommended_tags=recommended_tags,
        deduplication=verdict,
    )
