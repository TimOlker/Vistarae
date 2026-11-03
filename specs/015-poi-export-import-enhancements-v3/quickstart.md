# Quickstart Guide: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Feature**: `015-poi-export-import-enhancements-v3`  
**Date**: 2026-11-02  
**Status**: Ready for Verification  

---

## 1. Prerequisites

- Python 3.12+ with virtual environment activated
- Node.js 20+ with npm
- PostgreSQL 16+ running on port `5433` with PostGIS 3.4+

---

## 2. Database Migrations

Apply Alembic migrations to ensure the ISO administrative address columns and composite indexes exist:

```bash
# Check current migration head
python -m alembic current

# Upgrade to head (revisions 0015 and 0016)
python -m alembic upgrade head
```

Verify the `pois` and `ingest_candidates` columns in PostgreSQL:
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'pois' 
  AND column_name IN ('country_code', 'admin_level_1', 'admin_level_2', 'locality', 'photo_directories');
```

---

## 3. Contract & Frontend Generation

Synchronize the OpenAPI schema and regenerate TypeScript definitions:

```bash
# Export backend OpenAPI contract
python -m scripts.export_openapi

# Regenerate frontend TypeScript bindings
npm --prefix frontend run codegen
```

---

## 4. Running Automated Unit Tests

### 4.1 Frontend Component Tests

Run the full frontend test suite including the Unified Staging Workbench:

```bash
npm --prefix frontend run test:unit
```

Target the specific workbench test suite:
```bash
npm --prefix frontend run test:unit -- src/tests/ingest/CSVImportWorkbenchModal.test.tsx
```

### 4.2 Backend Unit Tests

Run targeted backend tests without pytest-watch blocking:

```bash
# Ingest staging & parser tests
python -m pytest tests/unit/services/ingest/ -o addopts=""

# POI service & geocoding tests
python -m pytest tests/unit/services/poi/ -o addopts=""

# Worker enrichment tests
python -m pytest tests/unit/services/worker/ -o addopts=""
```

---

## 5. End-to-End Workbench Walkthrough

1. **Launch the Development Stack**:
   ```powershell
   .\scripts\start-dev.ps1
   ```
2. **Upload a Sample International CSV**:
   - Open `http://localhost:5173`.
   - Click **Import Travel Points (CSV)**.
   - Select a CSV containing international landmarks (e.g. Mount Fuji, Colosseum, Petra, Singapore).
   - Click **Start Ingestion**.
3. **Inspect the Unified Staging Workbench**:
   - Verify the split layout: Candidate Master Table on left, Detail Editor on right.
   - Switch the perspective dropdown between **POI** (alphabetical) and **Location** (geographic).
   - Click column headers to verify dynamic sort overrides.
4. **Test Detail Editor Capabilities**:
   - **Interactive Map**: Drag the pin or click on the map. Verify latitude/longitude update. Click "Re-sync Address from Pin" to reverse-geocode.
   - **Hero Image**: Enter an image URL and observe the uncropped preview directly below.
   - **Websites**: Add dynamic website pairs, delete one, and observe the confirmation dialog.
   - **Tag Library**: Click tag chips to toggle selection against account library.
   - **Photo Directories**: Add a directory path and remove an existing path.
   - **In-Batch Merge**: For a duplicate row, set disposition to `in_batch_merge` and select the target candidate.
   - **Commit**: Click **Commit Import** and verify candidates transition into canonical POIs.

