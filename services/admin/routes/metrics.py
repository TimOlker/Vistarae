# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Admin platform metrics route — GET /api/admin/metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import UserMetricsTable, UserQuotasTable, UserTable
from vistarae_core.domain.entities import User
from vistarae_core.schemas.admin import AdminMetricsResponse

from services.admin.dependencies import require_admin

router = APIRouter()


@router.get("/metrics", response_model=AdminMetricsResponse)
async def get_metrics(
    _admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminMetricsResponse:
    """Aggregates platform-wide telemetry and usage metrics.

    Args:
        _admin: Admin caller (validated by RBAC dependency, unused directly).
        session: Active database session.

    Returns:
        AdminMetricsResponse with total_users, active_users, disabled_users,
        total_pois, total_tokens_consumed, and tier_distribution.
    """
    total_users = await session.scalar(select(func.count()).select_from(UserTable))
    active_users = await session.scalar(
        select(func.count()).where(UserTable.is_active.is_(True))
    )
    disabled_users = await session.scalar(
        select(func.count()).where(UserQuotasTable.is_disabled.is_(True)).select_from(UserQuotasTable)
    )
    total_pois = await session.scalar(select(func.sum(UserMetricsTable.poi_count)))
    total_tokens = await session.scalar(
        select(func.sum(UserMetricsTable.total_tokens_consumed))
    )

    tier_rows = await session.execute(
        select(UserQuotasTable.tier, func.count().label("count"))
        .group_by(UserQuotasTable.tier)
    )
    tier_distribution = {row.tier: row.count for row in tier_rows}

    return AdminMetricsResponse(
        total_users=int(total_users or 0),
        active_users=int(active_users or 0),
        disabled_users=int(disabled_users or 0),
        total_pois=int(total_pois or 0),
        total_tokens_consumed=int(total_tokens or 0),
        tier_distribution=tier_distribution,
    )
