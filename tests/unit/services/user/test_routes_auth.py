# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for UserFunction authentication routes (REQ-AUTH-001..006).

Tests cover:
- POST /api/auth/register (201 Created and 409 Conflict)
- POST /api/auth/confirm-signup (200 OK and tenant database provisioning)
- POST /api/auth/login (200 OK and 401 Unauthorized)
- POST /api/auth/forgot-password (200 OK and 404 Not Found)
- POST /api/auth/reset-password (200 OK and 400 Bad Request)
- POST /api/auth/logout (200 OK and 400 Bad Request)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.ports.identity import IIdentityProvider

from services.local_gateway import app
from services.user.dependencies import get_identity_provider


@pytest.fixture
def mock_identity() -> AsyncMock:
    """Mock identity provider implementing IIdentityProvider."""
    mock = AsyncMock(spec=IIdentityProvider)
    mock.sign_up.return_value = {"user_sub": "sub-123", "user_confirmed": False}
    mock.confirm_sign_up.return_value = True
    mock.initiate_auth.return_value = {
        "access_token": "mock-acc-token",
        "id_token": "mock-id-token",
        "refresh_token": "mock-ref-token",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    mock.forgot_password.return_value = {"Destination": "user@example.com"}
    mock.confirm_forgot_password.return_value = True
    mock.global_sign_out.return_value = True
    return mock


@pytest.fixture
def mock_session() -> AsyncMock:
    """Mock async DB session."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def client(mock_identity: AsyncMock, mock_session: AsyncMock) -> TestClient:
    """Test client overriding identity and db session dependencies."""
    app.dependency_overrides[get_identity_provider] = lambda: mock_identity
    app.dependency_overrides[get_db_session] = lambda: mock_session

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestAuthRoutes:
    """Tests for /api/auth/* endpoints."""

    def test_register_success(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/register returns 201 Created with user_sub."""
        payload = {
            "email": "traveler@example.com",
            "password": "StrongPassword123!",
            "full_name": "Traveler Name",
        }
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_sub"] == "sub-123"
        assert data["user_confirmed"] is False
        mock_identity.sign_up.assert_called_once()

    def test_register_user_already_exists_conflict(
        self, client: TestClient, mock_identity: AsyncMock
    ) -> None:
        """Asserts POST /api/auth/register returns 409 when user already exists."""
        mock_identity.sign_up.side_effect = ValueError(
            "User with email 'traveler@example.com' already exists."
        )
        payload = {
            "email": "traveler@example.com",
            "password": "StrongPassword123!",
        }
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 409

    def test_confirm_signup_success(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/confirm-signup confirms user and creates tenant."""
        payload = {
            "email": "traveler@example.com",
            "confirmation_code": "123456",
            "full_name": "Confirmed Traveler",
        }
        resp = client.post("/api/auth/confirm-signup", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] is True
        assert "user_id" in data
        mock_identity.confirm_sign_up.assert_called_once()

    def test_confirm_signup_invalid_code(
        self, client: TestClient, mock_identity: AsyncMock
    ) -> None:
        """Asserts POST /api/auth/confirm-signup returns 400 on invalid code."""
        mock_identity.confirm_sign_up.side_effect = ValueError(
            "Invalid or expired verification code."
        )
        payload = {
            "email": "traveler@example.com",
            "confirmation_code": "bad-code",
        }
        resp = client.post("/api/auth/confirm-signup", json=payload)
        assert resp.status_code == 400

    def test_login_success(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/login returns JWT tokens."""
        payload = {
            "email": "traveler@example.com",
            "password": "StrongPassword123!",
        }
        resp = client.post("/api/auth/login", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "mock-acc-token"
        assert data["id_token"] == "mock-id-token"
        assert data["token_type"] == "Bearer"

    def test_login_invalid_credentials(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/login returns 401 on bad credentials."""
        mock_identity.initiate_auth.side_effect = ValueError("Invalid email or password.")
        payload = {
            "email": "traveler@example.com",
            "password": "WrongPassword",
        }
        resp = client.post("/api/auth/login", json=payload)
        assert resp.status_code == 401

    def test_forgot_password_success(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/forgot-password dispatches reset code."""
        payload = {"email": "traveler@example.com"}
        resp = client.post("/api/auth/forgot-password", json=payload)
        assert resp.status_code == 200
        assert "dispatched" in resp.json()["message"]

    def test_forgot_password_user_not_found(
        self, client: TestClient, mock_identity: AsyncMock
    ) -> None:
        """Asserts POST /api/auth/forgot-password returns 404 if user unknown."""
        mock_identity.forgot_password.side_effect = ValueError("User not found.")
        payload = {"email": "unknown@example.com"}
        resp = client.post("/api/auth/forgot-password", json=payload)
        assert resp.status_code == 404

    def test_reset_password_success(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/reset-password resets password successfully."""
        payload = {
            "email": "traveler@example.com",
            "confirmation_code": "123456",
            "new_password": "NewStrongPassword123!",
        }
        resp = client.post("/api/auth/reset-password", json=payload)
        assert resp.status_code == 200

    def test_reset_password_invalid_code(
        self, client: TestClient, mock_identity: AsyncMock
    ) -> None:
        """Asserts POST /api/auth/reset-password returns 400 on bad reset code."""
        mock_identity.confirm_forgot_password.side_effect = ValueError("Invalid code.")
        payload = {
            "email": "traveler@example.com",
            "confirmation_code": "bad-code",
            "new_password": "NewStrongPassword123!",
        }
        resp = client.post("/api/auth/reset-password", json=payload)
        assert resp.status_code == 400

    def test_logout_with_header(self, client: TestClient, mock_identity: AsyncMock) -> None:
        """Asserts POST /api/auth/logout with Bearer token invalidates session."""
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer valid-token"},
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["logged_out"] is True
        mock_identity.global_sign_out.assert_called_once_with(access_token="valid-token")

    def test_logout_missing_token_returns_400(self, client: TestClient) -> None:
        """Asserts POST /api/auth/logout without token returns 400."""
        resp = client.post("/api/auth/logout", json={})
        assert resp.status_code == 400
