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
│       ├── test-backend.yml       # Pytest, ruff linting & PostGIS container suite
│       └── deploy-supabase.yml    # Supabase CLI migrations on push
├── supabase/                      # Native Supabase CLI workspace
│   ├── config.toml                # Supabase local config
│   ├── seed.sql                   # Starter test data (Yosemite & Glacier Point)
│   └── migrations/                # Versioned SQL migrations (DDL & PostGIS)
│       ├── 20261001_init_postgis.sql
│       ├── 20261002_create_pois_and_access_points.sql
│       ├── 20261003_create_lists_and_geocache.sql
│       └── 20261004_create_users_and_add_user_id.sql
├── backend/                       # FastAPI Ingestion Engine
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI entrypoint, CORS, auth & POI routes
│   │   ├── config.py              # Pydantic Settings (multi-env cascade)
│   │   ├── db.py                  # SQLAlchemy asyncpg session engine
│   │   ├── models.py              # SQLAlchemy ORM models (users, pois, lists, cache)
│   │   ├── middleware/
│   │   │   └── telemetry.py       # OpenTelemetry W3C trace propagation middleware
│   │   ├── schemas/
│   │   │   ├── auth.py            # User registration, login, and JWT schemas
│   │   │   ├── poi.py             # Pydantic models for POI records & collision
│   │   │   └── extraction.py      # LLM structured output schemas
│   │   └── services/
│   │       ├── auth.py            # Bcrypt hashing, JWT issuance & get_current_user
│   │       ├── extraction.py      # Gemini Flash-Lite structured JSON client
│   │       ├── geocoding.py       # Nominatim client with 1 req/s rate limit & cache
│   │       └── deduplication.py   # PostGIS spatial radius & trigram matching (user scoped)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
├── extension/                     # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── background/
│   │   ├── service_worker.js      # W3C trace injection & API dispatcher
│   │   ├── auth.js                # Cognito silent refresh & token mutex
│   │   └── telemetry.js           # W3C traceparent & Idempotency-Key
│   ├── content/
│   │   ├── content_script.js      # Selection listener & Shadow DOM modal injector
│   │   ├── overlay.css            # Scoped CSS styles for Shadow DOM form
│   │   └── parsers/               # Polymorphic site parsers (Maps, Roadtrippers, TripAdvisor)
│   ├── browser/                   # Full-tab POI Explorer workstation & CSV export
│   └── icons/                     # Vistarae compass icons (16, 48, 128)
├── native_host/                   # Chrome Native Messaging Host (Pure Python)
│   ├── folder_dispatcher.py       # 4-byte framed stdio dispatcher with UNC guards
│   ├── run_dispatcher.bat         # Windows python -u unbuffered launcher
│   └── com.vistarae.folder_opener.json # Native messaging host manifest
├── docker-compose.yml             # Local dev stack (FastAPI + PostGIS + Jaeger)
├── Makefile                       # Developer orchestration shortcuts
├── GEMINI.md                      # Project architectural rules & standards
└── README.md                      # Architecture overview and operational guide
```

---

## ⚡ Tech Stack & Operational Guardrails

- **Frontend**: Chrome Extension (Manifest V3), Vanilla JavaScript, CSS-isolated Shadow DOM.
- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy (asyncio) with asyncpg & GeoAlchemy2.
- **Database & Geospatial Engine**: PostgreSQL 16+ with PostGIS 3.4+ and `pg_trgm` extensions.
  - _Development_: Local Docker container (`postgis/postgis:16-3.4`).
  - _Production_: Supabase Free Tier (PostGIS enabled, connection via Transaction Pooler port 6543).
- **LLM Extraction**: Google Gemini Flash-Lite via Google AI Studio (`google-genai` SDK) utilizing strict JSON schema / Pydantic structured output. Reasoning/thinking budget set to `0` for low latency and minimal token usage.
- **Deterministic Geocoding**: OpenStreetMap Nominatim API (1 req/sec rate limit, custom User-Agent `VistaraeTravelEngine/1.0`, backed by an internal PostGIS `geocache` table with SHA256 hashing).
- **Distributed Observability**: OpenTelemetry W3C distributed tracing (`traceparent` header propagation), Jaeger tracing, and strict microservice message logging tags.

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

## 🔗 Downstream Systems (Future Scope)

1. **Photo Cataloging**: Embedding IPTC/EXIF location metadata into images based on GPS/time matching.
2. **Trip Planning**: Clustering POIs into daily itineraries using physical effort, duration, indoor/outdoor tags, and access points.
3. **Map Sharing**: Exporting GeoJSON layers with custom pins to Google My Maps, Leaflet, or Mapbox.
