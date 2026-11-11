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
from vistarae_core.domain.entities import POI, IngestCandidate, User
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
    svc.enrich_candidates_phase2 = AsyncMock()
    svc.cancel_staging = AsyncMock(return_value=3)
    svc.commit_job = AsyncMock(return_value=(2, [uuid.uuid4()], [uuid.uuid4()]))
    from vistarae_core.schemas.ingest_staging import ActiveSessionResponse

    svc.get_active_session = AsyncMock(return_value=ActiveSessionResponse(has_active_session=False))
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase1/cancel")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["purged_count"] == 5


@pytest.mark.asyncio
async def test_enrich_phase2(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    cand = IngestCandidate(
        id=candidate_id,
        user_id=mock_user.id,
        job_id=job_id,
        row_index=1,
        poi_name="Bibury Trout Farm",
        description=None,
    )
    mock_staging_service.list_candidates = AsyncMock(return_value=[cand])

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/ingest/jobs/{job_id}/phase2/enrich")

    app.dependency_overrides.clear()

    assert resp.status_code == 202
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["advanced_count"] == 1


@pytest.mark.asyncio
async def test_get_phase2_progress(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    from vistarae_core.schemas.ingest_staging import Phase2ProgressResponse

    job_id = uuid.uuid4()
    mock_staging_service.get_phase2_progress.return_value = Phase2ProgressResponse(
        job_id=job_id,
        total_count=1,
        enriched_count=1,
        is_complete=True,
        percent_complete=100,
        status_message="Done",
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/ingest/jobs/{job_id}/phase2/progress")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["percent_complete"] == 100
    assert data["is_complete"] is True


@pytest.mark.asyncio
async def test_get_job_candidates_with_filters(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    c1 = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Kyoto Temple",
        recommended_disposition=IngestDisposition.ACCEPT,
        hero_image_url="https://example.com/kyoto.jpg",
        latitude=Decimal("35.0"),
        longitude=Decimal("135.0"),
        street_address="123 Temple Way",
        official_url="https://kyoto.org",
        no_websites=False,
    )
    c2 = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=1,
        poi_name="Tokyo Shrine",
        recommended_disposition=IngestDisposition.ACCEPT,
        hero_image_url=None,  # missing photo => incomplete
        latitude=Decimal("35.6"),
        longitude=Decimal("139.7"),
        street_address="456 Shrine St",
        official_url=None,
        no_websites=False,
    )
    mock_staging_service.list_candidates.return_value = [c1, c2]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Filter by search
        resp = await client.get(f"/api/ingest/jobs/{job_id}/candidates?search=Kyoto")
        assert resp.status_code == 200
        assert resp.json()["total_candidates"] == 1
        assert resp.json()["candidates"][0]["poi_name"] == "Kyoto Temple"

        # Filter by completeness: incomplete
        resp_comp = await client.get(
            f"/api/ingest/jobs/{job_id}/candidates?completeness=incomplete"
        )
        assert resp_comp.status_code == 200
        assert resp_comp.json()["total_candidates"] == 1
        assert resp_comp.json()["candidates"][0]["poi_name"] == "Tokyo Shrine"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_put_candidate_workbench_fields(
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
        poi_name="Updated Candidate",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=IngestDisposition.ACCEPT,
        no_websites=True,
        disposition_justification="Verified no site",
        is_user_overridden=True,
    )
    mock_staging_service.update_candidate.return_value = updated_cand

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put(
            f"/api/ingest/jobs/{job_id}/candidates/{candidate_id}",
            json={
                "poi_name": "Updated Candidate",
                "no_websites": True,
                "disposition_justification": "Verified no site",
                "is_user_overridden": True,
            },
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["poi_name"] == "Updated Candidate"
    assert data["no_websites"] is True
    assert data["is_user_overridden"] is True
    assert data["disposition_justification"] == "Verified no site"


@pytest.mark.asyncio
async def test_upload_active_session_guard_returns_409(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    from vistarae_core.schemas.ingest_staging import ActiveSessionResponse

    active_job_id = uuid.uuid4()
    mock_staging_service.get_active_session = AsyncMock(
        return_value=ActiveSessionResponse(
            has_active_session=True,
            job_id=active_job_id,
            total_candidates=10,
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ingest/upload",
            files={"file": ("test.csv", b"poi_name\nTest POI\n", "text/csv")},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 409
    assert resp.headers["content-type"] == "application/problem+json"
    data = resp.json()
    assert data["status"] == 409
    assert data["title"] == "Active Staging Session Exists"
    assert data["job_id"] == str(active_job_id)


@pytest.mark.asyncio
async def test_upload_staging_failure_rolls_back_and_returns_500(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    """Verifies that an unhandled exception in stage_records rolls back and returns 500 error."""
    from unittest.mock import AsyncMock

    from vistarae_core.adapters.db.session import get_db_session
    from vistarae_core.schemas.ingest_staging import ActiveSessionResponse

    mock_staging_service.get_active_session = AsyncMock(
        return_value=ActiveSessionResponse(has_active_session=False)
    )
    mock_staging_service.wipe_active_session = AsyncMock(
        side_effect=RuntimeError("Database constraint error: ck_ingest_candidates_recommended_disp")
    )
    mock_staging_service.stage_records = AsyncMock(
        side_effect=RuntimeError("Database constraint error: ck_ingest_candidates_recommended_disp")
    )

    mock_session = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.create_job = AsyncMock(
        return_value=MagicMock(id=uuid.uuid4(), total_rows=1, processed_rows=0, job_status=MagicMock(value="pending"))
    )

    from services.ingest.dependencies import get_ingest_repo

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_ingest_repo] = lambda: mock_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ingest/upload",
            files={"file": ("test.csv", b"poi_name\nTest POI\n", "text/csv")},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 500
    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
    data = resp.json()
    assert data["title"] == "Ingest Staging Failed"
    assert "Database constraint error" in data["detail"]


@pytest.mark.asyncio
async def test_upload_commits_session_on_success(
    mock_user: User,
    mock_staging_service: MagicMock,
) -> None:
    """Verifies that session.commit() is explicitly awaited before returning success."""
    from unittest.mock import AsyncMock

    from vistarae_core.adapters.db.session import get_db_session
    from vistarae_core.domain.value_objects import IngestDisposition
    from vistarae_core.schemas.ingest_staging import ActiveSessionResponse

    mock_staging_service.get_active_session = AsyncMock(
        return_value=ActiveSessionResponse(has_active_session=False)
    )
    mock_staging_service.wipe_active_session = AsyncMock()
    candidate_mock = MagicMock(
        id=uuid.uuid4(),
        row_index=0,
        poi_name="Petra",
        recommended_disposition=IngestDisposition.EXISTING,
        street_address=None,
        city=None,
        latitude=None,
        longitude=None,
    )
    mock_staging_service.stage_records = AsyncMock(return_value=[candidate_mock])

    mock_session = AsyncMock()
    job_id = uuid.uuid4()
    mock_repo = AsyncMock()
    job_mock = MagicMock(
        id=job_id,
        total_rows=1,
        processed_rows=0,
        duplicate_payloads=[],
        job_status=MagicMock(value="completed"),
    )
    mock_repo.create_job = AsyncMock(return_value=job_mock)

    from services.ingest.dependencies import get_ingest_repo

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_ingest_repo] = lambda: mock_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ingest/upload",
            files={"file": ("test.csv", b"poi_name\nPetra\n", "text/csv")},
        )

    app.dependency_overrides.clear()

    assert resp.status_code in (200, 202)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_job_candidates_multi_disposition_filter(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    c1 = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Candidate Accept",
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=None,
    )
    c2 = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=1,
        poi_name="Candidate Update",
        recommended_disposition=IngestDisposition.UPDATE_EXISTING,
        user_disposition=None,
    )
    c3 = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=2,
        poi_name="Candidate Ignore",
        recommended_disposition=IngestDisposition.IGNORE,
        user_disposition=None,
    )
    mock_staging_service.list_candidates.return_value = [c1, c2, c3]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Multi-select: accept and update_existing
        resp = await client.get(f"/api/ingest/jobs/{job_id}/candidates?disposition=accept,update_existing")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) == 2
        names = {c["poi_name"] for c in data["candidates"]}
        assert names == {"Candidate Accept", "Candidate Update"}

        # None selected: disposition=none
        resp_none = await client.get(f"/api/ingest/jobs/{job_id}/candidates?disposition=none")
        assert resp_none.status_code == 200
        assert len(resp_none.json()["candidates"]) == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_job_candidates_completeness_filter(
    mock_user: User,
    mock_staging_service: MagicMock,
    mock_poi_repo: MagicMock,
) -> None:
    job_id = uuid.uuid4()
    c_complete = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=0,
        poi_name="Complete POI",
        recommended_disposition=IngestDisposition.ACCEPT,
        hero_image_url="https://example.com/photo.jpg",
        latitude=Decimal("48.8584"),
        longitude=Decimal("2.2945"),
        street_address="Champ de Mars, 5 Av. Anatole France",
        official_url="https://toureiffel.paris",
    )
    c_incomplete = IngestCandidate(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        job_id=job_id,
        row_index=1,
        poi_name="Incomplete POI",
        recommended_disposition=IngestDisposition.ACCEPT,
        hero_image_url=None,
        latitude=Decimal("48.8584"),
        longitude=Decimal("2.2945"),
        street_address="Somewhere",
    )
    mock_staging_service.list_candidates.return_value = [c_complete, c_incomplete]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Completed Only
        resp = await client.get(f"/api/ingest/jobs/{job_id}/candidates?completeness=complete")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["poi_name"] == "Complete POI"

        # Incomplete Only
        resp_inc = await client.get(f"/api/ingest/jobs/{job_id}/candidates?completeness=incomplete")
        assert resp_inc.status_code == 200
        data_inc = resp_inc.json()
        assert len(data_inc["candidates"]) == 1
        assert data_inc["candidates"][0]["poi_name"] == "Incomplete POI"

    app.dependency_overrides.clear()

