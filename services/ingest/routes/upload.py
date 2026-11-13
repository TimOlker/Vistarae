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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import IngestJob, User
from vistarae_core.domain.enums import TagResolutionAction
from vistarae_core.domain.value_objects import IngestJobStatus
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


async def _run_background_staging(
    user_id: UUID,
    job_id: UUID,
    records: list[POIExportRecord],
) -> None:
    """Asynchronously stages CSV records into ingest_candidates with rate-limited geocaching (Option A)."""
    import logging

    from vistarae_core.adapters.db.session import get_session_factory

    from services.ingest.dependencies import create_staging_service

    logger = logging.getLogger(__name__)
    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local")).lower()
    if stage == "testing":
        logger.info("STAGE is 'testing'; skipping background database staging task.")
        return

    try:
        session_factory = get_session_factory()
    except Exception as exc:
        logger.warning("Could not obtain session factory for background staging: %s", exc)
        return

    try:
        async with session_factory() as bg_session:
            staging_svc = create_staging_service(bg_session)
            await staging_svc.stage_records_progressive(
                user_id=user_id,
                job_id=job_id,
                records=records,
                session=bg_session,
            )
    except Exception as exc:
        logger.exception("Background staging failed for job %s: %s", job_id, exc)


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
    background_tasks: BackgroundTasks,
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
    session: AsyncSession = Depends(get_db_session),
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

    try:
        if staging_service is not None:
            await staging_service.wipe_active_session(user.id)

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
    except Exception as exc:
        if session is not None and hasattr(session, "rollback"):
            await session.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://api.vistarae.com/errors/internal-server-error",
                "title": "Ingest Staging Failed",
                "status": 500,
                "detail": f"Failed to stage CSV records: {exc}",
                "instance": request.url.path,
            },
            headers={"Content-Type": "application/problem+json"},
        )

    # Convert parsed rows to POIExportRecord objects
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

        def _parse_uuid(val: Any) -> uuid.UUID | None:
            if not val:
                return None
            try:
                return uuid.UUID(str(val).strip())
            except Exception:
                return None

        rec_duration = None
        if rd.get("recommended_duration_hours"):
            with contextlib.suppress(Exception):
                rec_duration = Decimal(str(rd["recommended_duration_hours"]).strip())

        rec_days = None
        if rd.get("recommended_visit_days"):
            with contextlib.suppress(Exception):
                rec_days = int(str(rd["recommended_visit_days"]).strip())

        export_records.append(
            POIExportRecord(
                poi_name=rd.get("poi_name") or rd.get("name", "Unknown"),
                street_address=[rd["street_address"]] if rd.get("street_address") else [],
                town_city=[rd["city"]] if rd.get("city") else [],
                state_province=[rd["state_province"]] if rd.get("state_province") else [],
                zip_code=[rd["postal_code"]] if rd.get("postal_code") else [],
                country=[rd["country"]] if rd.get("country") else [],
                tags=rd.get("tags") or [],
                latitude=lat,
                longitude=lon,
                dates_visited=rd.get("dates_visited", []),
                photo_directory=rd.get("photo_directory", ""),
                photo_directories=rd.get("photo_directories") or [],
                location_confidence_percent=rd.get("confidence_score", 0),
                confidence_source=rd.get("confidence_source"),
                candidate_id=_parse_uuid(rd.get("candidate_id")),
                parent_candidate_id=_parse_uuid(rd.get("parent_candidate_id")),
                parent_poi_id=_parse_uuid(rd.get("parent_poi_id")),
                matched_existing_poi_id=_parse_uuid(rd.get("matched_existing_poi_id")),
                merge_target_id=_parse_uuid(rd.get("merge_target_id")),
                locality=rd.get("locality") or None,
                admin_level_1=rd.get("admin_level_1") or None,
                admin_level_2=rd.get("admin_level_2") or None,
                country_code=rd.get("country_code") or None,
                description=rd.get("description") or None,
                reason_to_visit=rd.get("reason_to_visit") or None,
                hero_image_url=rd.get("hero_image_url") or None,
                official_url=rd.get("official_url") or None,
                wiki_url=rd.get("wiki_url") or None,
                related_websites=rd.get("related_websites") or [],
                no_websites=bool(rd.get("no_websites", False)),
                recommended_duration_hours=rec_duration,
                recommended_visit_days=rec_days,
                estimated_visit_time_notes=rd.get("estimated_visit_time_notes") or None,
                recommended_disposition=rd.get("recommended_disposition") or None,
                user_disposition=rd.get("user_disposition") or None,
                disposition_justification=rd.get("disposition_justification") or None,
                is_user_overridden=bool(rd.get("is_user_overridden", False)),
                raw_geocoding=rd.get("raw_geocoding") or None,
            )
        )

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

    # Commit the IngestJob immediately so GET /api/ingest/jobs/{job_id} finds it right away
    if session is not None and hasattr(session, "commit"):
        await session.commit()

    # Launch asynchronous background staging (Option A)
    if staging_service is not None:
        background_tasks.add_task(
            _run_background_staging,
            user_id=user.id,
            job_id=created_job.id,
            records=export_records,
        )

    return IngestUploadResponse(
        job_id=created_job.id,
        job_status=created_job.job_status
        if isinstance(getattr(created_job, "job_status", None), IngestJobStatus)
        else IngestJobStatus.PENDING,
        total_rows=created_job.total_rows,
        message="CSV upload accepted for asynchronous batch processing.",
    )


async def _run_background_flexible_staging(
    user_id: UUID,
    job_id: UUID,
    records: list[POIExchangeRecord],
) -> None:
    """Asynchronously stages exchange records with rate-limited geocaching."""
    import logging

    from vistarae_core.adapters.db.session import get_session_factory

    from services.ingest.dependencies import create_staging_service

    logger = logging.getLogger(__name__)
    stage = os.getenv("STAGE", os.getenv("APP_ENV", "local")).lower()
    if stage == "testing":
        logger.info("STAGE is 'testing'; skipping background database staging task.")
        return

    try:
        session_factory = get_session_factory()
    except Exception as exc:
        logger.warning("Could not obtain session factory for flexible background staging: %s", exc)
        return

    try:
        async with session_factory() as bg_session:
            staging_svc = create_staging_service(bg_session)
            await staging_svc.stage_exchange_records(
                user_id=user_id,
                job_id=job_id,
                records=records,
            )
            await bg_session.commit()
    except Exception as exc:
        logger.exception("Flexible background staging failed for job %s: %s", job_id, exc)


@router.post(
    "/api/v1/ingest/upload-flexible",
    summary="Accept multi-format file upload with format sniffing, column alignment, and pre-validation",
)
async def upload_flexible(
    request: Request,
    file: Annotated[UploadFile, File(description="CSV, JSON, or YAML file to ingest")],
    background_tasks: BackgroundTasks,
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
    session: AsyncSession = Depends(get_db_session),
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
    if session is not None and hasattr(session, "commit"):
        await session.commit()

    background_tasks.add_task(
        _run_background_flexible_staging,
        user_id=user.id,
        job_id=job_id,
        records=records,
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "QUEUED",
            "job_id": str(job_id),
            "total_rows": len(records),
        },
    )
