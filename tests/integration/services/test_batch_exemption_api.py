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

"""Integration tests for batch candidate exemption API (T016).

Validates EARS requirements:
- REQ-EXM-016: Multi-row candidate selection in staging workbench.
- REQ-EXM-017: Batch marking candidates as no_address = true.
- REQ-EXM-018: Batch marking candidates as no_websites = true.
- REQ-EXM-019: Batch clearing candidate exemptions (no_address = false, no_websites = false).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import User

from services.ingest.dependencies import (
    get_current_user,
    get_staging_service,
)
from services.ingest.main import app


@pytest.fixture
def mock_user() -> User:
    """Provides a mock authenticated user fixture."""
    return User(
        id=uuid.uuid4(),
        cognito_sub="auth0|mock-user-123",
        email="traveler@vistarae.internal",
        full_name="Explorer Test",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_batch_mark_no_address(mock_user: User) -> None:
    """Tests batch setting no_address=True on multiple candidates."""
    job_id = uuid.uuid4()
    cids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    mock_staging = AsyncMock()
    mock_staging.batch_edit_candidates.return_value = 3

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/candidates/batch-edit",
                json={
                    "candidate_ids": [str(c) for c in cids],
                    "no_address": True,
                },
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["updated_count"] == 3

            mock_staging.batch_edit_candidates.assert_awaited_once()
            args = mock_staging.batch_edit_candidates.await_args[0]
            assert args[0] == mock_user.id
            assert args[1] == job_id
            req_body = args[2]
            assert req_body.no_address is True
            assert req_body.no_websites is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_batch_mark_no_websites(mock_user: User) -> None:
    """Tests batch setting no_websites=True on multiple candidates."""
    job_id = uuid.uuid4()
    cids = [uuid.uuid4(), uuid.uuid4()]

    mock_staging = AsyncMock()
    mock_staging.batch_edit_candidates.return_value = 2

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/candidates/batch-edit",
                json={
                    "candidate_ids": [str(c) for c in cids],
                    "no_websites": True,
                },
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["updated_count"] == 2

            mock_staging.batch_edit_candidates.assert_awaited_once()
            args = mock_staging.batch_edit_candidates.await_args[0]
            req_body = args[2]
            assert req_body.no_websites is True
            assert req_body.no_address is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_batch_clear_all_exemptions(mock_user: User) -> None:
    """Tests batch clearing both exemptions (no_address=False, no_websites=False)."""
    job_id = uuid.uuid4()
    cids = [uuid.uuid4(), uuid.uuid4()]

    mock_staging = AsyncMock()
    mock_staging.batch_edit_candidates.return_value = 2

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/ingest/jobs/{job_id}/candidates/batch-edit",
                json={
                    "candidate_ids": [str(c) for c in cids],
                    "no_address": False,
                    "no_websites": False,
                },
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["updated_count"] == 2

            mock_staging.batch_edit_candidates.assert_awaited_once()
            args = mock_staging.batch_edit_candidates.await_args[0]
            req_body = args[2]
            assert req_body.no_address is False
            assert req_body.no_websites is False
    finally:
        app.dependency_overrides.clear()
