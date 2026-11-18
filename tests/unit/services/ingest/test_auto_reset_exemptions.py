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

"""Unit tests for automatic exemption reset when non-empty data is entered (T026).

Validates EARS requirements:
- REQ-EXM-026: Entering non-empty street_address resets no_address to false.
- REQ-EXM-027: Entering non-empty official_url or related_websites resets no_websites to false.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from vistarae_core.domain.entities import POI, IngestCandidate
from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
    WGS84Point,
)
from vistarae_core.schemas.ingest_staging import CandidateUpdateRequest
from vistarae_core.schemas.poi import POIUpdateRequest

from services.ingest.services.staging_service import StagingService
from services.poi.routes.pois import _apply_poi_updates


def _make_candidate(
    cand_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    no_address: bool = True,
    no_websites: bool = True,
) -> IngestCandidate:
    return IngestCandidate(
        id=cand_id,
        job_id=uuid.uuid4(),
        user_id=user_id,
        row_index=1,
        poi_name="Exempted Peak",
        latitude=Decimal("46.8523"),
        longitude=Decimal("-121.7603"),
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
async def test_candidate_update_auto_resets_no_address() -> None:
    """Tests that patching street_address on a candidate automatically resets no_address to False."""
    user_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    cand = _make_candidate(cand_id, user_id, no_address=True, no_websites=True)

    mock_cand_repo = AsyncMock()
    mock_cand_repo.get_candidate.return_value = cand
    mock_cand_repo.update_candidate.side_effect = lambda uid, c: c

    staging_service = StagingService(candidate_repo=mock_cand_repo)

    req = CandidateUpdateRequest(street_address="500 Alpine Way")
    updated = await staging_service.update_candidate(user_id, cand_id, req)

    assert updated.street_address == "500 Alpine Way"
    assert updated.no_address is False
    assert updated.no_websites is True  # untouched


@pytest.mark.asyncio
async def test_candidate_update_auto_resets_no_websites() -> None:
    """Tests that patching official_url or related_websites automatically resets no_websites to False."""
    user_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    cand = _make_candidate(cand_id, user_id, no_address=True, no_websites=True)

    mock_cand_repo = AsyncMock()
    mock_cand_repo.get_candidate.return_value = cand
    mock_cand_repo.update_candidate.side_effect = lambda uid, c: c

    staging_service = StagingService(candidate_repo=mock_cand_repo)

    req = CandidateUpdateRequest(official_url="https://rainier.gov")
    updated = await staging_service.update_candidate(user_id, cand_id, req)

    assert updated.official_url == "https://rainier.gov"
    assert updated.no_websites is False
    assert updated.no_address is True  # untouched


def test_poi_update_auto_resets_exemptions() -> None:
    """Tests that updating a permanent POI with valid address or website resets respective exemptions."""
    poi = POI(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Wilderness Lookout",
        geom=WGS84Point(lat=46.0, lon=-121.0),
        no_address=True,
        no_websites=True,
    )

    req_addr = POIUpdateRequest(address="100 Lookout Trail")
    _apply_poi_updates(poi, req_addr)
    assert poi.address == "100 Lookout Trail"
    assert poi.no_address is False
    assert poi.no_websites is True

    req_url = POIUpdateRequest(official_url="https://lookout.org")
    _apply_poi_updates(poi, req_url)
    assert poi.official_url == "https://lookout.org"
    assert poi.no_websites is False
