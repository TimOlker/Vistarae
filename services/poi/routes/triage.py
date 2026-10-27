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
from vistarae_core.adapters.repositories.user_prompt_repo import SqlAlchemyUserPromptRepository
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import IGeocodingCacheRepository, ITagRepository
from vistarae_core.services.prompt_cache import default_prompt_cache
from vistarae_core.schemas.scraping import (
    ExtractAndCheckRequest,
    ExtractAndCheckResponse,
    ReverseGeocodeRequest,
    ReverseGeocodeResponse,
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

    # 2.5 Resolve active user prompt directives for personalized synthesis (REQ-CTX-027)
    prompt_repo = SqlAlchemyUserPromptRepository(session)
    prompt_directives = await default_prompt_cache.get_or_load(current_user.id, prompt_repo)

    # 3. Extract POI candidate attributes
    candidate = await orchestrator.extract(
        source_url=req.source_url,
        page_title=req.page_title,
        selected_text=req.selected_text,
        client_latitude=req.latitude,
        client_longitude=req.longitude,
        client_raw_address=req.raw_address,
        client_category=req.category,
        prompt_directives=prompt_directives,
        user_id=current_user.id,
    )

    # 4. Match vetted taxonomy tags with system fallback (REQ: FR-016, T-011)
    from uuid import uuid4

    from vistarae_core.domain.entities import TagEntity

    from services.poi.services.tag_seeder import DEFAULT_TAGS, seed_default_tags

    user_tags = await tag_repo.list_by_user(current_user.id)
    if not user_tags:
        try:
            await seed_default_tags(current_user.id, session)
            user_tags = await tag_repo.list_by_user(current_user.id)
        except Exception as exc:
            logger.warning("Auto-seeding default tags failed: %s", exc)

    if user_tags:
        combined_tags = list(user_tags)
    else:
        combined_tags = [
            TagEntity(
                id=uuid4(),
                user_id=current_user.id,
                name=t["name"],
                slug=t["slug"],
                aliases=t.get("aliases", []),
            )
            for t in DEFAULT_TAGS
        ]

    text_to_match = (
        f"{candidate.name} {candidate.description} {req.page_title or ''} "
        f"{req.selected_text or ''} {req.category or ''}"
    )
    recommended_tags = TagMatcher(combined_tags).match_tags(text_to_match)

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

    from vistarae_core.schemas.scraping import UserTagItemSchema

    available_tags = [
        UserTagItemSchema(id=t.id, name=t.name, slug=t.slug, aliases=t.aliases or [])
        for t in combined_tags
    ]

    return ExtractAndCheckResponse(
        candidate=candidate,
        recommended_tags=recommended_tags,
        available_tags=available_tags,
        deduplication=verdict,
    )


@router.post(
    "/v1/geocoding/reverse",
    response_model=ReverseGeocodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse-geocode coordinates to structured address line and sovereign country",
)
@router.post(
    "/pois/geocode/reverse",
    response_model=ReverseGeocodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse-geocode coordinates to structured address line and sovereign country (legacy path)",
)
async def reverse_geocode_v1(
    req: ReverseGeocodeRequest,
    current_user: User = Depends(get_current_user),
    geocache_repo: IGeocodingCacheRepository = Depends(get_geocache_repo),
) -> ReverseGeocodeResponse:
    """Reverse geocodes coordinates via internal PostGIS cache and rate-limited OSM Nominatim."""
    service = GeocodingService(cache_repo=geocache_repo)
    return await service.reverse_geocode_structured(lat=req.latitude, lng=req.longitude)
