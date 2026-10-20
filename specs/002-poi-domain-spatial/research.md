# Phase 0: Technical Research & Architecture Decisions

**Feature Identifier**: `002-poi-domain-spatial`  
**Date**: 2026-10-19  
**Status**: Completed  
**Author**: Antigravity

---

## 1. Executive Summary

This document records the architectural investigations, technology evaluations, and concrete engineering decisions required to implement Phase 2 (`002-poi-domain-spatial`). All decisions adhere strictly to `.specify/memory/constitution.md` (specifically Principle 2: Monorepo & Ports/Adapters, Principle 3: Database & Tenancy Invariants, Principle 4: Alembic Isolation, Principle 5: API Contracts, and Operational Invariant 2: Geospatial Storage & Coordinate Transformations).

---

## 2. Research Decisions

### Decision 1: PostGIS Dual-Index Separation & Spatial Query Casts

- **Decision**: Persist single point coordinates as `geography(Point, 4326)` in `pois.geom` and regional polygon boundaries as `geometry(MultiPolygon, 4326)` in `pois.region_geom`. Implement strict dual-index separation:
  1. **Planar Viewport Queries**: Cast `pois.geom` to geometry `(geom::geometry) && ST_MakeEnvelope(minLng, minLat, maxLng, maxLat, 4326)` backed by composite functional GiST index `idx_pois_user_geom_geometry` on `(user_id, (geom::geometry))`.
  2. **Geodesic Proximity Queries**: Execute `ST_DWithin(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography, radius_meters)` and `ST_Distance(...)` in meters backed by composite GiST index `idx_pois_user_geom` on `(user_id, geom)`.
- **Rationale**:
  - `geography` accurately calculates great-circle distances over large continental spans in SI meters without map projection distortion.
  - Bounding-box queries using PostGIS geometry bounding-box intersection operators (`&&` with `ST_MakeEnvelope`) on planar projections are up to 10x faster and naturally support 2D map tile viewports.
  - Creating a functional GiST index directly on `(user_id, (geom::geometry))` allows PostgreSQL to execute an index scan without re-casting at query execution time.
  - The `btree_gist` extension (already installed in Phase 1) enables composite GiST indexes pairing standard UUID equality (`user_id = :current_user_id`) with spatial geometry/geography indexing.
- **Alternatives Considered**:
  - _Storing geometry with SRID 3857 (Web Mercator)_: Rejected because distance calculations in Web Mercator distort heavily as latitude approaches the poles (e.g. northern Canada/Alaska).
  - _Single geography index for bounding boxes (`ST_Covers` or polygon casts)_: Rejected because geography polygon intersections are significantly more CPU-intensive and don't take advantage of fast bounding-box GiST bounding-tree intersection (`&&`).

---

### Decision 2: Deduplication Engine (Trigram Similarity + Proximity Filtering)

- **Decision**: Implement a two-stage deduplication probe in `POIRepository`:
  1. **Spatial Proximity Filter**: First prune candidates using `ST_DWithin(geom, :point::geography, :radius_meters)` with configurable presets: `80,467` meters (50 miles) for macro sites (national parks, mountain ranges) and `805` meters (0.5 miles) for urban sites (museums, cafes, viewpoints).
  2. **Trigram Similarity Scoring**: For candidates within the spatial envelope, evaluate PostgreSQL trigram similarity `similarity(name, :candidate_name) >= 0.60`. Enable `pg_trgm` extension in Alembic migration `0002_poi_domain_spatial.py` and create a GIN trigram index `idx_pois_name_trgm` on `pois USING gin (name gin_trgm_ops)`.
- **Rationale**:
  - Spatial filtering dramatically cuts down the candidate set before computing character n-gram similarities.
  - Trigram similarity (`pg_trgm`) is robust against typos, slight word-order inversions ("Yosemite NP" vs "Yosemite National Park"), and clipping discrepancies.
  - Presets (0.5 mi vs 50 mi) align with user mental models: two coffee shops 1 mile apart are distinct entities, but two records for "Yellowstone National Park" 20 miles apart represent the same destination.
- **Alternatives Considered**:
  - _Levenshtein Distance_: Rejected because it requires full table scans and does not scale efficiently without specialized indexing, whereas `pg_trgm` natively integrates with GiST/GIN indexes.
  - _Client-side deduplication_: Rejected because transferring thousands of user POIs over the wire violates network efficiency and exposes unneeded tenant coordinates.

---

### Decision 3: Atomic Interactive Merge & Hierarchy Cycle Prevention

- **Decision**: Execute `POST /api/pois/merge` inside a single PostgreSQL database transaction:
  1. Verify tenant ownership (`user_id = current_user_id`) for both `target_poi_id` (record to retain) and `source_poi_id` (record to delete).
  2. Perform cycle detection: Verify that `target_poi_id` is not currently a descendant of `source_poi_id`. If `target_poi_id` is a descendant, reject with RFC 7807 400 Bad Request.
  3. Re-parent all subordinate child POIs: Update all POIs with `parent_poi_id = source_poi_id` to `parent_poi_id = target_poi_id`.
  4. Attribute copy: Copy requested fields specified in `use_source_for` (e.g. description, website, images, rating) from source to target.
  5. List & Tag re-assignment: Transfer all `poi_lists` associations from source to target using `ON CONFLICT DO NOTHING`. If `merge_tags = true`, transfer `poi_tags` associations; if resulting tags exceed 30, raise RFC 7807 422 Unprocessable Content.
  6. Delete `source_poi_id` and recalculate `embedding_md5` on `target_poi_id`.
- **Rationale**:
  - Atomic transactions guarantee that network hiccups or constraint violations never leave orphaned child POIs, dangling list links, or partial merges.
  - Preventing circular hierarchies preserves the directed acyclic graph (DAG) structure of national parks, campuses, and multi-attraction complexes.
- **Alternatives Considered**:
  - _Soft-deleting source POI_: Rejected because user intent during merge is to permanently collapse duplicates into a single canonical record. Soft deletes add query overhead and complicate multi-column unique constraints.

---

### Decision 4: Token-Bucket Geocoding, Cache Keying & Mapbox Adapter

- **Decision**:
  1. Define `GeocodingPort` in `packages/core/vistarae_core/ports/geocoding.py` as a Python `typing.Protocol` with async methods `forward_geocode(query: str) -> GeocodingResult` and `reverse_geocode(lat: float, lon: float) -> GeocodingResult`.
  2. Implement `MapboxGeocodingAdapter` in `packages/core/vistarae_core/adapters/geocoding/mapbox.py` adhering to Mapbox Geocoding v5/v6 APIs, with `MockGeocodingAdapter` for local tests and CI.
  3. Wrap outbound calls in an in-memory asynchronous Token Bucket rate limiter enforcing a 1 request/second sustained rate per host to respect external rate limits.
  4. Implement persistent SHA-256 caching in `geocoding_cache`:
     - Forward queries: `sha256(re.sub(r'\s+', ' ', query.strip().lower()).encode('utf-8')).hexdigest()`.
     - Reverse queries: `sha256(f"{round(lat, 5)},{round(lon, 5)}".encode('utf-8')).hexdigest()`.
     - 90-day time-to-live (`expires_at = NOW() + INTERVAL '90 days'`).
     - Opportunistic eviction during insert: `DELETE FROM geocoding_cache WHERE expires_at <= NOW()`.
  5. Fallback & Resilience: Enforce a 3.0-second timeout. If timeout or provider failure occurs, persist user-supplied coordinates with `enrichment_status = 'PARTIAL'` and return HTTP 201/200 without raising a 500.
- **Rationale**:
  - SHA-256 query normalization prevents whitespace and case variations from generating duplicate external billable API hits.
  - 5 decimal places (`round(lat, 5)`) yields ~1.1 meter precision, which is more than sufficient for street-level reverse geocoding while ensuring stable cache keying.
  - Opportunistic eviction prevents unbounded growth of the `geocoding_cache` table without requiring external cron schedulers or Lambda event rules.
- **Alternatives Considered**:
  - _Redis for geocaching_: Rejected per Constitution Operational Invariant 3 (Zero-Cost Architecture) to avoid running additional managed cloud infrastructure or memory caches.
  - _OSM Nominatim directly in production_: Mapbox provides superior global address indexing and structured metadata; Mock/Nominatim can serve as local developer fallbacks.

---

### Decision 5: Gemini Embeddings, Canonical Payload Sanitization & HNSW Vector Indexing

- **Decision**:
  1. Define `EmbeddingPort` in `packages/core/vistarae_core/ports/embedding.py` as a Python `typing.Protocol` with async method `generate_embedding(text: str) -> list[float]`.
  2. Implement `GeminiEmbeddingAdapter` in `packages/core/vistarae_core/adapters/embedding/gemini.py` using `google-genai` SDK (`gemini-embedding-001` or `text-embedding-004`) configured for `768` dimensions. Provide `MockEmbeddingAdapter` with deterministic 768-dim mock vectors for unit/integration tests.
  3. Canonical text sanitization:
     - Name: `re.sub(r'\s+', ' ', name.strip())`
     - Description: Coalesce null to `""`, then `re.sub(r'\s+', ' ', desc.strip())`
     - Tags: Lowercase, trim, deduplicate, sort alphabetically, join with `", "`
     - Composite text: `f"{norm_name}\n{norm_desc}\nTags: {', '.join(norm_sorted_tags)}"`
     - Checksum: `embedding_md5 = md5(composite_text.encode('utf-8')).hexdigest()`
  4. Invalidation Bypass: On POI updates, compute `embedding_md5`. If unchanged, bypass the Gemini API call and preserve the existing vector.
  5. Database Vector Index: `CREATE INDEX idx_pois_embedding ON pois USING hnsw (embedding vector_cosine_ops)`. Cosine distance query: `pois.embedding.cosine_distance(query_vector)` with similarity score `1.0 - cosine_distance`.
  6. Outbound Retry Policy: Wrap Gemini calls in `tenacity` retry loop with 3 attempts and exponential jitter (500ms to 3000ms).
- **Rationale**:
  - MD5 hash caching completely eliminates redundant Gemini API costs and network latency when users update non-semantic fields (rating, visit state, estimated cost, duration).
  - Normalizing whitespace and sorting tags prevents spurious vector recalculations due to formatting differences.
  - HNSW (Hierarchical Navigable Small World) provides superior search recall and sub-millisecond query latency compared to IVFFlat for high-dimensional vectors.
- **Alternatives Considered**:
  - _IVFFlat Index_: Rejected because IVFFlat requires periodic retraining as data grows and performs poorly on cold/small datasets, whereas HNSW works instantly and accurately.
  - _384-dimensional miniLM_: Rejected because Gemini embeddings natively integrate with Google AI Studio SDK and provide 768-dimensional semantic depth.

---

### Decision 6: WGS-84 Canonical Storage & Shift Isolation

- **Decision**:
  - Canonical Storage: Database always persists coordinates in unshifted WGS-84 coordinate space (`EPSG:4326`).
  - Shift Isolation: The backend server never performs GCJ-02 or BD-09 coordinate transformations.
  - Coordinate transformations (`wgs84_to_gcj02`, `gcj02_to_wgs84`) are executed purely in the frontend single-page application and Chrome extension when rendering on Chinese map tiles (e.g. Amap/Baidu) if and only if coordinates fall within the China bounding box (`73.66°E <= lon <= 135.05°E` and `18.16°N <= lat <= 53.55°N`).
- **Rationale**:
  - Storing non-standard shifted coordinates in PostgreSQL corrupts PostGIS distance and spatial intersection calculations (`ST_Distance` on GCJ-02 coordinates produces mathematically incorrect distances).
  - Isolating shifts to client presentation layers guarantees that international GPS tracks, GPX imports, and open-source map tiles remain accurate.
- **Alternatives Considered**:
  - _Server-side transformation middleware_: Rejected because it introduces dual-coordinate state bugs and breaks idempotency when round-tripping coordinates through API updates.

---

### Decision 7: Multi-Tenancy Invariant Across Spatial Queries

- **Decision**:
  - Every spatial query on `pois`, `lists`, and `tags` must include `WHERE user_id = :current_user_id` as part of the query predicate.
  - Composite indexes `idx_pois_user_geom` and `idx_pois_user_geom_geometry` place `user_id` as the leading column (`USING gist (user_id, geom)` and `USING gist (user_id, (geom::geometry))`), ensuring PostgreSQL filters by tenant ID simultaneously with spatial bounds.
  - Public lists (`is_public = TRUE`) are accessed through a dedicated route `GET /api/lists/{id}/shared` that specifically permits cross-tenant read-only viewing of the list and its member POIs without exposing other private user data.
- **Rationale**:
  - Fulfills Constitution Principle 3 (Database, PgBouncer & Tenancy Invariants) preventing cross-tenant data leakage across shared connection pools.
  - Placing `user_id` in the composite spatial index guarantees fast multi-tenant partition pruning.
- **Alternatives Considered**:
  - _Separate spatial index per user_: Rejected because dynamic table or index creation per user does not scale in relational architectures.

---

### Decision 8: Alembic Migration Revision `0002_poi_domain_spatial.py`

- **Decision**:
  1. `upgrade()`:
     - Enable `pg_trgm` extension via `CREATE EXTENSION IF NOT EXISTS "pg_trgm"`.
     - Create tables: `pois`, `lists`, `tags`, `poi_lists`, `poi_tags`, `geocoding_cache`.
     - Add check constraints: `ck_pois_visit_state`, `ck_pois_rating`, `ck_pois_duration`, `ck_pois_enrichment`.
     - Create indexes:
       - `idx_pois_user_geom`: `USING gist (user_id, geom)`
       - `idx_pois_user_geom_geometry`: `USING gist (user_id, (geom::geometry))`
       - `idx_pois_embedding`: `USING hnsw (embedding vector_cosine_ops)`
       - `idx_pois_name_trgm`: `USING gin (name gin_trgm_ops)`
       - `idx_pois_parent_poi_id`: `(parent_poi_id)`
       - `idx_geocoding_cache_expires_at`: `(expires_at)`
  2. `downgrade()`:
     - Drop all created tables in strict reverse foreign-key dependency order: `poi_tags`, `poi_lists`, `tags`, `lists`, `pois`, `geocoding_cache`.
     - Drop `pg_trgm` extension conditionally if unused.
     - Fully reversible; no-op downgrade is strictly forbidden per Constitution Principle 4.
- **Rationale**:
  - Guarantees strict Alembic reversibility and ensures `alembic check` passes in CI.

---

### Decision 9: Multi-State and Multi-Country Modeling via JSONB Arrays & GIN Indexing

- **Decision**: Store states/provinces and sovereign countries as JSONB string arrays in columns `pois.states` (`JSONB NOT NULL DEFAULT '[]'::jsonb`) and `pois.countries` (`JSONB NOT NULL DEFAULT '[]'::jsonb`). Create dedicated GIN indexes `idx_pois_states_gin` and `idx_pois_countries_gin`. Implement Pydantic request normalization to accept both scalar strings (`state: "California"`) and array lists (`states: ["California", "Nevada"]`), normalizing all inputs to canonical lists of trimmed strings. Query filtering in `GET /api/pois?state=...&country=...` uses PostgreSQL JSONB containment (`states @> :state_json` and `countries @> :country_json`).
- **Rationale**:
  - Many natural travel destinations, national parks, mountain ranges, and scenic corridors physically cross administrative state lines (e.g., Yellowstone spanning Wyoming, Montana, and Idaho; Lake Tahoe spanning California and Nevada; Great Smoky Mountains spanning North Carolina and Tennessee; Four Corners Monument spanning Arizona, New Mexico, Utah, and Colorado) or international sovereign borders (e.g., Niagara Falls spanning the United States and Canada; Mont Blanc spanning France and Italy; Iguazu Falls spanning Argentina and Brazil).
  - Storing scalar `VARCHAR(100)` forces arbitrary truncation or lossy single-jurisdiction picking.
  - JSONB arrays align with existing schema patterns for `image_urls`, `directory_paths`, and `visited_dates`.
  - GIN indexes on JSONB arrays allow PostgreSQL to evaluate `@>` containment queries using index scans with sub-millisecond execution times.
- **Alternatives Considered**:
  - _Many-to-many junction tables (`poi_states`, `poi_countries`)_: Rejected because administrative subdivisions and country names are small, bounded sets of strings where junction tables add excessive join overhead and complexity without performance advantage.
  - _Delimited text string (e.g. "WY,MT,ID")_: Rejected because string matching with `LIKE '%MT%'` requires full table scans and leads to false positives (e.g., "MI" matching "Mississippi").
