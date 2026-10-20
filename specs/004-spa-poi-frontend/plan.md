# Implementation Plan: Phase 4 — Single-Page Application (SPA) & Interactive POI Frontend

**Branch**: `004-spa-poi-frontend` | **Date**: 2026-10-20 | **Spec**: [specs/004-spa-poi-frontend/spec.md](file:///d:/Coding/Vistarae/specs/004-spa-poi-frontend/spec.md)  
**Input**: Feature specification from `specs/004-spa-poi-frontend/spec.md`  
**Constitution**: [.specify/memory/constitution.md](file:///d:/Coding/Vistarae/.specify/memory/constitution.md)

---

## 1. Summary

Phase 4 delivers the single-page application (SPA) under `frontend/` powered by Vite, React 18, and strict TypeScript. It features:
- A modular architecture consuming backend OpenAPI contracts via `npx openapi-typescript` (`src/types/api.ts`).
- An RFC 7807 / RFC 9457 `ProblemDetails` error boundary and toast notification system with `Retry-After` countdown banners.
- A Vanilla CSS design system with an instant (< 50ms) Theme Engine (`light`, `dark`, `system`) persisted to `user_preferences.ui.theme`.
- Full AWS Cognito authentication flows (Sign Up with verification code, Sign In, Forgot/Reset Password, Logout) and sub-domain preference management (Account/UI, POI Mode, Planner Mode).
- An interactive MapLibre GL JS map with 7 tile layers (Google Maps, OpenStreetMap, Satellite, Road, AutoNavi/Amap, Baidu).
- An in-browser Two-Way Coordinate Transform Module (`wgs84_to_gcj02`, `gcj02_to_wgs84`, `wgs84_to_bd09`, `bd09_to_wgs84`) executed strictly inside the China bounding box (`73.66°E–135.05°E`, `18.16°N–53.55°N`) using Newton's numerical iteration (< 0.000001° threshold) for sub-meter pin drops.
- Viewport debouncing (300ms) with client-side Supercluster (< 1,000 POIs) updating GeoJSON in-place via `map.getSource('pois').setData(...)` and bidirectional table synchronization.
- A client-only Photo EXIF Reader supporting JPEG, WebP, PNG, and HEIC/HEIF in browser memory with zero cloud egress and Blob URL cleanup.
- An Ingestion CSV modal with >2MB / >2,000 row split instructions, 2-second job polling, and duplicate triage persistence in IndexedDB (`vistarae_ingest_db`, store `triage_jobs`) with a 7-day TTL.
- An administrative governance dashboard (`/admin`) for user tier management, status toggles, and token budget metrics.

---

## 2. Technical Context

- **Language/Version**: TypeScript 5.5+ (`target: ES2022`), Node.js 20+
- **Primary Dependencies**: React 18 (`react`, `react-dom`), Vite 5 (`vite`, `@vitejs/plugin-react`), MapLibre GL JS (`maplibre-gl`), Supercluster (`supercluster`, `@types/supercluster`), ExifReader (`exifreader`), IndexedDB Wrapper (`idb`), OpenAPI TypeScript (`openapi-typescript`), Lucide React icons (`lucide-react`)
- **Storage**: Browser `IndexedDB` (`vistarae_ingest_db`, store `triage_jobs` with 7-day TTL), `localStorage` (theme mode, auth token, session overrides)
- **Testing**: Vitest (`vitest`), React Testing Library (`@testing-library/react`, `@testing-library/user-event`), jsdom (`jsdom`)
- **Target Platform**: Modern Evergreen Web Browsers (Chrome 110+, Firefox 110+, Safari 16+, Edge 110+)
- **Project Type**: Single-Page Web Application (SPA) with static build output (`frontend/dist`) deployable to Amazon S3 fronted by CloudFront
- **Performance Goals**:
  - First Contentful Paint (FCP): $< 1.2$ seconds
  - Time to Interactive (TTI): $< 2.0$ seconds
  - Theme toggle latency: $< 50$ milliseconds
  - Client-side clustering: 60 FPS ($< 16$ms render per frame) for collections $< 1,000$ POIs
  - Viewport motion debounce: single API request fired after $300$ms idle
  - Newton iteration coordinate resolution: $< 0.1$ms compute, sub-meter accuracy ($< 0.000001^\circ$)
- **Constraints**:
  - Zero cloud bandwidth/compute for photo metadata extraction (Zero-Cost Architecture)
  - Zero database writes on layer widget toggling (session-first with explicit default persistence)
  - Mandatory standardized copyright header banner (`// Copyright (c) 2026 Vistarae. All rights reserved.`) on every `.ts` and `.tsx` file
  - Strict RFC 7807 / RFC 9457 Problem Details error handling across all API responses
  - Strict OpenAPI type contract synchronization (`git diff --exit-code ./frontend/src/types/api.ts`)
- **Scale/Scope**: 50,000+ MAU, personal collections up to 10,000 POIs, CSV uploads up to 2,000 rows / 2MB.

---

## 3. Constitution Check

*GATE: Verified prior to research and re-evaluated post-design against `.specify/memory/constitution.md`.*

| Constitutional Invariant | Status | Compliance Detail |
| :--- | :---: | :--- |
| **1. File Header & Pre-Commit** | **PASS** | Every `.ts` and `.tsx` file starts with `// Copyright (c) 2026 Vistarae. All rights reserved.` and `SPDX-License-Identifier: Apache-2.0`. Pre-commit verifies `prettier` and `check-copyright-header`. Max nesting $\le 3$, cognitive complexity $\le 15$ (coordinate math exempted). |
| **2. Monorepo & Ports/Adapters** | **PASS** | `frontend/` isolated from backend python packages; communicates strictly via REST API over `/api` proxy. |
| **3. Database & Tenancy** | **PASS** | Frontend passes Cognito JWT bearer tokens. In local development (`STAGE == "local"`), passes `X-Mock-User-Id` and `X-Mock-User-Tier`. No direct database access from frontend. |
| **4. Alembic & Environment** | **PASS** | Frontend consumes existing backend migrations (`0001`, `0002`, `0003`). No new database migrations required for Phase 4. |
| **5. API Contract & Validation** | **PASS** | `./frontend/src/types/api.ts` generated directly from `./openapi.json` via `openapi-typescript`. CI checks `git diff --exit-code ./frontend/src/types/api.ts`. All error handling maps RFC 7807 `ProblemDetails`. |
| **6. Middleware & Security** | **PASS** | Local Vite proxy targets `http://localhost:8000` with CORS whitelisting `http://localhost:5173`. Mutating operations supply UUIDv4 `Idempotency-Key` headers. |
| **7. Observability & Tracing** | **PASS** | Frontend generates W3C `traceparent` headers (`00-{trace_id}-{span_id}-01`) and sets `X-Source: web-client`, `X-Destination: backend`. |
| **8. PyTest & SDD Governance** | **PASS** | Unit tests cover all coordinate transforms, EXIF extraction, and triage persistence. Implementation plan derived strictly from ratified `spec.md`. |
| **Operational & Infrastructure 1** | **PASS** | CSV uploads pre-validated client-side ($\le$ 2MB, $\le$ 2,000 rows). Oversized files present split instructions modal. Triage decisions persisted in IndexedDB with 7-day TTL matching SQS retention. |
| **Operational & Infrastructure 2** | **PASS** | Coordinate transformations (`wgs84_to_gcj02`, `gcj02_to_wgs84`) executed purely on client side if and only if inside China bounding box (`73.66°E–135.05°E`, `18.16°N–53.55°N`). Backend persists canonical WGS-84 exclusively. |
| **Operational & Infrastructure 3** | **PASS** | Static build output (`frontend/dist`) designed for private Amazon S3 bucket fronted by AWS CloudFront with Origin Access Control (OAC). Photo EXIF runs in-memory with zero AWS bandwidth. |

---

## 4. Project Structure

### 4.1 Documentation (Phase 4)

```text
specs/004-spa-poi-frontend/
├── spec.md              # Requirements and architecture specification
├── plan.md              # This implementation plan
├── research.md          # Architectural research & decisions
├── data-model.md        # Frontend entities, state machines & IndexedDB schemas
├── quickstart.md        # Step-by-step local verification & test scenarios
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── contracts/
    └── frontend-contracts.md # Module signatures, test vectors & HTTP protocols
```

### 4.2 Source Code Layout (`frontend/`)

```text
frontend/
├── index.html                       # HTML5 entrypoint with Google Fonts (Inter, Outfit)
├── package.json                     # Dependencies, scripts (dev, build, test, codegen)
├── tsconfig.json                    # Strict TypeScript configuration (ES2022)
├── vite.config.ts                   # Vite proxy: /api -> http://localhost:8000
├── src/
│   ├── main.tsx                     # Application bootstrap and root DOM mounting
│   ├── App.tsx                      # Root routes, Error Boundary, and Context Providers
│   ├── index.css                    # Design tokens, themes (light/dark), fluid typography
│   ├── types/
│   │   ├── api.ts                   # Authoritative OpenAPI types generated from openapi.json
│   │   ├── map.ts                   # POIMapFeature, BoundingBox, LayerConfig
│   │   └── triage.ts                # StagedTriageRecord, DecisionItem
│   ├── services/
│   │   ├── api.ts                   # Typed fetch client with W3C tracing & RFC 7807 interceptor
│   │   ├── auth.ts                  # Cognito auth service & local mock header injection
│   │   ├── triageStorage.ts         # IndexedDB store (vistarae_ingest_db) with 7-day TTL eviction
│   │   └── clustering.ts            # Supercluster client-side indexing & viewport filtering
│   ├── utils/
│   │   ├── coordinates.ts           # Two-way WGS-84 <-> GCJ-02/BD-09 Newton's method iteration
│   │   ├── exifReader.ts            # Client-only in-memory EXIF extraction & Blob URL lifecycle
│   │   └── formatters.ts            # Date, currency, duration, and rating formatters
│   ├── context/
│   │   ├── AuthContext.tsx          # User session, JWT tokens, login/logout state
│   │   ├── ThemeContext.tsx         # Light/dark/system theme management & DOM class toggling
│   │   ├── PreferencesContext.tsx   # Cached UI, POI, and Planner sub-domain preferences
│   │   └── ToastContext.tsx         # RFC 7807 ProblemDetails toast notifications
│   ├── components/
│   │   ├── common/
│   │   │   ├── ErrorBoundary.tsx    # Global React error boundary for uncaught exceptions
│   │   │   ├── ToastBanner.tsx      # ProblemDetails toast banner with Retry-After countdown
│   │   │   ├── Navbar.tsx           # Global header with theme toggle, nav links, profile menu
│   │   │   └── Modal.tsx            # Accessible modal container with backdrop
│   │   ├── map/
│   │   │   ├── MapView.tsx          # MapLibre GL JS canvas, viewport debouncing, marker rendering
│   │   │   ├── MapLayerSwitcher.tsx # 7-layer selector (OSM, Satellite, Road, Amap, Baidu)
│   │   │   └── POIPopupCard.tsx     # Rich inspection tooltip & quick action triggers
│   │   ├── poi/
│   │   │   ├── POITable.tsx         # Synchronized table with "Filter to viewport" toggle
│   │   │   ├── ManualAddPOIModal.tsx# Photo EXIF reader, geolocation, map pin pick
│   │   │   └── POIDetailDrawer.tsx  # In-place POI view & attribute editing
│   │   └── ingest/
│   │       ├── CSVUploadModal.tsx   # File drag/drop with >2MB / >2,000 row guardrails
│   │       ├── SplitModal.tsx       # Instructions modal for oversized CSVs
│   │       ├── CSVProgressModal.tsx # 2-second polling for active SQS ingestion jobs
│   │       └── CSVTriageModal.tsx   # Interactive duplicate review with IndexedDB persistence
│   └── pages/
│       ├── HomePage.tsx             # Main interactive dashboard (MapView + POITable)
│       ├── LoginPage.tsx            # Cognito email/password sign-in
│       ├── SignUpPage.tsx           # Registration and verification code entry
│       ├── ForgotPasswordPage.tsx   # Password reset request and confirmation
│       ├── ProfilePage.tsx          # User profile, metrics card, GDPR account deletion
│       ├── SettingsPage.tsx         # Tabbed preferences (Account/UI, POI, Planner)
│       ├── AdminDashboardPage.tsx   # Governance dashboard (user table, metrics, controls)
│       └── TermsPage.tsx            # Public Terms of Service
└── tests/
    ├── unit/
    │   ├── coordinates.test.ts      # Newton iteration precision & China bbox tests
    │   ├── exifReader.test.ts       # JPEG/HEIC metadata & Blob URL cleanup tests
    │   ├── triageStorage.test.ts    # IndexedDB persistence & TTL eviction tests
    │   └── api.test.ts              # RFC 7807 ProblemDetails mapping & traceparent tests
    └── components/
        ├── AuthAndPreferences.test.tsx # Cognito auth, settings tabs & theme persistence tests
        ├── MapView.test.tsx         # MapLibre layer swapping, 300ms debounce & table sync tests
        └── AdminDashboard.test.tsx  # Admin route guard, tier mutations & metrics tests
```

---

## 5. Complexity Tracking

No constitutional violations exist. All design decisions adhere strictly to:
- Principle 1 (Standardized copyright header `// Copyright (c) 2026 Vistarae. All rights reserved.`).
- Principle 5 (Synchronized TypeScript types via `openapi-typescript` and RFC 7807 Problem Details).
- Principle 6 (CORS whitelisting `http://localhost:5173` in local development).
- Operational Invariants 1 & 2 (Client-side China coordinate math, SQS ingestion limits, IndexedDB 7-day TTL).
- Operational Invariant 3 (Zero-Cost Architecture, in-memory EXIF parsing with zero cloud bandwidth).
