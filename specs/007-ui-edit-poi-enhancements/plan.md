# Implementation Plan: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Branch**: `007-ui-edit-poi-enhancements` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-ui-edit-poi-enhancements/spec.md`

---

## Summary

Phase 7 delivers a comprehensive, intelligent POI Curation Studio within the Vistarae platform. The technical approach expands the POI data model with structured multi-address JSONB arrays (indexed via GIN `jsonb_path_ops`), self-referential hierarchical parenting (`parent_poi_id`, `parent_poi_name`) with recursive CTE cycle prevention, and deterministic visit lifecycle state calculation. An interactive Location Finder modal provides hybrid geocoding (client-debounced forward search + backend cached reverse geocoding via PostGIS `geocache`). A visual merge engine performs atomic field-by-field POI reconciliation, re-parenting dependent itinerary items, list memberships, scanned photo paths, and child POIs before deleting the duplicate source. Pre-save duplicate detection intercepts potential collisions using trigram name similarity and geodesic proximity with in-memory draft preservation.

---

## Technical Context

**Language/Version**: Python 3.12 (backend microservices & core library), TypeScript 5.5+ / React 18+ (frontend single page app)  
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2.10+, SQLAlchemy 2.0+ (asyncpg), Alembic, Leaflet/MapLibre (map canvas), Lucide React (UI icons)  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`geography(Point, 4326)` for geodesic calculations, GiST spatial indexing), GIN index (`jsonb_path_ops`) on `pois.addresses`, pg_trgm for trigram name similarity  
**Testing**: pytest, pytest-cov, pytest-asyncio (enforcing strict $\ge 90\%$ branch and line coverage ceiling per Constitution Principle 8), Vitest / React Testing Library (frontend)  
**Target Platform**: AWS Lambda serverless execution (via Mangum / API Gateway HTTP APIs), Amazon S3 / CloudFront (frontend hosting), local development via Docker Compose & Uvicorn ASGI gateway  
**Project Type**: Monorepo Web Application (FastAPI backend microservices, shared `packages/core` workspace package, React SPA frontend)  
**Performance Goals**: Location Finder modal load & coordinate selection $< 15$s, POI merge transaction $< 500$ms, parent POI typeahead filtering $< 100$ms for 1,000 items, reverse geocoding within 1 req/sec rate limit  
**Constraints**: Zero PostgreSQL RLS (`WHERE user_id = :current_user_id` on all queries), OSM Nominatim 1 req/sec throttling with custom User-Agent, Pydantic `extra="forbid"`, RFC 7807 / RFC 9457 `ProblemDetails` error formatting  
**Scale/Scope**: Multi-address trans-boundary support, DAG hierarchy nesting without cycles, dual-column diff-only visual merge workspace, pre-save duplicate interception

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle / Rule                        | Compliance Status | Implementation Detail                                                                                                                                                                             |
| :-------------------------------------- | :---------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------ | --------------------------------------------------------------------------- |
| **1. File Header & Docstrings**         | PASS              | All new `.py`, `.ts`, `.tsx`, and `.sql` files mandate Apache-2.0 copyright headers and Google-style docstrings.                                                                                  |
| **2. Ports & Adapters Architecture**    | PASS              | Domain entities, value objects (`AddressRecord`, `SourceType`), and schemas reside in `packages/core/vistarae_core/`. No infrastructure leakage into domain models.                               |
| **3. Tenancy Invariants (No RLS)**      | PASS              | All queries enforce `WHERE user_id = :current_user_id`. No PostgreSQL Row-Level Security enabled.                                                                                                 |
| **4. Alembic & Environment Isolation**  | PASS              | Migration `0005_poi_edit_enhancements.py` provides fully reversible `downgrade()` dropping added columns and indexes. Zero native PostgreSQL enum types.                                          |
| **5. API Contracts & Pydantic v2**      | PASS              | OpenAPI 3.1 contract documented in [poi-edit-api.yaml](./contracts/poi-edit-api.yaml). All schemas subclass `StrictBaseModel` with `extra="forbid"`. All errors return RFC 7807 `ProblemDetails`. |
| **6. Middleware & Rate Limiting**       | PASS              | Nominatim geocache enforces 1 req/sec rate limit. Frontend uses debounced forward queries ($\ge 500$ms).                                                                                          |
| **7. Observability & Tracing**          | PASS              | Cross-boundary directional tags (`MSG: -->                                                                                                                                                        | `, `MSG: <-- | `) and W3C `traceparent` headers supported across all POI service handlers. |
| **8. PyTest Governance (90% Coverage)** | PASS              | Unit tests mirrored 1:1 in `tests/unit/services/poi/` and `tests/unit/packages/core/` with `--cov-fail-under=90`.                                                                                 |

---

## Project Structure

### Documentation (this feature)

```text
specs/007-ui-edit-poi-enhancements/
├── spec.md              # Feature specification with strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 architectural & technical decisions
├── data-model.md        # Phase 1 database schema, domain entities & schemas
├── quickstart.md        # Phase 1 runnable end-to-end validation scenarios
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── poi-edit-api.yaml
└── tasks.md             # Phase 2 task checklist (generated by /speckit-tasks)
```

### Source Code Impact (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py              # POI aggregate extensions (addresses, parent_poi_id, visit flags)
│   └── value_objects.py         # AddressRecord, SourceType
├── schemas/
│   ├── poi.py                   # POIUpdateRequest, POIReadResponse, AddressRecordSchema
│   ├── poi_merge.py             # POIMergeRequest, POIMergeResponse, selected scalars/sets
│   └── poi_duplicate.py         # DuplicateCheckRequest, DuplicateCheckResponse
└── services/
    └── address_normalizer.py    # Standard English state/country normalization engine

services/poi/
├── routes/
│   ├── poi.py                   # PATCH /api/pois/{id}, GET /api/pois/{id}
│   ├── merge.py                 # POST /api/pois/merge
│   ├── duplicate.py             # POST /api/pois/check-duplicate
│   ├── hierarchy.py             # GET /api/pois/parents
│   └── geocode.py               # GET /api/pois/geocode/reverse
├── services/
│   ├── merge_service.py         # Atomic merge & reference re-parenting engine
│   ├── hierarchy_service.py     # Recursive CTE cycle detection & parent filtering
│   └── geocode_service.py       # PostGIS geocache lookup & Nominatim rate limiter
└── repositories/
    └── poi_repository.py        # SQLAlchemy 2.0 async queries with tenant isolation

db/migrations/versions/
└── 0005_poi_edit_enhancements.py # Alembic migration with data backfill & reversible downgrade

frontend/src/
├── components/poi/
│   ├── POIEditDrawer.tsx        # Multi-tab / comprehensive POI curation drawer
│   ├── LocationFinderModal.tsx  # Map canvas, pin placement, adaptive zoom, reverse geocode
│   ├── POIMergeModal.tsx        # Dual-column comparison view, diff toggle, scalar/set radios
│   ├── DuplicateCollisionModal.tsx # 3-way triage dialog (Create New, Merge, Cancel)
│   ├── ParentPOISelector.tsx    # Debounced typeahead searchable dropdown
│   └── MultiAddressEditor.tsx   # Structured multi-address cards with normalization tags
├── services/
│   ├── poiService.ts            # Client SDK for POI update, merge, parents, duplicate check
│   └── geocodeService.ts        # Client forward search with debounce & reverse geocode API
└── types/
    └── api.ts                   # Synchronized TypeScript types via openapi-typescript

tests/
├── unit/
│   ├── services/poi/
│   │   ├── test_poi_update.py
│   │   ├── test_poi_merge.py
│   │   ├── test_poi_hierarchy.py
│   │   └── test_poi_duplicate.py
│   └── packages/core/
│       ├── test_address_normalization.py
│       └── test_visit_lifecycle.py
```

---

## Complexity Tracking

> **Zero Constitutional Violations**: All architectural components comply with Constitution v1.1.0 invariants. No complexity exceptions required.
