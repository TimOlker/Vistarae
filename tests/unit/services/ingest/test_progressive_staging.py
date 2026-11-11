# Copyright (c) 2026 Tim Olker
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for StagingService progressive staging and rate-limited geocaching (Option A)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from vistarae_core.domain.entities import IngestCandidate, User
from vistarae_core.domain.value_objects import IngestDisposition, IngestJobStatus
from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.schemas.scraping import DeduplicationVerdictSchema

from services.ingest.services.staging_service import StagingService


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def job_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_candidate_repo() -> MagicMock:
    repo = MagicMock()
    repo.create_batch = AsyncMock(side_effect=lambda candidates: candidates)
    return repo


@pytest.fixture
def mock_ingest_repo() -> MagicMock:
    repo = MagicMock()
    repo.increment_processed_rows = AsyncMock()
    repo.append_duplicate_payload = AsyncMock()
    repo.append_error_summary = AsyncMock()
    repo.update_job_status = AsyncMock()
    return repo


@pytest.fixture
def mock_geocoding_service() -> MagicMock:
    service = MagicMock()
    service.geocode = AsyncMock(return_value=(37.7749, -122.4194, [], True))
    service.reverse_geocode = AsyncMock(return_value=[])
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
    mock_geocoding_service: MagicMock,
    mock_duplicate_service: MagicMock,
    mock_ingest_repo: MagicMock,
) -> StagingService:
    return StagingService(
        candidate_repo=mock_candidate_repo,
        geocoding_service=mock_geocoding_service,
        duplicate_service=mock_duplicate_service,
        ingest_repo=mock_ingest_repo,
    )


@pytest.mark.asyncio
async def test_stage_records_progressive_increments_and_commits_per_row(
    staging_service: StagingService,
    mock_candidate_repo: MagicMock,
    mock_ingest_repo: MagicMock,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Verifies that progressive staging increments processed_rows and commits per record."""
    records = [
        POIExportRecord(
            poi_name=f"Place {i}",
            latitude=Decimal("37.7") + Decimal(str(i * 0.01)),
            longitude=Decimal("-122.4") + Decimal(str(i * 0.01)),
            photo_directory="",
        )
        for i in range(3)
    ]
    mock_session = AsyncMock()

    staged = await staging_service.stage_records_progressive(
        user_id=user_id,
        job_id=job_id,
        records=records,
        session=mock_session,
    )

    assert len(staged) == 3
    # 3 records persisted one by one
    assert mock_candidate_repo.create_batch.await_count == 3
    # 3 increments to processed_rows
    assert mock_ingest_repo.increment_processed_rows.await_count == 3
    # Marked as COMPLETED at the end
    mock_ingest_repo.update_job_status.assert_awaited_once_with(
        job_id, user_id, IngestJobStatus.COMPLETED
    )
    # Commits: 1 per record + 1 on completion = 4
    assert mock_session.commit.await_count == 4


@pytest.mark.asyncio
async def test_stage_records_progressive_geocodes_missing_coordinates(
    staging_service: StagingService,
    mock_geocoding_service: MagicMock,
    mock_ingest_repo: MagicMock,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Verifies missing coordinates trigger geocoding service and populate coordinates."""
    mock_session = AsyncMock()
    record = POIExportRecord(
        poi_name="Golden Gate Bridge",
        latitude=None,
        longitude=None,
        town_city=["San Francisco"],
        photo_directory="",
    )

    staged = await staging_service.stage_records_progressive(
        user_id=user_id,
        job_id=job_id,
        records=[record],
        session=mock_session,
    )

    assert len(staged) == 1
    assert staged[0].latitude == Decimal("37.7749")
    assert staged[0].longitude == Decimal("-122.4194")
    mock_geocoding_service.geocode.assert_awaited()
    mock_ingest_repo.update_job_status.assert_awaited_once_with(
        job_id, user_id, IngestJobStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_stage_records_progressive_handles_row_failure_resiliently(
    staging_service: StagingService,
    mock_candidate_repo: MagicMock,
    mock_ingest_repo: MagicMock,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Verifies that an error on one row records in error_summary and advances processed_rows."""
    mock_session = AsyncMock()
    # Row 0 succeeds, Row 1 fails, Row 2 succeeds
    mock_candidate_repo.create_batch = AsyncMock(
        side_effect=[
            [MagicMock()],
            RuntimeError("PostGIS geometry error on row 1"),
            [MagicMock()],
        ]
    )

    records = [
        POIExportRecord(poi_name="Place 0", latitude=Decimal("37.1"), longitude=Decimal("-122.1"), photo_directory=""),
        POIExportRecord(poi_name="Corrupt Place 1", latitude=Decimal("37.2"), longitude=Decimal("-122.2"), photo_directory=""),
        POIExportRecord(poi_name="Place 2", latitude=Decimal("37.3"), longitude=Decimal("-122.3"), photo_directory=""),
    ]

    await staging_service.stage_records_progressive(
        user_id=user_id,
        job_id=job_id,
        records=records,
        session=mock_session,
    )

    # All 3 rows accounted for in processed_rows
    assert mock_ingest_repo.increment_processed_rows.await_count == 3
    # Error summary recorded for the failing row
    assert mock_ingest_repo.append_error_summary.await_count == 1
    err_args = mock_ingest_repo.append_error_summary.await_args[0]
    assert err_args[0] == job_id
    assert err_args[1] == user_id
    assert err_args[2]["raw_name"] == "Corrupt Place 1"
    assert "PostGIS geometry error" in err_args[2]["detail"]
    # Job still marked COMPLETED because all rows processed
    mock_ingest_repo.update_job_status.assert_awaited_once_with(
        job_id, user_id, IngestJobStatus.COMPLETED
    )

