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

"""Authentication and identity lifecycle route handlers.

Implements REQ-AUTH-001 through REQ-AUTH-006:
- POST /register (Cognito sign-up)
- POST /confirm-signup (Confirmation code and PostgreSQL tenant initialization)
- POST /login (USER_PASSWORD_AUTH and JWT token issuance)
- POST /forgot-password (Password reset code dispatch)
- POST /reset-password (Password reset confirmation)
- POST /logout (GlobalSignOut session revocation)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.repositories.user_repo import SqlAlchemyUserRepository
from vistarae_core.domain.entities import User, UserMetric, UserPreferences, UserQuota
from vistarae_core.domain.value_objects import PacingMode, ThemeMode, TransitSpeedMode, UserTier
from vistarae_core.ports.identity import IIdentityProvider
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

from services.user.dependencies import get_identity_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["auth"])


def _build_default_user_entities(
    user_id: uuid.UUID,
    cognito_sub: str,
    email: str,
    full_name: str | None,
) -> tuple[User, UserPreferences, UserQuota, UserMetric]:
    """Constructs default tenant domain entities for initial account provisioning.

    Args:
        user_id: Pre-allocated UUID for tenant.
        cognito_sub: Unique Cognito subject claim.
        email: Verified email address.
        full_name: Optional full name.

    Returns:
        Tuple of (User, UserPreferences, UserQuota, UserMetric).
    """
    now = datetime.now(UTC)
    user = User(
        id=user_id,
        cognito_sub=cognito_sub,
        email=email,
        full_name=full_name,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    prefs = UserPreferences(
        user_id=user_id,
        theme=ThemeMode.SYSTEM,
        email_notifications_enabled=True,
        push_notifications_enabled=True,
        marketing_emails_enabled=False,
        clustering_enabled=True,
        clustering_radius_meters=50,
        default_map_layer="standard",
        geoproximity_scope_km=25.0,
        pin_color_presets={
            "favorite": "#E11D48",
            "dream": "#8B5CF6",
            "visited": "#10B981",
            "default": "#3B82F6",
        },
        pacing=PacingMode.MODERATE,
        meal_intervals_hours=4.0,
        lunch_packing_enabled=False,
        transit_speed_mode=TransitSpeedMode.WALKING,
        daily_activity_hour_cap=8.0,
        preferred_currency="USD",
        created_at=now,
        updated_at=now,
    )
    quota = UserQuota(
        user_id=user_id,
        monthly_token_quota=50000,
        current_token_usage=0,
        tier=UserTier.LOW,
        request_count=0,
        window_start_at=now,
        is_disabled=False,
        updated_at=now,
    )
    metric = UserMetric(
        user_id=user_id,
        poi_count=0,
        total_tokens_consumed=0,
        updated_at=now,
    )
    return user, prefs, quota, metric


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    id_provider: IIdentityProvider = Depends(get_identity_provider),
) -> RegisterResponse:
    """Registers a new user in the identity provider.

    Args:
        body: Registration parameters (email, password, full_name).
        id_provider: Injected identity provider.

    Returns:
        RegisterResponse with Cognito subject and confirmation status.

    Raises:
        HTTPException: 400 or 409 if validation or registration fails.
    """
    try:
        result = await id_provider.sign_up(
            email=str(body.email),
            password=body.password,
            full_name=body.full_name,
        )
        return RegisterResponse(
            user_sub=result["user_sub"],
            user_confirmed=result.get("user_confirmed", False),
            message="Verification code dispatched to your registered email.",
        )
    except ValueError as exc:
        msg = str(exc)
        status_code = (
            status.HTTP_409_CONFLICT if "already exists" in msg else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=msg) from exc
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {exc}",
        ) from exc


@router.post(
    "/confirm-signup",
    response_model=ConfirmSignUpResponse,
    status_code=status.HTTP_200_OK,
)
async def confirm_signup(
    body: ConfirmSignUpRequest,
    id_provider: IIdentityProvider = Depends(get_identity_provider),
    session: AsyncSession = Depends(get_db_session),
) -> ConfirmSignUpResponse:
    """Confirms signup and provisions local database tenant records.

    Args:
        body: Confirmation parameters (email, confirmation_code, full_name).
        id_provider: Injected identity provider.
        session: Active database session.

    Returns:
        ConfirmSignUpResponse with tenant user UUID.

    Raises:
        HTTPException: 400 if verification code is invalid.
    """
    try:
        await id_provider.confirm_sign_up(
            email=str(body.email),
            confirmation_code=body.confirmation_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confirmation failed: {exc}",
        ) from exc

    user_repo = SqlAlchemyUserRepository(session)
    existing_user = await user_repo.get_by_email(str(body.email))
    if existing_user is not None:
        return ConfirmSignUpResponse(
            confirmed=True,
            user_id=existing_user.id,
            message="Account verified and active.",
        )

    # Derive deterministic Cognito sub or allocate a new UUID
    user_id = uuid.uuid4()
    cognito_sub = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(body.email)))
    user, prefs, quota, metric = _build_default_user_entities(
        user_id=user_id,
        cognito_sub=cognito_sub,
        email=str(body.email),
        full_name=body.full_name,
    )
    await user_repo.create(user, prefs, quota, metric)
    await session.commit()

    return ConfirmSignUpResponse(
        confirmed=True,
        user_id=user_id,
        message="Account verified and tenant workspace initialized.",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    body: LoginRequest,
    id_provider: IIdentityProvider = Depends(get_identity_provider),
) -> LoginResponse:
    """Authenticates credentials against identity provider.

    Args:
        body: Login credentials.
        id_provider: Injected identity provider.

    Returns:
        LoginResponse with JWT bearer tokens.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    try:
        tokens = await id_provider.initiate_auth(
            email=str(body.email),
            password=body.password,
        )
        return LoginResponse(
            access_token=tokens["access_token"],
            id_token=tokens["id_token"],
            refresh_token=tokens.get("refresh_token"),
            token_type=tokens.get("token_type", "Bearer"),
            expires_in=tokens.get("expires_in", 3600),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {exc}",
        ) from exc


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(
    body: ForgotPasswordRequest,
    id_provider: IIdentityProvider = Depends(get_identity_provider),
) -> ForgotPasswordResponse:
    """Initiates password reset code dispatch.

    Args:
        body: Registered email.
        id_provider: Injected identity provider.

    Returns:
        ForgotPasswordResponse acknowledgement.

    Raises:
        HTTPException: 404 if email not found.
    """
    try:
        await id_provider.forgot_password(email=str(body.email))
        return ForgotPasswordResponse(
            message=f"Password reset code dispatched to {body.email}.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forgot password request failed: {exc}",
        ) from exc


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_password(
    body: ResetPasswordRequest,
    id_provider: IIdentityProvider = Depends(get_identity_provider),
) -> ResetPasswordResponse:
    """Confirms password reset with code and new password.

    Args:
        body: Password reset parameters.
        id_provider: Injected identity provider.

    Returns:
        ResetPasswordResponse acknowledgement.

    Raises:
        HTTPException: 400 if code is invalid or password rejected.
    """
    try:
        await id_provider.confirm_forgot_password(
            email=str(body.email),
            confirmation_code=body.confirmation_code,
            new_password=body.new_password,
        )
        return ResetPasswordResponse(message="Password reset successfully.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset failed: {exc}",
        ) from exc


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
async def logout(
    body: LogoutRequest = LogoutRequest(),
    authorization: str | None = Header(default=None, alias="Authorization"),
    id_provider: IIdentityProvider = Depends(get_identity_provider),
) -> LogoutResponse:
    """Revokes active user session via GlobalSignOut.

    Args:
        body: Optional body containing access_token.
        authorization: Optional Authorization header with Bearer token.
        id_provider: Injected identity provider.

    Returns:
        LogoutResponse confirming sign out.

    Raises:
        HTTPException: 400 if no access token was supplied.
    """
    token = body.access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token provided for logout.",
        )

    try:
        await id_provider.global_sign_out(access_token=token)
        return LogoutResponse(logged_out=True, message="Signed out successfully.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {exc}",
        ) from exc
