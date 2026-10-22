# Vistarae (`vistarae`)

> **Collect places you dream to visit, organize them effortlessly, and conquer your travel dreams.**

Vistarae empowers travelers to capture points of interest (POIs), scenic overlooks, trails, and travel dreams from anywhere across the web via a Manifest V3 Chrome Extension.

Vistarae extracts structured entities from highlighted text and page metadata using Google Gemini Flash-Lite (with zero-thinking latency optimization), deterministically geocodes coordinates via OpenStreetMap Nominatim, performs spatial collision and deduplication checks via PostgreSQL/PostGIS, and renders an isolated Shadow DOM verification modal directly in the active browser tab. Once verified by the user, the record is committed to PostGIS.

---

## 🏛️ Monorepo Architecture

```
vistarae/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Monorepo CI: PostGIS, pytest >=90%, alembic check, OpenAPI drift
│       └── deploy.yml             # Keyless OIDC CD: Neon migrations, S3 sync, CloudFront invalidation
├── packages/
│   └── core/                      # Shared domain library (vistarae-core)
│       ├── vistarae_core/
│       │   ├── domain/            # Domain entities and value objects
│       │   ├── ports/             # Repository and adapter interfaces (Protocols)
│       │   ├── schemas/           # Pydantic v2 strict models & boundaries
│       │   ├── adapters/          # SQLAlchemy async repositories & PostGIS adapters
│       │   └── middleware/        # Telemetry, Rate limiting, and Idempotency middleware
├── services/                      # Independent domain microservices (FastAPI + Mangum)
│   ├── poi/                       # POI management, spatial clustering & AI Trip Planner
│   ├── user/                      # Cognito auth, user profiles & preferences
│   ├── ingest/                    # CSV upload validation, triage & SQS dispatch
│   ├── admin/                     # Admin metrics, tenant quotas & spend killswitch
│   ├── worker/                    # SQS Batch Ingest worker for geocoding & deduplication
│   └── local_gateway.py           # Unified local ASGI development gateway
├── frontend/                      # Single-Page Application (React 18 + Vite + TypeScript)
│   ├── src/
│   │   ├── components/            # UI components (map, ingest, poi, planner)
│   │   ├── pages/                 # Route pages (PlannerPage, ItineraryDetailPage, MapView)
│   │   └── services/              # API clients and offline triage storage
├── extension/                     # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── background/                # Service worker, auth refresh mutex & telemetry
│   ├── content/                   # Shadow DOM modal injector & polymorphic parsers
│   └── browser/                   # Full-tab POI Explorer workstation & CSV export
├── native_host/                   # Chrome Native Messaging Host (Pure Python)
│   ├── folder_dispatcher.py       # 4-byte framed stdio dispatcher with UNC guards
│   └── com.vistarae.folder_opener.json
├── db/
│   └── migrations/                # Alembic async database migrations (0001–0004)
├── cloudfront/
│   └── spa-router.js              # CloudFront Function for extensionless SPA routing
├── template.yaml                  # AWS SAM Serverless Infrastructure (us-east-2)
├── docker-compose.yml             # Local dev stack (PostGIS + ElasticMQ + Jaeger)
├── Makefile                       # Developer orchestration shortcuts (uv-powered)
├── GEMINI.md                      # Project architectural rules & standards
└── README.md                      # Architecture overview and operational guide
```

---

## ⚡ Tech Stack & Operational Guardrails

- **Frontend SPA**: React 18, TypeScript 5.4+, Vite, `@hello-pangea/dnd`, MapLibre GL, Lucide React.
- **Browser Extension**: Chrome Extension (Manifest V3), Vanilla JavaScript, CSS-isolated Shadow DOM.
- **Backend Microservices**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, asyncpg, GeoAlchemy2, Mangum.
- **Cloud Infrastructure**: AWS SAM (`template.yaml` in `us-east-2`), S3 SPA with CloudFront OAC, HTTP API Gateway, 6 domain Lambdas (arm64), SQS + DLQ, and automated SpendKillSwitch ($15.00 ceiling).
- **Database & Geospatial Engine**: PostgreSQL 16+ with PostGIS 3.4+, `btree_gist`, and `vector` (pgvector 768-dim).
  - _Development_: Local Docker container (`postgis/postgis:16-3.4`).
  - _Production_: Neon Serverless PostgreSQL with PgBouncer connection pooler.
- **LLM Extraction & Trip Planning**: Google Gemini Flash-Lite and `text-embedding-004` (768-dim embeddings) via `google-genai` SDK with strict JSON schema enforcement and zero-latency thinking budget.
- **Deterministic Geocoding**: OpenStreetMap Nominatim API (1 req/sec rate limit, custom User-Agent `VistaraeTravelEngine/1.0`, backed by an internal PostGIS `geocache` table with SHA256 hashing).
- **Distributed Observability**: OpenTelemetry W3C distributed tracing (`traceparent` header propagation), AWS X-Ray Active Tracing (1% sampling rule), and strict microservice message logging tags.

---

## 📡 Telemetry & OpenTelemetry Conventions

Every API interaction across the extension and backend strictly conforms to W3C Trace Context standards:

1. **Trace Propagation**:
   - The Chrome extension generates a root trace context and injects:
     - `traceparent: 00-{trace_id}-{client_span_id}-01`
     - `X-Source: extension`
     - `X-Destination: backend`
   - FastAPI middleware extracts the W3C context, instantiates a server span, and logs:
     `INCOMING | TraceID={trace_id} | SpanID={span_id} | ParentID={parent_span_id} | Source={source} -> Destination={destination}`
   - FastAPI attaches correlation headers to all responses:
     - `X-Transaction-ID: {trace_id}`
     - `X-Current-Span-ID: {span_id}`
     - `X-Parent-Transaction-ID: {parent_span_id}`
2. **Egress Tracking**: Outgoing backend calls to Nominatim and Gemini are wrapped in child spans recording `http.destination`.
3. **Message Tag Convention**:
   All communication logging follows the microservice tagging convention:
   - `MSG ->|  ` : Inbound message received by service
   - `MSG <-|  ` : Outbound response returned by service
   - `MSG   |->` : Outbound external request dispatched
   - `MSG   |<-` : External response received

---

## 📐 Deduplication & Hierarchy Algorithm

When the backend processes candidate coordinates (`cand_lat`, `cand_lng`, `radius_ft`) and name (`cand_name`), it executes:

1. **Spatial Radius Query**:
   $$ST\_DWithin(\text{location}, ST\_MakePoint(cand\_lng, cand\_lat)::geography, \text{radius\_meters})$$
   where $radius\_meters = radius\_ft \times 0.3048$.
2. **Trigram String Similarity**:
   $$similarity(\text{name}, cand\_name)$$
   evaluated alongside `name_aliases`.
3. **Classification**:
   - 🟡 **Potential Duplicate**: Distance $\le$ radius AND similarity $\ge 0.60$.
   - 🔵 **Nearby Parent / Nesting Candidate**: Distance $\le$ radius, but similarity $< 0.60$ AND existing POI is a macro-site (e.g. National Park, historic district, campus).
   - 🟢 **Unique Location**: No records found within spatial radius.

---

## 🚀 Quickstart & Developer Orchestration

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY from Google AI Studio
```

### 2. Start Services

- **Windows (PowerShell)**:
  ```powershell
  docker compose up -d
  ```
- **macOS / Linux (Make)**:
  ```bash
  make up
  ```

### 3. Sync Environment & Dependencies

- **Using uv (Recommended)**:
  ```bash
  uv sync
  ```
- **Windows (PowerShell)**:
  ```powershell
  .\vistarae.ps1 sync
  ```
- **macOS / Linux (Make)**:
  ```bash
  make sync
  ```

### 4. Run Migrations & Seed Sample Data

- **Windows (PowerShell)**:
  ```powershell
  .\vistarae.ps1 migrate
  .\vistarae.ps1 seed
  ```
- **Using uv directly**:
  ```bash
  uv run alembic upgrade head
  uv run python scripts/seed_local_db.py
  ```
- **macOS / Linux (Make)**:
  ```bash
  make migrate
  make seed
  ```

### 5. Register Native Messaging Host & Load Extension

_(Detailed guide: [Chrome Extension & Native Host Guide](docs/extension_native_host.md))_

1. **Register the Native Messaging Host** (user-level, non-admin):
   ```bash
   python scripts/register_native_host.py
   ```
2. **Load Unpacked Extension in Chrome**:
   - Open Google Chrome and navigate to `chrome://extensions/`.
   - Toggle on **Developer mode** in the upper-right corner.
   - Click **Load unpacked** and select the `extension/` directory inside this repository (`D:\Coding\Vistarae\extension`).
   - Pin **Vistarae — POI & Travel Capture Engine** to your toolbar.
3. **Capture POIs**:
   - Highlight any text or navigate to Google Maps, Roadtrippers, or TripAdvisor.
   - Press `Ctrl+Shift+S` (Windows) or `Cmd+Shift+S` (macOS), or right-click and choose **"Capture to Vistarae"**!
   - Review pre-extracted details in the isolated Shadow DOM modal and hit `Ctrl+Enter` or **Save to Vistarae**.
4. **Browse POIs & Reveal Local Folders**:
   - Right-click anywhere and select **"Browse Saved POIs"** to launch the full-tab POI Explorer.
   - Filter by tags or proximity, export to sanitized CSV, or click **"Reveal Folder"** to open local photo directories.

### 6. Run Automated Tests & Linting

- **Windows (PowerShell)**:
  ```powershell
  .\vistarae.ps1 test
  .\vistarae.ps1 lint
  ```
- **Using uv directly**:
  ```bash
  uv run pytest -v
  uv run ruff check .
  ```
- **macOS / Linux (Make)**:
  ```bash
  make test
  make lint
  ```

---

## ☁️ Serverless Infrastructure & CloudFront Deployment (Phase 6)

Vistarae provisions an enterprise, zero-idle-cost serverless architecture in AWS `us-east-2` via AWS SAM (`template.yaml`):

```
                                  +---------------------------+
                                  |    CloudFront Distribution|
                                  |    (Viewer TLS 1.3 / OAC) |
                                  +-------------+-------------+
                                                |
                       +------------------------+-----------------------+
                       |                                                |
          Path: /* (Default Cache Behavior)                Path: /api/* (API Cache Behavior)
                       |                                                |
          +------------v------------+                      +------------v------------+
          | CloudFront Function     |                      | API Gateway HTTP API    |
          | (spa-router.js)         |                      | ($default stage)        |
          +------------+------------+                      +------------+------------+
                       |                                                |
          +------------v------------+                 +-----------------+-----------------+
          | Private S3 SPA Bucket   |                 |                                   |
          | (All Public Access OFF) |          +------v------+                     +------v------+
          +-------------------------+          | PoiFunction | ...                 | AdminFunction
                                               | (fastapi)   |                     | (killswitch)|
                                               +------+------+                     +-------------+
                                                      |
                                         +------------v------------+
                                         | Neon Serverless PostGIS |
                                         | (PostgreSQL 16 + pgvector)
                                         +-------------------------+
```

### Deployed Endpoints & Routing

- **Frontend SPA**: `https://${CLOUDFRONT_DOMAIN}/`
  - Routes rewritten via `cloudfront/spa-router.js` to `/index.html` for client-side deep linking (`/planner`, `/trips/:id`, `/pois`).
  - Immutable asset caching: `public, max-age=31536000, immutable` for `/assets/*`.
  - Non-cached HTML entrypoint: `public, max-age=0, must-revalidate` for `/index.html`.
- **API Gateway HTTP API**: `https://${CLOUDFRONT_DOMAIN}/api/*`
  - Proxied via CloudFront origin request policy `AllViewerExceptHostHeader` with `CachingDisabled`.
  - `/api/itineraries/generate`: Natural language prompt to day-by-day RAG itinerary synthesis.
  - `/api/itineraries`: List user itineraries, create manual trip, retrieve details, update, and delete.
  - `/api/itineraries/{id}/items/reorder`: Interactive drag-and-drop item timeline updates.
  - `/api/health/ready`: Non-recurring deployment readiness probe (safe for Neon scale-to-zero).
- **Automated Spend Killswitch**: 4-tier cascading shutdown triggered at $15.00 AWS Budgets alert via SNS. Emergency restoration executed via `python scripts/reset_killswitch.py`.

---

## 🔗 Downstream Systems (Future Scope)

1. **Photo Cataloging**: Embedding IPTC/EXIF location metadata into images based on GPS/time matching.
2. **Offline Mobile Sync**: Syncing Trip Planner schedules and route maps to offline PWA storage.
3. **Collaborative Planning**: Multi-traveler concurrent WebSocket itinerary voting and edits.
