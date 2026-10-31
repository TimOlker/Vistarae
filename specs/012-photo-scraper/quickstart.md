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

# Quickstart & Verification Guide: Phase 12 — Photo Scraper CLI & Two-Phase Interactive CSV Ingestion

**Feature Identifier**: `012-photo-scraper`  
**Feature Branch**: `012-photo-scraper`  
**Date**: 2026-10-28  
**Status**: Ready for Implementation  

---

## 1. Prerequisites & Environment Setup

Verify required environment variables and services:

```powershell
# 1. Ensure Python virtualenv is active and packages/core is installed
.venv\Scripts\Activate.ps1
pip install -e ./packages/core

# 2. Verify local Docker infrastructure (PostGIS + ElasticMQ)
docker compose up -d

# 3. Ensure GOOGLE_API_KEY is present
$env:GOOGLE_API_KEY = "your-google-ai-studio-api-key"

# 4. Verify local database migration status
alembic upgrade head
```

---

## 2. Validation Scenario 1: Standalone Photo Scraper CLI Execution

### Step 1.1: Run CLI Against Test Photo Directory

```powershell
python -m services.scraper.photo_scraper `
    --input-dir ./tests/fixtures/sample_photos `
    --output-csv ./vistarae_pois.csv `
    --cache-dir ./.scraper_cache
```

### Expected Outcome:
- Traversal prunes noise folders (`thumbs`, `bad`, `.hidden`, `New Folder (2)`, `Tim`).
- Path parser normalizes `1-Tokyo` -> `Tokyo`, `Trip To India\Agra` -> `India / Agra`.
- EXIF & companion sidecars (`.xmp`, `.json`) are parsed for GPS coordinates and earliest date visited.
- The output CSV is generated with 12 standardized columns:
  `POI Name,Street Address,Town/City,State/Province,Zip Code,Country,Tags,latitude,longitude,dates visited,Photo directory,location_confidence_percent`
- **Zero Filesystem Mutation Check**: Hash sum of `./tests/fixtures/sample_photos` before and after matches exactly.

---

### Step 1.2: Verify Incremental Scanning via `--previous-csv`

```powershell
python -m services.scraper.photo_scraper `
    --input-dir ./tests/fixtures/sample_photos `
    --previous-csv ./vistarae_pois.csv `
    --output-csv ./vistarae_pois_delta.csv
```

### Expected Outcome:
- All previously processed directories in `./vistarae_pois.csv` are skipped.
- Output `./vistarae_pois_delta.csv` contains zero rows (or only newly added directories).

---

## 3. Validation Scenario 2: Web App Two-Phase CSV Ingestion

### Step 2.1: Upload CSV via Web Application

1. Start development services:
   ```powershell
   .\scripts\start-dev.ps1
   ```
2. Navigate to `http://localhost:5173`.
3. Open the **Import POIs** modal (`CSVUploadModal.tsx`) and select `./vistarae_pois.csv`.
4. Observe the active progress bar (`CSVProgressModal.tsx`) as SQS workers parse rows, run reverse/forward geocoding fallbacks, and stage rows into `ingest_candidates`.

---

### Step 2.2: Phase 1 Interactive Validation & Sublocation Parent Selection

1. The **Phase 1 Validation Window** (`CSVTriageModal.tsx`) automatically opens upon pre-validation completion.
2. Verify candidate dispositions:
   - Known duplicate POIs display `update existing POI`.
   - New landmarks display `accept`.
   - Low-confidence or generic folders (e.g. `Sledding`) display `ignore`.
   - Nested attractions display `sublocation`.
3. **Sublocation Map Binding**:
   - For an item set to `sublocation`, click an existing POI marker directly on the interactive map.
   - Assert the candidate's `parent_poi_id` binds to the clicked marker.
4. Click **Proceed to Phase 2**.

---

### Step 2.3: Phase 2 AI Enrichment & Final Confirmation

1. The backend orchestrator fetches external web context and invokes Gemini Flash-Lite using the traveler's custom travel style prompt directives (from Phase 11 `user_prompts`).
2. The **Phase 2 Review Window** (`CSVPhase2ReviewModal.tsx`) renders the enriched table with generated `description`, personalized `reason_to_visit`, and tags.
3. Test inline review actions:
   - Toggle **Skip** on one POI.
   - Click **Edit POI** to customize the generated description.
4. Click **Save to DB**.

---

### Step 2.4: Verify Database Persistence & Multi-Visit Merge

Query PostgreSQL to confirm correct transactional commit and merge:

```sql
-- 1. Verify newly created POI
SELECT name, description, reason_to_visit, parent_poi_id, visited_dates, directory_paths
FROM pois
WHERE user_id = '<current_user_id>' AND name = 'Senso-ji';

-- 2. Verify sublocation POI links to parent
SELECT name, parent_poi_id FROM pois WHERE name = 'Monte Alban';

-- 3. Verify multi-visit duplicate merge (union of visited_dates and directory_paths)
SELECT name, visited_dates, directory_paths FROM pois WHERE name = 'Garfield Park Conservatory';

-- 4. Verify staging table clean teardown (0 remaining rows for job)
SELECT count(*) FROM ingest_candidates WHERE job_id = '<job_id>';
```

---

## 4. Automated Test Suite Execution

Run pytest unit and integration suites enforcing $\ge 90\%$ branch and line coverage per Constitution Principle 8:

```powershell
pytest tests/unit/services/scraper/ --cov=services/scraper --cov-fail-under=90
pytest tests/unit/services/ingest/ --cov=services/ingest --cov-fail-under=90
```

