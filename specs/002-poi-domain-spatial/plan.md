# Implementation Plan: Point of Interest Domain & Geospatial Engine

**Branch**: `002-poi-domain-spatial` | **Date**: 2026-10-19 | **Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/spec.md)

**Input**: Feature specification from `specs/002-poi-domain-spatial/spec.md`

---

## Summary

Phase 2 (`002-poi-domain-spatial`) implements the Point of Interest (POI) domain, geospatial engine, and semantic search layer. The architectural design establishes:
1. Pure domain aggregates and value objects in `packages/core/vistarae_core/domain/` (`POI`, `ListEntity`, `TagEntity`, `GeocodingCacheEntry`, `WGS84Point`, `BoundingBox`, `DeduplicationPreset`, `MergeResolutionRule`), supporting cross-border and multi-jurisdiction destinations spanning multiple states and/or sovereign countries via JSONB string arrays (`states`, `countries`).
2. Dual-indexed PostGIS persistence in `packages/core/vistarae_core/adapters/db/tables.py` and `adapters/repositories/poi_repo.py`:
   - Planar viewport exploration using `(geom::geometry) && ST_MakeEnvelope(...)` backed by composite functional GiST index `idx_pois_user_geom_geometry`.
   - Geodesic proximity and distance sorting using `ST_DWithin` and `ST_Distance` on `geography(Point, 4326)` backed by composite GiST index `idx_pois_user_geom`.
   - JSONB containment filtering (`@>`) backed by GIN indexes `idx_pois_states_gin` and `idx_pois_countries_gin`.
3. Deterministic deduplication engine (`GET /api/pois/dedup-check`) combining `pg_trgm` name similarity ($\ge 0.60$) and geodesic proximity presets (805m urban vs 80,467m macro).
4. Atomic interactive record merging (`POST /api/pois/merge`) with attribute resolution rules, tag/list unioning within the 30-tag ceiling, subordinate child POI cascade re-parenting, and recursive loop cycle detection (RFC 7807 400).
5. Token-bucket geocoding via `GeocodingPort` (`MapboxGeocodingAdapter`) with 1 rps rate limiting, 90-day SHA-256 query caching in `geocoding_cache`, opportunistic expired row eviction, and 3.0s timeout fallback to `enrichment_status = 'PARTIAL'`.
6. High-dimensional vector semantic search via `EmbeddingPort` (`GeminiEmbeddingAdapter`) with 768 dimensions, composite text payload sanitization, MD5 checksum invalidation bypass, and HNSW cosine distance indexing (`idx_pois_embedding`).
7. Fully reversible Alembic migration revision `0002_poi_domain_spatial.py`.

---

## Technical Context

**Language/Version**: Python 3.12 (enforced by `pyproject.toml` `requires-python = ">=3.12"`)

**Primary Dependencies**:
- Web & Validation: `fastapi>=0.115.0`, `pydantic>=2.8.0`, `mangum>=0.17.0`
- Persistence & Geospatial: `sqlalchemy[asyncio]>=2.0.32`, `asyncpg>=0.29.0`, `geoalchemy2>=0.15.0`, `shapely>=2.0.0`, `alembic>=1.13.0`
- AI & Embeddings: `google-genai>=0.1.1`, `tenacity`
- Geocoding & Networking: `httpx>=0.27.0`
- Observability: `opentelemetry-api>=1.26.0`, `opentelemetry-sdk>=1.26.0`

**Storage**: PostgreSQL 16+ with extensions:
- `postgis` (3.4+)
- `btree_gist` (composite multi-column GiST indexes with UUID `user_id`)
- `pg_trgm` (trigram fuzzy string matching)
- `vector` (pgvector for 768-dim HNSW embeddings)
- `uuid-ossp` (server-default UUID generation)

**Testing**: `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `pytest-cov>=5.0.0` enforcing $\ge 90\%$ branch and line coverage ceiling.

**Target Platform**: Linux server / AWS Lambda container runtime (via Mangum) + local Docker Compose (`postgis/postgis:16-3.4`).

**Project Type**: Monorepo with shared editable core library (`packages/core`) and modular domain service (`services/poi`).

**Performance Goals**:
- Planar viewport queries (`GET /api/pois?bbox=...`): $< 75$ms p95 latency for up to 200 spatial points over 10,000 indexed records (SC-001).
- Geocoding cache resolution: $< 10$ms response latency with 0 outbound network requests on cache hits (SC-002).
- Interactive merge operations: $< 150$ms atomic execution with 0 orphaned relationships (SC-004).

**Constraints**:
- Zero-Cost architecture (no DynamoDB, CloudWatch PutMetricData, or Redis).
- Canonical WGS-84 coordinate storage (`EPSG:4326`); China bounding box shifts (GCJ-02/BD-09) isolated strictly to frontend clients.
- Multi-tenant tenant scoping (`WHERE user_id = :current_user_id`) enforced across all database queries.
- Strict tag ceiling: maximum 30 tags per POI, max 64 characters per tag.
- Geocoding outbound rate limit: maximum 1 request per second token bucket; 3.0s timeout ceiling.

**Scale/Scope**: Up to 10,000 POIs per tenant, 20 REST endpoints across POIs, deduplication, merging, curated lists, and tags.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Rule | Compliance Status | Analysis & Evidence |
|---|---|---|
| **Principle 1: File Headers & Pre-Commit** | **PASS** | All new source files (`.py`, `.sql`) mandate Apache-2.0 copyright header banner, Google-style docstrings, cognitive complexity $\le 15$, and max 3 indentation levels. |
| **Principle 2: Ports & Adapters Architecture** | **PASS** | Domain entities (`POI`, `ListEntity`, `TagEntity`) and interfaces (`IPOIRepository`, `IGeocodingPort`, `IEmbeddingPort`) reside in `packages/core`. Adapters (`POIRepository`, `MapboxGeocodingAdapter`, `GeminiEmbeddingAdapter`) are isolated in `packages/core/vistarae_core/adapters/`. `services/poi` handles HTTP routing and Mangum entrypoints. |
| **Principle 3: Database, PgBouncer & Tenancy** | **PASS** | All operations use SQLAlchemy 2.0 Pure Async components (`AsyncSession`). `WHERE user_id = :current_user_id` is enforced across all repository queries and composite GiST indexes. Row-Level Security (RLS) is strictly omitted. Prepared statement caching disabled via `statement_cache_size=0`. |
| **Principle 4: Alembic Isolation & Reversibility** | **PASS** | Migration `0002_poi_domain_spatial.py` provides a 100% reversible `downgrade()` function dropping all tables and indexes in reverse dependency order. All enum columns use Python `StrEnum` backed by `VARCHAR(n)` with `CheckConstraint` (no PostgreSQL native `ENUM`). |
| **Principle 5: API Contracts & Error Standards** | **PASS** | Authoritative OpenAPI 3.1 specification generated at `contracts/poi-api.yaml`. Boundary models use Pydantic v2 `StrictBaseModel`. All error responses formatted as RFC 7807 `ProblemDetails`. |
| **Principle 6: Middleware Order & Security** | **PASS** | LIFO middleware ordering (`RateLimitMiddleware` outermost, `IdempotencyMiddleware` innermost) maintained via `services.local_gateway`. No hardcoded API keys; all Mapbox/Gemini tokens injected via environment settings. |
| **Principle 7: Observability & OpenTelemetry** | **PASS** | Cross-boundary directional message logging (`MSG: -->|`, `MSG: <--|`) enforced for local runs; W3C `traceparent` passed across service calls. |
| **Principle 8: PyTest & SDD Governance** | **PASS** | Tests mirror production structure 1:1 under `tests/unit/services/poi/`. Total test coverage gate enforced at $\ge 90\%$ line and branch coverage. |
| **Operational Invariant 2: Geospatial Storage** | **PASS** | Coordinates stored canonically as `geography(Point, 4326)` in `pois.geom` and `geometry(MultiPolygon, 4326)` in `pois.region_geom`. Viewport queries use `(geom::geometry) && ST_MakeEnvelope` backed by composite functional GiST index `idx_pois_user_geom_geometry`. Miles converted to meters (`miles * 1609.344`). China coordinate shifts strictly isolated to frontend client. |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-poi-domain-spatial/
├── spec.md              # Ratified Feature Specification
├── plan.md              # This file (Implementation Plan)
├── research.md          # Phase 0 Architecture & Decisions Output
├── data-model.md        # Phase 1 Data Models, Schemas & Lifecycle
├── quickstart.md        # Phase 1 Runnable Developer Validation Guide
├── contracts/           # Phase 1 API Interface Specifications
│   └── poi-api.yaml     # OpenAPI 3.1 Contract for POI & Geospatial Service
├── checklists/
│   ├── requirements.md  # Built-in Specification Quality Checklist (16/16 Passed)
│   └── geospatial.md    # Domain Quality Checklist (27 Items)
└── tasks.md             # Phase 2 Work Breakdown (/speckit-tasks output)
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py              # POI, ListEntity, TagEntity, GeocodingCacheEntry
│   ├── value_objects.py         # VisitState, EnrichmentStatus, WGS84Point, BoundingBox, MergeResolutionRule
│   └── exceptions.py            # DuplicatePOIError, CyclicHierarchyError, TagLimitExceededError, GeocodingTimeoutError
├── ports/
│   ├── repositories.py          # IPOIRepository, IListRepository, ITagRepository, IGeocodingCacheRepository
│   ├── geocoding.py             # IGeocodingPort, GeocodingResult
│   └── embedding.py             # IEmbeddingPort
└── adapters/
    ├── db/
    │   └── tables.py            # POITable, ListTable, TagTable, POIListTable, POITagTable, GeocodingCacheTable
    ├── repositories/
    │   ├── poi_repo.py          # POIRepository (PostGIS dual-index queries, dedup, merge)
    │   ├── list_repo.py         # ListRepository (CRUD & public sharing)
    │   ├── tag_repo.py          # TagRepository (User tags with uniqueness)
    │   └── geocache_repo.py     # GeocodingCacheRepository (SHA-256 caching & opportunistic eviction)
    ├── geocoding/
    │   ├── mapbox.py            # MapboxGeocodingAdapter (v5/v6 APIs)
    │   ├── rate_limiter.py      # Async TokenBucketRateLimiter (1 rps)
    │   └── mock.py              # MockGeocodingAdapter (deterministic offline test adapter)
    └── embedding/
        ├── gemini.py            # GeminiEmbeddingAdapter (google-genai SDK, 768-dim, MD5 hash caching)
        └── mock.py              # MockEmbeddingAdapter (deterministic 768-dim vectors)

services/poi/
├── __init__.py
├── main.py                      # Standalone FastAPI service & lambda_handler = Mangum(app)
├── dependencies.py              # DI providers for repositories, adapters, and session
└── routes/
    ├── __init__.py
    ├── pois.py                  # GET /api/pois, POST /api/pois, GET/PATCH/DELETE /api/pois/{id}
    ├── dedup.py                 # GET /api/pois/dedup-check, POST /api/pois/merge
    ├── bulk.py                  # POST /api/pois/bulk-tags, bulk-lists, bulk-delete
    ├── lists.py                 # GET/POST /api/lists, GET /api/lists/{id}, GET /api/lists/{id}/shared
    └── tags.py                  # GET/POST /api/tags, DELETE /api/tags/{id}

db/migrations/versions/
├── 0001_foundation_auth_quota.py
└── 0002_poi_domain_spatial.py   # Reversible migration creating tables, constraints, GiST/HNSW/GIN indexes

tests/unit/services/poi/
├── test_entities.py             # Domain value objects, sanitization, coordinate bounds
├── test_poi_repo.py             # Spatial queries (bbox, ST_DWithin, ST_MakeEnvelope)
├── test_dedup_merge.py          # Trigram matching, merge resolution, cycle detection
├── test_geocoding.py            # Rate limiting, SHA-256 cache, timeout fallback
├── test_embedding.py            # MD5 hash invalidation, payload normalization
└── test_routes.py               # FastAPI endpoint contracts and RFC 7807 error boundaries
```

**Structure Decision**: Monorepo adhering to Ports & Adapters Architecture. Core business entities, ports, and persistence adapters are housed in editable `packages/core/vistarae_core`. Service routes and HTTP application wiring are housed in `services/poi/`. The unified local gateway (`services/local_gateway.py`) mounts the POI service under `/api`.

---

## Complexity Tracking

> **Constitution Check passed with zero violations.** No complexity justifications required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | N/A | N/A |
