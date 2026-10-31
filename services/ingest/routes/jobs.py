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

"""Job progress polling and duplicate inspection routes (T-032).

Provides GET /api/ingest/jobs/{job_id} reporting row progress counters, percentage,
and staged duplicate candidate records for tenant review per REQ-INGEST-013 and REQ-INGEST-015.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from vistarae_core.domain.entities import User
from vistarae_core.domain.exceptions import IngestJobNotFoundError
from vistarae_core.ports.repositories import IIngestJobRepository
from vistarae_core.schemas.ingest import DuplicateItemResponse, IngestJobProgressResponse

from services.ingest.dependencies import get_current_user, get_ingest_repo

router = APIRouter(tags=["ingest"])


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=IngestJobProgressResponse,
    summary="Poll ingestion job status and retrieve staged duplicates",
)
@router.get(
    "/api/ingest/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=IngestJobProgressResponse,
    include_in_schema=False,
)
async def get_job_progress(
    job_id: UUID,
    user: User = Depends(get_current_user),
    ingest_repo: IIngestJobRepository = Depends(get_ingest_repo),
) -> IngestJobProgressResponse:
    """Retrieves ingestion job state enforcing tenant isolation.

    Args:
        job_id: Unique ingestion job UUID.
        user: Authenticated tenant user.
        ingest_repo: Active IngestJobRepository port.

    Returns:
        IngestJobProgressResponse containing progress metrics and staged duplicates.

    Raises:
        IngestJobNotFoundError: If job does not exist or belongs to another tenant.
    """
    job = await ingest_repo.get_job_by_id(job_id=job_id, user_id=user.id)
    if job is None:
        raise IngestJobNotFoundError(str(job_id))

    import contextlib
    import uuid as _uuid_mod

    duplicates: list[DuplicateItemResponse] = []
    for item in job.duplicate_payloads:
        with contextlib.suppress(Exception):
            cand_id_raw = (
                item.get("candidate_poi_id") or item.get("candidate_id") or _uuid_mod.uuid4()
            )
            duplicates.append(
                DuplicateItemResponse(
                    row_number=item.get("row_number", 1),
                    raw_name=item.get("raw_name", "Unknown"),
                    candidate_poi_id=UUID(str(cand_id_raw)),
                    match_type=item.get("match_type", "POTENTIAL_DUPLICATE"),
                    similarity_score=float(item.get("similarity_score", 0.0)),
                    distance_meters=float(item.get("distance_meters", 0.0)),
                    triage_status=item.get("triage_status", "PENDING_REVIEW"),
                    staged_poi_data=item.get("staged_poi_data", {}),
                )
            )

    return IngestJobProgressResponse(
        job_id=job.id,
        job_status=job.job_status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        percent_complete=job.percent_complete,
        duplicate_payloads=duplicates,
        error_summary=job.error_summary,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
