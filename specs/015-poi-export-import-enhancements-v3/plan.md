# Implementation Plan: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Branch**: `015-poi-export-import-enhancements-v3` | **Date**: 2026-11-02 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from [`specs/015-poi-export-import-enhancements-v3/spec.md`](./spec.md)

---

## Summary

Consolidate the fragmented Phase 1 (triage) and Phase 2 (enrichment review) modal workflows into a single, cohesive **Import Staging Workbench** modal (`CSVImportWorkbenchModal.tsx`). Replace the legacy US-centric address model with a flexible international ISO 3166-1 alpha-2 administrative layer (`country_code`, `admin_level_1`, `admin_level_2`, `locality`, `street_address`, `postal_code`, `raw_geocoding`, and `photo_directories`). Enforce English place and address negotiation across all external Nominatim endpoints (`Accept-Language: en`, `accept-language=en`). Implement a split-pane master-detail layout supporting dynamic perspective switching ("POI" vs "Location"), MapLibre GL map interaction with pin-drag relocation and "Re-sync Address from Pin", dynamic website list management with confirmation dialogs, account Tag Library strict chip selection, local photo directory management, and additive deduplicated union merges upon database commit.

---

## Technical Context

**Language/Version**: Python 3.12+ (Backend & Worker Services), TypeScript 5.4+ / React 18+ (Frontend & Extension)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (AsyncIO), Alembic, Pydantic v2, MapLibre GL, Lucide React, HTTPX  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`GEOGRAPHY(Point, 4326)`), `pg_trgm`, `uuid-ossp`  
**Testing**: Vitest + React Testing Library (Frontend), Pytest + pytest-asyncio (Backend Services)  
**Target Platform**: Modern Chromium Browsers (Chrome 120+, Edge), Linux / Windows containerized host  
**Project Type**: Monorepo with ports/adapters architecture (`packages/core`, `services/ingest`, `services/poi`, `services/worker`, `frontend`, `extension`)  
**Performance Goals**: Perspective view toggle < 100ms; table sort < 50ms; geocode batch ingest with Nominatim 1 req/sec rate ceiling  
**Constraints**: Zero un-migrated DB breaking changes; strict tenant isolation on all queries (`user_id == current_user_id`); strict EARS requirement syntax  
**Scale/Scope**: Ingest jobs up to 500 rows per batch; spatial radius proximity search up to 50 miles  

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Check / Invariant | Status | Verification Detail |
| :--- | :--- | :--- | :--- |
| **Principle 1** | Standard Copyright Header Banner | PASS | All `.py`, `.ts`, `.tsx`, and `.sql` files contain Apache 2.0 header. Google-style docstrings applied. |
| **Principle 2** | Monorepo & Ports/Adapters | PASS | Core domain entities (`POI`, `IngestCandidate`), value objects (`AddressRecord`), and tables live in `packages/core`. |
| **Principle 3** | Tenancy & Database Invariants | PASS | Queries enforce tenant scoping (`user_id == current_user_id`). Spatial points stored as `GEOGRAPHY(Point, 4326)`. |
| **Principle 4** | Alembic & Migrations | PASS | Revisions `0015` and `0016` linearized without destructive mutations. Head stamped and applied. |
| **Principle 5** | API Contracts & Schemas | PASS | Pydantic v2 schemas use `StrictBaseModel`. OpenAPI spec exported and TypeScript types synchronized via codegen. |
| **Principle 6** | Middleware & Security | PASS | W3C tracing (`traceparent`), Nominatim policy compliance (1 req/sec max, custom User-Agent, internal PostGIS geocache). |
| **Principle 7** | Observability & Messaging Tags | PASS | Cross-service boundaries log with exact tags: `MSG ->|`, `MSG <-|`, `MSG   |->`, `MSG   |<-`. |
| **Principle 8** | PyTest & SDD Governance | PASS | All 240 frontend tests, 101 ingest backend tests, 295 poi tests, and 35 worker tests pass with zero regressions. |

---

## Project Structure

### Documentation (this feature)

```text
specs/015-poi-export-import-enhancements-v3/
├── plan.md              # Implementation architecture & planning (this file)
├── research.md          # Phase 0 technical research & decision rationale
├── data-model.md        # Phase 1 database schema, entity models & union semantics
├── quickstart.md        # Phase 1 test execution & verification quickstart
├── contracts/           # Phase 1 OpenAPI specifications
│   └── import-staging-workbench-api.yaml
└── checklists/          # Specification quality checklists
    └── requirements.md
```

### Source Code Layout

```text
d:\Coding\Vistarae\
├── db/migrations/versions/
│   ├── 20261102_add_workbench_fields.py      # Alembic revision 0015
│   └── 20261102_add_iso_address_fields.py    # Alembic revision 0016 (ISO address & indexes)
├── packages/core/vistarae_core/
│   ├── adapters/db/tables.py                 # POITable & IngestCandidateTable with ISO fields
│   ├── adapters/repositories/
│   │   ├── ingest_candidate_repo.py          # Candidate persistence & batch updates
│   │   └── poi_repo.py                       # Canonical POI CRUD with ISO address tiers
│   ├── domain/
│   │   ├── entities.py                       # POI & IngestCandidate domain models
│   │   ├── exceptions.py                     # CyclicHierarchyError & domain exceptions
│   │   └── value_objects.py                  # AddressRecord with ISO fields
│   ├── schemas/
│   │   ├── ingest_staging.py                 # CandidateItemResponse & CandidateUpdateRequest
│   │   └── poi.py                            # POICreateRequest, POIUpdateRequest & POIResponse
│   └── services/
│       └── address_normalizer.py             # Nominatim ISO fallback parser & English cleanup
├── services/
│   ├── ingest/
│   │   ├── routes/
│   │   │   ├── export.py                     # POI export route
│   │   │   └── staging.py                    # Staging workbench endpoints
│   │   └── services/
│   │       ├── csv_parser.py                 # CSV ingestion parser aligned with ISO headers
│   │       └── staging_service.py            # Staging lifecycle & additive union merge commit
│   ├── poi/
│   │   ├── routes/pois.py                    # POI API endpoints
│   │   └── services/
│   │       ├── geocode_service.py            # Reverse geocoding with English negotiation
│   │       ├── geocoding_service.py          # Forward geocoding with English negotiation
│   │       └── scraping_orchestrator.py      # Wikipedia / secondary source enrichment
│   └── worker/
│       └── candidate_enricher.py             # AI enrichment worker with "No Websites" skip logic
└── frontend/
    └── src/
        ├── components/ingest/
        │   ├── CSVImportWorkbenchModal.tsx   # Single unified split-screen workbench
        │   └── WorkbenchMap.tsx              # MapLibre GL map with pin drag & nearby markers
        ├── services/
        │   └── ingestApi.ts                  # Ingest API client & CandidateItem types
        ├── tests/ingest/
        │   └── CSVImportWorkbenchModal.test.tsx # Component unit tests
        └── types/
            └── api.ts                        # Generated OpenAPI TypeScript definitions
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| **None** | All implementations strictly adhere to the Vistarae Constitution. | N/A |
