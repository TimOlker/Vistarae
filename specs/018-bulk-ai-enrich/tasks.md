# Tasks: AI Bulk Enrichment (018-bulk-ai-enrich)

**Input**: Design documents from `/specs/018-bulk-ai-enrich/`  
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/bulk_enrichment_api.yaml](./contracts/bulk_enrichment_api.yaml), [quickstart.md](./quickstart.md)  
**Tests**: Unit tests, component tests, and contract tests are explicitly included per Constitution Principle 8 ($\ge 90\%$ coverage gate).  
**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story?] Description with file path (REQ-ID) [Test: test_path]`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Every task includes exact file paths, EARS requirement mappings, and test/validation references.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Core configuration, domain models, schemas, and repository interfaces.

- [X] T001 Define environment variable `BULK_ENRICHMENT_CONCURRENCY` (integer, default 3, bounded 1..10) in `packages/core/vistarae_core/domain/entities.py` and configuration loader (REQ-ENR-014) [Validation: `tests/unit/worker/test_bulk_enrichment_manager.py`]
- [X] T002 [P] Create domain entities and StrEnum classes (`BulkEnrichmentStatus`, `EnrichmentResultCode`, `RecoveryPromptAction`, `EnrichmentSession`, `EnrichmentQueueItem`, `BulkEnrichmentResult`) in `packages/core/vistarae_core/domain/entities.py` and `packages/core/vistarae_core/domain/enums.py` (REQ-ENR-012, REQ-ENR-015, REQ-ENR-033, REQ-ENR-035) [Validation: `tests/unit/domain/test_bulk_enrichment_entities.py`]
- [X] T003 [P] Implement Pydantic v2 `StrictBaseModel` boundary schemas (`BulkEnrichmentInitiateRequest`, `BulkEnrichmentInitiateResponse`, `BulkEnrichmentProgressResponse`, `BulkEnrichmentCancelResponse`, `BulkEnrichmentHeartbeatResponse`, `BulkEnrichmentSummaryResponse`, `BulkEnrichmentRecoveryResponse`, `BulkEnrichmentRecoveryActionRequest`) in `packages/core/vistarae_core/schemas/bulk_enrichment.py` with `extra="forbid"` (REQ-ENR-001, REQ-ENR-022, REQ-ENR-026, REQ-ENR-034) [Validation: `tests/unit/schemas/test_bulk_enrichment_schemas.py`]
- [X] T004 [P] Define `IBulkEnrichmentRepository` protocol interface in `packages/core/vistarae_core/ports/repositories.py` abstracting `create_result`, `get_result_by_session_id`, `get_unacknowledged_recovery_run`, and `acknowledge_recovery_run` (REQ-ENR-033, REQ-ENR-034, REQ-ENR-036, REQ-ENR-037) [Validation: `tests/unit/repositories/test_bulk_enrichment_repo.py`]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database persistence layer and repository implementation required by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Define SQLAlchemy ORM table `BulkEnrichmentResultsTable` in `packages/core/vistarae_core/adapters/db/tables.py` mapping table `bulk_enrichment_results` with columns `id UUID PK`, `user_id UUID FK NOT NULL`, `job_id UUID FK NOT NULL`, `session_id UUID UNIQUE NOT NULL`, `status VARCHAR(32) NOT NULL`, `processed_count INT NOT NULL DEFAULT 0`, `unprocessed_count INT NOT NULL DEFAULT 0`, `failure_count INT NOT NULL DEFAULT 0`, `success_count INT NOT NULL DEFAULT 0`, `total_resources_used INT NOT NULL DEFAULT 0`, `total_duration_ms INT NOT NULL DEFAULT 0`, `average_duration_ms INT NOT NULL DEFAULT 0`, `termination_reason TEXT NOT NULL`, `acknowledged_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, plus composite index `idx_bulk_enrichment_user_recovery` on `(user_id, acknowledged_at, created_at DESC)` (REQ-ENR-033, REQ-ENR-034) [Validation: `tests/unit/repositories/test_bulk_enrichment_repo.py`]
- [X] T006 Create Alembic migration script `db/migrations/versions/0019_add_bulk_enrichment_results.py` with fully reversible `upgrade()` and `downgrade()` creating table `bulk_enrichment_results` and composite B-tree index `idx_bulk_enrichment_user_recovery` without native DB enums (REQ-ENR-033, Constitution §Alembic) [Validation: `alembic check`]
- [X] T007 Implement `SqlAlchemyBulkEnrichmentRepository` in `packages/core/vistarae_core/adapters/repositories/bulk_enrichment_repo.py` adhering to `statement_cache_size: 0` and strict tenant isolation `WHERE user_id = :current_user_id` on all queries (REQ-ENR-033, REQ-ENR-034, Constitution §Database) [Validation: `tests/unit/repositories/test_bulk_enrichment_repo.py`]
- [X] T008 [P] Implement unit tests for `SqlAlchemyBulkEnrichmentRepository` in `tests/unit/repositories/test_bulk_enrichment_repo.py` verifying create, lookup, unacknowledged retrieval filtering, and acknowledge updates with tenant isolation (REQ-ENR-033, REQ-ENR-034) [Test: `tests/unit/repositories/test_bulk_enrichment_repo.py`]

**Checkpoint**: Foundation ready — database schema, models, schemas, and repository layer operational. User story implementation can now begin.

---

## Phase 3: User Story 1 - Canary-Gated Fail-Fast Bulk Enrichment Dispatch (Priority: P1) 🎯 MVP

**Goal**: Deliver canary-gated bulk AI enrichment execution where candidate #1 runs solitary with concurrency 1, scaling up to concurrency ceiling ($C=3$) upon canary success, and halting immediately on blocking external errors (HTTP 402/429) with zero downstream resource waste.

**Independent Test**: Initiate bulk enrichment on 5 candidates with mock external credentials configured to return HTTP 402 `RESOURCE_EXHAUSTED`. Verify that candidate #1 executes alone as canary, circuit-breaking halts further dispatches within $< 500\text{ ms}$, candidates #2–#5 remain unprocessed in queue, and candidate updates commit immediately.

### Tests for User Story 1

- [X] T009 [P] [US1] Unit test canary execution, concurrency scaling, worker 45s ceiling timeout, and fail-fast circuit breaker in `tests/unit/worker/test_bulk_enrichment_manager.py` (REQ-ENR-012 through REQ-ENR-019, SC-001, SC-002) [Test: `tests/unit/worker/test_bulk_enrichment_manager.py`]
- [X] T010 [P] [US1] Unit test subscription tier verification and candidate selection validation in `tests/unit/services/ingest/test_bulk_enrichment_routes.py` (REQ-ENR-001 through REQ-ENR-009) [Test: `tests/unit/services/ingest/test_bulk_enrichment_routes.py`]

### Implementation for User Story 1

- [X] T011 [US1] Implement `BulkEnrichmentSessionManager` orchestrator in `services/worker/bulk_enrichment_manager.py` managing queue lifecycle: extract candidate #1 as isolated canary, execute canary with concurrency 1, release concurrency semaphore to `BULK_ENRICHMENT_CONCURRENCY` upon success/temporary error, wrap candidate workers in `asyncio.wait_for(timeout=45.0)`, and trigger fail-fast stop event on `BLOCKING_EXTERNAL_ERROR` (REQ-ENR-012 through REQ-ENR-019, SC-001, SC-002) [Test: `tests/unit/worker/test_bulk_enrichment_manager.py`]
- [X] T012 [US1] Implement selective field population and immediate per-candidate database persistence in `services/worker/bulk_enrichment_manager.py` preserving pre-existing non-empty fields when `force_refresh=False`, honoring `is_user_overridden`, and committing each candidate immediately via isolated `AsyncSession` (REQ-ENR-029, REQ-ENR-030, REQ-ENR-031) [Test: `tests/unit/worker/test_bulk_enrichment_manager.py`]
- [X] T013 [US1] Implement session initiation endpoint `POST /api/ingest/jobs/{job_id}/bulk-enrichment/start` in `services/ingest/routes/bulk_enrichment.py` validating active premium subscription (`user.subscription_tier == "PREMIUM"` returning HTTP 403 ProblemDetails for non-premium), resolving candidate selection, asserting no existing active session (HTTP 409 Conflict), and launching orchestrator (REQ-ENR-001 through REQ-ENR-009) [Test: `tests/unit/services/ingest/test_bulk_enrichment_routes.py`]
- [X] T014 [US1] Register `bulk_enrichment` router in `services/ingest/main.py` and mount in `services/local_gateway.py` with W3C telemetry middleware and directional message tags (`MSG: -->|`, `MSG: <--|`) (REQ-ENR-001, Constitution §Observability) [Test: `tests/unit/services/ingest/test_bulk_enrichment_routes.py`]

**Checkpoint**: User Story 1 (MVP) complete and independently testable. Canary execution, concurrency control, fail-fast circuit breaking, selective persistence, and premium gating functional.

---

## Phase 4: User Story 2 - Real-Time Enrichment Progress & Interactive Graceful Cancellation (Priority: P1)

**Goal**: Provide live progress telemetry (queue counts, in-flight workers, elapsed time, average duration, percentage) and an interactive "Cancel" button that stops new queue dispatches and drains in-flight workers within a 30-second grace window, coupled with a 5-second client heartbeat protecting against abandoned sessions.

**Independent Test**: Start bulk enrichment on 20 candidates. Verify progress telemetry updates within $< 1\text{ second}$ of candidate completion. Click "Cancel" at 30% completion and verify that active workers drain cleanly within 30 seconds, remaining candidates are marked cancelled, and session concludes without orphaned tasks.

### Tests for User Story 2

- [X] T015 [P] [US2] Unit test progress polling, client heartbeat disconnection abort (>15s timeout), and graceful cancellation drain in `tests/unit/worker/test_bulk_enrichment_progress.py` (REQ-ENR-020, REQ-ENR-021, REQ-ENR-022, REQ-ENR-025, REQ-ENR-032, SC-003, SC-006) [Test: `tests/unit/worker/test_bulk_enrichment_progress.py`]
- [X] T016 [P] [US2] Contract test progress, cancel, and heartbeat endpoints in `tests/contract/test_bulk_enrichment_contracts.py` against `contracts/bulk_enrichment_api.yaml` (REQ-ENR-020, REQ-ENR-022, REQ-ENR-032) [Test: `tests/contract/test_bulk_enrichment_contracts.py`]

### Implementation for User Story 2

- [X] T017 [US2] Implement `GET /api/ingest/jobs/{job_id}/bulk-enrichment/progress`, `POST /api/ingest/jobs/{job_id}/bulk-enrichment/cancel`, and `POST /api/ingest/jobs/{job_id}/bulk-enrichment/heartbeat` in `services/ingest/routes/bulk_enrichment.py` returning real-time metrics, accepting graceful cancellation, and resetting session heartbeat timestamp (REQ-ENR-020 through REQ-ENR-025, REQ-ENR-032) [Test: `tests/contract/test_bulk_enrichment_contracts.py`]
- [X] T018 [P] [US2] Add frontend API client methods `startBulkEnrichment`, `getBulkEnrichmentProgress`, `cancelBulkEnrichment`, and `heartbeatBulkEnrichment` in `frontend/src/services/ingestApi.ts` matching TypeScript OpenAPI schemas (REQ-ENR-020, REQ-ENR-022, REQ-ENR-032) [Validation: `frontend/src/services/__tests__/ingestApi.test.ts`]
- [X] T019 [US2] Update `frontend/src/components/ingest/CSVEnrichmentProgressModal.tsx` to render total queue count, completed count, issue count, remaining count, in-flight workers, percentage progress bar, elapsed duration, calculated average duration per POI, and interactive "Cancel" button triggering `cancelBulkEnrichment` and showing draining state (REQ-ENR-022 through REQ-ENR-025, SC-003) [Test: `frontend/src/components/ingest/__tests__/CSVEnrichmentProgressModal.test.tsx`]
- [X] T020 [US2] Implement 5-second recurring heartbeat interval via `heartbeatBulkEnrichment` inside `CSVEnrichmentProgressModal.tsx` while active, handling graceful teardown when unmounted or connection lost (REQ-ENR-032) [Test: `frontend/src/components/ingest/__tests__/CSVEnrichmentProgressModal.test.tsx`]

**Checkpoint**: User Stories 1 and 2 functional. Live progress telemetry, 5-second heartbeat, and graceful cancellation draining operational.

---

## Phase 5: User Story 3 - Post-Processing Summary Window & Telemetry Audit (Priority: P2)

**Goal**: Persist complete audit records of every enrichment run to `bulk_enrichment_results`, present an itemized post-run summary window upon session termination, and render an interactive login recovery prompt when an unacknowledged failed or blocked run exists, routing the traveler back into the workbench filtered by `"Incomplete"`.

**Independent Test**: Complete a bulk run with mixed results (successes, temporary errors, and cancelled items). Verify summary window itemizes all counts and termination reason. Simulate browser reload; verify recovery prompt dialog displays for unacknowledged runs. Click "Yes, resume processing" and verify workbench opens with `"Incomplete"` filter active and `acknowledged_at` updated.

### Tests for User Story 3

- [X] T021 [P] [US3] Unit test session audit persistence and login recovery query filtering in `tests/unit/services/ingest/test_bulk_enrichment_recovery.py` (REQ-ENR-026, REQ-ENR-033, REQ-ENR-034, SC-007, SC-008) [Test: `tests/unit/services/ingest/test_bulk_enrichment_recovery.py`]
- [X] T022 [P] [US3] Component test for `BulkEnrichmentRecoveryModal` and `CSVEnrichmentSummaryModal` in `frontend/src/components/ingest/__tests__/EnrichmentModals.test.tsx` (REQ-ENR-026, REQ-ENR-035 through REQ-ENR-038) [Test: `frontend/src/components/ingest/__tests__/EnrichmentModals.test.tsx`]

### Implementation for User Story 3

- [X] T023 [US3] Implement session audit logging in `BulkEnrichmentSessionManager` (`services/worker/bulk_enrichment_manager.py`) persisting final `BulkEnrichmentResult` via `IBulkEnrichmentRepository` upon entering `COMPLETED`, `BLOCKED`, `CANCELLED`, or `FAILED` state with total counts, durations, resources used, and termination reason (REQ-ENR-033, SC-007) [Test: `tests/unit/services/ingest/test_bulk_enrichment_recovery.py`]
- [X] T024 [US3] Implement audit summary endpoint `GET /api/ingest/jobs/{job_id}/bulk-enrichment/summary` in `services/ingest/routes/bulk_enrichment.py` returning detailed metrics and itemized error classifications (REQ-ENR-026, REQ-ENR-027, REQ-ENR-028) [Test: `tests/unit/services/ingest/test_bulk_enrichment_routes.py`]
- [X] T025 [US3] Implement login recovery check and response endpoints `GET /api/ingest/bulk-enrichment/recovery` and `POST /api/ingest/bulk-enrichment/recovery/respond` in `services/ingest/routes/bulk_enrichment.py` querying unacknowledged runs where `status IN ('BLOCKED', 'FAILED')` and updating `acknowledged_at = NOW()` when user selects "resume" or "dismiss" (REQ-ENR-034 through REQ-ENR-038, SC-008) [Test: `tests/unit/services/ingest/test_bulk_enrichment_recovery.py`]
- [X] T026 [P] [US3] Create `frontend/src/components/ingest/CSVEnrichmentSummaryModal.tsx` rendering comprehensive post-run statistics: total POIs, succeeded, issues breakdown, unprocessed, duration, average time, resources consumed, and termination reason (REQ-ENR-026, REQ-ENR-027, REQ-ENR-028) [Test: `frontend/src/components/ingest/__tests__/EnrichmentModals.test.tsx`]
- [X] T027 [P] [US3] Create `frontend/src/components/common/BulkEnrichmentRecoveryModal.tsx` offering "Yes, resume processing", "No", and "Cancel" buttons, with action handlers calling `respondBulkEnrichmentRecovery` (REQ-ENR-035 through REQ-ENR-038) [Test: `frontend/src/components/ingest/__tests__/EnrichmentModals.test.tsx`]
- [X] T028 [US3] Mount `checkBulkEnrichmentRecovery` in `frontend/src/App.tsx` (or `HomePage.tsx`) during authentication initialization, displaying `BulkEnrichmentRecoveryModal` when an unacknowledged failure exists, and routing "resume" to open `CSVImportWorkbenchModal` with initial filter `completeness="incomplete"` (REQ-ENR-034, REQ-ENR-036) [Test: `frontend/src/components/ingest/__tests__/EnrichmentModals.test.tsx`]

**Checkpoint**: User Stories 1, 2, and 3 functional. Audit persistence, post-run summary window, and login recovery flow fully operational.

---

## Phase 6: User Story 4 - Mutual Exclusion Workbench Locking & Race Condition Prevention (Priority: P2)

**Goal**: Prevent concurrent write race conditions by locking the POI Import Staging Workbench in a read-only state during active or draining bulk enrichment, and dynamically validating candidate row selection.

**Independent Test**: Initiate bulk enrichment from the staging workbench. Attempt candidate inline editing, candidate deletion, triage status change, and commit while session is active; verify 100% of mutations are blocked with interactive controls disabled.

### Tests for User Story 4

- [X] T029 [P] [US4] Component test workbench read-only locking and selection confirmation prompt in `frontend/src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx` (REQ-ENR-005 through REQ-ENR-011, SC-004) [Test: `frontend/src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx`]

### Implementation for User Story 4

- [X] T030 [US4] Implement selection scope checking in `CSVImportWorkbenchModal.tsx`: if row checkboxes are selected, pass selected `candidate_ids` to `startBulkEnrichment`; if 0 rows selected, prompt confirmation dialog asking whether to enrich all eligible POIs or abort (REQ-ENR-005 through REQ-ENR-009) [Test: `frontend/src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx`]
- [X] T031 [US4] Implement mutual exclusion workbench lock state in `CSVImportWorkbenchModal.tsx`: while `isEnrichmentActive` or `isEnrichmentDraining` is true, disable all edit drawer inputs, row selection checkboxes, delete buttons, manual override toggles, and commit buttons, showing a visual status badge (REQ-ENR-010, REQ-ENR-011, SC-004) [Test: `frontend/src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx`]
- [X] T032 [US4] Connect `CSVEnrichmentProgressModal` and `CSVEnrichmentSummaryModal` to `CSVImportWorkbenchModal.tsx` lifecycle, transitioning from progress modal to summary modal upon completion, re-enabling workbench controls, and triggering candidate reload on dismiss (REQ-ENR-011, REQ-ENR-026) [Test: `frontend/src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx`]

**Checkpoint**: All user stories functional. Mutual exclusion locking prevents write collisions, selection prompts handle empty selections, and modal state transitions are seamless.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: OpenAPI synchronization, end-to-end quickstart validation, and CI/CD quality gate enforcement.

- [X] T033 [P] Export OpenAPI specification to `openapi.json` via `python -m scripts.export_openapi` and regenerate strict TypeScript types via `npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts` (Constitution §API Contract) [Validation: `git diff --exit-code ./frontend/src/types/api.ts`]
- [X] T034 [P] Execute end-to-end quickstart validation scenarios A through D in `specs/018-bulk-ai-enrich/quickstart.md` verifying canary isolation, fail-fast stop, login recovery prompt, and graceful cancellation (SC-001 through SC-008) [Validation: `specs/018-bulk-ai-enrich/quickstart.md`]
- [X] T035 [P] Run pre-commit checks (`ruff check`, `ruff format`, `prettier`, and `check-copyright-header`) across all modified backend and frontend source files, asserting Apache 2.0 headers and Cognitive Complexity $\le 15$ (Constitution §File Header) [Validation: `ruff check .`]
- [X] T036 Run comprehensive pytest suite with coverage enforcement `pytest tests/unit/services/ingest tests/unit/worker tests/unit/repositories --cov=services/ingest --cov=services/worker --cov=packages/core/vistarae_core --cov-fail-under=90` (Constitution §PyTest Governance) [Test: `pytest`]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup (T001-T004)
        │
        ▼
Phase 2: Foundational Prerequisites (T005-T008) ───► BLOCKS ALL USER STORIES
        │
        ├─────────────────────────────┬─────────────────────────────┐
        ▼                             ▼                             ▼
Phase 3: User Story 1 (P1)     Phase 4: User Story 2 (P1)     Phase 5: User Story 3 (P2)
  Canary & Fail-Fast             Progress & Heartbeat           Audit & Recovery Prompt
  (T009-T014)                    (T015-T020)                    (T021-T028)
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      ▼
                        Phase 6: User Story 4 (P2)
                          Workbench Locking & Scope
                          (T029-T032)
                                      │
                                      ▼
                        Phase 7: Polish & Validation (T033-T036)
```

### User Story Dependencies

- **User Story 1 (P1)**: Can begin immediately after Phase 2 (Foundational). Has no dependencies on other stories.
- **User Story 2 (P1)**: Depends on Phase 2 (Foundational) and interacts with `BulkEnrichmentSessionManager` from US1 for live telemetry.
- **User Story 3 (P2)**: Depends on Phase 2 (Foundational) and records audit results emitted by `BulkEnrichmentSessionManager`.
- **User Story 4 (P2)**: Integrates UI modals from US2/US3 with `CSVImportWorkbenchModal.tsx`.

---

## Parallel Execution Opportunities

- **Phase 1 (Setup)**: Tasks `T002`, `T003`, and `T004` can execute simultaneously in parallel across separate files.
- **Phase 2 (Foundational)**: Task `T008` (repository tests) can be written in parallel with `T007` implementation.
- **Phase 3 (User Story 1)**: Tests `T009` and `T010` can be authored in parallel before `T011`–`T014` implementation.
- **Phase 4 (User Story 2)**: Tests `T015` and `T016` and frontend client `T018` can execute in parallel.
- **Phase 5 (User Story 3)**: Tests `T021` and `T022`, plus UI components `T026` and `T027`, can execute in parallel.
- **Phase 7 (Polish)**: Tasks `T033`, `T034`, and `T035` can execute in parallel before final pytest execution (`T036`).

---

## Implementation Strategy & MVP Delivery

1. **Step 1: Foundation (Phases 1 & 2)**
   - Implement domain entities, database migration `0019_add_bulk_enrichment_results.py`, and repository adapter.
   - Run `alembic upgrade head` and verify repository unit tests pass.
2. **Step 2: MVP Increment (Phase 3 - User Story 1)**
   - Implement `BulkEnrichmentSessionManager` orchestrator with canary gating and fail-fast circuit breaking.
   - Implement session start endpoint with premium subscription gate.
   - **STOP & VALIDATE**: Run Scenario B from `quickstart.md` proving canary halts on HTTP 402 with zero downstream waste.
3. **Step 3: Real-Time Telemetry & Cancellation (Phase 4 - User Story 2)**
   - Add progress polling, 5-second heartbeat, and graceful cancellation draining.
   - Connect frontend `CSVEnrichmentProgressModal`.
   - **VALIDATE**: Run Scenario D from `quickstart.md` proving cancellation drains active tasks within 30 seconds.
4. **Step 4: Audit & Login Recovery (Phase 5 - User Story 3)**
   - Add database audit persistence and login recovery prompt dialog.
   - **VALIDATE**: Run Scenario C from `quickstart.md` proving recovery prompt re-opens workbench filtered by `"Incomplete"`.
5. **Step 5: Mutual Exclusion Locking & Polish (Phases 6 & 7)**
   - Lock workbench during processing to eliminate write race conditions.
   - Regenerate TypeScript types, format source code, and assert $\ge 90\%$ test coverage.

