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
