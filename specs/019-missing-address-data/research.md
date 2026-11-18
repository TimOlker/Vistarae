# Research & Technical Decisions: Incomplete Data Acknowledgment & Exemption Checkboxes (019-missing-address-data)

**Feature**: `019-missing-address-data`  
**Date**: 2026-11-18  
**Status**: Completed  

---

## 1. Technical Context & Baseline Architecture

The Vistarae platform is built as a modular monorepo (`packages/core`, `services/`, `frontend/`) governed by the principles in `.specify/memory/constitution.md`.

- **Backend**: FastAPI 0.115+, Python 3.12, SQLAlchemy 2.0 Async (`asyncpg`), Mangum ASGI adapter for AWS Lambda.
- **Database**: PostgreSQL 16+ with PostGIS 3.4+, Neon connection pooling via PgBouncer.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Heroicons.
- **Observability**: OpenTelemetry W3C distributed tracing (`traceparent`, `X-Source`, `X-Destination`) with messaging tags protocol (`MSG ->|`, `MSG <-|`).

---

## 2. Research Decisions & Architectural Tradeoffs

### Decision 1: Persistent Schema Strategy for `no_address` and `no_websites`

- **Decision**: Add `no_address` and `no_websites` as non-nullable `BOOLEAN` columns with `DEFAULT FALSE` and `server_default=text("FALSE")` to both the permanent `pois` table and the staging `ingest_candidates` table.
- **Rationale**:
  - `ingest_candidates` already possesses `no_websites`, but lacks `no_address`.
  - `pois` currently lacks both `no_address` and `no_websites`. When staged candidates were committed in earlier versions, manual triage exemptions were discarded, causing exported or re-imported POIs to re-flag as incomplete.
  - Adding these columns to `pois` ensures permanent persistence, round-trip fidelity through CSV/JSON export and import, and seamless presentation in the main application `EditPOIModal`.
- **Alternatives Considered**:
  - *Storing exemptions in a JSONB metadata bag (`creation_metadata`)*: Rejected because relational booleans provide strict indexing, query simplicity (`WHERE no_address = FALSE`), schema type safety, and direct OpenAPI/TypeScript generation without nested object parsing.

### Decision 2: Elimination of Automated Exemption Assignment (Resolving Contradiction with Legacy Spec 014)

- **Decision**: Completely remove lines in `services/worker/candidate_enricher.py` (specifically lines 441 and 813) that automatically assigned `cand.no_websites = True` when zero external websites were located.
- **Rationale**:
  - The user explicitly mandated: *"These checkboxes should never be automatically set. This will help users in finding records that need to be fixed, and not need to keep seeing POIs that are known to be missing data."*
  - Automatically setting exemptions when scrapers fail hides actual deficiencies from the traveler. Exemption checkboxes must strictly represent conscious human acknowledgment that missing data is acceptable.
- **Alternatives Considered**:
  - *Heuristic flag with an `is_auto` indicator*: Rejected as unnecessarily complex; user requirement explicitly forbids automated checking.

### Decision 3: Completeness Evaluation Logic & Filter Semantics in Workbench

- **Decision**: Update `getCandidateMissingFields` in `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx` so that:
  - `cand.no_address === true` satisfies the Street Address requirement (removes `"Street Address"` from missing fields).
  - `cand.no_websites === true` satisfies the Websites requirement (removes `"Websites"` from missing fields).
  - Overall candidate completeness evaluates to `Complete` when all missing fields are covered by populated data or active exemptions.
  - Expand `CompletenessFilter` type to:
    ```typescript
    export type CompletenessFilter =
      | "all"
      | "complete"
      | "incomplete"
      | "needs_action"
      | "exempted"
      | "missing_photo"
      | "missing_location"
      | "missing_websites";
    ```
  - Semantics:
    - `"needs_action"`: Displays candidates having at least one unfulfilled required field that is not exempted (`getCandidateMissingFields(cand).length > 0`).
    - `"exempted"`: Displays candidates where `Boolean(cand.no_address) || Boolean(cand.no_websites)`.
- **Rationale**:
  - Satisfies Clarification Session Q1 & Q2. By filtering to `"needs_action"`, travelers instantly isolate candidates requiring actual remediation without being distracted by records where data absence has already been declared acceptable.
- **Alternatives Considered**:
  - *A separate toggle checkbox*: Rejected during clarification session in favor of dropdown integration for a cleaner toolbar.

### Decision 4: Multi-Row Batch Operations via Existing Ingest Infrastructure

- **Decision**: Extend `BatchEditCandidatesRequest` in `packages/core/vistarae_core/schemas/ingest_staging.py` and `batch_edit_candidates` in `services/ingest/services/staging_service.py` to accept optional `no_address: bool | None = None` and `no_websites: bool | None = None`.
- **Rationale**:
  - The endpoint `POST /api/ingest/jobs/{job_id}/batch-edit` already exists and executes batched updates scoped to `WHERE user_id = :current_user_id AND job_id = :job_id AND id IN :candidate_ids`.
  - Reusing this existing transactional service method avoids proliferating one-off endpoints while maintaining strict tenancy guarantees.
- **Alternatives Considered**:
  - *Creating a separate `/batch-exemption` router*: Rejected to avoid endpoint redundancy; extending `BatchEditCandidatesRequest` cleanly handles batch marking and clearing.

### Decision 5: Automatic Exemption Reset upon Valid Data Entry

- **Decision**: In both the frontend candidate editor and the backend update handlers, when a user enters or updates a non-empty `street_address`, the system automatically resets `no_address = false`. Similarly, when valid website data is added, `no_websites = false` is automatically set.
- **Rationale**:
  - Eliminates contradictory states where a candidate has a valid physical address while simultaneously claiming "no address available".
- **Alternatives Considered**:
  - *Warning prompt*: Adds friction and unnecessary modal confirmations for common editing actions.

### Decision 6: AI Bulk Enrichment Worker Optimization (Spec 018 Parity)

- **Decision**: In `services/worker/candidate_enricher.py`, check `cand.no_address` and `cand.no_websites` before initiating external calls:
  - If `cand.no_websites is True`, bypass secondary lookups (Wikipedia OpenSearch, TripAdvisor, Hillman Wonders, and generic scraping).
  - If `cand.no_address is True`, bypass reverse-geocoding street address lookups.
- **Rationale**:
  - Prevents burning Gemini tokens and external scraping rate limits on data already confirmed not to exist. Reduces execution duration for large batches of wilderness or natural landmark POIs.

---

## 3. Constitution & SDD Compliance Matrix

| Constitution Principle | Requirement | Compliance Implementation |
| :--- | :--- | :--- |
| **Principle 1** | File Header & Pre-Commit | All new and modified `.py`, `.ts`, `.tsx`, and `.sql` files contain the standard Apache 2.0 copyright header banner. Cognitive Complexity $\le 15$. |
| **Principle 2** | Monorepo & Ports/Adapters | Schema definitions isolated in `packages/core/vistarae_core/schemas/` and `tables.py`. No infrastructure leakage into domain layers. |
| **Principle 3** | Database & Tenancy | Boolean columns non-nullable with `server_default=text("FALSE")`. All queries append `WHERE user_id = :current_user_id`. No RLS. |
| **Principle 4** | Alembic & Reversibility | Migration in `db/migrations/versions/` provides fully reversible `upgrade()` and `downgrade()`. No native database ENUMs. |
| **Principle 5** | API Contract & TypeScript | OpenAPI contract updated. TypeScript types synchronized in `frontend/src/types/api.ts` via `npx openapi-typescript`. |
| **Principle 7** | Distributed Tracing & Tags | W3C headers extracted/propagated. Staging endpoints log `MSG ->|` and `MSG <-|` with transaction correlation headers. |
| **Principle 8** | PyTest & SDD Governance | Comprehensive unit and integration tests covering database migration, repository queries, completeness scoring, and batch actions. |
