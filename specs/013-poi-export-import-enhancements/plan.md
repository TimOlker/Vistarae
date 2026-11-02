<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Implementation Plan: Phase 13 — Multi-Stage POI Export, Flexible Multi-Fidelity Import & Ingestion Enhancements

**Branch**: `013-poi-export-import-enhancements` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/013-poi-export-import-enhancements/spec.md`

---

## Summary

Phase 13 establishes a unified, bi-directional POI Data Exchange architecture across Vistarae. It removes the processing bottlenecks and data migration friction of large POI datasets by delivering:
1. **Strictly Selective Multi-Stage Export**: Streaming export of checked POIs across Explorer, Phase 1 Triage, and Phase 2 Review in CSV (UTF-8 BOM), JSON, and YAML formats. Export aborts with a user prompt if 0 rows are checked.
2. **Dynamically Derived Schema Introspection**: Exports dynamically inspect `POIExchangeRecord` in `packages/core` rather than hardcoded column lists, automatically discovering any future fields added to the domain model.
3. **Flexible Multi-Fidelity Ingestion Engine**: Dynamically resolves missing attributes per individual POI record; provides canonical column aliasing with an **Interactive Column Mapping Dialog** for non-standard third-party headers.
4. **Pre-Import Type Sanity Gate**: Catches malformed column types (such as non-numeric coordinates), presenting the user with an **Import Validation Error Modal** offering to "Skip Invalid Rows & Continue" or "Abort Import".
5. **Decoupled Parallel & Throttled Processing**: Decouples bulk import into per-POI async worker tasks paced by a centralized token-bucket rate limiter enforcing Nominatim's strict 1 req/sec policy and bounding concurrent LLM tasks ($\le 5$).
6. **Early Tag Library Gatekeeper**: Intercepts unapproved tags before staging, offering a one-click "Approve & Add All to Library" action.
7. **Creation Timestamp Auditing (`created_at`)**: PostgreSQL `created_at` timestamp with time zone on `pois`, indexed via `(user_id, created_at DESC)`, exposed as a table column and date filter in Explorer.

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.5+ (frontend)  
**Primary Dependencies**:
- Backend: FastAPI 0.111+, SQLAlchemy 2.0 (pure async with `asyncpg`), Pydantic v2 (`StrictBaseModel`), PyYAML, `codecs`, Alembic
- Frontend: React 18, Vite 5, Lucide React, Tailwind CSS  
**Storage**: PostgreSQL 16+ / PostGIS 3.4+ (`pois` table with `created_at`, `ingest_candidates` staging table, `geocache` table)  
**Testing**: pytest with pytest-asyncio and pytest-cov ($\ge 90\%$ branch/line coverage threshold), Vitest for frontend components  
**Target Platform**: AWS Lambda (serverless Mangum ASGI entrypoint with streaming chunked responses), Linux server, Modern Evergreen Web Browsers (Vite SPA)  
**Project Type**: Monorepo with Ports & Adapters architecture (`packages/core/`, `services/ingest/`, `services/worker/`, `frontend/`)  
**Performance Goals**: Export 2,000 records in < 3 seconds; early tag & format validation dialogs display in < 1.5 seconds; memory consumption $\le 128\text{MB}$ during chunked streaming  
**Constraints**:
- Strictly enforce Nominatim 1 req/sec rate limit via shared token bucket
- Strict tenant isolation via `WHERE user_id = :current_user_id` (no PostgreSQL RLS)
- Prepend UTF-8 BOM (`\xef\xbb\xbf`) to CSV exports for Excel Windows compatibility; sanitize formula injection (`'`, `=`, `+`, `-`, `@`)
- Zero-selection export abort gate across all phases  
**Scale/Scope**: Datasets up to 5,000 POIs / 5MB per upload file

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle | Requirement Summary | Status | Compliance Verification |
| :--- | :--- | :---: | :--- |
| **1. File Header & Docstrings** | Standard Apache 2.0 copyright banner on all `.py`, `.ts`, `.tsx`, `.sql`. Max nesting 3, Cognitive Complexity $\le 15$. | **PASS** | All new modules (`poi_exporter.py`, `poi_importer.py`, `poi_exchange.py`, modals) include copyright header, Google-style docstrings, and early returns. |
| **2. Ports & Adapters Architecture** | Domain models isolated in `packages/core`. Pure domain decoupled from `boto3`, HTTP, and framework internals. | **PASS** | Authoritative exchange schema `POIExchangeRecord` resides in `packages/core`. Ingestion parser and exporter decoupled from transport protocols. |
| **3. Database & Tenancy** | Pure Async SQLAlchemy 2.0 (`asyncpg`). NullPool in cloud, QueuePool in local. `statement_cache_size=0`. No RLS. `WHERE user_id = :current_user_id`. | **PASS** | `created_at` query filters append `WHERE user_id = :current_user_id`. Tenant-scoped ID reconciliation checks `WHERE id = :poi_id AND user_id = :current_user_id`. |
| **4. Alembic & Environment Isolation** | Schema migrations in `db/migrations/`. Reversible `downgrade()`. Status/category fields typed with Python `StrEnum` backed by `VARCHAR(n)`. | **PASS** | Migration adds `created_at` column and index with clean reversible `downgrade()`. Enums `TagResolutionAction` use `StrEnum`. |
| **5. API Contract & Validation** | OpenAPI 3.1 authoritative contract. TypeScript types synced via `npx openapi-typescript`. Pydantic v2 `StrictBaseModel`. RFC 7807 ProblemDetails for errors. | **PASS** | OpenAPI contract created in `contracts/poi-exchange-api.yaml`. Boundary schemas inherit from `StrictBaseModel`. Validation failures return RFC 7807 problem payloads. |
| **6. Middleware & Security** | Idempotency first, RateLimit second. Formula injection neutralization (`'`, `=`, `+`, `-`, `@`, `\t`, `\r`). | **PASS** | CSV serializer escapes formula characters with prepended single quote (`'`). Strict zero-selection gate aborts accidental mass exports. |
| **7. Observability & Tracing** | Directional `MSG` logging markers (`MSG: -->\|`, `MSG: <--\|`, etc.). Structured JSON in cloud. W3C `traceparent` propagation. | **PASS** | Worker pool and export streaming maintain W3C trace context and log directional telemetry across external Nominatim/LLM boundaries. |
| **8. PyTest & SDD Governance** | Minimum 90% branch and line coverage. Mirror source tree in `tests/unit/`. Spec governs as absolute truth. Strict YAGNI. | **PASS** | Independent unit test suites planned in `tests/unit/services/ingest/` and `tests/unit/services/worker/` targeting $\ge 90\%$ line and branch coverage. |
| **Operational Guardrails** | Nominatim 1 req/sec policy. Chunked HTTP streaming $\le 128\text{MB}$. Bounded LLM concurrency ($\le 5$). | **PASS** | Shared `AsyncTokenBucket` singleton paces Nominatim requests; chunked generator streams responses without full-dataset memory buffering. |

---

## Project Structure

### Documentation (this feature)

```text
specs/013-poi-export-import-enhancements/
├── spec.md                  # Approved specification in strict EARS syntax
├── plan.md                  # This implementation plan
├── research.md              # Phase 0 technical decisions matrix
├── data-model.md            # Phase 1 domain entities, schema, and lifecycle
├── quickstart.md            # Phase 1 verification and runnable scenarios guide
├── checklists/
│   └── requirements.md      # Specification quality validation checklist
├── contracts/
│   └── poi-exchange-api.yaml # OpenAPI 3.1 specification for export/import exchange
└── tasks.md                 # Phase 2 implementation task breakdown (speckit-tasks)
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   └── enums.py                            # Add TagResolutionAction StrEnum
├── schemas/
│   └── poi_exchange.py                     # POIExchangeRecord with dynamic introspection
└── services/
    ├── poi_exporter.py                     # Streaming serializer (CSV with BOM, JSON, YAML)
    └── poi_importer.py                     # Multi-format parser with alias dictionary & type checker

services/ingest/
├── routes/
│   ├── export.py                           # Streaming export endpoints (Explorer, Phase 1, Phase 2)
│   ├── upload.py                           # Updated flexible upload route & format detection
│   └── tags.py                             # Early tag validation resolution endpoint
└── services/
    ├── flexible_parser.py                  # Integration between raw uploads and poi_importer
    └── staging_service.py                  # Dynamic per-field candidate staging

services/worker/
├── processor.py                            # Decoupled per-POI task dispatcher
├── candidate_enricher.py                   # Selective field re-calculation & LLM worker
└── rate_limiter.py                         # Shared AsyncTokenBucket (1 req/sec Nominatim)

db/migrations/versions/
└── 20261031_add_poi_created_at.py          # Alembic migration for pois.created_at & index

frontend/src/
├── components/
│   ├── ingest/
│   │   ├── CSVUploadModal.tsx              # Multi-format upload & format sniffer
│   │   ├── ColumnMappingModal.tsx          # Interactive column alignment with 3-row preview
│   │   ├── ImportValidationErrorModal.tsx  # Format error dialog with "Skip Invalid Rows"
│   │   ├── TagValidationWarningModal.tsx   # Early tag resolution ("Approve & Add All")
│   │   ├── CSVTriageModal.tsx              # Export Selected button & Select All toggle
│   │   └── CSVPhase2ReviewModal.tsx        # Export Selected button & Select All toggle
│   ├── poi/
│   │   ├── POITable.tsx                    # "Date Added" column & Explorer Export Selected button
│   │   └── POIFilterBar.tsx                # Date Added filter presets (Today, 7D, 30D, Custom)
│   └── services/
│       └── exportApi.ts                    # API client for streaming export downloads

tests/unit/
├── services/
│   ├── ingest/
│   │   ├── test_poi_exporter.py            # Unit tests for CSV BOM, JSON, YAML streaming
│   │   ├── test_poi_importer.py            # Unit tests for alias dict, multi-format parsing
│   │   ├── test_column_mapping.py          # Unit tests for column alignment & type validation
│   │   └── test_export_routes.py           # Unit tests for zero-selection abort & streaming
│   └── worker/
│       └── test_rate_limiter.py            # Unit tests for 1 req/sec token bucket pacing
└── frontend/
    └── ingest/
        ├── ColumnMappingModal.test.tsx     # Vitest for column alignment preview
        └── ImportValidationErrorModal.test.tsx # Vitest for skip invalid rows interaction
```
