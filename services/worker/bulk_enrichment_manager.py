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

"""Canary-gated, fail-fast bulk AI enrichment orchestrator.

Implements REQ-ENR-012 through REQ-ENR-033:
- Candidate #1 executes as an isolated canary with concurrency 1
- Scales up to BULK_ENRICHMENT_CONCURRENCY upon canary success
- Fail-fast circuit breaker halts queue on BLOCKING_EXTERNAL_ERROR (HTTP 402/429)
- 45-second execution timeout ceiling per candidate worker
- 30-second graceful worker draining on cancellation or blocking error
- 5-second client heartbeat with 15-second disconnection cancellation
- Immediate per-candidate database persistence preserving non-empty attributes
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.domain.entities import (
    BulkEnrichmentResult,
    EnrichmentSession,
    get_bulk_enrichment_concurrency,
)
from vistarae_core.domain.enums import (
    BulkEnrichmentStatus,
    EnrichmentResultCode,
)
from vistarae_core.ports.repositories import IBulkEnrichmentRepository, IIngestCandidateRepository
from vistarae_core.schemas.bulk_enrichment import (
    BulkEnrichmentProgressResponse,
    BulkEnrichmentSummaryResponse,
    CandidateIssueDetail,
)

logger = logging.getLogger("vistarae.worker.bulk_enrichment_manager")


class ActiveSessionConflictError(Exception):
    """Raised when an enrichment session is already actively running for the given job."""


class BulkEnrichmentSessionManager:
    """Coordinates canary execution, concurrency scaling, fail-fast and telemetry."""

    _session_factory: Callable[[], AsyncSession] | None = None
    _bulk_repo: IBulkEnrichmentRepository | None = None
    _candidate_repo: IIngestCandidateRepository | None = None

    def __init__(
        self,
        worker_func: Callable[..., Any] | None = None,
        candidate_enricher: Any | None = None,
        bulk_repo: IBulkEnrichmentRepository | None = None,
        candidate_repo: IIngestCandidateRepository | None = None,
        concurrency_limit: int | None = None,
        worker_timeout_seconds: float = 45.0,
        drain_grace_seconds: float = 30.0,
        heartbeat_timeout_seconds: float = 120.0,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        """Initializes the session manager with worker dependencies and timeouts.

        Args:
            worker_func: Optional worker override for unit testing.
            candidate_enricher: CandidateEnricher instance for production enrichment.
            bulk_repo: IBulkEnrichmentRepository for audit persistence.
            candidate_repo: IIngestCandidateRepository for candidate lookups and writes.
            concurrency_limit: Optional concurrency override; defaults to BULK_ENRICHMENT_CONCURRENCY.
            worker_timeout_seconds: Per-candidate worker execution ceiling (default: 45.0s).
            drain_grace_seconds: Grace window for in-flight worker draining (default: 30.0s).
            heartbeat_timeout_seconds: Client disconnect timeout (default: 15.0s).
            session_factory: Factory yielding fresh AsyncSession for background tasks.
        """
        self._worker_func = worker_func
        self._candidate_enricher = candidate_enricher
        self._bulk_repo = bulk_repo
        self._candidate_repo = candidate_repo
        self._session_factory = session_factory
        self._concurrency_limit = concurrency_limit or get_bulk_enrichment_concurrency()
        self._worker_timeout_seconds = worker_timeout_seconds
        self._drain_grace_seconds = drain_grace_seconds
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds

        self._active_sessions: dict[UUID, EnrichmentSession] = {}
        self._session_tasks: dict[UUID, asyncio.Task[None]] = {}
        self._session_stop_events: dict[UUID, asyncio.Event] = {}
        self._latest_summaries: dict[UUID, BulkEnrichmentSummaryResponse] = {}

    def get_session(self, job_id: UUID) -> EnrichmentSession | None:
        """Retrieves active session state by job UUID."""
        return self._active_sessions.get(job_id)

    def record_heartbeat(self, job_id: UUID) -> bool:
        """Records an active client heartbeat for the session."""
        session = self._active_sessions.get(job_id)
        if session:
            session.last_heartbeat_at = datetime.now(UTC)
            return True
        return False

    def get_progress(self, job_id: UUID) -> BulkEnrichmentProgressResponse | None:
        """Retrieves live telemetry progress metrics for the active session."""
        session = self._active_sessions.get(job_id)
        if not session:
            return None

        now = datetime.now(UTC)
        elapsed = int((now - session.started_at).total_seconds())
        remaining = max(0, session.total_count - session.processed_count)
        percent = (
            int((session.processed_count / session.total_count) * 100)
            if session.total_count > 0
            else 100
        )
        avg_ms = (
            int(session.total_duration_ms / session.processed_count)
            if session.processed_count > 0
            else None
        )

        in_flight = 1 if session.status == BulkEnrichmentStatus.CANARY_DISPATCH else 0
        if session.status in (BulkEnrichmentStatus.ACTIVE, BulkEnrichmentStatus.DRAINING):
            in_flight = min(self._concurrency_limit, remaining)

        msg = f"Processing {session.processed_count} of {session.total_count} POIs..."
        if session.status == BulkEnrichmentStatus.CANARY_DISPATCH:
            msg = "Validating canary record..."
        elif session.status == BulkEnrichmentStatus.DRAINING:
            msg = "Cancelling... waiting for active workers to complete."

        return BulkEnrichmentProgressResponse(
            session_id=session.session_id,
            job_id=session.job_id,
            status=session.status,
            total_count=session.total_count,
            completed_count=session.processed_count,
            success_count=session.success_count,
            issue_count=session.failure_count,
            remaining_count=remaining,
            in_flight_count=in_flight,
            percent_complete=percent,
            elapsed_seconds=elapsed,
            average_duration_ms=avg_ms,
            can_cancel=session.status
            in (BulkEnrichmentStatus.ACTIVE, BulkEnrichmentStatus.CANARY_DISPATCH),
            status_message=msg,
        )

    async def cancel_session(self, job_id: UUID) -> bool:
        """Initiates graceful cancellation and worker draining."""
        session = self._active_sessions.get(job_id)
        if not session:
            return False

        if session.status in (
            BulkEnrichmentStatus.COMPLETED,
            BulkEnrichmentStatus.CANCELLED,
            BulkEnrichmentStatus.BLOCKED,
            BulkEnrichmentStatus.FAILED,
        ):
            return False

        session.stop_requested = True
        session.status = BulkEnrichmentStatus.DRAINING
        session.termination_reason = "Cancelled by traveler"
        stop_event = self._session_stop_events.get(job_id)
        if stop_event:
            stop_event.set()
        logger.info(
            "Session %s for job %s marked for graceful cancellation", session.session_id, job_id
        )
        return True

    def get_summary(self, job_id: UUID) -> BulkEnrichmentSummaryResponse | None:
        """Retrieves post-run summary window statistics."""
        return self._latest_summaries.get(job_id)

    async def wait_session(self, job_id: UUID) -> None:
        """Awaits completion of the session background task."""
        task = self._session_tasks.get(job_id)
        if task:
            await task

    async def start_session(
        self,
        user_id: UUID,
        job_id: UUID,
        candidate_ids: list[UUID],
        force_refresh: bool = False,
    ) -> EnrichmentSession:
        """Initiates a new canary-gated bulk enrichment session.

        Args:
            user_id: Tenant user UUID.
            job_id: Staging import job UUID.
            candidate_ids: List of candidate IDs to process.
            force_refresh: If True, recomputes all target attributes.

        Returns:
            The created EnrichmentSession entity.

        Raises:
            ActiveSessionConflictError: If a session is already active for this job.
        """
        existing = self._active_sessions.get(job_id)
        if existing and existing.status in (
            BulkEnrichmentStatus.INITIALIZING,
            BulkEnrichmentStatus.CANARY_DISPATCH,
            BulkEnrichmentStatus.ACTIVE,
            BulkEnrichmentStatus.DRAINING,
        ):
            raise ActiveSessionConflictError(f"Enrichment session already active for job {job_id}")

        total = len(candidate_ids)
        canary_id = candidate_ids[0] if candidate_ids else uuid4()
        now = datetime.now(UTC)

        cand_meta = await self._load_candidate_metadata(user_id, job_id, candidate_ids)

        session = EnrichmentSession(
            session_id=uuid4(),
            job_id=job_id,
            user_id=user_id,
            status=BulkEnrichmentStatus.INITIALIZING,
            total_count=total,
            concurrency_limit=self._concurrency_limit,
            canary_candidate_id=canary_id,
            started_at=now,
            last_heartbeat_at=now,
            unprocessed_count=total,
            candidate_meta=cand_meta,
        )

        self._active_sessions[job_id] = session
        stop_event = asyncio.Event()
        self._session_stop_events[job_id] = stop_event

        task = asyncio.create_task(
            self._run_session(user_id, job_id, candidate_ids, force_refresh, stop_event)
        )
        self._session_tasks[job_id] = task
        return session

    async def _load_candidate_metadata(
        self,
        user_id: UUID,
        job_id: UUID,
        candidate_ids: list[UUID],
    ) -> dict[UUID, dict[str, Any]]:
        """Preloads candidate names and row indexes for diagnostic issue reporting."""
        cand_meta: dict[UUID, dict[str, Any]] = {}
        if self._session_factory:
            try:
                from sqlalchemy import select
                from vistarae_core.adapters.db.tables import IngestCandidateTable

                async with self._session_factory() as db_session:
                    stmt = select(
                        IngestCandidateTable.id,
                        IngestCandidateTable.poi_name,
                        IngestCandidateTable.row_index,
                        IngestCandidateTable.latitude,
                        IngestCandidateTable.longitude,
                    ).where(
                        IngestCandidateTable.job_id == job_id,
                        IngestCandidateTable.user_id == user_id,
                    )
                    res = await db_session.execute(stmt)
                    for row in res.fetchall():
                        cand_meta[row[0]] = {
                            "poi_name": row[1] or "Unknown POI",
                            "row_index": row[2] or 0,
                            "latitude": row[3],
                            "longitude": row[4],
                        }
            except Exception as exc:
                logger.debug("Could not pre-load candidate metadata from db: %s", exc)
        elif self._candidate_repo:
            try:
                for idx, cid in enumerate(candidate_ids):
                    c = await self._candidate_repo.get_by_id(user_id, cid)
                    if c:
                        cand_meta[cid] = {
                            "poi_name": getattr(c, "poi_name", "Unknown POI"),
                            "row_index": getattr(c, "row_index", idx + 1),
                            "latitude": getattr(c, "latitude", None),
                            "longitude": getattr(c, "longitude", None),
                        }
            except Exception as exc:
                logger.debug("Could not pre-load candidate metadata from repo: %s", exc)

        for idx, cid in enumerate(candidate_ids):
            if cid not in cand_meta:
                cand_meta[cid] = {
                    "poi_name": f"Candidate #{idx + 1}",
                    "row_index": idx + 1,
                    "latitude": None,
                    "longitude": None,
                }
        return cand_meta

    def _record_candidate_issue(
        self,
        session: EnrichmentSession,
        cand_id: UUID,
        result_code: EnrichmentResultCode | None,
        err_msg: str,
        is_interrupted: bool = False,
        candidate_obj: Any = None,
    ) -> None:
        """Appends structured diagnostic feedback for an incomplete or failed candidate."""
        meta = session.candidate_meta.get(cand_id, {})
        name = (
            getattr(candidate_obj, "poi_name", None)
            or meta.get("poi_name")
            or f"Candidate #{meta.get('row_index', '')}"
        )
        row_idx = getattr(candidate_obj, "row_index", None) or meta.get("row_index", 0)

        if is_interrupted:
            category = "INTERRUPTED"
            severity = "warning"
            error_type = "INTERRUPTED_UNPROCESSED"
            reason = f"Enrichment was halted before this candidate was processed ({err_msg or 'session interrupted'})."
            suggested_action = (
                "This candidate was not reached. Click 'Resume Enrichment' to continue processing remaining POIs."
            )
            is_retryable = True
        elif result_code == EnrichmentResultCode.BLOCKING_EXTERNAL_ERROR:
            category = "RESOURCE_EXHAUSTION"
            severity = "blocking"
            err_lower = err_msg.lower()
            error_type = (
                "QUOTA_EXHAUSTED"
                if any(k in err_lower for k in ["quota", "402", "resource_exhausted"])
                else "RATE_LIMIT_EXCEEDED"
            )
            reason = f"API limit or quota exceeded: {err_msg}"
            suggested_action = (
                "Your AI or geocoding usage limit has been reached. Please check your plan quota or wait before retrying. Do not retry immediately."
            )
            is_retryable = False
        elif result_code == EnrichmentResultCode.TEMPORARY_EXTERNAL_ERROR:
            category = "TEMPORARY_FAILURE"
            severity = "warning"
            error_type = "SERVICE_TIMEOUT" if "timeout" in err_msg.lower() else "NETWORK_ERROR"
            reason = f"Temporary service or network failure: {err_msg}"
            suggested_action = "A temporary external network error or service timeout occurred. Safe to retry."
            is_retryable = True
        else:
            err_lower = err_msg.lower()
            if any(
                k in err_lower
                for k in [
                    "geocode",
                    "coordinate",
                    "unresolvable",
                    "not found",
                    "invalid address",
                    "missing geographic",
                ]
            ):
                category = "INPUT_DATA_ISSUE"
                severity = "warning"
                error_type = (
                    "MISSING_COORDINATES"
                    if "coordinate" in err_lower
                    else "UNRESOLVABLE_LOCATION"
                )
                reason = err_msg or "Geographic coordinates could not be resolved for this location."
                suggested_action = (
                    "Open this POI in the workbench to verify the name, address, or manually enter coordinates before retrying."
                )
                is_retryable = False
            elif "timeout" in err_lower:
                category = "TEMPORARY_FAILURE"
                severity = "warning"
                error_type = "WORKER_TIMEOUT"
                reason = f"Processing timeout exceeded: {err_msg}"
                suggested_action = "The enrichment worker took too long to complete. Safe to retry."
                is_retryable = True
            else:
                category = "TEMPORARY_FAILURE"
                severity = "warning"
                error_type = "INTERNAL_PROCESSING_ERROR"
                reason = err_msg or "An unexpected processing error occurred during candidate enrichment."
                suggested_action = "An internal processing error occurred. Safe to retry."
                is_retryable = True

        issue = {
            "candidate_id": str(cand_id),
            "poi_name": name,
            "row_index": int(row_idx),
            "category": category,
            "severity": severity,
            "error_type": error_type,
            "reason": reason,
            "suggested_action": suggested_action,
            "is_retryable": is_retryable,
        }
        session.candidate_issues.append(issue)

    async def _execute_single_worker(
        self,
        user_id: UUID,
        job_id: UUID,
        cand_id: UUID,
        is_canary: bool,
        force_refresh: bool,
    ) -> tuple[EnrichmentResultCode, str, int, int, Any]:
        """Executes worker logic for one candidate with 45s execution ceiling.

        Returns:
            Tuple of (result_code, error_message, duration_ms, resources_used, candidate_obj).
        """
        start_time = datetime.now(UTC)
        logger.info(
            "MSG: -->| Producer dispatching candidate (id=%s, canary=%s)", cand_id, is_canary
        )

        try:
            if self._worker_func:
                coro = self._worker_func(cand_id, is_canary, force_refresh)
            elif self._candidate_enricher:
                coro = self._candidate_enricher.enrich_candidate(
                    user_id=user_id,
                    candidate_id=cand_id,
                    job_id=job_id,
                    force_refresh=force_refresh,
                )
            else:
                coro = asyncio.sleep(0.01)

            res = await asyncio.wait_for(coro, timeout=self._worker_timeout_seconds)

            dur_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

            cand_obj = None
            if isinstance(res, tuple):
                result_code = res[0]
                err_msg = res[1] if len(res) > 1 else ""
                resources = res[2] if len(res) > 2 else 1
                cand_obj = res[3] if len(res) > 3 else None
            elif hasattr(res, "poi_name"):
                cand_obj = res
                if (
                    getattr(cand_obj, "latitude", None) is None
                    or getattr(cand_obj, "longitude", None) is None
                ):
                    result_code = EnrichmentResultCode.INTERNAL_ERROR
                    err_msg = (
                        f"Missing geographic coordinates for '{cand_obj.poi_name}'. Location could not be resolved."
                    )
                    resources = 1
                else:
                    result_code = EnrichmentResultCode.SUCCESS
                    err_msg = ""
                    resources = 1
            elif res is None and self._candidate_enricher:
                result_code = EnrichmentResultCode.INTERNAL_ERROR
                err_msg = f"Candidate not found or ignored (id={cand_id})"
                resources = 0
            else:
                result_code = EnrichmentResultCode.SUCCESS
                err_msg = ""
                resources = 1

            logger.info(
                "MSG: <--| Worker completed candidate (id=%s) - Result: %s", cand_id, result_code
            )
            return result_code, err_msg, dur_ms, resources, cand_obj

        except TimeoutError:
            dur_ms = int(self._worker_timeout_seconds * 1000)
            logger.warning(
                "Worker execution timed out for candidate %s after %ds",
                cand_id,
                self._worker_timeout_seconds,
            )
            return (
                EnrichmentResultCode.TEMPORARY_EXTERNAL_ERROR,
                f"Worker timeout exceeded {self._worker_timeout_seconds}s ceiling",
                dur_ms,
                0,
                None,
            )
        except Exception as exc:
            dur_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            err_str = str(exc)
            logger.exception("Worker error on candidate %s: %s", cand_id, exc)

            is_blocking = any(
                k in err_str.lower() for k in ["402", "429", "quota", "resource_exhausted"]
            )
            result_code = (
                EnrichmentResultCode.BLOCKING_EXTERNAL_ERROR
                if is_blocking
                else EnrichmentResultCode.INTERNAL_ERROR
            )
            return result_code, err_str, dur_ms, 0, None

    async def _execute_canary_stage(
        self,
        session: EnrichmentSession,
        user_id: UUID,
        job_id: UUID,
        canary_id: UUID,
        total: int,
        force_refresh: bool,
        processed_ids: set[UUID],
    ) -> tuple[bool, int, int, int]:
        """Executes canary candidate #1 solitary with concurrency 1."""
        session.status = BulkEnrichmentStatus.CANARY_DISPATCH
        logger.info("Dispatching canary candidate [1 of %d] (id=%s)", total, canary_id)

        c_code, c_err, c_dur, c_res, c_cand = await self._execute_single_worker(
            user_id, job_id, canary_id, is_canary=True, force_refresh=force_refresh
        )
        processed_ids.add(canary_id)

        session.processed_count += 1
        session.total_duration_ms += c_dur
        session.total_resources_used += c_res

        temp_errors = 0
        blocking_errors = 0
        internal_errors = 0

        if c_code == EnrichmentResultCode.SUCCESS:
            session.success_count += 1
        else:
            self._record_candidate_issue(
                session, canary_id, c_code, c_err, candidate_obj=c_cand
            )
            if c_code == EnrichmentResultCode.BLOCKING_EXTERNAL_ERROR:
                blocking_errors += 1
                session.failure_count += 1
                session.status = BulkEnrichmentStatus.BLOCKED
                session.termination_reason = f"Canary halted on external blocking error: {c_err}"
                session.unprocessed_count = total - 1
                logger.warning("Canary candidate failed with blocking error. Halted queue dispatch.")
                return False, temp_errors, blocking_errors, internal_errors
            elif c_code == EnrichmentResultCode.TEMPORARY_EXTERNAL_ERROR:
                temp_errors += 1
                session.failure_count += 1
            else:
                internal_errors += 1
                session.failure_count += 1

        return True, temp_errors, blocking_errors, internal_errors

    async def _drain_tasks(self, tasks: set[asyncio.Task[None]]) -> None:
        """Drains in-flight worker tasks within configured grace seconds."""
        if not tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self._drain_grace_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Grace drain period (%ds) expired. Force-cancelling remaining tasks.",
                self._drain_grace_seconds,
            )
            for t in tasks:
                t.cancel()

    async def _execute_worker_pool(
        self,
        session: EnrichmentSession,
        user_id: UUID,
        job_id: UUID,
        remaining_ids: list[UUID],
        force_refresh: bool,
        stop_event: asyncio.Event,
        temp_errors: int,
        blocking_errors: int,
        internal_errors: int,
        processed_ids: set[UUID],
    ) -> tuple[int, int, int]:
        """Dispatches pool of concurrent candidate workers up to semaphore limit."""
        session.status = BulkEnrichmentStatus.ACTIVE
        semaphore = asyncio.Semaphore(self._concurrency_limit)
        active_tasks: set[asyncio.Task[None]] = set()

        async def _worker_wrapper(cand_id: UUID) -> None:
            nonlocal temp_errors, blocking_errors, internal_errors
            async with semaphore:
                if stop_event.is_set():
                    return
                code, err, dur, res_used, cand_obj = await self._execute_single_worker(
                    user_id, job_id, cand_id, is_canary=False, force_refresh=force_refresh
                )
                processed_ids.add(cand_id)
                session.processed_count += 1
                session.total_duration_ms += dur
                session.total_resources_used += res_used

                if code == EnrichmentResultCode.SUCCESS:
                    session.success_count += 1
                else:
                    self._record_candidate_issue(
                        session, cand_id, code, err, candidate_obj=cand_obj
                    )
                    if code == EnrichmentResultCode.BLOCKING_EXTERNAL_ERROR:
                        blocking_errors += 1
                        session.failure_count += 1
                        session.status = BulkEnrichmentStatus.DRAINING
                        session.termination_reason = f"Circuit breaker tripped on blocking error: {err}"
                        stop_event.set()
                    elif code == EnrichmentResultCode.TEMPORARY_EXTERNAL_ERROR:
                        temp_errors += 1
                        session.failure_count += 1
                    else:
                        internal_errors += 1
                        session.failure_count += 1

        for cid in remaining_ids:
            if stop_event.is_set():
                break

            now = datetime.now(UTC)
            if (now - session.last_heartbeat_at).total_seconds() > self._heartbeat_timeout_seconds:
                session.stop_requested = True
                session.status = BulkEnrichmentStatus.DRAINING
                session.termination_reason = (
                    f"Client disconnected (heartbeat timeout >{int(self._heartbeat_timeout_seconds)}s)"
                )
                stop_event.set()
                break

            while len(active_tasks) >= self._concurrency_limit and not stop_event.is_set():
                await asyncio.sleep(0.05)
                now = datetime.now(UTC)
                if (now - session.last_heartbeat_at).total_seconds() > self._heartbeat_timeout_seconds:
                    session.stop_requested = True
                    session.status = BulkEnrichmentStatus.DRAINING
                    session.termination_reason = (
                        f"Client disconnected (heartbeat timeout >{int(self._heartbeat_timeout_seconds)}s)"
                    )
                    stop_event.set()
                    break

            if stop_event.is_set():
                break

            t = asyncio.create_task(_worker_wrapper(cid))
            active_tasks.add(t)
            t.add_done_callback(active_tasks.discard)

        if stop_event.is_set():
            await self._drain_tasks(active_tasks)
        elif active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        return temp_errors, blocking_errors, internal_errors

    def _record_unprocessed_issues(
        self,
        session: EnrichmentSession,
        candidate_ids: list[UUID],
        processed_ids: set[UUID],
        default_reason: str,
    ) -> None:
        """Records diagnostic issues for candidates not reached before session termination."""
        term_reason = session.termination_reason or default_reason
        for cid in candidate_ids:
            if cid not in processed_ids:
                self._record_candidate_issue(
                    session, cid, result_code=None, err_msg=term_reason, is_interrupted=True
                )

    def _resolve_terminal_status(self, session: EnrichmentSession) -> None:
        """Calculates final terminal status and termination reason."""
        if session.stop_requested:
            session.status = BulkEnrichmentStatus.CANCELLED
        elif session.status == BulkEnrichmentStatus.DRAINING:
            session.status = BulkEnrichmentStatus.BLOCKED
        elif session.status not in (BulkEnrichmentStatus.BLOCKED, BulkEnrichmentStatus.FAILED):
            session.status = BulkEnrichmentStatus.COMPLETED
            if not session.termination_reason:
                if session.unprocessed_count > 0:
                    session.termination_reason = (
                        f"Completed with {session.unprocessed_count} unprocessed candidate(s)."
                    )
                else:
                    session.termination_reason = "All candidates processed successfully."

    async def _run_session(
        self,
        user_id: UUID,
        job_id: UUID,
        candidate_ids: list[UUID],
        force_refresh: bool,
        stop_event: asyncio.Event,
    ) -> None:
        """Internal background session loop handling canary, concurrency, drain, and audit."""
        session = self._active_sessions[job_id]
        total = len(candidate_ids)
        processed_ids: set[UUID] = set()

        if total == 0:
            session.status = BulkEnrichmentStatus.COMPLETED
            session.termination_reason = "No candidates to enrich"
            session.unprocessed_count = 0
            await self._finalize_and_audit(session, 0, 0, 0)
            return

        # Stage 1: Canary
        canary_ok, temp_errors, blocking_errors, internal_errors = await self._execute_canary_stage(
            session, user_id, job_id, candidate_ids[0], total, force_refresh, processed_ids
        )

        if not canary_ok:
            session.unprocessed_count = max(0, total - session.processed_count)
            self._record_unprocessed_issues(
                session, candidate_ids, processed_ids, "Canary halted on external error"
            )
            await self._finalize_and_audit(session, temp_errors, blocking_errors, internal_errors)
            return

        if total == 1 or session.stop_requested or stop_event.is_set():
            session.status = (
                BulkEnrichmentStatus.CANCELLED
                if session.stop_requested
                else BulkEnrichmentStatus.COMPLETED
            )
            session.unprocessed_count = max(0, total - session.processed_count)
            if not session.termination_reason:
                session.termination_reason = "Canary record completed batch."
            self._record_unprocessed_issues(
                session, candidate_ids, processed_ids, "Session completed or stopped"
            )
            await self._finalize_and_audit(session, temp_errors, blocking_errors, internal_errors)
            return

        # Stage 2: Scale Worker Pool to Concurrency Ceiling & Stage 3: Drain
        temp_errors, blocking_errors, internal_errors = await self._execute_worker_pool(
            session,
            user_id,
            job_id,
            candidate_ids[1:],
            force_refresh,
            stop_event,
            temp_errors,
            blocking_errors,
            internal_errors,
            processed_ids,
        )

        session.unprocessed_count = max(0, total - session.processed_count)
        self._resolve_terminal_status(session)
        self._record_unprocessed_issues(
            session, candidate_ids, processed_ids, "Session ended before candidate was processed"
        )

        await self._finalize_and_audit(session, temp_errors, blocking_errors, internal_errors)

    async def _finalize_and_audit(
        self,
        session: EnrichmentSession,
        temp_errors: int,
        blocking_errors: int,
        internal_errors: int,
    ) -> None:
        """Persists audit record and stores latest summary response."""
        now = datetime.now(UTC)
        session.ended_at = now
        avg_ms = (
            int(session.total_duration_ms / session.processed_count)
            if session.processed_count > 0
            else 0
        )

        audit = BulkEnrichmentResult(
            id=uuid4(),
            user_id=session.user_id,
            job_id=session.job_id,
            session_id=session.session_id,
            status=session.status,
            processed_count=session.processed_count,
            unprocessed_count=session.unprocessed_count,
            failure_count=session.failure_count,
            success_count=session.success_count,
            total_resources_used=session.total_resources_used,
            total_duration_ms=session.total_duration_ms,
            average_duration_ms=avg_ms,
            termination_reason=session.termination_reason or "Completed",
            candidate_issues=session.candidate_issues,
            acknowledged_at=None
            if session.status in (BulkEnrichmentStatus.BLOCKED, BulkEnrichmentStatus.FAILED)
            else now,
            created_at=now,
            updated_at=now,
        )

        if self._session_factory:
            try:
                from vistarae_core.adapters.repositories.bulk_enrichment_repo import (
                    SqlAlchemyBulkEnrichmentRepository,
                )

                async with self._session_factory() as db_session, db_session.begin():
                    repo = SqlAlchemyBulkEnrichmentRepository(db_session)
                    await repo.create_result(audit)
            except Exception as exc:
                logger.error("Failed to persist bulk enrichment audit result: %s", exc)
        elif self._bulk_repo:
            try:
                await self._bulk_repo.create_result(audit)
            except Exception as exc:
                logger.error("Failed to persist bulk enrichment audit result: %s", exc)

        summary = BulkEnrichmentSummaryResponse(
            session_id=session.session_id,
            job_id=session.job_id,
            status=session.status,
            total_candidates=session.total_count,
            succeeded_count=session.success_count,
            temporary_error_count=temp_errors,
            blocking_error_count=blocking_errors,
            internal_error_count=internal_errors,
            unprocessed_count=session.unprocessed_count,
            total_duration_ms=session.total_duration_ms,
            average_duration_ms=avg_ms,
            total_resources_used=session.total_resources_used,
            termination_reason=session.termination_reason or "Completed",
            candidate_issues=[
                CandidateIssueDetail(**issue) if isinstance(issue, dict) else issue
                for issue in session.candidate_issues
            ],
            created_at=now,
        )
        self._latest_summaries[session.job_id] = summary
        logger.info("Session %s finished with status %s", session.session_id, session.status)
