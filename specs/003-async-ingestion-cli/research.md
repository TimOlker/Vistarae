# Research & Architecture Decisions: Asynchronous Ingestion Pipeline, Batch Worker & Operational CLIs

**Feature Identifier**: `003-async-ingestion-cli`  
**Date**: 2026-10-19  
**Status**: Completed  
**Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/spec.md)

---

## 1. CSV Upload Guardrails, Security Sanitization & Ingestion API

### Context & Problem

CSV imports accept untrusted user spreadsheets that may contain Formula Injection payloads (CSV injection via `=`, `+`, `-`, `@`, `\t`, `\r`), raw HTML or script tags, excessively long descriptions, corrupted encodings, or oversized payloads that could exhaust server memory.

### Decision

Implement a multi-tier streaming validation and sanitization pipeline in `services/ingest/routes/upload.py`:

1. **Size & MIME Pre-Check**:
   - Verify `Content-Length <= 2,097,152` bytes (2MB); return RFC 7807 413 Payload Too Large if exceeded.
   - Enforce MIME check: must be `text/csv`, `text/plain`, or `application/vnd.ms-excel`; return RFC 7807 415 if invalid.
2. **Streaming Parse & Row Counting**:
   - Stream bytes through a UTF-8 decoder (`codecs.getincrementaldecoder`).
   - Parse lines using standard library `csv.DictReader`.
   - Terminate and reject with RFC 7807 422 if data rows exceed 2,000.
3. **Formula & HTML Sanitization**:
   - If any cell text begins with `=`, `+`, `-`, `@`, `\t`, or `\r`, prepend a single quote (`'`) to neutralize spreadsheet calculation execution.
   - Strip all raw HTML tags using a compiled regex (`re.sub(r'<[^>]+>', '', text)`).
   - Truncate descriptions to exactly 4,000 characters, appending `...` if truncated.
4. **Header Validation**:
   - Require at least one name column (`name`, `title`, or `place_name`) and one location indicator (`address`, `query`, or both `latitude` and `longitude`).

### Alternatives Considered & Rejected

- _Pandas / Polars DataFrame parsing_: Rejected to avoid bringing heavyweight data science dependencies into the lightweight serverless runtime.
- _Strict formula stripping (removing characters entirely)_: Rejected because negative numbers or legitimate titles (e.g. "- Overlook Point") would lose their first character. Prepending `'` safely neutralizes execution in Excel/Sheets while preserving content readability.

---

## 2. SQS Micro-Batch Dispatch & Message Granularity

### Context & Problem

In AWS Lambda with SQS event source mapping, reporting partial batch failures (`batchItemFailures`) operates at the SQS message level (`messageId`), not on sub-elements within a custom JSON array. If multiple CSV rows are packed into a single SQS message, a failure in row 3 causes SQS to redrive all rows in that message, requiring complex partial state tracking.

### Decision

Partition CSV rows 1:1 into individual SQS messages (`IngestRowMessage`):

1. Each CSV row becomes an independent SQS message containing:
   - `job_id: UUID`
   - `user_id: UUID`
   - `target_list_id: UUID | None`
   - `absolute_row_number: int` (1-based index matching the original CSV file)
   - `row_data: dict[str, str]` (sanitized POI attributes)
2. To minimize HTTP overhead during dispatch from FastAPI, messages are sent using `boto3` `send_message_batch` in chunks of 10 messages per batch API call.
3. Each SQS message includes W3C tracing metadata in `MessageAttributes`:
   - `traceparent` (DataType: `String`)
   - `X-Amzn-Trace-Id` (DataType: `String`)
   - `user_id` (DataType: `String`)
   - `job_id` (DataType: `String`)
4. The primary queue is configured with `ReceiveMessageWaitTimeSeconds: 20` (Long Polling) and `VisibilityTimeout: 180s` (6x the Lambda 30-second timeout). The dead-letter queue (DLQ) is configured with `maxReceiveCount: 3` and 14-day retention.

### Alternatives Considered & Rejected

- _Packing 10 rows per SQS message_: Rejected during clarification because a transient failure in one row would force SQS to redrive all 10 rows, increasing complexity and risk of poison-pill message looping.

---

## 3. Worker Concurrency & In-Memory Rate Limiting

### Context & Problem

OpenStreetMap Nominatim enforces an absolute usage ceiling of 1 request per second per application. When background workers process hundreds of rows, they must never exceed 1 req/sec. Distributed database locking in Neon PgBouncer transaction mode introduces connection pool contention and risks compute scale-to-zero disruptions.

### Decision

1. **Single-Worker Concurrency (`ReservedConcurrentExecutions: 1`)**:
   - The SQS consumer Lambda function is configured with `ReservedConcurrentExecutions: 1` in AWS.
   - In local development, the worker loop runs as a single async consumer process.
2. **In-Memory Interval Tracking**:
   - Because exactly one worker instance executes at any time, rate limiting is coordinated entirely in process memory without any database locks.
   - An asynchronous rate limiter records `last_request_timestamp: float`.
   - When an address needs geocoding:
     - Check `geocoding_cache` first. If cached and `expires_at > NOW()`, return coordinates immediately with 0 delay (bypass rate limiter).
     - If a cache miss occurs, calculate `elapsed = time.monotonic() - last_request_timestamp`. If `elapsed < 1.0`, execute `await asyncio.sleep(1.0 - elapsed)`.
     - Update `last_request_timestamp = time.monotonic()` and issue outbound HTTP request to Nominatim with custom `User-Agent: VistaraeTravelEngine/1.0`.
     - Store result in `geocoding_cache` with a 90-day expiration (`NOW() + INTERVAL '90 days'`).

### Alternatives Considered & Rejected

- _Distributed table lock row in Neon (`rate_limit_locks`)_: Rejected during clarification audit. Holding locks or executing high-frequency updates across shared PgBouncer transaction pools wastes connection slots and contradicts Constitution Principle 3 tenancy standards.
- _Redis token bucket_: Rejected. Vistarae adheres to a Zero-Cost Architecture with no external Redis infrastructure.

---

## 4. Record-Level Idempotency & Partial Batch Failure Handling

### Context & Problem

Serverless queues guarantee at-least-once delivery. If a network blip occurs after a row is saved to the database but before the SQS message is deleted, SQS will re-deliver the message. Re-delivery must not generate duplicate POIs or corrupt job metrics.

### Decision

1. **Synthetic Idempotency Key**:
   - For every row message, the worker computes:
     `key = hashlib.sha256(f"{user_id}:{job_id}:{absolute_row_number}".encode()).hexdigest()`
   - Before executing geocoding or spatial insertions, the worker attempts an atomic insert:
     ```sql
     INSERT INTO idempotency_keys (user_id, idempotency_key, status, created_at)
     VALUES (:user_id, :key, 'COMPLETED', NOW())
     ON CONFLICT (user_id, idempotency_key) DO NOTHING
     RETURNING id;
     ```
   - If 0 rows are returned, the row was already processed in a previous execution; the worker acknowledges the message and skips further processing immediately.
2. **Partial Batch Failure Mapping**:
   - When consuming a batch of SQS messages (up to 10 per Lambda invocation), the worker wraps each message in a `try/except` block.
   - If an unrecoverable transient error occurs (e.g. database timeout or Nominatim 503), the message ID is captured:
     `batch_item_failures.append({"itemIdentifier": record["messageId"]})`
   - The Lambda handler returns `{"batchItemFailures": batch_item_failures}`.
   - SQS deletes successfully processed messages and automatically retries only the failed message IDs.

---

## 5. Operational Dead-Letter Queue (DLQ) Redrive

### Context & Problem

Operational scripts that move messages from dead-letter queues back into production queues carry high operational risk. Running an unintended redrive in production can flood downstream services with poisoned messages.

### Decision

Implement `scripts/redrive_dlq.py` with rigorous environment gating:

1. Mandate `--env` argument (`local`, `staging`, `prod` / `production`).
2. Provide `--dry-run` to inspect visible DLQ message counts without altering queues.
3. For cloud environments (`staging`, `prod`):
   - If standard input is a TTY and `--dry-run` is false, require the operator to type `"yes"` interactively.
   - If standard input is not a TTY (CI or headless cron) and `--non-interactive` is passed, require explicit `--yes` flag; otherwise abort immediately with exit code 1.
   - Use AWS native `sqs.start_message_move_task(SourceArn=dlq_arn, DestinationArn=main_arn)` to execute server-side redrives.
4. For local development (`local` against ElasticMQ):
   - Use client-side loop with `receive_message`, `send_message_batch`, and `delete_message_batch` in batches of 10.

---

## 6. AI Photo Scanner CLI (`photo_scraper`) Architecture

### Context & Problem

Travelers have large photo collections organized in nested directories (e.g. `2024/Japan/Kyoto/Fushimi Inari/DSC_0123.jpg`). Extracting POIs requires parsing file path structures, reading EXIF GPS tags, utilizing LLM semantic reasoning to infer landmark identities, and resolving uncertain locations.

### Decision

1. **EXIF & Metadata Extraction**:
   - Use Pillow / ExifRead to extract GPS latitude/longitude, timestamp taken, and camera tags.
   - Extract directory path components, splitting into continent/country/region/city/landmark candidates.
2. **Gemini Flash-Lite Structured Extraction**:
   - Invoke Google Gemini Flash-Lite using `google-genai` SDK with `response_mime_type="application/json"` enforcing Pydantic model `PhotoPOIInference`.
   - Set `thinking_budget = 0` for low-latency, deterministic, cost-efficient entity extraction.
3. **Interactive & Non-Interactive Triage**:
   - If `is_uncertain == True`, confidence score $< 0.70$, or the inferred name represents a generic category (e.g. "Airport", "Hotel", "Restaurant"):
     - In interactive TTY mode: prompt the user interactively in the CLI to confirm, rename, or discard.
     - In `--non-interactive` mode or non-TTY: assign `triage_status = 'NEEDS_REVIEW'` in the CSV output.
4. **CSV Export**:
   - Write standard Vistarae ingestion CSV with headers:
     `name,description,address,city,state,country,latitude,longitude,visited_date,tags,triage_status`
   - Sanitize all formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) during export.
