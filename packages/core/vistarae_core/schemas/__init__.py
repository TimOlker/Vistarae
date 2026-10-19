# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pydantic v2 boundary schemas for requests, responses, and errors."""

from vistarae_core.schemas.admin import (
    AdminMessageRequest,
    AdminMetricsResponse,
    AdminUserDetailResponse,
    QuotaDefaultsRequest,
    QuotaDefaultsResponse,
)
from vistarae_core.schemas.auth import (
    ConfirmSignUpRequest,
    ConfirmSignUpResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.errors import InvalidParam, ProblemDetails
from vistarae_core.schemas.preferences import (
    PlannerPreferencesResponse,
    POIPreferencesResponse,
    UIPreferencesResponse,
    UpdatePlannerPreferencesRequest,
    UpdatePOIPreferencesRequest,
    UpdateUIPreferencesRequest,
    UserPreferencesResponse,
)
from vistarae_core.schemas.user import (
    UpdateUserQuotaRequest,
    UpdateUserRequest,
    UserMetricsResponse,
    UserProfileResponse,
    UserQuotaResponse,
    UserResponse,
)

__all__ = [
    "AdminMessageRequest",
    "AdminMetricsResponse",
    "AdminUserDetailResponse",
    "ConfirmSignUpRequest",
    "ConfirmSignUpResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "InvalidParam",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "LogoutResponse",
    "PlannerPreferencesResponse",
    "POIPreferencesResponse",
    "ProblemDetails",
    "QuotaDefaultsRequest",
    "QuotaDefaultsResponse",
    "RegisterRequest",
    "RegisterResponse",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "StrictBaseModel",
    "UIPreferencesResponse",
    "UpdatePlannerPreferencesRequest",
    "UpdatePOIPreferencesRequest",
    "UpdateUIPreferencesRequest",
    "UpdateUserQuotaRequest",
    "UpdateUserRequest",
    "UserMetricsResponse",
    "UserPreferencesResponse",
    "UserProfileResponse",
    "UserQuotaResponse",
    "UserResponse",
]
