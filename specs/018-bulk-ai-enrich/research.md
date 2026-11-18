# Technical Research: AI Bulk Enrichment (018-bulk-ai-enrich)

**Date**: 2026-11-13  
**Status**: Completed  
**Feature Spec**: [spec.md](./spec.md)

---

## 1. Real-Time Progress Telemetry: SSE vs. Polling + Heartbeat

### Decision
Implement a hybrid approach:
1. **Primary Transport**: Dedicated REST polling endpoint `GET /api/ingest/jobs/{job_id}/bulk-enrichment/progress` coupled with bidirectional client heartbeat `POST /api/ingest/jobs/{job_id}/bulk-enrichment/heartbeat` at 5-second intervals.
2. **Rationale**:
   - Vistarae's production deployment targets AWS API Gateway + AWS Lambda behind CloudFront (`Mangum(app, lifespan="off")`). API Gateway HTTP APIs and standard serverless Lambdas have a 29-second connection ceiling and do not natively maintain long-lived HTTP streaming (SSE/chunked transfer) without WebSocket API gateways or external pub/sub services.
   - The workbench already uses polling intervals (`800ms`–`1000ms`) via `getPhase2Progress`. A lightweight polling endpoint backed by Redis/in-memory session state or database session records easily satisfies `SC-003` (< 1-second UI responsiveness) without violating zero-cost serverless constraints.
   - The heartbeat request resets an `active_heartbeat_at` timestamp on the active `EnrichmentSession`. If more than 15 seconds elapse without a heartbeat, the background producer triggers an automatic abort and drains in-flight workers (`REQ-ENR-032`).
3. **Alternatives Considered**:
   - *Server-Sent Events (SSE)*: Excellent for local development or continuous containers (Uvicorn), but fragile and requires persistent connection maintenance in AWS Lambda/API Gateway environments without dedicated streaming proxies.
   - *WebSockets*: Requires AWS API Gateway WebSocket API, separate Lambda routes for `$connect`, `$disconnect`, and `$default`, plus connection ID tracking in DynamoDB, introducing unnecessary complexity and potential AWS billable events violating Zero-Cost Architecture principles.

---

## 2. Concurrency Control, Canary Gating & Circuit Breaking

### Decision
Implement an asynchronous producer-worker orchestration engine (`BulkEnrichmentSessionManager`) within `services/worker/bulk_enrichment_manager.py`:
1. **Canary Gating**:
   - Upon session start, candidate at position 1 ($X=1$) is extracted as the canary candidate.
   - Canary executes in complete isolation (concurrency ceiling = 1) while all subsequent candidates ($X=2..N$) remain enqueued.
   - Only when the canary completes with `result_code == SUCCESS` or `TEMPORARY_EXTERNAL_ERROR` does the producer release the concurrency semaphore to `BULK_ENRICHMENT_CONCURRENCY` (default 3, configurable from 1 to 10 via environment variable).
2. **Fail-Fast Circuit Breaker**:
   - If any worker (canary or subsequent) returns `BLOCKING_EXTERNAL_ERROR` (Gemini HTTP 402 `RESOURCE_EXHAUSTED`, HTTP 429 quota depletion, or scraping auth revocation), an internal `asyncio.Event` (`_stop_requested`) is immediately signaled (`SC-002`: < 500ms).
   - Once signaled, the producer halts dequeueing. In-flight workers continue executing until their individual work completes or the 30-second grace window expires (`REQ-ENR-020`, `REQ-ENR-021`).
   - Session status transitions to `BLOCKED`.
3. **Per-Candidate Execution Ceiling**:
   - Every candidate worker task is wrapped in `asyncio.wait_for(..., timeout=45.0)`.
   - If a worker exceeds 45 seconds, the task is cancelled, the candidate is marked with `result_code=INTERNAL_ERROR` and `error_message="Worker timeout exceeded 45s ceiling"`, and the session continues unless a blocking error was flagged.
4. **Alternatives Considered**:
   - *Celery with Redis/RabbitMQ*: Heavily increases infrastructure overhead, requires standing worker daemon processes, violating the zero-cost containerless AWS Lambda deployment model.
   - *AWS Step Functions with SQS*: Adds AWS service charges and introduces high cold-start latencies per candidate.

---

## 3. Immediate Per-Candidate Persistence & Tenant Isolation

### Decision
Persist candidate updates immediately upon worker completion using an isolated `AsyncSession` per candidate:
1. **Persistence Pattern**:
   - Each worker acquires an independent database session from `async_session_factory`, applies updates to `ingest_candidates`, and commits immediately (`REQ-ENR-029`).
   - The query and update strictly enforce `WHERE user_id = :current_user_id AND id = :candidate_id` complying with Constitution Principle 3 (`Tenancy Invariants`).
   - Disabling asyncpg prepared statement caching (`statement_cache_size: 0`) ensures connection multiplexing across Neon PgBouncer transaction-mode pools.
2. **Selective Enrichment Field Governance**:
   - Worker checks existing candidate attributes before querying external APIs or Gemini.
   - If `force_refresh=False` (default), fields that are already populated (`description`, `reason_to_visit`, `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `hero_image_url`, `tags`) are retained. Only null/empty attributes are targeted for scraping and AI synthesis (`REQ-ENR-030`).
   - If `candidate.is_user_overridden` is `True`, user-edited attributes are never overwritten regardless of `force_refresh` setting.
3. **Alternatives Considered**:
   - *Batch Commit at End of Run*: If the server restarts, tab closes, or a blocking error interrupts processing, all in-flight work would be lost. Immediate per-candidate commits preserve all completed progress.

---

## 4. Persistent Audit Entity & Login Recovery Flow

### Decision
Create a dedicated `bulk_enrichment_results` table via Alembic migration, with repository methods in `packages/core/vistarae_core/adapters/repositories/bulk_enrichment_repo.py`:
1. **Database Schema (`bulk_enrichment_results`)**:
   - `id`: `UUID` (Primary Key, default `uuid4`)
   - `user_id`: `UUID` (Foreign key to `users.id` with `ondelete="CASCADE"`, indexed)
   - `job_id`: `UUID` (Foreign key to `ingest_jobs.id`, indexed)
   - `session_id`: `UUID` (Unique session identifier, indexed)
   - `status`: `VARCHAR(32)` (Backing `BulkEnrichmentStatus`: `COMPLETED`, `BLOCKED`, `CANCELLED`, `FAILED`)
   - `processed_count`: `INTEGER`
   - `unprocessed_count`: `INTEGER`
   - `failure_count`: `INTEGER`
   - `success_count`: `INTEGER`
   - `total_resources_used`: `INTEGER`
   - `total_duration_ms`: `INTEGER`
   - `average_duration_ms`: `INTEGER`
   - `termination_reason`: `TEXT`
   - `acknowledged_at`: `TIMESTAMP WITH TIME ZONE` (Nullable; `NULL` for unacknowledged runs)
   - `created_at`: `TIMESTAMP WITH TIME ZONE` (Default `CURRENT_TIMESTAMP`)
   - `updated_at`: `TIMESTAMP WITH TIME ZONE` (Default `CURRENT_TIMESTAMP`)
2. **Composite Index**:
   - Index on `(user_id, acknowledged_at, created_at DESC)` ensures instantaneous evaluation of the login check query (`REQ-ENR-034`):
     ```sql
     SELECT * FROM bulk_enrichment_results
     WHERE user_id = :user_id
       AND acknowledged_at IS NULL
       AND status IN ('BLOCKED', 'FAILED')
     ORDER BY created_at DESC
     LIMIT 1;
     ```
3. **Login Recovery Action Handling**:
   - `GET /api/ingest/bulk-enrichment/recovery`: Returns active unacknowledged failed/blocked run (or 204 No Content).
   - `POST /api/ingest/bulk-enrichment/recovery/respond`: Accepts `{ "result_id": UUID, "action": "resume" | "dismiss" | "cancel" }`.
     - `"resume"`: Sets `acknowledged_at = NOW()`, returns target `job_id` and initial filter parameter `completeness=incomplete`.
     - `"dismiss"`: Sets `acknowledged_at = NOW()`.
     - `"cancel"`: Leaves `acknowledged_at = NULL`.
4. **Alternatives Considered**:
   - *Reusing `ingest_jobs` table*: `ingest_jobs` tracks overall CSV ingestion and commit lifecycle. An individual import job can undergo multiple enrichments (e.g. single candidate, selective bulk re-enrichment). Tracking bulk runs in `bulk_enrichment_results` isolates run-level auditing and telemetry without mutating job-level status.

---

## 5. Mutual Exclusion & Frontend UI Locking

### Decision
1. **Workbench Locking**:
   - When bulk enrichment is active for a `job_id`, the workbench state machine sets `isEnrichmentActive = true`.
   - All interactive controls (edit drawer, delete actions, triage dispatches, commit button, manual row selection) are disabled or masked with a semi-transparent modal overlay.
   - The progress modal (`CSVEnrichmentProgressModal`) displays live counts:
     - Total candidates in queue
     - Successfully enriched count
     - Encountered issues count (with breakdown)
     - Remaining count
     - In-flight worker count
     - Progress bar (%)
     - Elapsed duration & Average duration per candidate
     - "Cancel" button triggering graceful drain
2. **Post-Run Summary Modal**:
   - Once the session enters a terminal state (`COMPLETED`, `BLOCKED`, `CANCELLED`, `FAILED`), the progress modal transitions to the post-processing summary window displaying comprehensive statistics (`REQ-ENR-026`).
   - Closing the summary window re-enables the workbench controls and triggers a fresh candidate table reload.
3. **Login Recovery Prompt**:
   - Mounted at the top-level application root (`App.tsx` or `HomePage.tsx`) during authentication initialization.
   - If an unacknowledged recovery record is returned, displays the modal prompt with "Yes, resume processing", "No", and "Cancel".
   - Selecting "Yes" opens the workbench with `initialCompletenessFilter="incomplete"`.

