# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure async SQLAlchemy 2.0 connection factory with Neon cold-start resilience.

Implements Constitution Principle 3:
- URL normalization from postgres:// or postgresql:// → postgresql+asyncpg://
- sslmode=require → ssl=require query-param translation
- QueuePool (pool_size=5, max_overflow=5) when STAGE == 'local'
- NullPool with statement_cache_size=0 for cloud/serverless (Neon + Lambda)
- 3-attempt exponential backoff retry loop: 500ms → 1500ms → 3000ms
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import AsyncGenerator

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

logger = logging.getLogger(__name__)

# Singleton engine held at module level for connection pool reuse.
_engine: AsyncEngine | None = None

# Retry configuration: wait intervals in seconds between connection attempts.
_RETRY_DELAYS: tuple[float, ...] = (0.5, 1.5, 3.0)


def _normalize_url(raw_url: str) -> str:
    """Converts legacy postgres:// or plain postgresql:// to postgresql+asyncpg://.

    Also translates sslmode=require query parameter to ssl=require so asyncpg
    can interpret it correctly.

    Args:
        raw_url: Raw database URL string, possibly with legacy scheme.

    Returns:
        Normalized URL string suitable for create_async_engine.
    """
    # Replace scheme to ensure asyncpg dialect is always selected.
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", raw_url)
    # Translate sslmode=require → ssl=require for asyncpg compatibility.
    url = url.replace("sslmode=require", "ssl=require")
    return url


def _build_engine(database_url: str) -> AsyncEngine:
    """Constructs an AsyncEngine with appropriate pool strategy.

    Uses QueuePool locally to amortize connection overhead and NullPool with
    statement_cache_size=0 in cloud environments for Neon + PgBouncer
    compatibility (Constitution Principle 3).

    Args:
        database_url: Normalized postgresql+asyncpg:// connection URL.

    Returns:
        Configured AsyncEngine instance.
    """
    stage = os.getenv("STAGE", "local")
    normalized = _normalize_url(database_url)

    if stage == "local":
        return create_async_engine(
            normalized,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=5,
            max_overflow=5,
            echo=False,
        )

    # Cloud / serverless path — NullPool prevents persistent connections across
    # Lambda invocations; statement_cache_size=0 disables asyncpg prepared-
    # statement caching which conflicts with PgBouncer transaction-mode pooling.
    return create_async_engine(
        normalized,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
        echo=False,
    )


async def _probe_connection(engine: AsyncEngine) -> None:
    """Executes a lightweight SELECT 1 to verify the engine can acquire a connection.

    Args:
        engine: AsyncEngine instance to probe.

    Raises:
        Exception: Any connectivity failure from the underlying driver.
    """
    from sqlalchemy import text  # noqa: PLC0415

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Returns the module-level singleton AsyncEngine, creating it on first call.

    Args:
        database_url: Optional override URL; defaults to DATABASE_URL env var.

    Returns:
        Shared AsyncEngine instance.

    Raises:
        ValueError: If no DATABASE_URL is available and no URL is provided.
    """
    global _engine  # noqa: PLW0603

    if _engine is None:
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "DATABASE_URL environment variable is required but not set."
            )
        _engine = _build_engine(url)

    return _engine


async def init_engine(database_url: str | None = None) -> AsyncEngine:
    """Initializes the singleton engine with 3-attempt exponential backoff retry.

    Designed to survive Neon scale-to-zero cold starts and transient network
    failures during Lambda initialization (Constitution Principle 3).

    Args:
        database_url: Optional override URL; defaults to DATABASE_URL env var.

    Returns:
        Verified AsyncEngine instance with confirmed connectivity.

    Raises:
        RuntimeError: If all 3 retry attempts are exhausted without success.
    """
    engine = get_engine(database_url)

    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            await _probe_connection(engine)
            logger.info(
                "MSG ->| [session.py -> database] Engine connected on attempt %d",
                attempt,
            )
            return engine
        except Exception as exc:  # noqa: BLE001
            if attempt == len(_RETRY_DELAYS):
                logger.error(
                    "MSG <-| [database -> session.py] All %d connection attempts failed: %s",
                    len(_RETRY_DELAYS),
                    exc,
                )
                raise RuntimeError(
                    f"Database connection failed after {len(_RETRY_DELAYS)} attempts: {exc}"
                ) from exc

            logger.warning(
                "MSG ->| [session.py -> database] Attempt %d failed (%s). "
                "Retrying in %.1fs…",
                attempt,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # Unreachable: the loop above always raises on the final iteration.
    raise RuntimeError("Unreachable: retry loop exited without return or raise.")  # pragma: no cover


def reset_engine() -> None:
    """Clears the cached singleton engine reference.

    Primarily used in tests to ensure a fresh engine per test suite.
    """
    global _engine  # noqa: PLW0603
    _engine = None


# ---------------------------------------------------------------------------
# FastAPI / Starlette dependency
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns (or lazily creates) the module-level async session factory.

    Returns:
        Configured async_sessionmaker bound to the singleton engine.
    """
    global AsyncSessionLocal  # noqa: PLW0603

    if AsyncSessionLocal is None:
        AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    return AsyncSessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI/Starlette dependency yielding a transactional AsyncSession.

    Rolls back automatically if an exception is raised within the handler.

    Yields:
        Open AsyncSession bound to the active engine connection pool.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
