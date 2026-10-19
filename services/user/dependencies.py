# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stage-aware authentication dependency for UserFunction.

Resolves authenticated user context from either:
1. X-Mock-User-Id header (STAGE == 'local' only)
2. Bearer JWT validated against AWS Cognito JWKS (all other stages)

Returns a populated User entity or raises RFC 7807 error responses.
"""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.identity.cognito import CognitoIdentityProvider
from vistarae_core.adapters.identity.mock import MockIdentityProvider
from vistarae_core.domain.entities import User
from vistarae_core.ports.identity import IIdentityProvider

_cognito_provider = CognitoIdentityProvider()
_mock_provider = MockIdentityProvider()


def get_identity_provider() -> IIdentityProvider:
    """Returns the stage-aware identity provider.

    Returns:
        MockIdentityProvider when STAGE is 'local', CognitoIdentityProvider otherwise.
    """
    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local"))
    if stage == "local":
        return _mock_provider
    return _cognito_provider


def _problem(status_code: int, problem_type: str, title: str, detail: str) -> HTTPException:
    """Constructs an HTTPException that will be caught by the RFC 7807 handler.

    Args:
        status_code: HTTP status code.
        problem_type: URI identifying the problem type.
        title: Short human-readable title.
        detail: Detailed human-readable explanation.

    Returns:
        HTTPException with detail set to the problem type title.
    """
    raise HTTPException(status_code=status_code, detail=detail)


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_mock_user_id: str | None = Header(default=None, alias="X-Mock-User-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """FastAPI dependency that resolves the authenticated user entity.

    Args:
        authorization: Bearer token from Authorization header.
        x_mock_user_id: Mock user UUID from X-Mock-User-Id header (local only).
        session: Active database session.

    Returns:
        Authenticated User domain entity.

    Raises:
        HTTPException: 401 if the token is invalid or user is not provisioned.
        HTTPException: 403 if the account is disabled.
    """
    stage = os.getenv("STAGE", "local")

    if stage == "local" and x_mock_user_id:
        return await _resolve_mock_user(x_mock_user_id, session)

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")
    return await _resolve_cognito_user(token, session)


async def _resolve_mock_user(mock_id: str, session: AsyncSession) -> User:
    """Resolves or provisions a mock user by UUID for local development.

    Args:
        mock_id: UUID string from X-Mock-User-Id header.
        session: Active database session.

    Returns:
        Matched or newly provisioned User entity.

    Raises:
        HTTPException: 401 if the mock_id is not a valid UUID format.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from vistarae_core.adapters.db.tables import UserTable  # noqa: PLC0415

    try:
        claims = await _mock_provider.verify_token(mock_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user_uuid = UUID(claims["sub"])

    result = await session.execute(select(UserTable).where(UserTable.id == user_uuid))
    row = result.scalar_one_or_none()

    if row is None:
        # Auto-provision a mock user for local development.
        from datetime import UTC, datetime  # noqa: PLC0415

        from vistarae_core.adapters.db.tables import (  # noqa: PLC0415
            UserMetricsTable,
            UserPreferencesTable,
            UserQuotasTable,
        )

        now = datetime.now(UTC)
        user_row = UserTable(
            id=user_uuid,
            cognito_sub=claims["sub"],
            email=claims["email"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(user_row)
        session.add(UserPreferencesTable(user_id=user_uuid, created_at=now, updated_at=now))
        session.add(UserMetricsTable(user_id=user_uuid, updated_at=now))
        session.add(UserQuotasTable(user_id=user_uuid, window_start_at=now, updated_at=now))
        await session.flush()
        row = user_row

    if row.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {user_uuid} has been administratively disabled.",
        )

    return User(
        id=row.id,
        cognito_sub=row.cognito_sub,
        email=row.email,
        full_name=row.full_name,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _resolve_cognito_user(token: str, session: AsyncSession) -> User:
    """Validates a Cognito JWT and resolves the tenant user.

    Args:
        token: Raw Bearer JWT string.
        session: Active database session.

    Returns:
        Matched User entity.

    Raises:
        HTTPException: 401 if the JWT is invalid or the user has no DB record.
        HTTPException: 403 if the account is disabled.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from vistarae_core.adapters.db.tables import UserTable  # noqa: PLC0415

    try:
        claims = await _cognito_provider.verify_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    cognito_sub = claims["sub"]
    result = await session.execute(select(UserTable).where(UserTable.cognito_sub == cognito_sub))
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No Vistarae account found for Cognito identity '{cognito_sub}'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if row.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {row.id} has been administratively disabled.",
        )

    return User(
        id=row.id,
        cognito_sub=row.cognito_sub,
        email=row.email,
        full_name=row.full_name,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
