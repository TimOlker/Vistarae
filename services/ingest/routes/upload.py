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

"""Bulk CSV upload route and SQS batch partitioning (T-016).

Accepts CSV uploads, validates MIME and size boundaries, sanitizes spreadsheet formula
injection and HTML, stores job record, and dispatches rows 1:1 to SQS in chunks of 10.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import time
import uuid
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse
from vistarae_core.domain.entities import IngestJob, User
from vistarae_core.domain.enums import TagResolutionAction
from vistarae_core.domain.value_objects import IngestDisposition, IngestJobStatus
from vistarae_core.ports.queue import IQueuePort
from vistarae_core.ports.repositories import IIngestJobRepository, IListRepository
from vistarae_core.schemas.ingest import IngestUploadResponse
from vistarae_core.schemas.poi_exchange import POIExchangeRecord
from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.services.poi_importer import POIImporter

from services.ingest.dependencies import (
    get_current_user,
    get_ingest_repo,
    get_list_repo,
    get_queue_port,
    get_staging_service,
)
from services.ingest.services.csv_parser import parse_and_sanitize_csv
from services.ingest.services.staging_service import StagingService

router = APIRouter(tags=["ingest"])


def _extract_or_generate_trace_context(request: Request) -> dict[str, str]:
    """Extracts incoming W3C and AWS trace context or generates new root IDs.

    Args:
        request: FastAPI HTTP request context.

    Returns:
        Dict with 'traceparent' and 'X-Amzn-Trace-Id'.
    """
    traceparent = request.headers.get("traceparent")
    if not traceparent:
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        traceparent = f"00-{trace_id}-{span_id}-01"

    amzn_trace_id = request.headers.get("x-amzn-trace-id")
    if not amzn_trace_id:
        epoch_hex = f"{int(time.time()):08x}"
        random_hex = secrets.token_hex(12)
        amzn_trace_id = f"Root=1-{epoch_hex}-{random_hex}"

    return {
        "traceparent": traceparent,
        "X-Amzn-Trace-Id": amzn_trace_id,
    }


@router.post(
    "/csv",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestUploadResponse,
    summary="Accept bulk CSV upload for asynchronous processing",
)
@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestUploadResponse,
    include_in_schema=False,
)
@router.post(
    "/api/ingest/csv",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestUploadResponse,
    include_in_schema=False,
)
@router.post(
    "/api/ingest/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestUploadResponse,
    include_in_schema=False,
)
async def upload_csv(  # noqa: C901
    request: Request,
    file: Annotated[UploadFile, File(description="CSV file to ingest")],
    target_list_id: Annotated[UUID | None, Form(description="Optional target list ID")] = None,
    target_list_name: Annotated[
        str | None, Form(description="Optional target list name to attach POIs to")
    ] = None,
    column_mapping: Annotated[
        str | None, Form(description="Optional JSON string of column mappings")
    ] = None,
    user: User = Depends(get_current_user),
    ingest_repo: IIngestJobRepository = Depends(get_ingest_repo),
    list_repo: IListRepository = Depends(get_list_repo),
    queue_port: IQueuePort = Depends(get_queue_port),
    staging_service: StagingService | None = Depends(get_staging_service),
) -> IngestUploadResponse:
    """Accepts CSV file upload, applies security guardrails, and dispatches to queue.

    Args:
        request: HTTP request context.
        file: Multipart uploaded file.
        target_list_id: Optional UUID of list to attach imported POIs.
        user: Authenticated tenant user.
        ingest_repo: Active IngestJobRepository instance.
        queue_port: Active IQueuePort adapter.

    Returns:
        IngestUploadResponse with HTTP 202 Accepted.
    """
    # Active staging session guard (FR-031)
    if staging_service is not None:
        active_session = await staging_service.get_active_session(user.id)
        if active_session.has_active_session:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "type": "https://api.vistarae.com/errors/conflict",
                    "title": "Active Staging Session Exists",
                    "status": 409,
                    "detail": (
                        f"An active uncommitted staging session ({active_session.job_id}) is currently in progress. "
                        "Commit or discard the active session before uploading a new file."
                    ),
                    "instance": request.url.path,
                    "job_id": str(active_session.job_id) if active_session.job_id else None,
                },
                headers={"Content-Type": "application/problem+json"},
            )

    mapping_dict = None
    if column_mapping:
        import json

        with contextlib.suppress(Exception):
            mapping_dict = json.loads(column_mapping)
            if not isinstance(mapping_dict, dict):
                mapping_dict = None

    file_bytes = await file.read()
    parsed_rows = parse_and_sanitize_csv(
        file_bytes, content_type=file.content_type, column_mapping=mapping_dict
    )

    # Resolve or create target list if specified by name
    if target_list_name and target_list_name.strip() and not target_list_id:
        clean_name = target_list_name.strip()
        try:
            user_lists = await list_repo.list_by_user(user.id)
            matched = next(
                (lst for lst in user_lists if lst.title.strip().lower() == clean_name.lower()),
                None,
            )
            if matched:
                target_list_id = matched.id
            else:
                from vistarae_core.domain.entities import ListEntity

                new_list = ListEntity(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=clean_name,
                    description=f"Imported from {file.filename or 'CSV'}",
                    is_public=False,
                )
                created_list = await list_repo.create(new_list)
                target_list_id = created_list.id
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed resolving target list '%s': %s", clean_name, exc
            )

    job_id = uuid.uuid4()
    job = IngestJob(
        id=job_id,
        user_id=user.id,
        job_status=IngestJobStatus.PENDING,
        total_rows=len(parsed_rows),
        processed_rows=0,
        duplicate_payloads=[],
        target_list_id=target_list_id,
        error_summary=[],
    )
    created_job = await ingest_repo.create_job(job)

    # Stage records into ingest_candidates for interactive two-phase triage
    export_records: list[POIExportRecord] = []
    for r in parsed_rows:
        rd = r["row_data"]
        lat = None
        if rd.get("latitude"):
            with contextlib.suppress(Exception):
                lat = Decimal(str(rd["latitude"]).lstrip("'").strip())
        lon = None
        if rd.get("longitude"):
            with contextlib.suppress(Exception):
                lon = Decimal(str(rd["longitude"]).lstrip("'").strip())

        export_records.append(
            POIExportRecord(
                poi_name=rd.get("poi_name") or rd.get("name", "Unknown"),
                street_address=[rd["street_address"]] if rd.get("street_address") else [],
                town_city=[rd["city"]] if rd.get("city") else [],
                state_province=[rd["state_province"]] if rd.get("state_province") else [],
                zip_code=[rd["postal_code"]] if rd.get("postal_code") else [],
                country=[rd["country"]] if rd.get("country") else [],
                latitude=lat,
                longitude=lon,
                dates_visited=rd.get("dates_visited", []),
                photo_directory=rd.get("photo_directory", ""),
                location_confidence_percent=rd.get("confidence_score", 0),
                confidence_source=rd.get("confidence_source"),
            )
        )

    staged_candidates = []
    if staging_service is not None:
        try:
            # Wipe any previous uncommitted staging progress for tenant
            with contextlib.suppress(Exception):
                await staging_service.wipe_active_session(user.id)

            staged_candidates = list(
                await staging_service.stage_records(user.id, created_job.id, export_records)
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).exception("StagingService.stage_records failed: %s", exc)

    if staged_candidates:
        dup_payloads = [
            {
                "row_number": c.row_index + 1,
                "raw_name": c.poi_name,
                "candidate_poi_id": str(c.id),
                "match_type": "POTENTIAL_DUPLICATE",
                "similarity_score": 0.0,
                "distance_meters": 0.0,
                "triage_status": "PENDING_REVIEW",
                "staged_poi_data": {
                    "name": c.poi_name,
                    "address": c.street_address or "",
                    "city": c.city or "",
                    "latitude": float(c.latitude) if c.latitude is not None else None,
                    "longitude": float(c.longitude) if c.longitude is not None else None,
                },
            }
            for c in staged_candidates
            if c.recommended_disposition != IngestDisposition.ACCEPT
        ]
        created_job.processed_rows = len(staged_candidates)
        created_job.duplicate_payloads = dup_payloads
        created_job.job_status = IngestJobStatus.COMPLETED
        with contextlib.suppress(Exception):
            await ingest_repo.increment_processed_rows(
                created_job.id, user.id, len(staged_candidates)
            )
            await ingest_repo.update_job_status(created_job.id, user.id, IngestJobStatus.COMPLETED)

    # Prepare SQS messages with trace attributes
    trace_ctx = _extract_or_generate_trace_context(request)
    trace_attrs = {
        "traceparent": trace_ctx["traceparent"],
        "X-Amzn-Trace-Id": trace_ctx["X-Amzn-Trace-Id"],
        "user_id": str(user.id),
        "job_id": str(created_job.id),
    }

    queue_name = os.getenv("INGEST_QUEUE_NAME", "vistarae-ingest-local")

    # Partition rows 1:1 and dispatch in batches of up to 10
    messages: list[dict[str, Any]] = []
    for row in parsed_rows:
        body = {
            "job_id": str(created_job.id),
            "user_id": str(user.id),
            "target_list_id": str(target_list_id) if target_list_id else None,
            "absolute_row_number": row["absolute_row_number"],
            "row_data": row["row_data"],
        }
        messages.append(
            {
                "Id": f"row-{row['absolute_row_number']}",
                "MessageBody": body,
                "MessageAttributes": trace_attrs,
            }
        )

    # Send in chunks of 10
    with contextlib.suppress(Exception):
        for i in range(0, len(messages), 10):
            batch = messages[i : i + 10]
            await queue_port.send_message_batch(queue_name, batch)

    return IngestUploadResponse(
        job_id=created_job.id,
        job_status=created_job.job_status,
        total_rows=created_job.total_rows,
        message="CSV upload accepted for asynchronous batch processing.",
    )


@router.post(
    "/api/v1/ingest/upload-flexible",
    summary="Accept multi-format file upload with format sniffing, column alignment, and pre-validation",
)
async def upload_flexible(
    request: Request,
    file: Annotated[UploadFile, File(description="CSV, JSON, or YAML file to ingest")],
    skip_invalid_rows: Annotated[bool, Form()] = False,
    column_mappings: Annotated[str | None, Form()] = None,
    recalculate_fields: Annotated[str | None, Form()] = None,
    target_list_id: Annotated[UUID | None, Form()] = None,
    target_list_name: Annotated[str | None, Form()] = None,
    tag_action: Annotated[str | None, Form()] = None,
    user: User = Depends(get_current_user),
    ingest_repo: IIngestJobRepository = Depends(get_ingest_repo),
    list_repo: IListRepository = Depends(get_list_repo),
    staging_service: StagingService = Depends(get_staging_service),
) -> JSONResponse:
    """Handles multi-format uploads, column mapping detection, and pre-validation reporting (T-018)."""
    file_bytes = await file.read()
    filename = file.filename or "uploaded_file.csv"

    mappings_dict: dict[str, str] | None = None
    if column_mappings:
        try:
            import json

            mappings_dict = json.loads(column_mappings)
        except Exception:
            mappings_dict = None

    # Step 1: Inspect headers and detect unmapped columns
    raw_headers, unmapped, samples = POIImporter.inspect_headers_and_samples(
        content=file_bytes,
        filename=filename,
        column_mappings=mappings_dict,
    )

    job_id = uuid.uuid4()

    if unmapped:
        sample_rows_list = [
            {"column": col, "sample_values": samples.get(col, [])} for col in unmapped
        ]
        return JSONResponse(
            status_code=200,
            content={
                "status": "NEEDS_COLUMN_MAPPING",
                "job_id": str(job_id),
                "unmapped_columns": unmapped,
                "sample_rows": sample_rows_list,
                "target_fields": POIExchangeRecord.get_export_field_names(),
            },
        )

    # Step 2: Parse and execute type/range pre-validation
    records, _, issues = POIImporter.parse_file_bytes(
        content=file_bytes,
        filename=filename,
        column_mappings=mappings_dict,
        skip_invalid_rows=skip_invalid_rows,
    )

    if issues and not skip_invalid_rows:
        return JSONResponse(
            status_code=422,
            content={
                "error_type": "VALIDATION_ERROR",
                "total_rows": len(records) + len(issues),
                "invalid_row_count": len(issues),
                "can_skip_invalid": True,
                "issues": [issue.model_dump() for issue in issues],
            },
        )

    # Step 3: Check unapproved tags (Early Tag Validation Dialog REQ-VAL-001)
    unapproved_tags = await staging_service.get_unapproved_tags(user.id, records)
    if unapproved_tags:
        if not tag_action:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "NEEDS_TAG_APPROVAL",
                    "job_id": str(job_id),
                    "unapproved_tags": unapproved_tags,
                    "total_unapproved_count": len(unapproved_tags),
                },
            )
        if tag_action == "ABORT":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ABORTED",
                    "job_id": str(job_id),
                    "message": "Import aborted by user during tag validation.",
                },
            )
        action_enum = TagResolutionAction(tag_action)
        records = await staging_service.resolve_unapproved_tags(
            user.id, records, action_enum, list(unapproved_tags.keys())
        )

    # Step 4: Create job and stage records
    job = IngestJob(
        id=job_id,
        user_id=user.id,
        job_status=IngestJobStatus.PENDING,
        total_rows=len(records),
        processed_rows=0,
        duplicate_payloads=[],
        target_list_id=target_list_id,
        error_summary=[],
    )
    await ingest_repo.create_job(job)

    await staging_service.stage_exchange_records(user.id, job_id, records)

    return JSONResponse(
        status_code=200,
        content={
            "status": "QUEUED",
            "job_id": str(job_id),
            "total_rows": len(records),
        },
    )
