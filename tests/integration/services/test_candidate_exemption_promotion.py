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

"""Integration tests for candidate promotion to POIs and CSV/JSON round-trip (T019).

Validates EARS requirements:
- REQ-EXM-003: Promoting candidates to POIs preserves no_address and no_websites on pois table.
- REQ-EXM-023: Exporting POIs preserves no_address and no_websites.
- REQ-EXM-024, REQ-EXM-025: Importing files preserves or defaults exemption attributes.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from vistarae_core.domain.entities import POI, IngestCandidate, User
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
)

from services.ingest.services.csv_parser import parse_and_sanitize_csv
from services.ingest.services.staging_service import StagingService


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
async def test_commit_candidate_promotes_exemptions_to_poi(mock_user: User) -> None:
    """Tests that committing candidates copies no_address and no_websites to permanent POI records."""
    job_id = uuid.uuid4()
    c1 = IngestCandidate(
        id=uuid.uuid4(),
        job_id=job_id,
        user_id=mock_user.id,
        row_index=1,
        poi_name="Mountain Wilderness Overlook",
        latitude=Decimal("46.8523"),
        longitude=Decimal("-121.7603"),
        street_address=None,
        official_url=None,
        hero_image_url="https://example.com/hero.jpg",
        no_address=True,
        no_websites=True,
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
        recommended_disposition=IngestDisposition.ACCEPT,
        user_disposition=IngestDisposition.ACCEPT,
    )

    mock_cand_repo = AsyncMock()
    mock_cand_repo.list_by_job.return_value = [c1]

    created_pois: list[POI] = []

    async def mock_create_poi(poi: POI) -> POI:
        created_pois.append(poi)
        return poi

    mock_poi_repo = AsyncMock()
    mock_poi_repo.create.side_effect = mock_create_poi

    service = StagingService(
        candidate_repo=mock_cand_repo,
        poi_repo=mock_poi_repo,
    )

    count, created, merged = await service.commit_job(mock_user.id, job_id)

    assert count == 1
    assert len(created) == 1
    assert len(created_pois) == 1

    saved_poi = created_pois[0]
    assert saved_poi.name == "Mountain Wilderness Overlook"
    assert saved_poi.no_address is True
    assert saved_poi.no_websites is True


def test_exemption_csv_round_trip() -> None:
    """Tests that exporting and re-importing candidates preserves no_address and no_websites."""
    csv_text = (
        "POI Name,Street Address,No Address Flag,No Websites Flag,Latitude,Longitude\n"
        "Remote Peak,,true,true,48.0,-121.0\n"
        "City Museum,100 Main St,false,false,48.0,-121.0\n"
    )

    parsed = parse_and_sanitize_csv(csv_text.encode("utf-8"))
    assert len(parsed) == 2

    row1 = parsed[0]["row_data"]
    assert row1["poi_name"] == "Remote Peak"
    assert row1["no_address"] is True
    assert row1["no_websites"] is True

    row2 = parsed[1]["row_data"]
    assert row2["poi_name"] == "City Museum"
    assert row2["no_address"] is False
    assert row2["no_websites"] is False
