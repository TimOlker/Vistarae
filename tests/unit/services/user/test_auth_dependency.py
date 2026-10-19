# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for stage-aware authentication dependency (T-017).

Tests cover:
- Local stage mock bypass (existing user, auto-provisioning new user, disabled user 403, invalid UUID 401)
- Cloud stage bearer token handling (missing header 401, invalid token 401, orphaned JWT 401, disabled user 403, success 200)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from vistarae_core.adapters.db.tables import UserTable

from services.user.dependencies import get_current_user


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestLocalMockBypass:
    """Tests authentication via X-Mock-User-Id when STAGE == 'local'."""

    @pytest.mark.asyncio
    async def test_mock_user_existing_active(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns User entity for existing active mock user."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_row = UserTable(
            id=test_id,
            cognito_sub=str(test_id),
            email="mock@local.vistarae.dev",
            full_name="Mock User",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        user = await get_current_user(
            authorization=None,
            x_mock_user_id=str(test_id),
            session=mock_session,
        )

        assert user.id == test_id
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_mock_user_auto_provisioning(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-provisions new mock user and sub-tables when user not found in DB."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user = await get_current_user(
            authorization=None,
            x_mock_user_id=str(test_id),
            session=mock_session,
        )

        assert user.id == test_id
        assert mock_session.add.call_count == 4
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_user_disabled_returns_403(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Disabled mock user returns 403 Forbidden."""
        monkeypatch.setenv("STAGE", "local")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_row = UserTable(
            id=test_id,
            cognito_sub=str(test_id),
            email="mock@local.vistarae.dev",
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization=None,
                x_mock_user_id=str(test_id),
                session=mock_session,
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_mock_user_invalid_uuid_returns_401(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed mock UUID returns 401 Unauthorized."""
        monkeypatch.setenv("STAGE", "local")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization=None,
                x_mock_user_id="not-a-valid-uuid",
                session=mock_session,
            )
        assert exc_info.value.status_code == 401


class TestCognitoCloudAuthentication:
    """Tests authentication via Bearer JWT and Cognito JWKS verification."""

    @pytest.mark.asyncio
    async def test_missing_authorization_header_returns_401(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing or non-bearer header returns 401."""
        monkeypatch.setenv("STAGE", "production")

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization=None,
                x_mock_user_id=None,
                session=mock_session,
            )
        assert exc_info.value.status_code == 401

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization="Basic 123",
                x_mock_user_id=None,
                session=mock_session,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Token validation failure returns 401."""
        monkeypatch.setenv("STAGE", "production")

        with patch(
            "services.user.dependencies._cognito_provider.verify_token",
            side_effect=ValueError("Token expired"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    authorization="Bearer bad-token",
                    session=mock_session,
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_orphaned_jwt_returns_401(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid token for non-existent DB user returns 401."""
        monkeypatch.setenv("STAGE", "production")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch(
            "services.user.dependencies._cognito_provider.verify_token",
            return_value={"sub": "sub-unknown"},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    authorization="Bearer valid-token",
                    session=mock_session,
                )
            assert exc_info.value.status_code == 401
            assert "No Vistarae account found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_disabled_cognito_user_returns_403(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid token for disabled DB user returns 403."""
        monkeypatch.setenv("STAGE", "production")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_row = UserTable(
            id=test_id,
            cognito_sub="sub-disabled",
            email="disabled@example.com",
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        with patch(
            "services.user.dependencies._cognito_provider.verify_token",
            return_value={"sub": "sub-disabled"},
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    authorization="Bearer valid-token",
                    session=mock_session,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_cognito_user_success(
        self, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid token for active user returns User entity."""
        monkeypatch.setenv("STAGE", "production")
        test_id = uuid.uuid4()
        now = datetime.now(UTC)

        fake_row = UserTable(
            id=test_id,
            cognito_sub="sub-alice",
            email="alice@example.com",
            full_name="Alice",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        with patch(
            "services.user.dependencies._cognito_provider.verify_token",
            return_value={"sub": "sub-alice"},
        ):
            user = await get_current_user(
                authorization="Bearer valid-token",
                session=mock_session,
            )
            assert user.id == test_id
            assert user.email == "alice@example.com"
