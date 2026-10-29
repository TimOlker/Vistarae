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

"""Contract and unit tests for Phase 2 review endpoints (T-031).

Verifies OpenAPI contracts for:
- POST /api/ingest/jobs/{job_id}/phase2/commit
- POST /api/ingest/jobs/{job_id}/phase2/cancel
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import User

from services.ingest.dependencies import get_current_user, get_staging_service
from services.ingest.main import app


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-test-5678",
        email="traveler@example.com",
    )


@pytest.fixture
def mock_staging_service() -> MagicMock:
    svc = MagicMock()
    svc.commit_job = AsyncMock(return_value=(3, [uuid.uuid4(), uuid.uuid4()], [uuid.uuid4()]))
    svc.cancel_staging = AsyncMock(return_value=3)
    return svc


@pytest.mark.asyncio
async def test_commit_phase2(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    job_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase2/commit")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["committed_count"] == 3
    assert len(data["created_pois"]) == 2
    assert len(data["merged_pois"]) == 1
    mock_staging_service.commit_job.assert_awaited_once_with(mock_user.id, job_id)


@pytest.mark.asyncio
async def test_cancel_phase2(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    job_id = uuid.uuid4()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase2/cancel")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["purged_count"] == 3
    mock_staging_service.cancel_staging.assert_awaited_once_with(mock_user.id, job_id)

