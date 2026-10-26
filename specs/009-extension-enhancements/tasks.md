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

# Implementation Tasks: Phase 9 — Extension Enhancements & Web App Tag Management (Tag Governance, Rich Web Scraping & Multi-Source Augmentation, Duplicate Triage)

**Feature Identifier**: `009-extension-enhancements`  
**Feature Branch**: `009-extension-enhancements`  
**Date**: 2026-10-22  
**Status**: Ready for Implementation  
**Specification**: [spec.md](./spec.md) | **Implementation Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md) | **Contracts**: [contracts/extension-enhancements-api.yaml](./contracts/extension-enhancements-api.yaml) | **Quickstart**: [quickstart.md](./quickstart.md) | **Checklists**: [checklists/extension.md](./checklists/extension.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify development runtime, workspace packages, and API contract synchronization.

- [X] T-001 Verify Python 3.12, Node.js, and Chrome extension environments; ensure `packages/core` workspace package is installed in editable mode (`pip install -e ./packages/core`) in root `pyproject.toml`.
- [X] T-002 [P] Configure frontend API contract export and TypeScript generation scripts in `frontend/package.json` (`npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema migration, ORM tables, Pydantic v2 schemas, repository interfaces, and default tag seeder required by all user stories.

**⚠️ CRITICAL**: No user story implementation work can begin until this foundational phase is complete.

- [X] T-003 Create Alembic migration `db/migrations/versions/0007_tag_governance_and_scraping_preferences.py` adding `slug` VARCHAR(64) NOT NULL and `aliases` JSONB NOT NULL DEFAULT `'[]'::jsonb` to `tags` table, adding unique constraint `uq_tags_user_slug` on `(user_id, slug)` and index `idx_tags_user_slug`, adding `valid_scraping_domains` JSONB NOT NULL DEFAULT `'["wikipedia.org", "tripadvisor.com", "atlasobscura.com", "google.com/maps", "roadtrippers.com"]'::jsonb` to `user_preferences` table, and providing fully reversible `downgrade()` in `db/migrations/versions/0007_tag_governance_and_scraping_preferences.py`. [REQ-EXT-004, REQ-EXT-019]
- [X] T-004 [P] Update `TagTable` ORM definition in `packages/core/vistarae_core/adapters/db/tables.py` with `slug: Mapped[str] = mapped_column(String(64), nullable=False)`, `aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))`, and `UniqueConstraint("user_id", "slug", name="uq_tags_user_slug")`. [REQ-EXT-004, REQ-EXT-005]
- [X] T-005 [P] Update `UserPreferencesTable` ORM definition in `packages/core/vistarae_core/adapters/db/tables.py` adding `valid_scraping_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[\"wikipedia.org\", \"tripadvisor.com\", \"atlasobscura.com\", \"google.com/maps\", \"roadtrippers.com\"]'::jsonb"))`. [REQ-EXT-019]
- [X] T-006 [P] Create Pydantic v2 schemas in `packages/core/vistarae_core/schemas/tag.py` (`TagCreateRequest`, `TagResponse`, `TagInUseProblemDetails`) and `packages/core/vistarae_core/schemas/scraping.py` (`ScrapingSourcesResponse`, `ScrapingSourcesUpdateRequest`) subclassing `StrictBaseModel` with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True`. [REQ-EXT-004, REQ-EXT-006, REQ-EXT-019, REQ-EXT-034]
- [X] T-007 [P] Define repository port interfaces `ITagRepository` and `IScrapingPreferencesRepository` in `packages/core/vistarae_core/ports/repositories.py`. [REQ-EXT-001, REQ-EXT-019]
- [X] T-008 Implement SQLAlchemy 2.0 async repository `TagRepository` in `services/poi/repositories/tag_repository.py` enforcing `WHERE user_id = :current_user_id` on all queries, alphabetical sorting by `name ASC`, and referential check against `poi_tags` before deletion. [REQ-EXT-001, REQ-EXT-002, REQ-EXT-006, REQ-EXT-007]
- [X] T-009 Implement default tag seeder service `seed_default_tags(user_id, session)` in `services/poi/services/tag_seeder.py` inserting the 30 standardized default tags (Fortification, Landmark, Ship, Aircraft, Military, Rail, Historic, Memorial, Building, Church, Temple, Museum, Scenic, Waterfall, Water, Park, Wilderness, Coast, Mountain, Food, NPS, UNESCO, Culture, Lighthouse, Zoo, Animal, Shopping, Entertainment, Film Location, Humorous) with `slug` and `aliases` (`ON CONFLICT (user_id, slug) DO NOTHING`). [REQ-EXT-003]

**Checkpoint**: Foundation ready — database schema, core domain models, tenant-isolated tag repository, and 30-tag seeder verified.

---

## Phase 3: User Story 1 - Web App Tag Management & Vetted Tag Governance (Priority: P1) 🎯 MVP

**Goal**: Enable travelers to manage their vetted tag library in alphabetical order on the Preferences page (`/settings`), create custom tags with slugs and search aliases, and enforce referential integrity preventing deletion of tags in use with a direct remediation filter link.

**Independent Test**: Navigate to `/settings` -> Tags tab, verify 30 seeded tags render alphabetically, create custom tag `Historic Railway` with aliases `steam train, cog railway`, assign to test POI, attempt deletion (verify 409 Conflict modal with "View Affected POIs in Table" button), unassign tag, and delete successfully.

### Tests for User Story 1
- [X] T-010 [P] [US1] Unit and contract tests for tag management endpoints in `tests/unit/services/poi/test_tags.py` validating alphabetical listing, slug generation, 409 Conflict referential protection, and deletion. [REQ-EXT-001 to REQ-EXT-007, REQ-EXT-034]
- [X] T-011 [P] [US1] Unit and contract tests for scraping sources preferences endpoints in `tests/unit/services/poi/test_preferences.py` validating `GET` and `PUT /api/user/preferences/scraping-sources`. [REQ-EXT-019, REQ-EXT-034]
- [X] T-012 [P] [US1] Frontend unit tests for `TagManager` and `TagListItem` in `frontend/src/tests/components/tags/TagManager.test.tsx` verifying alphabetical sorting, add modal, slug validation, and delete conflict remediation link. [REQ-EXT-002, REQ-EXT-004, REQ-EXT-005, REQ-EXT-006]

### Implementation for User Story 1
- [X] T-013 [US1] Implement FastAPI tag routes in `services/poi/routes/tags.py` (`GET /api/pois/tags`, `POST /api/pois/tags`, `DELETE /api/pois/tags/{tag_id}`) returning RFC 7807 `TagInUseProblemDetails` on 409 Conflict with `referencing_poi_count` and `remediation_filter_url`. [REQ-EXT-001, REQ-EXT-002, REQ-EXT-005, REQ-EXT-006, REQ-EXT-007]
- [X] T-014 [US1] Implement FastAPI scraping sources routes in `services/poi/routes/preferences.py` (`GET /api/user/preferences/scraping-sources`, `PUT /api/user/preferences/scraping-sources`). [REQ-EXT-019]
- [X] T-015 [P] [US1] Implement `TagListItem.tsx` in `frontend/src/components/tags/TagListItem.tsx` rendering tag name, slug badge, alias pills, POI reference count, and delete button. [REQ-EXT-002, REQ-EXT-004]
- [X] T-016 [US1] Implement `TagManager.tsx` in `frontend/src/components/tags/TagManager.tsx` with alphabetical list, "Add Tag" modal with alias chips, and deletion guard modal providing direct button "View Affected POIs in Table" pre-filtering the POI table. [REQ-EXT-002, REQ-EXT-004, REQ-EXT-005, REQ-EXT-006]
- [X] T-017 [US1] Mount Tags management and Scraping Sources preferences tabs into `frontend/src/pages/SettingsPage.tsx` and integrate with `frontend/src/context/PreferencesContext.tsx`. [REQ-EXT-002, REQ-EXT-019]

**Checkpoint**: User Story 1 complete — Web App Tag Management and Scraping Sources fully testable and operational.

---

## Phase 4: User Story 2 - Extension Streamlining & Authenticated User Context (Priority: P1) 🎯 MVP

**Goal**: Purge redundant tabular UI and demo placeholder records from the extension browser page, replace with an educational companion dashboard, and enforce pre-capture authentication on keystrokes.

**Independent Test**: Load extension without active auth session (verify capture keystroke opens login with return redirect), log in via Web App, open `browser.html` (verify user email is displayed, no CSV button exists, no POI table exists, no demo data appears, and overview guide is visible).

### Tests for User Story 2
- [X] T-018 [P] [US2] Extension unit and DOM tests for companion dashboard and demo data purge in `extension/tests/browser.test.js` asserting absence of `#btn-export-csv`, `#poi-tbody`, `#input-search`, and mock demo records. [REQ-EXT-011, REQ-EXT-012, REQ-EXT-013]
- [X] T-019 [P] [US2] Unit tests for pre-capture authentication gate and redirect helpers in `extension/tests/auth.test.js`. [REQ-EXT-008, REQ-EXT-009, REQ-EXT-010]

### Implementation for User Story 2
- [X] T-020 [US2] Refactor `extension/browser/browser.html` to remove CSV export button, POI table, search bar, and category filters, replacing them with a branded landing hub (workflow overview, shortcut cheat sheet, server status, Web App link). [REQ-EXT-011, REQ-EXT-013]
- [X] T-021 [US2] Update `extension/browser/browser.js` and `extension/browser/browser.css` to delete mock demo destinations (`Glacier Point Overlook`, `Mist Trail`), display authenticated user email and status badge, and bind "Open Vistarae Web App" action. [REQ-EXT-010, REQ-EXT-012, REQ-EXT-013]
- [X] T-022 [US2] Update `extension/background/service_worker.js` and `extension/background/auth.js` to enforce pre-capture token check on `Ctrl+Shift+S` and context menu, redirecting unauthenticated tabs to `/login?return_to=extension` before overlay injection. [REQ-EXT-008, REQ-EXT-009, REQ-EXT-010]

**Checkpoint**: User Story 2 complete — Extension companion page streamlined, demo records purged, and authentication gate enforced.

---

## Phase 5: User Story 3 - Full-Spectrum Synchronized Web Scraping & Multi-Source Augmentation (Priority: P1)

**Goal**: Execute comprehensive web scraping with 1:1 POI Editor field parity, secondary source augmentation (Wikipedia/TripAdvisor) adhering to user-configured domains, 3.0s timeout ceiling with graceful partial fallback, tight Gemini summary synthesis, and vetted tag recommendation.

**Independent Test**: On a third-party webpage, press `Ctrl+Shift+S`, observe Shadow DOM overlay populate with standardized English name, synthesized summary, official URL, Wikipedia URL, hero image thumbnail, estimated duration, and recommended vetted tags. Assert star rating is empty, local photo folder is null, and simulate secondary timeout to verify graceful partial fallback.

### Tests for User Story 3
- [X] T-023 [P] [US3] Unit tests for `ScrapingOrchestrator`, secondary source adapters, and timeout fallback in `tests/unit/services/poi/test_scraping_orchestrator.py`. [REQ-EXT-017, REQ-EXT-018, REQ-EXT-020, REQ-EXT-021, REQ-EXT-028]
- [X] T-024 [P] [US3] Extension DOM tests for capture overlay field synchronization in `extension/tests/overlay.test.js`. [REQ-EXT-014, REQ-EXT-015, REQ-EXT-016, REQ-EXT-029]

### Implementation for User Story 3
- [X] T-025 [US3] Implement secondary source adapters (`WikipediaAdapter`, `TripAdvisorAdapter`) in `services/poi/scraping/secondary_sources.py` querying REST APIs and extracting coordinates, links, thumbnail, and duration respecting `user_preferences.valid_scraping_domains`. [REQ-EXT-018, REQ-EXT-019]
- [X] T-026 [US3] Implement `ScrapingOrchestrator` in `services/poi/scraping/orchestrator.py` with 3.0s timeout ceiling (`asyncio.wait_for`), graceful partial fallback on error/timeout, English name normalization, and Gemini Flash-Lite (`thinking_budget = 0`) tight summary synthesis. [REQ-EXT-017, REQ-EXT-018, REQ-EXT-020, REQ-EXT-021, REQ-EXT-028]
- [X] T-027 [US3] Implement tag recommendation matching engine in `services/poi/scraping/tag_matcher.py` matching scraped text against user's vetted tag slugs and aliases (supporting overlapping aliases recommending all candidate tags). [REQ-EXT-029]
- [X] T-028 [US3] Update `extension/content/content_script.js` and `extension/content/overlay.css` to render full field parity with POI Editor (name, description, multi-address, lat/long, official URL, Wikipedia URL, hero image, duration, parent POI, vetted tags toggle; excluding photo folders and leaving star rating unassigned by default). [REQ-EXT-014, REQ-EXT-015, REQ-EXT-016, REQ-EXT-029]

**Checkpoint**: User Story 3 complete — Multi-source scraping, Gemini summary synthesis, and field-synchronized overlay operational.

---

## Phase 6: User Story 4 - Intelligent Geocoding, Boundary-Aware Addressing & Rate-Limit Caching (Priority: P2)

**Goal**: Resolve coordinates and addresses adhering strictly to OSM Nominatim policy (1 req/sec max with custom User-Agent, PostGIS `geocoding_cache` SHA-256 pre-check), reverse geocode missing address components, and generate multi-address entries for trans-boundary landmarks.

**Independent Test**: Trigger capture for a multi-state or multi-country POI (e.g. Yellowstone National Park or Iguazu Falls), verify multiple address entries are created with English normalized countries (ISO 3166-1), verify the SHA-256 cache entry is written to `geocoding_cache`, and assert subsequent captures reuse cache without HTTP calls.

### Tests for User Story 4
- [X] T-029 [P] [US4] Unit tests for Nominatim geocoding rate limiter, PostGIS `geocoding_cache` lookup, and trans-boundary addressing in `tests/unit/services/poi/test_geocoding.py`. [REQ-EXT-022 to REQ-EXT-027]

### Implementation for User Story 4
- [X] T-030 [US4] Implement geocaching check against `geocoding_cache` (SHA-256 query hash) in `services/poi/services/geocoding_service.py` prior to outbound queries. [REQ-EXT-022, REQ-EXT-027]
- [X] T-031 [US4] Enforce 1 req/sec rate limiting with custom `User-Agent: VistaraeTravelEngine/1.0` and reverse geocoding fallback for missing street/admin fields in `services/poi/services/geocoding_service.py`. [REQ-EXT-023, REQ-EXT-024]
- [X] T-032 [US4] Implement trans-boundary multi-address generation and English ISO 3166-1 country normalization in `services/poi/services/address_normalizer.py`. [REQ-EXT-025, REQ-EXT-026]

**Checkpoint**: User Story 4 complete — Rate-limited geocoding, PostGIS cache lookups, and boundary-aware addressing verified.

---

## Phase 7: User Story 5 - Early Scale-Aware Duplicate & Parent-Child Nesting Triage (Priority: P2)

**Goal**: Classify destination spatial scale (Macro, Medium, Micro) early in extraction, evaluate dual-threshold duplicate vs. parent proximity, and present a 3-way triage prompt ("Proceed", "Make Child", "Abort") in the capture overlay.

**Independent Test**: Create POI "Millennium Park" in database, trigger capture for "Cloud Gate" at identical coordinates, assert early triage modal appears within 500ms and recommends "Make Child", click "Make Child", and assert new POI has `parent_poi_id` set to Millennium Park.

### Tests for User Story 5
- [X] T-033 [P] [US5] Unit tests for scale classification heuristic and dual-threshold duplicate triage in `tests/unit/services/poi/test_triage.py`. [REQ-EXT-030, REQ-EXT-031, REQ-EXT-032]

### Implementation for User Story 5
- [X] T-034 [US5] Implement spatial scale classifier (`Macro`: 5,000m, `Medium`: 500m, `Micro`: 50m) in `services/poi/scraping/scale_classifier.py`. [REQ-EXT-031]
- [X] T-035 [US5] Implement dual-threshold duplicate triage engine in `services/poi/services/duplicate_service.py` distinguishing `POTENTIAL_DUPLICATE` from `NEARBY_PARENT` within the initial 500ms analysis window, including circular parenting prevention to verify candidate parent is not an existing descendant POI. [REQ-EXT-030, REQ-EXT-031]
- [X] T-036 [US5] Integrate 3-action triage modal (`Proceed`, `Make Child`, `Abort`) and parent persistence (`parent_poi_id`, `parent_poi_name`) into `extension/content/content_script.js`. [REQ-EXT-032]

**Checkpoint**: User Story 5 complete — Scale-aware duplicate detection and 3-way parenting triage verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Observability, telemetry tracing, contract validation, and full regression verification.

- [X] T-037 [P] Inject standard W3C distributed tracing headers (`traceparent: 00-{trace_id}-{client_span_id}-01`, `X-Source: extension`, `X-Destination: backend`) into all extension fetch calls in `extension/background/service_worker.js` and verify directional `MSG` logging in `services/poi/middleware/telemetry.py`. [REQ-EXT-033]
- [X] T-038 [P] Verify Pydantic v2 `StrictBaseModel` boundary validation and RFC 7807 `ProblemDetails` error formats across all Phase 9 endpoints in `tests/contract/test_api_contracts.py`. [REQ-EXT-034]
- [X] T-039 Execute all 6 end-to-end scenarios from `quickstart.md` across Web App and Chrome Extension to validate integration. [Quickstart Scenarios 1–6]
- [X] T-040 Execute pytest suite with coverage gate: `pytest --cov=services/poi --cov=packages/core --cov-fail-under=90`.

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 (Setup)**: No dependencies — can start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories.
- **Phase 3 (User Story 1 - Tags & Preferences)**: Depends on Phase 2 — MVP Foundation.
- **Phase 4 (User Story 2 - Extension Streamlining)**: Depends on Phase 2 — Can run in parallel with Phase 3.
- **Phase 5 (User Story 3 - Multi-Source Scraping)**: Depends on Phase 3 (tag matcher) and Phase 4 (auth gate).
- **Phase 6 (User Story 4 - Geocoding & Addressing)**: Depends on Phase 2 & Phase 5 (extraction pipeline).
- **Phase 7 (User Story 5 - Duplicate Triage)**: Depends on Phase 5 & Phase 6 (coordinates and scale).
- **Phase 8 (Polish)**: Depends on all user stories being implemented.

### Parallel Execution Opportunities
- Tasks marked `[P]` can be executed concurrently without shared file locks:
  - Phase 2: `T-004`, `T-005`, `T-006`, `T-007`
  - Phase 3: `T-010`, `T-011`, `T-012`, `T-015`
  - Phase 4: `T-018`, `T-019`
  - Phase 5: `T-023`, `T-024`
  - Phase 8: `T-037`, `T-038`
