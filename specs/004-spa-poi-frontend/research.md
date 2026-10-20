# Research & Architectural Decisions: Phase 4 — Single-Page Application (SPA) & Interactive POI Frontend

**Feature Identifier**: `004-spa-poi-frontend`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/004-spa-poi-frontend/spec.md](file:///d:/Coding/Vistarae/specs/004-spa-poi-frontend/spec.md)  
**Constitution Reference**: [.specify/memory/constitution.md](file:///d:/Coding/Vistarae/.specify/memory/constitution.md)

---

## 1. Executive Research Summary

Phase 4 introduces the traveler-facing frontend for Vistarae. The technical stack and architectural decisions must strictly comply with project constitutional principles (Zero-Cost Architecture, RFC 7807 Problem Details, pure client-side coordinate transformations, and OpenAPI contract synchronization) while providing an ultra-responsive, visually stunning user experience.

---

## 2. Topic 1: SPA Foundation, Tooling & Build Toolchain

### 2.1 Decision: Vite 5 + React 18 + Strict TypeScript
- **Decision**: Initialize the frontend under `frontend/` using Vite 5, React 18, and TypeScript 5.5+ in strict mode.
- **Rationale**:
  - Vite provides lightning-fast Hot Module Replacement (HMR) and an integrated HTTP development proxy (`/api` -> `http://localhost:8000`).
  - React 18 provides robust ecosystem alignment with MapLibre GL JS, Supercluster, and IndexedDB libraries without introducing heavy framework overhead.
  - Zero-config static output (`frontend/dist/`) aligns directly with AWS CloudFront + private S3 deployment using Origin Access Control (OAC) per Constitution Invariant 3.
- **Alternatives Considered**:
  - *Next.js / SSR*: Rejected due to unnecessary server compute, cold starts on serverless hosting, and violation of the pure static S3/CloudFront zero-cost hosting invariant.
  - *Vanilla JS without components*: Rejected due to state complexity across map-table synchronization, modal dialogs, and multi-tab preferences.

### 2.2 Decision: Vanilla CSS Design System with CSS Custom Properties
- **Decision**: Implement a bespoke Vanilla CSS design system anchored in modern CSS custom properties (`--bg-primary`, `--bg-surface`, `--text-primary`, `--accent`, `--border-color`), fluid typography (Inter & Outfit Google Fonts), glassmorphism, and micro-animations.
- **Rationale**:
  - Provides instantaneous (< 50ms) theme toggling (`light`, `dark`, `system`) by simply updating the `data-theme` attribute on `document.documentElement` without runtime CSS re-computation.
  - Avoids heavy runtime CSS-in-JS dependencies (e.g. styled-components) that degrade First Contentful Paint.
  - Avoids TailwindCSS build churn unless explicitly requested.
- **Alternatives Considered**:
  - *TailwindCSS*: Rejected per project web guidelines (Vanilla CSS preferred for maximum design control and aesthetic distinction).

### 2.3 Decision: Automated OpenAPI Contract Type Generation
- **Decision**: Integrate `openapi-typescript` into `npm run codegen` targeting `./openapi.json` to generate `./frontend/src/types/api.ts`.
- **Rationale**:
  - Constitution Principle 5 mandates: `npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts` and enforces `git diff --exit-code ./frontend/src/types/api.ts` in CI pull requests.
  - Provides end-to-end compile-time type safety across all backend schemas (`POIResponse`, `UserPreferencesResponse`, `ProblemDetails`, `IngestJobProgressResponse`).
- **Alternatives Considered**:
  - *Manual TypeScript interfaces*: Rejected due to contract drift risk and CI failure under Constitution Principle 5.

### 2.4 Decision: RFC 7807 / RFC 9457 Global Error Boundary & Toast Mapper
- **Decision**: Implement a centralized `apiClient` fetch wrapper that automatically intercepts non-2XX responses, parses `application/problem+json`, and passes a strongly typed `ProblemDetails` object to an app-level Toast notification system and Error Boundary.
- **Rationale**:
  - Constitution Principle 5 mandates that all service errors return RFC 7807 JSON (`type`, `title`, `status`, `detail`, `instance`, `invalid_params`).
  - For HTTP 429 Too Many Requests, the client extracts the `Retry-After` header and renders a real-time countdown banner.
  - Parameter validation errors (`invalid_params`) automatically highlight relevant form inputs in modal dialogs.
- **Alternatives Considered**:
  - *Generic alert() popups*: Rejected as substandard UX and violating REQ-UI-004.

---

## 3. Topic 2: Interactive Geospatial Mapping, Tile Sets & Client Clustering

### 3.1 Decision: MapLibre GL JS for Core Vector & Raster Rendering
- **Decision**: Use MapLibre GL JS (v4.x) as the primary map rendering engine.
- **Rationale**:
  - Open-source, fork of Mapbox GL with zero proprietary telemetry, zero commercial licensing fees, and full WebGL2 rendering performance.
  - Native support for dynamic vector styling, raster tile sources, GeoJSON clustering layers, pitch/bearing manipulation, and high-DPI retina display.
  - Smooth tile provider swapping without destroying canvas state or resetting viewport position.
- **Alternatives Considered**:
  - *Leaflet*: Good for basic 2D maps, but lacks WebGL hardware acceleration, dynamic GeoJSON vector clustering performance at 60 FPS, and pitch/rotation capabilities.
  - *Mapbox GL JS v2/v3*: Proprietary pricing model per map load violates Zero-Cost Architecture.

### 3.2 Decision: Supported Map Tile Providers & Layer Switching
- **Decision**: Support 7 standard tile configurations via MapLibre style sources:
  1. `osm`: OpenStreetMap standard raster tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`).
  2. `satellite`: Esri World Imagery raster tiles (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`).
  3. `google-roadmap`: Google Maps raster/vector roadmap.
  4. `google-hybrid`: Google Maps satellite imagery with road/label overlays.
  5. `road`: CartoDB Positron / OSM Road clean vector/raster tiles.
  6. `amap`: AutoNavi / Amap shifted tile set (`https://wprd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7`).
  7. `baidu`: Baidu Maps tile service with BD-09 projection.
- **Rationale**:
  - Provides travelers with versatile coverage ranging from open-source terrain to commercial satellite detail and authorized Chinese navigation.

### 3.3 Decision: Viewport Debouncing (300ms) vs. Client Supercluster (< 1,000 POIs)
- **Decision**: Implement dual-mode spatial query routing based on user POI volume:
  - **Mode A (Small Collections: Total POIs < 1,000)**: Fetch entire POI collection once on initial load (`/api/pois?limit=1000`). Index in-memory using `supercluster`. On map pan/zoom, query clusters directly from memory (`supercluster.getClusters(bbox, zoom)`) and update `map.getSource('pois').setData(...)`. Zero network requests during map exploration.
  - **Mode B (Large Collections: Total POIs >= 1,000)**: Debounce map `moveend` event by 300ms. Dispatch `GET /api/pois?bbox={minLng,minLat,maxLng,maxLat}` to fetch visible features from the PostGIS spatial engine.
- **Rationale**:
  - 95%+ of personal travel collections contain fewer than 500 POIs. Mode A completely eliminates backend server load, database queries, and network latency, delivering 60 FPS clustering.
  - Mode B cleanly scales to power users with 10,000+ points without crashing browser memory.

### 3.4 Decision: Bidirectional Map-Table Synchronization
- **Decision**: Maintain a synchronized state between the map canvas and tabular list.
  - When the "Filter table to current map viewport" switch is toggled, table data is filtered via spatial bounds check against `map.getBounds()`.
  - Clicking a table row triggers `map.flyTo({ center: [lng, lat], zoom: 15, essential: true })` and activates the POI popup card.
  - Clicking a map marker highlights and scrolls the corresponding row into view in the table.

---

## 4. Topic 3: Two-Way Coordinate Transformation (WGS-84 $\leftrightarrow$ GCJ-02/BD-09)

### 4.1 Decision: Mathematical Specification & Bounds Guard
- **Decision**: Implement pure client-side mathematical projection module `packages/frontend/src/utils/coordinates.ts` implementing `wgs84_to_gcj02`, `gcj02_to_wgs84`, `wgs84_to_bd09`, and `bd09_to_gcj02`.
- **China Geographic Bounding Box**:
  $$\text{lng} \in [73.66^\circ\text{E}, 135.05^\circ\text{E}], \quad \text{lat} \in [18.16^\circ\text{N}, 53.55^\circ\text{N}]$$
- **Guard Condition**: Transformations execute **strictly and exclusively** when:
  `in_china_bbox(lat, lng) == true AND active_layer IN ('amap', 'baidu')`
  Outside this bounding box or on standard layers (OSM, Google, Satellite), coordinates pass through completely untransformed.

### 4.2 Decision: Sub-Meter Reverse Transformation via Newton's Method
- **Decision**: Use Newton's numerical iteration method for `gcj02_to_wgs84` with a convergence threshold of $\Delta < 1 \times 10^{-6}$ degrees ($\approx 0.1$ meter ground resolution).
- **Algorithm**:
  ```typescript
  export function gcj02_to_wgs84(gcjLng: number, gcjLat: number): [number, number] {
    if (!isInChinaBBox(gcjLng, gcjLat)) return [gcjLng, gcjLat];
    let wgsLng = gcjLng;
    let wgsLat = gcjLat;
    const threshold = 1e-6; // Sub-meter accuracy
    const maxIterations = 30;

    for (let i = 0; i < maxIterations; i++) {
      const [currGcjLng, currGcjLat] = wgs84_to_gcj02(wgsLng, wgsLat);
      const dLng = currGcjLng - gcjLng;
      const dLat = currGcjLat - gcjLat;
      if (Math.abs(dLng) < threshold && Math.abs(dLat) < threshold) {
        break;
      }
      wgsLng -= dLng;
      wgsLat -= dLat;
    }
    return [wgsLng, wgsLat];
  }
  ```
- **Rationale**:
  - Closed-form reverse GCJ-02 analytical equations do not exist because the Chinese State Bureau equations utilize non-linear trigonometric polynomial series.
  - Newton's iteration converges reliably within 3–5 iterations (< 0.05ms compute), guaranteeing that any pin dropped on AutoNavi/Amap is submitted to the backend in true canonical WGS-84 coordinate space.

---

## 5. Topic 4: Client-Only Photo EXIF Reader

### 5.1 Decision: Zero-Cloud-Cost In-Memory Metadata Extraction
- **Decision**: Integrate `exifreader` library in the browser to extract EXIF, IPTC, and XMP tags directly from the user's selected file buffer.
- **Supported Formats**:
  - Standard raster: JPEG, WebP, PNG
  - Mobile containers: HEIC, HEIF (native iPhone camera format)
- **Extracted Fields**:
  - `GPSLatitude` & `GPSLatitudeRef` $\rightarrow$ Decimal Latitude
  - `GPSLongitude` & `GPSLongitudeRef` $\rightarrow$ Decimal Longitude
  - `DateTimeOriginal` $\rightarrow$ ISO 8601 string for `visited_dates`
  - `Orientation` $\rightarrow$ CSS rotation transformation
- **Rationale**:
  - Zero server bandwidth and zero AWS Lambda invocation costs.
  - User photos are never transmitted across the network unless the user explicitly uploads them to an asset bucket in future phases.
  - Immediate instant metadata pre-fill in the manual creation form.

### 5.2 Decision: Ephemeral Object URL Memory Lifecycle
- **Decision**: Render thumbnail previews using `URL.createObjectURL(file)`, maintaining an active reference in component state and registering an unmount cleanup hook calling `URL.revokeObjectURL(url)`.
- **Rationale**:
  - Prevents browser memory leaks during extended map sessions where travelers inspect multiple candidate photos.

### 5.3 Decision: Geolocation & Map Fallback Workflows
- **Decision**: When EXIF GPS metadata is absent (stripped by social media or camera privacy settings):
  1. Display advisory badge: "No GPS metadata found in photo".
  2. Provide 1-click "Use Current Location" button invoking `navigator.geolocation.getCurrentPosition()`.
  3. Provide 1-click "Pick on Map" button entering interactive pin placement mode on the MapLibre canvas.

---

## 6. Topic 5: Asynchronous CSV Ingestion, Triage & Client Persistence

### 6.1 Decision: Client-Side Upload Guardrails & Split Modal
- **Decision**: Validate file payload before issuing `POST /api/ingest/upload`:
  - Size check: `file.size <= 2 * 1024 * 1024` (2MB limit).
  - Row check: Stream first 2,050 lines; reject if lines exceed 2,000.
  - When limits are exceeded, display a dedicated Split Instructions Modal with pre-configured split instructions (CLI command `split -l 2000` or spreadsheet export guidelines).
- **Rationale**:
  - Aligns with Constitution Operational Invariant 1 (Asynchronous SQS Ingestion & Queue Discipline).
  - Prevents wasteful network transmissions of unprocessable payloads.

### 6.2 Decision: IndexedDB Ingestion Triage Store with 7-Day TTL
- **Decision**: Implement an IndexedDB client wrapper using `idb` targeting database `vistarae_ingest_db` and object store `triage_jobs` (keyed by `job_id`).
- **Record Schema**:
  ```typescript
  interface StagedTriageRecord {
    job_id: string; // KeyPath
    decisions: Record<number, 'COMMITTED' | 'REJECTED'>;
    last_updated: number; // Unix timestamp ms
    expires_at: number; // last_updated + 7 days (604,800,000 ms)
  }
  ```
- **Lifecycle & Eviction Policy**:
  - On app launch / navigating to `/ingest`: scan `triage_jobs` index and delete all records where `expires_at <= Date.now()`.
  - On submitting triage (`POST /api/ingest/jobs/{job_id}/triage` returning 200 OK): immediately delete the `job_id` record.
  - On polling job status: if job reaches `COMPLETED` or `FAILED`, delete the local IndexedDB record to avoid showing stale duplicates.
  - In private browsing where IndexedDB may fail: gracefully fall back to an in-memory Map with an advisory toast.

---

## 7. Topic 6: Authentication, User Profiles, Preferences & Administration

### 7.1 Decision: AWS Cognito Integration with Local Mocking
- **Decision**: Implement modular authentication service interfacing with AWS Cognito User Pools via direct REST/SDK calls in production and `X-Mock-User-Id` / `X-Mock-User-Tier` header injection when `VITE_APP_ENV === 'local'`.
- **Views**:
  - `/signup`: Email, password, full name $\rightarrow$ transitions to verification code entry.
  - `/login`: Email and password $\rightarrow$ stores JWT access/id tokens in memory / secure storage.
  - `/forgot-password` & `/reset-password`: Two-step password recovery flow.
  - `/logout`: Invalidates session and clears local credentials.
- **Profile & Preferences**:
  - `/profile`: Shows identity details, token usage metrics, quota tier, and GDPR account deletion modal.
  - Sub-domain preference panels:
    - `/settings/account`: Account & presentation preferences (`ui`).
    - `/settings/poi`: Clustering radius, geoproximity scope, pin color presets, default map layer (`poi`).
    - `/settings/planner`: Pacing, transit mode, currency, activity caps (`planner`).

### 7.2 Decision: Admin Governance Dashboard
- **Decision**: Create an administrative route `/admin` protected by a client-side route guard (`user.is_admin === true`) consuming:
  - `GET /api/admin/users`: User table with tier badge, search, and status controls.
  - `PATCH /api/admin/users/{id}/tier` & `PATCH /api/admin/users/{id}/status`: In-place tenant governance.
  - `GET /api/admin/metrics`: Platform metrics cards (users, active sessions, monthly token consumption).
  - `GET /api/admin/controls`: Operational toggles and platform rate limits.
- **Security Guard**: Non-admin users attempting access are redirected to `/` with an RFC 7807 403 Forbidden error toast.

---

## 8. Summary of Technology Selections

| Domain | Technology Selection | Rationale & Constitutional Fit |
| :--- | :--- | :--- |
| **Framework / Bundler** | Vite 5 + React 18 + TypeScript 5.5 | Ultra-fast HMR, static S3/CloudFront deployment (Invariant 3) |
| **Styling & Theming** | Vanilla CSS + CSS Variables | Instant light/dark/system themes, zero bundle bloat |
| **Map Rendering** | MapLibre GL JS (v4.x) | Open-source WebGL hardware acceleration, 60 FPS |
| **Clustering Engine** | Supercluster | Client-side 60 FPS clustering for < 1,000 POIs |
| **Coordinate Transformation** | Pure TS Newton's Method Iteration | Sub-meter < 0.000001° canonical WGS-84 precision |
| **Photo EXIF Reader** | ExifReader (Pure in-memory JS) | Zero cloud bandwidth/compute, supports HEIC/JPEG |
| **Triage Storage** | Browser IndexedDB (`vistarae_ingest_db`) | 7-day TTL persistence for uncommitted duplicate reviews |
| **API Contract** | `openapi-typescript` $\rightarrow$ `api.ts` | Principle 5 mandatory CI type synchronization |
| **Error Handling** | RFC 7807 `ProblemDetails` Mapper | Principle 5 standardized error notifications |
