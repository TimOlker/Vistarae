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

"""Unit tests for candidate staging, deduplication, and geocoding fallbacks (T-024).

Verifies REQ-ING-003 through REQ-ING-010:
- Hierarchical reverse geocoding fallback for rows with coordinates
- Hierarchical forward geocoding fallback for rows without coordinates
- Unmappable missing-coordinate fallback to IGNORE
- Spatial (<= 50m) and trigram (>= 0.60) duplicate detection -> UPDATE_EXISTING
- Macro-site spatial nesting (< 0.60 similarity) -> SUBLOCATION
- Unique location confidence >= 40% -> ACCEPT
- Unique location confidence < 40% -> IGNORE
- In-batch duplicate detection across multi-year visits
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import IngestCandidate
from vistarae_core.domain.value_objects import (
    AddressRecord,
    IngestCandidatePhaseState,
    IngestDisposition,
)
from vistarae_core.schemas.ingest_staging import CandidateUpdateRequest
from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.schemas.scraping import DeduplicationVerdictSchema

from services.ingest.services.staging_service import StagingService


@pytest.fixture
def mock_candidate_repo() -> MagicMock:
    repo = MagicMock()
    repo.create_batch = AsyncMock(side_effect=lambda candidates: candidates)
    repo.list_by_job = AsyncMock(return_value=[])
    repo.get_candidate = AsyncMock(return_value=None)
    repo.update_candidate = AsyncMock(side_effect=lambda user_id, cand: cand)
    repo.advance_to_phase2 = AsyncMock(return_value=1)
    repo.commit_job = AsyncMock(return_value=[])
    repo.purge_by_job = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def mock_poi_repo() -> MagicMock:
    repo = MagicMock()
    repo.create = AsyncMock(side_effect=lambda poi: poi)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update = AsyncMock(side_effect=lambda poi: poi)
    return repo


@pytest.fixture
def mock_geocoding_service() -> MagicMock:
    service = MagicMock()
    service.reverse_geocode = AsyncMock(return_value=[])
    service.geocode = AsyncMock(return_value=(None, None, [], False))
    return service


@pytest.fixture
def mock_duplicate_service() -> MagicMock:
    service = MagicMock()
    service.evaluate_candidate = AsyncMock(
        return_value=DeduplicationVerdictSchema(
            status="UNIQUE_LOCATION",
            scale_classification="medium",
            recommended_action="proceed",
        )
    )
    return service


@pytest.fixture
def staging_service(
    mock_candidate_repo: MagicMock,
    mock_poi_repo: MagicMock,
    mock_geocoding_service: MagicMock,
    mock_duplicate_service: MagicMock,
) -> StagingService:
    return StagingService(
        candidate_repo=mock_candidate_repo,
        poi_repo=mock_poi_repo,
        geocoding_service=mock_geocoding_service,
        duplicate_service=mock_duplicate_service,
    )


@pytest.mark.asyncio
async def test_stage_candidates_spatial_duplicate(
    staging_service: StagingService,
    mock_duplicate_service: MagicMock,
    mock_candidate_repo: MagicMock,
) -> None:
    """Tests duplicate match (<= 50m, similarity >= 0.60) yields UPDATE_EXISTING."""
    user_id = uuid4()
    job_id = uuid4()
    existing_poi_id = uuid4()

    mock_duplicate_service.evaluate_candidate.return_value = DeduplicationVerdictSchema(
        status="POTENTIAL_DUPLICATE",
        distance_meters=15.0,
        similarity_score=0.92,
        existing_poi_id=existing_poi_id,
        existing_poi_name="Senso-ji Temple",
        scale_classification="medium",
        recommended_action="abort",
    )

    record = POIExportRecord(
        poi_name="Sensoji",
        street_address=["2 Chome-3-1 Asakusa"],
        town_city=["Taito City"],
        state_province=["Tokyo"],
        zip_code=["111-0032"],
        country=["Japan"],
        latitude=Decimal("35.7147"),
        longitude=Decimal("139.7966"),
        dates_visited=["2023-04-10"],
        photo_directory="Japan 2023/Sensoji",
        location_confidence_percent=95,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.recommended_disposition == IngestDisposition.UPDATE_EXISTING
    assert item.matched_existing_poi_id == existing_poi_id
    mock_candidate_repo.create_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_stage_candidates_sublocation_nesting(
    staging_service: StagingService,
    mock_duplicate_service: MagicMock,
) -> None:
    """Tests sublocation near macro-site (< 0.60 similarity) yields SUBLOCATION."""
    user_id = uuid4()
    job_id = uuid4()
    parent_poi_id = uuid4()

    mock_duplicate_service.evaluate_candidate.return_value = DeduplicationVerdictSchema(
        status="NEARBY_PARENT",
        distance_meters=45.0,
        similarity_score=0.20,
        existing_poi_id=parent_poi_id,
        existing_poi_name="Garfield Park Conservatory",
        scale_classification="medium",
        recommended_action="make_child",
    )

    record = POIExportRecord(
        poi_name="Fern Room",
        street_address=["300 N Central Park Ave"],
        town_city=["Chicago"],
        state_province=["Illinois"],
        zip_code=["60624"],
        country=["United States"],
        latitude=Decimal("41.8860"),
        longitude=Decimal("-87.7170"),
        dates_visited=["2022-05-12"],
        photo_directory="Chicago/Garfield Park/Fern Room",
        location_confidence_percent=90,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.recommended_disposition == IngestDisposition.SUBLOCATION
    assert item.parent_poi_id == parent_poi_id


@pytest.mark.asyncio
async def test_stage_candidates_unique_location_accept(
    staging_service: StagingService,
    mock_duplicate_service: MagicMock,
) -> None:
    """Tests unique location with confidence >= 40 yields ACCEPT."""
    user_id = uuid4()
    job_id = uuid4()

    record = POIExportRecord(
        poi_name="Meiji Shrine",
        street_address=["1-1 Yoyogikamizonocho"],
        town_city=["Shibuya"],
        state_province=["Tokyo"],
        zip_code=["151-0052"],
        country=["Japan"],
        latitude=Decimal("35.6764"),
        longitude=Decimal("139.6993"),
        dates_visited=["2023-04-12"],
        photo_directory="Japan 2023/Meiji Shrine",
        location_confidence_percent=85,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    assert staged[0].recommended_disposition == IngestDisposition.ACCEPT


@pytest.mark.asyncio
async def test_stage_candidates_low_confidence_ignore(
    staging_service: StagingService,
) -> None:
    """Tests unique location with confidence < 40 yields IGNORE."""
    user_id = uuid4()
    job_id = uuid4()

    record = POIExportRecord(
        poi_name="Sledding",
        street_address=[],
        town_city=[],
        state_province=[],
        zip_code=[],
        country=[],
        latitude=Decimal("41.8500"),
        longitude=Decimal("-87.6500"),
        dates_visited=["2010-01-15"],
        photo_directory="Tim/2010/Sledding",
        location_confidence_percent=10,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    assert staged[0].recommended_disposition == IngestDisposition.IGNORE


@pytest.mark.asyncio
async def test_stage_candidates_reverse_geocoding_fallback(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
) -> None:
    """Tests reverse geocoding is called when row has coordinates but lacks address."""
    user_id = uuid4()
    job_id = uuid4()

    mock_geocoding_service.reverse_geocode.return_value = [
        AddressRecord(
            street="2 Chome-3-1 Asakusa",
            city="Taito City",
            state_province="Tokyo",
            country="Japan",
            postal_code="111-0032",
        )
    ]

    record = POIExportRecord(
        poi_name="Senso-ji",
        street_address=[],
        town_city=[],
        state_province=[],
        zip_code=[],
        country=[],
        latitude=Decimal("35.7147"),
        longitude=Decimal("139.7966"),
        dates_visited=["2023-04-10"],
        photo_directory="Japan 2023/Sensoji",
        location_confidence_percent=90,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.street_address == "2 Chome-3-1 Asakusa"
    assert item.city == "Taito City"
    assert item.country == "Japan"
    mock_geocoding_service.reverse_geocode.assert_awaited_once()


@pytest.mark.asyncio
async def test_stage_candidates_forward_geocoding_fallback(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
) -> None:
    """Tests hierarchical forward geocoding resolves missing coordinates."""
    user_id = uuid4()
    job_id = uuid4()

    mock_geocoding_service.geocode.return_value = (
        35.6764,
        139.6993,
        [
            AddressRecord(
                street="1-1 Yoyogikamizonocho",
                city="Shibuya",
                state_province="Tokyo",
                country="Japan",
                postal_code="151-0052",
            )
        ],
        False,
    )

    record = POIExportRecord(
        poi_name="Meiji Shrine",
        street_address=[],
        town_city=["Shibuya"],
        state_province=["Tokyo"],
        zip_code=[],
        country=["Japan"],
        latitude=None,
        longitude=None,
        dates_visited=["2023-04-12"],
        photo_directory="Japan 2023/Meiji Shrine",
        location_confidence_percent=85,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.latitude == Decimal("35.6764")
    assert item.longitude == Decimal("139.6993")
    assert item.recommended_disposition == IngestDisposition.ACCEPT


@pytest.mark.asyncio
async def test_stage_candidates_poi_name_only_forward_geocoding(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
) -> None:
    """Tests that a record with only a POI name (like Petra or Colosseum) is forward geocoded directly."""
    user_id = uuid4()
    job_id = uuid4()

    mock_geocoding_service.geocode.return_value = (
        30.3258,
        35.4745,
        [
            AddressRecord(
                street="",
                city="Wadi Musa",
                state_province="Ma'an",
                country="Jordan",
                postal_code="71810",
            )
        ],
        False,
    )

    record = POIExportRecord(
        poi_name="Petra",
        street_address=[],
        town_city=[],
        state_province=[],
        zip_code=[],
        country=[],
        latitude=None,
        longitude=None,
        dates_visited=[],
        photo_directory="",
        location_confidence_percent=0,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.latitude == Decimal("30.3258")
    assert item.longitude == Decimal("35.4745")
    assert item.city == "Wadi Musa"
    assert item.country == "Jordan"
    assert item.recommended_disposition == IngestDisposition.ACCEPT
    mock_geocoding_service.geocode.assert_awaited_with("Petra", country_hint=None)


@pytest.mark.asyncio
async def test_stage_candidates_unmappable_missing_coordinates_ignore(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
) -> None:
    """Tests forward geocoding failure for unmappable row marks disposition as IGNORE."""
    user_id = uuid4()
    job_id = uuid4()

    mock_geocoding_service.geocode.return_value = (None, None, [], False)

    record = POIExportRecord(
        poi_name="Random Room",
        street_address=[],
        town_city=[],
        state_province=[],
        zip_code=[],
        country=[],
        latitude=None,
        longitude=None,
        dates_visited=["2023-01-01"],
        photo_directory="Random Room",
        location_confidence_percent=20,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    assert staged[0].recommended_disposition == IngestDisposition.IGNORE


@pytest.mark.asyncio
async def test_stage_candidates_in_batch_multi_visit_duplicate(
    staging_service: StagingService,
) -> None:
    """Tests two rows in same batch representing same POI mark 2nd as UPDATE_EXISTING."""
    user_id = uuid4()
    job_id = uuid4()

    rec1 = POIExportRecord(
        poi_name="Garfield Park Conservatory",
        street_address=["300 N Central Park Ave"],
        town_city=["Chicago"],
        state_province=["Illinois"],
        zip_code=["60624"],
        country=["United States"],
        latitude=Decimal("41.8860"),
        longitude=Decimal("-87.7170"),
        dates_visited=["2002-06-15"],
        photo_directory="Tim/2002/Garfield Park Conservatory",
        location_confidence_percent=90,
    )
    rec2 = POIExportRecord(
        poi_name="Garfield Park Conservatory",
        street_address=["300 N Central Park Ave"],
        town_city=["Chicago"],
        state_province=["Illinois"],
        zip_code=["60624"],
        country=["United States"],
        latitude=Decimal("41.8860"),
        longitude=Decimal("-87.7170"),
        dates_visited=["2005-09-20"],
        photo_directory="Tim/2005/Garfield Park Conservatory",
        location_confidence_percent=90,
    )

    staged = await staging_service.stage_records(user_id, job_id, [rec1, rec2])
    assert len(staged) == 2
    assert staged[0].recommended_disposition == IngestDisposition.ACCEPT
    assert staged[1].recommended_disposition == IngestDisposition.IN_BATCH_MERGE


@pytest.mark.asyncio
async def test_update_and_advance_candidates(
    staging_service: StagingService,
    mock_candidate_repo: MagicMock,
) -> None:
    """Tests candidate field update and Phase 1 proceed transition."""
    user_id = uuid4()
    job_id = uuid4()
    cand_id = uuid4()

    existing = IngestCandidate(
        id=cand_id,
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Old Name",
        recommended_disposition=IngestDisposition.IGNORE,
        user_disposition=None,
        photo_directory="dir",
        phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
    )
    mock_candidate_repo.get_candidate.return_value = existing

    # Update candidate
    update_req = CandidateUpdateRequest(
        poi_name="New Name",
        user_disposition=IngestDisposition.ACCEPT,
    )
    updated = await staging_service.update_candidate(user_id, cand_id, update_req)
    assert updated.poi_name == "New Name"
    assert updated.user_disposition == IngestDisposition.ACCEPT

    # Proceed to Phase 2
    mock_candidate_repo.list_by_job.return_value = [updated]
    adv, ign = await staging_service.advance_to_phase2(user_id, job_id)
    assert adv == 1
    assert ign == 0


@pytest.mark.asyncio
async def test_stage_candidates_forward_geocoding_with_street_address(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
) -> None:
    """Tests forward geocoding utilizes street address and city when coordinates are missing."""
    user_id = uuid4()
    job_id = uuid4()

    mock_geocoding_service.geocode.return_value = (
        55.9497,
        -3.1909,
        [
            AddressRecord(
                street="Royal Mile",
                city="Edinburgh",
                state_province="Scotland",
                country="United Kingdom",
                postal_code="EH1 2PB",
            )
        ],
        False,
    )

    record = POIExportRecord(
        poi_name="Adam Smith Statue",
        street_address=["Royal Mile"],
        town_city=["Edinburgh"],
        state_province=["Scotland"],
        zip_code=[],
        country=["United Kingdom"],
        latitude=None,
        longitude=None,
        dates_visited=["2025-05-15"],
        photo_directory="Great Britain/Edinburgh/Adam Smith Statue",
        location_confidence_percent=95,
    )

    staged = await staging_service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    item = staged[0]
    assert item.latitude == Decimal("55.9497")
    assert item.longitude == Decimal("-3.1909")
    assert item.recommended_disposition == IngestDisposition.ACCEPT

    # Assert geocode was called with queries containing street and city
    called_queries = [call.args[0] for call in mock_geocoding_service.geocode.await_args_list]
    assert any("Royal Mile" in q and "Edinburgh" in q for q in called_queries)


@pytest.mark.asyncio
async def test_duplicate_matches_existing_poi_with_no_changes_sets_disposition_existing() -> None:
    """Verifies that matching an existing DB POI where import won't change values sets disposition to 'existing'."""
    from unittest.mock import AsyncMock, MagicMock

    from vistarae_core.domain.entities import POI
    from vistarae_core.domain.value_objects import IngestDisposition, WGS84Point
    from vistarae_core.schemas.scraping import DeduplicationVerdictSchema

    user_id = uuid4()
    job_id = uuid4()
    existing_id = uuid4()

    mock_cand_repo = MagicMock()
    mock_cand_repo.create_batch = AsyncMock(side_effect=lambda cands: cands)

    existing_poi = POI(
        id=existing_id,
        user_id=user_id,
        name="Castillo de San Marcos",
        geom=WGS84Point(lon=-81.3125, lat=29.8978),
        city="St. Augustine",
        admin_level_1="Florida",
        country_code="US",
        visited_dates=["2024-01-15"],
    )

    mock_poi_repo = MagicMock()
    mock_poi_repo.get_by_id = AsyncMock(return_value=existing_poi)

    mock_dup_service = MagicMock()
    mock_dup_service.evaluate_candidate = AsyncMock(
        return_value=DeduplicationVerdictSchema(
            status="POTENTIAL_DUPLICATE",
            distance_meters=2.5,
            similarity_score=0.98,
            scale_classification="micro",
            existing_poi_id=existing_id,
            existing_poi_name="Castillo de San Marcos",
            recommended_action="proceed",
        )
    )

    service = StagingService(
        candidate_repo=mock_cand_repo,
        poi_repo=mock_poi_repo,
        duplicate_service=mock_dup_service,
    )

    # Record with identical coordinates, city, dates
    record = POIExportRecord(
        poi_name="Castillo de San Marcos",
        town_city=["St. Augustine"],
        state_province=["Florida"],
        country=["United States"],
        latitude=Decimal("29.8978"),
        longitude=Decimal("-81.3125"),
        dates_visited=["2024-01-15"],
        photo_directory="",
        location_confidence_percent=100,
    )

    staged = await service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    assert staged[0].recommended_disposition == IngestDisposition.EXISTING
    assert "identical values (no changes detected)" in (staged[0].disposition_justification or "")


@pytest.mark.asyncio
async def test_duplicate_matches_existing_poi_with_changes_sets_update_existing() -> None:
    """Verifies that matching an existing DB POI where import adds new values sets disposition to 'update_existing'."""
    from unittest.mock import AsyncMock, MagicMock

    from vistarae_core.domain.entities import POI
    from vistarae_core.domain.value_objects import IngestDisposition, WGS84Point
    from vistarae_core.schemas.scraping import DeduplicationVerdictSchema

    user_id = uuid4()
    job_id = uuid4()
    existing_id = uuid4()

    mock_cand_repo = MagicMock()
    mock_cand_repo.create_batch = AsyncMock(side_effect=lambda cands: cands)

    existing_poi = POI(
        id=existing_id,
        user_id=user_id,
        name="Castillo de San Marcos",
        geom=WGS84Point(lon=-81.3125, lat=29.8978),
        city="St. Augustine",
        admin_level_1="Florida",
        country_code="US",
        visited_dates=["2024-01-15"],
    )

    mock_poi_repo = MagicMock()
    mock_poi_repo.get_by_id = AsyncMock(return_value=existing_poi)

    mock_dup_service = MagicMock()
    mock_dup_service.evaluate_candidate = AsyncMock(
        return_value=DeduplicationVerdictSchema(
            status="POTENTIAL_DUPLICATE",
            distance_meters=2.5,
            similarity_score=0.98,
            scale_classification="micro",
            existing_poi_id=existing_id,
            existing_poi_name="Castillo de San Marcos",
            recommended_action="proceed",
        )
    )

    service = StagingService(
        candidate_repo=mock_cand_repo,
        poi_repo=mock_poi_repo,
        duplicate_service=mock_dup_service,
    )

    # Record introduces a new visited date ("2025-02-20")
    record = POIExportRecord(
        poi_name="Castillo de San Marcos",
        town_city=["St. Augustine"],
        state_province=["Florida"],
        country=["United States"],
        latitude=Decimal("29.8978"),
        longitude=Decimal("-81.3125"),
        dates_visited=["2025-02-20"],
        photo_directory="",
        location_confidence_percent=100,
    )

    staged = await service.stage_records(user_id, job_id, [record])
    assert len(staged) == 1
    assert staged[0].recommended_disposition == IngestDisposition.UPDATE_EXISTING


@pytest.mark.asyncio
async def test_commit_job_skips_existing_disposition_same_as_ignore_and_exclude() -> None:
    """Verifies that candidates with disposition 'existing' are skipped on commit without creating or updating POIs."""
    from unittest.mock import AsyncMock, MagicMock

    from vistarae_core.domain.entities import IngestCandidate
    from vistarae_core.domain.value_objects import IngestDisposition

    user_id = uuid4()
    job_id = uuid4()

    existing_cand = IngestCandidate(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        row_index=0,
        poi_name="Existing Fortress",
        recommended_disposition=IngestDisposition.EXISTING,
        user_disposition=None,
        latitude=Decimal("29.8978"),
        longitude=Decimal("-81.3125"),
    )

    mock_cand_repo = MagicMock()
    mock_cand_repo.list_by_job = AsyncMock(return_value=[existing_cand])
    mock_cand_repo.purge_by_job = AsyncMock(return_value=1)

    mock_poi_repo = MagicMock()
    mock_poi_repo.create = AsyncMock()
    mock_poi_repo.update = AsyncMock()

    service = StagingService(
        candidate_repo=mock_cand_repo,
        poi_repo=mock_poi_repo,
    )

    total, created, merged = await service.commit_job(user_id, job_id)
    assert total == 0
    assert len(created) == 0
    assert len(merged) == 0
    mock_poi_repo.create.assert_not_called()
    mock_poi_repo.update.assert_not_called()
