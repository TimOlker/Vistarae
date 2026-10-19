# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Local database seeding script (T-052).

Creates test users across low, high, and admin tiers.
Enforces Constitution Principle 6: Strictly verifies STAGE == 'local' before
performing any destructive or seeding operations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from vistarae_core.adapters.db.session import _get_session_factory, init_engine
from vistarae_core.adapters.db.tables import (
    UserMetricsTable,
    UserPreferencesTable,
    UserQuotasTable,
    UserTable,
)

SEED_USERS = [
    {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "cognito_sub": "00000000-0000-0000-0000-000000000001",
        "email": "low-tier@local.vistarae.dev",
        "full_name": "Low Tier Traveler",
        "tier": "low",
        "monthly_token_quota": 50000,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000002"),
        "cognito_sub": "00000000-0000-0000-0000-000000000002",
        "email": "high-tier@local.vistarae.dev",
        "full_name": "High Tier Traveler",
        "tier": "high",
        "monthly_token_quota": 200000,
    },
    {
        "id": UUID("00000000-0000-0000-0000-000000000003"),
        "cognito_sub": "00000000-0000-0000-0000-000000000003",
        "email": "admin@local.vistarae.dev",
        "full_name": "Admin Operator",
        "tier": "admin",
        "monthly_token_quota": 1000000,
    },
]


async def seed_local_db() -> None:
    """Seeds test users and configurations in local development database.

    Raises:
        RuntimeError: If STAGE is not 'local'.
    """
    stage = os.getenv("STAGE", "local")
    if stage != "local":
        raise RuntimeError(
            f"Database seeding is strictly permitted only when STAGE == 'local'. Current STAGE='{stage}'."
        )

    await init_engine()
    factory = _get_session_factory()
    now = datetime.now(UTC)

    async with factory() as session:
        for seed in SEED_USERS:
            existing = await session.scalar(
                select(UserTable).where(UserTable.id == seed["id"])
            )
            if existing is not None:
                await session.execute(delete(UserTable).where(UserTable.id == seed["id"]))

            user_row = UserTable(
                id=seed["id"],
                cognito_sub=seed["cognito_sub"],
                email=seed["email"],
                full_name=seed["full_name"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            pref_row = UserPreferencesTable(
                user_id=seed["id"],
                created_at=now,
                updated_at=now,
            )
            metric_row = UserMetricsTable(
                user_id=seed["id"],
                updated_at=now,
            )
            quota_row = UserQuotasTable(
                user_id=seed["id"],
                tier=seed["tier"],
                monthly_token_quota=seed["monthly_token_quota"],
                current_token_usage=0,
                request_count=0,
                window_start_at=now,
                is_disabled=False,
                updated_at=now,
            )
            session.add_all([user_row, pref_row, metric_row, quota_row])

        await session.commit()
    print(f"Successfully seeded {len(SEED_USERS)} test users.")


if __name__ == "__main__":
    try:
        asyncio.run(seed_local_db())
    except Exception as exc:
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
