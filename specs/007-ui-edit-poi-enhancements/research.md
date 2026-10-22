# Phase 0 Research: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Feature Identifier**: `007-ui-edit-poi-enhancements`  
**Date**: 2026-10-21  
**Status**: Ratified  
**Target Systems**: `services/poi/`, `packages/core/vistarae_core/`, `frontend/src/components/poi/`, `db/migrations/`

---

## 1. Multi-Address Structure & Schema Evolution

### Decision
Store multiple structured addresses per POI in a top-level JSONB array column (`addresses: list[AddressRecord]`) directly on the `pois` table, supported by a GIN index using `jsonb_path_ops`. An Alembic migration (`0005_poi_edit_enhancements.py`) will backfill `addresses` from legacy `states` and `countries` JSONB columns while deprecating legacy column usage.

### Rationale
- **Document Atomicity**: In Vistarae, addresses are subordinate value objects tightly coupled to the POI aggregate lifecycle. A JSONB array allows single-query retrieval and atomic updates without multi-table join overhead (`SELECT * FROM pois LEFT JOIN poi_addresses...`) on every POI fetch.
- **Trans-Boundary Sites**: Sites such as Iguazu Falls (Argentina and Brazil) or Yellowstone (Wyoming, Montana, Idaho) require multiple distinct country and state records. A JSONB array cleanly accommodates heterogeneous address blocks (street, municipality, state/province, country, zip).
- **Index Efficiency**: PostgreSQL GIN indexing with `jsonb_path_ops` provides high-performance containment searches (`addresses @> '[{"country": "Germany"}]'`) while maintaining a smaller index footprint than default GIN operator classes.
- **Consistency with Existing Core**: Vistarae already models collection attributes (`tags`, `states`, `countries`) as JSONB arrays in `pois`, ensuring architectural consistency.

### Alternatives Considered
- *Dedicated `poi_addresses` relational child table*: Rejected because it requires separate repository queries, foreign key management, join overhead, and complex cascade/merge reconciliation for simple value object storage.
- *Scalar columns on `pois` with overflow array*: Rejected because splitting primary vs. secondary addresses introduces conditional query branching and inconsistent normalization logic.

---

## 2. Hierarchical POI Parenting & Cycle Prevention

### Decision
Model POI hierarchy using a self-referential foreign key `parent_poi_id` on `pois.id` with `ON DELETE SET NULL`. Provide a dedicated endpoint `GET /api/pois/parents?exclude_id={id}&query={q}` that queries candidate parent POIs, filtering out the active POI and its descendants using a recursive Common Table Expression (CTE) to guarantee zero cyclical loops.

### Rationale
- **Attraction Nesting**: Travelers frequently organize sub-attractions within macro sites (e.g., "Old Faithful" within "Yellowstone National Park", or "Eiffel Tower Summit" within "Eiffel Tower").
- **Cycle Prevention**: Circular references (A -> B -> A) corrupt navigation trees and UI rendering. Executing an ancestor traversal CTE during parent selection and backend validation (`REQ-EDIT-014`) guarantees mathematical DAG (Directed Acyclic Graph) integrity.
- **Graceful Deletion**: Configuring `ON DELETE SET NULL` ensures that deleting a parent POI gracefully promotes child POIs to top-level items rather than cascade-deleting them.

### Alternatives Considered
- *Materialized Path / Nested Sets*: Rejected as overly complex for shallow 2–3 level travel attraction hierarchies. A simple adjacency list (`parent_poi_id`) with recursive CTE cycle checks provides optimal simplicity and flexibility.
- *Pure Client-Side Filtering*: Rejected because client-side-only checks cannot enforce database consistency against concurrent API updates or direct REST requests.

---

## 3. Hybrid Geocoding & Rate-Limiting Architecture

### Decision
Adopt a hybrid geocoding routing pattern:
1. **Forward Search (Location Finder)**: Executed directly from the browser against the geocoding provider with client-side debouncing ($\ge 500$ms). This offloads high-frequency interactive typing queries from backend queues and keeps the map search experience snappy.
2. **Reverse Geocoding (Apply & Save)**: Routed through backend endpoints (`/api/pois/geocode/reverse`) backed by the PostGIS `geocache` table (SHA-256 hash lookup of coordinates rounded to 5 decimal places) and OpenStreetMap Nominatim 1 request/second global rate limiting with `User-Agent: VistaraeTravelEngine/1.0`.

### Rationale
- **Constitutional Compliance**: Principle 6 & Invariant 3 mandate strict adherence to OSM Nominatim policies (1 req/sec max, custom User-Agent, internal `geocache` table lookup). Reverse geocoding on "Apply" and "Save" is critical for authoritative database records and must pass through the cached backend pipeline.
- **Responsiveness**: Forward autocomplete in a map search box requires sub-200ms interactive keystroke feedback. Routing forward typing keystrokes through a 1 req/sec backend queue would introduce severe UI latency and search backpressure.
- **Cache Hit Optimization**: Rounding reverse-geocoding coordinates to 5 decimal places (~1.1 meter resolution) maximizes cache hits across repeated queries for the same venue.

### Alternatives Considered
- *All Geocoding via Backend*: Rejected because forward landmark search keystrokes would rapidly queue up behind the 1 req/sec rate limiter, degrading the user experience.
- *All Geocoding via Frontend*: Rejected because it bypasses the PostGIS `geocache`, violates Nominatim custom User-Agent and rate-limiting policies across multiple concurrent users, and leaks raw provider URLs.

---

## 4. Field-by-Field POI Comparison & Atomic Merge Workflow

### Decision
Implement the POI Merge workflow as an atomic transaction (`services/poi/services/merge_service.py`):
1. Load both source and target POIs under pessimistic locks (`SELECT ... FOR UPDATE`).
2. Synthesize scalar fields from user-selected radios and union set-based fields (tags, addresses, visited dates, directory paths, image URLs) with deduplication.
3. Atomically re-parent dependent foreign references:
   - `UPDATE itinerary_items SET poi_id = :target_id WHERE poi_id = :source_id`
   - `INSERT INTO poi_list_memberships ... ON CONFLICT DO NOTHING` followed by deleting source memberships.
   - `UPDATE pois SET parent_poi_id = :target_id WHERE parent_poi_id = :source_id`
   - Re-assign photo scanned paths (`scanned_paths`).
4. Update target POI with synthesized data.
5. Delete the source POI.
6. Commit transaction in under 500 milliseconds.

### Rationale
- **Referential Integrity**: Simply deleting the source POI would cause foreign key constraint violations or orphaned records in itineraries and curated lists. Re-parenting within the same transaction preserves user itinerary schedules and list memberships seamlessly.
- **Diff-First UX**: Defaulting the UI merge view to diff-only reduces visual clutter by $\ge 50\%$, allowing users to focus exclusively on conflicting attributes.

### Alternatives Considered
- *Soft-Deleting Source POI*: Rejected because Vistarae's domain mandates library deduplication and clean records without ghost entities cluttering search indices.
- *Cascade Deleting Dependents*: Unacceptable as it would silently destroy a traveler's planned itineraries or list memberships.

---

## 5. Duplicate Interception with In-Memory Draft Preservation

### Decision
Expose a lightweight pre-save endpoint `POST /api/pois/check-duplicate` accepting candidate name and coordinates. When a collision is detected (trigram similarity $\ge 0.60$ and spatial distance $\le 200$m), the frontend intercepts save execution and displays a 3-way modal:
1. **Create New**: Ignores collision and commits draft.
2. **Merge**: Passes the in-memory draft directly into `POIMergeModal` as the source POI against the conflicting target POI, preserving all unsaved edits without writing a dirty temporary database record.
3. **Cancel**: Closes modal and returns user to editor with draft state intact.

### Rationale
- **Zero Data Loss**: Travelers may spend considerable time entering rich descriptions, multiple addresses, and photo paths. Discarding draft changes or requiring pre-saves to PostgreSQL risks data loss or database pollution.
- **In-Memory Source Synthesis**: Passing the draft object directly into the merge comparison engine allows the user to immediately pick which draft fields should update the existing POI.

### Alternatives Considered
- *Persisting Temporary Draft Record in DB*: Rejected because creating uncommitted or orphaned dirty records complicates cleanup routines and triggers spurious duplicate detections.
- *Blocking Save Entirely*: Rejected because false positives can occur (e.g., adjacent venues with similar names in a food court).

---

## 6. Local Photo Folder Directory Input & Access Protocol

### Decision
Implement a hybrid input pattern in the frontend:
1. Provide a standard text input field for direct manual entry or pasting of filesystem paths (supporting Windows drive letters `C:\...`, UNC shares `\\...`, or Unix paths `/...`).
2. Provide a "Browse Folder" button that checks for the Chromium File System Access API (`window.showDirectoryPicker()`). If supported, it opens a native directory picker and extracts the directory name/path.
3. Stored paths integrate with the Phase 5 Chrome Native Messaging Host (`com.vistarae.folder_opener`), which securely executes OS-level directory opening via 4-byte native endian integer framing.

### Rationale
- **Browser Sandbox Limitations**: Standard web browser file inputs (`<input type="file">`) sanitize local paths to `C:\fakepath\...` for security. Direct text entry ensures travelers can specify arbitrary local folders, while `showDirectoryPicker()` offers enhanced convenience where supported.
- **Native Host Decoupling**: Storing normalized directory path strings decouples the web application from local execution, enabling the native messaging bridge to handle explorer launches safely with metacharacter neutralization.

### Alternatives Considered
- *Direct File Upload Only*: Rejected because the user requirement explicitly mandates referencing local machine photo directories for organization without consuming server-side storage quotas.
- *Custom Electron App*: Rejected as out-of-scope; Vistarae is an agile web SPA + Chrome Extension architecture.
