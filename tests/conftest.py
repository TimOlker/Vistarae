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

"""Shared PyTest configuration and fixtures."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from vistarae_core.domain.entities import User, UserPreferences, UserQuota
from vistarae_core.domain.value_objects import UserTier


@pytest.fixture
def mock_user_id() -> UUID:
    """Provides a stable mock UUID for testing."""
    return uuid4()


@pytest.fixture
def mock_user(mock_user_id: UUID) -> User:
    """Provides a default test user entity."""
    return User(
        id=mock_user_id,
        cognito_sub=f"cognito-{mock_user_id}",
        email="traveler@example.com",
        full_name="Vistarae Traveler",
    )


@pytest.fixture
def mock_preferences(mock_user_id: UUID) -> UserPreferences:
    """Provides default test user preferences."""
    return UserPreferences(user_id=mock_user_id)


@pytest.fixture
def mock_quota(mock_user_id: UUID) -> UserQuota:
    """Provides default low-tier user quotas."""
    return UserQuota(user_id=mock_user_id, tier=UserTier.LOW)


@pytest.fixture
def mock_admin_quota(mock_user_id: UUID) -> UserQuota:
    """Provides admin-tier user quotas."""
    return UserQuota(user_id=mock_user_id, tier=UserTier.ADMIN)
