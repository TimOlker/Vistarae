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

# Implementation Plan: Phase 12 — Photo Scraper CLI & Two-Phase Interactive CSV Ingestion

**Branch**: `012-photo-scraper` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/012-photo-scraper/spec.md`

---

## Summary

Phase 12 delivers an end-to-end bridge between digital photo archives and the Vistarae discovery platform through two coordinated, non-duplicative systems:

1. **Standalone Photo Scraper CLI Tool**: An offline-portable, strictly read-only filesystem scanner (`services/scraper/`) that recursively traverses photo directories, prunes noise subfolders, parses hierarchical path tokens, extracts coordinates and earliest capture timestamps across embedded standards (EXIF, IPTC-IIM, XMP) and companion sidecars (`.xmp`, `.json`, `.xml`), resolves location candidates using Google Gemini Flash-Lite with local SQLite caching, and exports an RFC 4180 CSV with formula injection sanitization.
2. **Two-Phase Interactive Web Application Ingestion Engine**: An interactive ingestion pipeline within the Vistarae web application that consumes standardized CSV exports. Phase 1 performs progressive geocoding fallbacks and deduplication, presenting a triage review interface with interactive map pins and four discrete dispositions (`accept`, `ignore`, `update existing POI`, `sublocation`). Phase 2 triggers downstream web scraping and personalized LLM enrichment (incorporating the traveler's custom travel style prompt directives from Phase 11) exclusively on validated POIs before committing changes to the database.

---

## Technical Context

**Language/Version**: Python 3.12 (backend & CLI), TypeScript 5.5+ (frontend)  
**Primary Dependencies**:
- Backend & CLI: FastAPI 0.111+, SQLAlchemy 2.0 (pure async with `asyncpg`), Pydantic v2 (`StrictBaseModel`), Google GenAI SDK (`google-genai` Flash-Lite, `thinking_budget = 0`), Pillow, `exifread`, `defusedxml`, Alembic
- Frontend: React 18, Vite 5, Lucide React, Leaflet / MapLibre GL  
**Storage**: PostgreSQL 16+ / PostGIS 3.4+ (`pois` table, `ingest_candidates` staging table, `geocache` table), local SQLite cache (`.scraper_cache.db`) for CLI  
**Testing**: pytest with pytest-asyncio and pytest-cov ($\ge 90\%$ branch/line coverage threshold), Vitest for frontend components  
**Target Platform**: AWS Lambda (serverless Mangum ASGI entrypoint), Linux server, Modern Evergreen Web Browsers (Vite SPA), Cross-platform CLI (Windows, macOS, Linux)  
**Project Type**: Monorepo with Ports & Adapters architecture (`packages/core/`, `services/scraper/`, `services/ingest/`, `services/poi/`, `services/worker/`, `frontend/`)  
**Performance Goals**: CLI scanning 1,000 folders / 10,000 photos in < 5 minutes with warm cache; Web app CSV pre-validation < 500ms UI latency per progress step; AI enrichment < 4.0s per candidate  
**Constraints**:
- Zero-cost AWS free tier architecture (SQS batch size 10, visibility 180s, Neon scale-to-zero)
- Scanned photo directory read-only invariant (zero filesystem mutations on user media archives)
- Strictly adhere to OSM Nominatim rate limits (1 req/sec max) with User-Agent `VistaraeTravelEngine/1.0` and SHA-256 caching
- Strict tenant isolation via `WHERE user_id = :current_user_id` (no PostgreSQL RLS)
- Deterministic AI extraction with `thinking_budget = 0`  
**Scale/Scope**: Archives with thousands of directories and multi-year repeat visits; batch CSV imports up to 2,000 rows / 2MB

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle | Requirement Summary | Status | Compliance Verification |
| :--- | :--- | :---: | :--- |
| **1. File Header & Docstrings** | Standard Apache 2.0 copyright banner on all `.py`, `.ts`, `.tsx`, `.sql`. Max nesting 3, Cognitive Complexity $\le 15$. | **PASS** | Every new/modified file includes exact copyright header, Google-style docstrings, and guard-clause structure. |
| **2. Ports & Adapters Architecture** | Domain models isolated in `packages/core`. Pure domain decoupled from `boto3`, HTTP, and framework internals. | **PASS** | Shared export schema `POIExportRecord` and `csv_exporter.py` in `packages/core`. Staging repositories defined via Python protocols. |
| **3. Database & Tenancy** | Pure Async SQLAlchemy 2.0 (`asyncpg`). NullPool in cloud, QueuePool in local. `statement_cache_size=0`. No RLS. `WHERE user_id = :current_user_id`. Cascade delete on user. | **PASS** | Staging table `ingest_candidates` references `users(id)` ON DELETE CASCADE. All queries strictly filter by `user_id`. No PostgreSQL RLS used. |
| **4. Alembic & Environment Isolation** | Schema migrations in `db/migrations/`. Reversible `downgrade()`. Status/category fields typed with Python `StrEnum` backed by `VARCHAR(n)`. | **PASS** | Migration creates `ingest_candidates` table with reversible `downgrade()`. Enums `IngestDisposition` and `IngestCandidatePhaseState` use `StrEnum` + `VARCHAR(32)`. |
| **5. API Contract & Validation** | OpenAPI 3.1 authoritative contract. TypeScript types synced via `npx openapi-typescript`. Pydantic v2 `StrictBaseModel` (extra='forbid', str_strip_whitespace=True). RFC 7807 ProblemDetails for errors. | **PASS** | OpenAPI contracts defined in `contracts/photo-scraper-api.yaml`. Boundary schemas inherit from `StrictBaseModel`. RFC 7807 ProblemDetails responses implemented. |
| **6. Middleware & Security** | Idempotency first, RateLimit second. Formula injection neutralization (`'`, `=`, `+`, `-`, `@`, `\t`, `\r`). Read-only safety on scanned directories. | **PASS** | CSV formatter neutralizes formula injection prefixes. CLI opens media files in binary read-only mode (`rb`) with zero directory writes. |
| **7. Observability & Tracing** | Directional `MSG` logging markers (`MSG: -->\|`, `MSG: <--\|`, etc.) in local dev. Structured JSON in cloud. W3C `traceparent` propagation. | **PASS** | Directional messaging tags applied to Gemini location resolver, geocoder, and SQS worker ingestion pipelines. |
| **8. PyTest & SDD Governance** | Minimum 90% branch and line coverage. Mirror source tree in `tests/unit/`. Spec governs as absolute truth. Strict YAGNI. | **PASS** | Dedicated unit test suites structured to mirror source tree with $\ge 90\%$ coverage target across `services/scraper/` and `services/ingest/`. |
| **Operational Guardrails** | Zero-Cost Architecture (Neon tables, SQLite CLI cache, no paid Redis/DynamoDB). SQS batch size 10, visibility 180s, Nominatim 1 req/sec. | **PASS** | Local SQLite caching for CLI; PostGIS `geocache` for backend; SQS chunking adheres strictly to AWS free-tier limits. |

---

## Project Structure

### Documentation (this feature)

```text
specs/012-photo-scraper/
├── spec.md                  # Approved specification in strict EARS syntax
├── plan.md                  # This implementation plan
├── research.md              # Phase 0 technical decisions matrix
├── data-model.md            # Phase 1 domain entities, schema, and lifecycle
├── quickstart.md            # Phase 1 verification and runnable scenarios guide
├── checklists/
│   └── requirements.md      # Specification quality validation checklist
├── contracts/
│   └── photo-scraper-api.yaml # OpenAPI 3.1 specification for two-phase ingestion
└── tasks.md                 # Phase 2 implementation task breakdown (speckit-tasks)
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── adapters/
│   └── db/
│       └── tables.py                       # Add ingest_candidates table mapping
├── domain/
│   └── value_objects.py                    # Add IngestDisposition & IngestCandidatePhaseState
├── ports/
│   └── repositories.py                     # IIngestCandidateRepository protocol
├── schemas/
│   └── poi_export.py                       # POIExportRecord shared schema
└── services/
    └── csv_exporter.py                     # RFC 4180 exporter with formula sanitization & alignment

services/scraper/
├── __init__.py
├── photo_scraper.py                        # Standalone CLI entrypoint
├── path_parser.py                          # Path cleaning, noise pruning & gazetteer heuristics
├── metadata_extractor.py                   # EXIF, IPTC, XMP & sidecar (.xmp, .json, .xml) reader
├── location_resolver.py                    # Gemini Flash-Lite resolver & confidence scorer
└── cache.py                                # Local SQLite .scraper_cache.db manager

services/ingest/
├── routes/
│   ├── staging.py                          # Phase 1 triage & Phase 2 review endpoints
│   ├── upload.py                           # Updated upload streaming & candidate staging
│   └── jobs.py                             # Progress polling endpoints
├── services/
│   ├── csv_parser.py                       # Updated parser consuming POIExportRecord
│   └── staging_service.py                  # Candidate lifecycle, deduplication & multi-visit merge
└── dependencies.py

frontend/src/
├── components/
│   └── ingest/
│       ├── CSVUploadModal.tsx              # Updated CSV upload component
│       ├── CSVProgressModal.tsx            # Real-time progress bar component
│       ├── CSVTriageModal.tsx              # Phase 1 Validation & Triage Modal (Map Parent Selection)
│       └── CSVPhase2ReviewModal.tsx        # Phase 2 AI Enrichment Review Modal (Skip/Edit/Commit)
└── services/
    └── ingestApi.ts                        # Frontend client for staging & triage endpoints

db/migrations/
└── versions/
    └── 20261028_add_ingest_candidates.py   # Alembic migration script for ingest_candidates table

tests/
├── unit/
│   ├── services/
│   │   ├── scraper/
│   │   │   ├── test_path_parser.py         # Prefix stripping, trip detection, gazetteer tests
│   │   │   ├── test_metadata_extractor.py  # EXIF, IPTC, XMP, sidecar (.xmp, .json) tests
│   │   │   ├── test_location_resolver.py   # Gemini scoring, ambiguity penalties, cache tests
│   │   │   └── test_photo_scraper_cli.py   # CLI integration, incremental diffing, read-only invariant
│   │   └── ingest/
│   │       ├── test_csv_parser.py          # POIExportRecord parsing & formula sanitization tests
│   │       ├── test_staging_service.py     # Deduplication, multi-visit merge & lifecycle tests
│   │       └── test_staging_routes.py      # OpenAPI contract tests for Phase 1 & Phase 2 endpoints
└── fixtures/
    └── sample_photos/                      # Test media archive with images and sidecars
```

---

## Complexity Tracking

_No constitutional violations. Design strictly leverages existing repository patterns, pure async SQLAlchemy, shared core schemas, and zero-cost local caching._

| Proposed Mechanism | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| `ingest_candidates` staging table | Resilient multi-step triage surviving browser refresh during long async enrichment jobs. | Client-only memory state loses Phase 1 user edits if browser reloads during AI web scraping. |
| Pure-Python metadata extractor | Cross-platform zero-dependency execution across Windows, Linux, and macOS CLI runs. | Native ExifTool subprocess introduces external binary dependencies and installation hurdles. |
| Local SQLite CLI cache | Zero-cost cache preventing redundant external API calls and token waste on repeated photo scans. | In-memory cache loses state across CLI invocations; cloud cache requires online cloud credentials for offline runs. |
