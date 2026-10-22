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

# Quickstart & Verification Guide: Phase 8 — UI Main Page Enhancements

**Feature Identifier**: `008-ui-main-page-enhancements`  
**Date**: 2026-10-22  
**Status**: Completed  
**Spec Reference**: [spec.md](./spec.md) | **Plan Reference**: [plan.md](./plan.md)

---

## 1. Prerequisites & Environment Setup

Verify the local development environment meets project standards:

- **Python**: 3.12+ with editable `packages/core` installed (`pip install -e ./packages/core`).
- **Node.js**: 20+ with npm dependencies installed (`npm --prefix frontend install`).
- **PostgreSQL**: PostgreSQL 16+ running PostGIS 3.4+ container (`postgis/postgis:16-3.4`).

---

## 2. Database Migration: `0006_filter_rules`

Apply the new Alembic migration to create the `filter_rules` table:

```bash
# Apply migration
alembic upgrade head

# Verify migration status
alembic current

# Verify reversible downgrade and re-upgrade
alembic downgrade -1
alembic upgrade head

# Verify schema alignment with SQLAlchemy metadata
alembic check
```

---

## 3. End-to-End Verification Scenarios

### Scenario 1: Space Management Layout Switching

1. Start the frontend application (`npm --prefix frontend run dev`).
2. Log into the Vistarae discovery canvas (`http://localhost:5173/`).
3. Observe the layout segmented control in the top navigation bar (`Split`, `Map Only`, `Table Only`).
4. **Click "Map Only"**:
   - Verify the POI table smoothly collapses (`display: none`).
   - Verify the Map canvas expands to fill 100% of the horizontal viewport.
   - Verify `map.resize()` is triggered without WebGL context destruction or visual flash.
5. **Click "Table Only"**:
   - Verify the Map canvas collapses.
   - Verify the POI table expands to fill 100% of the horizontal viewport.
   - Verify all visible columns are fully readable without horizontal clipping.
6. **Click "Split View"**:
   - Verify both Map and Table restore side-by-side proportions (~58% map, 42% table).
   - Verify active selections and viewport states are preserved intact.

---

### Scenario 2: Visual Query Builder & Hybrid Filtering

1. In the header bar, click the **Filter** toggle button to expand the query builder panel.
2. Add a rule: `Country` `equals` `"Japan"`.
3. Add a conjunction `AND` with rule: `Rating` `>=` `4`.
4. Add a nested `OR` group: `already_visited` `equals` `false` OR `want_to_visit_again` `equals` `true`.
5. Click **"Apply Filter"**:
   - For collections $<1,000$ POIs: Verify instant ($<50$ms) in-memory filtering of markers on the map and rows in the POI table.
   - For collections $\ge 1,000$ POIs: Verify payload sent to `POST /api/pois/query` with bounding box integration.
   - Verify POI table shows exactly the filtered count.
6. Click **"Clear Filter"**:
   - Verify all filters reset and all tenant POIs reappear within the current viewport.

---

### Scenario 3: Persisting, Loading, and Managing Filter Rules

1. With active filters applied (`Country = "Japan"`, `Rating >= 4`):
   - Configure table columns: reorder to `[Name, Rating, City, Tags]`.
   - Set pin coloring scheme: `Rating` mode (5-star Gold, 4-star Blue).
2. Click **"Save Rule"**:
   - Enter name: `"Japan Top Picks"`.
   - Confirm save: Verify `POST /api/pois/filter-rules` returns HTTP 201.
3. Refresh the browser page (`F5`):
   - Verify the saved rules dropdown lists `"Japan Top Picks"`.
   - Select `"Japan Top Picks"`:
     - Verify the query tree, column layout, and pin colors immediately restore.
4. Modify a condition and click **"Save As"**:
   - Enter name: `"Japan All Curated"`.
   - Verify `POST /api/pois/filter-rules` inserts a second, independent rule record.
5. Click **"Delete Rule"** on `"Japan All Curated"`:
   - Confirm deletion prompt: Verify `DELETE /api/pois/filter-rules/{id}` returns HTTP 204.
   - Verify the deleted rule is removed from the selector.

---

### Scenario 4: Multi-Select Mode & Atomic Bulk Operations

1. In the POI table header, toggle **"Multi-Select Mode"**:
   - Verify a checkbox column appears on every table row.
   - Verify the bulk operations toolbar renders above the table displaying `"0 selected"`.
2. Click the **master header checkbox**:
   - Verify all currently filtered rows are checked.
   - Verify the toolbar updates to display `"N selected"`.
3. **Bulk Rating Update**:
   - Open Bulk Actions -> "Set Star Rating" -> Select 5 stars.
   - Confirm: Verify `POST /api/pois/bulk-edit` updates `rating = 5` across all selected POIs in a single transaction.
4. **Bulk Address Update with Primary-Address Preservation**:
   - Select a multi-address POI (e.g. Iguazu Falls with Argentina & Brazil addresses) and 2 single-address POIs.
   - Open Bulk Actions -> "Update Location Details" -> Set City: `"Puerto Iguazú"`.
   - Confirm:
     - Verify Iguazu Falls' primary address (`addresses[0]`) has `city = "Puerto Iguazú"`.
     - Verify Iguazu Falls' secondary address (`addresses[1]`) remains untouched (Brazil address preserved).
5. **Bulk Batch Ceiling Verification**:
   - Attempt a bulk request with $>500$ `poi_ids`:
   - Verify API returns HTTP 422 with RFC 7807 problem details: `code: "batch_limit_exceeded"`.

---

### Scenario 5: MapLibre GL Cluster Navigation & Pin Popups

1. Pan and zoom the map to a region with dense POIs (e.g. Paris or Beijing).
2. **Cluster Click**:
   - Click a cluster pin showing badge count `(12)`:
   - Verify the map animates bounds easing (`fitBounds`) in 300ms, expanding into child pins.
   - Verify the POI table automatically filters to display strictly the POIs visible in the settled viewport.
3. **Unclustered Pin Click**:
   - Click an individual POI pin:
   - Verify `POIPopupCard` opens anchored directly over the marker.
   - Verify popup displays POI name, star rating, formatted address (or "Multiple Locations ({N})" badge), and thumbnail image.
4. **Edit POI Action**:
   - In the popup, click **"Edit POI"**:
   - Verify the popup closes and `POIEditDrawer` opens populated with the complete POI aggregate record.

---

## 4. Automated PyTest Execution

Run the complete backend test suite ensuring full tenant isolation and coverage targets:

```bash
# Run unit tests for filter rules and bulk operations
pytest tests/unit/services/poi/test_filter_rules.py tests/unit/services/poi/test_bulk.py -v

# Run with strict 90% branch coverage enforcement (Constitution Principle 8)
pytest --cov=services/poi --cov=packages/core/vistarae_core --cov-report=term-missing --cov-fail-under=90
```

---

## 5. Contract Verification (TypeScript Sync)

Assert that backend OpenAPI models synchronize cleanly with frontend types:

```bash
# Export OpenAPI contract
python -m scripts.export_openapi

# Generate TypeScript definitions
npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts

# Assert zero diff
git diff --exit-code ./frontend/src/types/api.ts
```
