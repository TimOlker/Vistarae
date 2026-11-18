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

"""Unit tests for candidate update endpoints with exemption flags (T012).

Validates EARS requirements:
- REQ-EXM-004: Exemptions are set strictly through explicit user update action.
- REQ-EXM-005: Patching candidates persists no_address and no_websites.
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
    poi_name: str = "Trailhead Vista",
    no_address: bool = False,
    no_websites: bool = False,
) -> IngestCandidate:
    """Helper to build IngestCandidate domain entity."""
    return IngestCandidate(
        id=cand_id,
        job_id=job_id,
        user_id=user_id,
        row_index=1,
        poi_name=poi_name,
        latitude=Decimal("45.1234"),
        longitude=Decimal("-121.5678"),
        street_address=None,
        official_url=None,
        hero_image_url="https://example.com/hero.jpg",
        no_address=no_address,
        no_websites=no_websites,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
        recommended_disposition=IngestDisposition.ACCEPT,
        confidence_score=90,
    )


@pytest.mark.asyncio
async def test_patch_candidate_exemptions(mock_user: User) -> None:
    """Tests updating a candidate with no_address=True and no_websites=True via PATCH."""
    job_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    updated_cand = _make_candidate(cand_id, job_id, mock_user.id, no_address=True, no_websites=True)

    mock_staging = AsyncMock()
    mock_staging.update_candidate.return_value = updated_cand
    mock_poi_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_staging_service] = lambda: mock_staging
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/api/ingest/jobs/{job_id}/candidates/{cand_id}",
                json={"no_address": True, "no_websites": True},
                headers={"X-Mock-User-Id": str(mock_user.id)},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(cand_id)
            assert data["no_address"] is True
            assert data["no_websites"] is True

            mock_staging.update_candidate.assert_awaited_once()
            call_args = mock_staging.update_candidate.await_args
            assert call_args[0][0] == mock_user.id
            assert call_args[0][1] == cand_id
            update_req = call_args[0][2]
            assert update_req.no_address is True
            assert update_req.no_websites is True
    finally:
        app.dependency_overrides.clear()
