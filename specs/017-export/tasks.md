# Tasks: Full-Fidelity CSV Export & Roundtrip Re-Import (017-export)

**Input**: Design documents from `/specs/017-export/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`)  
**Prerequisites**: `plan.md` (complete), `spec.md` (complete), `data-model.md` (complete), `contracts/` (complete)

## Format: `[ID] [P?] [Story?] Description [Requirements] [Tests]`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story identifier (`[US1]`, `[US2]`, `[US3]`) mapping to `spec.md`
- **[Requirements]**: EARS functional requirement IDs (`[FR-001]` ... `[FR-013]`, `[SC-001]` ... `[SC-005]`)
- **[Tests]**: Target test or validation files

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, and shared test fixtures

- [X] T-001 Create shared export schema module files in `packages/core/vistarae_core/schemas/export_schema.py` and `frontend/src/types/export-schema.ts`
- [X] T-002 [P] Create mock candidate test fixtures with complete 35+ attributes and multi-valued fields in `tests/fixtures/export_fixtures.py` and `frontend/src/tests/fixtures/exportFixtures.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema registry and serialization utilities that MUST be complete before user stories begin

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete

- [X] T-003 [P] Implement centralized `ExportFieldDefinition` schema registry in `packages/core/vistarae_core/schemas/export_schema.py` defining all 35+ candidate attributes, data types, header aliases, and formula flags [FR-001] [Tests: tests/unit/packages/core/test_export_schema.py]
- [X] T-004 [P] Implement frontend TypeScript canonical candidate export registry and header mapping definitions in `frontend/src/types/export-schema.ts` matching backend schema [FR-001, FR-009] [Tests: frontend/src/tests/ingest/exportSchema.test.ts]
- [X] T-005 [P] Implement formula injection defense (`'`) sanitization and desanitization utilities in `packages/core/vistarae_core/schemas/export_schema.py` and `frontend/src/utils/csvExport.ts` [FR-004] [Tests: tests/unit/packages/core/test_formula_sanitizer.py]
- [X] T-006 Implement dual-mode serializer and deserializer helpers (semicolon for simple string lists, JSON for complex object pairs) in `packages/core/vistarae_core/schemas/export_schema.py` and `frontend/src/utils/csvExport.ts` [FR-003, FR-006] [Tests: tests/unit/packages/core/test_dual_mode_serializer.py]

**Checkpoint**: Canonical schema registry and serialization utilities functional; user story implementation can begin.

---

## Phase 3: User Story 1 - Full-Fidelity Workbench CSV Export (Priority: P1) 🎯 MVP

**Goal**: Traveler can export all candidate fields from the Staging Workbench into an RFC 4180 CSV with UTF-8 BOM, active editor state flushed, and scope selection preserved.  
**Independent Test**: Open workbench with diverse candidate metadata, edit candidate detail, click "Export", and verify downloaded CSV matches [csv-schema.json](./contracts/csv-schema.json) with all 35+ fields, formula prefix escaping, and active edits present.

### Tests for User Story 1

- [X] T-007 [P] [US1] Unit test for frontend CSV exporter in `frontend/src/tests/ingest/csvExport.test.ts` covering 35+ fields, formula prefix escaping, semicolon tags, JSON websites, and UTF-8 BOM [FR-001, FR-003, FR-004, FR-010]
- [X] T-008 [P] [US1] Unit test for backend candidate export stream in `tests/unit/services/ingest/test_export_route.py` testing RFC 4180 compliance, tenant isolation, and UTF-8 BOM [FR-002, FR-010, FR-013]

### Implementation for User Story 1

- [X] T-009 [P] [US1] Implement full-fidelity client-side CSV generator `exportWorkbenchCandidatesToCsv` in `frontend/src/utils/csvExport.ts` supporting candidate scoping (all vs checked rows), RFC 4180 escaping, and formula neutralization [FR-001, FR-002, FR-003, FR-004, FR-010] [Tests: frontend/src/tests/ingest/csvExport.test.ts]
- [X] T-010 [US1] Update `handleExportCsv` in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` to automatically flush active detail editor state, resolve selection scope, and trigger `exportWorkbenchCandidatesToCsv` download [FR-002, FR-012] [Tests: frontend/src/tests/ingest/CSVImportWorkbenchModal.test.tsx]
- [X] T-011 [P] [US1] Extend backend candidate streaming exporter `POIExporter.stream_candidate_export_chunks` in `packages/core/vistarae_core/services/poi_exporter.py` to stream all 35+ candidate attributes with UTF-8 BOM [FR-001, FR-002, FR-010] [Tests: tests/unit/packages/core/test_poi_exporter.py]
- [X] T-012 [US1] Implement dedicated candidate export endpoint `GET /api/ingest/jobs/{job_id}/candidates/export` in `services/ingest/routes/export.py` streaming full-fidelity CSV chunks [FR-013] [Tests: tests/unit/services/ingest/test_export_route.py]

**Checkpoint**: User Story 1 complete. Full-fidelity export functional both client-side in the workbench and via backend streaming API.

---

## Phase 4: User Story 2 - Lossless Re-Import & Session Rebuild (Priority: P1)

**Goal**: Traveler can upload an exported CSV back into Vistarae and restore the exact candidate list with all metadata, dispositions, and parent-child hierarchies intact.  
**Independent Test**: Export a staged workbench CSV, upload that CSV into a fresh intake job, and verify 100% attribute parity, disposition preservation, and intra-batch hierarchy reconstruction.

### Tests for User Story 2

- [X] T-013 [P] [US2] Unit test for re-import parser in `tests/unit/services/ingest/test_csv_parser_reimport.py` testing full-fidelity header detection, disposition preservation, dual-mode deserialization, and formula desanitization [FR-005, FR-006, FR-007, SC-002]
- [X] T-014 [P] [US2] Integration test for intra-batch nesting reconstruction in `tests/integration/services/ingest/test_reimport_nesting.py` testing UUID translation mapping for `parent_candidate_id` and `merge_target_id` [FR-011, SC-002]

### Implementation for User Story 2

- [X] T-015 [US2] Extend `_COLUMN_MAPPINGS` and header aliasing in `services/ingest/services/csv_parser.py` to recognize all canonical exported column names case-insensitively [FR-005] [Tests: tests/unit/services/ingest/test_csv_parser_reimport.py]
- [X] T-016 [US2] Update `parse_and_sanitize_csv` in `services/ingest/services/csv_parser.py` to strip formula-neutralizing leading apostrophes (`'`) from text values [FR-004, FR-006] [Tests: tests/unit/services/ingest/test_csv_parser_reimport.py]
- [X] T-017 [US2] Implement dual-mode collection deserializer in `services/ingest/services/csv_parser.py` for `tags`, `photo_directories`, `dates_visited`, and `related_websites` supporting JSON and semicolon formats [FR-003, FR-006] [Tests: tests/unit/services/ingest/test_csv_parser_reimport.py]
- [X] T-018 [US2] Implement user disposition and override preservation in `services/ingest/services/staging_service.py` ensuring imported `user_disposition`, `disposition_justification`, and `is_user_overridden` bypass heuristic recalculation [FR-007] [Tests: tests/unit/services/ingest/test_staging_service_reimport.py]
- [X] T-019 [US2] Implement UUID translation table mapping (`exported_candidate_id` to new database UUID) in `services/ingest/services/staging_service.py` to reconstruct `parent_candidate_id` and `merge_target_id` linkages [FR-011] [Tests: tests/integration/services/ingest/test_reimport_nesting.py]

**Checkpoint**: User Stories 1 and 2 complete. Roundtrip export and re-import achieves 100% fidelity.

---

## Phase 5: User Story 3 - Schema-Driven Extensibility for Future Intake Fields (Priority: P2)

**Goal**: New intake attributes registered in the canonical schema registry automatically propagate to export and import without disparate file changes, and unknown external columns are preserved in metadata.  
**Independent Test**: Register a new mock attribute in the schema registry and upload a CSV with that column; verify it is parsed into candidate attributes and re-exported automatically. Upload an unknown column and verify it is captured in `raw_geocoding['_unmapped_columns']`.

### Tests for User Story 3

- [X] T-020 [P] [US3] Unit test for schema extensibility and unmapped column preservation in `tests/unit/services/ingest/test_schema_extensibility.py` [FR-008, FR-009, SC-004]

### Implementation for User Story 3

- [X] T-021 [US3] Implement dynamic metadata dictionary capture in `services/ingest/services/csv_parser.py` to preserve unmapped/extension columns under `_unmapped_columns` in `raw_geocoding` [FR-008] [Tests: tests/unit/services/ingest/test_schema_extensibility.py]
- [X] T-022 [US3] Add synchronization validation script `scripts/validate_export_schema_sync.py` to verify backend `export_schema.py` and frontend `export-schema.ts` column definitions remain strictly synchronized [FR-009] [Tests: tests/unit/packages/core/test_export_schema.py]

**Checkpoint**: User Story 3 complete. Schema extensibility and dynamic column capture verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, documentation, and regression validation

- [X] T-023 [P] Performance benchmark test in `tests/performance/test_export_import_performance.py` validating 1,000-candidate re-import $\le 5$ seconds [SC-005]
- [X] T-024 [P] Verify and update end-to-end documentation and quickstart instructions in `specs/017-export/quickstart.md`
- [X] T-025 Run full regression suite across core, ingest service, and frontend test suites (`pytest` and `pnpm test`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion (and uses export format from US1)
- **User Story 3 (Phase 5)**: Depends on US1 and US2 completion
- **Polish (Phase 6)**: Depends on all user story phases completion

### Parallel Opportunities

- Within Phase 1: `T-002` can run in parallel with `T-001`.
- Within Phase 2: `T-003`, `T-004`, `T-005` can run in parallel across Python and TypeScript.
- Within Phase 3 (US1): `T-007`, `T-008`, `T-009`, `T-011` can proceed in parallel.
- Within Phase 4 (US2): `T-013` and `T-014` tests can be authored in parallel with parser extensions.
- Across Stories: Once Phase 2 completes, frontend export (`T-009`, `T-010`) and backend re-import parser (`T-015`, `T-016`, `T-017`) can be worked on concurrently by different developers.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T-001`, `T-002`).
2. Complete Phase 2: Foundational (`T-003`, `T-004`, `T-005`, `T-006`).
3. Complete Phase 3: User Story 1 (`T-007` – `T-012`).
4. **STOP and VALIDATE**: Verify full-fidelity CSV export from the workbench modal with all 35+ fields and formula protection.

### Incremental Delivery

1. Setup + Foundation ready.
2. User Story 1 (Full-Fidelity Export) deployed & verified (MVP).
3. User Story 2 (Lossless Re-Import & UUID Translation) deployed & verified (Roundtrip Parity).
4. User Story 3 (Schema Extensibility & Dynamic Metadata Capture) deployed & verified.
5. Polish & Performance Benchmark verified ($\le 5$s for 1,000 rows).

