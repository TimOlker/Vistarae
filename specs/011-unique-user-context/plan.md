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

# Implementation Plan: Phase 11 — Unique User Context (Personalized LLM Prompt Extensions & "Reason to Visit" POI Enrichment)

**Branch**: `011-unique-user-context` | **Date**: 2026-10-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-unique-user-context/spec.md`

---

## Summary

Phase 11 implements **Unique User Context** across Vistarae, providing personalized AI extraction and enriched POI knowledge:
1. **POI Schema Parity & Search**: Adds a multiline `reason_to_visit` field to the POI record, positioned immediately after `description` across the Web App (Edit Drawer, Manual Add Modal, Detail Drawer) and Chrome Extension review overlay. Expands full-text and trigram search to evaluate both `description` and `reason_to_visit`.
2. **Traveler Travel Style & AI Prompt Decomposition**: Adds a travel style text input to the Web App User Profile (`/profile`). When saved, Google Gemini Flash-Lite (`thinking_budget = 0`) decomposes the narrative into modular prompt directives (`description`, `reason_to_visit`, `time_spent`), which are persisted in a `user_prompts` table and rendered as read-only cards on the profile.
3. **In-Memory Caching**: Caches user prompt directives in process memory with TTL and immediate tenant eviction on profile mutation, ensuring sub-2ms prompt resolution during captures without external Redis/DynamoDB costs.
4. **Universal Ingestion Enrichment**: Dynamically augments base prompts with the active traveler's directives during Chrome Extension web scraping, Web App manual import, and batch CSV ingestion.
5. **Onboarding & Migration Login Redirection**: Detects unpopulated travel styles upon user login (new users or legacy accounts) and displays an informative modal popup that redirects the user directly to `/profile` to complete their travel style configuration. In contrast, Chrome Extension capture for unconfigured travelers silently uses standard base prompts without modal interruptions.

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.5+ (frontend, extension)  
**Primary Dependencies**:
- Backend: FastAPI 0.111+, SQLAlchemy 2.0 (pure async with `asyncpg`), Pydantic v2 (`StrictBaseModel`), Google GenAI SDK (`google-genai` Flash-Lite, `thinking_budget = 0`), Alembic
- Frontend: React 18, Vite 5, Lucide React
- Extension: Pure Vanilla JS / Chrome Manifest V3 with Shadow DOM
**Storage**: PostgreSQL 16+ / PostGIS 3.4+ (`pois` table with `reason_to_visit`, `user_prompts` table, `user_preferences` table with `travel_style_description`), process-level in-memory cache for prompt directives  
**Testing**: pytest with pytest-asyncio and pytest-cov ($\ge 90\%$ branch/line coverage threshold), Vitest for frontend components  
**Target Platform**: AWS Lambda (serverless Mangum ASGI entrypoint), Linux server, Modern Chromium browsers (Extension MV3), Evergreen Web Browsers (Vite SPA)  
**Project Type**: Monorepo with Ports & Adapters architecture (`packages/core/`, `services/user/`, `services/poi/`, `services/ingest/`, `services/worker/`, `frontend/`, `extension/`)  
**Performance Goals**: Prompt decomposition < 4.0s end-to-end, in-memory cache resolution < 2ms (99th percentile), POI capture extraction < 3.0s ceiling  
**Constraints**:
- Zero-cost AWS free tier architecture (no external paid caching like Redis/ElastiCache/DynamoDB)
- Strictly adhere to OSM Nominatim rate limits (1 req/sec max) and local SHA-256 geocache
- Strict tenant isolation via `WHERE user_id = :current_user_id` (no PostgreSQL RLS)
- Zero thinking budget (`thinking_budget = 0`) on all Gemini extraction calls
**Scale/Scope**: 10,000+ POIs per user, multi-source enrichment across authorized domains, batch CSV parsing up to 2,000 rows / 2MB  

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle | Requirement Summary | Status | Compliance Verification |
| :--- | :--- | :--- | :--- |
| **1. File Header & Docstrings** | Standard Apache 2.0 copyright banner on all `.py`, `.ts`, `.tsx`, `.sql`. Max nesting 3, Cognitive Complexity $\le 15$. | **PASS** | Every new/modified file includes exact copyright header, Google-style docstrings, and guard-clause structure. |
| **2. Ports & Adapters Architecture** | Domain models isolated in `packages/core`. Pure domain decoupled from `boto3`, HTTP, and framework internals. | **PASS** | New entities (`UserPrompt`, `PromptType`) and value objects isolated in `packages/core/vistarae_core`. Repositories defined via Python protocols. |
| **3. Database & Tenancy** | Pure Async SQLAlchemy 2.0 (`asyncpg`). NullPool in cloud, QueuePool in local. `statement_cache_size=0`. No RLS. `WHERE user_id = :current_user_id`. `users(id) ON DELETE CASCADE`. | **PASS** | Table `user_prompts` references `users(id)` with cascade delete. Repository applies tenant filter. No PostgreSQL RLS used. |
| **4. Alembic & Environment Isolation** | Schema migrations in `db/migrations/`. Reversible `downgrade()`. Status/category fields typed with Python `StrEnum` backed by `VARCHAR(n)` (no native DB ENUMs). | **PASS** | Migration creates `user_prompts` and adds `reason_to_visit` and `travel_style_description`. `PromptType` uses `StrEnum` + `VARCHAR(32)`. Fully reversible. |
| **5. API Contract & Validation** | OpenAPI 3.1 authoritative contract. TypeScript types synced via `npx openapi-typescript`. Pydantic v2 `StrictBaseModel` (extra='forbid', str_strip_whitespace=True). RFC 7807 ProblemDetails for errors. | **PASS** | Contracts defined in `contracts/user-context-api.yaml`. Boundary schemas inherit from `StrictBaseModel`. ProblemDetails error responses implemented. |
| **6. Middleware & Security** | Idempotency first, RateLimit second. CORS restricted. Sensitive tokens excluded from logs. | **PASS** | Middleware order preserved. Travel style prompts validated against prompt injection via XML delimiters. |
| **7. Observability & Tracing** | Directional `MSG` logging markers (`MSG: -->|`, `MSG: <--|`, etc.) in local dev. Structured JSON in cloud. W3C `traceparent` propagation. | **PASS** | Directional messaging tags applied to Gemini synthesizer and user context routes. Tracing context propagated across services. |
| **8. PyTest & SDD Governance** | Minimum 90% branch and line coverage. Mirror source tree in `tests/unit/`. Spec governs as absolute truth. Strict YAGNI. | **PASS** | Dedicated unit test suites structured to mirror source tree with $\ge 90\%$ coverage target. |
| **Operational Guardrails** | Zero-Cost Architecture (Neon tables, in-memory caching, no paid Redis/DynamoDB). SQS long-polling, 1 req/sec geocache policy. | **PASS** | In-memory process cache uses standard Python dictionary/LRU with thread-safe TTL. No external cloud dependencies introduced. |

---

## Project Structure

### Documentation (this feature)

```text
specs/011-unique-user-context/
├── spec.md                  # Approved specification in strict EARS syntax
├── plan.md                  # This implementation plan
├── research.md              # Phase 0 technical decisions matrix
├── data-model.md            # Phase 1 domain entities, schema, and lifecycle
├── quickstart.md            # Phase 1 verification and runnable scenarios guide
├── checklists/
│   └── requirements.md      # Specification quality validation checklist
├── contracts/
│   └── user-context-api.yaml # OpenAPI 3.1 specification for user context & POI API
└── tasks.md                 # Phase 2 implementation task breakdown (speckit-tasks)
```

### Source Code (repository root)

```text
packages/core/vistarae_core/
├── adapters/
│   ├── db/
│   │   └── tables.py                       # UserPromptTable, POITable (reason_to_visit), UserPreferencesTable
│   └── repositories/
│       ├── poi_repo.py                     # list_pois search updated with reason_to_visit & description
│       └── user_prompt_repo.py             # SqlAlchemyUserPromptRepository implementation
├── domain/
│   ├── entities.py                         # UserPrompt entity, POI entity updated with reason_to_visit
│   └── value_objects.py                    # PromptType StrEnum
├── ports/
│   └── repositories.py                     # IUserPromptRepository protocol
├── schemas/
│   ├── poi.py                              # POIResponse, POICreateRequest, POIUpdateRequest
│   ├── scraping.py                         # POICandidateSchema (reason_to_visit)
│   └── user.py                             # TravelStyleUpdateRequest, TravelStyleResponse, UserPromptItem
└── services/
    └── prompt_cache.py                     # Thread-safe in-memory UserPromptCache with TTL & eviction

services/user/
├── routes/
│   └── profile.py                          # PUT/GET/DELETE /api/user/profile/travel-style
└── services/
    └── prompt_synthesizer.py               # UserPromptSynthesizer using Gemini Flash-Lite (thinking_budget = 0)

services/poi/
├── routes/
│   ├── pois.py                             # POI endpoints with reason_to_visit
│   └── triage.py                           # Personalized extract-and-check endpoint
└── scraping/
    └── orchestrator.py                     # ScrapingOrchestrator injecting personalized prompt extensions

services/ingest/
└── services/
    └── csv_parser.py                       # CSV parsing and row mapping with reason_to_visit

services/worker/
└── processor.py                            # SQS ingestion worker applying prompt extensions

frontend/
├── src/
│   ├── components/
│   │   ├── poi/
│   │   │   ├── ManualAddPOIModal.tsx       # Reason to Visit multiline textarea
│   │   │   ├── POIDetailDrawer.tsx         # Why Visit section card
│   │   │   ├── POIEditDrawer.tsx           # Reason to Visit multiline textarea below Description
│   │   │   └── POITable.tsx                # Reason to Visit column and unified table search
│   │   └── profile/
│   │       └── TravelStyleOnboardingModal.tsx # Login onboarding popup for unpopulated travel style
│   ├── context/
│   │   └── AuthContext.tsx                 # Post-login evaluation of travel_style_description
│   ├── pages/
│   │   └── ProfilePage.tsx                 # Travel Style & Preferences card + read-only prompt cards
│   └── types/
│       └── api.ts                          # Regenerated TypeScript contracts

extension/
├── content/
│   ├── content_script.js                   # Shadow DOM capture overlay with Reason to Visit textarea
│   └── overlay.css                         # Layout and styling for Reason to Visit input
└── browser/
    └── browser.js                          # Extension companion UI updates
```

**Structure Decision**: The monorepo architecture strictly isolates domain entities and database tables within `packages/core/vistarae_core`. Backend microservices consume shared core packages, while the frontend SPA and Chrome Extension maintain 1:1 schema parity via generated OpenAPI TypeScript contracts.

---

## Complexity Tracking

> **Constitution Check: 0 Violations. All architectural choices strictly adhere to constitutional invariants.**

| Area | Decision | Constitution Justification |
| :--- | :--- | :--- |
| **Cache Architecture** | In-process memory cache with TTL & eviction | Avoids paid Redis/DynamoDB clusters, satisfying Zero-Cost Architecture & AWS Free-Tier Guardrails. |
| **Enum Modeling** | Python `StrEnum` + `VARCHAR(32)` | Adheres to Constitution Principle 4 (strictly avoiding native PostgreSQL database ENUMs). |
| **AI Synthesis** | Gemini Flash-Lite with `thinking_budget = 0` | Adheres to Constitution Core Rules & Invariants for deterministic, low-latency, zero-overhead extraction. |
