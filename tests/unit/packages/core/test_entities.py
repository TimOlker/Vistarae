# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for domain entities, value objects, and domain exceptions."""

from __future__ import annotations

from uuid import uuid4

from vistarae_core.domain.entities import (
    IdempotencyRecord,
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.exceptions import (
    AccountDisabledError,
    DomainError,
    IdempotencyConflictError,
    QuotaExceededError,
    TenantNotFoundError,
)
from vistarae_core.domain.value_objects import (
    IdempotencyStatus,
    PacingMode,
    ThemeMode,
    TransitSpeedMode,
    UserTier,
)


class TestValueObjects:
    """Tests for StrEnum value objects."""

    def test_user_tier_values(self) -> None:
        """Asserts UserTier string values."""
        assert UserTier.LOW == "low"
        assert UserTier.HIGH == "high"
        assert UserTier.ADMIN == "admin"

    def test_theme_mode_values(self) -> None:
        """Asserts ThemeMode string values."""
        assert ThemeMode.LIGHT == "light"
        assert ThemeMode.DARK == "dark"
        assert ThemeMode.SYSTEM == "system"

    def test_pacing_mode_values(self) -> None:
        """Asserts PacingMode string values."""
        assert PacingMode.RELAXED == "relaxed"
        assert PacingMode.MODERATE == "moderate"
        assert PacingMode.FAST_PACED == "fast_paced"

    def test_transit_speed_mode_values(self) -> None:
        """Asserts TransitSpeedMode string values."""
        assert TransitSpeedMode.WALKING == "walking"
        assert TransitSpeedMode.BICYCLING == "bicycling"
        assert TransitSpeedMode.TRANSIT == "transit"
        assert TransitSpeedMode.DRIVING == "driving"

    def test_idempotency_status_values(self) -> None:
        """Asserts IdempotencyStatus string values."""
        assert IdempotencyStatus.PENDING == "PENDING"
        assert IdempotencyStatus.COMPLETED == "COMPLETED"
        assert IdempotencyStatus.FAILED == "FAILED"


class TestEntities:
    """Tests for domain entities."""

    def test_user_creation(self) -> None:
        """Asserts User entity default and explicit properties."""
        uid = uuid4()
        user = User(id=uid, cognito_sub="sub-123", email="user@example.com")
        assert user.id == uid
        assert user.cognito_sub == "sub-123"
        assert user.email == "user@example.com"
        assert user.is_active is True
        assert user.full_name is None

    def test_user_preferences_defaults(self) -> None:
        """Asserts UserPreferences defaults match specification."""
        uid = uuid4()
        prefs = UserPreferences(user_id=uid)
        assert prefs.user_id == uid
        assert prefs.theme == ThemeMode.SYSTEM
        assert prefs.email_notifications_enabled is True
        assert prefs.push_notifications_enabled is True
        assert prefs.marketing_emails_enabled is False
        assert prefs.clustering_enabled is True
        assert prefs.clustering_radius_meters == 50
        assert prefs.default_map_layer == "standard"
        assert prefs.geoproximity_scope_km == 25.0
        assert "favorite" in prefs.pin_color_presets
        assert prefs.pacing == PacingMode.MODERATE
        assert prefs.meal_intervals_hours == 4.0
        assert prefs.transit_speed_mode == TransitSpeedMode.WALKING
        assert prefs.daily_activity_hour_cap == 8.0
        assert prefs.preferred_currency == "USD"

    def test_user_metric_defaults(self) -> None:
        """Asserts UserMetric counters initialize to zero."""
        uid = uuid4()
        metric = UserMetric(user_id=uid)
        assert metric.user_id == uid
        assert metric.poi_count == 0
        assert metric.total_tokens_consumed == 0

    def test_user_quota_token_availability(self) -> None:
        """Asserts UserQuota token availability computation."""
        uid = uuid4()
        quota = UserQuota(user_id=uid, monthly_token_quota=1000, current_token_usage=500)
        assert quota.has_available_tokens is True

        quota.current_token_usage = 1000
        assert quota.has_available_tokens is False

        quota.current_token_usage = 1200
        assert quota.has_available_tokens is False

    def test_idempotency_record_defaults(self) -> None:
        """Asserts IdempotencyRecord initialization."""
        uid = uuid4()
        record = IdempotencyRecord(user_id=uid, idempotency_key="key-abc")
        assert record.user_id == uid
        assert record.idempotency_key == "key-abc"
        assert record.status == IdempotencyStatus.PENDING
        assert record.response_code is None
        assert record.response_payload is None


class TestDomainExceptions:
    """Tests for domain exceptions."""

    def test_account_disabled_error(self) -> None:
        """Asserts AccountDisabledError formatting."""
        err = AccountDisabledError("user-123")
        assert isinstance(err, DomainError)
        assert "Account user-123 is disabled." in str(err)
        assert err.user_id == "user-123"

    def test_quota_exceeded_error(self) -> None:
        """Asserts QuotaExceededError retry_after capture."""
        err = QuotaExceededError("Rate limit reached", retry_after=30)
        assert isinstance(err, DomainError)
        assert "Rate limit reached" in str(err)
        assert err.retry_after == 30

    def test_idempotency_conflict_error(self) -> None:
        """Asserts IdempotencyConflictError formatting."""
        err = IdempotencyConflictError("key-999")
        assert isinstance(err, DomainError)
        assert "key-999" in str(err)
        assert err.idempotency_key == "key-999"

    def test_tenant_not_found_error(self) -> None:
        """Asserts TenantNotFoundError formatting."""
        err = TenantNotFoundError("id-404")
        assert isinstance(err, DomainError)
        assert "id-404" in str(err)
        assert err.identifier == "id-404"
