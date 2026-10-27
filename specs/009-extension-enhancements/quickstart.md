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

# Phase 1 Quickstart & Validation Guide: Extension Enhancements & Tag Governance

**Feature**: `009-extension-enhancements`  
**Date**: 2026-10-22  
**Status**: Ready for Validation

---

## 1. Prerequisites & Environment Setup

### 1.1 Local Infrastructure

Ensure local PostgreSQL with PostGIS 3.4+ is running:

```bash
docker compose up -d
```

### 1.2 Apply Database Migrations

Apply Alembic revision `0007` to update the `tags` and `user_preferences` schema:

```bash
alembic upgrade head
```

### 1.3 Launch Backend Gateway & Frontend Dev Server

In separate terminal sessions:

```bash
# Terminal 1: Backend API Gateway (Port 8000)
uvicorn services.local_gateway:app --reload --port 8000

# Terminal 2: Vite SPA Frontend (Port 5173)
cd frontend
npm run dev
```

### 1.4 Load Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (top right toggle).
3. Click **Load unpacked** and select `d:\Coding\Vistarae\extension`.
4. Ensure the extension ID is registered and active.

---

## 2. Validation Scenarios

### Scenario 1: Web App Tag Governance & Referential Deletion Protection

1. Open the Web App at `http://localhost:5173` and log in.
2. Navigate to **Preferences** (`/settings`) and click the **Tags** tab.
3. **Verify Alphabetical Order & Defaults**:
   - Confirm 30 standard default tags render in strict ascending alphabetical order (Aircraft, Animal, Building ... Zoo).
   - Inspect `Fortification`: verify it displays aliases `castle`, `fort`, `citadel`, `fortress`.
4. **Create a Custom Tag**:
   - Click **Add Tag**. Enter Name: `Historic Railway`, Aliases: `steam train, cog railway`.
   - Submit form. Confirm tag appears sorted alphabetically with auto-generated slug `historic_railway`.
5. **Assign Tag to a POI**:
   - Open any existing POI in the POI table and edit its tags to include `Historic Railway`.
   - Save POI.
6. **Attempt Deletion (Referential Protection)**:
   - Return to `/settings` -> Tags tab.
   - Click the delete (trash) icon next to `Historic Railway`.
   - **Expected Outcome**: Deletion is blocked with an RFC 7807 409 Conflict modal:
     `"Cannot delete tag 'historic_railway': currently used by 1 POI. [View 1 Affected POI in Table]"`.
7. **Remediate and Delete**:
   - Click `[View 1 Affected POI in Table]`. Confirm table navigates pre-filtered to `Historic Railway`.
   - Remove `Historic Railway` from that POI.
   - Return to Tags tab and click delete again. Confirm tag is permanently removed.

---

### Scenario 2: Web App Scraping Sources Configuration

1. In the Web App Preferences (`/settings`), navigate to the **Scraping Sources** section.
2. **Verify Defaults**:
   - Confirm default domains render: `wikipedia.org`, `tripadvisor.com`, `atlasobscura.com`, `google.com/maps`, `roadtrippers.com`.
3. **Add Custom Domain**:
   - Input `nationalgeographic.com` and click **Add Domain**.
   - Click **Save Scraping Preferences**.
4. **Verify API Contract**:
   ```bash
   curl -X GET http://localhost:8000/api/user/preferences/scraping-sources \
     -H "Authorization: Bearer <JWT_TOKEN>"
   ```
   **Expected Outcome**: Returns HTTP 200 with JSON payload containing the updated domain array.

---

### Scenario 3: Extension Companion Page Overhaul & Demo Data Purge

1. Click the Vistarae extension icon in the Chrome toolbar to open `browser.html`.
2. **Verify Streamlined Design**:
   - Confirm the old tabular POI list, search bar, category dropdown, and "Export to CSV" button are **completely removed**.
   - Confirm no demo records (`Glacier Point Overlook`, `Mist Trail`) appear anywhere on the page.
3. **Verify Overview Content**:
   - Confirm the authenticated user banner displays the logged-in email (`Signed in as: ...`).
   - Confirm the capture keystroke cheat sheet renders: `Ctrl+Shift+S` (Windows/Linux) or `Cmd+Shift+S` (Mac).
   - Click the **Open Vistarae Web App** button; confirm it opens `http://localhost:5173` in a new tab.

---

### Scenario 4: Extension Authentication Safeguard

1. Open Chrome DevTools for the extension background service worker:
   - Navigate to `chrome://extensions/` -> Vistarae -> click `service_worker`.
2. In the console, simulate logged-out state:
   ```javascript
   chrome.storage.local.clear();
   ```
3. Switch to any web tab (e.g. `https://en.wikipedia.org/wiki/Eiffel_Tower`) and press `Ctrl+Shift+S`.
4. **Expected Outcome**:
   - Capture overlay is **not** injected.
   - Active tab immediately opens `http://localhost:5173/login?return_to=extension`.

---

### Scenario 5: Multi-Source Scraping & Full Field Parity

1. Log in to Vistarae in the Web App to restore active tokens to `chrome.storage.local`.
2. Navigate to `https://en.wikipedia.org/wiki/Bamburgh_Castle`.
3. Highlight text: `Bamburgh Castle is a castle on the coast at Bamburgh in Northumberland, England.`
4. Press `Ctrl+Shift+S`.
5. **Verify Capture Overlay Form Parity**:
   - **Name**: `Bamburgh Castle` (Standardized English).
   - **Description**: Synthesized concise summary generated via Gemini Flash-Lite.
   - **Coordinates**: Latitude `55.6089`, Longitude `-1.7099` extracted from Wikipedia.
   - **Addresses**: Address object populated with Country `United Kingdom` (ISO 3166-1).
   - **Official Website**: `https://www.bamburghcastle.com`.
   - **Wikipedia URL**: `https://en.wikipedia.org/wiki/Bamburgh_Castle`.
   - **Hero Image**: Thumbnail preview loaded from Wikimedia Commons.
   - **Estimated Duration**: Populated (e.g., 3.5 hours, 0 days).
   - **Tags**: Pre-selected candidate tags `Fortification` and `Historic` (from aliases "castle" and "historic").
   - **Star Rating**: Clean/unassigned (awaits traveler manual selection).
   - **Local Photo Folder**: Completely absent/null.
6. Select 5 stars and click **Save to Vistarae**.
7. Confirm HTTP 200 response and overlay auto-closes.

---

### Scenario 6: Scale-Aware Duplicate & Nesting Triage

1. In the Web App, ensure you have a saved POI named `Millennium Park` in Chicago (Coordinates: `41.8826`, `-87.6226`).
2. Navigate to a webpage about `Cloud Gate` (e.g. `https://en.wikipedia.org/wiki/Cloud_Gate`).
3. Press `Ctrl+Shift+S`.
4. **Verify Early Triage Prompt**:
   - Within 500ms, the overlay displays the triage banner:
     `"Discovered existing location: Millennium Park (25m away). Cloud Gate appears to be located within Millennium Park."`
   - Three buttons appear: `Proceed as New`, `Make Child of Millennium Park` (highlighted/recommended), and `Abort`.
5. Click **Make Child of Millennium Park**.
6. Click **Save to Vistarae**.
7. In the Web App POI table, inspect `Cloud Gate`:
   - Confirm `parent_poi_id` matches Millennium Park's ID.
   - Confirm `parent_poi_name` renders as `Millennium Park`.

---

## 3. Automated Test Execution

Execute the full suite of backend and frontend unit tests:

```bash
# Backend domain and service unit tests (with 90% coverage enforcement)
pytest tests/unit/services/poi/ -v --cov=services/poi --cov-fail-under=90
pytest tests/unit/packages/core/ -v --cov=packages/core --cov-fail-under=90

# Frontend component & preference tests
cd frontend
npm test
```
