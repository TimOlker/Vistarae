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

# Implementation Tasks: Phase 8 — UI Main Page Enhancements (Space Management, Visual POI Filter Rules, Multi-Select Bulk Actions & Map Popups)

**Feature Identifier**: `008-ui-main-page-enhancements`  
**Feature Branch**: `008-ui-main-page-enhancements`  
**Date**: 2026-10-22  
**Status**: Ready for Implementation  
**Specification**: [spec.md](./spec.md) | **Implementation Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/main-page-api.yaml](./contracts/main-page-api.yaml) | **Quickstart**: [quickstart.md](./quickstart.md) | **Checklists**: [checklists/ui.md](./checklists/ui.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify development runtime, dependencies, and contract synchronization tooling.

- [x] T-001 Verify Python 3.12 and Node.js environments and ensure `packages/core` workspace package is installed in editable mode (`pip install -e ./packages/core`) in root `pyproject.toml`.
- [x] T-002 [P] Configure frontend API contract export and TypeScript generation scripts in `frontend/package.json` (`npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema migration, ORM table, domain entities, value objects, and repository query methods required by all user stories.

**⚠️ CRITICAL**: No user story implementation work can begin until this foundational phase is complete.

- [x] T-003 Create Alembic migration `db/migrations/versions/0006_filter_rules.py` adding `filter_rules` table (`id` UUID PK, `user_id` UUID FK to `users.id` ON DELETE CASCADE, `name` VARCHAR(100) NOT NULL, `query_tree` JSONB NOT NULL DEFAULT `'{}'::jsonb`, `table_config` JSONB NOT NULL DEFAULT `'{}'::jsonb`, `pin_color_scheme` JSONB NOT NULL DEFAULT `'{}'::jsonb`, `created_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ), unique constraint `uq_filter_rules_user_name` on `(user_id, name)`, B-Tree index `ix_filter_rules_user_id_name`, and reversible `downgrade()` in `db/migrations/versions/0006_filter_rules.py`. [REQ-MAIN-012, REQ-MAIN-013]
- [x] T-004 [P] Add `FilterRuleTable` ORM definition with `uq_filter_rules_user_name` UniqueConstraint in `packages/core/vistarae_core/adapters/db/tables.py`. [REQ-MAIN-012, REQ-MAIN-013]
- [x] T-005 [P] Add `FilterRuleEntity` domain entity in `packages/core/vistarae_core/domain/entities.py` and value objects (`FilterOperator`, `FilterConjunction`, `PinColorMode`, `SortDirection`) in `packages/core/vistarae_core/domain/value_objects.py`. [REQ-MAIN-009, REQ-MAIN-012, REQ-MAIN-019, REQ-MAIN-020]
- [x] T-006 [P] Create Pydantic v2 schemas in `packages/core/vistarae_core/schemas/filter_rule.py` (`RuleClauseSchema`, `QueryTreeSchema`, `TableConfigSchema`, `PinColorSchemeSchema`, `FilterRuleCreateRequest`, `FilterRuleUpdateRequest`, `FilterRuleResponse`, `FilterRuleListResponse`) subclassing `StrictBaseModel` with `extra="forbid"`. [REQ-MAIN-008, REQ-MAIN-009, REQ-MAIN-012, REQ-MAIN-019, REQ-MAIN-020]
- [x] T-007 [P] Extend Pydantic schemas in `packages/core/vistarae_core/schemas/poi.py` with `BulkEditAction`, `BulkAddressUpdatePayload`, `BulkEditPayload`, `BulkEditRequest` (with `poi_ids` min 1, max 500 ceiling), `BulkDeleteRequest` (with `poi_ids` min 1, max 500 ceiling), and `POIQueryRequest`. [REQ-MAIN-026, REQ-MAIN-027 to REQ-MAIN-035]
- [x] T-008 [P] Define repository port interfaces `IFilterRuleRepository` and bulk mutation extensions on `IPOIRepository` in `packages/core/vistarae_core/ports/repositories.py`. [REQ-MAIN-014, REQ-MAIN-027 to REQ-MAIN-035]
- [x] T-009 Implement SQLAlchemy 2.0 async repository `FilterRuleRepository` in `services/poi/repositories/filter_rule_repository.py` enforcing `WHERE user_id = :current_user_id` on all lookups, creations, updates, and deletions. [REQ-MAIN-014, REQ-MAIN-015, REQ-MAIN-016, REQ-MAIN-018]
- [x] T-010 Implement backend AST query compiler `FilterQueryTranslator` in `services/poi/services/filter_evaluator.py` translating `QueryTree` AST nodes into SQLAlchemy binary expressions with spatial bounding box integration and `WHERE user_id = :current_user_id`. [REQ-MAIN-010, REQ-MAIN-014]

**Checkpoint**: Foundation ready — database schema, core domain models, and tenant-isolated repository lookups verified.

---

## Phase 3: User Story 1 - Adaptive Space Management & Focus Modes (Priority: P1) 🎯 MVP

**Goal**: Enable travelers to switch between `split`, `map_only`, and `table_only` layouts, allocating 100% horizontal space to map or table on demand with session-only in-memory state and zero WebGL canvas destruction.

**Independent Test**: Load main page in Split View, click "Map Only" (verify map expands to 100% width, table hidden, `map.resize()` triggered, no WebGL reload), click "Table Only" (verify table expands to 100% width, map hidden), click "Split View" (verify side-by-side view restored), and assert active POI selection and scroll positions are preserved.

### Implementation for User Story 1

- [x] T-011 [P] [US1] Create frontend layout types in `frontend/src/types/layout.ts` (`LayoutMode = 'split' | 'map_only' | 'table_only'`). [REQ-MAIN-001]
- [x] T-012 [P] [US1] Implement `ViewModeControl.tsx` segmented button group in `frontend/src/components/layout/ViewModeControl.tsx` with accessible icons, active state styling, and tooltip helpers. [REQ-MAIN-001, CHK001]
- [x] T-013 [US1] Update `HomePage.tsx` in `frontend/src/pages/HomePage.tsx` to integrate `ViewModeControl`, managing `layoutMode` state (defaulting to `'split'`), adjusting horizontal flex container proportions (`map_only` = map 100%, table hidden; `table_only` = table 100%, map hidden; `split` = map 58%, table 42%), triggering `map.resize()` on layout change, and preserving active POI selection. [REQ-MAIN-001 to REQ-MAIN-005, SC-001]
- [x] T-014 [P] [US1] Write component unit tests for layout mode switching and state preservation in `frontend/src/tests/components/layout/ViewModeControl.test.tsx`. [REQ-MAIN-001 to REQ-MAIN-005, SC-001]

**Checkpoint**: User Story 1 is fully functional and independently testable. Core space management operational.

---

## Phase 4: User Story 2 - Visual POI Filtering & Persisted Filter Rules (Priority: P1)

**Goal**: Provide an expandable query builder supporting multi-clause `AND`/`OR` conditions, hybrid client/server execution, customizable table columns/sort, dynamic pin color schemes, and tenant-isolated database persistence.

**Independent Test**: Open filter bar, construct multi-clause query (`Country = "Japan" AND Rating >= 4`), apply filter, verify map and table update within 200ms, configure table columns and star-rating pin colors, save as "Japan Top Picks", reload page, load rule, and verify query tree, table columns, and pin colors restore accurately.

### Tests for User Story 2

- [x] T-015 [P] [US2] Write unit tests for FilterRule CRUD and AST compilation in `tests/unit/services/poi/test_filter_rules.py`. [REQ-MAIN-010, REQ-MAIN-012 to REQ-MAIN-020, SC-002, SC-003]

### Implementation for User Story 2

- [x] T-016 [US2] Implement Filter Rules router in `services/poi/routes/filter_rules.py` handling `GET /api/pois/filter-rules`, `POST /api/pois/filter-rules` (with 409 on name conflict), `GET /api/pois/filter-rules/{id}`, `PUT /api/pois/filter-rules/{id}`, and `DELETE /api/pois/filter-rules/{id}` with RFC 7807 problem details. [REQ-MAIN-012 to REQ-MAIN-018, SC-003, SC-007]
- [x] T-017 [US2] Implement hybrid query endpoint `POST /api/pois/query` in `services/poi/routes/pois.py` evaluating `QueryTreeSchema` via `FilterQueryTranslator` with bounding-box support. [REQ-MAIN-010, SC-002]
- [x] T-018 [P] [US2] Implement TypeScript filter types and API client methods in `frontend/src/types/filter.ts` and `frontend/src/services/filterRuleService.ts`. [REQ-MAIN-008, REQ-MAIN-012]
- [x] T-019 [P] [US2] Implement client-side in-memory AST evaluator `evaluateQueryTree` in `frontend/src/utils/filterEvaluator.ts` supporting all 10 filter dimensions and operators for datasets $<1,000$ POIs. [REQ-MAIN-009, REQ-MAIN-010, SC-002]
- [x] T-020 [P] [US2] Implement `QueryBuilder.tsx` in `frontend/src/components/filter/QueryBuilder.tsx` supporting recursive clause addition, field selection, operator selection, value inputs, and `AND`/`OR` conjunction switches. [REQ-MAIN-008, REQ-MAIN-009]
- [x] T-021 [P] [US2] Implement `SavedRuleSelector.tsx` in `frontend/src/components/filter/SavedRuleSelector.tsx` supporting rule loading, "Save Rule" (with overwrite confirmation modal), "Save As" (new rule modal), and "Delete Rule" with confirmation. [REQ-MAIN-015 to REQ-MAIN-018]
- [x] T-022 [P] [US2] Implement `ColumnConfigModal.tsx` in `frontend/src/components/filter/ColumnConfigModal.tsx` allowing column visibility selection, order sequence reordering, and sort direction specification (`asc`, `desc`, `unsorted`). [REQ-MAIN-019]
- [x] T-023 [P] [US2] Implement `PinColorSchemeModal.tsx` in `frontend/src/components/filter/PinColorSchemeModal.tsx` allowing selection between `uniform`, `rating`, `visit_status`, and `custom` modes with color palette pickers. [REQ-MAIN-020, REQ-MAIN-021]
- [x] T-024 [US2] Implement `FilterBar.tsx` in `frontend/src/components/filter/FilterBar.tsx` integrating `QueryBuilder`, `SavedRuleSelector`, `ColumnConfigModal`, and `PinColorSchemeModal` with expand/collapse toggle, active criteria summary, "Apply Filter", and "Clear Filter" buttons. [REQ-MAIN-006, REQ-MAIN-007, REQ-MAIN-010, REQ-MAIN-011]
- [x] T-025 [US2] Wire `FilterBar` and dynamic pin coloring into `HomePage.tsx`, applying hybrid filtering ($<1,000$ client in-memory vs. $\ge 1,000$ `/api/pois/query`), updating `POITable` column layout/sorting, and dynamically styling MapLibre pin SVGs according to the active scheme. [REQ-MAIN-010, REQ-MAIN-019, REQ-MAIN-021, SC-002]

**Checkpoint**: User Story 2 operational. Filter builder, saved rules, and pin color schemes fully integrated.

---

## Phase 5: User Story 3 - Multi-Select Mode & Atomic Bulk Operations (Priority: P1)

**Goal**: Provide a multi-select mode with master toggle and row checkboxes for up to 500 POIs, executing atomic bulk updates (ratings, visit dates, visit again, tags, lists, safe primary-address updates) and deletions.

**Independent Test**: Enable multi-select mode in POI Table, click master checkbox to select filtered POIs, perform bulk rating update to 5 stars, perform bulk location update to "Kyoto", verify primary address updated while secondary addresses are preserved, and assert all operations execute in a single database transaction under 2.0s.

### Tests for User Story 3

- [x] T-026 [P] [US3] Write unit tests for atomic bulk mutations, address preservation, and 500-batch ceiling validation in `tests/unit/services/poi/test_bulk_operations.py`. [REQ-MAIN-026 to REQ-MAIN-035, SC-004, SC-006]

### Implementation for User Story 3

- [x] T-027 [US3] Implement bulk mutations in `services/poi/repositories/poi_repository.py` supporting `bulk_edit` (rating, visit date appending with lifecycle calculation, visit again toggle, tags, lists, and non-destructive `addresses[0]` updates using `AddressNormalizer`) and `bulk_delete` within single `async with session.begin():` transactions. [REQ-MAIN-027 to REQ-MAIN-034, SC-004, SC-006]
- [x] T-028 [US3] Update `services/poi/routes/bulk.py` implementing `POST /api/pois/bulk-edit` and updating `POST /api/pois/bulk-delete` with strict 500-batch ceiling validation (returning RFC 7807 422 if `len(poi_ids) > 500`) and tenant verification. [REQ-MAIN-026, REQ-MAIN-035, SC-004, SC-007]
- [x] T-029 [P] [US3] Update `POITable.tsx` in `frontend/src/components/poi/POITable.tsx` with multi-select toggle button, row checkbox column, master header checkbox (toggle all currently filtered), and selection state callbacks. [REQ-MAIN-022 to REQ-MAIN-025]
- [x] T-030 [P] [US3] Implement `BulkActionsToolbar.tsx` in `frontend/src/components/bulk/BulkActionsToolbar.tsx` displaying selected count badge (enforcing 500 max ceiling), action trigger buttons, and "Deselect All". [REQ-MAIN-026]
- [x] T-031 [P] [US3] Implement `BulkOperationsModal.tsx` in `frontend/src/components/bulk/BulkOperationsModal.tsx` supporting rating picker, visit date picker, visit again toggle, tag add/remove, list add/remove, location editor (City, State, Country with clear triggers), and destructive bulk deletion confirmation dialog. [REQ-MAIN-027 to REQ-MAIN-034]
- [x] T-032 [US3] Integrate `BulkActionsToolbar` and `BulkOperationsModal` into `POITable.tsx` and `HomePage.tsx`, invoking `/api/pois/bulk-edit` and `/api/pois/bulk-delete`, displaying progress/success notifications, and refreshing table and map pins. [REQ-MAIN-026, REQ-MAIN-034, SC-004]

**Checkpoint**: User Story 3 operational. Multi-select batch editing and deletion functioning with single-transaction atomicity.

---

## Phase 6: User Story 4 - Map Cluster Exploration & Rich Pin Popups (Priority: P1)

**Goal**: Smoothly ease camera into cluster bounding boxes on click, handle max-zoom ($z \ge 20$) co-location spiderfication, and display rich interactive pin preview popups (`POIPopupCard`) with instant entry into the POI Edit Drawer.

**Independent Test**: Click map cluster pin (verify map zooms and pans to bounding box of child POIs in 300ms, POI table synchronizes to visible pins), click unclustered pin (verify `POIPopupCard` displays name, rating, address badge, and thumbnail), click "Edit POI" (verify popup closes and `POIEditDrawer` opens populated with POI data).

### Implementation for User Story 4

- [x] T-033 [P] [US4] Implement cluster click bounding-box calculation and `map.fitBounds(bounds, { padding: 60, maxZoom: 18, duration: 300 })` camera easing in `frontend/src/components/map/MapView.tsx`. [REQ-MAIN-036, SC-005]
- [x] T-034 [P] [US4] Implement co-located POI disambiguation list popup for overlapping markers at max zoom ($z \ge 19.5$) in `frontend/src/components/map/MapView.tsx`. [REQ-MAIN-037]
- [x] T-035 [US4] Enhance `POIPopupCard.tsx` in `frontend/src/components/map/POIPopupCard.tsx` displaying canonical name, star rating visual indicator, formatted address (or "Multiple Locations ({N})" badge with address count), thumbnail image preview with fallback, and "Edit POI" button. [REQ-MAIN-038]
- [x] T-036 [US4] Wire `POIPopupCard` in `MapView.tsx` and `HomePage.tsx` so clicking "Edit POI" closes the popup, selects the POI, and opens `POIEditDrawer` with pre-populated aggregate data. [REQ-MAIN-038, REQ-MAIN-039]
- [x] T-037 [US4] Guarantee continuous bidirectional synchronization in `MapView.tsx` and `HomePage.tsx`, updating `displayedTablePois` to strictly reflect POIs within the current map bounding box regardless of cluster state. [REQ-MAIN-040]

**Checkpoint**: User Story 4 operational. Cluster navigation, co-located spiderfication, and rich pin popups fully synchronized.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end integration, performance validation, and contract verification across all 4 pillars.

- [x] T-038 [P] Export updated OpenAPI 3.1 specification via `python -m scripts.export_openapi` and regenerate TypeScript types via `npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts`, verifying zero diff. [Constitution Principle 5]
- [x] T-039 [P] Run complete PyTest test suite with coverage enforcement (`pytest --cov=services/poi --cov=packages/core/vistarae_core --cov-fail-under=90`). [Constitution Principle 8]
- [x] T-040 Execute end-to-end scenarios documented in `quickstart.md` validating space management layout switching ($<100$ms), hybrid filtering ($<200$ms), rule persistence, bulk mutations (up to 500 POIs in $<2.0$s), and cluster navigation ($<300$ms). [SC-001 to SC-007]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — MVP foundation.
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2); can run in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2); can run in parallel with US1 and US2.
- **User Story 4 (Phase 6)**: Depends on Foundational (Phase 2); can run in parallel with US1, US2, and US3.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### Parallel Execution Opportunities

- **Foundational**: Tasks T-004, T-005, T-006, T-007, T-008 can all be developed in parallel across different files.
- **User Story 1**: Tasks T-011, T-012, T-014 can be developed in parallel.
- **User Story 2**: Tasks T-015, T-018, T-019, T-020, T-021, T-022, T-023 can be developed in parallel.
- **User Story 3**: Tasks T-026, T-029, T-030, T-031 can be developed in parallel.
- **User Story 4**: Tasks T-033, T-034 can be developed in parallel.
- **Polish**: Tasks T-038 and T-039 can run concurrently.

---

## Implementation Strategy

### MVP First (User Story 1 Focus)

1. Complete Phase 1: Setup (T-001, T-002).
2. Complete Phase 2: Foundational (T-003 to T-010).
3. Complete Phase 3: User Story 1 (T-011 to T-014).
4. **Checkpoint**: Test Space Management layout toggles (`split`, `map_only`, `table_only`) independently.

### Incremental Feature Expansion

1. Add User Story 2 (T-015 to T-025): Visual query builder, hybrid filtering, and rule persistence.
2. Add User Story 3 (T-026 to T-032): POI Table multi-select mode and atomic bulk mutations.
3. Add User Story 4 (T-033 to T-037): Cluster easing and rich map pin popups.
4. Run Phase 7 Polish (T-038 to T-040): Coverage and quickstart verification.

---

## Phase 8: Convergence

- [x] T-041 Refactor `translate_clause` in `services/poi/services/filter_evaluator.py` into dimension-specific handler helpers to reduce McCabe cognitive complexity to $\le 15$ per Constitution Principle 1 (`contradicts`)
- [x] T-042 Execute code formatting via `python -m ruff format .` and `npm --prefix frontend run format:extension` across all modified files per Constitution Principle 1 Pre-Commit Standard (`partial`)
