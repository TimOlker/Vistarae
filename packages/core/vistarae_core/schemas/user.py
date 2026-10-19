# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""User profile, metrics, and quota boundary schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from vistarae_core.domain.value_objects import UserTier
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.preferences import UserPreferencesResponse


class UserResponse(StrictBaseModel):
    """Basic representation of a registered user."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateUserRequest(StrictBaseModel):
    """Payload to update basic user profile details."""

    full_name: str = Field(..., min_length=1, max_length=100)


class UserMetricsResponse(StrictBaseModel):
    """Aggregate consumption and activity counters."""

    poi_count: int
    total_tokens_consumed: int
    updated_at: datetime


class UserQuotaResponse(StrictBaseModel):
    """Governance allocation and rate limiting status."""

    monthly_token_quota: int
    current_token_usage: int
    tier: UserTier
    is_disabled: bool
    updated_at: datetime


class UpdateUserQuotaRequest(StrictBaseModel):
    """Administrative payload to adjust tenant quota or tier."""

    monthly_token_quota: int | None = Field(None, ge=0)
    tier: UserTier | None = None


class UserProfileResponse(StrictBaseModel):
    """Combined profile representation containing identity, preferences, quotas, and metrics."""

    user: UserResponse
    preferences: UserPreferencesResponse
    metrics: UserMetricsResponse
    quotas: UserQuotaResponse
