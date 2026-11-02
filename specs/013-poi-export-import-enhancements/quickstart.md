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

# Quickstart Validation Guide: Phase 13 — Multi-Stage POI Export, Flexible Multi-Fidelity Import & Ingestion Enhancements

**Feature Identifier**: `013-poi-export-import-enhancements`  
**Date**: 2026-10-31  
**Spec Reference**: [spec.md](./spec.md)  
**Data Model**: [data-model.md](./data-model.md)  
**API Contracts**: [contracts/poi-exchange-api.yaml](./contracts/poi-exchange-api.yaml)

---

## 1. Prerequisites & Environment Setup

Verify backend environment and run database migrations:
```powershell
# 1. Activate Python virtual environment
.venv\Scripts\Activate.ps1

# 2. Run Alembic migration to add created_at column and index
alembic upgrade head

# 3. Verify PostgreSQL table schema
python -c "import asyncio; from vistarae_core.adapters.db.session import get_db_session; from sqlalchemy import text; asyncio.run((lambda: [asyncio.sleep(0), (await anext(get_db_session())).execute(text('SELECT id, name, created_at FROM pois LIMIT 1;'))][1])())"
```

Verify frontend environment and type generation:
```powershell
# Sync OpenAPI TypeScript definitions
python -m scripts.export_openapi
npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts

# Ensure frontend builds cleanly
npm --prefix frontend run build
```

---

## 2. Runnable Scenario 1: Strict Zero-Selection Export Prevention & Selective Export

### Objective
Verify that attempting to export when 0 rows are checked aborts with a user prompt, and that checking rows exports exclusively the selected records with all core schema fields and UTF-8 BOM.

### Execution Steps
1. Navigate to Vistarae Explorer in your browser (`http://localhost:5173/`).
2. Without checking any checkboxes, click the **Export** button in the top action bar.
   - **Expected Outcome**: No file download triggers. An alert banner appears: *"No records selected. Please select at least one record to export."*
3. Check 3 specific POI checkboxes in the table.
4. Click **Export** $\rightarrow$ **CSV**.
   - **Expected Outcome**: A file named `vistarae_pois_YYYY-MM-DD.csv` downloads.
5. Inspect the downloaded CSV with PowerShell / Python:
   ```powershell
   python -c "with open('vistarae_pois.csv', 'rb') as f: data = f.read(); assert data.startswith(b'\xef\xbb\xbf'), 'Missing UTF-8 BOM'; print('BOM Verified!')"
   ```
   - **Expected Outcome**: First 3 bytes are `\xef\xbb\xbf` (UTF-8 BOM), the header row contains all core schema fields dynamically derived from `POIExchangeRecord`, and exactly 3 data rows are present.

---

## 3. Runnable Scenario 2: Interactive Column Alignment & Type Validation

### Objective
Verify that uploading a CSV with non-standard headers launches the Interactive Column Mapping Dialog, and that malformed row coordinates trigger the Import Validation Error Modal with a "Skip" option.

### Execution Steps
1. Create a test file `test_trails.csv`:
   ```csv
   Waypoint,Lon,Lat,Notes
   Old Faithful,-110.8281,44.4605,Famous geyser
   Grand Prismatic,true,44.5250,Colorful thermal spring
   Mammoth Hot Springs,-110.7033,44.9769,Terraced limestone
   ```
2. In the Vistarae UI, click **Import** and upload `test_trails.csv`.
3. **Interactive Column Mapping**:
   - `Lon` and `Lat` auto-alias to `longitude` and `latitude`.
   - `Waypoint` prompts for mapping $\rightarrow$ Select `POI Name`.
   - `Notes` prompts for mapping $\rightarrow$ Select `AI Description`.
   - Click **Confirm & Proceed**.
4. **Pre-Import Type Sanity Gate**:
   - The system detects `Grand Prismatic` has boolean `'true'` in `Lon`.
   - The **Import Validation Error Modal** displays:
     *"Invalid coordinate in column 'Lon' (mapped to Longitude). Row 2 contains 'true'. Expected numeric coordinate between -180 and 180."*
5. Click **"Skip 1 Invalid Row & Continue"**.
   - **Expected Outcome**: Staging proceeds with the 2 valid rows (`Old Faithful` and `Mammoth Hot Springs`), skipping row 2 cleanly.

---

## 4. Runnable Scenario 3: Early Tag Library Resolution Dialog

### Objective
Verify that unvetted tags trigger the Early Tag Validation Dialog with one-click "Approve & Add All" capability.

### Execution Steps
1. Create a test file `test_tags.csv` containing an unapproved tag `Onsen`:
   ```csv
   POI Name,latitude,longitude,tags
   Kurokawa Onsen,33.0805,131.1415,Onsen;Scenic
   ```
2. Upload the file.
3. The **Early Tag Validation Dialog** opens before staging:
   *"Found 1 tag not in your library: 'Onsen' (1 POI)"*.
4. Click **"Approve & Add All to Library"**.
   - **Expected Outcome**: `Onsen` is automatically inserted into your `tags` preferences table in PostgreSQL, and the candidate advances to Phase 1 Triage with both `Onsen` and `Scenic` approved.

---

## 5. Runnable Scenario 4: Automated PyTest Suite Verification

Execute the backend automated test suite covering serialization, rate-limiting, and validation:
```powershell
.venv\Scripts\python -m pytest tests/unit/services/ingest/test_poi_exporter.py tests/unit/services/ingest/test_flexible_parser.py tests/unit/services/worker/test_token_bucket.py -o addopts="" --no-cov
```
- **Expected Outcome**: All tests pass ($100\%$ green), asserting UTF-8 BOM presence, formula injection escaping, token bucket 1 req/sec pacing, and column auto-aliasing.

