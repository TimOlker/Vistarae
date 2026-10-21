# Implementation Tasks: Phase 5 — Manifest V3 Browser Extension & Native Messaging Host

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)  
**Plan Reference**: [specs/005-browser-extension-native-host/plan.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/plan.md)  
**Constitution**: [.specify/memory/constitution.md](file:///d:/Coding/Vistarae/.specify/memory/constitution.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory scaffolding, icons, and shared metadata configuration across extension and native host packages.

- [x] T001 Create project directory scaffolding for `extension/background/`, `extension/content/parsers/`, `extension/browser/`, `extension/icons/`, `native_host/`, and `tests/unit/native_host/`
- [x] T002 Generate extension branding assets in `extension/icons/icon16.png`, `extension/icons/icon48.png`, and `extension/icons/icon128.png`
- [x] T003 [P] Configure Apache-2.0 copyright and license headers across all JavaScript and Python source files per constitutional header rules

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core extension manifests, tracing middleware, and authentication mutex infrastructure that MUST be complete before ANY user story can execute.

> **CRITICAL**: No user story implementation work can begin until this foundational phase is complete.

- [x] T004 Create Manifest V3 configuration in `extension/manifest.json` declaring permissions (`activeTab`, `scripting`, `contextMenus`, `storage`, `nativeMessaging`), scoped host permissions (Cognito, CloudFront/API Gateway, travel sites), keyboard shortcut `Ctrl+Shift+S`, and `externally_connectable` stanza for `localhost:5173` and CloudFront (REQ-EXT-001, REQ-EXT-002, REQ-EXT-003, REQ-EXT-004)
- [x] T005 [P] Implement W3C distributed tracing and telemetry utilities in `extension/background/telemetry.js` generating `traceparent` headers, `X-Source: extension`, and `X-Destination: backend` with directional logging tags `MSG   |->` and `MSG <-|  ` (REQ-EXT-009, Constitution Principle 1 & 7)
- [x] T006 [P] Implement secure credential storage and single-flight silent JWT token refresh mutex in `extension/background/auth.js` with 5-minute pre-flight margin, AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`), transient network error backoff, and state broadcasting (REQ-EXT-006, REQ-EXT-007, REQ-EXT-008, REQ-EXT-008a, REQ-EXT-008b, REQ-EXT-010)

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel or sequentially.

---

## Phase 3: User Story 1 - Hotkey & Context Menu Travel Capture with In-Page Shadow DOM Overlay (Priority: P1) [MVP]

**Goal**: Empower travelers to capture travel ideas and POIs from any webpage via `Ctrl+Shift+S` or context menu into an isolated Shadow DOM overlay (`<vistarae-capture-root>`), sending text to Gemini Flash-Lite for entity extraction, geocoding via Nominatim, and deduplication against PostGIS.

**Independent Test**: Navigate to any webpage, highlight a travel snippet, press `Ctrl+Shift+S`, verify Shadow DOM overlay mounts with CSS reset (`all: initial`), verify POI candidate extracts and displays with category, address, tags, and spatial dedup badge (`UNIQUE_LOCATION` / `POTENTIAL_DUPLICATE` / `NEARBY_PARENT`), and verify saving persists the POI with a unique UUIDv4 `Idempotency-Key`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [x] T007 [P] [US1] Unit test for silent token refresh concurrency mutex and transient retry backoff in `frontend/src/tests/extension/auth.test.ts` (REQ-EXT-007, REQ-EXT-008, REQ-EXT-008a, REQ-EXT-008b) [Test: frontend/src/tests/extension/auth.test.ts]
- [x] T008 [P] [US1] Unit test for Shadow DOM injection, z-index isolation (`2147483647 !important`), and keyboard event trapping in `frontend/src/tests/extension/overlay.test.ts` (REQ-EXT-011, REQ-EXT-012, REQ-EXT-019) [Test: frontend/src/tests/extension/overlay.test.ts]

### Implementation for User Story 1

- [x] T009 [P] [US1] Create scoped CSS stylesheet in `extension/content/overlay.css` for capture modal with CSS reset (`all: initial`), dark/light theme tokens, micro-animations, dedup side-by-side cards, and responsive drawer layout (REQ-EXT-012, REQ-EXT-014)
- [x] T010 [US1] Implement in-page Shadow DOM capture overlay controller in `extension/content/content_script.js` mounting `<vistarae-capture-root>` with `mode: 'open'`, keyboard trap (`Escape` to close, `Ctrl+Enter` to save), maximum z-index (`2147483647 !important`), and host style isolation (REQ-EXT-011, REQ-EXT-012, REQ-EXT-013, REQ-EXT-019)
- [x] T011 [US1] Implement background capture routing and backend API orchestration in `extension/background/service_worker.js` handling `TRIGGER_CAPTURE`, `EXTRACT_AND_CHECK`, and `SAVE_POI` with dynamic content script injection fallback (`chrome.scripting.executeScript`) on pre-existing tabs (REQ-EXT-005, REQ-EXT-015, REQ-EXT-016, REQ-EXT-017, REQ-EXT-018)
- [x] T012 [US1] Implement deduplication decision UI and side-by-side card comparison logic inside `extension/content/content_script.js` allowing users to overwrite, keep both, or link to existing parent site for `POTENTIAL_DUPLICATE` and `NEARBY_PARENT` responses (REQ-EXT-017)

**Checkpoint**: User Story 1 (MVP) is fully functional and testable independently.

---

## Phase 4: User Story 2 - Polymorphic In-Page Content Scraper Framework (Priority: P1)

**Goal**: Automatically extract structured travel POI data (name, category, address, coordinates, rating, website) on specialized travel websites (Google Maps, Roadtrippers, TripAdvisor) using an extensible object-oriented parser registry with generic fallback.

**Independent Test**: Navigate to a Google Maps place page, Roadtrippers waypoint, or TripAdvisor attraction, trigger capture (`Ctrl+Shift+S`), and verify that the parser accurately extracts structured metadata without requiring manual copy-pasting.

### Tests for User Story 2

- [x] T013 [P] [US2] Unit test suite for parser registry and scrapers (`BasePoiParser`, `GoogleMapsParser`, `RoadtrippersParser`, `TripAdvisorParser`, `GenericSelectionParser`) in `frontend/src/tests/extension/parsers.test.ts` (REQ-EXT-020 through REQ-EXT-026) [Test: frontend/src/tests/extension/parsers.test.ts]

### Implementation for User Story 2

- [x] T014 [P] [US2] Implement abstract `BasePoiParser` and parser registry in `extension/content/parsers/BasePoiParser.js` defining `canParse(url, doc)` and `parse(doc, selection)` contract (REQ-EXT-020, REQ-EXT-025, REQ-EXT-026)
- [x] T015 [P] [US2] Implement `GoogleMapsParser` in `extension/content/parsers/GoogleMapsParser.js` extracting place title (`h1.DUwDvf`), address, category button, rating/reviews, website link, and `@lat,lng` from URL pathname (REQ-EXT-021)
- [x] T016 [P] [US2] Implement `RoadtrippersParser` in `extension/content/parsers/RoadtrippersParser.js` extracting waypoint metadata, latitude/longitude, category tags, and description (REQ-EXT-022)
- [x] T017 [P] [US2] Implement `TripAdvisorParser` in `extension/content/parsers/TripAdvisorParser.js` extracting attraction/restaurant title, address, bubble rating, and JSON-LD `schema.org/Place` metadata (REQ-EXT-023)
- [x] T018 [P] [US2] Implement `GenericSelectionParser` in `extension/content/parsers/GenericSelectionParser.js` extracting highlighted text (`window.getSelection()`), page title, meta description, and OpenGraph `og:image` / `og:title` tags (REQ-EXT-024)
- [x] T019 [US2] Integrate parser registry into `extension/content/content_script.js` to automatically inspect current document, select the highest-priority matching parser, and populate the capture overlay with structured fields (REQ-EXT-025, REQ-EXT-026)

**Checkpoint**: User Stories 1 and 2 are functional and testable independently.

---

## Phase 5: User Story 3 - Bi-Directional External SPA Connection & Extension Proxying (Priority: P2)

**Goal**: Enable the Vistarae Single-Page Application (`localhost:5173` or CloudFront origin) to communicate with the extension service worker via `chrome.runtime.sendMessage`, proxying local folder opening requests to the native messaging host and providing installation guidance.

**Independent Test**: Dispatch `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: "/test" })` from the SPA dev server, verify the extension service worker validates origin against `"externally_connectable"`, forwards to native host via `chrome.runtime.sendNativeMessage`, and returns RFC 7807 problem details or success.

### Tests for User Story 3

- [x] T020 [P] [US3] Unit test for external message origin filtering and RFC 7807 error conversion in `frontend/src/tests/extension/external_connectable.test.ts` (REQ-EXT-003, REQ-NATIVE-001) [Test: frontend/src/tests/extension/external_connectable.test.ts]

### Implementation for User Story 3

- [x] T021 [US3] Implement `chrome.runtime.onMessageExternal` listener in `extension/background/service_worker.js` with origin verification, rate-limiting, and forwarding of `open_folder` commands to native host `com.vistarae.folder_opener` via `chrome.runtime.sendNativeMessage` (REQ-EXT-003, REQ-NATIVE-001)
- [x] T022 [US3] Implement native host connection error handling and RFC 7807 error formatting in `extension/background/service_worker.js` to catch `chrome.runtime.lastError` (e.g., host not found) and return actionable diagnostics to the caller (REQ-NATIVE-001, Spec User Story 3 Acceptance Scenarios 3-4)
- [x] T023 [P] [US3] Add helper `openLocalFolder(path)` with extension detection, installation banner, and registration toast to `frontend/src/services/nativeHostService.ts` (REQ-EXT-003, Extension Contract §1.1)

**Checkpoint**: User Story 3 bridge operates cleanly between SPA and Extension.

---

## Phase 6: User Story 4 - Pure Python Binary Native Messaging Host with Windows stdio & UNC Guards (Priority: P2)

**Goal**: Provide a lightweight, zero-dependency Python script (`native_host/folder_dispatcher.py`) communicating over unbuffered stdio using 4-byte native endian integer framing. Enforces `os.O_BINARY` via `msvcrt.setmode` on Windows, uses exact-byte accumulation loop (`read_exact`), isolates logs to `sys.stderr`, normalizes `file:///` URIs, rejects shell metacharacters, restricts UNC paths to private network subnets with a 1.0s timeout probe, and safely launches OS file managers.

**Independent Test**: Run `pytest tests/unit/native_host/test_folder_dispatcher.py` verifying 4-byte framing (`=I`), CRLF binary integrity, shell metacharacter rejection, external UNC rejection (`UNTRUSTED_NETWORK_HOST`), private UNC timeout probe, and OS file explorer execution without `shell=True`.

### Tests for User Story 4

- [x] T024 [P] [US4] Comprehensive unit test suite in `tests/unit/native_host/test_folder_dispatcher.py` testing 4-byte native-endian framing, `read_exact` loop, shell metacharacter rejection (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`), null byte rejection (`\0`), external UNC rejection, private UNC 1.0s reachability probe, and OS launch commands with $\ge 90\%$ branch and line coverage (REQ-NATIVE-002 through REQ-NATIVE-017) [Test: tests/unit/native_host/test_folder_dispatcher.py]

### Implementation for User Story 4

- [x] T025 [P] [US4] Implement 4-byte native endian binary stdio framing, Windows `msvcrt.setmode` binary stream initialization, chunked `read_exact` loop, and `sys.stderr` log isolation in `native_host/folder_dispatcher.py` (REQ-NATIVE-002, REQ-NATIVE-002a, REQ-NATIVE-002b, REQ-NATIVE-003, REQ-NATIVE-003a, REQ-NATIVE-004, REQ-NATIVE-005, REQ-NATIVE-007)
- [x] T026 [US4] Implement path canonicalization, `file:///` URI unquoting, shell metacharacter rejection, and null byte detection in `native_host/folder_dispatcher.py` (REQ-NATIVE-008, REQ-NATIVE-009, REQ-NATIVE-010, REQ-NATIVE-011)
- [x] T027 [US4] Implement UNC network share security inspection, private subnet validation (RFC 1918 + localhost), and 1.0-second socket/reachability probe in `native_host/folder_dispatcher.py` (REQ-NATIVE-008a, REQ-NATIVE-011a, REQ-NATIVE-012)
- [x] T028 [US4] Implement cross-platform OS file manager launching (`os.startfile` / `explorer.exe` on Windows, `open` on macOS, `xdg-open` on Linux with `shell=False`) and framed JSON response encoding in `native_host/folder_dispatcher.py` (REQ-NATIVE-013, REQ-NATIVE-014, REQ-NATIVE-015, REQ-NATIVE-016, REQ-NATIVE-017)

**Checkpoint**: Native Messaging Host functions standalone on all platforms.

---

## Phase 7: User Story 5 - User-Level Cross-Platform Native Host Registration Script (Priority: P2)

**Goal**: Enable standard users without administrator or root rights to register `com.vistarae.folder_opener` on Windows (via `HKCU\Software\Google\Chrome\NativeMessagingHosts`), macOS, and Linux (via user application support/config directories).

**Independent Test**: Run `python scripts/register_native_host.py --extension-id <ID>`, verify `run_dispatcher.bat` is generated on Windows invoking `python -u`, manifest `com.vistarae.folder_opener.json` points to launcher, and HKCU registry key or user folder contains valid manifest reference.

### Tests for User Story 5

- [x] T029 [P] [US5] Unit test suite in `tests/unit/scripts/test_register_native_host.py` verifying Windows user registry writing, batch launcher creation (`python -u`), macOS/Linux `chmod +x` permissions, and manifest JSON path resolution with $\ge 90\%$ coverage (REQ-NATIVE-018, REQ-NATIVE-019, REQ-NATIVE-020) [Test: tests/unit/scripts/test_register_native_host.py]

### Implementation for User Story 5

- [x] T030 [P] [US5] Create Windows batch launcher `native_host/run_dispatcher.bat` invoking Python with `-u` unbuffered flag (`@echo off & python -u "%~dp0folder_dispatcher.py"`) (REQ-NATIVE-002a, REQ-NATIVE-019)
- [x] T031 [P] [US5] Create Native Messaging Host manifest template in `native_host/com.vistarae.folder_opener.json` with host name `com.vistarae.folder_opener`, description, type `stdio`, and allowed origins placeholder (REQ-NATIVE-019, REQ-NATIVE-020)
- [x] T032 [US5] Implement cross-platform user-level registration script in `scripts/register_native_host.py` supporting Windows (`winreg` HKCU registration), macOS (`~/Library/Application Support/...`), and Linux (`~/.config/google-chrome/...`) with CLI flags `--extension-id` and `--uninstall` (REQ-NATIVE-018, REQ-NATIVE-019, REQ-NATIVE-020)

**Checkpoint**: Non-admin registration script works cleanly across Windows, macOS, and Linux.

---

## Phase 8: User Story 6 - Full-Tab POI Explorer & Database Browser with CSV Export (Priority: P3)

**Goal**: Provide a full-tab browser workstation (`browser/browser.html`) for searching, filtering by city/country/tag, inline editing, bulk deleting POIs, revealing local photo directories via the native host, and exporting to RFC 4180 CSV with formula injection neutralization.

**Independent Test**: Open `browser/browser.html` in Chrome, filter POIs by keyword and tags, click "Export to CSV" to confirm formula characters (`=`, `+`, `-`, `@`) are neutralized with prepended `'`, and click "Reveal Folder" to launch local photo directory.

### Tests for User Story 6

- [x] T033 [P] [US6] Unit test suite for CSV formula injection neutralization and RFC 4180 escaping in `frontend/src/tests/extension/csv_export.test.ts` (REQ-EXT-030, REQ-EXT-031) [Test: frontend/src/tests/extension/csv_export.test.ts]

### Implementation for User Story 6

- [x] T034 [P] [US6] Create full-tab POI Explorer HTML interface in `extension/browser/browser.html` with responsive data table, filter controls (city, country, tags, visit state), search bar, geoproximity toggle, and CSV export action button (REQ-EXT-027, REQ-EXT-028)
- [x] T035 [P] [US6] Create responsive stylesheets and dark/light mode CSS variables in `extension/browser/browser.css` matching Vistarae design system tokens (REQ-EXT-027)
- [x] T036 [US6] Implement client-side table rendering, sorting, search debounce, inline editing, bulk deletion, and geolocation distance calculation in `extension/browser/browser.js` (REQ-EXT-028, REQ-EXT-029)
- [x] T037 [US6] Implement RFC 4180 CSV spreadsheet export with formula injection sanitization (`=`, `+`, `-`, `@` escaped with prepended `'`) and native folder opener integration (`NATIVE_OPEN_FOLDER`) in `extension/browser/browser.js` (REQ-EXT-030, REQ-EXT-031, REQ-EXT-032, REQ-EXT-033)

**Checkpoint**: All user stories functional and independently verified.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Multi-component hardening, linting, developer quickstart verification, and cross-cutting documentation.

- [x] T038 [P] Add pre-commit validation and linting checks for extension JavaScript (`npm run lint` / `prettier`) and Python files (`ruff check`, `ruff format`) (Constitution Principle 1)
- [x] T039 [P] Execute end-to-end quickstart test scenarios documented in `specs/005-browser-extension-native-host/quickstart.md`
- [x] T040 Update developer documentation in `README.md` and `docs/extension_native_host.md` detailing extension installation, loading unpacked extension in developer mode, and native host registration

---

## Dependencies & Execution Order

### Phase Dependencies

```
+-----------------------------------------------------------+
| Phase 1: Setup (T001 - T003)                              |
+-----------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------+
| Phase 2: Foundational (T004 - T006)                       |
+-----------------------------------------------------------+
         |                     |                     |
         v                     v                     v
+------------------+  +------------------+  +------------------+
| Phase 3: US1 (P1)|  | Phase 4: US2 (P1)|  | Phase 6: US4 (P2)|
| Capture Overlay  |  | OOP Scrapers     |  | Native Host CLI  |
| (T007 - T012)    |  | (T013 - T019)    |  | (T024 - T028)    |
+------------------+  +------------------+  +------------------+
         |                     |                     |
         +----------+----------+                     v
                    |                       +------------------+
                    v                       | Phase 7: US5 (P2)|
+--------------------------------------+    | Host Registration|
| Phase 5: US3 (P2) SPA-Extension-Host |    | (T029 - T032)    |
| (T020 - T023)                        |    +------------------+
+--------------------------------------+             |
                    |                                |
                    +---------------+----------------+
                                    |
                                    v
+-----------------------------------------------------------+
| Phase 8: US6 (P3) POI Explorer & CSV Export (T033 - T037) |
+-----------------------------------------------------------+
                              |
                              v
+-----------------------------------------------------------+
| Phase 9: Polish & Cross-Cutting Concerns (T038 - T040)    |
+-----------------------------------------------------------+
```

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Foundational (Phase 2). Delivers standalone in-page capture overlay.
- **User Story 2 (P1)**: Depends on Foundational (Phase 2) and integrates with US1 content script overlay.
- **User Story 3 (P2)**: Depends on Foundational (Phase 2) and US1 background service worker routing.
- **User Story 4 (P2)**: Depends on Foundational (Phase 2). Pure Python implementation, completely independent of browser extension.
- **User Story 5 (P2)**: Depends on US4 dispatcher scripts. Can be verified via CLI standalone.
- **User Story 6 (P3)**: Depends on US1 (auth & API orchestration) and US4 (native folder opener).
- **Polish (Phase 9)**: Depends on completion of all user story implementations.

### Parallel Opportunities

- **Setup & Foundational**:
  - `T002` (icons) and `T003` (headers) can run in parallel.
  - `T005` (telemetry) and `T006` (auth mutex) can run in parallel.
- **User Stories (cross-team parallelism)**:
  - Phase 3 (Extension UI / Service Worker), Phase 4 (Scrapers), and Phase 6 (Python Native Host) can proceed completely concurrently.
  - Within Phase 4: `T014`, `T015`, `T016`, `T017`, `T018` (all separate parser files) can be implemented in parallel.
  - Within Phase 6: `T024` (tests) can run in parallel with implementation drafting.
  - Within Phase 8: `T034` (HTML) and `T035` (CSS) can run in parallel.

---

## Parallel Example: User Story 2 (Parsers)

```bash
# Launch parser implementations concurrently:
Task: "Implement BasePoiParser in extension/content/parsers/BasePoiParser.js"
Task: "Implement GoogleMapsParser in extension/content/parsers/GoogleMapsParser.js"
Task: "Implement RoadtrippersParser in extension/content/parsers/RoadtrippersParser.js"
Task: "Implement TripAdvisorParser in extension/content/parsers/TripAdvisorParser.js"
Task: "Implement GenericSelectionParser in extension/content/parsers/GenericSelectionParser.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T001` - `T003`).
2. Complete Phase 2: Foundational (`T004` - `T006`).
3. Complete Phase 3: User Story 1 (`T007` - `T012`).
4. **STOP and VALIDATE**: Load unpacked extension in Chrome, navigate to any site, press `Ctrl+Shift+S`, extract snippet, and save POI.

### Incremental Delivery

1. **Increment 1 (MVP)**: Hotkey capture with in-page Shadow DOM overlay and Gemini extraction.
2. **Increment 2**: Polymorphic scrapers for Google Maps, Roadtrippers, and TripAdvisor (US2).
3. **Increment 3**: Desktop integration — Pure Python Native Host and non-admin registration script (US4, US5).
4. **Increment 4**: Full bi-directional connection between SPA and native host (US3).
5. **Increment 5**: Full-tab POI Explorer workstation with RFC 4180 CSV export (US6).
6. **Increment 6**: Quality polish, pre-commit enforcement, and quickstart end-to-end verification.
