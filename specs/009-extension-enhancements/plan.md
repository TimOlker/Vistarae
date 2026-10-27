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

# Implementation Plan: Phase 9 — Extension Enhancements & Web App Tag Management (Tag Governance, Rich Web Scraping & Multi-Source Augmentation, Duplicate Triage)

**Branch**: `009-extension-enhancements` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-extension-enhancements/spec.md`

---

## Summary

Phase 9 establishes an integrated, high-integrity travel capture companion connecting the Vistarae Manifest V3 Chrome Extension, core FastAPI backend, and React Single Page Application. The technical implementation delivers four architectural cornerstones:

1. **User-Scoped Tag Governance & Referential Integrity**:
   - Updates the database schema (`tags` table) to store immutable slugified identifiers (`slug`) with display names and search alias arrays (`aliases`).
   - Seeding 30 standardized travel tags on user registration while enabling users to customize and add tags in alphabetical order on the Preferences page (`/settings`).
   - Hard-blocking tag deletion (RFC 7807 409 Conflict) whenever referenced by active POIs, paired with an interactive remediation link pre-filtering the POI table for bulk tag unassignment.
2. **Extension Streamlining & Informational Landing Page**:
   - Purges redundant UI elements from `browser.html` (CSV export button, POI table, search toolbar, category dropdowns) and eliminates all fake placeholder mock destinations (`Glacier Point Overlook`, `Mist Trail`).
   - Replaces the extension browser tab with an educational overview detailing Vistarae's capture workflow, keystroke shortcuts (`Ctrl+Shift+S` / `Cmd+Shift+S`), server health, user email badge, and direct navigation to the Web App.
3. **Pre-Capture Authentication Gate & 1:1 Schema Parity**:
   - Enforces token verification prior to initiating capture keystrokes, redirecting unauthenticated users to the Web App login page.
   - Synchronizes capture overlay inputs 1:1 with the database and Web App POI Editor (Standardized English name, tight summary description, multi-address list, lat/long, official URL, Wikipedia URL, hero image, estimated hours/days, user star rating, and vetted tags; excluding local photo folders).
4. **Multi-Source Scraping Orchestrator & Scale-Aware Duplicate Triage**:
   - Coordinates primary page extraction, English name standardization, and authorized secondary source augmentation (`wikipedia.org`, `tripadvisor.com`, etc.) configured via `user_preferences.valid_scraping_domains`.
   - Incorporates a 3.0-second timeout ceiling with graceful partial fallback if secondary sources stall or rate-limit.
   - Enforces Nominatim rate limiting (1 req/sec max with custom User-Agent) fronted by PostGIS `geocoding_cache` SHA-256 query hashing.
   - Implements a dual-threshold heuristic distinguishing exact duplicates (`POTENTIAL_DUPLICATE`: distance $\le$ scale radius AND similarity $\ge 0.60$) from parent-child candidates (`NEARBY_PARENT`: distance $\le$ scale radius AND similarity $< 0.60$ with larger scale candidate), offering a 3-way triage modal (Proceed, Make Child, Abort).

---

## Technical Context

**Language/Version**: Python 3.12 (backend microservices & core domain package), TypeScript 5.5+ / React 18+ (web app single-page application), Vanilla JavaScript ES2022 (Manifest V3 Chrome Extension)  
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2.10+, SQLAlchemy 2.0+ (asyncpg), Alembic, `google-genai` SDK (Gemini 2.0 Flash-Lite, `thinking_budget = 0`), Lucide React (frontend icons)  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`geography(Point, 4326)`), PostGIS `geocoding_cache` (SHA-256 query hash), JSONB arrays on `tags.aliases` and `user_preferences.valid_scraping_domains`  
**Testing**: pytest, pytest-cov, pytest-asyncio (enforcing strict $\ge 90\%$ branch and line coverage ceiling per Constitution Principle 8), Vitest / React Testing Library (frontend)  
**Target Platform**: AWS Lambda serverless execution (via Mangum / API Gateway HTTP APIs), Amazon S3 / CloudFront (frontend hosting), Chrome / Chromium Manifest V3 browser extension, local development via Docker Compose & Uvicorn ASGI gateway  
**Project Type**: Monorepo Web Application & Chrome Extension (FastAPI microservices, shared `packages/core` workspace package, React SPA frontend, Manifest V3 extension)  
**Performance Goals**: Overlay injection $<400$ms upon `Ctrl+Shift+S`, multi-source scraping & summary synthesis $<2.5$s, duplicate/nesting check $<500$ms, tag listing & preference retrieval $<150$ms  
**Constraints**: Zero PostgreSQL RLS (`WHERE user_id = :current_user_id` on all queries and mutations), Pydantic `extra="forbid"`, RFC 7807 `ProblemDetails` error formatting, Nominatim 1 req/sec rate limit with custom User-Agent, English standardized country names (ISO 3166-1)  
**Scale/Scope**: 30 seeded default tags per user, up to 100 custom tags per user, scale-adjusted radii (Macro: 5,000m; Medium: 500m; Micro: 50m), graceful 3.0s fallback on secondary sources

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle / Rule                        | Compliance Status | Implementation Detail                                                                                                                                                                                                                   |
| :-------------------------------------- | :---------------: | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. File Header & Docstrings**         |       PASS        | All new `.py`, `.ts`, `.tsx`, and `.sql` files mandate Apache-2.0 copyright headers and Google-style docstrings with Cognitive Complexity $\le 15$.                                                                                     |
| **2. Ports & Adapters Architecture**    |       PASS        | Domain entities (`UserTagEntity`), value objects (`TagSlug`, `SpatialScale`), and schemas reside in `packages/core/vistarae_core/`. No infrastructure leakage into domain models.                                                       |
| **3. Tenancy Invariants (No RLS)**      |       PASS        | All queries on `tags`, `user_preferences`, and `pois` enforce `WHERE user_id = :current_user_id`. Zero PostgreSQL Row-Level Security used.                                                                                              |
| **4. Alembic & Environment Isolation**  |       PASS        | Migration `0007_tag_governance_and_scraping_preferences.py` provides fully reversible `downgrade()` dropping added columns and constraints. Zero native PostgreSQL enum types.                                                          |
| **5. API Contracts & Pydantic v2**      |       PASS        | OpenAPI 3.1 contract documented in [contracts/extension-enhancements-api.yaml](./contracts/extension-enhancements-api.yaml). All schemas subclass `StrictBaseModel` with `extra="forbid"`. All errors return RFC 7807 `ProblemDetails`. |
| **6. Middleware & Security Guardrails** |       PASS        | Extension origin whitelisted in `CORSMiddleware`. Idempotency and rate-limiting middleware configured.                                                                                                                                  |
| **7. Observability & Tracing**          |       PASS        | Cross-boundary directional tags (`MSG ->\|`, `MSG <-\|`, `MSG \|->`, `MSG \|<-`) and W3C `traceparent` headers supported across all new extension routes.                                                                               |
| **8. PyTest Governance (90% Coverage)** |       PASS        | Unit tests mirrored 1:1 in `tests/unit/services/poi/` and `tests/unit/packages/core/` with `--cov-fail-under=90`.                                                                                                                       |

---

## Project Structure

### Documentation (this feature)

```text
specs/009-extension-enhancements/
├── spec.md              # Feature specification with strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 architectural & technical decisions
├── data-model.md        # Phase 1 database schema, domain entities & schemas
├── quickstart.md        # Phase 1 runnable end-to-end validation scenarios
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── extension-enhancements-api.yaml
├── checklists/
│   └── requirements.md  # Specification quality checklist (16/16 passing)
└── tasks.md             # Phase 2 task checklist (generated by /speckit-tasks)
```

### Source Code Impact (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py              # UserTagEntity, ScrapingPreferencesEntity
│   └── value_objects.py         # TagSlug, SpatialScale, DeduplicationStatus
├── schemas/
│   ├── tag.py                   # TagCreateRequest, TagResponse, TagInUseProblemDetails
│   ├── scraping.py              # ScrapingSourcesResponse, ScrapingSourcesUpdateRequest
│   └── poi.py                   # POIExtractionPayload, DeduplicationVerdictSchema
├── adapters/db/
│   └── tables.py                # Updated TagTable (slug, aliases) and UserPreferencesTable (valid_scraping_domains)
└── ports/
    └── repositories.py          # ITagRepository, IUserPreferencesRepository, IScrapingSourceRepository

services/poi/
├── routes/
│   ├── tags.py                  # GET /api/pois/tags, POST /api/pois/tags, DELETE /api/pois/tags/{tag_id}
│   ├── preferences.py           # GET/PUT /api/user/preferences/scraping-sources
│   └── triage.py                # Enhanced POST /api/pois/extract-and-check
├── scraping/
│   ├── orchestrator.py          # ScrapingOrchestrator, timeout handling, Gemini synthesis
│   ├── secondary_sources.py     # WikipediaAdapter, TripAdvisorAdapter
│   └── scale_classifier.py      # Spatial scale heuristic classifier (Macro/Medium/Micro)
└── repositories/
    └── tag_repository.py        # TagRepository implementation with referential checks

frontend/src/
├── pages/
│   └── SettingsPage.tsx         # Tags management tab and Scraping Sources configuration
├── components/tags/
│   ├── TagManager.tsx           # Alphabetical tag list, add modal, delete guard modal
│   └── TagListItem.tsx          # Tag row with display name, slug, aliases, and action buttons
└── components/poi/
    └── POIEditDrawer.tsx        # Vetted tag selector integration

extension/
├── manifest.json                # Permission updates and host permissions
├── background/
│   ├── service_worker.js        # Auth gate on capture shortcut, multi-source extraction dispatch
│   └── auth.js                  # Stored token verification and redirect helpers
├── browser/
│   ├── browser.html             # Streamlined informational companion page (no table/CSV)
│   ├── browser.js               # Companion page controller without mock demo records
│   └── browser.css              # Branded companion styling
└── content/
    ├── content_script.js        # Synchronized form inputs, 3-way triage modal (Proceed, Make Child, Abort)
    └── overlay.css              # Overlay styling matching web app editor
```

---

## Complexity Tracking

> **No constitutional violations detected.** All components adhere strictly to ports/adapters isolation, tenant isolation (`WHERE user_id = :current_user_id`), Pydantic v2 `extra="forbid"`, and PyTest 90% coverage enforcement.
