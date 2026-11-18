# Quickstart Validation Guide: AI Bulk Enrichment (018-bulk-ai-enrich)

**Date**: 2026-11-13  
**Status**: Ready  
**Feature Spec**: [spec.md](./spec.md) | **Data Model**: [data-model.md](./data-model.md) | **API Contract**: [bulk_enrichment_api.yaml](./contracts/bulk_enrichment_api.yaml)

---

## 1. Prerequisites & Environment Setup

1. **Local Infrastructure Active**:
   - Ensure local PostGIS database is running:
     ```bash
     docker compose up -d
     ```
2. **Apply Database Migration**:
   - Apply the migration script creating the `bulk_enrichment_results` table:
     ```bash
     alembic upgrade head
     ```
3. **Set Concurrency Configuration**:
   - In `.env` or execution shell:
     ```bash
     export BULK_ENRICHMENT_CONCURRENCY=3
     export STAGE=local
     ```
4. **Start Backend Gateway**:
   ```bash
   uvicorn services.local_gateway:app --reload --port 8000
   ```
5. **Start Frontend Client**:
   ```bash
   cd frontend && npm run dev
   ```

---

## 2. End-to-End Validation Scenarios

### Scenario A: Canary Validation & Normal Parallel Completion
**Objective**: Prove candidate #1 acts as a solitary canary, scales up to concurrency ceiling ($C=3$), and completes with an audit log.

1. **Step 1: Ingest Test Job**:
   - Upload a test CSV containing 6 POIs (e.g. `tests/fixtures/sample_japan_pois.csv`) into the Staging Workbench.
   - Note the returned `job_id`.
2. **Step 2: Trigger AI Enrich All**:
   - In the workbench, click **"AI Enrich All"**.
   - With 0 rows selected, verify the modal prompts: *"No POIs selected. Do you want to process all 6 eligible POIs?"*
   - Click **"Yes"**.
3. **Step 3: Observe Progress Telemetry**:
   - Modal renders showing:
     - Total: `6`, In-Flight: `1` (Canary phase)
   - Once canary succeeds:
     - In-Flight scales up to `3` (Concurrency limit)
     - Elapsed time updates every second
     - Average processing time per POI is calculated
4. **Step 4: Verify Completion & Persistence**:
   - Summary modal renders upon completion showing:
     - `6` Succeeded, `0` Issues, `0` Unprocessed
     - Total duration, average time, and total resources used
   - Verify database audit record in `bulk_enrichment_results`:
     ```sql
     SELECT id, status, processed_count, unprocessed_count, success_count
     FROM bulk_enrichment_results
     WHERE job_id = '<JOB_ID>';
     ```
     *Expected*: `status = 'COMPLETED'`, `processed_count = 6`, `success_count = 6`.

---

### Scenario B: Canary-Gated Fail-Fast Circuit Breaking
**Objective**: Prove external quota depletion (HTTP 402/429) on the canary immediately halts processing with zero downstream calls.

1. **Step 1: Mock Gemini Quota Depletion**:
   - Configure mock or test environment variable:
     ```bash
     export MOCK_GEMINI_STATUS=402
     ```
2. **Step 2: Trigger AI Enrich All**:
   - Click **"AI Enrich All"** with 5 candidates in the queue.
3. **Step 3: Verify Fail-Fast Behavior**:
   - Canary candidate (#1) executes and returns `BLOCKING_EXTERNAL_ERROR`.
   - Queue halts immediately (< 500ms).
   - In-flight drops to 0; candidates #2 through #5 are **not** dispatched.
   - Summary modal renders with:
     - `0` Succeeded, `1` Issue (Blocking External Error), `4` Unprocessed
     - Termination Reason: *"External service credits exhausted or quota exceeded (HTTP 402)"*
4. **Step 4: Verify Audit Record**:
   ```sql
   SELECT status, processed_count, unprocessed_count, failure_count
   FROM bulk_enrichment_results
   WHERE job_id = '<JOB_ID>';
   ```
   *Expected*: `status = 'BLOCKED'`, `processed_count = 1`, `unprocessed_count = 4`, `failure_count = 1`.

---

### Scenario C: Login Recovery Prompt
**Objective**: Prove unacknowledged failed or blocked runs surface an interactive prompt upon login, opening the workbench filtered to "Incomplete".

1. **Step 1: Reload / Log In**:
   - Refresh the browser or log out and log back in.
2. **Step 2: Verify Prompt Appearance**:
   - Dialog renders: *"Your previous bulk enrichment was interrupted with 4 unprocessed POIs. Would you like to resume processing?"*
   - Options: `"Yes, resume processing"`, `"No"`, `"Cancel"`.
3. **Step 3: Test "Cancel"**:
   - Click `"Cancel"`.
   - Dialog closes. Refresh page: prompt **reappears** because `acknowledged_at` remains `NULL`.
4. **Step 4: Test "Yes, resume processing"**:
   - Click `"Yes, resume processing"`.
   - Staging Workbench opens.
   - Completeness filter is automatically set to `"Incomplete"`.
   - Refresh page: prompt **does not reappear** (`acknowledged_at` was set).

---

### Scenario D: Graceful Cancellation
**Objective**: Prove traveler can stop execution at any time, allowing in-flight workers up to 30 seconds to drain cleanly.

1. **Step 1: Start Large Batch**:
   - Start bulk enrichment on a batch of 20 candidates.
2. **Step 2: Click Cancel**:
   - At ~30% progress, click the **"Cancel"** button on the progress modal.
3. **Step 3: Verify Draining**:
   - Status changes to *"Cancelling... draining active workers"*.
   - No new candidates are dequeued.
   - Active workers finish saving their records.
   - Summary modal renders reporting termination reason *"Cancelled by user"*.

---

## 3. Automated Test Verification Commands

Run targeted unit and contract tests:
```bash
# Backend unit tests for bulk enrichment manager and repository
pytest tests/unit/worker/test_bulk_enrichment_manager.py -v --cov=services/worker/bulk_enrichment_manager --cov-fail-under=90
pytest tests/unit/services/ingest/test_bulk_enrichment_routes.py -v
pytest tests/unit/repositories/test_bulk_enrichment_repo.py -v

# Frontend component tests
cd frontend && npm test -- src/components/ingest/__tests__/CSVEnrichmentProgressModal.test.tsx
cd frontend && npm test -- src/components/ingest/__tests__/BulkEnrichmentRecoveryModal.test.tsx
```

