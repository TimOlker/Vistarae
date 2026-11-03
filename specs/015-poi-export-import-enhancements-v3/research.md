# Technical Research: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Feature**: `015-poi-export-import-enhancements-v3`  
**Date**: 2026-11-02  
**Status**: Completed  

---

## 1. Research Objectives

1. Determine the exact international administrative address model to replace the US-centric address structure without breaking PostGIS geospatial queries, trigram duplicate detection, or existing frontend consumers.
2. Formulate deterministic Nominatim reverse geocode parsing and fallback rules for global POIs (urban centers, wilderness/natural landmarks, city-states, and UK constituent countries).
3. Investigate English language negotiation parameters across OpenStreetMap Nominatim forward and reverse endpoints.
4. Establish UX and state management patterns for a split-pane Import Staging Workbench in React/TypeScript with dynamic perspectives, MapLibre GL map integration, and additive deduplicated union merges.
5. Resolve all constitutional constraints (tenant isolation, PgBouncer compatibility, OpenAPI contract codegen, messaging tags, and rate limiting).

---

## 2. Technical Decisions & Analysis

### 2.1 International ISO Administrative Address Hierarchy

**Problem**: The legacy US-centric model (`street_address`, `city`, `state`, `country`, `zip_code`) fails on international administrative divisions:
- City-states (e.g. Singapore, Monaco, Vatican City) have no state/province or county.
- United Kingdom addresses split into constituent countries (England, Scotland, Wales, Northern Ireland) and post towns rather than conventional cities/states.
- Japan utilizes Prefectures and Wards/Cities; France uses Regions and Departments.
- Wilderness landmarks (e.g., Mount Fuji, trailheads) have no road or postal code.

**Resolution**: Adopt a two-tier ISO administrative schema:
- **Micro/Postal Layer**:
  - `street_address`: VARCHAR(255), Nullable (house number + road/pedestrian/footway).
  - `postal_code`: VARCHAR(20), Nullable (alphanumeric, e.g. "EC1A 1BB", "K1A 0B1", "111-0032").
  - `geom`: Geometry(Point, 4326), Not Null (spatial coordinates for GiST indexing).
- **Macro/Administrative Layer**:
  - `country_code`: CHAR(2), Not Null (ISO 3166-1 alpha-2 uppercase, e.g. "US", "GB", "JP", "FR", "SG").
  - `admin_level_1`: VARCHAR(100), Nullable (State, Province, Autonomous Region, Constituent Country).
  - `admin_level_2`: VARCHAR(100), Nullable (County, Department, Prefecture, District).
  - `locality`: VARCHAR(150), Nullable (City, Town, Municipality, Village).
  - `raw_geocoding`: JSONB, Nullable (verbatim provider payload for audit and future re-parsing).
- **Associated Media**:
  - `photo_directories`: JSONB / array of strings (local photo directories associated with the POI).
- **Indexing**:
  - Spatial GiST index on `geom`.
  - Composite B-tree index on `(country_code, admin_level_1, locality)` for multi-tier grouping and geographic queries.

---

### 2.2 Nominatim Ingestion & Fallback Transformation Chain

**Resolution**: Deterministic fallback chain in `AddressNormalizer.parse_nominatim_iso_address(raw)`:
```python
# 1. Street Address
house_num = addr.get("house_number")
road = addr.get("road") or addr.get("pedestrian") or addr.get("footway")
street_address = f"{house_num} {road}".strip() if (house_num and road) else (road or None)

# 2. Postal Code
postal_code = addr.get("postcode") or None

# 3. Country Code
country_code = (addr.get("country_code") or "US").strip().upper()[:2]

# 4. Admin Level 1 (State/Province/Constituent Country)
admin_level_1 = (
    addr.get("state")
    or addr.get("province")
    or addr.get("region")
    or addr.get("state_district")
    or None
)

# 5. Admin Level 2 (County/Department/District)
admin_level_2 = (
    addr.get("county")
    or addr.get("district")
    or addr.get("department")
    or None
)

# 6. Locality (City/Town/Municipality/Village)
locality = (
    addr.get("city")
    or addr.get("town")
    or addr.get("municipality")
    or addr.get("village")
    or addr.get("hamlet")
    or addr.get("suburb")
    or None
)
```
- Whitespace trimming and conversion of empty strings (`""`) to `None`.
- Tested against standard urban, remote wilderness, city-state, and UK benchmark locations.

---

### 2.3 English Language Geocoding Negotiation

**Resolution**: OSM Nominatim supports standard HTTP Content Negotiation and query parameters:
- Header: `Accept-Language: en`
- Query Parameter: `accept-language=en`
- Configured across both `geocode_service.py` (reverse geocoding) and `geocoding_service.py` (forward geocoding).
- Nominatim returns English name keys (`name:en`, `int_name`) when available, falling back cleanly to canonical Latin transliteration when English translations are absent in OpenStreetMap.

---

### 2.4 MapLibre GL Integration & Map Relocation

**Resolution**:
- Implement `WorkbenchMap.tsx` embedding MapLibre GL with vector/raster tiles.
- Render candidate coordinate marker with draggable capability.
- Dragging pin or clicking map updates `latitude` and `longitude` form fields immediately.
- To prevent destructive overwrites of manual address edits, provide a non-destructive **"Re-sync Address from Pin"** button that explicitly triggers reverse geocoding on demand.
- Dynamic Proximity Plotting: Query nearby points within the "Nearby Search Radius" slider (from DB and active import batch, excluding ignored/excluded), rendering color-coded pins and updating a count badge.

---

### 2.5 In-Batch Merge & Attribute Blending Policy

**Resolution**:
- When a candidate's disposition is `in_batch_merge`, the detail editor renders an In-Batch Merge Card with a selector to pick the target candidate in the active batch.
- On DB commit, the ingestion engine performs an additive deduplicated union merge:
  - `dates_visited`: union of distinct dates sorted chronologically.
  - `tags`: union of distinct tag names.
  - `photo_directories`: union of distinct file directory paths.
  - `related_websites`: union of distinct `{ name, url }` pairs keyed by URL.

---

### 2.6 AI Enrichment Idempotency & "No Websites" Policy

**Resolution**:
- If `len(candidate.related_websites) >= 1` or `candidate.no_websites is True`, the enrichment worker bypasses external website scraping entirely, preserving existing links.
- If `len(candidate.related_websites) == 0` and `candidate.no_websites is False`, the worker queries external sources; if 0 websites are discovered, it sets `no_websites = True` automatically.

---

### 2.7 Tag Library Strict Selection Policy

**Resolution**:
- Fetch vetted tags from `/api/tags`.
- Render interactive chip pills: clicked chips toggle active/inactive states on the candidate.
- In compliance with clarification Q3 (Option B), tag assignment is strictly constrained to existing library tags; ad-hoc tag creation is disallowed within the workbench modal to maintain tag governance.

---

## 3. Constitutional Guardrail Compliance

| Constitution Principle | Enforcement Mechanism |
| :--- | :--- |
| **Principle 1**: File Headers & Pre-Commit | Apache 2.0 license headers on all `.py`, `.ts`, `.tsx`, and `.sql` files. Google-style docstrings with explicit sections. Max 3 indentation levels. |
| **Principle 2**: Ports & Adapters Architecture | Shared domain entities (`POI`, `IngestCandidate`), value objects (`AddressRecord`), and port interfaces defined in `packages/core`. |
| **Principle 3**: Tenant Isolation & PgBouncer | Every SQL query explicitly filters `user_id == current_user_id`. Spatial coordinates stored in `GEOGRAPHY(Point, 4326)` with GiST indexes. |
| **Principle 4**: Alembic Migrations | Revision `0016` adds ISO address columns and indexes linearly without destructive mutations. |
| **Principle 5**: API Contracts & Error Standards | Pydantic v2 boundary schemas with `StrictBaseModel`, RFC 7807 problem details, and TypeScript contract generation via `openapi-typescript`. |
| **Principle 6**: Middleware & Rate Limiting | W3C tracing (`traceparent`, `X-Source`, `X-Destination`), Nominatim policy compliance (1 req/sec, User-Agent `VistaraeTravelEngine/1.0`, internal SHA256 geocache). |
| **Principle 7**: Observability & Messaging Protocol | Structured logging using messaging tags: `MSG ->|`, `MSG <-|`, `MSG   |->`, `MSG   |<-`. |
| **Principle 8**: PyTest & SDD Governance | Comprehensive unit and integration test coverage across ingest, poi, and worker services. Zero regressions. |
