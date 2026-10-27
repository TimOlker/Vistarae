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

"""User profile and GDPR deletion route handlers.

Implements GET /api/users/me, PATCH /api/users/me, and DELETE /api/users/me.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)
from vistarae_core.adapters.identity.cognito import CognitoIdentityProvider
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import PacingMode, ThemeMode, TransitSpeedMode, UserTier
from vistarae_core.services.prompt_cache import default_prompt_cache
from vistarae_core.schemas.preferences import (
    PlannerPreferencesResponse,
    POIPreferencesResponse,
    UIPreferencesResponse,
    UserPreferencesResponse,
)
from vistarae_core.schemas.user import (
    UpdateUserRequest,
    UserMetricsResponse,
    UserProfileResponse,
    UserQuotaResponse,
    UserResponse,
)

from services.user.dependencies import get_current_user

router = APIRouter()
_cognito = CognitoIdentityProvider(validate_config=False)


@router.get("/me", response_model=UserProfileResponse, status_code=status.HTTP_200_OK)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    """Returns the full profile for the authenticated tenant.

    Args:
        current_user: Authenticated user entity from dependency.
        session: Active database session.

    Returns:
        UserProfileResponse combining identity, preferences, metrics, and quotas.
    """
    prefs_row = await session.scalar(
        select(UserPreferencesTable).where(UserPreferencesTable.user_id == current_user.id)
    )
    metrics_row = await session.scalar(
        select(UserMetricsTable).where(UserMetricsTable.user_id == current_user.id)
    )
    quota_row = await session.scalar(
        select(UserQuotasTable).where(UserQuotasTable.user_id == current_user.id)
    )

    return UserProfileResponse(
        user=UserResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        ),
        preferences=UserPreferencesResponse(
            ui=UIPreferencesResponse(
                theme=ThemeMode(prefs_row.theme)
                if (prefs_row and prefs_row.theme)
                else ThemeMode.SYSTEM,
                email_notifications_enabled=prefs_row.email_notifications_enabled
                if (prefs_row and prefs_row.email_notifications_enabled is not None)
                else True,
                push_notifications_enabled=prefs_row.push_notifications_enabled
                if (prefs_row and prefs_row.push_notifications_enabled is not None)
                else True,
                marketing_emails_enabled=prefs_row.marketing_emails_enabled
                if (prefs_row and prefs_row.marketing_emails_enabled is not None)
                else False,
            ),
            poi=POIPreferencesResponse(
                clustering_enabled=prefs_row.clustering_enabled
                if (prefs_row and prefs_row.clustering_enabled is not None)
                else True,
                clustering_radius_meters=prefs_row.clustering_radius_meters
                if (prefs_row and prefs_row.clustering_radius_meters is not None)
                else 50,
                default_map_layer=prefs_row.default_map_layer
                if (prefs_row and prefs_row.default_map_layer)
                else "standard",
                geoproximity_scope_km=prefs_row.geoproximity_scope_km
                if (prefs_row and prefs_row.geoproximity_scope_km is not None)
                else 25.0,
                pin_color_presets=prefs_row.pin_color_presets
                if (prefs_row and prefs_row.pin_color_presets is not None)
                else {},
            ),
            planner=PlannerPreferencesResponse(
                pacing=PacingMode(prefs_row.pacing)
                if (prefs_row and prefs_row.pacing)
                else PacingMode.MODERATE,
                meal_intervals_hours=prefs_row.meal_intervals_hours
                if (prefs_row and prefs_row.meal_intervals_hours is not None)
                else 4.0,
                lunch_packing_enabled=prefs_row.lunch_packing_enabled
                if (prefs_row and prefs_row.lunch_packing_enabled is not None)
                else False,
                transit_speed_mode=TransitSpeedMode(prefs_row.transit_speed_mode)
                if (prefs_row and prefs_row.transit_speed_mode)
                else TransitSpeedMode.WALKING,
                daily_activity_hour_cap=prefs_row.daily_activity_hour_cap
                if (prefs_row and prefs_row.daily_activity_hour_cap is not None)
                else 8.0,
                preferred_currency=prefs_row.preferred_currency
                if (prefs_row and prefs_row.preferred_currency)
                else "USD",
            ),
            travel_style_description=prefs_row.travel_style_description
            if prefs_row
            else None,
        ),
        metrics=UserMetricsResponse(
            poi_count=metrics_row.poi_count
            if (metrics_row and metrics_row.poi_count is not None)
            else 0,
            total_tokens_consumed=metrics_row.total_tokens_consumed
            if (metrics_row and metrics_row.total_tokens_consumed is not None)
            else 0,
            updated_at=metrics_row.updated_at
            if (metrics_row and metrics_row.updated_at)
            else current_user.updated_at,
        ),
        quotas=UserQuotaResponse(
            monthly_token_quota=quota_row.monthly_token_quota
            if (quota_row and quota_row.monthly_token_quota is not None)
            else 50000,
            current_token_usage=quota_row.current_token_usage
            if (quota_row and quota_row.current_token_usage is not None)
            else 0,
            tier=UserTier(quota_row.tier) if (quota_row and quota_row.tier) else UserTier.LOW,
            is_disabled=quota_row.is_disabled
            if (quota_row and quota_row.is_disabled is not None)
            else False,
            updated_at=quota_row.updated_at
            if (quota_row and quota_row.updated_at)
            else current_user.updated_at,
        ),
    )


@router.patch("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def patch_me(
    body: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Updates the full_name of the authenticated tenant.

    Args:
        body: UpdateUserRequest containing the new full_name.
        current_user: Authenticated user entity from dependency.
        session: Active database session.

    Returns:
        Updated UserResponse.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    now = datetime.now(UTC)
    await session.execute(
        update(UserTable)
        .where(UserTable.id == current_user.id)
        .values(full_name=body.full_name, updated_at=now)
    )

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=body.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=now,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """GDPR-compliant cascade deletion of the authenticated tenant.

    Invokes Cognito AdminDeleteUser first, then deletes the DB row (which
    cascades to all sub-tables via ON DELETE CASCADE foreign keys).

    Args:
        current_user: Authenticated user entity from dependency.
        session: Active database session.
    """
    # 1. Remove from identity provider.
    await _cognito.delete_user(current_user.cognito_sub)
    # 2. Invalidate prompt cache
    default_prompt_cache.invalidate_user(current_user.id)
    # 3. Delete from PostgreSQL — triggers CASCADE on all child tables.
    await session.execute(delete(UserTable).where(UserTable.id == current_user.id))
