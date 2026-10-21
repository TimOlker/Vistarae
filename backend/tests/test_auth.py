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

"""Unit tests for user registration, bcrypt hashing, and JWT authentication."""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import app
from app.models import User
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    plain = "SuperTraveler2026!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_issuance_and_decoding():
    user_id = uuid.uuid4()
    email = "test@vistarae.com"
    token = create_access_token(user_id=user_id, email=email)

    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded["sub"] == str(user_id)
    assert decoded["email"] == email
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_register_user_success():
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None  # No existing user
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newtraveler@vistarae.com",
                "password": "Password123!",
                "full_name": "New Traveler",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newtraveler@vistarae.com"
    assert data["user"]["full_name"] == "New Traveler"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_duplicate_email_fails():
    mock_db = AsyncMock()
    existing = User(
        id=uuid.uuid4(),
        email="existing@vistarae.com",
        hashed_password="hash",
    )
    mock_db.scalar.return_value = existing
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@vistarae.com",
                "password": "Password123!",
            },
        )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_user_success():
    mock_db = AsyncMock()
    plain_password = "SecretPassword123!"
    existing_user = User(
        id=uuid.uuid4(),
        email="traveler@vistarae.com",
        hashed_password=hash_password(plain_password),
        full_name="Valid User",
        is_active=True,
    )
    mock_db.scalar.return_value = existing_user
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "traveler@vistarae.com",
                "password": plain_password,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "traveler@vistarae.com"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_invalid_password_fails():
    mock_db = AsyncMock()
    existing_user = User(
        id=uuid.uuid4(),
        email="traveler@vistarae.com",
        hashed_password=hash_password("RealPassword123!"),
        is_active=True,
    )
    mock_db.scalar.return_value = existing_user
    app.dependency_overrides[get_db] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "traveler@vistarae.com",
                "password": "WrongPassword!",
            },
        )

    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

    app.dependency_overrides.clear()
