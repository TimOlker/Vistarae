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

"""User preferences route handlers.

Implements GET /api/users/me/preferences and PATCH sub-domain routes for
UI, POI, and Planner mode preferences.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import PacingMode, ThemeMode, TransitSpeedMode
from vistarae_core.schemas.preferences import (
    PlannerPreferencesResponse,
    POIPreferencesResponse,
    UIPreferencesResponse,
    UpdatePlannerPreferencesRequest,
    UpdatePOIPreferencesRequest,
    UpdateUIPreferencesRequest,
    UserPreferencesResponse,
)

from services.user.dependencies import get_current_user

router = APIRouter()


async def _get_prefs(session: AsyncSession, user_id: object) -> UserPreferencesTable | None:
    """Retrieves the preferences row for a tenant.

    Args:
        session: Active database session.
        user_id: UUID of the target tenant.

    Returns:
        UserPreferencesTable ORM row or None.
    """
    return await session.scalar(
        select(UserPreferencesTable).where(UserPreferencesTable.user_id == user_id)
    )


def _build_response(prefs: UserPreferencesTable | None) -> UserPreferencesResponse:
    """Constructs a UserPreferencesResponse from an ORM row.

    Args:
        prefs: UserPreferencesTable row, may be None for defaults.

    Returns:
        Populated UserPreferencesResponse with all sub-domain preferences.
    """
    return UserPreferencesResponse(
        ui=UIPreferencesResponse(
            theme=ThemeMode(prefs.theme) if prefs else ThemeMode.SYSTEM,
            email_notifications_enabled=prefs.email_notifications_enabled if prefs else True,
            push_notifications_enabled=prefs.push_notifications_enabled if prefs else True,
            marketing_emails_enabled=prefs.marketing_emails_enabled if prefs else False,
        ),
        poi=POIPreferencesResponse(
            clustering_enabled=prefs.clustering_enabled if prefs else True,
            clustering_radius_meters=prefs.clustering_radius_meters if prefs else 50,
            default_map_layer=prefs.default_map_layer if prefs else "standard",
            geoproximity_scope_km=prefs.geoproximity_scope_km if prefs else 25.0,
            pin_color_presets=prefs.pin_color_presets if prefs else {},
        ),
        planner=PlannerPreferencesResponse(
            pacing=PacingMode(prefs.pacing) if prefs else PacingMode.MODERATE,
            meal_intervals_hours=prefs.meal_intervals_hours if prefs else 4.0,
            lunch_packing_enabled=prefs.lunch_packing_enabled if prefs else False,
            transit_speed_mode=TransitSpeedMode(prefs.transit_speed_mode)
            if prefs
            else TransitSpeedMode.WALKING,
            daily_activity_hour_cap=prefs.daily_activity_hour_cap if prefs else 8.0,
            preferred_currency=prefs.preferred_currency if prefs else "USD",
        ),
    )


@router.get(
    "/me/preferences",
    response_model=UserPreferencesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesResponse:
    """Returns all sub-domain preferences for the authenticated tenant.

    Args:
        current_user: Authenticated user entity.
        session: Active database session.

    Returns:
        UserPreferencesResponse with UI, POI, and Planner sub-domains.
    """
    prefs = await _get_prefs(session, current_user.id)
    return _build_response(prefs)


@router.patch(
    "/me/preferences/ui",
    response_model=UIPreferencesResponse,
    status_code=status.HTTP_200_OK,
)
async def patch_ui_preferences(
    body: UpdateUIPreferencesRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UIPreferencesResponse:
    """Updates Account/UI sub-domain preferences.

    Args:
        body: Partial update payload — None fields are not mutated.
        current_user: Authenticated user entity.
        session: Active database session.

    Returns:
        Updated UIPreferencesResponse.
    """
    updates = body.model_dump(exclude_none=True)
    if updates:
        if "theme" in updates:
            updates["theme"] = str(updates["theme"])
        await session.execute(
            update(UserPreferencesTable)
            .where(UserPreferencesTable.user_id == current_user.id)
            .values(**updates)
        )

    prefs = await _get_prefs(session, current_user.id)
    return _build_response(prefs).ui


@router.patch(
    "/me/preferences/poi",
    response_model=POIPreferencesResponse,
    status_code=status.HTTP_200_OK,
)
async def patch_poi_preferences(
    body: UpdatePOIPreferencesRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> POIPreferencesResponse:
    """Updates POI Mode sub-domain preferences.

    Args:
        body: Partial update payload — None fields are not mutated.
        current_user: Authenticated user entity.
        session: Active database session.

    Returns:
        Updated POIPreferencesResponse.
    """
    updates = body.model_dump(exclude_none=True)
    if updates:
        await session.execute(
            update(UserPreferencesTable)
            .where(UserPreferencesTable.user_id == current_user.id)
            .values(**updates)
        )

    prefs = await _get_prefs(session, current_user.id)
    return _build_response(prefs).poi


@router.patch(
    "/me/preferences/planner",
    response_model=PlannerPreferencesResponse,
    status_code=status.HTTP_200_OK,
)
async def patch_planner_preferences(
    body: UpdatePlannerPreferencesRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PlannerPreferencesResponse:
    """Updates Planner Mode sub-domain preferences.

    Args:
        body: Partial update payload — None fields are not mutated.
        current_user: Authenticated user entity.
        session: Active database session.

    Returns:
        Updated PlannerPreferencesResponse.
    """
    updates = body.model_dump(exclude_none=True)
    if updates:
        if "pacing" in updates:
            updates["pacing"] = str(updates["pacing"])
        if "transit_speed_mode" in updates:
            updates["transit_speed_mode"] = str(updates["transit_speed_mode"])
        await session.execute(
            update(UserPreferencesTable)
            .where(UserPreferencesTable.user_id == current_user.id)
            .values(**updates)
        )

    prefs = await _get_prefs(session, current_user.id)
    return _build_response(prefs).planner
