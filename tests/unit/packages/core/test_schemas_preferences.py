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

"""Unit tests for Pydantic v2 boundary schemas and validation rules."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from vistarae_core.domain.value_objects import PacingMode, ThemeMode, UserTier
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.errors import ProblemDetails
from vistarae_core.schemas.preferences import (
    PlannerPreferencesResponse,
    POIPreferencesResponse,
    UIPreferencesResponse,
    UserPreferencesResponse,
)
from vistarae_core.schemas.user import (
    UserMetricsResponse,
    UserProfileResponse,
    UserQuotaResponse,
    UserResponse,
)


class TestStrictBaseModel:
    """Tests for StrictBaseModel extra forbid and whitespace stripping."""

    def test_extra_forbidden(self) -> None:
        """Asserts that unexpected extra fields are rejected."""

        class SampleSchema(StrictBaseModel):
            name: str

        with pytest.raises(ValidationError) as exc_info:
            SampleSchema.model_validate({"name": "Alice", "unexpected_field": 123})
        assert "extra_forbidden" in str(exc_info.value)

    def test_whitespace_stripped(self) -> None:
        """Asserts that string values have whitespace stripped automatically."""

        class SampleSchema(StrictBaseModel):
            name: str

        model = SampleSchema(name="  John Doe  ")
        assert model.name == "John Doe"


class TestPreferencesValidation:
    """Tests for sub-domain preferences validation bounds."""

    def test_poi_preferences_bounds(self) -> None:
        """Asserts clustering radius and geoproximity boundaries."""
        valid_payload = {
            "clustering_enabled": True,
            "clustering_radius_meters": 50,
            "default_map_layer": "standard",
            "geoproximity_scope_km": 25.0,
            "pin_color_presets": {"default": "#3B82F6"},
        }
        res = POIPreferencesResponse.model_validate(valid_payload)
        assert res.clustering_radius_meters == 50

        # Radius < 10 must fail
        with pytest.raises(ValidationError):
            POIPreferencesResponse.model_validate({**valid_payload, "clustering_radius_meters": 5})

        # Radius > 500 must fail
        with pytest.raises(ValidationError):
            POIPreferencesResponse.model_validate(
                {**valid_payload, "clustering_radius_meters": 501}
            )

        # Scope < 1.0 must fail
        with pytest.raises(ValidationError):
            POIPreferencesResponse.model_validate({**valid_payload, "geoproximity_scope_km": 0.5})

    def test_planner_preferences_bounds(self) -> None:
        """Asserts planner hours and currency length limits."""
        valid_planner = {
            "pacing": "moderate",
            "meal_intervals_hours": 4.0,
            "lunch_packing_enabled": False,
            "transit_speed_mode": "walking",
            "daily_activity_hour_cap": 8.0,
            "preferred_currency": "USD",
        }
        res = PlannerPreferencesResponse.model_validate(valid_planner)
        assert res.pacing == PacingMode.MODERATE

        # Currency != 3 chars must fail
        with pytest.raises(ValidationError):
            PlannerPreferencesResponse.model_validate({**valid_planner, "preferred_currency": "US"})

        # Daily activity cap > 18.0 must fail
        with pytest.raises(ValidationError):
            PlannerPreferencesResponse.model_validate(
                {**valid_planner, "daily_activity_hour_cap": 24.0}
            )


class TestUserProfileResponse:
    """Tests for full UserProfileResponse composition."""

    def test_user_profile_response(self) -> None:
        """Asserts aggregation of user, preferences, metrics, and quotas."""
        now = datetime.now(UTC)
        uid = uuid4()
        user_res = UserResponse(
            id=uid,
            email="traveler@example.com",
            full_name="Explorer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        prefs_res = UserPreferencesResponse(
            ui=UIPreferencesResponse(
                theme=ThemeMode.SYSTEM,
                email_notifications_enabled=True,
                push_notifications_enabled=True,
                marketing_emails_enabled=False,
            ),
            poi=POIPreferencesResponse(
                clustering_enabled=True,
                clustering_radius_meters=50,
                default_map_layer="standard",
                geoproximity_scope_km=25.0,
                pin_color_presets={"fav": "#E11D48"},
            ),
            planner=PlannerPreferencesResponse(
                pacing=PacingMode.MODERATE,
                meal_intervals_hours=4.0,
                lunch_packing_enabled=False,
                transit_speed_mode="walking",
                daily_activity_hour_cap=8.0,
                preferred_currency="EUR",
            ),
        )
        metrics_res = UserMetricsResponse(
            poi_count=5,
            total_tokens_consumed=1250,
            updated_at=now,
        )
        quota_res = UserQuotaResponse(
            monthly_token_quota=50000,
            current_token_usage=1250,
            tier=UserTier.LOW,
            is_disabled=False,
            updated_at=now,
        )

        profile = UserProfileResponse(
            user=user_res,
            preferences=prefs_res,
            metrics=metrics_res,
            quotas=quota_res,
        )
        assert profile.user.email == "traveler@example.com"
        assert profile.quotas.tier == UserTier.LOW
        assert profile.metrics.poi_count == 5


class TestProblemDetails:
    """Tests for RFC 7807 ProblemDetails."""

    def test_problem_details_serialization(self) -> None:
        """Asserts ProblemDetails fields serialize accurately."""
        problem = ProblemDetails(
            type="https://errors.vistarae.com/rate-limit-exceeded",
            title="Too Many Requests",
            status=429,
            detail="Rate limit exceeded.",
            instance="/api/users/me",
        )
        data = problem.model_dump()
        assert data["status"] == 429
        assert data["title"] == "Too Many Requests"
        assert data["instance"] == "/api/users/me"
