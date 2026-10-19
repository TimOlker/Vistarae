# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Admin tenant inspection and governance route handlers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserMetricsTable, UserQuotasTable, UserTable
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import UserTier
from vistarae_core.middleware.rate_limit import invalidate_cache
from vistarae_core.schemas.admin import AdminUserDetailResponse
from vistarae_core.schemas.user import (
    UpdateUserQuotaRequest,
    UserMetricsResponse,
    UserQuotaResponse,
    UserResponse,
)

from services.admin.dependencies import require_admin

router = APIRouter()


async def _get_user_or_404(session: AsyncSession, user_id: UUID) -> tuple:
    """Retrieves user, quota, and metrics rows or raises 404.

    Args:
        session: Active database session.
        user_id: UUID of the target tenant.

    Returns:
        Tuple of (UserTable, UserQuotasTable, UserMetricsTable).

    Raises:
        HTTPException: 404 if the user is not found.
    """
    user_row = await session.scalar(select(UserTable).where(UserTable.id == user_id))
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )
    quota_row = await session.scalar(
        select(UserQuotasTable).where(UserQuotasTable.user_id == user_id)
    )
    metrics_row = await session.scalar(
        select(UserMetricsTable).where(UserMetricsTable.user_id == user_id)
    )
    return user_row, quota_row, metrics_row


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUserDetailResponse:
    """Retrieves complete tenant details for an admin inspection.

    Args:
        user_id: UUID of the target tenant.
        _admin: Admin caller (RBAC enforced by dependency).
        session: Active database session.

    Returns:
        AdminUserDetailResponse with profile, quota, and metrics.
    """
    user_row, quota_row, metrics_row = await _get_user_or_404(session, user_id)
    return AdminUserDetailResponse(
        profile=UserResponse(
            id=user_row.id,
            email=user_row.email,
            full_name=user_row.full_name,
            is_active=user_row.is_active,
            created_at=user_row.created_at,
            updated_at=user_row.updated_at,
        ),
        quotas=UserQuotaResponse(
            monthly_token_quota=quota_row.monthly_token_quota if quota_row else 50000,
            current_token_usage=quota_row.current_token_usage if quota_row else 0,
            tier=UserTier(quota_row.tier) if quota_row else UserTier.LOW,
            is_disabled=quota_row.is_disabled if quota_row else False,
            updated_at=quota_row.updated_at if quota_row else user_row.updated_at,
        ),
        metrics=UserMetricsResponse(
            poi_count=metrics_row.poi_count if metrics_row else 0,
            total_tokens_consumed=metrics_row.total_tokens_consumed if metrics_row else 0,
            updated_at=metrics_row.updated_at if metrics_row else user_row.updated_at,
        ),
    )


@router.patch("/users/{user_id}/quota", response_model=UserQuotaResponse)
async def update_user_quota(
    user_id: UUID,
    body: UpdateUserQuotaRequest,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> UserQuotaResponse:
    """Updates monthly token quota or tier for a tenant.

    Also invalidates the in-memory tier cache for that tenant.

    Args:
        user_id: UUID of the target tenant.
        body: Partial quota update payload.
        _admin: Admin caller (RBAC enforced).
        session: Active database session.

    Returns:
        Updated UserQuotaResponse.
    """
    updates = body.model_dump(exclude_none=True)
    if "tier" in updates:
        updates["tier"] = str(updates["tier"])
    if updates:
        await session.execute(
            update(UserQuotasTable).where(UserQuotasTable.user_id == user_id).values(**updates)
        )
        invalidate_cache(user_id)

    quota_row = await session.scalar(
        select(UserQuotasTable).where(UserQuotasTable.user_id == user_id)
    )
    if quota_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found."
        )
    return UserQuotaResponse(
        monthly_token_quota=quota_row.monthly_token_quota,
        current_token_usage=quota_row.current_token_usage,
        tier=UserTier(quota_row.tier),
        is_disabled=quota_row.is_disabled,
        updated_at=quota_row.updated_at,
    )


@router.post("/users/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Sets is_disabled=TRUE for a tenant and invalidates their tier cache.

    Args:
        user_id: UUID of the target tenant.
        _admin: Admin caller (RBAC enforced).
        session: Active database session.
    """
    await session.execute(
        update(UserQuotasTable).where(UserQuotasTable.user_id == user_id).values(is_disabled=True)
    )
    invalidate_cache(user_id)


@router.post("/users/{user_id}/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_user(
    user_id: UUID,
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Sets is_disabled=FALSE for a tenant and invalidates their tier cache.

    Args:
        user_id: UUID of the target tenant.
        _admin: Admin caller (RBAC enforced).
        session: Active database session.
    """
    await session.execute(
        update(UserQuotasTable).where(UserQuotasTable.user_id == user_id).values(is_disabled=False)
    )
    invalidate_cache(user_id)
