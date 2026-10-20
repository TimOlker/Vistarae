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

"""Authentication and identity lifecycle request and response schemas.

Enforces Constitution Principle 5 and REQ-AUTH-001 through REQ-AUTH-006.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import EmailStr, Field

from vistarae_core.schemas.base import StrictBaseModel


class RegisterRequest(StrictBaseModel):
    """Payload for user registration."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password (min 8 chars)")
    full_name: str | None = Field(default=None, max_length=200, description="Optional full name")


class RegisterResponse(StrictBaseModel):
    """Response returned upon successful registration."""

    user_sub: str = Field(..., description="Unique Cognito subject identifier")
    user_confirmed: bool = Field(..., description="Whether user account is pre-confirmed")
    message: str = Field(..., description="Instruction message")


class ConfirmSignUpRequest(StrictBaseModel):
    """Payload for confirming user signup via verification code."""

    email: EmailStr = Field(..., description="User's email address")
    confirmation_code: str = Field(
        ..., min_length=1, max_length=32, description="Verification code"
    )
    full_name: str | None = Field(
        default=None, max_length=200, description="Optional full name override"
    )


class ConfirmSignUpResponse(StrictBaseModel):
    """Response returned upon successful account confirmation and provisioning."""

    confirmed: bool = Field(..., description="Confirmation outcome")
    user_id: UUID = Field(..., description="Internal tenant user UUID")
    message: str = Field(..., description="Status message")


class LoginRequest(StrictBaseModel):
    """Payload for authenticating with credentials."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's account password")


class LoginResponse(StrictBaseModel):
    """Tokens returned upon successful login."""

    access_token: str = Field(..., description="JWT Bearer access token")
    id_token: str = Field(..., description="OpenID Connect ID token")
    refresh_token: str | None = Field(default=None, description="Cognito refresh token")
    token_type: str = Field(default="Bearer", description="Token scheme")
    expires_in: int = Field(default=3600, description="Token validity duration in seconds")


class ForgotPasswordRequest(StrictBaseModel):
    """Payload to initiate a password reset code dispatch."""

    email: EmailStr = Field(..., description="User's registered email address")


class ForgotPasswordResponse(StrictBaseModel):
    """Acknowledgement of password reset dispatch."""

    message: str = Field(..., description="Status message confirming code dispatch")


class ResetPasswordRequest(StrictBaseModel):
    """Payload to complete password reset with received code."""

    email: EmailStr = Field(..., description="User's email address")
    confirmation_code: str = Field(..., min_length=1, max_length=32, description="Reset code")
    new_password: str = Field(..., min_length=8, description="New password")


class ResetPasswordResponse(StrictBaseModel):
    """Acknowledgement of successful password reset."""

    message: str = Field(..., description="Status message confirming password reset")


class LogoutRequest(StrictBaseModel):
    """Payload to invalidate sessions via GlobalSignOut."""

    access_token: str | None = Field(
        default=None,
        description="Optional access token to revoke (falls back to Authorization header)",
    )


class LogoutResponse(StrictBaseModel):
    """Acknowledgement of successful logout."""

    logged_out: bool = Field(..., description="Logout outcome")
    message: str = Field(..., description="Status message confirming sign out")
