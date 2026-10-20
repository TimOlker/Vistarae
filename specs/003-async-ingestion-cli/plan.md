# Implementation Plan: Asynchronous Ingestion Pipeline, Batch Worker & Operational CLIs

**Branch**: `003-async-ingestion-cli` | **Date**: 2026-10-19 | **Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/spec.md)

**Input**: Feature specification from `specs/003-async-ingestion-cli/spec.md`

---

## Summary

Phase 3 (`003-async-ingestion-cli`) establishes the asynchronous ingestion backbone, scalable batch processing worker, and automated command-line ingestion utilities for the Vistarae platform:
1. **Asynchronous Ingest Gateway (`services/ingest`)**:
   - Accepts bulk CSV uploads with strict file size ($\le 2$MB) and row count ($\le 2,000$ rows) guardrails, returning RFC 7807 413 or 422 upon violation.
   - Neutralizes formula injection characters (`=`, `+`, `-`, `@`, `\t`, `\r`), strips raw HTML tags, and truncates descriptions to 4,000 characters.
   - Packages rows 1:1 into individual SQS messages (`IngestRowMessage`) with preserved `absolute_row_number` and W3C distributed tracing context (`traceparent`, `X-Amzn-Trace-Id`), dispatching via `send_message_batch` in chunks of up to 10 messages per API call.
   - Persists job metadata in `ingest_jobs` table and provides job polling (`GET /api/ingest/jobs/{job_id}`) and duplicate triage (`POST /api/ingest/jobs/{job_id}/triage`) supporting `StrEnum` decisions (`COMMITTED`, `PENDING_REVIEW`, `REJECTED`).
   - Exposes `/health/ready` (checking SQS `GetQueueAttributes` and DB `SELECT 1`) and `/health/live` (zero I/O).
2. **Batch Ingest Worker (`services/worker`)**:
   - SQS consumer configured with single-worker concurrency (`ReservedConcurrentExecutions: 1` in AWS and single-worker mode locally) to eliminate database locking overhead.
   - Coordinates Nominatim's 1 req/sec rate limit entirely in worker process memory (via an asynchronous interval timer), with unexpired `geocoding_cache` hits bypassing the rate limiter.
   - Enforces record-level idempotency via synthetic keys `sha256(f"{user_id}:{csv_job_id}:{absolute_row_number}")` inserted into `idempotency_keys` (`ON CONFLICT DO NOTHING`).
   - Leverages PostGIS spatial deduplication to stage suspected duplicates ($\ge 0.60$ trigram similarity and spatial radius) into `ingest_jobs.duplicate_payloads` as `PENDING_REVIEW` without creating immediate POIs.
   - Employs 1:1 message mapping to report partial batch failures (`batchItemFailures: [{"itemIdentifier": record.messageId}]`), ensuring AWS SQS retries only failed rows while deleting acknowledged messages.
3. **Operational & AI CLI Tooling**:
   - `scripts/redrive_dlq.py`: Safe dead-letter queue redrive script supporting `--env [local|staging|prod]`, `--dry-run`, `--non-interactive`, and `--yes` confirmation flags, utilizing ElasticMQ batch APIs locally and AWS native `start_message_move_task` in cloud environments.
   - **Photo Scanner CLI (`photo_scraper`)**: Traverses local photo hierarchies, extracts EXIF GPS and timestamp metadata, invokes Google Gemini Flash-Lite with structured JSON schema (`PhotoPOIInference`) and `thinking_budget = 0`, supports interactive confirmation and unattended `--non-interactive` triage, and exports sanitized Vistarae ingestion CSVs.
4. Fully reversible Alembic migration revision `0003_async_ingestion_cli.py`.

---

## Technical Context

**Language/Version**: Python 3.12 (enforced by `pyproject.toml` `requires-python = ">=3.12"`)

**Primary Dependencies**:
- Web & Validation: `fastapi>=0.115.0`, `pydantic>=2.8.0`, `mangum>=0.17.0`
- Persistence & Geospatial: `sqlalchemy[asyncio]>=2.0.32`, `asyncpg>=0.29.0`, `geoalchemy2>=0.15.0`, `alembic>=1.13.0`
- Queueing & Cloud: `boto3>=1.35.0`, `botocore>=1.35.0`
- AI & Image Extraction: `google-genai>=0.1.1`, `pillow>=10.4.0`, `exifread>=3.0.0`
- Networking: `httpx>=0.27.0`
- Observability: `opentelemetry-api>=1.26.0`, `opentelemetry-sdk>=1.26.0`, `aws-xray-sdk>=2.14.0`

**Storage**: PostgreSQL 16+ (Neon / Docker PostGIS) with extensions:
- `postgis` (3.4+)
- `btree_gist` (composite multi-column GiST indexes with UUID `user_id`)
- `pg_trgm` (trigram fuzzy string matching)
- `vector` (pgvector for 768-dim HNSW embeddings)
- `uuid-ossp` (server-default UUID generation)

**Testing**: `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `pytest-cov>=5.0.0` enforcing $\ge 90\%$ branch and line coverage ceiling.

**Target Platform**: Linux server / AWS Lambda container runtime (via Mangum & SQS Lambda event source mapping) + local Docker Compose (`postgis/postgis:16-3.4` and `softwaremill/elasticmq-native:latest`).

**Project Type**: Monorepo with shared editable core library (`packages/core`), modular ingestion service (`services/ingest`), background worker (`services/worker`), and CLI utilities (`scripts/`, `photo_scraper/`).

**Performance Goals**:
- CSV Upload Gateway: $< 1.5$s acceptance latency for 1,000-row CSV file returning HTTP 202 (SC-001).
- Ingestion Throughput: $> 50$ rows/second when addresses are cached in `geocoding_cache` (SC-003).
- Rate-Limited Geocoding: Exactly 1 req/second spacing across all outbound Nominatim calls (SC-002).
- Local DLQ Redrive: 100 messages redriven in $< 5$ seconds (SC-007).

**Constraints**:
- Zero-Cost architecture (no DynamoDB, CloudWatch PutMetricData, or Redis).
- OpenStreetMap Nominatim compliance: strictly $\le 1$ req/sec, custom `User-Agent: VistaraeTravelEngine/1.0`.
- Single-worker concurrency (`ReservedConcurrentExecutions: 1`) to eliminate distributed DB lock contention.
- Multi-tenant tenant scoping (`WHERE user_id = :current_user_id`) enforced across all database queries.
- Upload limits: max 2MB file size, max 2,000 rows.

**Scale/Scope**: Up to 2,000 rows per CSV upload job, asynchronous tracking across unlimited jobs, 1:1 SQS message isolation.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Rule | Compliance Status | Analysis & Evidence |
|---|---|---|
| **Principle 1: File Headers & Pre-Commit** | **PASS** | All new source files (`.py`, `.sql`) mandate Apache-2.0 copyright header banner, Google-style docstrings, cognitive complexity $\le 15$, and max 3 indentation levels. |
| **Principle 2: Ports & Adapters Architecture** | **PASS** | Domain entities (`IngestJob`, `IngestRowMessage`) and ports (`IIngestJobRepository`, `IQueuePort`) reside in `packages/core`. Adapters (`IngestJobRepository`, `SQSQueueAdapter`) are isolated in `packages/core/vistarae_core/adapters/`. `services/ingest` handles HTTP routing; `services/worker` handles SQS events. |
| **Principle 3: Database, PgBouncer & Tenancy** | **PASS** | All operations use SQLAlchemy 2.0 Pure Async components (`AsyncSession`). `WHERE user_id = :current_user_id` is enforced across all repository queries and composite indexes (`idx_ingest_jobs_user_created`). Row-Level Security (RLS) is omitted. Prepared statement caching disabled via `statement_cache_size=0`. |
| **Principle 4: Alembic Isolation & Reversibility** | **PASS** | Migration `0003_async_ingestion_cli.py` provides a 100% reversible `downgrade()` function dropping `ingest_jobs` and its indexes. `job_status` uses Python `StrEnum` backed by `VARCHAR(16)` with check constraints (no native PostgreSQL ENUM). |
| **Principle 5: API Contracts & Error Standards** | **PASS** | Authoritative OpenAPI 3.1 specification generated at `contracts/ingest-api.yaml`. Boundary models use Pydantic v2 `StrictBaseModel`. Error responses formatted as RFC 7807 `ProblemDetails` (413, 415, 422, 404). |
| **Principle 6: Middleware Order & Security** | **PASS** | `CORSMiddleware`, `RateLimitMiddleware`, and `IdempotencyMiddleware` configured in LIFO order. Formula injection characters neutralized (`=`, `+`, `-`, `@`, `\t`, `\r`) with prepended single quote; HTML tags stripped. Redrive CLI requires `--env` and confirmation. |
| **Principle 7: Observability & OpenTelemetry** | **PASS** | Cross-boundary directional message logging (`MSG: -->|`, `MSG: <--|`) enforced for local runs; W3C `traceparent` and `X-Amzn-Trace-Id` injected into SQS `MessageAttributes` and extracted into OpenTelemetry spans in `BatchIngestWorker`. |
| **Principle 8: PyTest & SDD Governance** | **PASS** | Tests mirror production structure 1:1 under `tests/unit/services/ingest/` and `tests/unit/services/worker/`. Minimum 90% branch and line coverage ceiling strictly enforced. |
| **Operational Invariant 1: Queue Discipline** | **PASS** | Uploads $> 2$MB or $> 2,000$ rows rejected with RFC 7807 413/422. Primary queue has `VisibilityTimeout: 180s` and `ReceiveMessageWaitTimeSeconds: 20`. DLQ redrive policy has `maxReceiveCount: 3` and 14-day retention. SQS worker enables `ReportBatchItemFailures: true` and maps failed messages 1:1. Synthetic idempotency key `sha256(f"{user_id}:{csv_job_id}:{row_number}")` guarantees record-level idempotency. |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-async-ingestion-cli/
├── spec.md              # Ratified Feature Specification
├── plan.md              # This file (Implementation Plan)
├── research.md          # Phase 0 Architecture & Decisions Output
├── data-model.md        # Phase 1 Data Models, Schemas & Lifecycle
├── quickstart.md        # Phase 1 Runnable Developer Validation Guide
├── contracts/           # Phase 1 Interface Contracts
│   ├── ingest-api.yaml  # OpenAPI 3.1 Contract for Ingestion Service
│   └── cli-contracts.md # CLI Specifications for redrive_dlq & photo_scraper
└── checklists/
    └── requirements.md  # Built-in Specification Quality Checklist (16/16 Passed)
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py              # IngestJob, DuplicatePayloadItem, IngestRowMessage
│   ├── value_objects.py         # IngestJobStatus, DuplicateTriageStatus, MatchType
│   └── exceptions.py            # IngestJobNotFoundError, FileTooLargeError, RowLimitExceededError
├── ports/
│   ├── repositories.py          # IIngestJobRepository
│   └── queue.py                 # IQueuePort (send_batch, receive, delete)
├── schemas/
│   └── ingest.py                # IngestUploadResponse, IngestJobProgressResponse, TriageRequest, PhotoPOIInference
└── adapters/
    ├── db/
    │   └── tables.py            # IngestJobTable
    ├── repositories/
    │   └── ingest_repo.py       # IngestJobRepository
    └── queue/
        ├── sqs.py               # SQSQueueAdapter (boto3 client with batch send & trace attributes)
        └── mock.py              # MockQueueAdapter (in-memory queue for unit tests)

services/ingest/
├── __init__.py
├── main.py                      # FastAPI app & Mangum entrypoint
├── dependencies.py              # DI providers for IngestJobRepository, QueuePort, Session
└── routes/
    ├── __init__.py
    ├── upload.py                # POST /api/ingest/csv (guardrails, formula sanitization, SQS dispatch)
    ├── jobs.py                  # GET /api/ingest/jobs/{job_id} (progress & pending duplicates)
    ├── triage.py                # POST /api/ingest/jobs/{job_id}/triage (commit/reject decisions)
    └── health.py                # GET /health/ready, GET /health/live

services/worker/
├── __init__.py
├── main.py                      # Standalone consumer loop & lambda_handler for SQS events
├── processor.py                 # BatchIngestWorker (trace extraction, idempotency, dedup, partial failure mapping)
└── rate_limiter.py              # InMemoryRateLimiter (1 req/sec interval tracking)

scripts/
└── redrive_dlq.py               # Updated DLQ redrive CLI (--env, --dry-run, --non-interactive, --yes, start_message_move_task)

photo_scraper/
├── main.py                      # Photo scraper entry point with --non-interactive support
└── core/
    ├── exif.py                  # EXIF GPS and timestamp extractor
    ├── llm_parser.py            # Gemini Flash-Lite structured JSON output with thinking_budget=0
    └── worker.py                # Scanning pipeline and CSV export with formula neutralization

db/migrations/versions/
└── 0003_async_ingestion_cli.py  # Reversible Alembic migration revision

tests/
├── unit/
│   ├── services/
│   │   ├── ingest/
│   │   │   ├── test_upload.py   # Guardrails (size, rows, formula injection, HTML stripping)
│   │   │   ├── test_jobs.py     # Progress polling & duplicate retrieval
│   │   │   ├── test_triage.py   # Commit & reject triage workflows
│   │   │   └── test_health.py   # Health live/ready probes
│   │   └── worker/
│   │       ├── test_processor.py# Trace extraction, idempotency, dedup, partial batch failures
│   │       └── test_rate_limiter.py # In-memory 1 req/sec interval verification
│   ├── scripts/
│   │   └── test_redrive_dlq.py  # CLI flags, interactive confirmation, non-interactive abort
│   └── photo_scraper/
│       ├── test_exif.py         # EXIF GPS extraction
│       └── test_llm_parser.py   # Gemini structured JSON schema validation
```

---

## Complexity Tracking

> **Constitution Check:** All principles passed without violations. No complexity exemptions required.
