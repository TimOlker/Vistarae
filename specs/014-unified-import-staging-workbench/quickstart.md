# Quickstart Guide: Unified POI Import Staging Workbench

**Feature**: `014-unified-import-staging-workbench`  
**Date**: 2026-11-02  
**Status**: Completed  

This guide provides end-to-end validation steps for the unified Import Staging Workbench, covering single-screen review, targeted single-POI enrichment, "No Websites" idempotency, and sublocation/merge commit integrity.

---

## Prerequisites

1. **Local Database & Services Running**:
   ```powershell
   docker compose up -d
   uv run alembic upgrade head
   ```

2. **Start FastAPI Backend Server** (Port 8000):
   ```powershell
   uv run uvicorn services.local_gateway:app --reload --port 8000
   ```

3. **Start Frontend Dev Server** (Port 5173):
   ```powershell
   npm --prefix frontend run dev
   ```

---

## End-to-End Validation Walkthrough

### Scenario 1: Upload CSV & Verify Active Session Guard
1. Log in to Vistarae at `http://localhost:5173`.
2. Click **Import CSV** and upload a sample file containing duplicate rows and an obscure landmark (e.g., `tests/fixtures/sample_pois.csv`).
3. Confirm column mapping.
4. Open a second browser tab or trigger `POST /api/ingest/upload`:
   - **Expected Result**: Backend rejects with HTTP 409 Conflict: `"Active import session in progress. Please commit or discard job {active_job_id} before uploading a new CSV."`

### Scenario 2: Single-Screen Workbench Navigation & Editing
1. View the unified workbench table.
2. Verify:
   - All rows display completeness indicators (e.g. `Missing Photo`, `Missing Websites`, `Complete`).
   - Clicking any row loads the candidate into the right-hand panel without any modal transitions.
   - The **"Save Candidate Changes"** button is permanently pinned at the bottom of the editor panel outside the vertical scroll container.
3. Edit the candidate's coordinates and address, then click **Save Candidate Changes**:
   - **Expected Result**: The row updates immediately in the left-hand table, and a success toast appears.

### Scenario 3: Targeted Single-POI Enrichment ("AI Enrich POI")
1. Select a candidate with missing photo, websites, or duration (e.g. *Caerleon Roman Legion Museum*).
2. Click the **"AI Enrich POI"** button in the candidate editor.
3. Observe:
   - A loading spinner appears on the button while other table rows remain fully interactive.
   - Within 2–3 seconds, the missing hero photo, related websites, description, and duration populate.
   - Existing user-entered fields are preserved.

### Scenario 4: "No Websites" State Machine & Idempotency
1. Locate or create an obscure candidate with no websites.
2. Trigger AI enrichment on it:
   - **Expected Result**: 0 websites found $\implies$ **"No Websites"** checkbox is automatically checked.
3. Re-run enrichment:
   - **Expected Result**: Backend skips external website search instantly without querying Nominatim or Wikidata.
4. Type a URL into the URL input and click **+ Add Link**:
   - **Expected Result**: The site name is auto-inferred from the domain (e.g. `museum.wales` $\rightarrow$ `National Museum Wales`), and the "No Websites" checkbox is immediately unchecked and disabled.

### Scenario 5: Sublocation Validation & Parent Linking
1. Change candidate disposition to **Sublocation**.
2. Leave parent unassigned and click **Save Candidate Changes**:
   - **Expected Result**: Inline error rejects save: *"Sublocation requires an assigned parent POI"*.
3. Open the parent selector modal and pick a parent (from either the database or another batch candidate).
4. Save again:
   - **Expected Result**: Save succeeds, displaying the parent reference.

### Scenario 6: Final Commit to PostGIS
1. Click **Save POI(s) to DB** in the workbench footer.
2. Observe:
   - Accepted candidates commit to PostGIS `pois` table.
   - In-batch merge candidates transfer unique related websites and notes to primary candidates before being pruned.
   - The staging session is cleared.
   - The map view loads showing all newly imported places.

---

## Automated Unit & Integration Tests

Run focused unit tests without running full test suites:

```powershell
# Core domain and repository tests
uv run pytest tests/unit/services/ingest/test_staging_routes.py -v

# Frontend workbench modal tests
npm --prefix frontend run test:unit -- src/tests/ingest/CSVImportWorkbenchModal.test.tsx
```

