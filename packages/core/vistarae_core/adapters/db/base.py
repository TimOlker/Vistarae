# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""SQLAlchemy 2.0 Declarative Base and shared column mixins.

All ORM models inherit from Base.  TimestampMixin provides created_at and
updated_at columns with automatic UTC timestamps.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide ORM declarative base.

    All table classes must inherit from this base to participate in Alembic
    autogenerate and SQLAlchemy metadata management.
    """


class TimestampMixin:
    """Provides automatic created_at / updated_at UTC timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
