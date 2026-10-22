# Implementation Tasks: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Feature Identifier**: `007-ui-edit-poi-enhancements`  
**Feature Branch**: `007-ui-edit-poi-enhancements`  
**Date**: 2026-10-21  
**Status**: Ready for Implementation  
**Specification**: [spec.md](./spec.md) | **Implementation Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/poi-edit-api.yaml](./contracts/poi-edit-api.yaml) | **Quickstart**: [quickstart.md](./quickstart.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify development runtime, dependencies, and contract synchronization tooling.

- [x] T-001 Verify Python 3.12 and Node.js environments and ensure `packages/core` workspace package is installed in editable mode (`pip install -e ./packages/core`) in root `pyproject.toml`.
- [x] T-002 [P] Configure frontend API contract export and TypeScript generation scripts in `frontend/package.json` (`npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema migrations, domain entities, value objects, and repository query methods required by all user stories.

**⚠️ CRITICAL**: No user story implementation work can begin until this foundational phase is complete.

- [x] T-003 Create Alembic migration `db/migrations/versions/0005_poi_edit_enhancements.py` adding columns (`description` TEXT, `parent_poi_id` UUID FK to `pois.id` ON DELETE SET NULL, `addresses` JSONB DEFAULT `'[]'`, `recommended_duration_hours` NUMERIC(4,2), `recommended_visit_days` INTEGER DEFAULT 1, `source_type` VARCHAR(50) DEFAULT `'Manual'`, `source_value` VARCHAR(1000), `official_url` VARCHAR(2000), `wiki_url` VARCHAR(2000), `directory_paths` JSONB DEFAULT `'[]'`, `image_urls` JSONB DEFAULT `'[]'`, `visited_dates` JSONB DEFAULT `'[]'`, `want_to_visit_again` BOOLEAN DEFAULT FALSE, `already_visited` BOOLEAN DEFAULT FALSE, `visit_pending` BOOLEAN DEFAULT TRUE), GIN index `idx_pois_addresses_path` on `addresses jsonb_path_ops`, B-Tree index `idx_pois_user_parent` on `(user_id, parent_poi_id)`, check constraint `chk_pois_parent_not_self`, legacy data backfill, and reversible `downgrade()` in `db/migrations/versions/0005_poi_edit_enhancements.py`.
- [x] T-004 [P] Implement `AddressRecord` value object (with `street` max 255, `city` max 100, `state_province` max 100, `country` required min 2 max 100, `postal_code` max 32) and `SourceType` StrEnum (`Web`, `CSV`, `Manual`, `Photo`) in `packages/core/vistarae_core/domain/value_objects.py`. [REQ-EDIT-002, REQ-EDIT-007]
- [x] T-005 [P] Implement state/province and country English standard normalization engine in `packages/core/vistarae_core/services/address_normalizer.py`. [REQ-EDIT-003, REQ-EDIT-004]
- [x] T-006 [P] Update `POI` domain aggregate entity in `packages/core/vistarae_core/domain/entities.py` with multi-address array, `parent_poi_id`, duration fields, local photo paths, gallery URLs, and `@model_validator` for deterministic visit lifecycle state calculation (`already_visited`, `visit_pending`). [REQ-EDIT-001, REQ-EDIT-005, REQ-EDIT-006, REQ-EDIT-009, REQ-EDIT-011, REQ-EDIT-013]
- [x] T-007 [P] Update Pydantic schemas in `packages/core/vistarae_core/schemas/poi.py` (`POIUpdateRequest` with `extra="forbid"`, `POIReadResponse` with parent name and address records). [REQ-EDIT-001, REQ-EDIT-002, REQ-EDIT-013]
- [x] T-008 Update base POI SQLAlchemy repository queries in `services/poi/repositories/poi_repository.py` with `WHERE user_id = :current_user_id` tenant isolation, JSONB address serialization, and parent POI join. [REQ-SAVE-004, REQ-EDIT-013]

**Checkpoint**: Foundation ready — database schema, core domain models, and tenant-isolated repository lookups verified.

---

## Phase 3: User Story 1 - Rich POI Field Editing, Hierarchical Parenting & Visit Tracking (Priority: P1) 🎯 MVP

**Goal**: Enable travelers to edit rich notes, assign hierarchical parent POIs with cycle exclusion, manage multiple international address records, and track chronological visit history with return intent.

**Independent Test**: Open the POI Editor for an existing POI, assign a parent POI from typeahead suggestions, enter multiple addresses with foreign country aliases, add visit dates, toggle "visit again", and assert normalized values, hierarchy links, and computed flags (`already_visited`, `visit_pending`) are persisted.

### Tests for User Story 1

- [x] T-009 [P] [US1] Write unit tests for POI update, hierarchical parent selection, and cycle rejection in `tests/unit/services/poi/test_poi_update.py`. [REQ-EDIT-001, REQ-EDIT-012, REQ-EDIT-014]

### Implementation for User Story 1

- [x] T-010 [US1] Implement recursive CTE hierarchy service in `services/poi/services/hierarchy_service.py` to validate parent POI assignments and detect cycles (`chk_pois_parent_not_self`, ancestor tree traversal). [REQ-EDIT-014]
- [x] T-011 [US1] Implement candidate parent POI search endpoint `GET /api/pois/parents` in `services/poi/routes/hierarchy.py` with typeahead name filtering and descendant exclusion. [REQ-EDIT-012, REQ-EDIT-013]
- [x] T-012 [US1] Implement `PATCH /api/pois/{poi_id}` endpoint in `services/poi/routes/poi.py` updating rich fields, addresses, duration, provenance, and visit dates with address normalization and RFC 7807 error handling. [REQ-EDIT-001 to REQ-EDIT-011, REQ-EDIT-013]
- [x] T-013 [P] [US1] Create frontend `ParentPOISelector.tsx` in `frontend/src/components/poi/ParentPOISelector.tsx` with debounced typeahead search, dropdown filtering, clear button, and parent name display. [REQ-EDIT-012, REQ-EDIT-013]
- [x] T-014 [P] [US1] Create frontend `MultiAddressEditor.tsx` in `frontend/src/components/poi/MultiAddressEditor.tsx` supporting multiple address cards, required country indicator, state/country inputs, and delete actions. [REQ-EDIT-002, REQ-EDIT-004]
- [x] T-015 [US1] Implement `POIEditDrawer.tsx` in `frontend/src/components/poi/POIEditDrawer.tsx` integrating multiline description (with character counter), duration (hours/days), provenance selector, official/Wikipedia URLs, chronological visited date list with date picker, "visit again" checkbox, visit status badges, and hybrid photo folder directory picker (`showDirectoryPicker`). [REQ-EDIT-001, REQ-EDIT-005 to REQ-EDIT-011]

**Checkpoint**: User Story 1 is fully functional and independently testable. Core editing and parent hierarchy operational.

---

## Phase 4: User Story 2 - Interactive Latitude/Longitude Map Finder (Priority: P1)

**Goal**: Provide an interactive modal map workspace for visual pin placement, forward landmark search with query-scoped zoom adaptation, and backend reverse geocoding on draft application.

**Independent Test**: Launch Location Finder, search for "Mount Rushmore", verify focal zoom (16–18), click canvas to place marker, click "Apply", and assert draft coordinates and reverse-geocoded address fields update without a database write.

### Tests for User Story 2

- [x] T-016 [P] [US2] Write unit tests for reverse geocoding endpoint and PostGIS geocache in `tests/unit/services/poi/test_geocoding.py`. [REQ-LOC-009]

### Implementation for User Story 2

- [x] T-017 [US2] Implement reverse geocoding service in `services/poi/services/geocode_service.py` with PostGIS `geocache` lookup, coordinate rounding (5 decimal places), and 1 req/sec rate limiting targeting OpenStreetMap Nominatim with custom User-Agent. [REQ-LOC-009]
- [x] T-018 [US2] Implement endpoint `GET /api/pois/geocode/reverse` in `services/poi/routes/geocode.py`. [REQ-LOC-009]
- [x] T-019 [P] [US2] Implement client-side geocoding service in `frontend/src/services/geocodeService.ts` supporting direct browser forward search with 500ms debounce and calls to `/api/pois/geocode/reverse`. [REQ-LOC-003, REQ-LOC-009]
- [x] T-020 [US2] Implement `LocationFinderModal.tsx` in `frontend/src/components/poi/LocationFinderModal.tsx` featuring Leaflet/MapLibre map canvas, layer switcher, pre-centering on existing coordinates, search input with query-scoped adaptive zoom (city 10–12 vs landmark 16–18), first-$X$ match plotting, specificity warning banner, click-to-pin coordinate readout, "Cancel", and "Apply" button auto-populating address draft. [REQ-LOC-001 to REQ-LOC-009]

**Checkpoint**: User Story 2 operational. Map finder and hybrid geocoding function independently.

---

## Phase 5: User Story 3 - Selective Field-by-Field POI Comparison & Atomic Merge (Priority: P2)

**Goal**: Empower travelers to resolve duplicate POIs through a dual-column comparison view with diff-only toggle, scalar radio selection, multi-value set checkboxes, and atomic re-parenting of dependent records.

**Independent Test**: Initiate merge between two distinct POIs, toggle "Show all fields", select conflicting scalars via radios, union multi-value sets via checkboxes, confirm merge, and verify target POI is updated, source POI is deleted, and dependent references (`itinerary_items`, `poi_list_memberships`, `scanned_paths`, and `child_pois`) are re-parented.

### Tests for User Story 3

- [x] T-021 [P] [US3] Write unit tests for atomic merge service and foreign reference re-parenting in `tests/unit/services/poi/test_poi_merge.py`. [REQ-MERGE-005, REQ-MERGE-006]

### Implementation for User Story 3

- [x] T-022 [US3] Implement `POIMergeRequest` and `POIMergeResponse` schemas in `packages/core/vistarae_core/schemas/poi_merge.py`. [REQ-MERGE-003, REQ-MERGE-004]
- [x] T-023 [US3] Implement atomic merge engine in `services/poi/services/merge_service.py` executing scalar synthesis, multi-value set de-duplication, and atomic re-parenting of `itinerary_items`, `poi_list_memberships`, `scanned_paths`, and `child_pois` before deleting source POI within a single transaction. [REQ-MERGE-003 to REQ-MERGE-006]
- [x] T-024 [US3] Implement `POST /api/pois/merge` endpoint in `services/poi/routes/merge.py` with tenant ownership verification and RFC 7807 error responses. [REQ-MERGE-005, REQ-MERGE-006]
- [x] T-025 [US3] Implement `POIMergeModal.tsx` in `frontend/src/components/poi/POIMergeModal.tsx` with dual-column layout, "Show all fields" toggle (defaulting to diff-only view), radio buttons for scalars, checkboxes for sets with de-duplication, and confirmation prompt. [REQ-MERGE-001 to REQ-MERGE-005]

**Checkpoint**: User Story 3 operational. Full visual merge and referential re-parenting verified.

---

## Phase 6: User Story 4 - Intelligent Save Workflow & Duplicate Interception (Priority: P1)

**Goal**: Prevent accidental duplicate creation on save through spatial proximity and trigram name similarity checks, intercepting collisions with an actionable 3-way triage modal preserving in-memory draft state.

**Independent Test**: Modify a POI draft to match an existing POI within 200m and name similarity $\ge 0.60$, click "Save Changes", assert collision dialog intercepts save, select "Merge", and verify draft fields populate the merge view without data loss.

### Tests for User Story 4

- [x] T-026 [P] [US4] Write unit tests for pre-save duplicate check and spatial/trigram collision detection in `tests/unit/services/poi/test_poi_duplicate.py`. [REQ-SAVE-002]

### Implementation for User Story 4

- [x] T-027 [US4] Implement `DuplicateCheckRequest` and `DuplicateCheckResponse` schemas in `packages/core/vistarae_core/schemas/poi_duplicate.py`. [REQ-SAVE-002]
- [x] T-028 [US4] Implement `POST /api/pois/check-duplicate` endpoint in `services/poi/routes/duplicate.py` using PostGIS geodesic distance $\le 200$m and trigram similarity $\ge 0.60$ under tenant isolation. [REQ-SAVE-002, REQ-SAVE-004]
- [x] T-029 [US4] Implement `DuplicateCollisionModal.tsx` in `frontend/src/components/poi/DuplicateCollisionModal.tsx` displaying conflicting POI preview and 3-way triage options ("Create as New", "Merge" launching POI Merge view with in-memory draft as source, "Cancel"). [REQ-SAVE-003]
- [x] T-030 [US4] Integrate pre-save coordinate change detection, reverse geocoding backfill, duplicate check interception, and save double-submit guard in `frontend/src/components/poi/POIEditDrawer.tsx`. [REQ-SAVE-001 to REQ-SAVE-004]

**Checkpoint**: All 4 user stories complete, integrated, and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Type generation, contract synchronization, automated regression validation, and quality gates.

- [x] T-031 [P] Generate updated TypeScript definitions from OpenAPI 3.1 specification (`npm run generate:types` -> `frontend/src/types/api.ts`) and verify zero diff divergence.
- [x] T-032 Execute all 5 end-to-end scenarios defined in `specs/007-ui-edit-poi-enhancements/quickstart.md` against local Docker PostGIS and Uvicorn gateway.
- [x] T-033 Execute full backend test suite (`pytest --cov=services/poi --cov=packages/core --cov-fail-under=90`) ensuring 90% branch and line coverage ceiling per Constitution Principle 8.
- [x] T-034 Execute pre-commit verification gates (`ruff check`, `ruff format`, `prettier`, and copyright header verification) across all modified files per Constitution Principle 1.

---

## Dependencies & Execution Order

### Phase Dependencies

```mermaid
graph TD
    Phase1[Phase 1: Setup] --> Phase2[Phase 2: Foundational Schema & Core Entities]
    Phase2 --> Phase3[Phase 3: US1 Rich POI Editing & Hierarchy (P1)]
    Phase2 --> Phase4[Phase 4: US2 Location Finder & Reverse Geocoding (P1)]
    Phase2 --> Phase5[Phase 5: US3 POI Merge & Re-Parenting (P2)]
    Phase3 & Phase4 --> Phase6[Phase 6: US4 Save Workflow & Duplicate Interception (P1)]
    Phase5 & Phase6 --> Phase7[Phase 7: Polish & Quality Gates]
```

### Within Each User Story

1. Unit tests written first and verified failing.
2. Domain schemas & services implemented.
3. FastAPI route handlers mounted with RFC 7807 problem details.
4. React components & services assembled.
5. Story verified against its Independent Test criteria.

---

## Parallel Execution Opportunities

- **Phase 1 & Phase 2**: `T-004` (Value objects), `T-005` (Address normalizer), `T-006` (Domain entity), and `T-007` (Schemas) can be implemented in parallel once `T-003` migration is authored.
- **Phase 3 (US1)**: `T-009` (Test suite), `T-013` (`ParentPOISelector.tsx`), and `T-014` (`MultiAddressEditor.tsx`) can be developed in parallel.
- **Phase 4 (US2)**: `T-016` (Geocoding tests) and `T-019` (`geocodeService.ts`) can run in parallel with `T-017` / `T-018`.
- **Phase 5 (US3)**: `T-021` (Merge tests) and `T-022` (Merge schemas) can run in parallel before `T-023` / `T-025`.
- **Phase 6 (US4)**: `T-026` (Duplicate tests) and `T-027` (Duplicate schemas) can run in parallel before `T-028` / `T-029`.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T-001`, `T-002`).
2. Complete Phase 2: Foundational (`T-003` to `T-008`).
3. Complete Phase 3: User Story 1 (`T-009` to `T-015`).
4. **Validate MVP**: Test rich editing, multi-address storage, and parent POI hierarchy independently.

### Incremental Delivery

1. Phase 1 + Phase 2 $\rightarrow$ Foundations ready.
2. Add User Story 1 $\rightarrow$ Test independently $\rightarrow$ MVP Delivered!
3. Add User Story 2 $\rightarrow$ Map pin location selection and cached reverse geocoding enabled.
4. Add User Story 3 $\rightarrow$ Full visual comparison and atomic POI merge enabled.
5. Add User Story 4 $\rightarrow$ Save collision interception and in-memory draft merge enabled.
6. Phase 7 $\rightarrow$ Full test suite passes coverage gate ($\ge 90\%$) and pre-commit checks.
