# Quickstart & Verification Guide: Phase 4 — Single-Page Application (SPA) & Interactive POI Frontend

**Feature Identifier**: `004-spa-poi-frontend`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/004-spa-poi-frontend/spec.md](file:///d:/Coding/Vistarae/specs/004-spa-poi-frontend/spec.md)  
**Contracts Reference**: [specs/004-spa-poi-frontend/contracts/frontend-contracts.md](file:///d:/Coding/Vistarae/specs/004-spa-poi-frontend/contracts/frontend-contracts.md)

---

## 1. Prerequisites & Environment Setup

### 1.1 Host Requirements
- **Node.js**: v20.x or later (`node -v`)
- **Package Manager**: `npm` v10.x or later
- **Python**: v3.12+ (for local backend gateway)
- **Docker**: Docker Desktop / Compose v2+ (for PostgreSQL/PostGIS and ElasticMQ)

### 1.2 Start Local Backend Infrastructure
Ensure local database and SQS containers are running:
```bash
docker compose up -d
```

Start the unified local ASGI gateway on port 8000:
```bash
python -m uvicorn services.local_gateway:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend health probe:
```bash
curl http://localhost:8000/health/live
# Expected: {"status":"alive"}
```

### 1.3 Initialize Frontend Workspace
Navigate to the frontend directory, install dependencies, and generate TypeScript types from the backend OpenAPI contract:
```bash
cd frontend
npm install
npm run codegen
```

Verify that `./frontend/src/types/api.ts` was generated and contains definitions for `POIResponse`, `UserPreferencesResponse`, etc.

### 1.4 Start Vite Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in an evergreen browser.

---

## 2. End-to-End Verification Scenarios

### Scenario 1: Authentication, Theming & Preferences Persistence
1. Navigate to `http://localhost:5173/signup`.
2. Register a new user (`traveler@example.com`, password, full name).
3. In local stage, verify the email confirmation code automatically pre-fills or input `123456`. Submit to confirm signup.
4. Verify redirection to `http://localhost:5173/login`. Authenticate with registered credentials.
5. In the top navigation bar, click the **Theme Switcher** icon:
   - Toggle to **Dark Mode**: Assert dark background (`--bg-primary: #0f172a`), crisp contrast, and instant transition (< 50ms) without page reload.
   - Toggle to **Light Mode**: Assert light background (`--bg-primary: #ffffff`).
   - Toggle to **System Mode**: Assert theme synchronizes with OS preference.
6. Navigate to `http://localhost:5173/settings/poi`:
   - Adjust clustering radius slider to `80m`.
   - Select default map layer: `amap`.
   - Click **Save Preferences**.
   - Assert success toast appears and inspect Network tab to verify `PATCH /api/users/me/preferences/poi` succeeded.

---

### Scenario 2: Interactive Map Exploration, Layer Switching & Viewport Synchronization
1. Navigate to the main dashboard map view at `http://localhost:5173/`.
2. Observe the layer switcher widget in the upper-right corner.
3. Switch layers:
   - Select **OpenStreetMap**: Verify standard OSM raster tiles render.
   - Select **Satellite**: Verify satellite imagery loads smoothly without page refresh.
   - Select **AutoNavi / Amap**: Verify Chinese shifted vector tiles load.
4. Test Viewport-Table synchronization:
   - Toggle the switch: **"Filter table to current map viewport"**.
   - Pan the map canvas away from existing POIs. Assert the POI Table updates to show "No POIs in current viewport".
   - Pan back so markers are inside the view. Assert the table repopulates with the visible POIs.
5. Test Bidirectional Highlighting:
   - Click a POI row in the table. Assert the map smoothly pans/zooms to center on the marker and opens the popup card.
   - Click a marker on the map canvas. Assert the corresponding row in the table highlights and scrolls into view.

---

### Scenario 3: Two-Way Coordinate Transformation (China Bounding Box)
1. In the search box or via panning, navigate the map view to Beijing, China (`116.4074°E, 39.9042°N`).
2. Activate the **AutoNavi / Amap** map layer.
3. Observe markers within China: Assert that markers render without visual displacement relative to road imagery (transformed to GCJ-02 in-memory).
4. Click the **"Add POI"** button and select **"Pick on Map"**.
5. Click on a landmark on the Amap canvas (e.g. Tiananmen Square).
6. Inspect the coordinates populated in the Add POI form:
   - Assert the latitude and longitude fields display canonical WGS-84 coordinates (not shifted GCJ-02).
   - Assert the reverse calculation executed Newton's numerical iteration to `< 0.000001°` precision.
7. Pan the map outside China (e.g., to Tokyo or London). Assert coordinates are passed through untransformed.

---

### Scenario 4: Client-Only Photo EXIF Metadata Reader
1. Open the **"Add POI"** modal dialog.
2. Drag and drop a sample photo containing GPS metadata (JPEG or iPhone `.heic` file):
   - Assert the photo thumbnail appears immediately via an ephemeral Blob URL.
   - Assert Latitude, Longitude, and Visited Date fields populate automatically.
   - Inspect the browser Network tab: Assert **ZERO** image bytes were transmitted over the network (100% in-memory extraction).
3. Close the modal dialog:
   - Assert that `URL.revokeObjectURL` was called, releasing the Blob memory.
4. Re-open the modal and drop an image without EXIF GPS data:
   - Assert the advisory badge appears: "No GPS metadata found in photo".
   - Click **"Use Current Location"**: Assert browser prompts for location permission and pre-fills coordinates.
   - Click **"Pick on Map"**: Assert interactive crosshair allows setting coordinates via map click.

---

### Scenario 5: CSV Ingestion Guardrails, Job Polling & Triage Persistence
1. Navigate to the Ingestion view (`/ingest`).
2. Test File Guardrails:
   - Attempt to select a CSV file larger than 2MB or containing > 2,000 rows.
   - Assert the UI blocks submission client-side and opens the **Split Instructions Modal** explaining how to segment the CSV.
3. Test Valid Upload & Polling:
   - Select a valid CSV file (< 2MB, < 2,000 rows). Click **Upload**.
   - Assert the Ingestion Progress view displays a real-time progress bar polling `GET /api/ingest/jobs/{job_id}` at 2s intervals.
4. Test Duplicate Triage Modal & IndexedDB Persistence:
   - When duplicate candidates are detected (`duplicates_pending_count > 0`), the **CSV Triage Modal** opens.
   - Toggle decisions: Mark Item 1 as `COMMITTED` and Item 2 as `REJECTED`.
   - Refresh the browser (`F5` / `Ctrl+R`).
   - Reopen the Ingestion Triage view: Assert the staged decisions (`COMMITTED`, `REJECTED`) are restored from `vistarae_ingest_db` (IndexedDB).
   - Click **"Commit All Decisions"**: Assert `POST /api/ingest/jobs/{job_id}/triage` succeeds and the IndexedDB record is cleared.

---

### Scenario 6: Admin Governance & Access Controls
1. Authenticate with an administrator account (or set `X-Mock-User-Tier: ADMIN`).
2. Navigate to `http://localhost:5173/admin`:
   - Assert the Admin Dashboard renders platform metric cards (total users, active sessions, monthly token budget utilization).
   - In the User Governance table, locate a user and update their tier (`LOW` to `HIGH`).
   - Assert the table row updates optimistically with a success toast.
3. Log out and log in with a standard non-admin account:
   - Attempt to navigate to `http://localhost:5173/admin`.
   - Assert the route guard intercepts the navigation, redirects to `/`, and displays an RFC 7807 403 Forbidden error toast.

---

## 3. Automated Test Suite Execution

Run the complete frontend test suite (unit tests, coordinate projection assertions, and component tests):
```bash
cd frontend
npm run test:unit
```

Expected Output:
```text
✓ src/utils/coordinates.test.ts (12 tests) - Sub-meter Newton iteration & China bbox guard
✓ src/utils/exifReader.test.ts (8 tests) - JPEG/HEIC in-memory extraction & Blob cleanup
✓ src/services/triageStorage.test.ts (6 tests) - IndexedDB persistence & 7-day TTL eviction
✓ src/components/ErrorBoundary.test.ts (5 tests) - RFC 7807 ProblemDetails mapping
✓ src/components/MapLayerSwitcher.test.ts (6 tests) - In-memory marker re-projection

Test Files  5 passed (5)
Tests  37 passed (37)
```
