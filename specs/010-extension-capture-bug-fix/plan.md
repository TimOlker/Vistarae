# Implementation Plan: Extension Capture Bug Fixes & Verification Controls

**Branch**: `010-extension-capture-bug-fix` | **Date**: 2026-10-26 | **Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/010-extension-capture-bug-fix/spec.md)

**Input**: Feature specification from [`specs/010-extension-capture-bug-fix/spec.md`](file:///d:/Coding/Vistarae/specs/010-extension-capture-bug-fix/spec.md)

---

## Summary

Resolves 9 defects identified in manual Chrome Extension capture testing (`Ctrl+Shift+S`) on Google Maps and travel websites:
1. Destination name sanitization stripping source platform branding (e.g. ` - Google Maps`).
2. Multi-source knowledge enrichment populating rich summary descriptions from Wikipedia/Wikidata instead of boilerplate text.
3. Interactive Leaflet/OpenStreetMap mini-map embedded in the Shadow DOM with click-to-place and pin-dragging coordinate reselection.
4. Robust 2-step Wikipedia resolution (direct summary + OpenSearch fallback) ensuring canonical article URL population.
5. "View" verification buttons for Official Website and Wikipedia links opening in new browser tabs.
6. Hero image visual preview thumbnail with interactive "Reload" preflight validation probe.
7. Address normalization stripping leading unicode glyphs (`🖈`, `📍`) and eliminating contradictory multi-country strings (`Germany, United States`) via authoritative coordinate reverse-geocoding.
8. Vetted tag recommendations leveraging system fallback tags and taxonomy matching.
9. Estimated visit duration inference using category/scale heuristics refined by Gemini Flash-Lite.

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.5 (frontend models), JavaScript ES2022 (Chrome Extension Manifest V3).

**Primary Dependencies**: 
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncpg), httpx, google-genai (Gemini Flash-Lite, `thinking_budget: 0`).
- Extension: Pure Vanilla JS / DOM APIs in isolated Shadow DOM, bundled Leaflet 1.9.4 for zero-cost OpenStreetMap rendering.

**Storage**: PostgreSQL 16 with PostGIS 3.4 (`geocache`, `pois`, `tags`, `user_preferences`).

**Testing**: `pytest` with `--cov-fail-under=90` (backend), `vitest` (frontend & extension unit tests).

**Target Platform**: Chrome Extension Manifest V3, Web SPA (React/Vite), Uvicorn/FastAPI local gateway and AWS Lambda (Mangum).

**Project Type**: Hybrid Web Extension & Serverless API.

**Performance Goals**:
- Extension modal initial render: < 100ms.
- Progressive enrichment completion: < 2.5s.
- Reverse-geocoding on pin drop/drag: < 500ms (PostGIS cache hit) / < 1.0s (OSM Nominatim).

**Constraints**:
- Strict zero-cost architecture: OpenStreetMap tiles via Leaflet, no paid Google/Mapbox map keys.
- Nominatim OSM policy: max 1 request/second with custom `User-Agent: VistaraeTravelEngine/1.0`.
- Manifest V3: No remote code execution; Leaflet library and CSS bundled locally.
- Pydantic v2 `StrictBaseModel` with `extra="forbid"`.

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Status | Evaluation & Compliance Notes |
| --------- | ------ | ----------------------------- |
| **1. File Header & Pre-Commit Standard** | **PASS** | All new/modified `.py` and `.js` files require Apache 2.0 copyright headers. Passes `ruff`, `prettier`, and `check-copyright-header`. |
| **2. Monorepo & Ports/Adapters Architecture** | **PASS** | Shared schemas in `packages/core/vistarae_core`. Repositories abstracted behind Protocol interfaces. |
| **3. Database, PgBouncer & Tenancy Invariants** | **PASS** | Pure async SQLAlchemy, `WHERE user_id = :current_user_id` on all mutations, zero RLS. |
| **4. Alembic & Environment Isolation** | **PASS** | Existing schema tables (`pois`, `geocache`, `tags`) already support all fields. No new database migration required. |
| **5. API Contract, Validation & Error Standard** | **PASS** | StrictBaseModel boundary schemas, OpenAPI 3.1 synchronization, RFC 7807 `ProblemDetails` error formats. |
| **6. Middleware Order & Security Guardrails** | **PASS** | CORS whitelist enforced, zero hardcoded credentials, isolated Shadow DOM. |
| **7. Observability, OpenTelemetry & X-Ray** | **PASS** | Standard W3C `traceparent` headers injected on extension fetches; directional `MSG` logging in local development. |
| **8. PyTest & SDD Governance** | **PASS** | Strict test parity in `tests/unit/`, 90% branch/line coverage threshold enforced. |
| **Op. Invariant 2: Geospatial Storage** | **PASS** | WGS-84 canonical coordinates stored in `GEOGRAPHY(Point, 4326)`. |
| **Op. Invariant 3: Zero-Cost Architecture** | **PASS** | Free OpenStreetMap raster tiles, unauthenticated Wikipedia/Wikidata read APIs, internal PostGIS geocache. |

---

## Project Structure

### Documentation (this feature)

```text
specs/010-extension-capture-bug-fix/
├── spec.md              # Requirements and clarifications in strict EARS syntax
├── plan.md              # This implementation plan
├── research.md          # Technical decisions and architecture
├── data-model.md        # Entities, schemas, and client state model
├── contracts/           # API and internal messaging contracts
│   └── extension-capture-api.yaml
├── checklists/
│   └── requirements.md  # Quality validation checklist
└── quickstart.md        # Runnable verification guide for 9 scenarios
```

### Source Code Layout

```text
packages/core/vistarae_core/
├── schemas/
│   └── scraping.py                     # Updated ExtractAndCheckRequest with coords/address
└── services/
    └── address_normalizer.py           # Glyph stripping and country conflict resolution

services/poi/
├── routes/
│   └── triage.py                       # Updated extract-and-check handler & reverse geocode endpoint
└── scraping/
    ├── orchestrator.py                 # Multi-source orchestrator with hybrid duration estimation
    └── secondary_sources.py            # WikipediaAdapter with OpenSearch fallback & hero images

extension/
├── manifest.json                       # Added leaflet resources to web_accessible_resources
├── content/
│   ├── content_script.js               # Shadow DOM modal with mini-map, preflight hero, view buttons
│   ├── overlay.css                     # Styles for mini-map, hero preview, view buttons, loading shimmer
│   ├── vendor/leaflet/                 # Bundled Leaflet JS and CSS for isolated Shadow DOM
│   │   ├── leaflet.js
│   │   └── leaflet.css
│   └── parsers/
│       ├── BasePoiParser.js            # sanitizeDestinationTitle utility
│       └── GoogleMapsParser.js         # Refined title, coordinates, and address selectors
└── background/
    └── service_worker.js               # Enhanced EXTRACT_AND_CHECK & REVERSE_GEOCODE handlers

tests/
├── unit/
│   ├── services/poi/
│   │   ├── test_scraping_orchestrator.py
│   │   ├── test_triage.py
│   │   └── test_geocoding.py
│   └── core/
│       └── test_address_normalizer.py
└── contract/
    └── test_api_contracts.py
```

---

## Execution Phases

### Phase 1: Core Schemas & Address Normalization (Tasks T-001 to T-004)
- Update `ExtractAndCheckRequest` in `packages/core/vistarae_core/schemas/scraping.py` to accept optional coordinates, category, and raw address.
- Enhance `AddressNormalizer` in `vistarae_core` to strip leading unicode icon glyphs (`🖈`, `📍`, etc.) and resolve single sovereign country without conflicting strings.
- Add unit tests verifying regex glyph stripping and country deduplication.

### Phase 2: Secondary Scraping & Knowledge Enrichment (Tasks T-005 to T-008)
- Upgrade `WikipediaAdapter` in `secondary_sources.py` with 2-step OpenSearch fallback and hero image extraction (`originalimage.source`).
- Enhance `ScrapingOrchestrator` in `orchestrator.py` with category-scale visit duration heuristics (e.g. 2.5h for castles, 1-2 days for national parks).
- Ensure `routes/triage.py` falls back to standard vetted system tags when user tag list is empty.
- Add reverse-geocoding route `POST /api/v1/geocoding/reverse` for interactive map pin drops.

### Phase 3: Extension Parsers & Title Sanitization (Tasks T-009 to T-011)
- Add `sanitizeDestinationTitle` in `BasePoiParser.js` to strip platform branding suffixes (` - Google Maps`, ` | TripAdvisor`, etc.).
- Update `GoogleMapsParser.js` to clean destination title, extract coordinates from URL/DOM, and cleanse address text.
- Eliminate hardcoded `{ country: "United States" }` fallback in `content_script.js`.

### Phase 4: Capture Modal UI Controls & Verification (Tasks T-012 to T-016)
- Bundle Leaflet 1.9.4 in `extension/content/vendor/leaflet/` and declare in `manifest.json`.
- Embed interactive mini-map under coordinates in `content_script.js` with "Reselect Location" toggle supporting click-to-place and pin-dragging.
- Add "View ↗" verification buttons next to Official Website and Wikipedia URL fields (`window.open(..., '_blank')`).
- Add Hero Image preview card and interactive "Reload / Preview" button with client-side in-memory preflight probe.
- Implement progressive enrichment flow: immediate local values followed by asynchronous background field updates with loading indicators.

### Phase 5: Testing, Contract Validation & Polish (Tasks T-017 to T-020)
- Verify `openapi.json` and TypeScript types synchronization (`npx openapi-typescript`).
- Run backend unit and contract tests: `pytest --cov=services/poi --cov=packages/core --cov-fail-under=90`.
- Run extension unit tests: `npx vitest run ../extension/tests`.
- Run pre-commit checks (`ruff`, `prettier`, `check-copyright-header`).
