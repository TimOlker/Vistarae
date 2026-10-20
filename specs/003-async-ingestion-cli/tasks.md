# Tasks: Asynchronous Ingestion Pipeline, Batch Worker & Operational CLIs

**Feature**: `003-async-ingestion-cli` | **Branch**: `003-async-ingestion-cli`  
**Input**: [spec.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/spec.md), [plan.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/plan.md), [data-model.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/data-model.md), [contracts/ingest-api.yaml](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/contracts/ingest-api.yaml), [contracts/cli-contracts.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/contracts/cli-contracts.md)

---

## Phase 1: Setup & Database Migration

**Purpose**: Database schema creation, queue configuration, and migration reversibility verification.

- [X] T-001 Configure local ElasticMQ queue definitions in `docker/elasticmq.conf` asserting `vistarae-ingest-local` has `receiveMessageWait = 20 seconds`, `defaultVisibilityTimeout = 180 seconds`, and dead-letter queue `vistarae-ingest-dlq-local` with `maxReceiveCount = 3` [Constitution Operational Invariant 1]
- [X] T-002 Create reversible Alembic migration revision `db/migrations/versions/0003_async_ingestion_cli.py` creating table `ingest_jobs` (`id UUID PK DEFAULT gen_random_uuid()`, `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`, `job_status VARCHAR(16) NOT NULL`, `total_rows INT NOT NULL DEFAULT 0`, `processed_rows INT NOT NULL DEFAULT 0`, `duplicate_payloads JSONB NOT NULL DEFAULT '[]'::jsonb`, `target_list_id UUID NULL REFERENCES lists(id) ON DELETE SET NULL`, `error_summary JSONB NOT NULL DEFAULT '[]'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`), check constraint `ck_ingest_jobs_status` ensuring `job_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED')`, composite indexes `idx_ingest_jobs_user_created` on `(user_id, created_at DESC)` and `idx_ingest_jobs_id_user` on `(id, user_id)`, with fully reversible `downgrade()` [REQ-INGEST-001, REQ-INGEST-002, REQ-INGEST-003, Constitution Principle 4]
- [X] T-003 [P] Implement migration verification tests in `tests/unit/db/test_0003_migration.py` verifying table creation, check constraint enforcement, index creation, foreign key cascade deletion, and clean downgrade reversibility [REQ-INGEST-001, REQ-INGEST-002, Constitution Principle 4]

---

## Phase 2: Foundational Architecture & Core Interfaces (Blocking Prerequisites)

**Purpose**: Core domain entities, value objects, ports, SQLAlchemy ORM tables, and queue adapters that MUST be complete before ANY user story can be implemented.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T-004 [P] Implement domain value objects and exceptions in `packages/core/vistarae_core/domain/value_objects.py` and `exceptions.py` (`IngestJobStatus`, `DuplicateTriageStatus`, `IngestJobNotFoundError`, `FileTooLargeError`, `RowLimitExceededError`, `InvalidMimeTypeError`, `InvalidCSVHeaderError`) [REQ-INGEST-001, REQ-INGEST-002, REQ-INGEST-004, REQ-INGEST-005, REQ-INGEST-006]
- [X] T-005 [P] Implement pure domain entities in `packages/core/vistarae_core/domain/entities.py` (`IngestJob`, `DuplicatePayloadItem`, `IngestRowMessage`) [REQ-INGEST-001, REQ-INGEST-009, REQ-INGEST-010, REQ-WORKER-002]
- [X] T-006 [P] Define port protocols in `packages/core/vistarae_core/ports/` (`IIngestJobRepository` in `repositories.py`; `IQueuePort` in `queue.py` defining `send_message_batch`, `receive_messages`, `delete_message`) [REQ-INGEST-001, REQ-INGEST-009, REQ-INGEST-010]
- [X] T-007 [P] Implement SQLAlchemy 2.0 ORM model in `packages/core/vistarae_core/adapters/db/tables.py` (`IngestJobTable`) with check constraints and index mappings [REQ-INGEST-001, REQ-INGEST-002, REQ-INGEST-003]
- [X] T-008 [P] Implement SQS queue adapter in `packages/core/vistarae_core/adapters/queue/sqs.py` (`SQSQueueAdapter`) and test double in `packages/core/vistarae_core/adapters/queue/mock.py` (`MockQueueAdapter`) supporting batch transmission up to 10 messages and W3C trace attributes injection (`traceparent`, `X-Amzn-Trace-Id`, `user_id`, `job_id`) [REQ-INGEST-009, REQ-INGEST-010, Constitution Principle 7]
- [X] T-009 [P] Unit tests for domain entities, value objects, and queue adapters in `tests/unit/core/test_ingest_domain.py` [REQ-INGEST-001, REQ-INGEST-009, REQ-INGEST-010]

**Checkpoint**: Core foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Bulk CSV Upload, Sanitization Guardrails & SQS Dispatch (Priority: P1) 🎯 MVP

**Goal**: Accept bulk CSV file uploads, enforce size ($\le 2$MB) and row ($\le 2,000$) guardrails, neutralize formula injection prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`), strip HTML tags, truncate descriptions to 4,000 characters, partition rows 1:1 into SQS messages with W3C trace headers, and return HTTP 202 Accepted.

**Independent Test**: Upload a 50-row CSV file via `POST /api/ingest/csv`, asserting HTTP 202 response with a job ID and `job_status: PENDING`, and verify that 50 individual messages are sent to SQS with valid trace attributes.

### Tests for User Story 1
- [X] T-010 [P] [US1] Unit tests for CSV parser, formula prefix neutralization, HTML stripping, description truncation, and error boundary status codes (RFC 7807 413, 415, 422) in `tests/unit/services/ingest/test_upload.py` [REQ-INGEST-004, REQ-INGEST-005, REQ-INGEST-006, REQ-INGEST-007]
- [X] T-011 [P] [US1] Unit tests for health probes (`/health/live` zero I/O, `/health/ready` SQS and DB connectivity) in `tests/unit/services/ingest/test_health.py` [REQ-INGEST-011, REQ-INGEST-012]
- [X] T-012 [P] [US1] Integration tests for upload workflow and SQS batch dispatch in `tests/integration/services/ingest/test_upload_pipeline.py` [REQ-INGEST-001, REQ-INGEST-008, REQ-INGEST-009, REQ-INGEST-010]

### Implementation for User Story 1
- [X] T-013 [P] [US1] Implement Pydantic v2 schemas in `packages/core/vistarae_core/schemas/ingest.py` (`IngestUploadResponse`, `IngestJobProgressResponse`, `DuplicateItemResponse`, `TriageRequest`, `TriageDecisionItem`) configured with `extra="forbid"` and `validate_assignment=True` [REQ-INGEST-001, REQ-INGEST-013, REQ-INGEST-014, Constitution Principle 5]
- [X] T-014 [US1] Implement `IngestJobRepository` in `packages/core/vistarae_core/adapters/repositories/ingest_repo.py` supporting `create_job`, `get_job_by_id`, `increment_processed_rows`, and `append_duplicate_payload` enforcing `WHERE user_id = :current_user_id` [REQ-INGEST-001, REQ-INGEST-013, Constitution Principle 3]
- [X] T-015 [US1] Implement CSV streaming parser and security sanitization module in `services/ingest/services/csv_parser.py` enforcing size ceiling ($\le 2$MB / 413), row count ($\le 2,000$ / 422), MIME verification (415), formula neutralization (prepending `'` to `=`, `+`, `-`, `@`, `\t`, `\r`), HTML tag stripping, and description truncation (4,000 chars) [REQ-INGEST-004, REQ-INGEST-005, REQ-INGEST-006, REQ-INGEST-007]
- [X] T-016 [US1] Implement `POST /api/ingest/csv` upload route in `services/ingest/routes/upload.py` creating the `ingest_jobs` record, validating optional `target_list_id`, partitioning rows 1:1 into `IngestRowMessage` payloads with preserved `absolute_row_number`, and dispatching via `IQueuePort.send_message_batch` in batches of 10 with W3C trace attributes [REQ-INGEST-001, REQ-INGEST-008, REQ-INGEST-009, REQ-INGEST-010]
- [X] T-017 [US1] Implement dependency readiness probe (`GET /health/ready` checking `sqs:GetQueueAttributes` and `SELECT 1`) and liveness probe (`GET /health/live`) in `services/ingest/routes/health.py` [REQ-INGEST-011, REQ-INGEST-012]
- [X] T-018 [US1] Assemble standalone FastAPI application in `services/ingest/main.py` with `lambda_handler = Mangum(app, lifespan="off")` and mount `/api/ingest` in `services/local_gateway.py` [REQ-INGEST-001, Constitution Principle 2]

**Checkpoint**: User Story 1 is fully functional and independently testable as the core MVP.

---

## Phase 4: User Story 2 - Resilient Batch Processing, In-Memory Rate Limiting & Partial Failures (Priority: P2)

**Goal**: SQS consumer worker that extracts trace context, enforces single-worker in-memory 1 req/sec Nominatim rate limiting, guarantees record-level idempotency via synthetic SHA-256 keys, resolves addresses against `geocoding_cache`, persists POIs with vector embeddings, and isolates partial batch failures via `batchItemFailures`.

**Independent Test**: Publish 10 SQS messages (5 cached, 4 new, 1 malformed), verify cached addresses resolve instantly, new addresses throttle at 1-second intervals, the 9 valid rows commit to the database, and only the single failing message ID returns in `batchItemFailures`.

### Tests for User Story 2
- [X] T-019 [P] [US2] Unit tests for in-memory interval rate limiter (1 req/sec pacing, concurrent task serialization) in `tests/unit/services/worker/test_rate_limiter.py` [REQ-WORKER-005, REQ-WORKER-006]
- [X] T-020 [P] [US2] Unit tests for synthetic idempotency key generation, collision detection, and skip behavior in `tests/unit/services/worker/test_idempotency.py` [REQ-WORKER-002, REQ-WORKER-003]
- [X] T-021 [P] [US2] Unit tests for worker batch processing, W3C trace extraction, geocoding cache lookup, POI persistence, vector generation, and `batchItemFailures` mapping in `tests/unit/services/worker/test_processor.py` [REQ-WORKER-001, REQ-WORKER-004, REQ-WORKER-007, REQ-WORKER-008, REQ-WORKER-009, REQ-WORKER-010, REQ-WORKER-011]
- [X] T-022 [P] [US2] Integration tests for worker event loop consuming local ElasticMQ messages in `tests/integration/services/worker/test_worker_pipeline.py` [REQ-WORKER-001, REQ-WORKER-010, REQ-WORKER-011]

### Implementation for User Story 2
- [X] T-023 [P] [US2] Implement `InMemoryRateLimiter` in `services/worker/rate_limiter.py` enforcing sustained 1.0 request/second interval pacing via `asyncio.sleep` with single-worker concurrency (`ReservedConcurrentExecutions: 1`) [REQ-WORKER-005, REQ-WORKER-006]
- [X] T-024 [US2] Implement record-level idempotency helper in `services/worker/idempotency.py` computing `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}".encode()).hexdigest()` and executing `INSERT INTO idempotency_keys ... ON CONFLICT DO NOTHING`, returning False if already processed [REQ-WORKER-002, REQ-WORKER-003, Constitution Operational Invariant 1]
- [X] T-025 [US2] Implement Nominatim geocoding client in `services/worker/geocoder.py` querying OpenStreetMap with custom `User-Agent: VistaraeTravelEngine/1.0`, checking `geocoding_cache` first, rate-limiting misses, and caching successful responses with 90-day TTL [REQ-WORKER-004, REQ-WORKER-006, REQ-WORKER-007, REQ-WORKER-008]
- [X] T-026 [US2] Implement batch row processor `BatchIngestWorker` in `services/worker/processor.py` extracting `traceparent` and `X-Amzn-Trace-Id` into OpenTelemetry/X-Ray spans, evaluating spatial deduplication (`similarity >= 0.60` and `ST_DWithin`), staging duplicates into `duplicate_payloads` as `PENDING_REVIEW`, persisting unique POIs with Gemini vector embeddings (`thinking_budget=0`), mapping failed message IDs into `{"batchItemFailures": [{"itemIdentifier": msg_id}]}`, and atomically incrementing `processed_rows` in `ingest_jobs` [REQ-WORKER-001, REQ-WORKER-009, REQ-WORKER-010, REQ-WORKER-011]
- [X] T-027 [US2] Implement consumer entrypoint in `services/worker/main.py` providing `lambda_handler(event, context)` for AWS SQS triggers and an asynchronous continuous polling loop for local ElasticMQ development [REQ-WORKER-001, REQ-WORKER-010, Constitution Principle 2]

**Checkpoint**: User Stories 1 and 2 are functional with asynchronous processing and resilient idempotency.

---

## Phase 5: User Story 3 - Duplicate Triage & Interactive Review for Bulk Imports (Priority: P3)

**Goal**: Enable users to poll ingestion job progress, review staged candidate duplicates flagged by trigram similarity and geographic proximity, and commit or reject items interactively.

**Independent Test**: Ingest a CSV row identical to an existing POI, call `GET /api/ingest/jobs/{job_id}` to verify the item is staged under `duplicate_payloads` with `triage_status: PENDING_REVIEW`, submit `POST /api/ingest/jobs/{job_id}/triage` with `COMMITTED`, and confirm the POI is persisted to `pois`.

### Tests for User Story 3
- [X] T-028 [P] [US3] Unit tests for job progress polling, tenant access boundary (RFC 7807 404), and duplicate retrieval in `tests/unit/services/ingest/test_jobs.py` [REQ-INGEST-013, REQ-INGEST-015]
- [X] T-029 [P] [US3] Unit tests for triage submission (`COMMITTED` creates POI, `REJECTED` discards) and status updates in `tests/unit/services/ingest/test_triage.py` [REQ-INGEST-014, REQ-INGEST-015]
- [X] T-030 [P] [US3] Integration test for full duplicate triage lifecycle in `tests/integration/services/ingest/test_triage_flow.py` [REQ-INGEST-013, REQ-INGEST-014]

### Implementation for User Story 3
- [X] T-031 [US3] Implement triage repository methods in `packages/core/vistarae_core/adapters/repositories/ingest_repo.py` (`get_pending_duplicates`, `update_duplicate_triage_decisions`, `recalculate_job_status`) enforcing `WHERE user_id = :current_user_id` [REQ-INGEST-013, REQ-INGEST-014, Constitution Principle 3]
- [X] T-032 [US3] Implement `GET /api/ingest/jobs/{job_id}` progress and duplicate retrieval route in `services/ingest/routes/jobs.py` returning `processed_rows`, `total_rows`, `percent_complete`, and pending review duplicate candidates [REQ-INGEST-013, REQ-INGEST-015]
- [X] T-033 [US3] Implement `POST /api/ingest/jobs/{job_id}/triage` endpoint in `services/ingest/routes/triage.py` processing a list of `TriageDecisionItem` objects, creating POIs for `COMMITTED` items, linking designated `target_list_id`, updating item status to `COMMITTED`/`REJECTED`, and transitioning `job_status` to `COMPLETED` when all duplicates are resolved [REQ-INGEST-014, REQ-INGEST-015]

**Checkpoint**: User Stories 1, 2, and 3 are fully operational with duplicate review workflows live.

---

## Phase 6: User Story 4 - Operational Dead-Letter Queue (DLQ) Redrive (Priority: P4)

**Goal**: Environment-aware operational CLI to inspect and redrive unprocessable dead-letter queue messages back into the primary queue, enforcing interactive confirmation in cloud environments and supporting non-interactive execution with `--yes`.

**Independent Test**: Place a message in `vistarae-ingest-dlq-local`, execute `python scripts/redrive_dlq.py --env local --max-messages 10`, and confirm the message is deleted from the DLQ and re-enqueued to `vistarae-ingest-local`.

### Tests for User Story 4
- [X] T-034 [P] [US4] Unit tests for redrive CLI argument parsing, `--dry-run`, interactive confirmation prompts, and non-interactive `--yes` enforcement in `tests/unit/scripts/test_redrive_dlq.py` [REQ-CLI-001, REQ-CLI-002, REQ-CLI-005, REQ-CLI-011]
- [X] T-035 [P] [US4] Integration test for local ElasticMQ message redriving in `tests/integration/scripts/test_redrive_dlq_integration.py` [REQ-CLI-003, REQ-CLI-004]

### Implementation for User Story 4
- [X] T-036 [US4] Update `scripts/redrive_dlq.py` implementing mandatory `--env [local|staging|prod]`, `--dry-run`, `--non-interactive`, and `--yes` flags, utilizing `receive_message`, `send_message_batch`, and `delete_message_batch` locally on ElasticMQ and AWS native `sqs.start_message_move_task` in staging/production [REQ-CLI-001, REQ-CLI-002, REQ-CLI-003, REQ-CLI-004, REQ-CLI-005, REQ-CLI-011, Constitution Principle 6]

**Checkpoint**: Operational DLQ redrive tooling is verified with environment safety gates.

---

## Phase 7: User Story 5 - AI-Assisted Local Photo Directory Scanner CLI (Priority: P5)

**Goal**: Local filesystem scanner that extracts EXIF GPS and timestamp metadata, queries Google Gemini Flash-Lite with structured JSON schema (`PhotoPOIInference`, `thinking_budget = 0`), interactively resolves uncertain locations (or marks them `NEEDS_REVIEW` with `--non-interactive`), and exports a sanitized ingestion CSV.

**Independent Test**: Run `python -m photo_scraper.main --dir ./tests/fixtures/sample_photos --out ./output/ingest.csv --non-interactive`, verify Gemini is invoked with structured JSON, and assert the output CSV matches the Vistarae schema with all formula injection characters neutralized.

### Tests for User Story 5
- [X] T-037 [P] [US5] Unit tests for EXIF GPS extraction and datetime parsing across JPEG/HEIC/TIFF formats in `tests/unit/photo_scraper/test_exif.py` [REQ-CLI-006, REQ-CLI-010]
- [X] T-038 [P] [US5] Unit tests for Gemini Flash-Lite structured JSON output parsing and Pydantic schema validation (`PhotoPOIInference`, `thinking_budget = 0`) in `tests/unit/photo_scraper/test_llm_parser.py` [REQ-CLI-007, REQ-CLI-008]
- [X] T-039 [P] [US5] Unit tests for interactive TTY prompting, `--non-interactive` triage marking (`triage_status = 'NEEDS_REVIEW'`), and formula-safe CSV export in `tests/unit/photo_scraper/test_worker.py` [REQ-CLI-008, REQ-CLI-009]
- [X] T-040 [P] [US5] Integration test for photo scraper directory scan end-to-end in `tests/integration/photo_scraper/test_scraper_e2e.py` [REQ-CLI-006, REQ-CLI-007, REQ-CLI-008, REQ-CLI-009]

### Implementation for User Story 5
- [X] T-041 [P] [US5] Implement EXIF metadata extractor in `photo_scraper/core/exif.py` reading GPS latitude, GPS longitude, date taken, and image tags using Pillow and ExifRead, gracefully skipping unreadable files [REQ-CLI-006, REQ-CLI-010]
- [X] T-042 [P] [US5] Implement Gemini inference parser in `photo_scraper/core/llm_parser.py` invoking Google Gemini Flash-Lite with `response_mime_type="application/json"` enforcing `PhotoPOIInference` and `thinking_budget = 0` [REQ-CLI-007]
- [X] T-043 [US5] Implement photo scanning and triage worker in `photo_scraper/core/worker.py` executing folder traversal, calling Gemini parser, interactively prompting on uncertain/generic candidates in TTY mode, and assigning `triage_status = 'NEEDS_REVIEW'` in `--non-interactive` mode [REQ-CLI-006, REQ-CLI-008, REQ-CLI-010]
- [X] T-044 [US5] Implement CLI entrypoint and CSV writer in `photo_scraper/main.py` formatting results into canonical columns `name,description,address,city,state,country,latitude,longitude,visited_date,tags,triage_status` with formula prefix neutralization [REQ-CLI-008, REQ-CLI-009]

**Checkpoint**: AI Photo Scanner CLI is fully operational for both interactive and automated workflows.

---

## Phase 8: Polish & Cross-Cutting Integration

**Purpose**: OpenAPI synchronization, end-to-end quickstart validation, and strict test coverage enforcement.

- [X] T-045 [P] Implement OpenAPI schema export and sync verification in `scripts/export_openapi.py` asserting TypeScript contract compliance (`git diff --exit-code ./frontend/src/types/api.ts`) [Constitution Principle 5]
- [X] T-046 Execute quickstart validation scenarios from `quickstart.md` against local gateway on port 8030 verifying CSV upload, worker processing, duplicate triage, DLQ redrive, and photo scanning [Success Criteria SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007, SC-008]
- [X] T-047 Execute complete test suite with coverage enforcement (`uv run pytest --cov=packages/core --cov=services --cov=scripts --cov=photo_scraper --cov-fail-under=90`) asserting $\ge 90\%$ branch and line coverage [Constitution Principle 8, SC-006]

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **BLOCKS all user stories**.
- **Phase 3 (User Story 1 - P1)**: Depends on Phase 2 completion — Core MVP.
- **Phase 4 (User Story 2 - P2)**: Depends on Phase 2 completion; consumes messages produced by User Story 1.
- **Phase 5 (User Story 3 - P3)**: Depends on Phase 3 and Phase 4 completion (triages duplicates staged by worker).
- **Phase 6 (User Story 4 - P4)**: Depends on Phase 1 and Phase 2 (manages queues configured in setup).
- **Phase 7 (User Story 5 - P5)**: Independent CLI; depends on Phase 2 core schemas (`PhotoPOIInference`).
- **Phase 8 (Polish)**: Depends on all user stories being complete.

### Parallel Opportunities
- Within **Phase 1**: T-003 [P] can run in parallel once T-002 migration is defined.
- Within **Phase 2**: T-004 [P], T-005 [P], T-006 [P], T-007 [P], T-008 [P] can all proceed in parallel across their respective files.
- Once **Phase 2 completes**:
  - Phase 3 (Upload Gateway) and Phase 6 (DLQ Redrive CLI) and Phase 7 (Photo Scanner CLI) can proceed in parallel.
- Within **Phase 3**: Tests T-010 [P], T-011 [P], T-012 [P] and schemas T-013 [P] can run in parallel before routes assemble.
- Within **Phase 4**: Tests T-019 [P], T-020 [P], T-021 [P] and rate limiter T-023 [P] can proceed in parallel.
- Within **Phase 5**: Tests T-028 [P], T-029 [P], T-030 [P] can proceed in parallel.
- Within **Phase 7**: Tests T-037 [P], T-038 [P], T-039 [P] and modules T-041 [P], T-042 [P] can run in parallel.
