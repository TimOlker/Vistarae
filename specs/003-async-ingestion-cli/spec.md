# Feature Specification: Asynchronous Ingestion Pipeline, Batch Worker & Operational CLIs

**Feature Identifier**: `003-async-ingestion-cli`  
**Feature Branch**: `003-async-ingestion-cli`  
**Created**: 2026-10-19  
**Status**: Draft  
**Target Systems**: Vistarae Ingestion Service (`services/ingest`), Background Worker (`services/worker`), Core Package (`packages/core`), Operational Scripts (`scripts/`), Photo Scanner CLI (`photo_scraper/`), Database (PostgreSQL 16 / PostGIS / Neon), SQS Queue (`vistarae-ingest-*`), AI Extraction (Google Gemini Flash-Lite)

---

## 1. Executive Summary & Context

Phase 3 (`003-async-ingestion-cli`) establishes the asynchronous ingestion backbone, scalable batch processing worker, and automated command-line ingestion utilities for the Vistarae platform. While Phase 1 provided authentication, rate-limiting, and quota governance, and Phase 2 delivered spatial POI storage and vector search, Phase 3 allows travelers to onboard massive collections of travel destinations effortlessly. 

This phase covers three tightly integrated systems:
1. **Asynchronous Ingest Gateway & Job Lifecycle (`/api/ingest/*`)**: Accepts bulk CSV uploads with strict file size, row count, formula injection, and HTML sanitization guardrails; partitions records into individual SQS messages (dispatched in SQS batch requests of 10) with W3C distributed tracing context; enqueues tasks to AWS SQS (or ElasticMQ locally); and exposes job progress polling and duplicate triage endpoints (`COMMITTED`, `PENDING_REVIEW`, `REJECTED`).
2. **Batch Ingest Worker (`BatchIngestWorker`)**: An event-driven SQS consumer that extracts OpenTelemetry and AWS X-Ray trace contexts, guarantees record-level idempotency via synthetic SHA-256 keys, enforces a 1 request/second Nominatim geocoding ceiling via in-memory rate limiting with single-worker concurrency, and reports partial batch failures back to SQS (`batchItemFailures`).
3. **Operational & AI CLI Tooling**:
   - `scripts/redrive_dlq.py`: A safety-gated administrative utility that moves failed dead-letter queue messages back into the primary queue, leveraging ElasticMQ batch APIs locally and AWS native `start_message_move_task` in staging and production.
   - **Photo Scanner CLI (`photo_scraper`)**: An intelligent local filesystem scanner that extracts EXIF GPS metadata, timestamps, and path hierarchies, utilizes Google Gemini Flash-Lite with structured JSON schema outputs to infer scenic POIs, flags uncertain or generic locations for interactive user confirmation, and compiles standardized ingestion CSVs.

---

## Clarifications

### Session 2026-10-19

- Q: How does the system guarantee record-level idempotency if an SQS message batch fails partially or is retried? → A: Before processing each individual row, the worker executes `INSERT INTO idempotency_keys (user_id, idempotency_key, status, created_at) VALUES (..., 'COMPLETED', NOW()) ON CONFLICT (user_id, idempotency_key) DO NOTHING` using the synthetic key `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}".encode()).hexdigest()`. If no row is inserted (0 rows affected), the row is identified as already processed and skipped immediately.
- Q: How should BatchIngestWorker coordinate the 1 req/sec Nominatim geocoding rate limit while honoring connection pooling and tenancy rules? → A: Restrict SQS worker concurrency to 1 (both locally and via `ReservedConcurrentExecutions: 1` in AWS) and coordinate the 1 req/sec rate limit entirely in worker memory without database locking, eliminating Neon connection pool contention. Cache hits in `geocoding_cache` bypass the rate limiter completely.
- Q: How should BatchIngestWorker handle a failure of 1 row within an SQS batch relative to SQS batchItemFailures? → A: Partition rows 1:1 into individual SQS messages (1 CSV row per SQS message, dispatched in SQS send batches of up to 10), allowing SQS Lambda event source mapping `batchItemFailures` to isolate and retry that exact failing row/message without retrying or delaying adjacent rows.
- Q: How should redrive_dlq.py and photo_scraper handle interactive prompts when running in non-interactive (CI, cron, non-TTY) environments? → A: Support the `--non-interactive` flag across both CLIs: `scripts/redrive_dlq.py` strictly aborts non-interactive cloud runs unless `--yes` is explicitly passed; `photo_scraper` marks uncertain POIs with `triage_status = 'NEEDS_REVIEW'` in the output CSV without prompting, enabling unattended batch runs.
- Q: How are suspected duplicate POIs handled during bulk CSV ingestion without blocking job completion? → A: When the spatial proximity and trigram similarity engine flags a candidate as `POTENTIAL_DUPLICATE` (distance $\le$ radius and similarity $\ge 0.60$), the worker records the item in `ingest_jobs.duplicate_payloads` with status `PENDING_REVIEW` rather than inserting a raw POI. The user can poll `GET /api/ingest/jobs/{job_id}` to review flagged items and submit triage decisions (`COMMITTED` to force creation or `REJECTED` to discard).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk CSV Upload with Upload Guardrails & Asynchronous Tracking (Priority: P1)

As a traveler with an extensive spreadsheet of saved travel recommendations, I want to upload a CSV file to Vistarae, receive an immediate job identifier, and monitor progress asynchronously, so that my browser does not freeze or time out while hundreds of destinations are verified and geocoded.

**Why this priority**: Bulk importing is the primary mechanism for migrating existing user travel archives into Vistarae. Without asynchronous processing, web gateways time out and large uploads fail unpredictably.

**Independent Test**: Can be fully tested by submitting a 50-row CSV file via `POST /api/ingest/csv`, receiving an HTTP 202 Accepted response with a job ID, polling `GET /api/ingest/jobs/{job_id}`, and verifying that `processed_rows` increments until reaching `job_status: COMPLETED`.

**Acceptance Scenarios**:
1. **Given** an authenticated user uploads a valid 500-row CSV file under 2MB, **When** submitting `POST /api/ingest/csv`, **Then** the service creates an `ingest_jobs` record, packages each row into an individual SQS message (sent in SQS batch requests of up to 10) with preserved `absolute_row_number`, enqueues them to SQS with trace headers, and returns HTTP 202 with `job_id` and initial status `PENDING`.
2. **Given** a client uploads a CSV file larger than 2MB, **When** submitting the upload, **Then** the service immediately returns an RFC 7807 413 Payload Too Large error without persisting data or enqueuing messages.
3. **Given** a client uploads a CSV file with 2,500 rows, **When** submitting the upload, **Then** the service returns an RFC 7807 422 Unprocessable Content error indicating the 2,000-row limit has been exceeded.
4. **Given** a CSV containing malicious formula injection characters (`=CMD|' /C ...'!A0`) or raw `<script>` tags, **When** parsed, **Then** the service neutralizes formula prefixes and strips HTML tags before queue dispatch.

---

### User Story 2 - Resilient Batch Processing, Rate Limiting & Partial Failures (Priority: P2)

As a platform operator, I need the SQS background worker to process micro-batches concurrently while strictly honoring external geocoding rate limits (1 req/sec), maintaining record idempotency during retries, and reporting partial batch failures so that temporary external outages do not discard healthy rows.

**Why this priority**: Compliance with OpenStreetMap Nominatim's strict usage policy prevents IP bans. Partial batch failure handling ensures resilient message delivery in serverless queueing.

**Independent Test**: Can be tested by publishing an SQS batch containing 10 rows (5 cached addresses, 4 new addresses, and 1 malformed record), verifying that cached rows return instantly, new addresses throttle at 1-second intervals, the 9 valid rows commit to the database, and the single failing message identifier is returned in `batchItemFailures`.

**Acceptance Scenarios**:
1. **Given** an SQS batch of 10 rows consumed by `BatchIngestWorker`, **When** the worker processes each row, **Then** it generates `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}")` and inserts an idempotency record; if the row was already recorded, it skips processing.
2. **Given** multiple concurrent worker tasks requiring external geocoding, **When** querying addresses not in `geocoding_cache`, **Then** workers coordinate through atomic database reservations to space outbound calls by at least 1.0 second.
3. **Given** an address query that already exists in `geocoding_cache` with an unexpired TTL, **When** processed by the worker, **Then** the worker retrieves the cached coordinates immediately without consuming a rate-limiter slot.
4. **Given** a batch of messages where one message encounters a transient unhandled exception, **When** the Lambda handler finishes, **Then** it returns `{"batchItemFailures": [{"itemIdentifier": failed_message_id}]}`, allowing AWS SQS to re-drive only that specific message while deleting acknowledged records.

---

### User Story 3 - Duplicate Triage & Interactive Review for Bulk Imports (Priority: P3)

As a traveler importing travel recommendations from travel blogs, I want the system to flag potential duplicates against my existing POIs and allow me to review and either commit or reject them, so that my map does not get cluttered with redundant pins.

**Why this priority**: Bulk importing frequently brings in places already saved under slightly different titles. Giving the user control over duplicate candidates maintains data cleanliness and user trust.

**Independent Test**: Can be tested by importing a CSV with a row identical in name and location to an existing POI, polling `GET /api/ingest/jobs/{job_id}`, observing the duplicate payload in `PENDING_REVIEW`, and posting `COMMITTED` to `/api/ingest/jobs/{job_id}/triage` to confirm the record commits to `pois`.

**Acceptance Scenarios**:
1. **Given** a CSV row matches an existing POI with trigram similarity $\ge 0.60$ and geodesic distance $\le 805$ meters, **When** processed by the worker, **Then** the worker appends the staged data and collision details into `duplicate_payloads` with status `PENDING_REVIEW` and does not insert into `pois`.
2. **Given** a job with items in `duplicate_payloads`, **When** the user calls `GET /api/ingest/jobs/{job_id}`, **Then** the response includes job progress and an array of `PENDING_REVIEW` items with match confidence and candidate details.
3. **Given** an item with status `PENDING_REVIEW`, **When** the user posts `decision: COMMITTED` to the triage endpoint, **Then** the system creates the POI, links it to any designated target list, and updates the triage status to `COMMITTED`.
4. **Given** an item with status `PENDING_REVIEW`, **When** the user posts `decision: REJECTED` to the triage endpoint, **Then** the system discards the staged data and updates the triage status to `REJECTED`.

---

### User Story 4 - Operational Dead-Letter Queue (DLQ) Redrive (Priority: P4)

As a system administrator or developer, I need a safe, environment-aware CLI tool to inspect and redrive unprocessable messages from the dead-letter queue back into the primary queue for reprocessing after a bug fix or external outage resolution.

**Why this priority**: Operational failures will occur in distributed architectures. A verified redrive mechanism prevents data loss and simplifies operational recovery across local, staging, and production environments.

**Independent Test**: Can be tested by placing a poisoned message into `vistarae-ingest-dlq-local`, running `python scripts/redrive_dlq.py --env local --max-messages 10`, and confirming the message is deleted from the DLQ and re-enqueued into `vistarae-ingest-local`.

**Acceptance Scenarios**:
1. **Given** messages exist in `vistarae-ingest-dlq-local`, **When** a developer executes `python scripts/redrive_dlq.py --env local`, **Then** the script moves messages in batches of up to 10 using SQS batch APIs without requiring interactive confirmation.
2. **Given** a developer executes `python scripts/redrive_dlq.py --env prod`, **When** prompted for interactive confirmation, **Then** the script aborts if the user does not explicitly type "yes".
3. **Given** confirmation is provided in a cloud environment (`staging` or `prod`), **When** executed, **Then** the script triggers AWS native `start_message_move_task` and reports task status.
4. **Given** the `--dry-run` flag is passed, **When** executed against any environment, **Then** the script displays the count of visible messages in the DLQ without moving any messages.
5. **Given** `scripts/redrive_dlq.py` is executed in a non-interactive environment without a TTY, **When** targeting `staging` or `prod`, **Then** the script aborts immediately with an error unless `--yes` is explicitly passed.

---

### User Story 5 - AI-Assisted Local Photo Directory Scanner CLI (Priority: P5)

As a photographer or traveler with gigabytes of vacation photos organized in folders, I want to scan my local photo folders to extract GPS coordinates and folder context, use AI to infer landmark names and descriptions, interactively clarify ambiguous locations, and export a clean ingestion CSV ready for import.

**Why this priority**: Vacation photo archives represent a goldmine of unorganized travel memories. Automating EXIF extraction and AI entity inference eliminates hours of manual data entry.

**Independent Test**: Can be tested by pointing `photo_scraper` at a folder containing sample JPEG photos with EXIF tags, verifying that Gemini Flash-Lite is invoked with structured JSON output, confirming that uncertain locations prompt the CLI user, and verifying that the final output is a valid CSV adhering to Vistarae ingestion standards.

**Acceptance Scenarios**:
1. **Given** a directory containing photo files with EXIF GPS coordinates and timestamp metadata, **When** running the photo scanner CLI, **Then** the scanner extracts coordinates, dates, and folder naming hierarchy.
2. **Given** extracted metadata, **When** calling Google Gemini Flash-Lite, **Then** the request enforces `response_mime_type="application/json"`, `thinking_budget=0`, and a strict Pydantic output schema (`PhotoPOIInference`).
3. **Given** Gemini returns `is_uncertain: true` or a confidence score below 0.70 or a generic category (e.g., "Airport", "Hotel", "Restaurant"), **When** running in interactive mode, **Then** the CLI prompts the user to confirm, edit, or reject the inferred POI; **When** running with `--non-interactive` or in a non-TTY environment, **Then** the CLI assigns `triage_status = 'NEEDS_REVIEW'` in the CSV without prompting.
4. **Given** completion of the scan and user triage, **When** the process finishes, **Then** the CLI writes a sanitized, formula-safe CSV containing `name,description,address,city,state,country,latitude,longitude,visited_date,tags`.

---

### Edge Cases

- **Zero-Byte or Empty CSVs**: If an uploaded CSV has 0 bytes or contains only whitespace/headers with zero data rows, the API returns RFC 7807 422 Unprocessable Content.
- **Corrupted or Binary File Uploads**: If the uploaded file is not valid UTF-8 text or contains null bytes (`\x00`), the upload validator rejects it with RFC 7807 422 Unprocessable Content.
- **Missing Required Columns**: CSVs must contain at least a name column (`name`, `title`, or `place_name`) and a location indicator (`address`, `query`, or `latitude` and `longitude`). Files missing these are rejected with an RFC 7807 422 error detailing the missing fields.
- **Long Text Overflow**: Description fields exceeding 4,000 characters are automatically truncated to 4,000 characters with an appended ellipsis (`...`).
- **Antimeridian & Extreme Coordinates**: Latitude coordinates outside `[-90.0, 90.0]` or longitude outside `[-180.0, 180.0]` cause that specific row to be rejected or flagged as unmappable without crashing the batch.
- **SQS Micro-Batch Poison Pill**: If a single record in a 10-row batch fails due to an unrecoverable schema anomaly, the worker records the failure in the job's error log, acknowledges valid rows, and only includes the message identifier in `batchItemFailures` if transient retry is appropriate.
- **Neon Cold Start During Worker Processing**: Worker database connections implement the constitutional 3-attempt exponential backoff (500ms, 1500ms, 3000ms) with `statement_cache_size=0` to ensure resilient execution across Neon compute wake-ups.
- **Rate Limit Clock Drift**: If server clocks experience slight drift, the database-managed timestamp in `rate_limit_locks` acts as the single source of truth for rate limiting, preventing concurrent worker clock disparities.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Ingestion Schema, API & Queue Dispatch (`REQ-INGEST-xxx`)

- **REQ-INGEST-001 (Ubiquitous):** The database schema shall persist batch ingestion jobs in table `ingest_jobs` containing columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`, `job_status VARCHAR(16) NOT NULL`, `total_rows INT NOT NULL DEFAULT 0`, `processed_rows INT NOT NULL DEFAULT 0`, `duplicate_payloads JSONB NOT NULL DEFAULT '[]'::jsonb`, `target_list_id UUID NULL REFERENCES lists(id) ON DELETE SET NULL`, `error_summary JSONB NOT NULL DEFAULT '[]'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- **REQ-INGEST-002 (Ubiquitous):** The database schema shall enforce check constraint `ck_ingest_jobs_status` ensuring `job_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'PARTIAL_SUCCESS', 'FAILED')`.
- **REQ-INGEST-003 (Ubiquitous):** The database schema shall create composite index `idx_ingest_jobs_user_created` on `ingest_jobs(user_id, created_at DESC)`.
- **REQ-INGEST-004 (Unwanted Behaviour):** If an uploaded CSV payload exceeds 2,097,152 bytes (2MB), then the ingestion gateway shall reject the request immediately with an RFC 7807 413 Payload Too Large error.
- **REQ-INGEST-005 (Unwanted Behaviour):** If an uploaded CSV contains more than 2,000 data rows (excluding the header), then the ingestion gateway shall reject the request immediately with an RFC 7807 422 Unprocessable Content error.
- **REQ-INGEST-006 (Unwanted Behaviour):** If an uploaded file has a MIME type other than `text/csv`, `text/plain`, or `application/vnd.ms-excel`, then the ingestion gateway shall reject the upload with an RFC 7807 415 Unsupported Media Type error.
- **REQ-INGEST-007 (Event-Driven):** When parsing uploaded CSV records, the parser shall neutralize formula injection prefixes by stripping or prefixing characters (`=`, `+`, `-`, `@`, `\t`, `\r`) with a single quote (`'`), strip all raw HTML markup tags, and truncate description fields exceeding 4,000 characters to exactly 4,000 characters.
- **REQ-INGEST-008 (Optional Feature):** Where a client provides an optional `target_list_id` parameter during `POST /api/ingest/csv`, the ingestion service shall validate that the authenticated user owns the referenced list and associate `target_list_id` with the created `ingest_jobs` record and all resulting POIs.
- **REQ-INGEST-009 (Event-Driven):** When dispatching parsed CSV records to SQS, the ingestion service shall package each row into an individual SQS message payload preserving the 1-based `absolute_row_number`, transmitting them using `send_message_batch` in batches of up to 10 messages per API call.
- **REQ-INGEST-010 (Event-Driven):** When enqueuing micro-batches to the SQS queue (`vistarae-ingest-{STAGE}`), the dispatching service shall inject W3C distributed tracing context into SQS `MessageAttributes`: `traceparent` (DataType `String`), `X-Amzn-Trace-Id` (DataType `String`), `user_id` (DataType `String`), and `job_id` (DataType `String`).
- **REQ-INGEST-011 (Event-Driven):** When a client requests `GET /health/ready` on the `IngestFunction`, the service shall execute `sqs:GetQueueAttributes` against the primary ingestion queue and execute `SELECT 1` against the database, returning HTTP 200 only if both external dependencies respond successfully.
- **REQ-INGEST-012 (Ubiquitous):** When a client requests `GET /health/live` on the `IngestFunction`, the service shall return HTTP 200 without executing any database or SQS network I/O.
- **REQ-INGEST-013 (Event-Driven):** When a client requests `GET /api/ingest/jobs/{job_id}`, the ingestion service shall verify that the job belongs to `current_user_id` and return the job metadata, `processed_rows`, `total_rows`, `job_status`, and all items in `duplicate_payloads` matching status `PENDING_REVIEW`.
- **REQ-INGEST-014 (Event-Driven):** When a client submits triage decisions via `POST /api/ingest/jobs/{job_id}/triage`, the service shall accept a list of row decisions with `row_number` and `decision` typed by `StrEnum` (`COMMITTED`, `REJECTED`). For each `COMMITTED` item, the service shall create the POI and update the duplicate record status to `COMMITTED`; for each `REJECTED` item, the service shall update the status to `REJECTED`.
- **REQ-INGEST-015 (Unwanted Behaviour):** If a client attempts to view or triage an `ingest_job` belonging to another user, then the service shall return an RFC 7807 404 Not Found error.

---

#### Batch Worker Processing, Idempotency & Rate Limiting (`REQ-WORKER-xxx`)

- **REQ-WORKER-001 (Event-Driven):** When the `BatchIngestWorker` receives an SQS event batch, the consumer shall extract `traceparent` and `X-Amzn-Trace-Id` from each record's `messageAttributes` and initialize active OpenTelemetry `TraceContext` and `AwsXRayPropagator` spans.
- **REQ-WORKER-002 (Event-Driven):** When processing each row in a micro-batch, the worker shall compute a synthetic idempotency key `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}".encode()).hexdigest()` and execute `INSERT INTO idempotency_keys (user_id, idempotency_key, status, created_at) VALUES (:user_id, :key, 'COMPLETED', NOW()) ON CONFLICT (user_id, idempotency_key) DO NOTHING`.
- **REQ-WORKER-003 (State-Driven):** While evaluating row idempotency, if the insertion produces 0 affected rows (conflict detected), the worker shall skip processing for that row to guarantee at-least-once SQS delivery does not create duplicate POIs.
- **REQ-WORKER-004 (Event-Driven):** When resolving geographic coordinates for an address string, the worker shall first compute the SHA-256 hash of the normalized address and check `geocoding_cache`. If a cache entry exists and `expires_at > NOW()`, the worker shall use the cached coordinates and bypass the outbound rate limiter.
- **REQ-WORKER-005 (State-Driven):** While processing address geocoding misses in the `BatchIngestWorker`, the worker runtime shall enforce a strict single-worker concurrency limit (`ReservedConcurrentExecutions: 1` in AWS and single-worker mode locally) and coordinate the 1 request per second Nominatim geocoding ceiling entirely within worker process memory (via an asynchronous token bucket or interval tracker) without database locking.
- **REQ-WORKER-006 (State-Driven):** While awaiting an in-memory geocoding interval slot, the worker shall execute `await asyncio.sleep(wait_seconds)` before issuing the HTTP request to OpenStreetMap Nominatim.
- **REQ-WORKER-007 (Ubiquitous):** All outbound geocoding requests to OpenStreetMap Nominatim shall include the mandatory header `User-Agent: VistaraeTravelEngine/1.0`.
- **REQ-WORKER-008 (Event-Driven):** When a new geocoding response is received, the worker shall write the result into `geocoding_cache` with an expiration timestamp set to 90 days from the current time (`NOW() + INTERVAL '90 days'`).
- **REQ-WORKER-009 (Event-Driven):** When a row's coordinates are resolved, the worker shall execute a spatial deduplication probe against the user's existing POIs:
  - If a match is found with trigram similarity `similarity(name, candidate_name) >= 0.60` and geodesic distance `ST_DWithin(geom, candidate_geom, radius_meters)`, the worker shall record the item in `ingest_jobs.duplicate_payloads` with `triage_status = 'PENDING_REVIEW'` and shall not insert into `pois`.
  - If no spatial match is found, the worker shall insert a new record into `pois`, generate a 768-dimensional vector embedding via Google Gemini Flash-Lite with `thinking_budget = 0`, and link the POI to `target_list_id` if present.
- **REQ-WORKER-010 (Event-Driven):** When row processing encounters an unrecoverable per-record error, the worker shall record the row error in `ingest_jobs.error_summary` and include that specific message identifier in the Lambda response `{"batchItemFailures": [{"itemIdentifier": record.messageId}]}`, ensuring SQS retries only the failed row while acknowledged rows are permanently deleted.
- **REQ-WORKER-011 (Event-Driven):** When all rows in a batch are processed, the worker shall atomically increment `processed_rows` in `ingest_jobs` and update `job_status` to `COMPLETED` (or `PARTIAL_SUCCESS` if duplicates require review) once `processed_rows >= total_rows`.

---

#### CLI Tooling: DLQ Redrive & AI Photo Scanner (`REQ-CLI-xxx`)

- **REQ-CLI-001 (Ubiquitous):** The operational DLQ redrive CLI script (`scripts/redrive_dlq.py`) shall mandate an explicit `--env` argument accepting only `local`, `staging`, or `prod` (or `production`).
- **REQ-CLI-002 (Unwanted Behaviour):** If the redrive script is executed against `staging` or `prod` without `--dry-run`, and the operator either fails to provide confirmation or executes in a non-interactive environment without flag `--yes`, then the script shall abort execution immediately with a non-zero exit code.
- **REQ-CLI-003 (State-Driven):** While executing in `local` mode against ElasticMQ, the redrive script shall transfer messages from `vistarae-ingest-dlq-local` to `vistarae-ingest-local` using `receive_message`, `send_message_batch`, and `delete_message_batch` in batches of up to 10 messages.
- **REQ-CLI-004 (State-Driven):** While executing in `staging` or `prod` mode against AWS SQS, the redrive script shall initiate a server-side redrive task via the AWS native `start_message_move_task` API.
- **REQ-CLI-005 (Optional Feature):** Where `--dry-run` is passed to the redrive script, the script shall query and display the count of visible messages in the dead-letter queue without moving or deleting any messages.
- **REQ-CLI-006 (Event-Driven):** When the Photo Scanner CLI (`photo_scraper`) is invoked on a target directory path (`--dir`), the scanner shall recursively inspect files and extract EXIF metadata (GPS latitude, GPS longitude, date taken, and image tags) alongside folder path hierarchy segments.
- **REQ-CLI-007 (Event-Driven):** When analyzing extracted photo metadata, the photo scanner shall query Google Gemini Flash-Lite using structured outputs (`response_mime_type="application/json"`) enforcing a strict Pydantic schema (`PhotoPOIInference`) with `thinking_budget` explicitly set to `0`.
- **REQ-CLI-008 (State-Driven):** While processing AI POI inferences, if `is_uncertain` is true, or the confidence score is below 0.70, or the inferred name represents a generic category (such as "Airport", "Hotel", "Restaurant", or "Train Station"):
  - Where the CLI executes in interactive mode with an active TTY, the CLI shall prompt the operator interactively to confirm, modify, or discard the candidate POI.
  - Where flag `--non-interactive` is passed or standard input is not a TTY, the CLI shall mark the row in the output CSV with `triage_status = 'NEEDS_REVIEW'` without blocking execution.
- **REQ-CLI-009 (Event-Driven):** When photo scanning and interactive triage complete, the photo scanner shall format the results into a standardized CSV file containing columns `name,description,address,city,state,country,latitude,longitude,visited_date,tags,triage_status` with all formula injection characters neutralized.
- **REQ-CLI-010 (Unwanted Behaviour):** If the photo scanner encounters unreadable or non-image files, it shall skip those files, log a debug warning, and continue scanning without terminating the execution.
- **REQ-CLI-011 (Optional Feature):** Where flag `--non-interactive` is passed to `scripts/redrive_dlq.py`, the script shall require flag `--yes` for cloud environment redrives, exiting with code 1 if `--yes` is absent.

---

### Key Entities *(include if feature involves data)*

- **IngestJob (`ingest_jobs`)**: Represents an asynchronous bulk ingestion task. Key attributes: `id` (UUID), `user_id` (UUID), `job_status` (`PENDING`, `PROCESSING`, `COMPLETED`, `PARTIAL_SUCCESS`, `FAILED`), `total_rows` (int), `processed_rows` (int), `duplicate_payloads` (JSONB array of staged duplicates awaiting triage), `target_list_id` (optional UUID), `created_at`, `updated_at`.
- **DuplicatePayload (Value Object in `duplicate_payloads`)**: Represents an imported row flagged as a potential duplicate. Attributes: `row_number` (int), `raw_name` (str), `candidate_poi_id` (UUID), `match_type` (`POTENTIAL_DUPLICATE` or `NEARBY_PARENT`), `similarity_score` (float), `distance_meters` (float), `triage_status` (`PENDING_REVIEW`, `COMMITTED`, `REJECTED`), `staged_poi_data` (dict of normalized POI fields).
- **IngestRowMessage (SQS Payload)**: The unit of queue transmission. Contains `job_id`, `user_id`, `target_list_id`, `absolute_row_number`, `raw_data`, and normalized attributes for a single CSV row.
- **IdempotencyKey (`idempotency_keys`)**: Ensures exactly-once side-effect execution per CSV row using composite key format `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}")`.
- **PhotoPOIInference (Pydantic Schema for Gemini Structured Output)**: Model defining the AI photo extraction contract:
  ```python
  class PhotoPOIInference(StrictBaseModel):
      name: str = Field(description="Specific name of the point of interest or scenic viewpoint")
      description: str = Field(description="Concise description of the location and photo context")
      address: str | None = Field(default=None, description="Street address if identifiable")
      city: str | None = Field(default=None)
      state: str | None = Field(default=None)
      country: str | None = Field(default=None)
      latitude: float | None = Field(default=None)
      longitude: float | None = Field(default=None)
      confidence_score: float = Field(ge=0.0, le=1.0)
      is_uncertain: bool = Field(description="True if location is ambiguous, generic, or uncertain")
      reasoning: str = Field(description="Brief explanation of inference signals")
  ```

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can upload a 1,000-row CSV file and receive an HTTP 202 response with a tracking job ID in under 1.5 seconds.
- **SC-002**: The asynchronous worker processes a 500-row ingestion job in under 10 minutes when all addresses require external geocoding, strictly respecting the 1 request/second rate limit.
- **SC-003**: Ingestion jobs with 100% pre-cached addresses complete processing at a rate exceeding 50 rows per second.
- **SC-004**: Zero duplicate POIs are created when duplicate SQS messages are delivered or batches are retried (100% record-level idempotency).
- **SC-005**: 100% of malicious CSV formula injections (`=`, `+`, `-`, `@`, `\t`, `\r`) and raw HTML tags are neutralized before reaching the database.
- **SC-006**: When processing micro-batches with failing records, 100% of healthy records commit successfully and only failing records are reported in `batchItemFailures`.
- **SC-007**: Operators can redrive 100 DLQ messages locally in under 5 seconds, and staging/prod redrives prevent accidental execution with 100% enforcement of interactive confirmation.
- **SC-008**: The photo scanner CLI achieves at least 80% automated location identification accuracy on photos with valid GPS EXIF data, correctly flagging ambiguous photos for user review.

---

## Assumptions

- **Target Users & Clients**: Ingestion CSV uploads will be initiated via the Vistarae web application or programmatic scripts using standard multi-part form data.
- **SQS Infrastructure**: Local development relies on ElasticMQ (`docker-compose.yml`), which supports standard SQS APIs (`receive_message`, `send_message_batch`, `delete_message_batch`). Cloud environments rely on AWS SQS with active dead-letter queues.
- **Worker Concurrency**: Worker concurrency is constrained to exactly 1 concurrent worker (`ReservedConcurrentExecutions: 1` in AWS and single-worker mode locally) to eliminate distributed database lock contention and coordinate the 1 req/sec Nominatim rate limit entirely in worker memory.
- **External Geocoding Service**: OpenStreetMap Nominatim is the default deterministic geocoding provider, subject to its 1 request per second policy and mandatory custom `User-Agent`.
- **AI Model**: Google Gemini Flash-Lite is available via `google-genai` SDK with structured output JSON schema support and `thinking_budget = 0`.
- **Database Tenancy & Session Isolation**: All queries enforce `WHERE user_id = :current_user_id` in compliance with Constitution Principle 3, with `statement_cache_size = 0` for Neon PgBouncer transaction pooling.
