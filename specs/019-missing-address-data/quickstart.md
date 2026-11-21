# Quickstart & Verification Guide: Incomplete Data Acknowledgment & Exemption Checkboxes (019-missing-address-data)

**Feature**: `019-missing-address-data`  
**Date**: 2026-11-18  

---

## Prerequisites

1. Local PostGIS Docker container running on port 5432 (`postgis/postgis:16-3.4`).
2. Virtual environment activated with packages installed in editable mode (`pip install -e ./packages/core`).
3. Frontend dependencies installed (`cd frontend && npm install`).

---

## Scenario 1: Database Migration & Schema Verification

Verify that the new columns are created with non-nullable booleans and default to `FALSE`, and that rollback cleanly drops them.

```bash
# 1. Run Alembic upgrade
alembic upgrade head

# 2. Verify schema columns in PostgreSQL
psql -h localhost -U postgres -d vistarae -c "\d pois"
psql -h localhost -U postgres -d vistarae -c "\d ingest_candidates"
# Expected: no_address (boolean, not null, default false) and no_websites (boolean, not null, default false) exist.

# 3. Test reversible downgrade (Constitution Principle 4)
alembic downgrade -1
psql -h localhost -U postgres -d vistarae -c "\d pois"
# Expected: no_address and no_websites columns cleanly removed without leftover artifacts.

# 4. Re-apply upgrade for continued testing
alembic upgrade head
```

---

## Scenario 2: Candidate Exemption & Completeness Recalculation

Verify that checking `no_address` and `no_websites` transitions a candidate from "Incomplete" to "Complete".

```bash
# Execute candidate completeness unit and API test suite
pytest tests/unit/services/ingest/test_completeness_exemptions.py -v
```

**Expected Results**:
- A candidate lacking a street address initially yields `missing_fields = ["Street Address"]` and `is_complete = False`.
- Patching `no_address = True` recalculates missing fields to `[]` and `is_complete = True`.
- Populating a non-empty `street_address` automatically resets `no_address = False`.

---

## Scenario 3: Workbench Filtering ("Needs Action" vs. "Exempted")

Verify filtering behavior in the React frontend:

```bash
# Run Jest / Vitest component tests for CSVImportWorkbenchModal
cd frontend
npm run test -- src/components/ingest/__tests__/CSVImportWorkbenchModal.test.tsx
```

**Expected Results**:
- Selecting `"Needs Action"` filters the table to candidates having at least one unexempted missing required field.
- Selecting `"Exempted"` filters the table to candidates with `no_address === true` or `no_websites === true`.
- Toggling batch action buttons ("Mark Selected: No Address") dispatches `POST /api/ingest/jobs/{job_id}/batch-edit` and updates all selected rows in under 100ms.

---

## Scenario 4: Promotion & POI Persistence Round-Trip

Verify that committing staged candidates persists the exemption flags to `pois` and that CSV export/import preserves them.

```bash
# Run end-to-end integration test
pytest tests/integration/services/test_candidate_exemption_promotion.py -v
```

**Expected Results**:
- Staged candidate with `no_address = True` and `no_websites = True` promoted to `pois` table retains `no_address = True` and `no_websites = True`.
- Exporting the POI to CSV includes `No Address` and `No Websites` column headers with `true`.
- Re-importing that CSV maps `no_address` and `no_websites` to `True` without manual intervention.

---

## Scenario 5: AI Bulk Enrichment Worker Skip Validation

Verify that background workers bypass external lookups when exemptions are set:

```bash
pytest tests/unit/services/worker/test_worker_exemption_skips.py -v
```

**Expected Results**:
- Worker processing candidate with `no_websites = True` skips Wikipedia OpenSearch, TripAdvisor, and scraper adapters.
- Worker processing candidate with `no_address = True` skips reverse geocoding lookups.
- Worker NEVER sets `cand.no_websites = True` or `cand.no_address = True` automatically.
