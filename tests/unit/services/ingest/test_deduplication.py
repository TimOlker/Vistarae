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

"""Unit tests for intra-batch duplicate detection and exclusion zone classification (FR-019, FR-020, T-023)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.domain.entities import UserExclusionZone
from vistarae_core.domain.value_objects import IngestDisposition
from vistarae_core.schemas.poi_export import POIExportRecord

from services.ingest.services.staging_service import StagingService


@pytest.mark.asyncio
async def test_in_batch_duplicate_assigned_merge_disposition_and_target_id() -> None:
    """Verifies that subsequent identical candidates in a batch are marked IN_BATCH_MERGE with merge_target_id (FR-019)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.create_batch = AsyncMock(side_effect=lambda batch: batch)

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=None,
        geocoding_service=None,
        duplicate_service=None,
        exclusion_zone_repo=None,
    )

    records = [
        POIExportRecord(
            poi_name="Golden Gate Overlook",
            street_address=["Langdon Court"],
            town_city=["San Francisco"],
            state_province=["CA"],
            zip_code=["94129"],
            country=["USA"],
            latitude=Decimal("37.8024"),
            longitude=Decimal("-122.4786"),
            dates_visited=["2023-08-15"],
            photo_directory="SF/Overlooks",
            location_confidence_percent=90,
        ),
        POIExportRecord(
            poi_name="Golden Gate Overlook",
            street_address=["Langdon Court"],
            town_city=["San Francisco"],
            state_province=["CA"],
            zip_code=["94129"],
            country=["USA"],
            latitude=Decimal("37.80241"),  # ~1m away
            longitude=Decimal("-122.47861"),
            dates_visited=["2024-02-10"],
            photo_directory="SF/Overlooks2",
            location_confidence_percent=90,
        ),
    ]

    staged = await service.stage_records(user_id=user_id, job_id=job_id, records=records)

    assert len(staged) == 2
    primary = staged[0]
    duplicate = staged[1]

    # Primary should be accepted
    assert primary.recommended_disposition == IngestDisposition.ACCEPT
    assert primary.merge_target_id is None

    # Duplicate should be marked IN_BATCH_MERGE pointing to primary
    assert duplicate.recommended_disposition == IngestDisposition.IN_BATCH_MERGE
    assert duplicate.merge_target_id == primary.id
    assert duplicate.disposition_justification is not None
    assert "Duplicate of #1 'Golden Gate Overlook' in batch" in duplicate.disposition_justification


@pytest.mark.asyncio
async def test_exclusion_zone_candidate_assigned_exclude_disposition() -> None:
    """Verifies that candidate within an exclusion zone is flagged with EXCLUDE and explanation (FR-020)."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_candidate_repo = MagicMock()
    mock_candidate_repo.create_batch = AsyncMock(side_effect=lambda batch: batch)

    # Exclusion zone centered at (40.7128, -74.0060) with 5km radius
    mock_exclusion_zone_repo = MagicMock()
    mock_exclusion_zone_repo.list_by_user = AsyncMock(
        return_value=[
            UserExclusionZone(
                id=uuid.uuid4(),
                user_id=user_id,
                name="Private Home Zone",
                latitude=40.7128,
                longitude=-74.0060,
                radius_km=5.0,
            )
        ]
    )

    service = StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=None,
        geocoding_service=None,
        duplicate_service=None,
        exclusion_zone_repo=mock_exclusion_zone_repo,
    )

    records = [
        POIExportRecord(
            poi_name="Secret Backyard Spot",
            street_address=["123 Broadway"],
            town_city=["New York"],
            state_province=["NY"],
            zip_code=["10007"],
            country=["USA"],
            latitude=Decimal("40.7130"),  # within 500m of exclusion center
            longitude=Decimal("-74.0062"),
            dates_visited=["2023-01-01"],
            photo_directory="NYC/Home",
            location_confidence_percent=95,
        ),
    ]

    staged = await service.stage_records(user_id=user_id, job_id=job_id, records=records)

    assert len(staged) == 1
    cand = staged[0]
    assert cand.recommended_disposition == IngestDisposition.EXCLUDE
    assert cand.disposition_justification == "Point falls within user exclusion zone"
