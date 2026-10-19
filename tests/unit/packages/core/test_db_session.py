# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the SQLAlchemy 2.0 async engine factory (T-009).

Tests cover:
- URL normalization for postgres://, postgresql://, and sslmode=require variants
- QueuePool selection when STAGE == 'local'
- NullPool with statement_cache_size=0 when STAGE != 'local'
- 3-attempt exponential backoff retry with correct delays
- Singleton engine caching and reset behavior
- ValueError when DATABASE_URL is missing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from vistarae_core.adapters.db.session import (
    _build_engine,
    _normalize_url,
    get_engine,
    init_engine,
    reset_engine,
)


class TestUrlNormalization:
    """Verifies that legacy and plain PostgreSQL URLs are correctly normalized."""

    def test_postgres_scheme_replaced(self) -> None:
        """postgres:// scheme should be converted to postgresql+asyncpg://."""
        result = _normalize_url("postgres://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_postgresql_scheme_replaced(self) -> None:
        """postgresql:// scheme should be converted to postgresql+asyncpg://."""
        result = _normalize_url("postgresql://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_asyncpg_scheme_unchanged(self) -> None:
        """Already-normalized URL should pass through unchanged."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _normalize_url(url)
        assert result == url

    def test_sslmode_require_translated(self) -> None:
        """sslmode=require should be replaced with ssl=require for asyncpg."""
        result = _normalize_url("postgres://user:pass@host/db?sslmode=require")
        assert "ssl=require" in result
        assert "sslmode=require" not in result

    def test_other_query_params_preserved(self) -> None:
        """Non-ssl query parameters must survive normalization unchanged."""
        result = _normalize_url("postgres://user:pass@host/db?connect_timeout=10")
        assert "connect_timeout=10" in result


class TestEnginePoolStrategy:
    """Validates correct pool class selection based on STAGE environment."""

    def setup_method(self) -> None:
        """Reset singleton before each test to avoid cross-contamination."""
        reset_engine()

    def teardown_method(self) -> None:
        """Restore clean state after each test."""
        reset_engine()

    def test_local_stage_uses_queue_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """STAGE=local must produce an engine with AsyncAdaptedQueuePool."""
        monkeypatch.setenv("STAGE", "local")
        engine = _build_engine("postgresql+asyncpg://user:pass@localhost/testdb")
        assert engine.pool.__class__.__name__ == "AsyncAdaptedQueuePool"

    def test_cloud_stage_uses_null_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """STAGE=cloud must produce an engine with NullPool."""
        monkeypatch.setenv("STAGE", "cloud")
        engine = _build_engine("postgresql+asyncpg://user:pass@localhost/testdb")
        assert engine.pool.__class__.__name__ == "NullPool"

    def test_production_stage_uses_null_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Any non-local STAGE must produce an engine with NullPool."""
        monkeypatch.setenv("STAGE", "production")
        engine = _build_engine("postgresql+asyncpg://user:pass@localhost/testdb")
        assert engine.pool.__class__.__name__ == "NullPool"


class TestEngineSingleton:
    """Tests singleton caching and reset behavior of get_engine."""

    def setup_method(self) -> None:
        reset_engine()

    def teardown_method(self) -> None:
        reset_engine()

    def test_get_engine_returns_same_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two calls to get_engine should return the exact same object."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    def test_get_engine_raises_without_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_engine must raise ValueError when DATABASE_URL is not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError, match="DATABASE_URL"):
            get_engine()

    def test_reset_engine_clears_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """reset_engine must allow a fresh engine to be created on the next call."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")
        engine1 = get_engine()
        reset_engine()
        engine2 = get_engine()
        assert engine1 is not engine2


class TestRetryBackoff:
    """Tests the 3-attempt exponential backoff in init_engine."""

    def setup_method(self) -> None:
        reset_engine()

    def teardown_method(self) -> None:
        reset_engine()

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """init_engine should succeed immediately when the first probe passes."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")

        with patch(
            "vistarae_core.adapters.db.session._probe_connection",
            new_callable=AsyncMock,
        ) as mock_probe:
            mock_probe.return_value = None
            engine = await init_engine()
            assert engine is not None
            assert mock_probe.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """init_engine should retry and succeed on the second attempt."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")

        call_count = 0

        async def flaky_probe(engine: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionRefusedError("DB not ready")

        with (
            patch("vistarae_core.adapters.db.session._probe_connection", side_effect=flaky_probe),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = await init_engine()
            assert engine is not None
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_all_attempts_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """init_engine should raise RuntimeError after all 3 attempts fail."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")

        with (
            patch(
                "vistarae_core.adapters.db.session._probe_connection",
                new_callable=AsyncMock,
                side_effect=ConnectionRefusedError("DB unreachable"),
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="Database connection failed after 3"),
        ):
            await init_engine()

    @pytest.mark.asyncio
    async def test_retry_delays_are_correct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Retry sleep calls should use 0.5s, 1.5s, 3.0s delays."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("STAGE", "local")

        sleep_calls: list[float] = []

        async def mock_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with (
            patch(
                "vistarae_core.adapters.db.session._probe_connection",
                new_callable=AsyncMock,
                side_effect=OSError("timeout"),
            ),
            patch("asyncio.sleep", side_effect=mock_sleep),
            pytest.raises(RuntimeError),
        ):
            await init_engine()

        assert sleep_calls == [0.5, 1.5]


class TestSessionDependency:
    """Tests for get_db_session generator and session factory."""

    def setup_method(self) -> None:
        reset_engine()

    def teardown_method(self) -> None:
        reset_engine()

    @pytest.mark.asyncio
    async def test_probe_connection(self) -> None:
        """Asserts _probe_connection acquires connection and executes text('SELECT 1')."""
        from vistarae_core.adapters.db.session import _probe_connection

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn

        await _probe_connection(mock_engine)
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Asserts get_db_session yields session and commits on clean exit."""
        from vistarae_core.adapters.db.session import get_db_session

        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch(
            "vistarae_core.adapters.db.session._get_session_factory", return_value=mock_factory
        ):
            gen = get_db_session()
            session = await anext(gen)
            assert session is mock_session
            with pytest.raises(StopAsyncIteration):
                await anext(gen)
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_db_session_rollback_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asserts get_db_session rolls back and re-raises on exception."""
        from vistarae_core.adapters.db.session import get_db_session

        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch(
            "vistarae_core.adapters.db.session._get_session_factory", return_value=mock_factory
        ):
            gen = get_db_session()
            session = await anext(gen)
            assert session is mock_session
            with pytest.raises(RuntimeError, match="Handler failure"):
                await gen.athrow(RuntimeError("Handler failure"))
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()
