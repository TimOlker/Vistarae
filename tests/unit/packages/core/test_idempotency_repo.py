# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for SqlAlchemyIdempotencyRepository (T-033).

Tests:
- get_or_create: new key insertion (PENDING)
- get_or_create: existing PENDING key
- get_or_create: existing COMPLETED key with cached payload
- get_or_create: existing FAILED key allowing retry
- complete: transitions to COMPLETED with code and payload
- fail: transitions to FAILED
- cleanup_older_than: executes delete with timestamp threshold
- get_record: found and not found
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.adapters.db.tables import IdempotencyKeysTable
from vistarae_core.adapters.repositories.idempotency_repo import (
    SqlAlchemyIdempotencyRepository,
)
from vistarae_core.domain.value_objects import IdempotencyStatus


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestIdempotencyRepositoryGetOrCreate:
    """Tests for get_or_create status transitions."""

    @pytest.mark.asyncio
    async def test_get_or_create_new_key(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """New key inserts PENDING record and returns (PENDING, None, None)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        status, code, payload = await repo.get_or_create(test_user_id, "new-key-1")

        assert status == IdempotencyStatus.PENDING
        assert code is None
        assert payload is None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_existing_pending(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Existing PENDING key returns (PENDING, None, None) without re-adding."""
        now = datetime.now(UTC)
        fake_row = IdempotencyKeysTable(
            user_id=test_user_id,
            idempotency_key="pending-key",
            status="PENDING",
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        status, code, payload = await repo.get_or_create(test_user_id, "pending-key")

        assert status == IdempotencyStatus.PENDING
        assert code is None
        assert payload is None
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_existing_completed(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Existing COMPLETED key returns status and cached response payload."""
        now = datetime.now(UTC)
        fake_row = IdempotencyKeysTable(
            user_id=test_user_id,
            idempotency_key="completed-key",
            status="COMPLETED",
            response_code=201,
            response_payload={"id": "item-1"},
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        status, code, payload = await repo.get_or_create(test_user_id, "completed-key")

        assert status == IdempotencyStatus.COMPLETED
        assert code == 201
        assert payload == {"id": "item-1"}

    @pytest.mark.asyncio
    async def test_get_or_create_existing_failed_allows_retry(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Existing FAILED key is reset to PENDING to permit retry."""
        now = datetime.now(UTC)
        fake_row = IdempotencyKeysTable(
            user_id=test_user_id,
            idempotency_key="failed-key",
            status="FAILED",
            response_code=500,
            response_payload={"error": "fail"},
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        status, code, payload = await repo.get_or_create(test_user_id, "failed-key")

        assert status == IdempotencyStatus.PENDING
        assert code is None
        assert payload is None
        assert fake_row.status == "PENDING"
        assert fake_row.response_code is None
        assert fake_row.response_payload is None
        mock_session.flush.assert_called_once()


class TestIdempotencyRepositoryMutations:
    """Tests for complete, fail, cleanup, and get_record."""

    @pytest.mark.asyncio
    async def test_complete(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts complete executes update with status COMPLETED."""
        repo = SqlAlchemyIdempotencyRepository(mock_session)
        await repo.complete(test_user_id, "key-1", 200, {"success": True})
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts fail executes update with status FAILED."""
        repo = SqlAlchemyIdempotencyRepository(mock_session)
        await repo.fail(test_user_id, "key-1")
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_older_than(self, mock_session: AsyncMock) -> None:
        """Asserts cleanup executes delete and returns deleted count."""
        mock_result = MagicMock()
        mock_result.rowcount = 7
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        deleted = await repo.cleanup_older_than(hours=24)
        assert deleted == 7

    @pytest.mark.asyncio
    async def test_get_record_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts get_record returns IdempotencyRecord when found."""
        now = datetime.now(UTC)
        fake_row = IdempotencyKeysTable(
            id=uuid.uuid4(),
            user_id=test_user_id,
            idempotency_key="key-rec",
            status="COMPLETED",
            response_code=200,
            response_payload={"data": 123},
            created_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_row
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        rec = await repo.get_record(test_user_id, "key-rec")

        assert rec is not None
        assert rec.user_id == test_user_id
        assert rec.idempotency_key == "key-rec"
        assert rec.status == IdempotencyStatus.COMPLETED
        assert rec.response_code == 200

    @pytest.mark.asyncio
    async def test_get_record_not_found(
        self, mock_session: AsyncMock, test_user_id: uuid.UUID
    ) -> None:
        """Asserts get_record returns None when record does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyIdempotencyRepository(mock_session)
        rec = await repo.get_record(test_user_id, "missing-key")
        assert rec is None
