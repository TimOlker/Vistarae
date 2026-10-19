# Tasks: Point of Interest Domain & Geospatial Engine

**Feature**: `002-poi-domain-spatial` | **Branch**: `002-poi-domain-spatial`  
**Input**: [spec.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/spec.md), [plan.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/plan.md), [data-model.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/data-model.md), [contracts/poi-api.yaml](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/contracts/poi-api.yaml)

---

## Phase 1: Setup & Environment Initialization

**Purpose**: Database extensions, migrations, and test harness infrastructure.

- [X] T-001 Configure and verify database extensions (`postgis`, `btree_gist`, `pg_trgm`, `vector`, `uuid-ossp`) in `docker-compose.yml` and workspace dependencies in `pyproject.toml` [REQ-GEO-001, REQ-GEO-002]
- [X] T-002 Create reversible Alembic migration revision `db/migrations/versions/0002_poi_domain_spatial.py` defining tables `pois`, `lists`, `tags`, `poi_lists`, `poi_tags`, `geocoding_cache`, check constraints (`ck_pois_visit_state`, `ck_pois_rating`, `ck_pois_duration`, `ck_pois_enrichment`), composite GiST indexes (`idx_pois_user_geom`, `idx_pois_user_geom_geometry`), GIN indexes (`idx_pois_states_gin`, `idx_pois_countries_gin`, `idx_pois_name_trgm`), HNSW vector index (`idx_pois_embedding`), and fully reversible `downgrade()` [REQ-POI-001, REQ-POI-002, REQ-POI-003, REQ-POI-004, REQ-POI-005, REQ-POI-006, REQ-POI-007, REQ-GEO-001, REQ-GEO-002, REQ-GEO-003, REQ-GEO-004, REQ-GEO-005, REQ-GEO-006, REQ-EMBED-001]
- [X] T-003 [P] Implement migration verification tests in `tests/unit/db/test_0002_migration.py` verifying clean schema creation, check constraints, composite GiST index operator classes, and complete downgrade reversibility [REQ-POI-001, REQ-GEO-001]

---

## Phase 2: Foundational Architecture & Core Interfaces (Blocking Prerequisites)

**Purpose**: Core domain entities, value objects, ports, and SQLAlchemy tables that MUST be complete before ANY user story can be implemented.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T-004 [P] Implement domain value objects and exceptions in `packages/core/vistarae_core/domain/value_objects.py` and `exceptions.py` (`VisitState`, `EnrichmentStatus`, `WGS84Point` with China bounding box check `73.66°E <= lon <= 135.05°E, 18.16°N <= lat <= 53.55°N`, `BoundingBox` with antimeridian detection, `DeduplicationPreset`, `MergeResolutionRule`, `CyclicHierarchyError`, `TagLimitExceededError`, `GeocodingTimeoutError`) [REQ-POI-002, REQ-POI-003, REQ-POI-004, REQ-POI-005, REQ-POI-012, REQ-POI-013, REQ-GEO-016]
- [X] T-005 [P] Implement pure domain entities in `packages/core/vistarae_core/domain/entities.py` (`POI`, `ListEntity`, `TagEntity`, `GeocodingCacheEntry`, `PotentialDuplicateMatch`) supporting native JSONB string arrays `states: list[str]` and `countries: list[str]` [REQ-POI-001, REQ-POI-006, REQ-POI-007, REQ-GEO-005]
- [X] T-006 [P] Define port protocols in `packages/core/vistarae_core/ports/` (`IPOIRepository`, `IListRepository`, `ITagRepository`, `IGeocodingCacheRepository` in `repositories.py`; `IGeocodingPort` and `GeocodingResult` in `geocoding.py`; `IEmbeddingPort` in `embedding.py`) [REQ-GEO-014, REQ-EMBED-002]
- [X] T-007 [P] Implement SQLAlchemy 2.0 ORM tables in `packages/core/vistarae_core/adapters/db/tables.py` (`POITable`, `ListTable`, `TagTable`, `POIListTable`, `POITagTable`, `GeocodingCacheTable`) with GeoAlchemy2 `Geography(Point, 4326)` and `Geometry(MultiPolygon, 4326)` [REQ-POI-001, REQ-POI-006, REQ-POI-007, REQ-GEO-001, REQ-GEO-004, REQ-GEO-005]
- [X] T-008 [P] Unit tests for domain entities, value objects, and coordinate bounds in `tests/unit/services/poi/test_entities.py` [REQ-POI-001, REQ-GEO-016]

**Checkpoint**: Core foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Planar Viewport POI Exploration & Combinable Filtering (Priority: P1) 🎯 MVP

**Goal**: Enable users to view, explore, and filter POIs within a 2D map viewport bounding box with high performance, supporting multi-facet filtering (tags, visit state, lists, hierarchy, state, country).

**Independent Test**: Create 10 POIs across North America and query `GET /api/pois?bbox=-120.0,37.0,-119.0,38.0&visit_state=not_visited&hierarchy=root_only&state=California`, asserting only matching points return in under 75ms p95 latency.

### Tests for User Story 1
- [X] T-009 [P] [US1] Unit & integration tests for viewport bounding-box queries, antimeridian split queries, and multi-facet filtering in `tests/unit/services/poi/test_viewport_repository.py` [REQ-POI-008, REQ-POI-009, REQ-POI-010, REQ-POI-011, REQ-GEO-003, REQ-GEO-004]

### Implementation for User Story 1
- [X] T-010 [US1] Implement PostGIS repository query builder in `packages/core/vistarae_core/adapters/repositories/poi_repo.py` executing planar `(geom::geometry) && ST_MakeEnvelope` utilizing `idx_pois_user_geom_geometry`, antimeridian split handling, JSONB containment (`states @>`, `countries @>`), and combinable filters [REQ-POI-008, REQ-POI-009, REQ-POI-010, REQ-POI-011, REQ-GEO-003, REQ-GEO-004]
- [X] T-011 [P] [US1] Implement Pydantic v2 schemas for POI creation, updates, and list responses in `packages/core/vistarae_core/schemas/poi.py` (`POICreateRequest`, `POIUpdateRequest`, `POIResponse`, `POIListResponse`) [REQ-POI-001, REQ-POI-008]
- [X] T-012 [US1] Implement POI CRUD and viewport exploration endpoints in `services/poi/routes/pois.py` (`GET /api/pois`, `POST /api/pois`, `GET /api/pois/{id}`, `PATCH /api/pois/{id}`, `DELETE /api/pois/{id}`) [REQ-POI-001, REQ-POI-008]
- [X] T-013 [P] [US1] Unit tests for POI routes and RFC 7807 problem details error boundaries in `tests/unit/services/poi/test_poi_routes.py` [REQ-POI-001, REQ-POI-008, REQ-POI-012]
- [X] T-014 [US1] Mount `services.poi.main:app` into unified local gateway router in `services/local_gateway.py` under `/api` [REQ-POI-008]

**Checkpoint**: User Story 1 is fully functional and independently testable as the core MVP.

---

## Phase 4: User Story 2 - Deduplication Detection & Interactive Record Merge (Priority: P2)

**Goal**: Identify potential duplicates within configurable proximity presets using trigram similarity and allow users to interactively merge conflicting records without data loss or cyclic hierarchy corruption.

**Independent Test**: Post two POIs located 400m apart with similar names ("Glacier Point" vs "Glacier Point Overlook"), verify collision detection flags them with `distance_meters < 805` and `name_similarity >= 0.60`, and execute `POST /api/pois/merge` asserting target POI retains selected attributes and children are safely re-parented.

### Tests for User Story 2
- [X] T-015 [P] [US2] Unit & integration tests for trigram similarity deduplication and interactive merge in `tests/unit/services/poi/test_dedup_merge.py` [REQ-POI-017, REQ-POI-018, REQ-POI-019]

### Implementation for User Story 2
- [X] T-016 [US2] Implement `find_potential_duplicates` in `packages/core/vistarae_core/adapters/repositories/poi_repo.py` combining `similarity(name, :candidate_name) >= 0.60` with `ST_DWithin` on `geography(Point, 4326)` using configurable proximity presets (805m urban vs 80,467m macro) [REQ-POI-017, REQ-POI-018, REQ-GEO-002]
- [X] T-017 [US2] Implement cycle detection and recursive hierarchy validation in `packages/core/vistarae_core/services/hierarchy.py` to prevent cyclic parent-child loops during parent assignment and merges [REQ-POI-012, REQ-POI-019]
- [X] T-018 [US2] Implement atomic interactive merge engine `merge_pois` in `packages/core/vistarae_core/adapters/repositories/poi_repo.py` handling attribute copying, list/tag unioning, child POI cascade re-parenting, and source deletion within a single transaction [REQ-POI-013, REQ-POI-019]
- [X] T-019 [US2] Implement deduplication and merge route endpoints in `services/poi/routes/dedup.py` (`GET /api/pois/dedup-check`, `POST /api/pois/merge`) [REQ-POI-017, REQ-POI-018, REQ-POI-019]

**Checkpoint**: User Stories 1 AND 2 are both functional and testable independently.

---

## Phase 5: User Story 3 - Cached, Rate-Limited Geocoding & Address Resolution (Priority: P3)

**Goal**: Enrich POI records with canonical coordinates and standardized addresses via Mapbox with a 1 rps token bucket, 90-day SHA-256 caching, opportunistic cleanup, and 3.0s timeout fallback.

**Independent Test**: Geocode an address twice; verify the first request calls the provider and writes to `geocoding_cache`, while the second returns immediately in $< 10$ms with 0 outbound network requests.

### Tests for User Story 3
- [X] T-020 [P] [US3] Unit tests for token bucket rate limiter, SHA-256 caching, opportunistic eviction, and 3.0s timeout fallback in `tests/unit/services/poi/test_geocoding.py` [REQ-GEO-005, REQ-GEO-006, REQ-GEO-007, REQ-GEO-008, REQ-GEO-009, REQ-GEO-010, REQ-GEO-011, REQ-GEO-012, REQ-GEO-013]

### Implementation for User Story 3
- [X] T-021 [P] [US3] Implement asynchronous `TokenBucketRateLimiter` (1 request per second sustained) in `packages/core/vistarae_core/adapters/geocoding/rate_limiter.py` [REQ-GEO-011]
- [X] T-022 [P] [US3] Implement `GeocodingCacheRepository` in `packages/core/vistarae_core/adapters/repositories/geocache_repo.py` with 90-day TTL index, SHA-256 query/coordinate hashing, and opportunistic expired row cleanup (`DELETE FROM geocoding_cache WHERE expires_at <= NOW()`) [REQ-GEO-005, REQ-GEO-006, REQ-GEO-007, REQ-GEO-008, REQ-GEO-009, REQ-GEO-010, REQ-GEO-013]
- [X] T-023 [US3] Implement `MapboxGeocodingAdapter` in `packages/core/vistarae_core/adapters/geocoding/mapbox.py` with 3.0s timeout fallback to user coordinates and `enrichment_status = 'PARTIAL'`, along with `MockGeocodingAdapter` in `mock.py` [REQ-GEO-012, REQ-GEO-014, REQ-GEO-015]
- [X] T-024 [US3] Wire geocoding resolution pipeline into `services/poi/dependencies.py` and POI creation workflow in `services/poi/routes/pois.py` [REQ-GEO-005, REQ-GEO-012, REQ-GEO-014, REQ-GEO-015]

**Checkpoint**: User Stories 1, 2, and 3 are fully operational with geocoding caching active.

---

## Phase 6: User Story 4 - Semantic & Vector Similarity POI Discovery (Priority: P4)

**Goal**: Provide natural language conceptual search over saved POIs via 768-dimensional Gemini vector embeddings and HNSW cosine distance indexing, short-circuiting unchanged records via composite MD5 checksums.

**Independent Test**: Generate embeddings for POIs, update only `rating`, verify `embedding_md5` is preserved and Gemini is not called, then issue `GET /api/pois?semantic_q=misty+mountain+views` and assert top cosine similarity matches rank highest.

### Tests for User Story 4
- [X] T-025 [P] [US4] Unit tests for composite text sanitization, MD5 checksum calculation, short-circuit bypass, and cosine distance search in `tests/unit/services/poi/test_embedding.py` [REQ-EMBED-001, REQ-EMBED-003, REQ-EMBED-004, REQ-EMBED-005, REQ-EMBED-006, REQ-EMBED-007, REQ-EMBED-008, REQ-EMBED-009, REQ-EMBED-010]

### Implementation for User Story 4
- [X] T-026 [P] [US4] Implement text payload normalizer and MD5 hasher in `packages/core/vistarae_core/services/embedding_sanitizer.py` (null coalescing, whitespace collapsing, alphabetical sorted tag formatting) [REQ-EMBED-004, REQ-EMBED-005]
- [X] T-027 [US4] Implement `GeminiEmbeddingAdapter` in `packages/core/vistarae_core/adapters/embedding/gemini.py` utilizing `google-genai` SDK (768 dimensions) with `tenacity` retry loop, and `MockEmbeddingAdapter` in `mock.py` [REQ-EMBED-002, REQ-EMBED-003, REQ-EMBED-007, REQ-EMBED-008]
- [X] T-028 [US4] Implement semantic search in `packages/core/vistarae_core/adapters/repositories/poi_repo.py` executing `pois.embedding.cosine_distance(query_vector)` backed by HNSW index `idx_pois_embedding` with normalized `similarity_score = 1.0 - cosine_distance` [REQ-EMBED-001, REQ-EMBED-009, REQ-EMBED-010]
- [X] T-029 [US4] Integrate `semantic_q` query parameter into `GET /api/pois` route in `services/poi/routes/pois.py` [REQ-POI-008, REQ-EMBED-009, REQ-EMBED-010]

**Checkpoint**: Conceptual vector discovery is live alongside planar spatial search.

---

## Phase 7: User Story 5 - Bulk Organization & Collaborative Sharing (Priority: P5)

**Goal**: Support bulk operations (tagging, list assignment, batch deletions) and collaborative read-only list sharing.

**Independent Test**: Select 5 POIs, execute `POST /api/pois/bulk-tags` to add "roadtrip-2026", verify all 5 reflect the association in a single transaction, and access `GET /api/lists/{id}/shared` without ownership credentials.

### Tests for User Story 5
- [X] T-030 [P] [US5] Unit & integration tests for bulk operations, list management, tag assignment, and shared lists in `tests/unit/services/poi/test_bulk_lists_tags.py` [REQ-POI-006, REQ-POI-007, REQ-POI-013, REQ-POI-014, REQ-POI-015, REQ-POI-016, REQ-POI-020]

### Implementation for User Story 5
- [X] T-031 [P] [US5] Implement `ListRepository` in `packages/core/vistarae_core/adapters/repositories/list_repo.py` supporting user-owned lists and public shared list retrieval (`is_public = TRUE`) [REQ-POI-006, REQ-POI-020]
- [X] T-032 [P] [US5] Implement `TagRepository` in `packages/core/vistarae_core/adapters/repositories/tag_repo.py` enforcing per-user unique tag names and 30-tag ceiling per POI [REQ-POI-007, REQ-POI-013]
- [X] T-033 [US5] Implement bulk repository methods `bulk_delete`, `bulk_attach_tags`, `bulk_detach_tags`, `bulk_attach_lists`, `bulk_detach_lists` in `packages/core/vistarae_core/adapters/repositories/poi_repo.py` [REQ-POI-014, REQ-POI-015, REQ-POI-016]
- [X] T-034 [US5] Implement endpoints for lists, shared lists, tags, and bulk operations in `services/poi/routes/lists.py`, `services/poi/routes/tags.py`, and `services/poi/routes/bulk.py` [REQ-POI-006, REQ-POI-007, REQ-POI-014, REQ-POI-015, REQ-POI-016, REQ-POI-020]

**Checkpoint**: All user stories are implemented, isolated, and verified.

---

## Phase 8: Polish & Cross-Cutting Integration

**Purpose**: OpenAPI synchronization, end-to-end quickstart validation, and strict test coverage enforcement.

- [X] T-035 [P] Implement OpenAPI schema export and sync verification in `scripts/export_openapi.py` asserting TypeScript contract compliance (`git diff --exit-code ./frontend/src/types/api.ts`) [Constitution §Principle 5]
- [X] T-036 Execute quickstart validation scenarios from `quickstart.md` against the local gateway on port 8030 verifying viewport lookups, dedup probes, merges, and semantic queries [Success Criteria SC-001, SC-002, SC-003, SC-004, SC-005]
- [X] T-037 Execute complete test suite with coverage enforcement (`uv run pytest --cov=packages/core --cov=services --cov-fail-under=90`) asserting $\ge 90\%$ branch and line coverage [Constitution §Principle 8, SC-006]

---

## Dependencies & Execution Order

### Phase Dependencies
1. **Phase 1 (Setup)**: Can start immediately.
2. **Phase 2 (Foundational)**: Depends on Phase 1 completion — **BLOCKS ALL USER STORIES**.
3. **Phase 3 (User Story 1 - MVP)**: Depends on Phase 2 completion.
4. **Phases 4-7 (User Stories 2-5)**: Can proceed sequentially or in parallel once Phase 2 (and T-010 in Phase 3 for shared POI repository foundation) is established.
5. **Phase 8 (Polish)**: Depends on completion of all user story phases.

### User Story Dependencies
- **User Story 1 (P1)**: Core spatial foundation. No story dependencies.
- **User Story 2 (P2)**: Extends `POIRepository` with `similarity()` and `merge_pois`.
- **User Story 3 (P3)**: Injects geocoding enrichment into `POIRepository.create`.
- **User Story 4 (P4)**: Injects vector embedding and HNSW cosine distance search into `POIRepository.list_pois`.
- **User Story 5 (P5)**: Adds `ListRepository`, `TagRepository`, and bulk mutations onto `POIRepository`.

### Parallel Execution Opportunities
- Setup & Foundational: `T-003`, `T-004`, `T-005`, `T-006`, `T-007`, `T-008` can all be executed in parallel.
- User Story 1: `T-009` (tests) and `T-011` (schemas) can execute in parallel before `T-010`/`T-012`.
- User Story 2: `T-015` (tests) can execute in parallel with `T-017` (hierarchy service).
- User Story 3: `T-020` (tests), `T-021` (rate limiter), and `T-022` (geocache repo) can execute in parallel.
- User Story 4: `T-025` (tests) and `T-026` (sanitizer) can execute in parallel before `T-027`/`T-028`.
- User Story 5: `T-030` (tests), `T-031` (list repo), and `T-032` (tag repo) can execute in parallel.

---

## Implementation Strategy

### MVP Milestone (Phases 1-3)
1. Complete Phase 1 (Extensions & Migration `0002`) and Phase 2 (Domain Entities, Value Objects, Ports, ORM Tables).
2. Complete Phase 3 (User Story 1): Planar Viewport POI Exploration & Combinable Filtering.
3. Validate independent test criteria for User Story 1 ($< 75$ms p95 latency on viewport lookups).

### Incremental Feature Milestones
- **Increment 1**: Deduplication Detection & Merge Engine (Phase 4).
- **Increment 2**: Token-Bucket Cached Geocoding (Phase 5).
- **Increment 3**: Semantic Vector Search with Gemini Embeddings (Phase 6).
- **Increment 4**: Bulk Organization & Public List Sharing (Phase 7).
- **Increment 5**: Complete Polish, Quickstart Validation, and 90% Coverage Gate (Phase 8).
