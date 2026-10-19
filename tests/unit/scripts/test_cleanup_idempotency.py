# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for idempotency key retention cleanup script (T-057).

Tests cover:
- cleanup_idempotency_keys calls repository cleanup_older_than with default hours
- cleanup_idempotency_keys calls with custom hours
- CLI main() executes successfully and returns exit code 0
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.cleanup_idempotency import cleanup_idempotency_keys, main


@pytest.mark.asyncio
async def test_cleanup_idempotency_keys_default_hours() -> None:
    """Asserts cleanup_idempotency_keys invokes repository cleanup_older_than with 24 hours."""
    mock_session = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with (
        patch("scripts.cleanup_idempotency.init_engine", new=AsyncMock()),
        patch("scripts.cleanup_idempotency._get_session_factory", return_value=mock_factory),
        patch("scripts.cleanup_idempotency.SqlAlchemyIdempotencyRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.cleanup_older_than.return_value = 5
        mock_repo_cls.return_value = mock_repo

        deleted = await cleanup_idempotency_keys(hours=24)

        assert deleted == 5
        mock_repo.cleanup_older_than.assert_called_once_with(hours=24)
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_idempotency_keys_custom_hours() -> None:
    """Asserts cleanup_idempotency_keys passes custom hours argument."""
    mock_session = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with (
        patch("scripts.cleanup_idempotency.init_engine", new=AsyncMock()),
        patch("scripts.cleanup_idempotency._get_session_factory", return_value=mock_factory),
        patch("scripts.cleanup_idempotency.SqlAlchemyIdempotencyRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.cleanup_older_than.return_value = 12
        mock_repo_cls.return_value = mock_repo

        deleted = await cleanup_idempotency_keys(hours=48)

        assert deleted == 12
        mock_repo.cleanup_older_than.assert_called_once_with(hours=48)


def test_main_cli_success(capsys: pytest.CaptureFixture[str]) -> None:
    """Asserts CLI main returns 0 and prints success output."""
    with patch(
        "scripts.cleanup_idempotency.cleanup_idempotency_keys",
        new=AsyncMock(return_value=3),
    ) as mock_cleanup:
        exit_code = main(["--hours", "48"])
        assert exit_code == 0
        mock_cleanup.assert_called_once_with(hours=48)
        captured = capsys.readouterr()
        assert "Successfully cleaned up 3 idempotency key(s)" in captured.out
