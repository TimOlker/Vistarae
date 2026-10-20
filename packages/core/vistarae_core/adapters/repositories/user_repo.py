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

"""SQLAlchemy 2.0 user and tenant preferences repository (T-020).

Implements IUserRepository interface using Pure Async SQLAlchemy 2.0.
Enforces Constitution Principle 3: Explicit WHERE user_id predicates on all operations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)
from vistarae_core.domain.entities import (
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.value_objects import (
    PacingMode,
    ThemeMode,
    TransitSpeedMode,
    UserTier,
)


class SqlAlchemyUserRepository:
    """SQLAlchemy 2.0 implementation of IUserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the repository with an active AsyncSession.

        Args:
            session: AsyncSession database handle.
        """
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieves a user by primary key.

        Args:
            user_id: UUID of the target user.

        Returns:
            User entity or None if not found.
        """
        stmt = select(UserTable).where(UserTable.id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return User(
            id=row.id,
            cognito_sub=row.cognito_sub,
            email=row.email,
            full_name=row.full_name,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_by_cognito_sub(self, sub: str) -> User | None:
        """Resolves a user entity from a Cognito JWT subject claim.

        Args:
            sub: Cognito unique subject identifier.

        Returns:
            Matched User entity or None.
        """
        stmt = select(UserTable).where(UserTable.cognito_sub == sub)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return User(
            id=row.id,
            cognito_sub=row.cognito_sub,
            email=row.email,
            full_name=row.full_name,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_by_email(self, email: str) -> User | None:
        """Resolves a user entity by registered email address.

        Args:
            email: User's registered email address.

        Returns:
            Matched User entity or None.
        """
        stmt = select(UserTable).where(UserTable.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return User(
            id=row.id,
            cognito_sub=row.cognito_sub,
            email=row.email,
            full_name=row.full_name,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create(
        self,
        user: User,
        preferences: UserPreferences,
        quotas: UserQuota,
        metrics: UserMetric,
    ) -> User:
        """Inserts a new tenant with all sub-tables atomically.

        Args:
            user: Core user aggregate.
            preferences: Partitioned tenant preferences.
            quotas: Initial quota allocation.
            metrics: Zero-initialized utilization metrics.

        Returns:
            Persisted User entity.
        """
        user_row = UserTable(
            id=user.id,
            cognito_sub=user.cognito_sub,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        pref_row = UserPreferencesTable(
            user_id=user.id,
            theme=preferences.theme.value
            if hasattr(preferences.theme, "value")
            else str(preferences.theme),
            email_notifications_enabled=preferences.email_notifications_enabled,
            push_notifications_enabled=preferences.push_notifications_enabled,
            marketing_emails_enabled=preferences.marketing_emails_enabled,
            clustering_enabled=preferences.clustering_enabled,
            clustering_radius_meters=preferences.clustering_radius_meters,
            default_map_layer=preferences.default_map_layer,
            geoproximity_scope_km=preferences.geoproximity_scope_km,
            pin_color_presets=preferences.pin_color_presets,
            pacing=preferences.pacing.value
            if hasattr(preferences.pacing, "value")
            else str(preferences.pacing),
            meal_intervals_hours=preferences.meal_intervals_hours,
            lunch_packing_enabled=preferences.lunch_packing_enabled,
            transit_speed_mode=preferences.transit_speed_mode.value
            if hasattr(preferences.transit_speed_mode, "value")
            else str(preferences.transit_speed_mode),
            daily_activity_hour_cap=preferences.daily_activity_hour_cap,
            preferred_currency=preferences.preferred_currency,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at,
        )
        quota_row = UserQuotasTable(
            user_id=user.id,
            monthly_token_quota=quotas.monthly_token_quota,
            current_token_usage=quotas.current_token_usage,
            tier=quotas.tier.value if hasattr(quotas.tier, "value") else str(quotas.tier),
            request_count=quotas.request_count,
            window_start_at=quotas.window_start_at,
            is_disabled=quotas.is_disabled,
            updated_at=quotas.updated_at,
        )
        metric_row = UserMetricsTable(
            user_id=user.id,
            poi_count=metrics.poi_count,
            total_tokens_consumed=metrics.total_tokens_consumed,
            updated_at=metrics.updated_at,
        )
        self._session.add_all([user_row, pref_row, quota_row, metric_row])
        await self._session.flush()
        return user

    async def update_profile(self, user_id: UUID, full_name: str) -> None:
        """Updates user display name.

        Args:
            user_id: UUID of the tenant.
            full_name: New display name value.
        """
        stmt = (
            update(UserTable)
            .where(UserTable.id == user_id)
            .values(full_name=full_name, updated_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def delete(self, user_id: UUID) -> None:
        """Permanently removes a tenant and all cascaded sub-records.

        Args:
            user_id: UUID of the tenant to delete.
        """
        stmt = delete(UserTable).where(UserTable.id == user_id)
        await self._session.execute(stmt)

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        """Retrieves the preferences record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserPreferences entity or None if not found.
        """
        stmt = select(UserPreferencesTable).where(UserPreferencesTable.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserPreferences(
            user_id=row.user_id,
            theme=ThemeMode(row.theme),
            email_notifications_enabled=row.email_notifications_enabled,
            push_notifications_enabled=row.push_notifications_enabled,
            marketing_emails_enabled=row.marketing_emails_enabled,
            clustering_enabled=row.clustering_enabled,
            clustering_radius_meters=row.clustering_radius_meters,
            default_map_layer=row.default_map_layer,
            geoproximity_scope_km=row.geoproximity_scope_km,
            pin_color_presets=row.pin_color_presets,
            pacing=PacingMode(row.pacing),
            meal_intervals_hours=row.meal_intervals_hours,
            lunch_packing_enabled=row.lunch_packing_enabled,
            transit_speed_mode=TransitSpeedMode(row.transit_speed_mode),
            daily_activity_hour_cap=row.daily_activity_hour_cap,
            preferred_currency=row.preferred_currency,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def update_preferences(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies a partial update to tenant preferences.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        updates_clean = dict(updates)
        for k, v in list(updates_clean.items()):
            if hasattr(v, "value"):
                updates_clean[k] = v.value
        updates_clean["updated_at"] = datetime.now(UTC)
        stmt = (
            update(UserPreferencesTable)
            .where(UserPreferencesTable.user_id == user_id)
            .values(**updates_clean)
        )
        await self._session.execute(stmt)

    async def get_metrics(self, user_id: UUID) -> UserMetric | None:
        """Retrieves aggregate metrics for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserMetric entity or None.
        """
        stmt = select(UserMetricsTable).where(UserMetricsTable.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserMetric(
            user_id=row.user_id,
            poi_count=row.poi_count,
            total_tokens_consumed=row.total_tokens_consumed,
            updated_at=row.updated_at,
        )

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves the quota record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        stmt = select(UserQuotasTable).where(UserQuotasTable.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UserQuota(
            user_id=row.user_id,
            monthly_token_quota=row.monthly_token_quota,
            current_token_usage=row.current_token_usage,
            tier=UserTier(row.tier),
            request_count=row.request_count,
            window_start_at=row.window_start_at,
            is_disabled=row.is_disabled,
            updated_at=row.updated_at,
        )
