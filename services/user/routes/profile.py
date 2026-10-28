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

"""Travel Style and Prompt Directives Profile Route Handlers (T-016).

Implements:
- GET /profile/travel-style: Fetch saved travel style and active prompt directives
- PUT /profile/travel-style: Update travel style and regenerate prompt directives
- DELETE /profile/travel-style: Clear travel style and delete prompt directives
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.adapters.repositories.user_prompt_repo import SqlAlchemyUserPromptRepository
from vistarae_core.domain.entities import User
from vistarae_core.schemas.user import (
    TravelStyleResponse,
    TravelStyleUpdateRequest,
    UserPromptItem,
)
from vistarae_core.services.prompt_cache import UserPromptCache, default_prompt_cache

from services.user.dependencies import get_current_user
from services.user.services.prompt_synthesizer import UserPromptSynthesizer

logger = logging.getLogger(__name__)

router = APIRouter()


def get_prompt_synthesizer() -> UserPromptSynthesizer:
    """Dependency providing the UserPromptSynthesizer service."""
    return UserPromptSynthesizer()


def get_prompt_cache() -> UserPromptCache:
    """Dependency providing the in-memory UserPromptCache."""
    return default_prompt_cache


@router.get(
    "/profile/travel-style",
    response_model=TravelStyleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get traveler travel style and active prompt directives",
)
async def get_travel_style(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TravelStyleResponse:
    """Returns the traveler's saved travel style narrative and active prompt directives."""
    logger.info("MSG ->| GET /profile/travel-style for user=%s", current_user.id)

    pref_row = await session.scalar(
        select(UserPreferencesTable).where(UserPreferencesTable.user_id == current_user.id)
    )
    travel_style_desc = pref_row.travel_style_description if pref_row else None

    prompt_repo = SqlAlchemyUserPromptRepository(session)
    prompts = await prompt_repo.list_by_user(current_user.id)

    prompt_items = [
        UserPromptItem(
            prompt_type=p.prompt_type,
            prompt_text=p.prompt_text,
            updated_at=p.updated_at,
        )
        for p in prompts
    ]

    logger.info(
        "MSG <-| GET /profile/travel-style 200 OK user=%s prompt_count=%d",
        current_user.id,
        len(prompt_items),
    )
    return TravelStyleResponse(
        travel_style_description=travel_style_desc,
        prompts=prompt_items,
    )


@router.put(
    "/profile/travel-style",
    response_model=TravelStyleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update travel style and regenerate prompt directives",
)
async def update_travel_style(
    payload: TravelStyleUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    synthesizer: UserPromptSynthesizer = Depends(get_prompt_synthesizer),
    cache: UserPromptCache = Depends(get_prompt_cache),
) -> TravelStyleResponse:
    """Saves freeform travel style narrative and invokes AI synthesis for directives."""
    logger.info("MSG ->| PUT /profile/travel-style for user=%s", current_user.id)

    now = datetime.now(UTC)
    narrative = payload.travel_style_description
    if narrative is not None:
        narrative = narrative.strip()
        if not narrative:
            narrative = None

    # Update or insert UserPreferencesTable
    pref_row = await session.scalar(
        select(UserPreferencesTable).where(UserPreferencesTable.user_id == current_user.id)
    )
    if pref_row is not None:
        pref_row.travel_style_description = narrative
        pref_row.updated_at = now
    else:
        new_prefs = UserPreferencesTable(
            user_id=current_user.id,
            travel_style_description=narrative,
            created_at=now,
            updated_at=now,
        )
        session.add(new_prefs)

    prompt_repo = SqlAlchemyUserPromptRepository(session)

    if narrative and len(narrative) >= 10:
        directives = await synthesizer.decompose(narrative)
        if directives:
            await prompt_repo.delete_by_user(current_user.id)
            await prompt_repo.upsert_prompts(current_user.id, directives)
        else:
            await prompt_repo.delete_by_user(current_user.id)
    else:
        await prompt_repo.delete_by_user(current_user.id)

    # Invalidate in-memory cache for this tenant
    cache.invalidate_user(current_user.id)
    await session.commit()

    # Re-fetch active prompts
    prompts = await prompt_repo.list_by_user(current_user.id)
    prompt_items = [
        UserPromptItem(
            prompt_type=p.prompt_type,
            prompt_text=p.prompt_text,
            updated_at=p.updated_at,
        )
        for p in prompts
    ]

    logger.info(
        "MSG <-| PUT /profile/travel-style 200 OK user=%s prompt_count=%d",
        current_user.id,
        len(prompt_items),
    )
    return TravelStyleResponse(
        travel_style_description=narrative,
        prompts=prompt_items,
    )


@router.delete(
    "/profile/travel-style",
    response_model=TravelStyleResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear traveler travel style and delete custom prompt directives",
)
async def clear_travel_style(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    cache: UserPromptCache = Depends(get_prompt_cache),
) -> TravelStyleResponse:
    """Deletes custom prompt directives and clears the travel style narrative."""
    logger.info("MSG ->| DELETE /profile/travel-style for user=%s", current_user.id)

    now = datetime.now(UTC)
    await session.execute(
        update(UserPreferencesTable)
        .where(UserPreferencesTable.user_id == current_user.id)
        .values(travel_style_description=None, updated_at=now)
    )

    prompt_repo = SqlAlchemyUserPromptRepository(session)
    await prompt_repo.delete_by_user(current_user.id)

    cache.invalidate_user(current_user.id)
    await session.commit()

    logger.info("MSG <-| DELETE /profile/travel-style 200 OK user=%s", current_user.id)
    return TravelStyleResponse(
        travel_style_description=None,
        prompts=[],
    )
