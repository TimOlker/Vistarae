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

"""Unit tests for AdminFunction RBAC dependency (T-041).

Tests:
- require_admin succeeds when current_user has tier == 'admin'
- require_admin raises 403 Forbidden when tier != 'admin'
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import UserTier

from services.admin.dependencies import require_admin


@pytest.fixture
def base_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-admin-test",
        email="user@example.com",
    )


class TestAdminRBACGuard:
    """Tests for require_admin dependency."""

    @pytest.mark.asyncio
    async def test_require_admin_success(self, base_user: User) -> None:
        """User with admin tier passes through."""
        base_user._tier = UserTier.ADMIN
        result = await require_admin(current_user=base_user)
        assert result is base_user

    @pytest.mark.asyncio
    async def test_require_admin_low_tier_forbidden(self, base_user: User) -> None:
        """User with low tier raises 403 Forbidden."""
        base_user._tier = UserTier.LOW
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=base_user)
        assert exc_info.value.status_code == 403
        assert "Administrative access required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_admin_no_tier_default_forbidden(self, base_user: User) -> None:
        """User without _tier attribute defaults to low tier and raises 403."""
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user=base_user)
        assert exc_info.value.status_code == 403
