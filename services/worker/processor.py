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

"""Batch ingestion SQS consumer worker (T-026).

Implements BatchIngestWorker:
- Extracts W3C traceparent and X-Amzn-Trace-Id into OpenTelemetry spans (REQ-WORKER-001)
- Record-level idempotency via synthetic SHA-256 keys (REQ-WORKER-002, REQ-WORKER-003)
- Cache-first geocoding with 1.0 req/sec pacing (REQ-WORKER-004, REQ-WORKER-006, REQ-WORKER-007)
- Spatial deduplication (similarity >= 0.60 & ST_DWithin) staging to PENDING_REVIEW (REQ-WORKER-009)
- POI persistence with Gemini vector embeddings (thinking_budget=0)
- Partial batch failure reporting via batchItemFailures (REQ-WORKER-010)
- Atomic processed_rows incrementing (REQ-WORKER-011)
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.repositories.ingest_repo import IngestJobRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.domain.entities import POI
from vistarae_core.domain.value_objects import DuplicateTriageStatus, VisitState, WGS84Point
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.repositories import IIngestJobRepository, IPOIRepository
from vistarae_core.services.prompt_cache import UserPromptCache

from services.worker.geocoder import NominatimGeocoder
from services.worker.idempotency import claim_row_idempotency

logger = logging.getLogger(__name__)


def _extract_attr_value(attrs: dict[str, Any], key: str) -> str | None:
    """Extracts string attribute value across Lambda and boto3 SQS formats."""
    if not attrs:
        return None
    val = attrs.get(key)
    if isinstance(val, dict):
        return val.get("stringValue") or val.get("StringValue")
    if isinstance(val, str):
        return val
    return None


class BatchIngestWorker:
    """Asynchronous SQS batch message consumer worker."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        geocoder: NominatimGeocoder,
        embedding_port: IEmbeddingPort,
        ingest_repo_factory: Callable[[AsyncSession], IIngestJobRepository] | None = None,
        poi_repo_factory: Callable[[AsyncSession], IPOIRepository] | None = None,
        prompt_cache: UserPromptCache | None = None,
        orchestrator: Any | None = None,
    ) -> None:
        """Initializes batch ingest worker.

        Args:
            session_factory: Callable returning an active SQLAlchemy AsyncSession.
            geocoder: NominatimGeocoder instance.
            embedding_port: IEmbeddingPort vector generator.
            ingest_repo_factory: Optional custom IngestJobRepository factory.
            poi_repo_factory: Optional custom POIRepository factory.
            prompt_cache: Optional UserPromptCache instance for personalized prompt resolution.
            orchestrator: Optional ScrapingOrchestrator for web enrichment and personalized synthesis.
        """
        self._session_factory = session_factory
        self._geocoder = geocoder
        self._embedding_port = embedding_port
        self._ingest_repo_factory = ingest_repo_factory or IngestJobRepository
        self._poi_repo_factory = poi_repo_factory or SqlAlchemyPOIRepository
        self._prompt_cache = prompt_cache
        self._orchestrator = orchestrator

    async def process_record(  # noqa: C901
        self,
        record: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Processes a single SQS message record within a database transaction.

        Args:
            record: Raw SQS message dictionary.
            session: Active SQLAlchemy AsyncSession.

        Raises:
            Exception: If an unhandled transient failure occurs (triggering partial retry).
        """
        raw_body = record.get("body", record.get("Body", "{}"))
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

        job_id = UUID(str(body["job_id"]))
        user_id = UUID(str(body["user_id"]))
        absolute_row_number = int(body["absolute_row_number"])
        target_list_id = UUID(str(body["target_list_id"])) if body.get("target_list_id") else None
        row_data = body.get("row_data", {})

        # Extract trace context
        attrs = record.get("messageAttributes", record.get("MessageAttributes", {}))
        traceparent = _extract_attr_value(attrs, "traceparent") or "00-local-span-01"
        amzn_trace_id = _extract_attr_value(attrs, "X-Amzn-Trace-Id") or "Root=1-local"

        logger.info(
            "INCOMING | TraceID=%s | AmznID=%s | Source=queue -> Destination=worker | Job=%s Row=%d",
            traceparent,
            amzn_trace_id,
            job_id,
            absolute_row_number,
        )

        ingest_repo = self._ingest_repo_factory(session)
        poi_repo = self._poi_repo_factory(session)

        # 1. Record-level idempotency
        is_new = await claim_row_idempotency(session, user_id, job_id, absolute_row_number)
        if not is_new:
            logger.info(
                "Skipping duplicate row %d for job %s (already processed)",
                absolute_row_number,
                job_id,
            )
            return

        # 2. Extract or resolve coordinates
        lat: float | None = None
        lon: float | None = None
        address = row_data.get("address", "")
        raw_name = row_data.get("name", "Unknown").strip()

        if row_data.get("latitude") and row_data.get("longitude"):
            try:
                lat = float(row_data["latitude"])
                lon = float(row_data["longitude"])
            except (ValueError, TypeError):
                lat = None
                lon = None

        if lat is None or lon is None:
            address_to_query = address or raw_name
            geo_res = await self._geocoder.geocode(address_to_query)
            if geo_res is not None:
                lat, lon, resolved_addr = geo_res
                address = resolved_addr or address
            else:
                # Permanent row failure: record in error_summary and increment processed_rows
                error_obj = {
                    "row_number": absolute_row_number,
                    "raw_name": raw_name,
                    "error_type": "GEOCODING_NOT_FOUND",
                    "detail": f"OpenStreetMap Nominatim could not resolve address '{address_to_query}'",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                await ingest_repo.append_error_summary(job_id, user_id, error_obj)
                await ingest_repo.increment_processed_rows(job_id, user_id, 1)
                return

        # Validate coordinates bounds
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            error_obj = {
                "row_number": absolute_row_number,
                "raw_name": raw_name,
                "error_type": "INVALID_COORDINATES",
                "detail": f"Coordinates out of bounds: lat={lat}, lon={lon}",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await ingest_repo.append_error_summary(job_id, user_id, error_obj)
            await ingest_repo.increment_processed_rows(job_id, user_id, 1)
            return

        point = WGS84Point(lon=lon, lat=lat)

        # 3. Spatial deduplication check
        matches = await poi_repo.find_potential_duplicates(
            user_id=user_id,
            name=raw_name,
            point=point,
            radius_meters=805.0,  # Urban preset (~0.5 miles)
            similarity_threshold=0.60,
        )

        # Resolve prompt directives for user if cache is configured
        prompt_directives: dict[str, str] = {}
        if self._prompt_cache:
            try:
                cached = self._prompt_cache.get(user_id)
                if cached:
                    prompt_directives = {
                        (k.value if hasattr(k, "value") else str(k)): v for k, v in cached.items()
                    }
            except Exception:
                logger.warning("Failed to retrieve prompt directives for user %s", user_id)

        description = row_data.get("description")
        reason_to_visit = row_data.get("reason_to_visit") or row_data.get("why_visit")
        recommended_duration_hours = (
            float(row_data["recommended_duration_hours"])
            if row_data.get("recommended_duration_hours")
            else None
        )
        estimated_visit_time_notes = row_data.get("estimated_visit_time_notes")

        if self._orchestrator:
            url = row_data.get("url") or row_data.get("source_url")
            if url:
                extracted = await self._orchestrator.extract_from_url(
                    url=url,
                    user_directives=prompt_directives,
                )
                if extracted:
                    if not description and extracted.description:
                        description = extracted.description
                    if not reason_to_visit and extracted.reason_to_visit:
                        reason_to_visit = extracted.reason_to_visit
                    if recommended_duration_hours is None and getattr(
                        extracted, "estimated_duration_hours", None
                    ):
                        recommended_duration_hours = extracted.estimated_duration_hours
                    elif recommended_duration_hours is None and getattr(
                        extracted, "recommended_duration_hours", None
                    ):
                        recommended_duration_hours = extracted.recommended_duration_hours
                    if not estimated_visit_time_notes and getattr(
                        extracted, "estimated_visit_time_notes", None
                    ):
                        estimated_visit_time_notes = extracted.estimated_visit_time_notes
            elif prompt_directives and not reason_to_visit and description:
                if hasattr(self._orchestrator, "synthesize_reason_to_visit"):
                    reason_to_visit = await self._orchestrator.synthesize_reason_to_visit(
                        name=raw_name,
                        description=description,
                        reason_directive=prompt_directives.get("reason_to_visit"),
                    )

        if matches:
            best = matches[0]
            staged_poi_data = {
                "name": raw_name,
                "description": description or "",
                "reason_to_visit": reason_to_visit or "",
                "estimated_visit_time_notes": estimated_visit_time_notes or None,
                "address": address,
                "city": row_data.get("city", ""),
                "states": [row_data["state"]] if row_data.get("state") else [],
                "countries": [row_data["country"]] if row_data.get("country") else [],
                "latitude": lat,
                "longitude": lon,
                "visited_date": row_data.get("visited_date"),
                "tags": [t.strip() for t in row_data.get("tags", "").split(",") if t.strip()],
            }
            dup_item = {
                "row_number": absolute_row_number,
                "raw_name": raw_name,
                "candidate_poi_id": str(best.existing_poi.id),
                "match_type": "POTENTIAL_DUPLICATE",
                "similarity_score": round(best.name_similarity, 2),
                "distance_meters": round(best.distance_meters, 1),
                "triage_status": DuplicateTriageStatus.PENDING_REVIEW.value,
                "staged_poi_data": staged_poi_data,
            }
            await ingest_repo.append_duplicate_payload(job_id, user_id, dup_item)
            await ingest_repo.increment_processed_rows(job_id, user_id, 1)
            return

        # 4. Unique POI persistence
        emb_text = f"{raw_name} {description or ''} {reason_to_visit or ''}".strip()
        embedding = await self._embedding_port.generate_embedding(emb_text)

        visited_date = row_data.get("visited_date")
        visit_state = VisitState.VISITED_RETURN if visited_date else VisitState.NOT_VISITED
        visited_dates = [visited_date] if visited_date else []

        poi_id = uuid.uuid4()
        poi = POI(
            id=poi_id,
            user_id=user_id,
            name=raw_name,
            geom=point,
            description=description,
            reason_to_visit=reason_to_visit,
            address=address,
            city=row_data.get("city"),
            states=[row_data["state"]] if row_data.get("state") else [],
            countries=[row_data["country"]] if row_data.get("country") else [],
            visited_dates=visited_dates,
            visit_state=visit_state,
            recommended_duration_hours=recommended_duration_hours,
            estimated_visit_time_notes=estimated_visit_time_notes,
            embedding=embedding,
        )
        await poi_repo.create(poi)

        # Attach to target list if specified
        if target_list_id:
            await poi_repo.bulk_attach_lists(user_id, [poi_id], [target_list_id])

        # Atomically increment processed rows
        await ingest_repo.increment_processed_rows(job_id, user_id, 1)

    async def process_batch(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Processes a batch of SQS message records, returning partial batch failures.

        Args:
            records: List of SQS message dictionaries from event or client.

        Returns:
            Dict in standard AWS format: {"batchItemFailures": [{"itemIdentifier": msg_id}]}.
        """
        batch_item_failures: list[dict[str, str]] = []

        for record in records:
            msg_id = str(record.get("messageId", record.get("MessageId", uuid.uuid4())))
            session = self._session_factory()
            try:
                async with session, session.begin():
                    await self.process_record(record, session)
            except Exception as exc:
                logger.exception("Transient failure processing message %s: %s", msg_id, exc)
                batch_item_failures.append({"itemIdentifier": msg_id})

        return {"batchItemFailures": batch_item_failures}
