# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure async Alembic migration runner.

Configures Alembic to execute migrations through the SQLAlchemy 2.0
asyncpg engine. Reads DATABASE_URL from the environment and normalizes
the URL scheme to postgresql+asyncpg:// before constructing the engine.

Constitution Principle 4: All schema migrations reside strictly inside
db/migrations/. Alembic check is enforced in CI.
"""

from __future__ import annotations

import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object providing access to alembic.ini values.
config = context.config

# Set up Python logging from alembic.ini [loggers] section if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the project Base so Alembic autogenerate can detect schema drift.
from vistarae_core.adapters.db.tables import (  # noqa: E402
    Base,
)

target_metadata = Base.metadata


def _normalize_url(raw_url: str) -> str:
    """Converts legacy postgres:// or plain postgresql:// to postgresql+asyncpg://.

    Args:
        raw_url: Raw database URL string, possibly with legacy scheme.

    Returns:
        Normalized URL string.
    """
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", raw_url)
    url = url.replace("sslmode=require", "ssl=require")
    # Alembic may have %-escaped percent signs; replace double-% with single.
    url = url.replace("%%", "%")
    return url


def _get_url() -> str:
    """Resolves the database connection URL from environment or alembic.ini.

    Returns:
        Normalized postgresql+asyncpg:// URL string.
    """
    raw = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    return _normalize_url(raw)


def run_migrations_offline() -> None:
    """Generates SQL migration scripts without a live database connection.

    Used by ``alembic upgrade --sql`` for generating DDL scripts.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Executes migrations within an active database connection context.

    Args:
        connection: Active SQLAlchemy async connection.
    """
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Creates an async engine and runs migrations using asyncpg driver."""
    url = _get_url()
    connectable = create_async_engine(
        url,
        connect_args={"statement_cache_size": 0},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration execution."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
