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

"""Unit tests for completeness evaluation and exemption satisfaction rules (T007).

Validates EARS requirements:
- REQ-EXM-006: Street address criterion satisfied when no_address = true.
- REQ-EXM-007: Websites criterion satisfied when no_websites = true.
- REQ-EXM-008: Overall candidate completeness evaluation with exemptions.
- REQ-EXM-013, REQ-EXM-014, REQ-EXM-015: Staging API completeness filters (complete, incomplete, needs_action, exempted).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import IngestCandidate, User
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
)

from services.ingest.dependencies import (
    get_current_user,
    get_poi_repo,
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


def _make_candidate(
    cand_id: uuid.UUID,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    poi_name: str = "Test Overlook",
    hero_image_url: str | None = "https://example.com/hero.jpg",
    latitude: float | None = 45.0,
    longitude: float | None = -120.0,
    street_address: str | None = None,
    official_url: str | None = None,
    related_websites: list[dict] | None = None,
    no_address: bool = False,
    no_websites: bool = False,
) -> IngestCandidate:
    """Helper to build IngestCandidate domain entities."""
    return IngestCandidate(
        id=cand_id,
        job_id=job_id,
        user_id=user_id,
        row_index=1,
        poi_name=poi_name,
        latitude=Decimal(str(latitude)) if latitude is not None else None,
        longitude=Decimal(str(longitude)) if longitude is not None else None,
        street_address=street_address,
        official_url=official_url,
        related_websites=related_websites or [],
        hero_image_url=hero_image_url,
        no_address=no_address,
        no_websites=no_websites,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
        recommended_disposition=IngestDisposition.ACCEPT,
        confidence_score=90,
    )


@pytest.mark.asyncio
async def test_completeness_filter_complete_with_exemptions(mock_user: User) -> None:
    """Tests that candidate with no_address=True and no_websites=True is returned as complete."""
    job_id = uuid.uuid4()
    c1 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Wilderness Peak",
        hero_image_url="https://example.com/peak.jpg",
        latitude=46.85,
        longitude=-121.76,
        street_address=None,
        official_url=None,
        no_address=True,
        no_websites=True,
    )
    c2 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Unfinished Overlook",
        hero_image_url="https://example.com/overlook.jpg",
        latitude=46.85,
        longitude=-121.76,
        street_address=None,
        official_url=None,
        no_address=False,
        no_websites=False,
    )

    mock_staging = AsyncMock()
    mock_staging.list_candidates.return_value = [c1, c2]
    mock_poi_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/ingest/jobs/{job_id}/candidates",
                params={"completeness": "complete"},
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_candidates"] == 1
            assert data["candidates"][0]["poi_name"] == "Wilderness Peak"
            assert data["candidates"][0]["no_address"] is True
            assert data["candidates"][0]["no_websites"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_completeness_filter_incomplete_excludes_fully_exempted(mock_user: User) -> None:
    """Tests that candidate with all missing fields exempted is NOT returned in incomplete filter."""
    job_id = uuid.uuid4()
    c1 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Wilderness Peak",
        hero_image_url="https://example.com/peak.jpg",
        latitude=46.85,
        longitude=-121.76,
        street_address=None,
        official_url=None,
        no_address=True,
        no_websites=True,
    )
    c2 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Unfinished Overlook",
        hero_image_url="https://example.com/overlook.jpg",
        latitude=46.85,
        longitude=-121.76,
        street_address=None,
        official_url=None,
        no_address=False,
        no_websites=False,
    )

    mock_staging = AsyncMock()
    mock_staging.list_candidates.return_value = [c1, c2]
    mock_poi_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/ingest/jobs/{job_id}/candidates",
                params={"completeness": "incomplete"},
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_candidates"] == 1
            assert data["candidates"][0]["poi_name"] == "Unfinished Overlook"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_completeness_filter_needs_action(mock_user: User) -> None:
    """Tests that 'needs_action' filter returns only records with unexempted missing fields."""
    job_id = uuid.uuid4()
    c_complete = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Fully Specified POI",
        hero_image_url="https://example.com/full.jpg",
        latitude=45.0,
        longitude=-120.0,
        street_address="123 Main St",
        official_url="https://example.com",
    )
    c_exempted = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Exempted Trailhead",
        hero_image_url="https://example.com/trail.jpg",
        latitude=45.0,
        longitude=-120.0,
        street_address=None,
        official_url=None,
        no_address=True,
        no_websites=True,
    )
    c_action = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Needs Address POI",
        hero_image_url="https://example.com/action.jpg",
        latitude=45.0,
        longitude=-120.0,
        street_address=None,
        official_url="https://example.com",
        no_address=False,
    )

    mock_staging = AsyncMock()
    mock_staging.list_candidates.return_value = [c_complete, c_exempted, c_action]
    mock_poi_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/ingest/jobs/{job_id}/candidates",
                params={"completeness": "needs_action"},
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_candidates"] == 1
            assert data["candidates"][0]["poi_name"] == "Needs Address POI"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_completeness_filter_exempted(mock_user: User) -> None:
    """Tests that 'exempted' filter returns any candidate with no_address or no_websites set."""
    job_id = uuid.uuid4()
    c1 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Exempted Address Only",
        no_address=True,
        no_websites=False,
    )
    c2 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="Exempted Websites Only",
        no_address=False,
        no_websites=True,
    )
    c3 = _make_candidate(
        uuid.uuid4(),
        job_id,
        mock_user.id,
        poi_name="No Exemptions",
        no_address=False,
        no_websites=False,
    )

    mock_staging = AsyncMock()
    mock_staging.list_candidates.return_value = [c1, c2, c3]
    mock_poi_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/ingest/jobs/{job_id}/candidates",
                params={"completeness": "exempted"},
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_candidates"] == 2
            names = [c["poi_name"] for c in data["candidates"]]
            assert "Exempted Address Only" in names
            assert "Exempted Websites Only" in names
            assert "No Exemptions" not in names
    finally:
        app.dependency_overrides.clear()
