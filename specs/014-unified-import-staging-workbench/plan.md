# Implementation Plan: Unified POI Import Staging Workbench

**Branch**: `014-unified-import-staging-workbench` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/014-unified-import-staging-workbench/spec.md`

---

## Summary

Consolidate the legacy two-phase CSV import modals (`CSVTriageModal` and `CSVPhase2ReviewModal`) into a single, unified `CSVImportWorkbenchModal` where travelers can triage, geocode, inspect, enrich, and commit POIs without backtracking. Introduce targeted single-candidate AI enrichment (`POST /api/ingest/jobs/{job_id}/candidates/{candidate_id}/enrich`), an idempotent `no_websites` state flag, in-batch merge attribute aggregation, multi-level sublocation hierarchy validation, and an active session guard.

---

## Technical Context

**Language/Version**: Python 3.12 (Backend), TypeScript 5.4+ (Frontend)  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, GeoAlchemy2, React 18, Vite, Lucide React, MapLibre GL, `google-genai` SDK  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+, `btree_gist`, JSONB columns for related websites, and reversible Alembic migrations  
**Testing**: `pytest` (backend unit tests with 90%+ coverage enforcement), `vitest` (frontend unit tests)  
**Target Platform**: AWS Lambda (arm64, Mangum) via SAM in Cloud; Unified ASGI Gateway (`services.local_gateway:app`) in local development  
**Project Type**: Monorepo with editable core workspace package (`packages/core`)  
**Performance Goals**:
- Single-POI targeted enrichment completed in $<3.5$ seconds
- Proximity radius queries (100 ft to 100 miles) executed in $<100$ms
- Dynamic UI updates without table re-renders or scroll resets
**Constraints**:
- Nominatim policy strictly enforced at $\le 1$ req/sec max with custom User-Agent `VistaraeTravelEngine/1.0`
- Gemini Flash-Lite `thinking_budget = 0` for zero-latency deterministic extraction
- W3C distributed tracing (`traceparent` header propagation) and microservice messaging tags protocol
**Scale/Scope**: Handles batches up to 500 candidates per CSV upload session with zero UI lag

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Check / Invariant | Status | Verification Detail |
| :--- | :--- | :--- | :--- |
| **1. File Header Standard** | Apache 2.0 license banner on all `.py`, `.ts`, `.tsx`, `.sql` files; max nesting $\le 3$; Cognitive Complexity $\le 15$. | PASS | Verified on all created and modified source files. |
| **2. Monorepo & Ports/Adapters** | Core domain entities and ports isolated in `packages/core`; no direct boto3 or HTTP in domain; ASGI local gateway mounted. | PASS | All entities defined in `vistarae_core.domain`, repositories implement protocols. |
| **3. Database & Tenancy** | SQLAlchemy 2.0 asyncpg exclusively; parameterized `WHERE user_id = :current_user_id`; `statement_cache_size=0` for PgBouncer. | PASS | All queries filter on `user_id`; clean async session lifecycle. |
| **4. Alembic & Environment Isolation** | Schema migrations strictly in `db/migrations/`; fully reversible `downgrade()` function; no native PostgreSQL ENUM types. | PASS | Migration `20261102_add_workbench_fields.py` implements full downgrade. |
| **5. API Contract & Validation** | Pydantic v2 `StrictBaseModel(extra="forbid")`; RFC 7807 `ProblemDetails` error formats; `openapi.json` synchronized to TypeScript. | PASS | Complete OpenAPI contract generated at `contracts/import-staging-workbench-api.yaml`. |
| **6. Middleware & Security** | CORS restricted to dev origin or Chrome extension; no wildcard origins; no hardcoded credentials. | PASS | Existing middleware stack maintained. |
| **7. Observability & Logging** | W3C `traceparent` propagation; microservice message tag logging protocol (`MSG ->\|`, `MSG <-\|`). | PASS | Enforced on all new routes and worker actions. |
| **8. PyTest & SDD Governance** | 90% branch/line coverage; unit tests organized in `Test<Method>` classes mirroring production tree; strict YAGNI. | PASS | Mirroring test tree in `tests/unit/services/ingest/`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/014-unified-import-staging-workbench/
├── spec.md              # Feature specification in strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Architecture decisions and trade-off analyses
├── data-model.md        # Domain entities, tables, and state machine
├── contracts/           # OpenAPI contract
│   └── import-staging-workbench-api.yaml
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── quickstart.md        # End-to-end validation guide
```

### Source Code Impact (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py                           # Add no_websites, disposition_justification, parent_candidate_id to IngestCandidate
│   └── enums.py                              # CandidateDisposition StrEnum
├── adapters/
│   ├── db/tables.py                          # IngestCandidateTable columns: no_websites, disposition_justification, merge_target_id
│   └── repositories/ingest_candidate_repo.py # Update create_batch, update, get_active_session, and list queries

db/migrations/versions/
└── 20261102_add_workbench_fields.py          # Alembic migration for no_websites, disposition_justification, merge_target_id

services/ingest/
├── routes/
│   ├── upload.py                             # Active session guard (reject 409 if session active)
│   └── staging.py                            # Consolidate candidate update, targeted enrich, batch-edit, and commit endpoints
└── services/staging_service.py               # In-batch merge aggregation, acyclic sublocation check, and commit logic

services/worker/
└── candidate_enricher.py                     # Check no_websites before external search; set no_websites=True if 0 found

frontend/src/
├── components/ingest/
│   ├── CSVImportWorkbenchModal.tsx           # Unified single-stage workbench (replaces CSVTriageModal and CSVPhase2ReviewModal)
│   └── ColumnMappingModal.tsx                # Seamless launch into workbench modal
├── services/ingestApi.ts                     # API client methods: enrichSingleCandidate, batchEditCandidates, commitStagingJob
└── types/api.ts                              # Updated OpenAPI TypeScript definitions

tests/unit/
├── services/ingest/test_staging_routes.py    # Test active session guard, targeted enrich, batch-edit, and commit
└── services/worker/test_candidate_enricher.py # Test no_websites flag and rate-limiting
```

---

## Phase 0: Research & Decisions
*All architecture unknowns resolved in [`research.md`](./research.md)*:
- Unified single-stage component chosen to eliminate modal navigation backtracking.
- Targeted single-candidate enrichment exposed as a direct synchronous/fast-path endpoint.
- `no_websites` boolean flag added to candidate schema to avoid redundant external queries.
- In-batch merge attribute aggregation merges non-overlapping URLs, tags, and notes.
- Sublocations support arbitrary depth with recursive acyclic ancestor checking.
- Active staging session guard enforces Option B (Strict Guard).

---

## Phase 1: Design & Contracts
*Artifacts generated*:
1. [`data-model.md`](./data-model.md): Detailed domain entities, database schema, state transitions, and validation invariants.
2. [`contracts/import-staging-workbench-api.yaml`](./contracts/import-staging-workbench-api.yaml): OpenAPI 3.1 specification for all staging workbench endpoints.
3. [`quickstart.md`](./quickstart.md): Step-by-step developer and testing guide covering end-to-end scenarios.

---

## Complexity Tracking

> **No Constitution violations detected.** All components adhere strictly to monorepo boundaries, pure async database conventions, and observability requirements.
