# Feature Specification: Point of Interest Domain & Geospatial Engine

**Feature Identifier**: `002-poi-domain-spatial`  
**Feature Branch**: `002-poi-domain-spatial`  
**Created**: 2026-10-19  
**Status**: Draft  
**Target Systems**: Vistarae Core (`packages/core`), POI Service (`services/poi`), Database (PostgreSQL 16 / PostGIS / pgvector / Alembic), Geocoding (Mapbox v5/v6), AI Embeddings (Google Gemini Flash / Text Embedding)

---

## 1. Executive Summary & Context

Phase 2 (`002-poi-domain-spatial`) establishes the core Point of Interest (POI) domain, geospatial engine, and semantic search layer for the Vistarae platform. Building directly on the Phase 1 multi-tenant foundation, rate-limiting, and idempotency framework, Phase 2 implements rich POI management, hierarchical nesting (parent/child relationships for complex parks and campuses), bounding-box planar viewport queries, combinable multi-facet filtering, bulk lifecycle operations, collaborative sharing, deterministic deduplication and interactive record merging, token-bucket geocoding with a 90-day SHA-256 query cache, and 768-dimensional vector embeddings with HNSW cosine similarity search.

---

## Clarifications

### Session 2026-10-19

- Q: How should the system handle subordinate child POIs when their parent record (`source_poi_id`) is merged into another POI (`target_poi_id`)? → A: Atomically re-parent all child POIs of `source_poi_id` to point to `target_poi_id` within the merge transaction, rejecting the transaction with RFC 7807 400 Bad Request if it would introduce a circular hierarchy.
- Q: How should PostGIS data types, indexes, and queries distinguish between planar viewport lookups and geodesic proximity calculations? → A: Strict Dual-Indexed Separation: Viewport queries strictly cast `(geom::geometry)` and use `ST_MakeEnvelope` in degrees backed by functional GiST index `idx_pois_user_geom_geometry`; proximity, radius filters, and distance sorting strictly use `geography` in meters with `ST_DWithin` and `ST_Distance` backed by `idx_pois_user_geom`, explicitly casting input query coordinates to `ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography`.
- Q: How should the system normalize text attributes and null values before computing the `embedding_md5` hash and dispatching vector generation requests to Google Gemini? → A: Canonical Sanitization: Coalesce null descriptions to `""`, collapse multi-whitespace runs in name and description (`re.sub(r'\s+', ' ', text.strip())`), deduplicate and lower-case tags in alphabetical order, and compute MD5 on the resulting UTF-8 composite payload `f"{norm_name}\n{norm_desc}\nTags: {', '.join(norm_sorted_tags)}"`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planar Viewport POI Exploration & Combinable Filtering (Priority: P1)

As a traveler exploring an interactive map, I need to rapidly fetch all saved POIs within my current screen viewport, optionally filtered by visit status, custom tags, lists, and hierarchical depth, so that I can visually plan my itinerary without interface lag or information overload.

**Why this priority**: Viewport-based map navigation is the primary user interaction in Vistarae. Without performant bounding-box queries and multi-facet filtering, the interactive map cannot render.

**Independent Test**: Can be fully tested by creating 10 POIs across various geographic locations and issuing `GET /api/pois?bbox=minLng,minLat,maxLng,maxLat&visit_state=not_visited&hierarchy=root_only`, verifying that only points matching both spatial envelope and filter criteria return in under 100ms.

**Acceptance Scenarios**:
1. **Given** a user has 50 POIs saved across North America, **When** the client submits `GET /api/pois?bbox=-120.0,37.0,-119.0,38.0`, **Then** the system returns only the POIs whose coordinates fall within that geographic envelope with HTTP 200.
2. **Given** a user filters by tag "scenic" and visit state "not_visited", **When** querying with an active viewport bounding box, **Then** the system returns the intersection of viewport containment, tag association, and visit state matching.
3. **Given** a user selects `hierarchy=root_only`, **When** querying POIs in a region containing a National Park and its subordinate viewpoints, **Then** only the top-level parent POI returns, omitting child overlooks.

---

### User Story 2 - Deduplication Detection & Interactive Record Merge (Priority: P2)

As a traveler capturing locations from multiple blogs and guides, I want the system to flag potential duplicates based on name similarity and geographic proximity, and allow me to interactively merge conflicting records attribute-by-attribute so that I keep a clean, unified travel log.

**Why this priority**: Travelers frequently clip the same attraction under slightly different titles (e.g., "Yosemite National Park" vs "Yosemite NP - Valley Floor"). An interactive merge engine prevents database clutter while giving the user absolute authority over which attributes, URLs, and photos to preserve.

**Independent Test**: Can be tested by posting two POIs located within 0.2 miles with similar names, executing a deduplication probe to verify collision reporting, and executing `POST /api/pois/merge` to verify the kept POI retains selected attributes while the duplicate is removed with foreign keys reassigned.

**Acceptance Scenarios**:
1. **Given** two existing POIs belonging to the user within 500 meters of each other, **When** the user checks for duplicates, **Then** the system returns them as potential duplicates with geodesic distance and match confidence.
2. **Given** two duplicate POIs (Source A and Source B), **When** the user calls `/api/pois/merge` specifying `target_poi_id=A`, `source_poi_id=B`, keeping Description from A, Website from B, and unioning all Tags, **Then** the system updates A with the selected fields, deletes B, re-links all list memberships, and logs the merge transaction.

---

### User Story 3 - Cached, Rate-Limited Geocoding & Address Resolution (Priority: P3)

As a traveler saving a scenic overlook by address or coordinates, I need the system to enrich the location with canonical coordinates and standardized addresses without exhausting external geocoding API rate limits or failing when offline.

**Why this priority**: Accurate spatial coordinates are required for distance calculations and map rendering. Robust caching and rate limiting prevent cost overruns and vendor rate throttling.

**Independent Test**: Can be tested by geocoding the same address query twice; the first request executes an outbound provider call and writes to `geocoding_cache`, while the second returns immediately from the database cache with zero outbound network traffic.

**Acceptance Scenarios**:
1. **Given** an address string not yet present in `geocoding_cache`, **When** geocoding is requested, **Then** the system queries the external provider, stores the result with a 90-day expiration timestamp, and sets enrichment status to `SUCCESS`.
2. **Given** a query whose normalized SHA-256 hash exists in `geocoding_cache` and `expires_at > NOW()`, **When** geocoding is requested, **Then** the system returns the cached coordinates and formatted address without making an outbound HTTP request.
3. **Given** an external geocoding provider times out after 3 seconds, **When** creating a POI with raw user-supplied coordinates, **Then** the POI is saved with `enrichment_status = 'PARTIAL'` and the operation succeeds without blocking the user.

---

### User Story 4 - Semantic & Vector Similarity POI Discovery (Priority: P4)

As a traveler seeking inspiration from my saved places, I want to search for conceptual experiences (e.g., "secluded misty waterfalls with easy hiking") and receive relevant POIs even if the exact words do not appear in the title, powered by high-dimensional vector embeddings.

**Why this priority**: Keyword search fails when users describe moods, terrain types, or activity vibes. Vector search unlocks conversational and conceptual retrieval across travel dreams.

**Independent Test**: Can be tested by creating POIs with narrative descriptions of alpine vistas, generating 768-dimensional embeddings, and querying `/api/pois?semantic_q=misty+mountain+views`, verifying that the top cosine similarity matches rank highest.

**Acceptance Scenarios**:
1. **Given** a new POI is created with a name, description, and tags, **When** persisted, **Then** the system computes an MD5 checksum of the normalized content, generates a 768-dimensional embedding via Gemini, and stores both on the record.
2. **Given** an existing POI receives an update modifying only its `rating`, **When** updated, **Then** the system verifies the `embedding_md5` is unchanged and bypasses external embedding generation.
3. **Given** a user queries `/api/pois?semantic_q=waterfall`, **When** evaluated, **Then** the database uses the HNSW cosine similarity index to return ranked POIs with similarity distance scores.

---

### User Story 5 - Bulk Organization & Collaborative Sharing (Priority: P5)

As a traveler organizing a group trip, I need to perform bulk tagging, bulk list assignments, bulk deletions, and generate public or user-specific share links for my curated lists and POIs.

**Why this priority**: Travel planning is inherently collaborative. Managing points individually becomes tedious when curating dozens of stops for an upcoming journey.

**Independent Test**: Can be tested by selecting 5 POIs, executing `POST /api/pois/bulk-tags` to add "roadtrip-2026", and verifying all 5 records reflect the new tag association in a single atomic transaction.

**Acceptance Scenarios**:
1. **Given** a user owns 10 POIs, **When** submitting a bulk tag request with 10 POI IDs and tag "Summer2026", **Then** all 10 POIs are linked to that tag atomically.
2. **Given** a user generates a share link for a list marked `is_public = TRUE`, **When** a secondary authenticated user accesses the shared list URL, **Then** the system returns the list details and member POIs in read-only mode.

---

### Edge Cases

- **Meridian & Antimeridian Bounding Boxes**: When a viewport crosses longitude +180° / -180° (e.g. Fiji or Chukotka), the bounding box minLng is greater than maxLng. The system splits the envelope into two disjoint polygons joined with `OR` or `ST_Collect`.
- **Poles & Latitude Limits**: Latitude inputs are constrained to `[-90.0, 90.0]` and longitude to `[-180.0, 180.0]`; out-of-bounds envelopes reject immediately with RFC 7807 422.
- **Tag-Bloat Defense**: A single POI cannot have more than 30 tags attached, and tag names are restricted to 64 characters, lower-cased and stripped of leading/trailing whitespace.
- **Hierarchical Cycle Prevention**: Setting `parent_poi_id` on POI A to POI B must verify that B is not already a descendant of A; recursive loop attempts return RFC 7807 400 Bad Request.
- **Child POI Merge Re-Parenting**: When merging `source_poi_id` into `target_poi_id`, all child POIs referencing `source_poi_id` are atomically updated to reference `target_poi_id`. If `target_poi_id` is a descendant of `source_poi_id`, the merge is rejected to prevent a circular hierarchy.
- **Chinese Shifted Coordinate Handling**: Coordinates within the China bounding box (`73.66°E to 135.05°E, 18.16°N to 53.55°N`) remain canonical WGS-84 in database storage; client-side transforms are applied strictly at the browser presentation layer.
- **Opportunistic Cache Eviction**: Expired geocaching rows (`expires_at <= NOW()`) are opportunistically pruned during cache insertions to prevent unbounded disk growth.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Point of Interest Domain & Lifecycle (`REQ-POI-xxx`)

- **REQ-POI-001 (Ubiquitous):** The database schema shall persist Points of Interest in a table named `pois` containing `id UUID PK`, `user_id UUID REFERENCES users(id) ON DELETE CASCADE`, `parent_poi_id UUID NULL REFERENCES pois(id) ON DELETE SET NULL`, `name VARCHAR(255) NOT NULL`, `description TEXT NULL`, `address VARCHAR(500) NULL`, `city VARCHAR(100) NULL`, `states JSONB NOT NULL DEFAULT '[]'::jsonb`, `countries JSONB NOT NULL DEFAULT '[]'::jsonb`, `official_url TEXT NULL`, `wiki_url TEXT NULL`, `image_urls JSONB NOT NULL DEFAULT '[]'::jsonb`, `directory_paths JSONB NOT NULL DEFAULT '[]'::jsonb`, `creation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `visit_state VARCHAR(32) NOT NULL DEFAULT 'not_visited'`, `visited_dates JSONB NOT NULL DEFAULT '[]'::jsonb`, `rating INT NULL`, `estimated_cost DECIMAL(10,2) NULL`, `pricing_unit VARCHAR(16) NULL`, `recommended_duration_hours DECIMAL(4,2) NULL`, `recommended_visit_days INT NOT NULL DEFAULT 1`, `enrichment_status VARCHAR(16) NOT NULL DEFAULT 'SUCCESS'`, `geom geography(Point, 4326) NOT NULL`, `region_geom geometry(MultiPolygon, 4326) NULL`, `embedding vector(768) NULL`, `embedding_md5 VARCHAR(32) NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. `states` and `countries` shall store arrays of strings to natively support destinations spanning multiple administrative territories (e.g., Yellowstone spanning Wyoming, Montana, and Idaho) or sovereign borders (e.g., Niagara Falls spanning the United States and Canada).
- **REQ-POI-002 (Ubiquitous):** The database schema shall enforce check constraint `ck_pois_visit_state` ensuring `visit_state IN ('not_visited', 'visited_do_not_return', 'visited_return')`.
- **REQ-POI-003 (Ubiquitous):** The database schema shall enforce check constraint `ck_pois_rating` ensuring `rating IS NULL OR (rating >= 0 AND rating <= 5)`.
- **REQ-POI-004 (Ubiquitous):** The database schema shall enforce check constraint `ck_pois_duration` ensuring `recommended_duration_hours IS NULL OR (recommended_duration_hours >= 0.25 AND recommended_duration_hours <= 12.00)`.
- **REQ-POI-005 (Ubiquitous):** The database schema shall enforce check constraint `ck_pois_enrichment` ensuring `enrichment_status IN ('SUCCESS', 'PARTIAL', 'FAILED')`.
- **REQ-POI-006 (Ubiquitous):** The database schema shall persist user-defined curated lists in table `lists` (`id UUID PK`, `user_id UUID REFERENCES users(id) ON DELETE CASCADE`, `title VARCHAR(200) NOT NULL`, `description TEXT NULL`, `is_public BOOLEAN NOT NULL DEFAULT FALSE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`) and association table `poi_lists` (`poi_id UUID REFERENCES pois(id) ON DELETE CASCADE`, `list_id UUID REFERENCES lists(id) ON DELETE CASCADE`, `added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `PRIMARY KEY (poi_id, list_id)`).
- **REQ-POI-007 (Ubiquitous):** The database schema shall persist user tags in table `tags` (`id UUID PK`, `user_id UUID REFERENCES users(id) ON DELETE CASCADE`, `name VARCHAR(64) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `UNIQUE (user_id, name)`) and association table `poi_tags` (`poi_id UUID REFERENCES pois(id) ON DELETE CASCADE`, `tag_id UUID REFERENCES tags(id) ON DELETE CASCADE`, `PRIMARY KEY (poi_id, tag_id)`).
- **REQ-POI-008 (Event-Driven):** When a client requests `GET /api/pois`, the system shall accept combinable query parameters: `bbox` (minLng,minLat,maxLng,maxLat), `list_id`, `tag_ids` (comma-separated), `state`, `country`, `visit_state`, `visited_from`, `visited_to`, `hierarchy` (`all`, `root_only`, `children_only`), `parent_id`, `q` (text search), `semantic_q` (vector search), `limit` (default 50, max 200), and `offset` (default 0). When `state` or `country` is specified, the repository shall query using JSONB containment (`states @> :state_json` or `countries @> :country_json`).
- **REQ-POI-009 (Event-Driven):** When evaluating `bbox` queries, the repository query builder shall construct the planar bounding-box filter using `(geom::geometry) && ST_MakeEnvelope(minLng, minLat, maxLng, maxLat, 4326)` to utilize functional GiST index `idx_pois_user_geom_geometry`.
- **REQ-POI-010 (Event-Driven):** When `hierarchy=root_only` is specified, the repository shall append `WHERE parent_poi_id IS NULL` to the query.
- **REQ-POI-011 (Event-Driven):** When `hierarchy=children_only` is specified, the repository shall append `WHERE parent_poi_id IS NOT NULL` to the query.
- **REQ-POI-012 (Unwanted Behaviour):** If a client attempts to set `parent_poi_id` to the POI's own ID or creates a cyclic hierarchy, then the service shall reject the mutation with an RFC 7807 400 Bad Request error.
- **REQ-POI-013 (Unwanted Behaviour):** If a client associates more than 30 tags with a single POI, then the service shall reject the mutation with an RFC 7807 422 Unprocessable Content error.
- **REQ-POI-014 (Event-Driven):** When a client executes `POST /api/pois/bulk-delete`, the system shall delete all specified POIs owned by `current_user_id` in a single transaction, cascading deletions to `poi_lists`, `poi_tags`, and child POIs (`parent_poi_id` set to null).
- **REQ-POI-015 (Event-Driven):** When a client executes `POST /api/pois/bulk-tags`, the system shall add or remove specified tag IDs across an array of POI IDs owned by `current_user_id` in a single transaction.
- **REQ-POI-016 (Event-Driven):** When a client executes `POST /api/pois/bulk-lists`, the system shall assign or remove specified list IDs across an array of POI IDs owned by `current_user_id` in a single transaction.
- **REQ-POI-017 (Event-Driven):** When a client requests `GET /api/pois/dedup-check`, the system shall scan the user's POIs for potential duplicates matching both trigram name similarity (`similarity(name, :candidate_name) >= 0.60`) and geodesic proximity (`ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_meters)`) utilizing GiST index `idx_pois_user_geom`.
- **REQ-POI-018 (State-Driven):** While performing deduplication checks, the system shall apply configurable proximity presets: 80,467 meters (50 miles) for macro sites (national parks, mountain ranges) and 805 meters (0.5 miles) for urban sites (museums, cafes, viewpoints).
- **REQ-POI-019 (Event-Driven):** When a client calls `POST /api/pois/merge`, the system shall accept `target_poi_id` (kept), `source_poi_id` (deleted), and attribute resolution rules (`use_source_for: list[str]` and `merge_tags: bool`), atomically copying chosen attributes from source to target, unioning tags and lists, re-parenting any child POIs referencing `source_poi_id` to `target_poi_id` (rejecting with RFC 7807 400 Bad Request if creating a cycle), deleting the source record, and returning the updated target POI.
- **REQ-POI-020 (Event-Driven):** When a list has `is_public = TRUE` and a user accesses `GET /api/lists/{id}/shared`, the system shall return the list metadata and member POIs without requiring list ownership.

---

#### Geospatial Storage, Indexes & Geocoding (`REQ-GEO-xxx`)

- **REQ-GEO-001 (Ubiquitous):** The database schema shall store point coordinates in column `pois.geom` using `geography(Point, 4326)` and regional boundary polygons in `pois.region_geom` using `geometry(MultiPolygon, 4326)`.
- **REQ-GEO-002 (Ubiquitous):** The database schema shall create composite GiST index `idx_pois_user_geom` on `pois USING gist (user_id, geom)` to optimize geodesic proximity filters (`ST_DWithin`) and geodesic distance calculations (`ST_Distance`).
- **REQ-GEO-003 (Ubiquitous):** The database schema shall create functional composite GiST index `idx_pois_user_geom_geometry` on `pois USING gist (user_id, (geom::geometry))` strictly to optimize planar 2D bounding-box queries (`ST_MakeEnvelope`).
- **REQ-GEO-004 (Ubiquitous):** The database schema shall create GIN indexes `idx_pois_states_gin` on `pois USING gin (states)` and `idx_pois_countries_gin` on `pois USING gin (countries)` to accelerate JSONB containment queries (`@>`).
- **REQ-GEO-005 (Ubiquitous):** The database schema shall persist geocoding responses in table `geocoding_cache` containing `query_hash VARCHAR(64) PRIMARY KEY`, `lat DOUBLE PRECISION NOT NULL`, `lon DOUBLE PRECISION NOT NULL`, `formatted_address TEXT NOT NULL`, `status VARCHAR(16) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `expires_at TIMESTAMPTZ NOT NULL`.
- **REQ-GEO-006 (Ubiquitous):** The database schema shall create index `idx_geocoding_cache_expires_at` on `geocoding_cache(expires_at)`.
- **REQ-GEO-007 (Event-Driven):** When hashing an address search query for geocaching, the geocoder shall compute the SHA-256 digest of normalized string `re.sub(r'\s+', ' ', query.strip().lower())`.
- **REQ-GEO-008 (Event-Driven):** When hashing latitude/longitude coordinates for reverse geocaching, the geocoder shall compute the SHA-256 digest of `f"{round(lat, 5)},{round(lon, 5)}"`.
- **REQ-GEO-009 (Ubiquitous):** The geocoding system shall set `expires_at` on new `geocoding_cache` entries to exactly 90 days from the insertion timestamp (`NOW() + INTERVAL '90 days'`).
- **REQ-GEO-010 (Event-Driven):** When resolving an address or coordinate, the geocoder shall inspect `geocoding_cache` where `query_hash = :hash AND expires_at > NOW()`; if a row exists, the system shall return cached coordinates and address without dispatching external network requests.
- **REQ-GEO-011 (Event-Driven):** When a cache miss occurs, the geocoder shall invoke the external provider via `GeocodingPort` through a 1-request-per-second token-bucket rate limiter.
- **REQ-GEO-012 (Unwanted Behaviour):** If the external geocoding provider fails or exceeds a 3.0-second timeout, then the system shall fall back to user-provided coordinates, record `enrichment_status = 'PARTIAL'`, and complete the POI insertion without raising a 500 error.
- **REQ-GEO-013 (Event-Driven):** When inserting a new record into `geocoding_cache`, the database adapter shall execute an opportunistic cleanup statement: `DELETE FROM geocoding_cache WHERE expires_at <= NOW()`.
- **REQ-GEO-014 (Ubiquitous):** The core package shall define `GeocodingPort` as a Python `typing.Protocol` with async methods `forward_geocode(query: str) -> GeocodingResult` and `reverse_geocode(lat: float, lon: float) -> GeocodingResult`, where `GeocodingResult` returns `states: list[str]` and `countries: list[str]`.
- **REQ-GEO-015 (Ubiquitous):** The POI service shall provide a concrete `MapboxGeocodingAdapter` implementing `GeocodingPort` compatible with Mapbox Geocoding v5 and v6 APIs.
- **REQ-GEO-016 (State-Driven):** While processing coordinates located inside the China bounding box (`73.66°E <= lon <= 135.05°E` and `18.16°N <= lat <= 53.55°N`), the system shall persist canonical WGS-84 coordinates in the database without applying server-side GCJ-02 or BD-09 offsets.

---

#### AI Embeddings & Vector Search (`REQ-EMBED-xxx`)

- **REQ-EMBED-001 (Ubiquitous):** The database schema shall create an HNSW index `idx_pois_embedding` on `pois USING hnsw (embedding vector_cosine_ops)` to accelerate approximate nearest-neighbor vector similarity lookups.
- **REQ-EMBED-002 (Ubiquitous):** The core package shall define `EmbeddingPort` as a Python `typing.Protocol` with async method `generate_embedding(text: str) -> list[float]`.
- **REQ-EMBED-003 (Ubiquitous):** The system shall provide a concrete `GeminiEmbeddingAdapter` implementing `EmbeddingPort` using the `google-genai` SDK with configurable model name (defaulting to `gemini-embedding-001` or `text-embedding-004`) and `EmbedContentConfig(output_dimensionality=768)`.
- **REQ-EMBED-004 (Event-Driven):** When constructing the text payload for POI embedding, the adapter shall perform canonical sanitization: coalescing null or missing `description` to empty string `""`, collapsing multi-whitespace runs in name and description (`re.sub(r'\s+', ' ', text.strip())`), and lower-casing, whitespace-trimming, deduplicating, and sorting all tags alphabetically into composite template `f"{norm_name}\n{norm_desc}\nTags: {', '.join(norm_sorted_tags)}"`.
- **REQ-EMBED-005 (Event-Driven):** When persisting or updating a POI, the system shall compute `embedding_md5` as the MD5 hex digest of the UTF-8 encoded canonical composite text payload.
- **REQ-EMBED-006 (State-Driven):** While executing a POI update mutation, if the newly calculated `embedding_md5` matches the existing record's `embedding_md5`, then the system shall bypass the `EmbeddingPort` external call and preserve the existing vector.
- **REQ-EMBED-007 (Event-Driven):** When calling the Gemini Embedding API, the adapter shall wrap the outbound request in a `tenacity` retry loop executing 3 attempts with exponential backoff and randomized jitter (initial 500ms, max 3000ms).
- **REQ-EMBED-008 (Unwanted Behaviour):** If all 3 embedding retry attempts fail, then the service shall set `embedding = NULL`, log the failure with OpenTelemetry trace context, and return an RFC 7807 503 Service Unavailable or fallback to partial enrichment depending on whether embedding generation was synchronous or deferred.
- **REQ-EMBED-009 (Event-Driven):** When a client query includes `semantic_q`, the system shall generate a 768-dimensional query embedding via `EmbeddingPort` and execute a cosine distance query using SQLAlchemy vector operator `pois.embedding.cosine_distance(query_vector)`.
- **REQ-EMBED-010 (Event-Driven):** When returning semantic search results, the response schema shall include `similarity_score` calculated as `1.0 - cosine_distance` normalized between 0.0 and 1.0.

---

### Key Entities *(include if feature involves data)*

- **`pois`**: Point of Interest representing a physical travel dream, scenic overlook, trail, or destination. Bound to a tenant `user_id`, optionally referencing a parent POI (`parent_poi_id`), carrying geography coordinates (`geom`), optional regional polygon boundaries (`region_geom`), 768-dimensional AI semantic vector (`embedding`), and visit tracking metadata.
- **`lists`**: Curated itinerary collections (e.g., "Pacific Coast Highway 2026", "Tokyo Coffee Tour") owned by a user, with support for public sharing.
- **`tags`**: Normalized taxonomy markers (e.g., "viewpoint", "waterfall", "sunset", "moderate-hike") scoped per user, limited to 30 per POI to prevent tag bloat.
- **`poi_lists`**: Composite many-to-many relationship linking POIs to lists with addition timestamps.
- **`poi_tags`**: Composite many-to-many relationship linking POIs to tags.
- **`geocoding_cache`**: Shared, persistent geocoding cache keyed by SHA-256 query hash, storing resolved coordinates and standardized addresses with a 90-day time-to-live (`expires_at`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Planar viewport queries (`GET /api/pois?bbox=...`) execute and return up to 200 spatial points in under 75 milliseconds p95 latency against a dataset of 10,000 indexed records.
- **SC-002**: 100% of geocoding repeat requests for identical normalized addresses or coordinates resolve directly from `geocoding_cache` in under 10 milliseconds without making external HTTP requests.
- **SC-003**: Deduplication detection flags duplicate POIs within 500 meters with identical or trigram-similar names ($\ge 0.60$) with 100% precision in test scenarios.
- **SC-004**: Interactive merge operations (`POST /api/pois/merge`) complete atomically in under 150 milliseconds, with 0 orphaned child relationships or broken foreign keys.
- **SC-005**: Embedding invalidation bypasses Gemini API calls 100% of the time when POI metadata changes do not alter `name`, `description`, or tags (verified by `embedding_md5` matching).
- **SC-006**: Automated test suite achieves $\ge 90\%$ line and branch coverage across all POI domain entities, spatial queries, repositories, geocoding adapters, and merge algorithms.

---

## Assumptions

- **Alembic Reversibility**: Migration `0002_poi_domain_spatial.py` must provide a 100% reversible `downgrade()` function dropping newly created tables and indexes in strict reverse dependency order.
- **Mapbox API Key**: When running locally without a valid `MAPBOX_ACCESS_TOKEN`, the Mapbox adapter operates in mock or fallback mode, returning deterministic coordinates or falling back to `enrichment_status = 'PARTIAL'`.
- **Gemini API Key**: When running tests, embedding generation uses an async mock adapter (`MockEmbeddingAdapter`) to prevent unneeded external LLM network calls, while production runtime uses `GeminiEmbeddingAdapter`.
- **Database Extensions**: PostgreSQL database running locally and in cloud environments has `postgis`, `btree_gist`, and `vector` (pgvector) extensions enabled from Phase 1.
- **User Scoping Invariant**: Every database query, update, deletion, and index lookup on `pois`, `lists`, and `tags` enforces strict multi-tenancy by filtering on `user_id = current_user_id`.
