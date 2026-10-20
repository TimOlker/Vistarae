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

"""Duplicate candidate triage submission endpoint (T-033).

Processes user triage decisions:
- COMMITTED: Creates POI and associates optional target_list_id
- REJECTED: Discards staged candidate record
- Updates triage_status and automatically transitions job_status to COMPLETED
  when all pending duplicates are resolved (REQ-INGEST-014, REQ-INGEST-015).
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from vistarae_core.domain.entities import POI, User
from vistarae_core.domain.exceptions import IngestJobNotFoundError
from vistarae_core.domain.value_objects import DuplicateTriageStatus, VisitState, WGS84Point
from vistarae_core.ports.repositories import IIngestJobRepository, IPOIRepository
from vistarae_core.schemas.ingest import (
    DuplicateItemResponse,
    IngestJobProgressResponse,
    TriageRequest,
)

from services.ingest.dependencies import get_current_user, get_ingest_repo, get_poi_repo

router = APIRouter(tags=["ingest"])


@router.post(
    "/jobs/{job_id}/triage",
    status_code=status.HTTP_200_OK,
    response_model=IngestJobProgressResponse,
    summary="Submit interactive triage decisions for suspected duplicates",
)
@router.post(
    "/api/ingest/jobs/{job_id}/triage",
    status_code=status.HTTP_200_OK,
    response_model=IngestJobProgressResponse,
    include_in_schema=False,
)
async def submit_triage_decisions(
    job_id: UUID,
    body: TriageRequest,
    user: User = Depends(get_current_user),
    ingest_repo: IIngestJobRepository = Depends(get_ingest_repo),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> IngestJobProgressResponse:
    """Applies triage decisions, persists committed POIs, and recalculates job status.

    Args:
        job_id: Ingest job UUID.
        body: TriageRequest payload with list of decision items.
        user: Authenticated tenant user.
        ingest_repo: Active IngestJobRepository port.
        poi_repo: Active IPOIRepository port.

    Returns:
        Updated IngestJobProgressResponse.

    Raises:
        IngestJobNotFoundError: If job is not found for tenant.
    """
    job = await ingest_repo.get_job_by_id(job_id=job_id, user_id=user.id)
    if job is None:
        raise IngestJobNotFoundError(str(job_id))

    dup_map: dict[int, dict[str, Any]] = {
        item["row_number"]: item for item in job.duplicate_payloads
    }

    # 1. Process committed decisions and create POIs
    for decision_item in body.decisions:
        row_num = decision_item.row_number
        decision = decision_item.decision

        if decision == DuplicateTriageStatus.COMMITTED and row_num in dup_map:
            staged = dup_map[row_num].get("staged_poi_data", {})
            lon = float(staged.get("longitude", 0.0))
            lat = float(staged.get("latitude", 0.0))
            point = WGS84Point(lon=lon, lat=lat)

            visited_date = staged.get("visited_date")
            visit_state = VisitState.VISITED_RETURN if visited_date else VisitState.NOT_VISITED
            visited_dates = [visited_date] if visited_date else []

            poi_id = uuid.uuid4()
            poi = POI(
                id=poi_id,
                user_id=user.id,
                name=staged.get("name", "Unknown"),
                geom=point,
                description=staged.get("description"),
                address=staged.get("address"),
                city=staged.get("city"),
                states=staged.get("states", []),
                countries=staged.get("countries", []),
                visited_dates=visited_dates,
                visit_state=visit_state,
            )
            await poi_repo.create(poi)

            if job.target_list_id:
                await poi_repo.bulk_attach_lists(user.id, [poi_id], [job.target_list_id])

    # 2. Update duplicate payloads triage status
    decision_dicts = [{"row_number": d.row_number, "decision": d.decision} for d in body.decisions]
    updated_job = await ingest_repo.update_duplicate_triage_decisions(
        job_id=job_id,
        user_id=user.id,
        decisions=decision_dicts,
    )
    if updated_job is None:
        updated_job = job

    # 3. Format response
    duplicates: list[DuplicateItemResponse] = []
    for item in updated_job.duplicate_payloads:
        duplicates.append(
            DuplicateItemResponse(
                row_number=item["row_number"],
                raw_name=item["raw_name"],
                candidate_poi_id=UUID(str(item["candidate_poi_id"])),
                match_type=item.get("match_type", "POTENTIAL_DUPLICATE"),
                similarity_score=float(item.get("similarity_score", 0.0)),
                distance_meters=float(item.get("distance_meters", 0.0)),
                triage_status=item["triage_status"],
                staged_poi_data=item.get("staged_poi_data", {}),
            )
        )

    return IngestJobProgressResponse(
        job_id=updated_job.id,
        job_status=updated_job.job_status,
        total_rows=updated_job.total_rows,
        processed_rows=updated_job.processed_rows,
        percent_complete=updated_job.percent_complete,
        duplicate_payloads=duplicates,
        error_summary=updated_job.error_summary,
        created_at=updated_job.created_at,
        updated_at=updated_job.updated_at,
    )
