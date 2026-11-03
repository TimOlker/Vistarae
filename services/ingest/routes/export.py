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

"""FastAPI streaming export endpoints for Vistarae Explorer and Ingestion Triage phases."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import IngestCandidateTable, POITable
from vistarae_core.domain.base import StrictBaseModel
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import ExportFormat, IngestDisposition
from vistarae_core.schemas.poi_exchange import POIExchangeRecord
from vistarae_core.services.poi_exporter import POIExporter

from services.user.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/export", tags=["export"])


class ExportPOIsRequest(StrictBaseModel):
    """Payload for exporting selected committed POIs from Vistarae Explorer."""

    poi_ids: list[UUID] = Field(
        default_factory=list,
        description="Explicit list of selected POI UUIDs to export.",
    )
    format: ExportFormat = Field(
        default=ExportFormat.CSV,
        description="Desired export file format (csv, json, yaml).",
    )


class ExportCandidatesRequest(StrictBaseModel):
    """Payload for exporting selected staged candidates from Phase 1 or Phase 2."""

    job_id: UUID = Field(
        ...,
        description="Active ingestion job UUID.",
    )
    candidate_ids: list[UUID] = Field(
        default_factory=list,
        description="Explicit list of selected candidate UUIDs to export.",
    )
    format: ExportFormat = Field(
        default=ExportFormat.CSV,
        description="Desired export file format (csv, json, yaml).",
    )


class ExportService:
    """Service retrieving domain entities and converting them into POIExchangeRecord streams."""

    def __init__(self, session: AsyncSession, current_user: User | None = None) -> None:
        self._session = session
        self._current_user = current_user

    async def get_pois_for_export(
        self, user_id: UUID, poi_ids: list[UUID]
    ) -> list[POIExchangeRecord]:
        """Fetches committed POIs matching IDs owned by the current tenant."""
        stmt = (
            select(POITable)
            .where(POITable.user_id == user_id, POITable.id.in_(poi_ids))
            .options(selectinload(POITable.tags))
        )
        res = await self._session.execute(stmt)
        poi_rows = res.scalars().all()

        records: list[POIExchangeRecord] = []
        for row in poi_rows:
            # Extract coordinates from geom
            lat, lon = None, None
            if row.geom is not None:
                from geoalchemy2.shape import to_shape

                point = to_shape(row.geom)
                lat, lon = point.y, point.x

            tag_names = [t.name for t in row.tags] if row.tags else []

            record = POIExchangeRecord(
                poi_id=row.id,
                poi_name=row.name,
                latitude=lat,
                longitude=lon,
                street_address=row.address or "",
                city=row.city or "",
                state_province=row.states[0] if row.states else "",
                postal_code="",
                country=row.countries[0] if row.countries else "",
                tags=tag_names,
                dates_visited=row.visited_dates or [],
                photo_directory=row.directory_paths[0] if row.directory_paths else "",
                location_confidence_percent=100,
                user_disposition=IngestDisposition.ACCEPT,
                rejection_reason="",
                ai_description=row.description or "",
                reason_to_visit=row.reason_to_visit or "",
                recommended_duration_hours=float(row.recommended_duration_hours)
                if row.recommended_duration_hours
                else 2.0,
                itinerary_days=row.recommended_visit_days or 1,
                hero_image_url=row.image_urls[0] if row.image_urls else "",
                official_website=row.official_url or "",
                wikipedia_url=row.wiki_url or "",
                created_at=row.created_at,
            )
            records.append(record)
        return records

    async def get_candidates_for_export(
        self, user_id: UUID, job_id: UUID, candidate_ids: list[UUID]
    ) -> list[POIExchangeRecord]:
        """Fetches staged candidates matching IDs for the active ingestion job."""
        stmt = select(IngestCandidateTable).where(
            IngestCandidateTable.user_id == user_id,
            IngestCandidateTable.job_id == job_id,
            IngestCandidateTable.id.in_(candidate_ids),
        )
        res = await self._session.execute(stmt)
        cand_rows = res.scalars().all()

        records: list[POIExchangeRecord] = []
        for c in cand_rows:
            lat = float(c.latitude) if c.latitude is not None else None
            lon = float(c.longitude) if c.longitude is not None else None
            record = POIExchangeRecord(
                poi_id=c.matched_existing_poi_id,
                poi_name=c.poi_name,
                latitude=lat,
                longitude=lon,
                street_address=c.street_address or "",
                city=getattr(c, "city", None) or getattr(c, "locality", None) or getattr(c, "town_city", "") or "",
                state_province=getattr(c, "state_province", None) or getattr(c, "admin_level_1", "") or "",
                postal_code=getattr(c, "postal_code", None) or getattr(c, "zip_code", "") or "",
                country=getattr(c, "country", None) or getattr(c, "country_code", "") or "",
                tags=c.tags or [],
                dates_visited=c.dates_visited or [],
                photo_directory=c.photo_directory or "",
                location_confidence_percent=getattr(c, "confidence_score", None) or getattr(c, "location_confidence_percent", 0) or 0,
                user_disposition=c.user_disposition,
                rejection_reason=getattr(c, "disposition_justification", None) or getattr(c, "rejection_reason", "") or "",
                ai_description=c.ai_description or "",
                reason_to_visit=c.reason_to_visit or "",
                recommended_duration_hours=float(c.recommended_duration_hours)
                if c.recommended_duration_hours
                else 2.0,
                itinerary_days=c.recommended_visit_days or 1,
                hero_image_url=c.hero_image_url or "",
                official_website=c.official_url or "",
                wikipedia_url=c.wiki_url or "",
                created_at=c.created_at,
            )
            records.append(record)
        return records


def get_export_service(
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user),
) -> ExportService:
    """Dependency provider returning an ExportService instance."""
    return ExportService(session=session, current_user=current_user)


def _build_streaming_export_response(
    records: list[POIExchangeRecord], export_format: ExportFormat, file_prefix: str
) -> StreamingResponse:
    """Builds a chunked HTTP StreamingResponse for the given records and format."""
    now_str = datetime.now(UTC).strftime("%Y-%m-%d")

    if export_format == ExportFormat.CSV:
        media_type = "text/csv; charset=utf-8"
        filename = f"{file_prefix}_{now_str}.csv"
        generator = POIExporter.stream_csv_chunks(records)
    elif export_format == ExportFormat.JSON:
        media_type = "application/json; charset=utf-8"
        filename = f"{file_prefix}_{now_str}.json"
        generator = POIExporter.stream_json_chunks(records)
    elif export_format == ExportFormat.YAML:
        media_type = "application/x-yaml; charset=utf-8"
        filename = f"{file_prefix}_{now_str}.yaml"
        generator = POIExporter.stream_yaml_chunks(records)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {export_format}")

    return StreamingResponse(
        generator,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/pois")
async def export_pois(
    payload: ExportPOIsRequest,
    current_user: User | None = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """Exports selected committed POIs from Vistarae Explorer. Aborts if 0 rows selected."""
    if not payload.poi_ids:
        raise HTTPException(
            status_code=400,
            detail="No records selected. Please select at least one record to export.",
        )

    user_id = current_user.id if current_user else UUID("00000000-0000-0000-0000-000000000000")
    records = await service.get_pois_for_export(user_id=user_id, poi_ids=payload.poi_ids)
    return _build_streaming_export_response(records, payload.format, "vistarae_pois")


@router.post("/candidates/phase1")
async def export_phase1_candidates(
    payload: ExportCandidatesRequest,
    current_user: User | None = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """Exports selected candidate records from Phase 1 Triage. Aborts if 0 rows selected."""
    if not payload.candidate_ids:
        raise HTTPException(
            status_code=400,
            detail="No records selected. Please select at least one record to export.",
        )

    user_id = current_user.id if current_user else UUID("00000000-0000-0000-0000-000000000000")
    records = await service.get_candidates_for_export(
        user_id=user_id, job_id=payload.job_id, candidate_ids=payload.candidate_ids
    )
    return _build_streaming_export_response(records, payload.format, "vistarae_phase1_triage")


@router.post("/candidates/phase2")
async def export_phase2_candidates(
    payload: ExportCandidatesRequest,
    current_user: User | None = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> StreamingResponse:
    """Exports selected candidate records from Phase 2 Review. Aborts if 0 rows selected."""
    if not payload.candidate_ids:
        raise HTTPException(
            status_code=400,
            detail="No records selected. Please select at least one record to export.",
        )

    user_id = current_user.id if current_user else UUID("00000000-0000-0000-0000-000000000000")
    records = await service.get_candidates_for_export(
        user_id=user_id, job_id=payload.job_id, candidate_ids=payload.candidate_ids
    )
    return _build_streaming_export_response(records, payload.format, "vistarae_phase2_review")
