# Implementation Plan: AI Bulk Enrichment (018-bulk-ai-enrich)

**Branch**: `018-bulk-ai-enrich` | **Date**: 2026-11-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-bulk-ai-enrich/spec.md`

---

## Summary

Deliver a production-grade, fail-fast bulk AI enrichment architecture for the POI Import Staging Workbench. The system replaces untracked in-memory background routines with an asynchronous, canary-gated producer-worker orchestrator (`BulkEnrichmentSessionManager`). Candidate #1 executes as an isolated canary; upon success, workers scale up to a configurable concurrency ceiling (`BULK_ENRICHMENT_CONCURRENCY`, default 3). Any `BLOCKING_EXTERNAL_ERROR` (HTTP 402/429) triggers sub-second circuit breaking, halts queue dispatch, drains active tasks within a 30-second grace window, and immediately displays an itemized audit summary. During processing, the staging workbench enters a mutually exclusive locked state, and a client heartbeat (5s interval, 15s disconnect ceiling) guarantees resource protection. All run outcomes are persistently audited in a new `bulk_enrichment_results` database table, enabling an interactive login recovery prompt that guides travelers to resume interrupted jobs filtered by `"Incomplete"`.

---

## Technical Context

**Language/Version**: Python 3.12 (Backend) / TypeScript 5.5+ (Frontend Single-Page Application)  
**Primary Dependencies**: FastAPI 0.115+, SQLAlchemy 2.0 (Pure Async with `asyncpg`), Pydantic v2 (`StrictBaseModel`), React 18, Vite, Lucide React, TailwindCSS  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+, Neon Serverless Postgres via PgBouncer connection pools (`statement_cache_size: 0`), Alembic schema migrations  
**Testing**: `pytest` with `pytest-asyncio` and `pytest-cov` (enforcing $\ge 90\%$ line and branch coverage), Vitest / React Testing Library  
**Target Platform**: AWS Lambda (serverless gateway via `Mangum(app, lifespan="off")`) / Local Uvicorn gateway (`STAGE == "local"`), AWS S3 + CloudFront (SPA)  
**Project Type**: Web service + Full-stack web application (FastAPI backend + React frontend)  
**Performance Goals**: 
- Canary dispatch within $< 200\text{ ms}$ of session initiation
- Sub-second circuit breaking ($< 500\text{ ms}$) upon receiving a `BLOCKING_EXTERNAL_ERROR`
- Live UI telemetry responsiveness within $< 1\text{ second}$ of worker completion
- Login recovery check evaluated in $< 5\text{ ms}$ via indexed database query
**Constraints**: 
- Strict tenant isolation (`WHERE user_id = :current_user_id` on all queries)
- Pure async SQLAlchemy 2.0 without session-polluting PostgreSQL Row-Level Security
- Max 45-second execution ceiling per candidate worker
- Max 30-second grace drain window on cancellation or external blocking errors
- Zero-cost architecture compliance: in-table metric tracking without CloudWatch `PutMetricData` or DynamoDB fees
**Scale/Scope**: Bulk batches of up to 2,000 candidates per import job; parallel concurrency ceiling of 1–10 workers (default 3)

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Constitutional Invariant | Status | Compliance Verification |
| :--- | :--- | :---: | :--- |
| **1. File Headers & Pre-Commit** | Standard Apache 2.0 copyright header on all `.py`, `.ts`, `.tsx`, `.sql` files | **PASS** | Automated pre-commit verification will enforce headers, `ruff`, `prettier`, and Cognitive Complexity $\le 15$. |
| **2. Monorepo & Ports/Adapters** | Core domain models, schemas, and port protocols in `packages/core/vistarae_core` | **PASS** | New entities, enums, schemas, and repository protocols live in `packages/core`; worker logic isolated in `services/worker/`. |
| **3. Database & Tenancy** | Pure Async SQLAlchemy 2.0, `statement_cache_size: 0`, tenant isolation via explicit `WHERE user_id = :current_user_id` | **PASS** | `bulk_enrichment_results` explicitly filters by `user_id`. No PostgreSQL RLS used. |
| **4. Alembic & Environment** | Reversible migrations in `db/migrations/versions/`, `VARCHAR(n)` backed by `StrEnum` (no native DB enums) | **PASS** | Migration `0019_add_bulk_enrichment_results.py` includes strict `upgrade()` and `downgrade()`, using `VARCHAR(32)` for `status`. |
| **5. API Contract & Validation** | OpenAPI 3.1 contracts, Pydantic v2 `StrictBaseModel` (`extra="forbid"`), RFC 7807 `ProblemDetails` | **PASS** | Endpoints use strict schemas, generate OpenAPI models, and map errors to RFC 7807 ProblemDetails. |
| **6. Middleware & Security** | Rate-limiting outer layer, strict CORS, no credentials in logs, `PREMIUM` subscription gate | **PASS** | Subscription check enforces HTTP 403 for non-premium users; all logs redact secrets. |
| **7. Observability & Tracing** | W3C `traceparent` propagation, directional messaging tags (`MSG: -->|`, etc.) in local mode | **PASS** | Worker logs output `[X of Y]` with request correlation UUIDs and local directional markers. |
| **8. PyTest & SDD Governance** | Min 90% branch/line coverage threshold, mirrored test tree in `tests/unit/` | **PASS** | Tests mirrored in `tests/unit/worker/` and `tests/unit/services/ingest/` with `--cov-fail-under=90`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/018-bulk-ai-enrich/
├── spec.md              # Ratified EARS requirements & user scenarios
├── plan.md              # This implementation plan
├── research.md          # Phase 0: Concurrency, canary gating, audit schema
├── data-model.md        # Phase 1: Entity definitions, schemas, state transitions
├── quickstart.md        # Phase 1: End-to-end runnable validation guide
├── contracts/
│   └── bulk_enrichment_api.yaml # OpenAPI 3.1 REST contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py             # BulkEnrichmentResult, EnrichmentSession, EnrichmentQueueItem
│   └── enums.py                # BulkEnrichmentStatus, EnrichmentResultCode, RecoveryPromptAction
├── ports/
│   └── repositories.py         # IBulkEnrichmentRepository protocol definition
├── schemas/
│   └── bulk_enrichment.py      # Pydantic v2 StrictBaseModel boundary schemas
└── adapters/
    ├── db/
    │   └── tables.py           # BulkEnrichmentResultsTable SQLAlchemy ORM mapping
    └── repositories/
        └── bulk_enrichment_repo.py # SqlAlchemyBulkEnrichmentRepository implementation

db/migrations/versions/
└── 0019_add_bulk_enrichment_results.py # Alembic migration for bulk_enrichment_results table

services/
├── ingest/
│   └── routes/
│       ├── staging.py          # Updated staging endpoints with bulk enrichment session routes
│       └── bulk_enrichment.py  # Dedicated router for start, progress, cancel, heartbeat, recovery
└── worker/
    └── bulk_enrichment_manager.py # BulkEnrichmentSessionManager orchestrator (canary, semaphore, circuit breaker)

frontend/src/
├── types/
│   └── api.ts                  # Generated TypeScript interfaces from OpenAPI
├── services/
│   └── ingestApi.ts            # Frontend API client methods for bulk enrichment
├── components/
│   ├── common/
│   │   └── BulkEnrichmentRecoveryModal.tsx # Interactive login recovery prompt dialog
│   └── ingest/
│       ├── CSVImportWorkbenchModal.tsx    # Modal workbench locking and selection integration
│       ├── CSVEnrichmentProgressModal.tsx # Live progress modal with metrics, elapsed time & Cancel
│       └── CSVEnrichmentSummaryModal.tsx  # Post-processing summary statistics window
└── pages/
    └── HomePage.tsx            # Login recovery check mounted upon authentication initialization

tests/
├── unit/
│   ├── repositories/
│   │   └── test_bulk_enrichment_repo.py
│   ├── services/
│   │   └── ingest/
│   │       └── test_bulk_enrichment_routes.py
│   └── worker/
│       └── test_bulk_enrichment_manager.py
└── contract/
    └── test_bulk_enrichment_openapi.py
```

**Structure Decision**: Web application layout integrating full-stack FastAPI backend and Vite/React frontend. Domain entities and repository ports remain in `packages/core` ensuring pure dependency inversion; orchestration logic is cleanly modularized in `services/worker/bulk_enrichment_manager.py`.

---

## Complexity Tracking

_No constitutional violations or unjustified complexity introduced. Design strictly adheres to pure async SQLAlchemy, serverless zero-cost patterns, and existing monorepo conventions._
