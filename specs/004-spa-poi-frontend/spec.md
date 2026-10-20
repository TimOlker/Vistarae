# Feature Specification: Phase 4 — Single-Page Application (SPA) & Interactive POI Frontend

**Feature Identifier**: `004-spa-poi-frontend`  
**Feature Branch**: `004-spa-poi-frontend`  
**Created**: 2026-10-19  
**Status**: Draft  
**Target Systems**: Web Browser (Modern Evergreen), Vite Dev Server / Proxy, OpenAPI TypeScript Engine, Map Rendering Engine, AWS Cognito Identity Provider

**Input**: User description: "/speckit.specify Create the specification for Phase 4 (004-spa-poi-frontend) using strict EARS syntax (REQ-UI-xxx, REQ-MAP-xxx)."

---

## 1. Executive Summary & Context

Phase 4 (`004-spa-poi-frontend`) delivers the responsive, high-performance Single-Page Application (SPA) for Vistarae travelers. It unites the identity, quota, administrative, spatial POI, and asynchronous ingestion capabilities engineered in Phases 1–3 into an intuitive, visually stunning web application. 

The application provides:
1. **Core SPA Architecture & Governance**: A Vite-powered modular TypeScript frontend with API proxying, auto-generated OpenAPI type contracts, RFC 7807/9457 ProblemDetails error boundary mapping, global Terms of Service (TOS), unified light/dark/system theme management, AWS Cognito authentication flows, deep sub-domain preference panels (Account/UI, POI Mode, Planner Mode), and an administrative governance dashboard.
2. **Interactive Map & Synchronized Table View**: Multi-layer geospatial mapping across global (OpenStreetMap, Satellite, Google Maps, Road) and shifted regional Chinese tile sets (AutoNavi/Amap, Baidu). It features an in-browser two-way coordinate transformation engine (WGS-84 $\leftrightarrow$ GCJ-02/BD-09) active strictly within the China bounding box, high-precision numerical iteration (< 0.000001° threshold) for sub-meter pin drops, 300ms viewport debounce, adaptive client-side Supercluster (< 1,000 POIs) vs. backend spatial query switching, and bidirectional map-table filtering.
3. **Client-Only Photo EXIF & Ingestion Triage UI**: A privacy-first, zero-cloud-bandwidth photo reader extracting GPS and timestamps directly in browser memory with interactive geolocation fallbacks, paired with an asynchronous CSV upload and triage modal supporting row/size error splitting, progress polling, and offline-persistent triage decisions.

---

## Clarifications

### Session 2026-10-20
- Q: How should the application handle map layer switching persistence and marker re-projection when a traveler toggles tile layers on the map view widget? → A: Option A (Session-first with explicit default): Layer changes on the map widget apply immediately to the active map session and re-project cached markers in-memory (setData) without network calls; default_map_layer in user_preferences.poi updates only via Settings (/settings/poi) or an explicit "Save as Default" control.
- Q: What lifecycle, eviction, and server synchronization policy should govern IndexedDB duplicate triage persistence? → A: Option A (Job-synced with 7-day TTL & auto-cleanup): IndexedDB (vistarae_ingest_db, store triage_jobs) keys decisions by job_id; purges the record immediately upon successful submission of POST /api/ingest/jobs/{job_id}/triage or when polled status is COMPLETED/FAILED; and opportunistically evicts records older than 7 days on app launch.
- Q: Which image formats and memory lifecycle rules should the client-only Photo EXIF Reader support during manual POI creation? → A: Option A (Universal mobile format support & Blob lifecycle): Client-only reader parses EXIF from JPEG, WebP, PNG, and HEIC/HEIF files entirely in browser memory; renders a local preview via URL.createObjectURL(file) with guaranteed URL.revokeObjectURL cleanup upon modal close; and stores extracted GPS coordinates as canonical WGS-84 (projecting to GCJ-02/BD-09 purely for display if a Chinese layer is active).

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 - Authentication, Profile, Preferences & Theming (Priority: P1)

A new or returning traveler accesses the Vistarae web application, registers with email verification or authenticates with Cognito credentials, manages their profile and security settings, seamlessly toggles or syncs their interface theme (Light, Dark, System), and configures preferences across Account/UI, POI Mode, and Planner Mode domains with instantaneous UI updates and cloud persistence.

**Why this priority**: Authentication and preferences establish tenant identity, secure session state, and user customization required for all subsequent POI capture and visualization features.

**Independent Test**: Can be fully tested by registering a new account, completing email verification, logging in, updating preferences across all three sub-domain tabs, verifying instant theme application and server persistence, and cleanly terminating the session via logout.

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor on the login page, **When** they submit valid registration details (email, password, full name), **Then** the system displays the email code confirmation form and creates the tenant profile upon successful verification.
2. **Given** an authenticated user on any page, **When** they toggle the theme switcher between `light`, `dark`, and `system`, **Then** the application applies CSS theme classes immediately without page refresh and persists the selection to `user_preferences`.
3. **Given** an authenticated user on the Preferences page, **When** they modify values in the Account/UI, POI Mode, or Planner Mode forms and click Save, **Then** the application validates inputs against schema bounds, submits sub-domain PATCH requests, and shows a confirmation toast.
4. **Given** an authenticated user whose session token expires or becomes invalid, **When** a background API request returns an HTTP 401 response, **Then** the system clears cached credentials and redirects the user to the login screen with a return-path parameter.

---

### User Story 2 - Interactive Map Exploration, Layer Switching & Viewport Synchronization (Priority: P1)

An authenticated traveler explores their collection of Points of Interest on an interactive full-screen map synchronized with a tabular view. The user pans and zooms across destinations, switches between global tile layers (Google Maps, OpenStreetMap, Satellite, Road) and regional Chinese layers, observes high-performance clustering, and toggles viewport filtering so the table lists only POIs visible on the current map canvas.

**Why this priority**: Geospatial visualization and synchronized tabular navigation form the core everyday value proposition for travel discovery and itinerary review.

**Independent Test**: Can be fully tested by loading a dataset of POIs, panning/zooming to trigger 300ms debounced queries or client-side Supercluster rendering, switching tile layers, and toggling the "Filter table to map viewport" control to assert table row synchronization.

**Acceptance Scenarios**:

1. **Given** a user viewing the map with fewer than 1,000 total POIs, **When** the map initial load completes, **Then** the system caches the GeoJSON dataset in browser memory, performs clustering client-side via Supercluster, and updates the map source in-place (`map.getSource('pois').setData(...)`) without issuing bounding-box network requests on map pan/zoom.
2. **Given** a user viewing the map with 1,000 or more total POIs, **When** the user stops panning or zooming (triggering `moveend`), **Then** the system waits for a 300ms debounce interval before dispatching `GET /api/pois?bbox={minLng,minLat,maxLng,maxLat}` to update viewport pins.
3. **Given** a user with the "Filter table to current map viewport" toggle enabled, **When** the map viewport bounding box changes, **Then** the table immediately filters its rows to include only the POIs currently visible within the map boundaries.
4. **Given** a user viewing the map, **When** they select a different map layer from the layer control (OpenStreetMap, Satellite, Google Maps, Road), **Then** the map swaps base tiles smoothly while preserving current viewport coordinates, zoom level, and active marker overlays.

---

### User Story 3 - Precision Coordinate Transformation for China Tiles (Priority: P2)

A traveler exploring destinations within mainland China switches to a shifted Chinese tile provider (AutoNavi/Amap or Baidu) or drops a new location pin on a Chinese map layer. The system dynamically applies coordinate offsets (WGS-84 to GCJ-02 or BD-09) strictly inside the China geographic bounding box so pins align with underlying imagery, and applies Newton's numerical iteration on pin drops to resolve sub-meter canonical WGS-84 coordinates prior to backend submission.

**Why this priority**: China's State Bureau of Surveying and Mapping mandates non-linear coordinate shifting (GCJ-02/BD-09). Without localized two-way coordinate transformation, pins in China appear offset by 300–700 meters, compromising navigational safety and location fidelity.

**Independent Test**: Can be fully tested by loading coordinates inside China (e.g., Beijing 116.4074°E, 39.9042°N) on standard OpenStreetMap (untransformed) vs. AutoNavi (transformed to GCJ-02), dropping a pin on AutoNavi, and verifying that the reverse transformation reproduces canonical WGS-84 coordinates within 0.000001° accuracy.

**Acceptance Scenarios**:

1. **Given** coordinates situated within the China bounding box (73.66°E–135.05°E, 18.16°N–53.55°N), **When** a shifted Chinese map layer (AutoNavi/Amap or Baidu) is selected, **Then** the frontend coordinate module transforms coordinates to GCJ-02 or BD-09 before rendering markers.
2. **Given** coordinates situated outside the China bounding box (e.g., Paris 2.3522°E, 48.8566°N), **When** any map layer is selected, **Then** the coordinate transformation module bypasses transformation and renders canonical WGS-84 coordinates directly.
3. **Given** a user dropping a pin on an active AutoNavi (GCJ-02) map layer within China, **When** the pin placement event fires, **Then** the system executes `gcj02_to_wgs84` using Newton's numerical iteration until the difference is below 0.000001° before transmitting the coordinates to the API.

---

### User Story 4 - Client-Only Photo EXIF Extraction & Manual POI Creation (Priority: P2)

A traveler creates a new POI by selecting or dragging a photo into the browser. The frontend extracts EXIF GPS coordinates and capture timestamps directly in client memory without transmitting the image binary to the cloud, protecting privacy and eliminating upload costs. If the photo lacks GPS metadata, the UI guides the user to supply coordinates via one-click browser geolocation or interactive map pin placement.

**Why this priority**: Instant photo-based POI creation is a marquee capture workflow; executing EXIF parsing purely on the client guarantees zero server compute/bandwidth costs while safeguarding sensitive user photos.

**Independent Test**: Can be fully tested by selecting an image with EXIF GPS to verify automated form population with zero outbound image network traffic, followed by testing an image without EXIF to verify geolocation fallback and manual map pin drop.

**Acceptance Scenarios**:

1. **Given** an image file containing valid EXIF GPS coordinates and timestamp, **When** the user drops or selects the image in the Manual Add POI dialog, **Then** the browser reads the metadata entirely in memory, populates latitude, longitude, and visited date fields, and does not upload the image file to AWS.
2. **Given** an image file lacking EXIF GPS metadata, **When** the user loads the image into the dialog, **Then** the system displays a clear notification stating that location metadata is absent and presents options for "Use Current Location" (`navigator.geolocation`) and "Pick on Map".
3. **Given** a user selecting "Pick on Map", **When** they click a location on the interactive map canvas, **Then** the dialog updates its latitude and longitude inputs with the clicked coordinates, converting from GCJ-02 to WGS-84 if a shifted Chinese layer is active.

---

### User Story 5 - Ingestion CSV Triage, Job Polling & Client Persistence (Priority: P3)

A user uploads a bulk travel CSV file for asynchronous ingestion. If the file exceeds operational guardrails (>2MB or >2,000 rows), the UI immediately displays a split-instructions modal. For valid uploads, the UI polls ingestion progress (`/api/ingest/jobs/{job_id}`) and presents an interactive duplicate triage modal where pending duplicate reviews can be committed or rejected individually or in bulk, with pending triage state persistently saved across page reloads in browser storage.

**Why this priority**: Bulk CSV ingestion can encounter network interruptions, browser refreshes, and multi-step duplicate triage; client-side persistence prevents data loss and redundant user effort.

**Independent Test**: Can be fully tested by uploading a valid CSV file, observing real-time progress bar polling, reviewing potential duplicates in the triage modal, refreshing the browser, asserting that pending triage selections survive reload via IndexedDB/localStorage, and submitting decisions.

**Acceptance Scenarios**:

1. **Given** a user attempting to upload a CSV file larger than 2MB or containing more than 2,000 rows, **When** the file validation runs, **Then** the UI blocks submission and displays a split instructions modal explaining how to segment the CSV into compliant chunks.
2. **Given** an accepted CSV ingestion job, **When** the background worker processes records, **Then** the UI polls `GET /api/ingest/jobs/{job_id}` at 2-second intervals, updating the progress bar, row count, and percent complete.
3. **Given** an ingestion job returning duplicate candidates in `PENDING_REVIEW` status, **When** the user opens the triage modal and toggles merge/create decisions, **Then** the UI persists the staging state in `localStorage`/`IndexedDB` so uncommitted decisions are preserved across browser refreshes.
4. **Given** staged triage decisions, **When** the user clicks "Commit All Decisions", **Then** the UI submits `POST /api/ingest/jobs/{job_id}/triage` with decision items and refreshes the POI collection upon completion.

---

### User Story 6 - Administrative Governance & System Controls (Priority: P3)

An authorized administrator navigates to the dedicated Admin Dashboard to review platform-wide operational health, inspect user consumption metrics, adjust user tiers and account statuses, monitor token quota utilization, and verify system operational controls.

**Why this priority**: Administrative observability and user governance protect platform integrity, enforce tier policies, and provide operational oversight without direct database intervention.

**Independent Test**: Can be fully tested by authenticating as an admin user, navigating to `/admin`, viewing user lists and consumption metrics, updating a user tier, and verifying that non-admin users receive an authorization error banner when attempting to access admin routes.

**Acceptance Scenarios**:

1. **Given** an authenticated user with admin credentials, **When** they navigate to `/admin`, **Then** the dashboard displays user counts, active tier distributions, token consumption metrics, and system control toggles.
2. **Given** an admin reviewing the user management table, **When** they update a user's tier (`LOW` to `HIGH`) or account status (`is_active: false`), **Then** the UI dispatches the administrative PATCH request and updates the table row with a success banner.
3. **Given** a standard non-admin user, **When** they attempt to navigate to `/admin`, **Then** the router redirects them to the main view and displays an RFC 7807 403 Forbidden toast notification.

---

### Edge Cases

- **Offline or Intermittent Connectivity**: When network connectivity drops during map panning, the UI displays a subtle offline indicator and retains cached markers without crashing or clearing the map.
- **Antimeridian Crossing (180° Longitude)**: When the map viewport spans across the International Date Line (minLng > maxLng), the client query builder splits the query into two bounding boxes or requests the wrap-around coordinates cleanly without infinite fetch loops.
- **Extreme Coordinate Bounds**: When marker coordinates lie exactly on the China bounding box boundary (e.g., 73.66°E or 53.55°N), the coordinate module handles boundary equality gracefully without throwing exceptions.
- **Newton Iteration Convergence**: If the numerical iteration for `gcj02_to_wgs84` fails to converge within 30 iterations, the module logs a warning, aborts the loop, and falls back to the current best estimate within 0.00001°.
- **Malformed or Stripped EXIF Data**: When a user selects a JPEG or HEIC file with corrupted, empty, or privacy-stripped EXIF markers, the photo reader catches the error cleanly and seamlessly triggers the geolocation/pin-drop fallback.
- **Storage Quota Exceeded in Private Browsing**: When `localStorage` or `IndexedDB` throws a quota or permission error (e.g., in strict private browsing), the UI falls back to an in-memory triage state and alerts the user that decisions will not persist across page reloads.
- **Rapid Viewport Dragging**: When a user rapidly flings or continuously drags the map, the 300ms debounce timer resets on each `movestart`/`move`, executing exactly one network request only after motion ceases.
- **RFC 7807 ProblemDetails Error Surfacing**: When any API route returns an RFC 7807/9457 error payload (e.g., 400 Bad Request with `invalid_params`, 429 Too Many Requests with `Retry-After`), the top-level error boundary and toast notification display the human-readable `detail` and parameter validation messages.

---

## 3. Requirements *(mandatory)*

### Core SPA Setup & UI Requirements (`REQ-UI-xxx`)

- **REQ-UI-001 (Ubiquitous):** The single-page application shall be located in the `frontend/` directory and configure a Vite proxy forwarding all `/api` requests to `http://localhost:8000` with `changeOrigin: true`.
- **REQ-UI-002 (Ubiquitous):** The build toolchain shall generate and maintain strict TypeScript types in `./frontend/src/types/api.ts` synchronized with the authoritative backend OpenAPI contract (`./openapi.json`) using `openapi-typescript`.
- **REQ-UI-003 (Event-Driven):** When any API request returns an HTTP status code outside the 2XX range, the frontend application shall parse the response as an RFC 7807 / RFC 9457 `ProblemDetails` payload containing `type`, `title`, `status`, `detail`, `instance`, and optional `invalid_params`.
- **REQ-UI-004 (Event-Driven):** When an RFC 7807 `ProblemDetails` error is caught, the top-level Error Boundary and Toast Notification system shall render an actionable notification banner displaying the error `title`, `detail`, and field-specific validation hints.
- **REQ-UI-005 (Event-Driven):** When an RFC 7807 429 Too Many Requests response is received, the Toast Notification shall extract the `Retry-After` header value and display an active countdown timer indicating when the rate limit window resets.
- **REQ-UI-006 (Ubiquitous):** The application shall provide a dedicated Terms of Service (`/terms`) page detailing data usage, privacy guardrails, and platform policies accessible without authentication.
- **REQ-UI-007 (Ubiquitous):** The application shall implement a global Theme Engine supporting three distinct modes: `light`, `dark`, and `system` (operating system preference).
- **REQ-UI-008 (Event-Driven):** When the user selects a theme mode, the Theme Engine shall apply the corresponding CSS variables and dark-mode utility classes immediately across all views, tables, modal dialogs, and map layer controls.
- **REQ-UI-009 (State-Driven):** While an authenticated user session is active, the Theme Engine shall persist the selected theme mode to the backend via `PATCH /api/users/me/preferences/ui` and initialize the theme from `user_preferences.ui.theme` on login.
- **REQ-UI-010 (State-Driven):** While no authenticated user session is active, the Theme Engine shall persist the theme mode in browser `localStorage` under key `vistarae_theme_mode` and synchronize with the OS media query `(prefers-color-scheme: dark)` when set to `system`.
- **REQ-UI-011 (Ubiquitous):** The application shall provide dedicated Cognito authentication views: Sign Up (`/signup`) with email verification code confirmation, Sign In (`/login`), Forgot/Reset Password (`/forgot-password`), and Logout (`/logout`).
- **REQ-UI-012 (Event-Driven):** When a user completes the sign-up form, the system shall submit the registration to `/api/auth/register` and transition to the code verification view for `/api/auth/confirm-signup`.
- **REQ-UI-013 (Event-Driven):** When a user initiates password recovery, the system shall submit `/api/auth/forgot-password`, prompt for the emailed recovery code and new password, and submit `/api/auth/reset-password`.
- **REQ-UI-014 (Event-Driven):** When an authenticated user logs out, the system shall call `/api/auth/logout`, purge all cached JWT tokens and user profile state from browser memory and storage, and redirect to `/login`.
- **REQ-UI-015 (Ubiquitous):** The application shall provide a dedicated Profile Page (`/profile`) displaying account details (full name, email, Cognito subject, created date), account deletion controls (GDPR cascade deletion with re-authentication confirmation), and current quota/metric utilization cards.
- **REQ-UI-016 (Ubiquitous):** The application shall provide dedicated Preferences Pages partitioned into three sub-domain panels:
  - Account/UI Preferences (`/settings/account`): Theme (`light`, `dark`, `system`), email notification toggles, push notification toggles, marketing email toggles.
  - POI Mode Preferences (`/settings/poi`): Clustering toggle, clustering radius slider (10m–500m), default map layer selector, geoproximity scope slider (1.0km–500.0km), pin color presets.
  - Planner Mode Preferences (`/settings/planner`): Pacing mode (`RELAXED`, `BALANCED`, `PACKED`), meal intervals slider (1.0h–8.0h), lunch packing toggle, transit speed mode (`WALKING`, `CYCLING`, `TRANSIT`, `DRIVING`), daily activity hour cap slider (1.0h–18.0h), preferred currency selector (ISO 4217).
- **REQ-UI-017 (Event-Driven):** When the user updates any preferences sub-domain panel, the system shall validate field bounds client-side and submit `PATCH /api/users/me/preferences/{ui|poi|planner}` with only modified fields.
- **REQ-UI-018 (Ubiquitous):** The application shall provide an Admin Dashboard (`/admin`) accessible strictly to users with administrator privileges, displaying:
  - User governance table with search, tier badge (`LOW`, `HIGH`), active status toggle, and actions to modify tier via `PATCH /api/admin/users/{user_id}/tier` or status via `PATCH /api/admin/users/{user_id}/status`.
  - System consumption metrics displaying total registered users, active sessions, monthly token budget utilization, and SQS queue health.
  - System control panel for administrative feature flags and quota ceilings.
- **REQ-UI-019 (Unwanted Behaviour):** If an unauthenticated or non-admin user attempts to navigate to `/admin`, then the router shall redirect the user to `/` and display an RFC 7807 403 Forbidden error toast.
- **REQ-UI-020 (Ubiquitous):** The application shall provide a Manual Add POI dialog featuring an in-browser Photo EXIF Reader.
- **REQ-UI-021 (Event-Driven):** When a user selects or drops an image file in the Manual Add POI dialog, the Photo EXIF Reader shall extract GPS coordinates (`latitude`, `longitude`) and capture timestamp (`visited_dates`) entirely within client memory using a JavaScript EXIF parser supporting JPEG, WebP, PNG, and HEIC/HEIF files without transmitting the image payload over the network.
- **REQ-UI-021a (Event-Driven):** When an image is loaded in the Manual Add POI dialog, the UI shall generate an ephemeral thumbnail preview via `URL.createObjectURL(file)` and explicitly revoke the object URL via `URL.revokeObjectURL(...)` upon dialog dismissal or photo replacement; extracted GPS coordinates shall be recorded as canonical WGS-84 and projected to GCJ-02 or BD-09 purely for preview marker rendering if a shifted Chinese map layer is active.
- **REQ-UI-022 (Event-Driven):** When an image lacks EXIF GPS metadata, the Manual Add POI dialog shall display an advisory notice and provide one-click buttons for "Use Current Location" (invoking `navigator.geolocation.getCurrentPosition`) and "Select on Map" (enabling interactive pin placement).
- **REQ-UI-023 (Event-Driven):** When a user drops a location pin on the map during manual POI creation, the dialog shall populate latitude and longitude inputs with the clicked position, converting coordinates to canonical WGS-84 if a shifted Chinese map layer is active.
- **REQ-UI-024 (Event-Driven):** When a user selects a CSV file for ingestion that exceeds 2MB in file size or contains more than 2,000 rows, the UI shall reject the file client-side prior to network dispatch and open a Split Instructions Modal explaining how to partition the dataset.
- **REQ-UI-025 (Event-Driven):** When an accepted CSV file is uploaded via `POST /api/ingest/upload`, the UI shall open the Ingestion Progress view and poll `GET /api/ingest/jobs/{job_id}` at 2-second intervals until the job status reaches `COMPLETED`, `PARTIAL_SUCCESS`, or `FAILED`.
- **REQ-UI-026 (Event-Driven):** When an ingestion job contains duplicate candidates (`duplicates_pending_count > 0`), the UI shall open an interactive CSV Triage Modal displaying candidate pairs side-by-side with match type, similarity score, distance in meters, and staged POI data.
- **REQ-UI-027 (State-Driven):** While duplicate triage is in progress, the UI shall persist `PENDING_REVIEW` decisions (`COMMITTED` or `REJECTED`) in browser `IndexedDB` (database `vistarae_ingest_db`, object store `triage_jobs`, falling back to `localStorage`) keyed by `job_id` with an explicit 7-day time-to-live (`expires_at`), so uncommitted triage work survives page refreshes and browser restarts.
- **REQ-UI-027a (Event-Driven):** When the application initializes or opens the Ingestion view, the storage manager shall scan `vistarae_ingest_db` and evict all triage records where `expires_at <= Date.now()`.
- **REQ-UI-028 (Event-Driven):** When the user confirms duplicate triage decisions, the UI shall submit `POST /api/ingest/jobs/{job_id}/triage` with the array of row-level decisions; upon receiving a 200 OK response OR if polling indicates the job has reached `COMPLETED` or `FAILED`, the UI shall immediately delete the corresponding `job_id` record from `IndexedDB`.

---

### Interactive Map & Geospatial Requirements (`REQ-MAP-xxx`)

- **REQ-MAP-001 (Ubiquitous):** The application shall provide a full-screen interactive Map View integrated with MapLibre GL JS / Leaflet, supporting pan, zoom, pitch, bearing, and responsive resize.
- **REQ-MAP-002 (Ubiquitous):** The Map View shall provide a layer switcher control supporting the following base tile providers:
  - OpenStreetMap Standard (`osm`)
  - Satellite Imagery (`satellite`)
  - Google Maps Standard (`google-roadmap`)
  - Google Maps Satellite/Hybrid (`google-hybrid`)
  - Road / Terrain View (`road`)
  - AutoNavi / Amap Shifted Vector Tiles (`amap`)
  - Baidu Shifted Tiles (`baidu`)
- **REQ-MAP-002a (Event-Driven):** When a user selects a map layer from the layer switcher control on the map canvas, the Map View shall swap base tiles immediately and re-project cached markers in-memory via `map.getSource('pois').setData(...)` without issuing network requests; the selection shall govern the active browser session, and shall only persist to `user_preferences.poi.default_map_layer` if the user clicks an explicit "Save as Default" control on the layer switcher widget or updates preferences on `/settings/poi`.
- **REQ-MAP-003 (State-Driven):** While coordinates fall inside the China geographic bounding box (73.66°E to 135.05°E, 18.16°N to 53.55°N) AND a shifted Chinese map layer is active (`amap` or `baidu`), the Two-Way Coordinate Transform Module shall execute coordinate transformation purely on the client side:
  - For AutoNavi / Amap: convert canonical WGS-84 to GCJ-02 (`wgs84_to_gcj02`).
  - For Baidu: convert canonical WGS-84 to BD-09 (`wgs84_to_bd09`).
- **REQ-MAP-004 (State-Driven):** While coordinates fall outside the China geographic bounding box OR a standard global layer (OpenStreetMap, Satellite, Google Maps, Road) is active, the Two-Way Coordinate Transform Module shall bypass transformation and pass canonical WGS-84 coordinates through unaltered.
- **REQ-MAP-005 (Event-Driven):** When a user drops or adjusts a location pin on an active AutoNavi/Amap map layer within China, the Coordinate Transform Module shall execute `gcj02_to_wgs84` using numerical iteration / Newton's method with a precision convergence threshold of `< 0.000001°` (sub-meter accuracy) before setting the canonical WGS-84 coordinates in the application state or submitting to the API.
- **REQ-MAP-006 (Event-Driven):** When a user drops or adjusts a location pin on an active Baidu map layer within China, the Coordinate Transform Module shall convert BD-09 to GCJ-02 (`bd09_to_gcj02`) followed by numerical iteration `gcj02_to_wgs84` to derive canonical WGS-84 coordinates within `< 0.000001°` precision.
- **REQ-MAP-007 (Ubiquitous):** The backend API and database shall receive and persist all spatial coordinates exclusively in canonical WGS-84 (`EPSG:4326`); no GCJ-02 or BD-09 transformed coordinates shall ever be transmitted to or stored in backend services.
- **REQ-MAP-008 (State-Driven):** While the total count of user-owned POIs is less than 1,000, the Map View shall cache the entire GeoJSON dataset in browser memory and execute spatial clustering and zoom-level filtering entirely on the client using `supercluster`.
- **REQ-MAP-009 (State-Driven):** While client-side clustering is active (< 1,000 POIs), the Map View shall update marker positions and cluster geometries in-place via `map.getSource('pois').setData(geojson)` without issuing HTTP network requests during map pan or zoom.
- **REQ-MAP-010 (State-Driven):** While the total count of user-owned POIs is greater than or equal to 1,000, the Map View shall fetch visible POIs from the backend by debouncing the map `moveend` event by 300 milliseconds before calling `GET /api/pois?bbox={minLng,minLat,maxLng,maxLat}`.
- **REQ-MAP-011 (Event-Driven):** When the user rapidly pans or zooms the map, the 300ms debounce timer shall reset on every motion event, ensuring only a single bounding-box network request is dispatched after movement stabilizes.
- **REQ-MAP-012 (Ubiquitous):** The application shall display a Synchronized POI Table alongside or underneath the interactive map canvas, featuring columns for name, address/city, visit state badge, rating stars, tags, and action buttons.
- **REQ-MAP-013 (Ubiquitous):** The UI shall provide a prominent "Filter table to current map viewport" toggle switch.
- **REQ-MAP-014 (State-Driven):** While the "Filter table to current map viewport" toggle is enabled, the POI Table shall filter its rows in real time to display only the POIs whose coordinates fall within the current map viewport bounding box.
- **REQ-MAP-015 (Event-Driven):** When a user clicks a row in the POI Table, the Map View shall smoothly pan and zoom to center on the corresponding POI marker and open its popup inspection card.
- **REQ-MAP-016 (Event-Driven):** When a user clicks a POI marker or cluster pin on the Map View, the system shall highlight the corresponding row in the POI Table and scroll it into view.
- **REQ-MAP-017 (Event-Driven):** When the user hovers over a POI marker on the map, the marker shall render an inspection tooltip displaying the POI name, visit status, and rating.
- **REQ-MAP-018 (Event-Driven):** When a user updates a POI's attributes (e.g., toggles visit state between `not_visited`, `visited_return`, `visited_do_not_return`, or updates rating), the Map View and POI Table shall update their displayed pins and row data optimistically and reflect the changes in-place.
- **REQ-MAP-019 (Ubiquitous):** The Map View shall render marker pins with distinct colors and glyphs reflecting the POI's `visit_state` and user-configured `pin_color_presets` from `user_preferences.poi.pin_color_presets`.
- **REQ-MAP-020 (Event-Driven):** When the active theme mode changes (`light` vs. `dark`), the Map View shall adjust vector tile styling and map control themes to maintain visual contrast and harmonious aesthetics with the overall application theme.

---

## 4. Key Entities & Data Models

### 4.1 Frontend State & Cache Entities

```
+-----------------------------------------------------------------------------------+
|                                 UserSessionState                                  |
+-----------------------------------------------------------------------------------+
| id: UUID                                                                          |
| email: string                                                                     |
| full_name: string                                                                 |
| token: string (Cognito JWT Access/ID Token)                                       |
| is_admin: boolean                                                                 |
| preferences: UserPreferences                                                      |
|   ui: UIPreferences (theme: light | dark | system, notifications)                 |
|   poi: POIPreferences (clustering_enabled, radius, default_layer, pin_colors)     |
|   planner: PlannerPreferences (pacing, meal_intervals, transit_mode, currency)    |
+-----------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------+
|                                  POIMapFeature                                    |
+-----------------------------------------------------------------------------------+
| id: UUID                                                                          |
| name: string                                                                      |
| canonical_lat: number (WGS-84, -90.0 to 90.0)                                     |
| canonical_lng: number (WGS-84, -180.0 to 180.0)                                   |
| render_lat: number (Transformed if China layer active, else WGS-84)               |
| render_lng: number (Transformed if China layer active, else WGS-84)               |
| visit_state: 'not_visited' | 'visited_do_not_return' | 'visited_return'           |
| rating: number | null (0 to 5)                                                    |
| tags: string[]                                                                    |
| lists: UUID[]                                                                     |
+-----------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------+
|               TriageStagedState (IndexedDB: vistarae_ingest_db.triage_jobs)       |
+-----------------------------------------------------------------------------------+
| job_id: UUID (KeyPath)                                                            |
| total_rows: number                                                                |
| processed_rows: number                                                            |
| status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL_SUCCESS' | 'FAILED'     |
| decisions: Map<number, 'COMMITTED' | 'REJECTED'> (indexed by row_number)          |
| duplicate_candidates: DuplicateItem[]                                             |
| last_updated: number (timestamp ms)                                               |
| expires_at: number (timestamp ms = last_updated + 7 days)                         |
+-----------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------+
|                               PhotoEXIFMetadata                                   |
+-----------------------------------------------------------------------------------+
| file_name: string                                                                 |
| file_size: number                                                                 |
| mime_type: 'image/jpeg' | 'image/webp' | 'image/png' | 'image/heic' | 'image/heif'  |
| preview_url: string | null (ephemeral Blob URL revoked on modal dismiss)          |
| has_gps: boolean                                                                  |
| latitude: number | null (Canonical WGS-84)                                        |
| longitude: number | null (Canonical WGS-84)                                       |
| captured_at: string | null (ISO 8601 date string)                                 |
| orientation: number | null                                                        |
+-----------------------------------------------------------------------------------+
```

### 4.2 Two-Way Coordinate Transform Specification

```
China Bounding Box:
  Min Longitude: 73.66° E
  Max Longitude: 135.05° E
  Min Latitude:  18.16° N
  Max Latitude:  53.55° N

Transform Rules:
  Condition: (73.66 <= lng <= 135.05 AND 18.16 <= lat <= 53.55) AND active_layer IN ('amap', 'baidu')
  True  -> Apply wgs84_to_gcj02 or wgs84_to_bd09 for marker rendering
  False -> Render canonical WGS-84 coordinates without modification

Reverse Transform on Pin Drop:
  Input: (gcj_lng, gcj_lat) on Chinese layer
  Algorithm: Newton's numerical iteration:
    Initial guess: (wgs_lng, wgs_lat) = (gcj_lng, gcj_lat)
    Loop:
      (curr_gcj_lng, curr_gcj_lat) = wgs84_to_gcj02(wgs_lng, wgs_lat)
      d_lng = curr_gcj_lng - gcj_lng
      d_lat = curr_gcj_lat - gcj_lat
      wgs_lng -= d_lng
      wgs_lat -= d_lat
    Terminates when: |d_lng| < 0.000001° AND |d_lat| < 0.000001° (or 30 iterations)
  Output: Sub-meter precision canonical WGS-84 coordinates (lat, lng) submitted to API
```

---

## 5. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Initial Load & Interactivity)**: The SPA achieves a First Contentful Paint (FCP) in under 1.2 seconds and Time to Interactive (TTI) in under 2.0 seconds on standard broadband connections.
- **SC-002 (Theme Switch Latency)**: Theme toggling (`light`, `dark`, `system`) applies styles across the entire application and active map controls in under 50 milliseconds without page refresh.
- **SC-003 (Viewport Debounce Efficiency)**: Map viewport motion triggers at most one network request per stop, debounced by 300ms, eliminating redundant server requests during continuous panning.
- **SC-004 (Client Clustering Responsiveness)**: For datasets under 1,000 POIs, client-side clustering re-renders marker clusters within 16 milliseconds (60 FPS) during pan/zoom operations without network latency.
- **SC-005 (Coordinate Transformation Accuracy)**: Reverse coordinate transformation (`gcj02_to_wgs84`) resolves canonical WGS-84 coordinates with an error margin of less than 0.000001° (sub-meter accuracy) within at most 10 numerical iterations.
- **SC-006 (Zero-Cloud-Cost Photo Parsing)**: 100% of EXIF metadata extraction executes in browser memory, incurring zero outbound image network bytes to AWS.
- **SC-007 (Triage Persistence Resilience)**: 100% of staged duplicate triage selections survive abrupt page refreshes, tab closures, and browser restarts via IndexedDB/localStorage persistence.
- **SC-008 (RFC 7807 Error Communication)**: 100% of non-2XX HTTP responses display structured, human-readable notifications with parameter-level guidance rather than generic error popups.
- **SC-009 (Administrative Protection)**: Unauthorized access attempts to `/admin` are intercepted and rejected client-side 100% of the time before any administrative API call can be dispatched.

---

## 6. Assumptions & Scope Boundaries

### 6.1 Assumptions

- **Browser Capabilities**: Users operate modern evergreen browsers (Chrome 110+, Firefox 110+, Safari 16+, Edge 110+) with WebGL 2.0, IndexedDB, and Geolocation API support.
- **Backend Infrastructure**: The backend FastAPI service is running locally on port 8000 during development, and the Vite proxy routes all `/api/*` traffic transparently.
- **Cognito Identity**: An AWS Cognito User Pool is configured, or local authentication mocking (`X-Mock-User-Id`, `X-Mock-User-Tier`) is active when running against local development environments.
- **Map Tile Availability**: Public OpenStreetMap and standard tile providers operate under acceptable use policies; commercial tile providers (Google Maps, Baidu, AutoNavi) utilize valid developer keys configured via environment variables.

### 6.2 Scope Boundaries

- **In Scope (Phase 4)**:
  - Vite SPA setup with TypeScript, OpenAPI types, Error Boundary, TOS page, Theme Engine.
  - AWS Cognito authentication UI, Profile, Preferences (Account/UI, POI, Planner), Admin Dashboard.
  - Interactive Map with multi-layer switching (Google, OSM, Satellite, Road, Amap, Baidu).
  - Two-way coordinate transformation module (WGS-84 $\leftrightarrow$ GCJ-02/BD-09) active strictly within China bounding box.
  - Viewport debouncing (300ms) and client-side Supercluster (< 1,000 POIs).
  - Synchronized POI Table with "Filter to viewport" toggle.
  - Client-only Photo EXIF reader with geolocation/map-pin fallback.
  - CSV Ingestion triage modal with >2MB / >2,000 row split instructions, progress polling, and IndexedDB persistence.
- **Out of Scope (Future Phases)**:
  - Phase 5: Chrome Extension (Manifest V3) capture popup, context menu, and Shadow DOM injection.
  - Phase 6: Automated itinerary planner engine and timeline scheduling.
  - Native iOS/Android mobile applications (responsive web mobile only in Phase 4).
  - Offline vector tile caching for air-gapped field operations.
