---
description: "Task list for Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)"
---

# Tasks: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Input**: Design documents from `/specs/015-poi-export-import-enhancements-v3/`  
**Prerequisites**: [`plan.md`](./plan.md) (required), [`spec.md`](./spec.md) (required for user stories), [`research.md`](./research.md), [`data-model.md`](./data-model.md), [`contracts/`](./contracts/)  
**Organization**: Tasks are grouped by user story (P1 $\rightarrow$ P2 $\rightarrow$ P3) and map directly to strict EARS requirement IDs (FR-001 through FR-020) and automated test/validation suites.

## Format: `- [ ] [TaskID] [P?] [Story] Description [REQ: ID] [Test: path]`

- **[P]**: Can run in parallel (independent file touchpoints with no incomplete dependencies)
- **[Story]**: User story classification (e.g. `[US1]`, `[US2]`, `[US3]`, `[US4]`, `[US5]`)
- **[REQ: ID]**: Strict EARS requirement traceability mapping
- **[Test: path]**: Dedicated test suite verifying task acceptance

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish build, contract, and migration prerequisites for international administrative modeling and staging workbench unification.

- [X] T-001 Verify database connectivity and execute Alembic head check against PostgreSQL 16+ on port 5433 [REQ: FR-001] [Test: `db/migrations/`]
- [X] T-002 [P] Export OpenAPI specification to `openapi.json` via gateway script `scripts/export_openapi.py` [REQ: FR-001, FR-006] [Test: `tests/unit/services/poi/test_poi_routes.py`]
- [X] T-003 [P] Execute frontend contract code generation `npm --prefix frontend run codegen` to generate TypeScript types in `frontend/src/types/api.ts` [REQ: FR-006] [Test: `frontend/src/types/api.ts`]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data layer, domain value objects, and repository mappings that MUST be complete before user story logic can execute.

- [X] T-004 Create Alembic database migration `db/migrations/versions/20261102_add_iso_address_fields.py` (Revision `0016`) adding `country_code`, `admin_level_1`, `admin_level_2`, `locality`, `raw_geocoding`, and `photo_directories` to `pois` and `ingest_candidates`, and creating composite index `idx_pois_iso_location` [REQ: FR-001, FR-002] [Test: `tests/unit/services/ingest/test_staging_service.py`]
- [X] T-005 [P] Update SQLAlchemy ORM table models `POITable` and `IngestCandidateTable` with ISO administrative columns and composite indexes in `packages/core/vistarae_core/adapters/db/tables.py` [REQ: FR-001, FR-002] [Test: `tests/unit/services/poi/test_viewport_repository.py`]
- [X] T-006 [P] Update domain entities `POI` and `IngestCandidate` in `packages/core/vistarae_core/domain/entities.py` and `AddressRecord` value object in `packages/core/vistarae_core/domain/value_objects.py` [REQ: FR-001] [Test: `tests/unit/services/poi/test_entities.py`]
- [X] T-007 [P] Update Pydantic schemas in `packages/core/vistarae_core/schemas/ingest_staging.py` and `packages/core/vistarae_core/schemas/poi.py` with ISO address fields, `photo_directories`, and `related_websites` [REQ: FR-001, FR-012] [Test: `tests/unit/services/ingest/test_staging_routes.py`]
- [X] T-008 Update repository persistence mappings in `packages/core/vistarae_core/adapters/repositories/ingest_candidate_repo.py` and `packages/core/vistarae_core/adapters/repositories/poi_repo.py` to persist and load all ISO address tiers and photo directories [REQ: FR-001, FR-016] [Test: `tests/unit/services/poi/test_dedup_merge.py`]

**Checkpoint**: Core domain and database foundation complete; user stories can now proceed.

---

## Phase 3: User Story 1 - Unified Staging Workbench Inspection & Perspective Sorting (Priority: P1) 🎯 MVP

**Goal**: Deliver a single, unified split-screen Import Staging Workbench with perspective switching ("POI" alphabetical vs "Location" geographic) and header-click sort overrides.

**Independent Test**: Mount `CSVImportWorkbenchModal` in Vitest, verify perspective dropdown toggle between "POI" and "Location", check bold POI name styling, and verify column header click overrides default sort order.

### Tests for User Story 1
- [X] T-009 [P] [US1] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying split layout, candidate counts, and initial candidate selection [REQ: FR-006] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-010 [P] [US1] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying perspective switcher ("POI" vs "Location") reorders columns and alters sort order [REQ: FR-006, FR-007] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]

### Implementation for User Story 1
- [X] T-011 [US1] Implement perspective state and sorting logic in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` supporting "POI" (alphabetical) and "Location" (geographic Country $\rightarrow$ State $\rightarrow$ City) modes [REQ: FR-006] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-012 [US1] Implement interactive column header click handlers in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` that override perspective default sorting while retaining active column order [REQ: FR-007] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-013 [US1] Render candidate POI Name in bold typography across both perspective modes in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` [REQ: FR-006] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]

**Checkpoint**: User Story 1 MVP fully operational and verified by automated unit tests.

---

## Phase 4: User Story 2 - International ISO Administrative Geocoding & English Translation (Priority: P1)

**Goal**: Implement deterministic Nominatim reverse geocode parsing fallback chains with whitespace trimming and mandatory English language negotiation (`Accept-Language: en`).

**Independent Test**: Execute backend pytest geocoding suite verifying Chicago urban museum, wilderness peak (NULL street/postal/locality), Singapore city-state (NULL admin_level_1/2), and UK constituent country / post town mapping.

### Tests for User Story 2
- [X] T-014 [P] [US2] Implement unit test in `tests/unit/services/ingest/test_staging_service.py` asserting Nominatim reverse geocoding fallback chain populates `street_address`, `country_code`, `admin_level_1`, `admin_level_2`, and `locality` [REQ: FR-003, FR-004] [Test: `tests/unit/services/ingest/test_staging_service.py`]
- [X] T-015 [P] [US2] Implement unit test in `tests/unit/services/poi/test_geocoding.py` verifying wilderness POI persists with NULL street address, postal code, and locality without constraint violations [REQ: FR-001, FR-004] [Test: `tests/unit/services/poi/test_geocoding.py`]
- [X] T-016 [P] [US2] Implement unit test in `tests/unit/services/worker/test_geocoder.py` verifying `Accept-Language: en` header and query parameter on outbound Nominatim requests [REQ: FR-005] [Test: `tests/unit/services/worker/test_geocoder.py`]

### Implementation for User Story 2
- [X] T-017 [US2] Implement `AddressNormalizer.parse_nominatim_iso_address(raw)` in `packages/core/vistarae_core/services/address_normalizer.py` implementing exact road combining, fallback chains, and whitespace/empty string cleanup [REQ: FR-003, FR-004] [Test: `tests/unit/services/ingest/test_staging_service.py`]
- [X] T-018 [US2] Update reverse geocoding service in `services/poi/services/geocode_service.py` to attach `Accept-Language: en`, parse ISO administrative tiers, and populate PostGIS geocache with raw responses [REQ: FR-004, FR-005] [Test: `tests/unit/services/poi/test_geocoding.py`]
- [X] T-019 [US2] Update forward geocoding service in `services/poi/services/geocoding_service.py` to attach `Accept-Language: en` and return structured `AddressRecord` with ISO tiers [REQ: FR-004, FR-005] [Test: `tests/unit/services/poi/test_geocoding.py`]
- [X] T-020 [US2] Update CSV parser and export mappings in `services/ingest/services/csv_parser.py` and `services/ingest/routes/export.py` to align with ISO headers and Photo Scraper formats [REQ: FR-020] [Test: `tests/unit/services/ingest/test_csv_parser.py`]

**Checkpoint**: User Stories 1 and 2 operate cohesively; international addresses parse into ISO tiers in English.

---

## Phase 5: User Story 3 - Interactive Mapping & Proximity Spatial Clustering (Priority: P2)

**Goal**: Embed interactive MapLibre GL map with draggable coordinate pin, click-to-relocate, non-destructive "Re-sync Address from Pin" button, and proximity radius nearby POI markers.

**Independent Test**: Test `WorkbenchMap.tsx` in Vitest verifying coordinate updates on pin drag, map click handler, "Re-sync Address from Pin" button rendering, and nearby POI count badge updates as slider adjusts.

### Tests for User Story 3
- [X] T-021 [P] [US3] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying primary marker renders and dragging updates `latitude` and `longitude` fields [REQ: FR-010] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-022 [P] [US3] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying proximity radius slider plots nearby DB and staged batch points and updates count badge [REQ: FR-011] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]

### Implementation for User Story 3
- [X] T-023 [US3] Create `frontend/src/components/ingest/WorkbenchMap.tsx` utilizing MapLibre GL, draggable pin, click-to-relocate, and nearby POI markers [REQ: FR-010, FR-011] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-024 [US3] Implement non-destructive "Re-sync Address from Pin" button in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` that triggers on-demand reverse geocoding without automatic destructive overwrites [REQ: FR-010] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-025 [US3] Implement dynamic proximity filtering in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` calculating nearby points within slider range (excluding ignored/excluded) [REQ: FR-011] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]

**Checkpoint**: Interactive spatial mapping and proximity clustering verified.

---

## Phase 6: User Story 4 - Rich Media, Tags Library & Dynamic Website Management (Priority: P2)

**Goal**: Deliver dynamic website management with confirmation dialogs, strict Tag Library chips, uncropped hero preview, local photo directories manager, reason to visit, color-coded confidence score badge, and additive union merges on commit.

**Independent Test**: In Vitest and Pytest, test adding/deleting dynamic websites with confirmation prompts, toggling Tag Library chips, managing photo directories, and committing an in-batch merge with additive deduplicated union.

### Tests for User Story 4
- [X] T-026 [P] [US4] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying dynamic website addition and deletion with `window.confirm` dialog [REQ: FR-012, FR-013] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-027 [P] [US4] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying Tag Library chip selection strictly against `/api/tags` [REQ: FR-015] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-028 [P] [US4] Create unit test in `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx` verifying in-batch merge target selector display and confidence score badge color styling [REQ: FR-008, FR-018] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-029 [P] [US4] Create integration test in `tests/unit/services/ingest/test_commit_staging.py` verifying commit of in-batch merged candidates performs additive union merge of dates, tags, photo directories, and websites [REQ: FR-008] [Test: `tests/unit/services/ingest/test_commit_staging.py`]

### Implementation for User Story 4
- [X] T-030 [US4] Implement dynamic website `{ name, url }` manager in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` with Add action and Delete confirmation prompt [REQ: FR-012, FR-013] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-031 [US4] Implement account Tag Library chip selector in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` toggling candidate tags strictly from `/api/tags` [REQ: FR-015] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-032 [US4] Implement uncropped hero photo preview container beneath URL input in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` with max-height ceiling [REQ: FR-009] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-033 [US4] Implement local photo directory manager, interactive visit dates manager, and Reason to Visit textarea in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` [REQ: FR-016, FR-017, FR-019] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-034 [US4] Implement readonly disposition justification and confidence score badge with color tier scale ($\ge 90\%$ green, $80\text{–}89\%$ lime, $70\text{–}79\%$ yellow, $<70\%$ orange/red) in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` [REQ: FR-018] [Test: `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`]
- [X] T-035 [US4] Implement in-batch merge target selector card in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` and additive deduplicated union commit logic in `services/ingest/services/staging_service.py` [REQ: FR-008] [Test: `tests/unit/services/ingest/test_commit_staging.py`]

**Checkpoint**: Rich media, tag governance, photo directories, and in-batch union merges verified.

---

## Phase 7: User Story 5 - AI Enrichment Idempotency & "No Websites" Policy (Priority: P3)

**Goal**: Enforce website enrichment idempotency: skip website lookup when $\ge 1$ website exists or "No Websites" is true; auto-set "No Websites" to true if 0 websites are found by AI.

**Independent Test**: Run worker pytest suite asserting AI enrichment skips external website lookups when websites exist or "No Websites" is True.

### Tests for User Story 5
- [X] T-036 [P] [US5] Implement unit test in `tests/unit/services/worker/test_candidate_enricher.py` verifying website scraping is bypassed when candidate has $\ge 1$ website or `no_websites = True` [REQ: FR-014] [Test: `tests/unit/services/worker/test_candidate_enricher.py`]

### Implementation for User Story 5
- [X] T-037 [US5] Update AI candidate enricher in `services/worker/candidate_enricher.py` to enforce the "No Websites" skip and auto-set policy [REQ: FR-014] [Test: `tests/unit/services/worker/test_candidate_enricher.py`]

**Checkpoint**: AI enrichment idempotency verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting observability, traceparent propagation, full test suite pass, and quickstart verification.

- [X] T-038 [P] Verify W3C distributed tracing (`traceparent`, `X-Source`, `X-Destination`) and messaging tags protocol (`MSG ->|`, `MSG <-|`, `MSG   |->`, `MSG   |<-`) across all ingest staging routes in `services/ingest/routes/staging.py` [REQ: FR-001] [Test: `tests/unit/services/ingest/test_staging_routes.py`]
- [X] T-039 [P] Execute full frontend unit test suite `npm --prefix frontend run test:unit` verifying all 43 test suites pass [REQ: FR-006, FR-010, FR-015] [Test: `frontend/src/tests/`]
- [X] T-040 [P] Execute full backend unit test suites across ingest, poi, and worker services with zero regressions [REQ: FR-001, FR-004, FR-014] [Test: `tests/unit/`]
- [X] T-041 [P] Validate complete end-to-end walkthrough per `specs/015-poi-export-import-enhancements-v3/quickstart.md` [REQ: FR-006, FR-008, FR-020] [Test: `quickstart.md`]

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 (Setup)**: Can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1; BLOCKS all User Stories.
- **Phase 3 (User Story 1 - MVP)**: Can start after Phase 2 completion.
- **Phase 4 (User Story 2)**: Can start after Phase 2 completion; integrates with User Story 1.
- **Phase 5 (User Story 3)**: Can start after Phase 2 completion; integrates with User Story 1 detail view.
- **Phase 6 (User Story 4)**: Can start after Phase 2 completion; integrates with User Story 1 & 2.
- **Phase 7 (User Story 5)**: Can start after Phase 2 completion.
- **Phase 8 (Polish)**: Depends on completion of all user story phases.

### Parallel Execution Opportunities
- Tasks marked with `[P]` (e.g. T-002, T-003, T-005, T-006, T-007, T-009, T-010, T-014, T-015, T-016, T-021, T-022, T-026, T-027, T-028, T-029, T-036, T-038, T-039, T-040, T-041) can be executed concurrently in separate sessions or worktrees.
- Unit test tasks within each story phase can be authored and validated concurrently prior to implementation code updates.

---

## Implementation Strategy: MVP First

1. **Step 1: Setup & Foundation (Phases 1 & 2)**: Apply migration `0016`, update ORM tables, entities, schemas, and repository mappings.
2. **Step 2: MVP Delivery (Phase 3)**: Complete `CSVImportWorkbenchModal.tsx` split layout and perspective switcher (POI vs Location). Validate independently via `frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx`.
3. **Step 3: Geocoding & Addresses (Phase 4)**: Implement `AddressNormalizer` ISO fallbacks and English negotiation. Validate via backend test suite.
4. **Step 4: Interactive Map (Phase 5)**: Integrate `WorkbenchMap.tsx` with MapLibre GL, draggable pin, and "Re-sync Address from Pin".
5. **Step 5: Rich Fields & Union Merge (Phase 6)**: Implement websites list, Tag Library chips, uncropped hero preview, and additive union commit.
6. **Step 6: AI Enrichment & Polish (Phases 7 & 8)**: Enforce idempotency and verify end-to-end via `quickstart.md`.
