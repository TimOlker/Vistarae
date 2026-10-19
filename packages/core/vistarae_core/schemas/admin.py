# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Administrative and platform telemetry schemas."""

from __future__ import annotations

from pydantic import Field

from vistarae_core.domain.value_objects import UserTier
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.user import (
    UserMetricsResponse,
    UserQuotaResponse,
    UserResponse,
)


class AdminMetricsResponse(StrictBaseModel):
    """System-wide telemetry and resource consumption aggregation."""

    total_users: int
    active_users: int
    disabled_users: int
    total_pois: int
    total_tokens_consumed: int
    tier_distribution: dict[str, int]


class AdminUserDetailResponse(StrictBaseModel):
    """Detailed operational overview of a target tenant."""

    profile: UserResponse
    quotas: UserQuotaResponse
    metrics: UserMetricsResponse


class QuotaDefaultsRequest(StrictBaseModel):
    """Payload to configure system-wide default tenant quotas."""

    default_token_quota: int = Field(..., ge=1000)
    default_tier: UserTier


class QuotaDefaultsResponse(StrictBaseModel):
    """Current system-wide default tenant quotas."""

    default_token_quota: int
    default_tier: str


class AdminMessageRequest(StrictBaseModel):
    """Payload to dispatch an administrative notification to a user."""

    title: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=2000)
