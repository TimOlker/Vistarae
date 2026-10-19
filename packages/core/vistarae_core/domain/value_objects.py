# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Domain value objects and enumeration types.

Strictly modeled as Python StrEnum backed by VARCHAR columns per Constitution
Principle 4 (prohibiting PostgreSQL native ENUM types).
"""

from __future__ import annotations

from enum import StrEnum


class UserTier(StrEnum):
    """Governance tier for user quotas and rate limiting."""

    LOW = "low"
    HIGH = "high"
    ADMIN = "admin"


class ThemeMode(StrEnum):
    """User interface display theme setting."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class PacingMode(StrEnum):
    """Itinerary generation speed pacing."""

    RELAXED = "relaxed"
    MODERATE = "moderate"
    FAST_PACED = "fast_paced"


class TransitSpeedMode(StrEnum):
    """Travel transit method for distance calculations."""

    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"
    DRIVING = "driving"


class IdempotencyStatus(StrEnum):
    """Lifecycle state of an idempotency key."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
