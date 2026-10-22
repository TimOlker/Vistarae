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

# Implementation Plan: Phase 8 — UI Main Page Enhancements (Space Management, Visual POI Filter Rules, Multi-Select Bulk Actions & Map Popups)

**Branch**: `008-ui-main-page-enhancements` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-ui-main-page-enhancements/spec.md`

---

## Summary

Phase 8 expands the main Vistarae discovery canvas into a high-density, interactive travel operations workspace. The technical architecture delivers four integrated pillars:

1. **Adaptive Space Management**: Segmented layout toggle (`split`, `map_only`, `table_only`) preserving active component state and selections, toggling CSS containers and triggering `map.resize()` in under 100ms with zero DOM unmounting.
2. **Visual Query Builder & Filter Rules Persistence**: Recursive Boolean AST query builder (`AND`/`OR`) with a hybrid execution engine (in-memory evaluation for $<1,000$ POIs; backend PostGIS translation for $\ge 1,000$ POIs) and PostgreSQL JSONB persistence via a dedicated tenant-isolated `filter_rules` table (`uq_filter_rules_user_name`). Includes custom table column ordering/sorting and dynamic SVG map pin coloring schemes (`uniform`, `rating`, `visit_status`, `custom`).
3. **Multi-Select Mode & Atomic Bulk Operations Engine**: Checkbox selection mode supporting up to 500 POIs per batch, executing rating assignment, visited date recording, return intent toggling, tag and list mutations, and safe primary-address updates (`addresses[0]` modification with secondary preservation) within a single atomic database transaction.
4. **MapLibre GL Cluster Navigation & Rich Popups**: Smooth camera easing (`fitBounds` in 300ms) on cluster expansion, max-zoom ($z \ge 20$) co-location spiderfication, and rich interactive pin preview popups (`POIPopupCard`) with instant entry into the `POIEditDrawer`.

---

## Technical Context

**Language/Version**: Python 3.12 (backend microservices & core domain package), TypeScript 5.5+ / React 18+ (frontend single page application)  
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2.10+, SQLAlchemy 2.0+ (asyncpg), Alembic, MapLibre GL 4+, Lucide React (UI icons)  
**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`geography(Point, 4326)`, GiST spatial indexing), JSONB columns on `filter_rules` and `pois`, GIN indexing on `addresses`  
**Testing**: pytest, pytest-cov, pytest-asyncio (enforcing strict $\ge 90\%$ branch and line coverage ceiling per Constitution Principle 8), Vitest / React Testing Library (frontend)  
**Target Platform**: AWS Lambda serverless execution (via Mangum / API Gateway HTTP APIs), Amazon S3 / CloudFront (frontend hosting), local development via Docker Compose & Uvicorn ASGI gateway  
**Project Type**: Monorepo Web Application (FastAPI backend microservices, shared `packages/core` workspace package, React SPA frontend)  
**Performance Goals**: Layout switching $<100$ms, in-memory filter evaluation $<200$ms for 5,000 POIs, rule persistence $<300$ms, bulk mutation (up to 500 POIs) $<1.5$s in a single transaction, cluster zoom easing $<300$ms  
**Constraints**: Zero PostgreSQL RLS (`WHERE user_id = :current_user_id` on all queries and mutations), Pydantic `extra="forbid"`, RFC 7807 `ProblemDetails` error formatting, max 500 records batch ceiling, English address normalization  
**Scale/Scope**: Hybrid filtering ($<1,000$ client in-memory vs. $\ge 1,000$ backend PostGIS AST), multi-address trans-boundary safety, session-only layout mode

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design._

| Principle / Rule                        | Compliance Status | Implementation Detail                                                                                                                                                                                         |
| :-------------------------------------- | :---------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ------- | --------- | ------------------------------------------------------------------- |
| **1. File Header & Docstrings**         | PASS              | All new `.py`, `.ts`, `.tsx`, and `.sql` files mandate Apache-2.0 copyright headers and Google-style docstrings with Cognitive Complexity $\le 15$.                                                           |
| **2. Ports & Adapters Architecture**    | PASS              | Domain entities (`FilterRuleEntity`), value objects (`FilterOperator`, `PinColorMode`), and schemas reside in `packages/core/vistarae_core/`. No infrastructure leakage into domain models.                   |
| **3. Tenancy Invariants (No RLS)**      | PASS              | All queries on `filter_rules` and `pois` enforce `WHERE user_id = :current_user_id`. Zero PostgreSQL Row-Level Security used.                                                                                 |
| **4. Alembic & Environment Isolation**  | PASS              | Migration `0006_filter_rules.py` provides fully reversible `downgrade()` dropping `filter_rules` and its unique constraint. Zero native PostgreSQL enum types.                                                |
| **5. API Contracts & Pydantic v2**      | PASS              | OpenAPI 3.1 contract documented in [contracts/main-page-api.yaml](./contracts/main-page-api.yaml). All schemas subclass `StrictBaseModel` with `extra="forbid"`. All errors return RFC 7807 `ProblemDetails`. |
| **6. Middleware & Security Guardrails** | PASS              | Security headers, CORS, and W3C distributed tracing context extracted and propagated across all endpoints.                                                                                                    |
| **7. Observability & Tracing**          | PASS              | Cross-boundary directional tags (`MSG ->                                                                                                                                                                      | `, `MSG <- | `, `MSG | ->`, `MSG | <-`) and W3C `traceparent` headers supported across all new routes. |
| **8. PyTest Governance (90% Coverage)** | PASS              | Unit tests mirrored 1:1 in `tests/unit/services/poi/` and `tests/unit/packages/core/` with `--cov-fail-under=90`.                                                                                             |

---

## Project Structure

### Documentation (this feature)

```text
specs/008-ui-main-page-enhancements/
├── spec.md              # Feature specification with strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 architectural & technical decisions
├── data-model.md        # Phase 1 database schema, domain entities & schemas
├── quickstart.md        # Phase 1 runnable end-to-end validation scenarios
├── contracts/           # Phase 1 OpenAPI 3.1 specification
│   └── main-page-api.yaml
├── checklists/
│   └── requirements.md  # Specification quality checklist (16/16 passing)
└── tasks.md             # Phase 2 task checklist (generated by /speckit-tasks)
```

### Source Code Impact (repository root)

```text
packages/core/vistarae_core/
├── domain/
│   ├── entities.py              # FilterRuleEntity aggregate
│   └── value_objects.py         # FilterOperator, FilterConjunction, PinColorMode, SortDirection
├── schemas/
│   ├── filter_rule.py           # FilterRuleCreateRequest, FilterRuleUpdateRequest, FilterRuleResponse, QueryTreeSchema
│   └── poi.py                   # BulkEditRequest, BulkOperationResponse, BulkDeleteRequest, BulkDeleteResponse (500 max)
├── adapters/db/
│   └── tables.py                # FilterRuleTable definition with uq_filter_rules_user_name
└── ports/
    └── repositories.py          # IFilterRuleRepository port interface and IPOIRepository bulk extensions

services/poi/
├── routes/
│   ├── filter_rules.py          # CRUD endpoints: GET, POST, PUT, DELETE /api/pois/filter-rules
│   ├── bulk.py                  # POST /api/pois/bulk-edit, POST /api/pois/bulk-delete (500 ceiling)
│   └── pois.py                  # POST /api/pois/query (hybrid filter evaluation endpoint)
├── repositories/
│   ├── filter_rule_repository.py# SQLAlchemy 2.0 async repository for FilterRuleTable
│   └── poi_repository.py        # Atomic bulk mutations (addresses[0] targeting) and AST filter compiler
└── services/
    └── filter_evaluator.py      # SQLAlchemy AST query compiler (translates QueryTree AST to SQL predicates)

db/migrations/versions/
└── 0006_filter_rules.py         # Alembic migration creating filter_rules table with reversible downgrade

frontend/src/
├── types/
│   ├── layout.ts                # LayoutMode ('split' | 'map_only' | 'table_only')
│   ├── filter.ts                # QueryGroup, RuleClause, TableConfig, PinColorScheme, FilterRule
│   └── bulk.ts                  # BulkEditAction, BulkEditPayload
├── components/
│   ├── layout/
│   │   └── ViewModeControl.tsx  # Segmented layout mode control ('split', 'map_only', 'table_only')
│   ├── filter/
│   │   ├── FilterBar.tsx        # Collapsible filter container with active summary & actions
│   │   ├── QueryBuilder.tsx     # Recursive visual query builder for AND/OR condition trees
│   │   ├── SavedRuleSelector.tsx# Dropdown for loading, saving, saving as, and deleting rules
│   │   ├── ColumnConfigModal.tsx# Column selection, ordering, and sort direction manager
│   │   └── PinColorSchemeModal.tsx# Dynamic map pin coloring scheme editor
│   ├── bulk/
│   │   ├── BulkActionsToolbar.tsx# Multi-select action bar with selection count and trigger menus
│   │   └── BulkOperationsModal.tsx# Atomic bulk mutation dialog (rating, dates, tags, lists, address)
│   ├── map/
│   │   ├── MapView.tsx          # Cluster bounding-box easing (fitBounds), max-zoom spiderfication
│   │   └── POIPopupCard.tsx     # Rich anchored pin preview card with 'Edit POI' drawer launcher
│   └── poi/
│       └── POITable.tsx         # Multi-select row checkboxes, master header toggle, dynamic columns & sorting
└── pages/
    └── HomePage.tsx             # Main canvas layout orchestration, hybrid filter evaluation, selection state
```

---

## Complexity Tracking

_No Constitution violations detected. All additions follow established repository patterns, pure async SQLAlchemy 2.0, ports/adapters separation, and strict Pydantic v2 models._
