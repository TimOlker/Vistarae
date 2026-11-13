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

"""Unit tests for streaming export routes and zero-selection abort gates."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import User
from vistarae_core.schemas.poi_exchange import POIExchangeRecord

from services.ingest.dependencies import get_current_user, get_staging_service
from services.ingest.main import app
from services.ingest.routes.export import get_export_service


@pytest.fixture
def mock_user() -> User:
    """Mock authenticated user."""
    return User(
        id=uuid4(),
        cognito_sub="sub-test-export-user",
        email="traveler@example.com",
    )


@pytest.fixture(autouse=True)
def override_auth_and_services(mock_user: User):
    """Override get_current_user, export_service, and staging_service across tests."""
    mock_export_svc = AsyncMock()
    mock_staging_svc = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_export_service] = lambda: mock_export_svc
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_svc
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_pois_empty_ids_returns_400():
    """Asserts that calling export with 0 selected POI IDs aborts with 400 Bad Request."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"poi_ids": [], "format": "csv"}
        res = await client.post("/api/v1/export/pois", json=payload)
        assert res.status_code == 400
        data = res.json()
        assert "No records selected" in data.get("detail", "") or "min_length" in str(data)


@pytest.mark.asyncio
async def test_export_phase1_candidates_empty_ids_returns_400():
    """Asserts that Phase 1 export aborts with 400 when candidate_ids is empty."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"job_id": str(uuid4()), "candidate_ids": [], "format": "csv"}
        res = await client.post("/api/v1/export/candidates/phase1", json=payload)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_phase2_candidates_empty_ids_returns_400():
    """Asserts that Phase 2 export aborts with 400 when candidate_ids is empty."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"job_id": str(uuid4()), "candidate_ids": [], "format": "json"}
        res = await client.post("/api/v1/export/candidates/phase2", json=payload)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_pois_valid_selection_streams_csv(mock_user: User):
    """Asserts that valid POI selection streams CSV starting with UTF-8 BOM."""
    poi_id = uuid4()
    mock_record = POIExchangeRecord(
        poi_id=poi_id,
        poi_name="Golden Gate Bridge",
        latitude=37.8199,
        longitude=-122.4783,
        city="San Francisco",
        state_province="CA",
        country="USA",
        tags=["Bridge", "Iconic"],
    )

    from services.ingest.routes.export import get_export_service

    mock_service = AsyncMock()
    mock_service.get_pois_for_export.return_value = [mock_record]
    app.dependency_overrides[get_export_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"poi_ids": [str(poi_id)], "format": "csv"}
            res = await client.post("/api/v1/export/pois", json=payload)
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/csv")
            assert "attachment; filename=" in res.headers["content-disposition"]
            body_bytes = res.content
            assert body_bytes.startswith(b"\xef\xbb\xbf")
            assert b"Golden Gate Bridge" in body_bytes
    finally:
        app.dependency_overrides.pop(get_export_service, None)


@pytest.mark.asyncio
async def test_export_phase1_candidates_streams_json(mock_user: User):
    """Asserts that Phase 1 candidates stream valid JSON."""
    cand_id = uuid4()
    job_id = uuid4()
    mock_record = POIExchangeRecord(
        poi_name="Kiyomizu-dera",
        latitude=34.9948,
        longitude=135.7850,
        city="Kyoto",
        country="Japan",
        tags=["Temple", "Historic"],
    )

    from services.ingest.routes.export import get_export_service

    mock_service = AsyncMock()
    mock_service.get_candidates_for_export.return_value = [mock_record]
    app.dependency_overrides[get_export_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"job_id": str(job_id), "candidate_ids": [str(cand_id)], "format": "json"}
            res = await client.post("/api/v1/export/candidates/phase1", json=payload)
            assert res.status_code == 200
            assert "application/json" in res.headers["content-type"]
            data = res.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["poi_name"] == "Kiyomizu-dera"
    finally:
        app.dependency_overrides.pop(get_export_service, None)


@pytest.mark.asyncio
async def test_export_phase2_candidates_streams_yaml(mock_user: User):
    """Asserts that Phase 2 candidates stream valid YAML."""
    cand_id = uuid4()
    job_id = uuid4()
    mock_record = POIExchangeRecord(
        poi_name="Matterhorn",
        latitude=45.9765,
        longitude=7.6585,
        city="Zermatt",
        country="Switzerland",
        tags=["Mountain", "Alpine"],
    )

    from services.ingest.routes.export import get_export_service

    mock_service = AsyncMock()
    mock_service.get_candidates_for_export.return_value = [mock_record]
    app.dependency_overrides[get_export_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"job_id": str(job_id), "candidate_ids": [str(cand_id)], "format": "yaml"}
            res = await client.post("/api/v1/export/candidates/phase2", json=payload)
            assert res.status_code == 200
            assert "application/x-yaml" in res.headers["content-type"]
            body_text = res.text
            assert "poi_name: Matterhorn" in body_text
    finally:
        app.dependency_overrides.pop(get_export_service, None)


@pytest.mark.asyncio
async def test_get_job_candidates_export_streams_full_fidelity_csv(mock_user: User):
    """Asserts that GET /api/ingest/jobs/{job_id}/candidates/export streams RFC 4180 CSV with UTF-8 BOM."""
    job_id = uuid4()
    cand1_id = uuid4()
    cand2_id = uuid4()

    from tests.fixtures.export_fixtures import get_sample_staged_candidates
    from services.ingest.dependencies import get_staging_service
    from vistarae_core.schemas.export_schema import UTF8_BOM_BYTES

    sample_candidates = get_sample_staged_candidates()

    mock_staging_service = AsyncMock()
    mock_staging_service.list_candidates.return_value = sample_candidates
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(f"/api/ingest/jobs/{job_id}/candidates/export")
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("text/csv")
            assert f"vistarae_staging_{job_id}" in res.headers["content-disposition"]
            body_bytes = res.content
            assert body_bytes.startswith(b"\xef\xbb\xbf")

            text = body_bytes.decode("utf-8")
            lines = text.replace("\ufeff", "").split("\r\n")
            header_cols = lines[0].split(",")
            assert len(header_cols) == 37
            assert header_cols[0] == "Candidate ID"
            assert header_cols[2] == "POI Name"
            assert "Yellowstone National Park" in text
            assert "'=Grand Prismatic Spring" in text
    finally:
        app.dependency_overrides.pop(get_staging_service, None)


@pytest.mark.asyncio
async def test_get_job_candidates_export_empty_returns_404(mock_user: User):
    """Asserts that exporting a job with 0 staged candidates returns 404 Not Found."""
    job_id = uuid4()
    from services.ingest.dependencies import get_staging_service

    mock_staging_service = AsyncMock()
    mock_staging_service.list_candidates.return_value = []
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(f"/api/ingest/jobs/{job_id}/candidates/export")
            assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_staging_service, None)
