# GEMINI.md - Vistarae Project Rules & Architecture Context

## Project Overview
Vistarae (`vistarae`) is a travel dream and point-of-interest (POI) capture platform. It empowers travelers to capture scenic overlooks, trails, experiences, and travel dreams from across the web via a Manifest V3 Chrome Extension, enrich and geocode them via FastAPI, and store them in PostgreSQL/PostGIS.

## Core Rules & Invariants

### 1. Telemetry & W3C Distributed Tracing
- Every request initiated by the Chrome Extension must include standard W3C headers:
  - `traceparent: 00-{trace_id}-{client_span_id}-01`
  - `X-Source: chrome-extension://vistarae`
  - `X-Destination: {BACKEND_API_URL}`
- FastAPI `telemetry.py` middleware extracts the W3C context, instantiates a server span, and logs:
  `INCOMING | TraceID={trace_id} | SpanID={span_id} | ParentID={parent_span_id} | Source={source} -> Destination={destination}`
- Correlation headers attached to all backend responses:
  - `X-Transaction-ID: {trace_id}`
  - `X-Current-Span-ID: {span_id}`
  - `X-Parent-Transaction-ID: {parent_span_id}`
- **Messaging Tags Protocol**:
  All messages sent or received across microservice boundaries, to LLMs, to external APIs, or between the Chrome Extension and backend MUST log with the exact tag format:
  - Received by service / inbound message: `MSG ->|  `
  - Response to a message sent out: `MSG <-|  `
  - Outbound message sent: `MSG   |->`
  - Response to an outbound message received: `MSG   |<-`

### 2. LLM Extraction
- Extraction uses Google Gemini Flash-Lite via Google AI Studio (`google-genai` SDK).
- `thinking_budget` MUST be explicitly set to `0` for low-latency, deterministic, cost-efficient entity extraction.
- Extraction MUST use structured JSON output enforcing Pydantic schemas.

### 3. Geocoding & Rate Limiting
- Deterministic geocoding uses OpenStreetMap Nominatim.
- Strictly adhere to OSM Nominatim policy:
  - 1 request per second max.
  - Custom `User-Agent: VistaraeTravelEngine/1.0`.
  - Check internal PostGIS `geocache` table (SHA256 of normalized address string) before making any outbound HTTP request.

### 4. Database & Geospatial Engine
- PostgreSQL 16+ with `postgis` (3.4+), `pg_trgm`, and `uuid-ossp` extensions.
- All spatial coordinates stored in `GEOGRAPHY(Point, 4326)` with GiST spatial indexes.
- Trigram similarity indexes on `pois.name` (`gin_trgm_ops`).
- Deduplication and nesting classification:
  - `POTENTIAL_DUPLICATE`: Distance $\le$ radius AND similarity $\ge 0.60$.
  - `NEARBY_PARENT`: Distance $\le$ radius AND similarity $< 0.60$ AND macro-site candidate.
  - `UNIQUE_LOCATION`: No records within spatial radius.

### 5. Chrome Extension (Manifest V3)
- Pure Vanilla JS without heavy framework runtimes.
- Content script injects an isolated Shadow DOM container to prevent host website CSS collisions.
- Keyboard trigger: `Ctrl+Shift+S` (Windows/Linux) or `Command+Shift+S` (Mac), alongside Context Menu item.
