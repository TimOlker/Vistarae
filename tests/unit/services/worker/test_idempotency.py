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

"""Unit tests for synthetic record-level idempotency hashing (T-020).

Verifies:
- Deterministic 64-character SHA-256 synthetic key generation
- Key sensitivity to user_id, job_id, and absolute_row_number
- First insertion claims row (returns True)
- Subsequent duplicate insertion skips row (returns False)
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.worker.idempotency import (
    claim_row_idempotency,
    compute_synthetic_idempotency_key,
)


class TestSyntheticIdempotency:
    """Verifies SHA-256 key computation and uniqueness."""

    def test_key_determinism_and_length(self) -> None:
        """Asserts key is 64 hex characters and deterministic."""
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        row_num = 42

        key1 = compute_synthetic_idempotency_key(user_id, job_id, row_num)
        key2 = compute_synthetic_idempotency_key(user_id, job_id, row_num)

        assert len(key1) == 64
        assert key1 == key2
        # Verify manual hash matches
        expected = hashlib.sha256(f"{user_id}:{job_id}:{row_num}".encode()).hexdigest()
        assert key1 == expected

    def test_key_differentiation(self) -> None:
        """Asserts differing row numbers or users yield different keys."""
        user1 = uuid.uuid4()
        user2 = uuid.uuid4()
        job_id = uuid.uuid4()

        k_row1 = compute_synthetic_idempotency_key(user1, job_id, 1)
        k_row2 = compute_synthetic_idempotency_key(user1, job_id, 2)
        k_user2 = compute_synthetic_idempotency_key(user2, job_id, 1)

        assert k_row1 != k_row2
        assert k_row1 != k_user2

    @pytest.mark.asyncio
    async def test_claim_row_first_time_succeeds(self) -> None:
        """Asserts claim_row_idempotency returns True when row is inserted."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = uuid.uuid4()
        mock_session.execute.return_value = mock_result

        claimed = await claim_row_idempotency(
            session=mock_session,
            user_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            absolute_row_number=5,
        )
        assert claimed is True
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_claim_row_duplicate_returns_false(self) -> None:
        """Asserts claim_row_idempotency returns False on conflict DO NOTHING (0 rows returned)."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        claimed = await claim_row_idempotency(
            session=mock_session,
            user_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            absolute_row_number=5,
        )
        assert claimed is False
