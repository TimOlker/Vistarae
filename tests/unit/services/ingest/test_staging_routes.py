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

"""Contract and unit tests for Phase 1 staging endpoints (T-025).

Verifies OpenAPI contracts for:
- GET /api/ingest/jobs/{job_id}/candidates
- PATCH /api/ingest/jobs/{job_id}/candidates/{candidate_id}
- POST /api/ingest/jobs/{job_id}/phase1/proceed
- POST /api/ingest/jobs/{job_id}/phase1/cancel
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import IngestCandidate, POI, User
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
    WGS84Point,
)

from services.ingest.dependencies import (
    get_current_user,
    get_poi_repo,
    get_staging_service,
)
from services.ingest.main import app


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        cognito_sub="sub-test-1234",
        email="traveler@example.com",
    )


@pytest.fixture
def mock_staging_service() -> MagicMock:
    svc = MagicMock()
    svc.list_candidates = AsyncMock(return_value=[])
    svc.get_candidate = AsyncMock(return_value=None)
    svc.update_candidate = AsyncMock()
    svc.advance_to_phase2 = AsyncMock(return_value=(2, 1))
    svc.cancel_staging = AsyncMock(return_value=3)
    svc.commit_job = AsyncMock(return_value=(2, [uuid.uuid4()], [uuid.uuid4()]))
    return svc


@pytest.fixture
def mock_poi_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_get_job_candidates(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    parent_id = uuid.uuid4()

    parent_poi = POI(
        id=parent_id,
        user_id=mock_user.id,
        name="Oaxaca City",
        geom=WGS84Point(lon=-96.72, lat=17.06),
    )
    mock_poi_repo.get_by_id.return_value = parent_poi

    cand = IngestCandidate(
        id=candidate_id,
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Monte Alban",
        recommended_disposition=IngestDisposition.SUBLOCATION,
        user_disposition=None,
        matched_existing_poi_id=None,
        parent_poi_id=parent_id,
        latitude=Decimal("17.0438"),
        longitude=Decimal("-96.7680"),
        photo_directory="Trip To Mexico/Monte Alban",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
    )
    mock_staging_service.list_candidates.return_value = [cand]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/ingest/jobs/{job_id}/candidates")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["total_candidates"] == 1
    assert data["candidates"][0]["poi_name"] == "Monte Alban"
    assert data["candidates"][0]["parent_poi_name"] == "Oaxaca City"
    assert data["candidates"][0]["recommended_disposition"] == "sublocation"


@pytest.mark.asyncio
async def test_update_candidate(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    updated_cand = IngestCandidate(
        id=candidate_id,
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Updated Name",
        recommended_disposition=IngestDisposition.IGNORE,
        user_disposition=IngestDisposition.ACCEPT,
        photo_directory="dir",
        latitude=Decimal("35.0"),
        longitude=Decimal("139.0"),
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
    )
    mock_staging_service.update_candidate.return_value = updated_cand

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/api/ingest/jobs/{job_id}/candidates/{candidate_id}",
            json={
                "poi_name": "Updated Name",
                "user_disposition": "accept",
                "latitude": 35.0,
                "longitude": 139.0,
            },
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["poi_name"] == "Updated Name"
    assert data["user_disposition"] == "accept"
    assert data["latitude"] == 35.0


@pytest.mark.asyncio
async def test_proceed_phase1(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    mock_staging_service.advance_to_phase2.return_value = (4, 1)

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase1/proceed")

    app.dependency_overrides.clear()

    assert resp.status_code == 202
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["advanced_count"] == 4
    assert data["ignored_count"] == 1


@pytest.mark.asyncio
async def test_cancel_phase1(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    mock_staging_service.cancel_staging.return_value = 5

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase1/cancel")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["purged_count"] == 5

