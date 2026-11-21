# Implementation Plan: Incomplete Data Acknowledgment & Exemption Checkboxes (019-missing-address-data)

**Branch**: `019-missing-address-data` | **Date**: 2026-11-18 | **Spec**: [specs/019-missing-address-data/spec.md](file:///d:/Coding/Vistarae/specs/019-missing-address-data/spec.md)

**Input**: Feature specification from `/specs/019-missing-address-data/spec.md`

---

## Summary

When importing points of interest (POIs) or creating them manually, candidates that naturally lack specific information (such as wilderness overlooks or mountain peaks without street addresses, or natural features without official websites) are currently flagged as permanently "Incomplete". 

This feature introduces user-controlled exemption checkboxes (`no_address` and `no_websites`) across both the staging workbench (`ingest_candidates`) and the permanent library (`pois`). These checkboxes satisfy the completeness rule for their respective fields when set, may **never** be set automatically by AI or scrapers, can be applied in bulk across selected rows, automatically reset when valid data is entered, optimize AI bulk enrichment by skipping unnecessary external web queries, and enable travelers to filter the workbench by `"Needs Action"` to focus strictly on actionable defects.

---

## Technical Context

**Language/Version**: Python 3.12 (Backend), TypeScript 5.5+ / React 19 (Frontend)  
**Primary Dependencies**: FastAPI 0.115+, SQLAlchemy 2.0 Async, Pydantic v2, Alembic, Tailwind CSS, Heroicons  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`pois` and `ingest_candidates` tables)  
**Testing**: `pytest` (backend unit/integration), Vitest / React Testing Library (frontend)  
**Target Platform**: AWS Lambda (Mangum ASGI) / CloudFront (Frontend) / Local Development (Uvicorn Gateway)  
**Project Type**: Monorepo Web Application (FastAPI microservices + React SPA)  
**Performance Goals**: Table filtering updates in $<100\text{ ms}$ for 1,000 candidates; batch exemption applies across 50 rows in $<1\text{ s}$  
**Constraints**: 
- Strict EARS requirement syntax compliance.
- Zero automatic setting of exemption checkboxes by AI or background scrapers.
- All database queries append `WHERE user_id = :current_user_id` without Row-Level Security (RLS).
- Alembic migration scripts must implement fully reversible `upgrade()` and `downgrade()` functions.
- Cognitive complexity $\le 15$ with early returns and guard clauses ($\le 3$ nesting levels).
**Scale/Scope**: Staging workbench batches up to 1,000 candidates; thousands of permanent POIs.

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Check / Invariant | Status | Verification & Evidence |
| :--- | :--- | :---: | :--- |
| **Principle 1** | Standard Apache 2.0 file header on `.py`, `.ts`, `.tsx`, `.sql` | **PASS** | Automated pre-commit hook runs `check-copyright-header`. |
| **Principle 2** | Monorepo isolation in `packages/core` with Dependency Inversion | **PASS** | Domain schemas defined in `packages/core/vistarae_core/schemas/` and entities in `tables.py`. |
| **Principle 3** | SQLAlchemy 2.0 Pure Async, `WHERE user_id = :current_user_id`, no RLS | **PASS** | Updates and batch edits strictly bound to tenant user ID. Boolean columns default to `FALSE`. |
| **Principle 4** | Alembic migration in `db/migrations/` with fully reversible `downgrade()` | **PASS** | Reversible migration cleanly drops added columns during rollback. |
| **Principle 5** | OpenAPI 3.1 authoritative contract & TypeScript type synchronization | **PASS** | Pydantic schema updates exported to `openapi.json` and synced to `frontend/src/types/api.ts`. |
| **Principle 7** | W3C distributed tracing (`traceparent`, `X-Source`, `X-Destination`) & `MSG ->|` tags | **PASS** | Router endpoints log inbound/outbound messaging protocol tags and propagate correlation headers. |
| **Principle 8** | SDD Governance & PyTest suite | **PASS** | Scenarios covered by unit, integration, and UI component tests. |

---

## Project Structure

### Documentation (this feature)

```text
specs/019-missing-address-data/
├── spec.md              # Feature specification in strict EARS syntax
├── checklists/          # Requirements completeness checklist
│   └── requirements.md  # 16/16 items validated
├── plan.md              # This implementation plan
├── research.md          # Phase 0: Architectural decisions and tradeoffs
├── data-model.md        # Phase 1: Database schemas, migrations, and completeness matrix
├── quickstart.md        # Phase 1: Step-by-step developer verification scenarios
└── contracts/           # Phase 1: API and UI interface specifications
    ├── candidate-exemption-api.yaml
    └── workbench-ui-contract.md
```

### Source Code Impact Areas

```text
packages/core/vistarae_core/
├── adapters/db/
│   └── tables.py                       # Add no_address & no_websites to POITable and IngestCandidateTable
└── schemas/
    ├── poi.py                          # Add no_address & no_websites to POIBase, POICreate, POIUpdate, POIResponse
    └── ingest_staging.py               # Add no_address to CandidateItem, CandidateUpdateRequest, BatchEditCandidatesRequest

db/migrations/versions/
└── <rev>_add_missing_data_exemptions.py # Reversible Alembic migration (upgrade & downgrade)

services/
├── ingest/
│   ├── routes/staging.py               # Pass no_address/no_websites in candidate update and batch edit
│   └── services/staging_service.py     # Handle no_address & no_websites in batch_edit_candidates
├── worker/
│   └── candidate_enricher.py           # Remove auto-setting lines 441 & 813; skip scraping when no_websites=True; skip geocoding when no_address=True
└── poi/
    └── routes/pois.py                  # Map no_address & no_websites in POI CRUD

frontend/src/
├── types/
│   └── api.ts                          # Regenerate via npx openapi-typescript ./openapi.json
└── components/
    ├── ingest/
    │   └── CSVImportWorkbenchModal.tsx # Completeness filter dropdown ("needs_action", "exempted"), batch toolbar buttons, Data Availability checkboxes, auto-reset
    └── pois/
        ├── CreatePOIModal.tsx          # Add no_address & no_websites checkboxes
        └── EditPOIModal.tsx            # Add no_address & no_websites checkboxes

tests/
├── unit/
│   ├── services/ingest/test_completeness_exemptions.py
│   └── services/worker/test_worker_exemption_skips.py
└── integration/
    └── services/test_candidate_exemption_promotion.py
```

---

## Phase Execution Roadmap

### Phase 0: Outline & Research (Completed)
- Resolved all architectural gaps and legacy contradictions in [research.md](file:///d:/Coding/Vistarae/specs/019-missing-address-data/research.md).
- Confirmed zero automated exemption assignment (resolving legacy Spec 014 conflict).
- Clarified `"Needs Action"` filter semantics and auto-reset behavior upon data entry.

### Phase 1: Design & Contracts (Completed)
- Designed database schema additions, Alembic migration script, and Pydantic schemas in [data-model.md](file:///d:/Coding/Vistarae/specs/019-missing-address-data/data-model.md).
- Authored OpenAPI contract and frontend UI contract in [contracts/](file:///d:/Coding/Vistarae/specs/019-missing-address-data/contracts/).
- Created end-to-end verification quickstart in [quickstart.md](file:///d:/Coding/Vistarae/specs/019-missing-address-data/quickstart.md).

### Phase 2: Implementation (Next Command: `/speckit-tasks`)
- **Backend & Database**:
  1. Generate and apply Alembic migration.
  2. Update `POITable` and `IngestCandidateTable` in `tables.py`.
  3. Update Pydantic models in `poi.py` and `ingest_staging.py`.
  4. Update `batch_edit_candidates` in `staging_service.py` and candidate update handlers.
  5. Remove automated setting of `no_websites` in `candidate_enricher.py` and add skip logic for web queries and geocoding.
  6. Regenerate `./openapi.json` and sync `frontend/src/types/api.ts`.
- **Frontend**:
  1. Update `getCandidateMissingFields` and `CompletenessFilter` in `CSVImportWorkbenchModal.tsx`.
  2. Add `"Needs Action"` and `"Exempted"` filter handling.
  3. Add batch exemption toolbar buttons when rows are selected.
  4. Add "Data Availability" checkboxes and auto-reset logic in Candidate Detail Editor.
  5. Add matching checkboxes to `CreatePOIModal.tsx` and `EditPOIModal.tsx`.
- **Testing & Verification**:
  1. Execute unit and integration tests across database, worker, and frontend components.
  2. Verify reversible Alembic migration rollback.
