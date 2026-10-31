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

"""Unit tests for multi-visit duplicate merging and coordinate preservation (T-037).

Verifies REQ-ING-023 and Clarification Q4:
- Union of visited_dates without duplicates
- Union of directory_paths without duplicates
- Tag aggregation without duplicates
- Preservation of existing primary coordinates and address by default (update_coordinates=False)
- Appending distinct candidate address records
- Overwriting primary coordinates and address when update_coordinates=True
- Protection of existing user-curated descriptions and reasons to visit
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import POI, IngestCandidate
from vistarae_core.domain.value_objects import (
    AddressRecord,
    IngestCandidatePhaseState,
    IngestDisposition,
    WGS84Point,
)

from services.ingest.services.staging_service import StagingService


@pytest.mark.asyncio
async def test_multi_visit_merge_preserves_coordinates_by_default() -> None:
    """Asserts commit of update_existing preserves existing coordinates and unions dates/paths."""
    user_id = uuid4()
    job_id = uuid4()
    existing_poi_id = uuid4()

    existing_poi = POI(
        id=existing_poi_id,
        user_id=user_id,
        name="Garfield Park Conservatory",
        geom=WGS84Point(lon=-87.7170, lat=41.8860),
        address="300 N Central Park Ave",
        city="Chicago",
        description="Historic botanical conservatory featuring glasshouses and rare plants.",
        reason_to_visit="Admire world-class tropical flora in historic glasshouses.",
        visited_dates=["2002-06-15"],
        directory_paths=["M:\\Photos\\2002\\Garfield Park"],
        addresses=[
            AddressRecord(
                street="300 N Central Park Ave",
                city="Chicago",
                state_province="Illinois",
                country="United States",
                postal_code="60624",
            )
        ],
    )

    update_candidate = IngestCandidate(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        row_index=1,
        poi_name="Garfield Park Conservatory",
        recommended_disposition=IngestDisposition.UPDATE_EXISTING,
        user_disposition=None,
        matched_existing_poi_id=existing_poi_id,
        latitude=Decimal("41.8865"),
        longitude=Decimal("-87.7175"),
        street_address="300 N Central Park Ave",
        city="Chicago",
        state_province="Illinois",
        postal_code="60624",
        country="United States",
        dates_visited=["2005-09-20"],
        photo_directory="M:\\Photos\\2005\\Garfield Park",
        tags=["chicago", "greenhouse"],
        update_coordinates=False,  # Default: preserve existing coordinates
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
    )

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.list_by_job = AsyncMock(return_value=[update_candidate])
    mock_candidate_repo.purge_by_job = AsyncMock(return_value=1)

    mock_poi_repo = MagicMock()
    mock_poi_repo.get_by_id = AsyncMock(return_value=existing_poi)
    mock_poi_repo.update = AsyncMock(side_effect=lambda p: p)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
    )

    count, created, merged = await service.commit_job(user_id, job_id)

    assert count == 1
    assert len(merged) == 1
    assert merged[0] == existing_poi_id

    mock_poi_repo.update.assert_awaited_once()
    updated = mock_poi_repo.update.call_args[0][0]

    # Preserved coordinates
    assert updated.geom.lat == 41.8860
    assert updated.geom.lon == -87.7170
    assert updated.address == "300 N Central Park Ave"

    # Preserved curated descriptions
    assert (
        updated.description
        == "Historic botanical conservatory featuring glasshouses and rare plants."
    )
    assert updated.reason_to_visit == "Admire world-class tropical flora in historic glasshouses."

    # Union of visited dates and directory paths
    assert sorted(updated.visited_dates) == ["2002-06-15", "2005-09-20"]
    assert sorted(updated.directory_paths) == [
        "M:\\Photos\\2002\\Garfield Park",
        "M:\\Photos\\2005\\Garfield Park",
    ]


@pytest.mark.asyncio
async def test_multi_visit_merge_overwrites_coordinates_when_toggled() -> None:
    """Asserts commit overwrites coordinates when update_coordinates is explicitly True."""
    user_id = uuid4()
    job_id = uuid4()
    existing_poi_id = uuid4()

    existing_poi = POI(
        id=existing_poi_id,
        user_id=user_id,
        name="Senso-ji",
        geom=WGS84Point(lon=139.7900, lat=35.7100),
        address="Rough Address",
        city="Tokyo",
        visited_dates=["2019-05-01"],
        directory_paths=["M:\\Photos\\2019\\Tokyo"],
    )

    update_candidate = IngestCandidate(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Senso-ji",
        recommended_disposition=IngestDisposition.UPDATE_EXISTING,
        user_disposition=None,
        matched_existing_poi_id=existing_poi_id,
        latitude=Decimal("35.7147"),
        longitude=Decimal("139.7966"),
        street_address="2 Chome-3-1 Asakusa",
        city="Taito City",
        dates_visited=["2023-04-10"],
        photo_directory="M:\\Photos\\2023\\Asakusa",
        update_coordinates=True,  # Explicitly opt in to coordinate update
        phase_state=IngestCandidatePhaseState.PHASE_2_ENRICHED,
    )

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.list_by_job = AsyncMock(return_value=[update_candidate])
    mock_candidate_repo.purge_by_job = AsyncMock(return_value=1)

    mock_poi_repo = MagicMock()
    mock_poi_repo.get_by_id = AsyncMock(return_value=existing_poi)
    mock_poi_repo.update = AsyncMock(side_effect=lambda p: p)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
    )

    await service.commit_job(user_id, job_id)

    updated = mock_poi_repo.update.call_args[0][0]
    # Overwritten coordinates and address
    assert updated.geom.lat == 35.7147
    assert updated.geom.lon == 139.7966
    assert updated.address == "2 Chome-3-1 Asakusa"
    assert updated.city == "Taito City"

    # Union of dates and paths
    assert sorted(updated.visited_dates) == ["2019-05-01", "2023-04-10"]
    assert sorted(updated.directory_paths) == [
        "M:\\Photos\\2019\\Tokyo",
        "M:\\Photos\\2023\\Asakusa",
    ]
