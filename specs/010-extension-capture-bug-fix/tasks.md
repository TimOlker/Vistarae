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

# Implementation Tasks: Phase 10 — Extension Capture Bug Fixes & Verification Controls

**Feature Identifier**: `010-extension-capture-bug-fix`  
**Feature Branch**: `010-extension-capture-bug-fix`  
**Date**: 2026-10-26  
**Status**: Ready for Implementation  
**Specification**: [spec.md](./spec.md) | **Implementation Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/extension-capture-api.yaml](./contracts/extension-capture-api.yaml) | **Quickstart**: [quickstart.md](./quickstart.md) | **Checklists**: [checklists/extension.md](./checklists/extension.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Vendor bundling for zero-cost mapping assets and API contract synchronization.

- [x] T-001 Bundle Leaflet 1.9.4 assets in `extension/content/vendor/leaflet/leaflet.js` and `extension/content/vendor/leaflet/leaflet.css`, and register them in `extension/manifest.json` under `web_accessible_resources`.
- [x] T-002 [P] Export OpenAPI specification to `openapi.json` and generate TypeScript definitions in `frontend/src/types/extension-capture-api.ts` using `npx openapi-typescript`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core request/response schemas, reverse-geocoding endpoint, and client-side title sanitization utility required across all capture bug fixes.

**⚠️ CRITICAL**: No user story implementation work can begin until this foundational phase is complete.

- [x] T-003 [P] Update `ExtractAndCheckRequest` in `packages/core/vistarae_core/schemas/scraping.py` adding optional fields: `latitude: float | None = Field(default=None, ge=-90.0, le=90.0)`, `longitude: float | None = Field(default=None, ge=-180.0, le=180.0)`, `raw_address: str | None = None`, and `category: str | None = None` under strict `extra="forbid"`. [REQ: FR-002, FR-014]
- [x] T-004 [P] Define `ReverseGeocodeRequest` (with `latitude` and `longitude`) and `ReverseGeocodeResponse` (with `formatted_address`, `country`, `country_code`, `city`, `postcode`, `addresses: list[AddressRecord]`) in `packages/core/vistarae_core/schemas/scraping.py`. [REQ: FR-013, FR-014]
- [x] T-005 [P] Implement `POST /api/v1/geocoding/reverse` in `services/poi/routes/triage.py` delegating to `GeocodingService.reverse_geocode()` backed by PostGIS `geocache` and rate-limited OSM Nominatim. [REQ: FR-013, FR-014]
- [x] T-006 Implement client-side `sanitizeDestinationTitle(rawTitle, platformHint)` utility in `extension/content/parsers/BasePoiParser.js` stripping common platform brand suffixes (` - Google Maps`, ` | TripAdvisor`, ` - Roadtrippers`, etc.) while preserving legitimate geographic hyphens. [REQ: FR-001]

**Checkpoint**: Foundation ready — boundary schemas updated, reverse-geocoding endpoint live, and title sanitization utility available.

---

## Phase 3: User Story 1 - Clean Identity & Multi-Source Knowledge Enrichment (Priority: P1) 🎯 MVP

**Goal**: Automatically sanitize destination titles from mapping platforms, enrich the capture modal with concise summary descriptions, populate canonical Wikipedia article URLs, recommend vetted tags, and infer estimated visit duration (hours and days).

**Independent Test**: Navigate to Google Maps place page for "Eltz Castle", trigger capture (`Ctrl+Shift+S`), and assert destination title is "Eltz Castle" (not "Eltz Castle - Google Maps"), summary description contains an informative overview, Wikipedia URL is populated, vetted tags are recommended, and duration is pre-filled.

### Tests for User Story 1

- [x] T-007 [P] [US1] Unit tests for title sanitization regex and Wikipedia 2-step OpenSearch fallback in `tests/unit/services/poi/test_scraping_orchestrator.py`. [REQ: FR-001, FR-002, FR-003]
- [x] T-008 [P] [US1] Unit tests for category/scale visit duration heuristics in `tests/unit/services/poi/test_scraping_orchestrator.py`. [REQ: FR-017]

### Implementation for User Story 1

- [x] T-009 [US1] Upgrade `WikipediaAdapter` in `services/poi/scraping/secondary_sources.py` implementing 2-step resolution: direct summary lookup (`/page/summary/{title}`) with OpenSearch fallback (`/w/api.php?action=opensearch`) on 404, extracting canonical URL, description, and hero thumbnail. [REQ: FR-002, FR-003]
- [x] T-010 [US1] Implement category and scale visit duration heuristics table (e.g. Castle/Museum: 2.0–2.5h, Theme Park: 6.0h, National Park: 1–2 days) in `services/poi/scraping/orchestrator.py` refined by Gemini Flash-Lite entity extraction (`thinking_budget=0`). [REQ: FR-017]
- [x] T-011 [US1] Update `services/poi/routes/triage.py` to fall back to standard system vetted tags (or auto-seed default tags) when `tag_repo.list_by_user()` returns empty. [REQ: FR-016]
- [x] T-012 [US1] Update `GoogleMapsParser.js` in `extension/content/parsers/GoogleMapsParser.js` to extract headline place name, apply `sanitizeDestinationTitle`, and pass parsed coordinates and category in capture candidate. [REQ: FR-001, FR-002]
- [x] T-013 [US1] Implement progressive asynchronous enrichment in `extension/content/content_script.js`: display instant local fields immediately and asynchronously stream enriched summary, Wikipedia URL, vetted tags, and duration with field-level loading indicators. [REQ: FR-002, FR-003, FR-016, FR-017]

**Checkpoint**: User Story 1 complete — Title sanitized, rich summary synthesized, Wikipedia linked, tags recommended, and duration inferred.

---

## Phase 4: User Story 2 - Address Sanitation & Geographic Accuracy (Priority: P1) 🎯 MVP

**Goal**: Purge invalid unicode icon glyphs (pushpin `🖈`, `📍`) from addresses, eliminate hardcoded `{ country: "United States" }` defaults, and ensure sovereign country accuracy without conflicting multi-country strings.

**Independent Test**: Capture a location from a page containing leading pushpins (e.g. `🖈56294 Wierschem, Germany`), verify the pushpin is completely stripped, country resolves strictly to Germany, and no "Germany, United States" contradiction occurs.

### Tests for User Story 2

- [x] T-014 [P] [US2] Unit tests for address glyph stripping (`🖈`, `📍`) and multi-country conflict resolution in `tests/unit/core/test_address_normalizer.py`. [REQ: FR-014, FR-015]

### Implementation for User Story 2

- [x] T-015 [US2] Enhance `AddressNormalizer` in `packages/core/vistarae_core/services/address_normalizer.py` with unicode regex stripping leading icon symbols (`🖈`, `📍`, `📌`, `🗺`) and filtering out contradictory secondary country tokens when sovereign country is verified. [REQ: FR-014, FR-015]
- [x] T-016 [US2] Eliminate hardcoded `{ country: "United States" }` fallback in `extension/content/content_script.js`, formatting addresses dynamically and giving authoritative precedence to coordinate reverse-geocoding. [REQ: FR-014, FR-015]

**Checkpoint**: User Story 2 complete — Address text cleansed of glyphs and sovereign country resolved accurately.

---

## Phase 5: User Story 3 - Visual Map Verification & Coordinate Reselection (Priority: P2)

**Goal**: Provide an interactive Leaflet/OpenStreetMap mini-map directly in the Shadow DOM overlay showing the plotted coordinates, with a "Reselect Location" toggle supporting both click-to-place and pin-dragging that immediately refreshes coordinates and reverse-geocoded address.

**Independent Test**: Open capture overlay on place with coordinates, observe mini-map centered on pinpoint marker. Click "Reselect Location", click or drag the marker to a new location, verify latitude/longitude fields update and address chip re-queries reverse-geocoding for the new position.

### Tests for User Story 3

- [x] T-017 [P] [US3] Unit tests for reverse-geocoding route `POST /api/v1/geocoding/reverse` in `tests/unit/services/poi/test_geocoding.py`. [REQ: FR-013]
- [x] T-018 [P] [US3] Extension DOM tests for mini-map container, marker placement, and reselection event handling in `extension/tests/overlay.test.js`. [REQ: FR-011, FR-012, FR-013]

### Implementation for User Story 3

- [x] T-019 [US3] Embed Leaflet mini-map container `<div id="vistarae-minimap"></div>` below Latitude/Longitude in `extension/content/content_script.js` and `extension/content/overlay.css`, initializing OSM raster tiles with scoped styles. [REQ: FR-011]
- [x] T-020 [US3] Implement "Reselect Location" mode in `extension/content/content_script.js` supporting both map canvas click-to-place and marker drag events, updating coordinate inputs and dispatching `REVERSE_GEOCODE` on release. [REQ: FR-012, FR-013]
- [x] T-021 [US3] Add `REVERSE_GEOCODE` message handler in `extension/background/service_worker.js` calling backend `POST /api/v1/geocoding/reverse` with W3C tracing headers. [REQ: FR-013]

**Checkpoint**: User Story 3 complete — Interactive mini-map and dual-mode coordinate reselection operational in Shadow DOM.

---

## Phase 6: User Story 4 - Media Preview, Live Reload & Link Verification (Priority: P2)

**Goal**: Provide dedicated "View ↗" preview buttons for Official Website and Wikipedia article inputs, render a visual Hero Image preview thumbnail, and provide an interactive "Reload / Preview" button with client-side preflight verification probe.

**Independent Test**: Capture a destination with hero image and Wikipedia link. Click "View ↗" next to Wikipedia and verify it opens in a new tab. Paste a custom image URL into Hero Image, click "Preview / Reload", and verify the thumbnail renders. Paste an invalid URL and verify an inline non-blocking warning appears.

### Tests for User Story 4

- [x] T-022 [P] [US4] Extension DOM tests for "View" verification buttons, hero preview thumbnail, and image preflight probe in `extension/tests/overlay.test.js`. [REQ: FR-004, FR-006, FR-009, FR-010]

### Implementation for User Story 4

- [x] T-023 [US4] Add "View ↗" verification buttons next to Official Website and Wikipedia URL inputs in `extension/content/content_script.js` and `extension/content/overlay.css`, binding secure new-tab navigation (`window.open(url, '_blank', 'noopener,noreferrer')`) and disabling when inputs are empty. [REQ: FR-004, FR-005, FR-006]
- [x] T-024 [US4] Implement Hero Image preview card `<div id="vistarae-hero-preview">` and interactive "Preview" button in `extension/content/content_script.js` with client-side in-memory `new Image()` preflight probe, displaying thumbnail on success and non-blocking warning on error. [REQ: FR-007, FR-008, FR-009, FR-010]

**Checkpoint**: User Story 4 complete — External links verified via "View" buttons and hero image preview with live reload functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Observability, contract validation, regression test coverage, and pre-commit gate execution.

- [x] T-025 [P] Add contract tests for `POST /api/pois/extract-and-check` and `POST /api/v1/geocoding/reverse` in `tests/contract/test_api_contracts.py` validating strict Pydantic v2 boundary models and RFC 7807 `ProblemDetails`. [REQ: FR-002, FR-013]
- [x] T-026 Execute all 9 end-to-end validation scenarios in `specs/010-extension-capture-bug-fix/quickstart.md` across Chrome Extension and local FastAPI dev server.
- [x] T-027 Execute pytest suite with coverage enforcement: `pytest --cov=services/poi --cov=packages/core --cov-fail-under=90` and extension vitest suite `npx vitest run ../extension/tests`.
- [x] T-028 Run pre-commit hooks across all modified files (`.venv\Scripts\pre-commit run --all-files`) verifying ruff, ruff-format, prettier, and Apache 2.0 copyright header banners.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories.
- **Phase 3 (User Story 1 - Clean Identity & Knowledge Enrichment)**: Depends on Phase 2 — MVP Foundation.
- **Phase 4 (User Story 2 - Address Sanitation & Accuracy)**: Depends on Phase 2 — Can run in parallel with Phase 3.
- **Phase 5 (User Story 3 - Visual Mini-Map & Reselection)**: Depends on Phase 2 & Phase 4 (reverse-geocoding endpoint).
- **Phase 6 (User Story 4 - Media Preview & Link Verification)**: Depends on Phase 2 & Phase 3 (Wikipedia and hero image fields).
- **Phase 7 (Polish)**: Depends on all user stories being implemented.

### Parallel Execution Opportunities

- Tasks marked `[P]` can be executed concurrently without shared file locks:
  - Phase 1: `T-002`
  - Phase 2: `T-003`, `T-004`, `T-005`
  - Phase 3: `T-007`, `T-008`
  - Phase 4: `T-014`
  - Phase 5: `T-017`, `T-018`
  - Phase 6: `T-022`
  - Phase 7: `T-025`
