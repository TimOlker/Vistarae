# Feature Specification: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Feature Identifier**: `007-ui-edit-poi-enhancements`  
**Feature Branch**: `007-ui-edit-poi-enhancements`  
**Created**: 2026-10-21  
**Status**: Draft  
**Target Systems**:
- POI Management Frontend: `frontend/src/components/poi/` (POI Editor modal/page, `LocationFinderModal`, `POIMergeModal`, Parent POI typeahead selector), Map layer integration, Form state management
- POI Backend Domain & Persistence: `services/poi/` (`/api/pois/*` update, merge, reverse geocode, parent lookup, and duplicate detection endpoints), `packages/core/vistarae_core/` (entity models, Pydantic v2 schemas, repositories, address normalization engine)
- Database: PostgreSQL 16+ / PostGIS / Alembic migrations for multi-address JSONB support, visit flags, parent hierarchy relations, and rich metadata

**Input**: User description:
> "/speckit.specify Create the specification for Phase 7 (007-ui-edit-poi-enhancements) using strict EARS syntax. This covers the edit POI page.
> Scope to cover:
> 1. Additional Fields to include for each POI entry and include into the DB:
>   - multiline free form description (this is a good source to parse for AI search)
>   - address (note multiple addresses can be entered for a POI for example Iguazu falls stretches across two countries, Yellowstone national park stretches across multiple US states).
>     - street address (if available)
>     - State/Province (use normalization rules before saving: standardize on official spelling / capitalization, use the English version of the name).
>     - Country (use normalization rules before saving: standardize on official spelling / capitalization, use the English version of the name) (required).
>     - zip code
>   - one or more photo folders on the local machine
>   - one or more URLs to an image for the POI
>   - estimated visit time (hours)
>   - estimated visit time (days)
>   - POI parent name - if an item has a parent list the POI name of the item (this is a drop down that lists all POIs, can type and it filters the records down)
>   - POI parent id - ID of the POI based on what was selected
>   - source type, 'source value' - source type can be from the 'Web', the 'source value' is the URL of the website, if the source type is 'CSV' and the 'source value' is the directory (if provided), if the 'source value', if the 'source type' is 'Manual' then leave the 'source value' blank. If the 'source type' is 'Photo' the 'source value' is the image that was uploaded.
>   - Official Website is a field that holds the website's official website (if found)
>   - Wikipedia Website is a field that holds the Wikipedia entry (if found)
>   - Photo Folders - is a list of folders associated with the POI
>   - list of dates visited: displayed in chronological order, ability to delete a specific date, ability to add a new date with a date picker. Checkbox that determines if the POI wants to be visited again. (If no date visited is present, set 'already visited' flag to False; if one or more dates populated, set 'already visited' flag to True. If multiple dates are populated and visit again checkbox is set, or no dates are populated, set 'visit pending' flag to True. If multiple dates are populated and visit again checkbox is not set, set 'visit pending' flag to False).
> 2. Latitude/Longitude Finder - select a new location (lat/long):
>   - When triggered from POI editor, brings up a new view with map (pan, zoom in/out, multiple layers).
>   - Center map on previous location if lat/long already provided.
>   - Text input box + search button to search destination. Zoom level corresponds to query scope (e.g., 'Paris, France' zooms to city; 'Mount Rushmore' zooms to monument). Plot first X matches (configurable). If more matches found, display warning to be more specific (e.g. searching 'McDonalds' prompts user to add location). Warning if empty input or no matches.
>   - Click on map to set a pin showing exact lat/long.
>   - 'Cancel' button closes without changing POI.
>   - 'Apply' button sets selected lat/long in draft (not saved to DB until POI is saved) and uses API to determine address (city/town, state/province, country).
> 3. POI Merge:
>   - On POI edit page, a 'merge into / merge from' brings up a new view. Merges selected POI into a second POI, then deletes the first selected POI.
>   - Toggle 'Show all fields' (default disabled -> only show fields where values differ; enabled -> show all fields).
>   - Single-value fields: radio button to pick value from either POI.
>   - Multi-value fields: checkboxes for each value, saving all checked items from both POIs (de-duplicated).
> 4. Saving changes:
>   - If lat/long has changed (including first population), populate street address, city, state/province, country using intelligence.
>   - Duplicate check: Standardize POI name and use lat/long to check duplicates. If potential duplicate detected, prompt user with merge logic:
>     a) Create a new POI entry as requested
>     b) Merge the draft data with the existing POI using selected values
>     c) Cancel (no create or update)"

---

## 1. Executive Summary & Context

Phase 7 (`007-ui-edit-poi-enhancements`) advances the Vistarae point-of-interest management lifecycle by elevating the POI editor drawer into a full-featured, intelligent POI Curation Studio. The feature delivers:

1. **Rich POI Metadata, Multi-Address Modeling & Hierarchical Parenting**:
   - Expands POI attributes to capture multiline semantic descriptions (for future RAG vectorization), multiple international address records per POI (handling trans-boundary sites such as Iguazu Falls or multi-state entities like Yellowstone), local photo folders, gallery image URLs, estimated visit durations (decimal hours and integer days), structured provenance tracking (`Web`, `CSV`, `Manual`, `Photo`), official and Wikipedia links, and granular visited date tracking.
   - Introduces **Hierarchical POI Parenting** (`parent_poi_id`, `parent_poi_name`), enabling travelers to model nested attraction structures (e.g., nesting "Old Faithful" under "Yellowstone National Park", or "Eiffel Tower Summit" under "Eiffel Tower"). The UI provides a searchable typeahead dropdown filtering the traveler's existing POI library, with strict cycle and self-parenting prevention.
   - Computes deterministic visit lifecycle state flags (`already_visited`, `visit_pending`) based on chronological visit dates and traveler return intent (`want_to_visit_again`).
   - Normalizes state/province and country entries against international standards (standardizing on official English names and ISO 3166-1/ISO 3166-2 references).

2. **Interactive Latitude/Longitude Map Finder**:
   - A dedicated modal map workspace supporting multi-layer basemaps (satellite, terrain, street), click-to-pin coordinate selection, and dynamic forward geocoding with adaptive zoom (broad regional zoom for cities like "Paris, France" vs. tight focal zoom for specific landmarks like "Mount Rushmore").
   - Result pagination with configurable display thresholds ($X$) and proactive query refinement warnings when high-cardinality brand matches (e.g., "McDonalds") occur.
   - Non-destructive draft application with automatic reverse-geocoding resolution upon clicking "Apply".

3. **Field-by-Field POI Comparison & Atomic Merge**:
   - An interactive visual merge workspace enabling travelers to combine two duplicate or overlapping POIs.
   - An intelligent "Show all fields" toggle (defaulting to a compact diff-only mode showing only diverging attributes).
   - Radio button resolution for scalar fields (name, description, duration, rating, parent POI, primary links) and multi-select checkbox aggregation for set-based fields (tags, lists, addresses, photo directories, visited dates), culminating in atomic target POI update and source POI deletion.
   - Atomically re-parents all dependent foreign references—including child POIs (`parent_poi_id`), itinerary items, curated list memberships, and scanned paths—to the target POI.

4. **Intelligent Save Workflow & Duplicate Interception**:
   - Upon clicking "Save Changes", the system automatically backfills missing address components if coordinates were altered.
   - Executes spatial and trigram duplicate detection against the tenant's existing POI library, intercepting potential collisions with an actionable triage prompt offering: (a) create new anyway, (b) launch selective merge with in-memory draft preservation, or (c) cancel.

---

## Clarifications

### Session 2026-10-21

- Q: How should the system handle foreign references in itineraries, curated lists, and photo paths when a source POI is merged into a target POI and deleted? → A: Option A (Atomic Re-parenting): Update `itinerary_items` (`poi_id = target_id`), re-parent `poi_list_memberships` (ignoring unique constraint duplicates), re-parent child POIs (`parent_poi_id = target_id`), and re-assign `scanned_paths` within the same database transaction before deleting the source POI.
- Q: How should the Location Finder's forward search and reverse geocoding requests be routed? → A: Option C (Hybrid Geocoding Routing): Forward landmark and destination search executes directly from the browser with client-side debouncing, while reverse geocoding (deriving address from coordinates on "Apply" and "Save") routes through backend `/api/pois/geocode/reverse` endpoints utilizing the PostGIS geocache and 1 req/sec rate limiting.
- Q: How should multiple addresses per POI be structured and persisted in PostgreSQL? → A: Option A (Structured JSONB Array): Persist multiple addresses as a structured JSONB array (`addresses: list[AddressRecord]`) directly on the `pois` table with GIN indexing (`jsonb_path_ops`), backfilled from legacy `states` and `countries` columns via Alembic migration `0005_poi_edit_enhancements.py`.
- Q: When a duplicate collision is intercepted on Save and the user chooses "Merge", how should unsaved draft changes be handled? → A: Option A (In-Memory Draft Merge): Pass the in-memory draft directly into the Merge view as the source POI, enabling selective merging of unsaved edits into the existing target POI without creating an intermediate database record.
- Q: How should local photo folder directory paths be input and captured in the POI Editor UI? → A: Option A (Hybrid Directory Input): Provide text inputs for typing or pasting local directory paths, alongside a "Browse Folder" button invoking the File System Access API (`window.showDirectoryPicker()`) where supported to capture local directory names and paths.

---

## 2. User Scenarios & Testing _(mandatory)_

### User Story 1 - Rich POI Field Editing, Hierarchical Parenting & Visit Tracking (Priority: P1)

A traveler reviews a captured scenic overlook in the POI Editor. They refine the free-form description with hiking trail conditions, assign a parent POI ("Yellowstone National Park") via a searchable typeahead dropdown, add two separate geographic addresses for a site spanning an international border, enter multiple visited dates from past travels, and check "Want to visit again". The UI automatically computes that `already_visited = true` and `visit_pending = true`. The traveler also attaches two local photo folders on their desktop (`C:\Photos\Yellowstone2024`) and links both the official national park site and Wikipedia page. When saved, all data is validated, normalized, and persisted to the database.

**Why this priority**: Core foundation of Phase 7. Travelers must be able to curate high-fidelity, complete records of their travel dreams, parent-child attraction relationships, and past journeys.

**Independent Test**: Can be tested by opening the POI Editor for an existing POI, entering multi-address records with foreign country aliases, filtering and assigning a parent POI, entering visit dates, toggling "visit again", and verifying that normalized values, hierarchy links, and computed flags are correctly rendered and persisted.

**Acceptance Scenarios**:

1. **Given** a traveler editing a POI spanning multiple states or countries, **When** they add multiple address blocks, **Then** the editor accepts distinct street, city, state/province, country, and zip code values for each address block.
2. **Given** an address entered with non-standard country or state casing (e.g. "deutschland" or "ca"), **When** the record is prepared for save, **Then** the system normalizes the entries to official English standard names (e.g. "Germany", "California").
3. **Given** a traveler searching for a parent POI in the editor, **When** typing into the parent POI input, **Then** the dropdown dynamically filters the traveler's existing POIs by name, displaying the matching POI names for selection.
4. **Given** a traveler selecting a parent POI from the dropdown, **When** selected, **Then** the editor sets `parent_poi_id` to the chosen POI's unique ID and displays the corresponding `parent_poi_name`.
5. **Given** a traveler editing a POI, **When** inspecting the parent POI selection list, **Then** the current POI itself and any of its existing descendants are excluded from the selectable options to prevent circular hierarchy loops.
6. **Given** a POI with no visited dates, **When** inspected in the editor, **Then** the system computes `already_visited = false` and `visit_pending = true`.
7. **Given** a POI with one or more visited dates and the "Want to visit again" checkbox checked, **When** evaluated, **Then** the system computes `already_visited = true` and `visit_pending = true`.
8. **Given** a POI with one or more visited dates and the "Want to visit again" checkbox unchecked, **When** evaluated, **Then** the system computes `already_visited = true` and `visit_pending = false`.
9. **Given** a list of visited dates, **When** rendered in the editor, **Then** dates appear in ascending chronological order with individual delete controls and a date picker to add new entries.
10. **Given** a source type selected as "Web", **When** rendered, **Then** the editor requires a valid website URL in the source value field; when "Manual" is selected, the source value is empty and disabled.
11. **Given** a traveler configuring local photo directories, **When** adding a path, **Then** the editor provides a direct text input for typing or pasting directory paths and a "Browse Folder" button using the File System Access API (`showDirectoryPicker`) when available in supported browsers.

---

### User Story 2 - Interactive Latitude/Longitude Map Finder (Priority: P1)

A traveler creates or edits a POI whose exact coordinates are missing or inaccurate. They click "Find on Map" in the POI Editor. A full-screen or large modal map opens. If coordinates exist, the map centers on them; otherwise, it centers on the user's active viewport. The user types "Mount Rushmore" in the destination search box. The browser queries the forward geocoding service with debouncing, identifies the landmark, pans directly to the monument, and sets a high zoom level (~16). The user fine-tunes the location by clicking directly on the visitor center on the map, dropping a marker that displays the exact latitude and longitude. The user clicks "Apply", which closes the finder, updates the coordinates in the POI draft without saving to the DB yet, and triggers reverse geocoding via the backend to pre-fill missing address fields.

**Why this priority**: Precise geographic location is required for spatial clustering, corridor routing, and map visualization.

**Independent Test**: Can be tested by opening the Location Finder, searching for a broad city vs. a specific monument, dropping a pin by clicking the map canvas, verifying coordinate reflection, clicking "Apply", and verifying that the POI draft coordinates and reverse-geocoded address fields update without a database write.

**Acceptance Scenarios**:

1. **Given** a POI with existing latitude and longitude, **When** the Location Finder is opened, **Then** the map initializes centered on the existing coordinates with an active pin.
2. **Given** a broad location search query (e.g., "Paris, France"), **When** the search executes, **Then** the map centers on the city with a regional zoom level (e.g. zoom 11–12).
3. **Given** a specific landmark search query (e.g., "Mount Rushmore"), **When** the search executes, **Then** the map centers directly on the landmark with a tight focal zoom level (e.g. zoom 16–17).
4. **Given** a search query yielding multiple matches (e.g. "McDonalds"), **When** results exceed the configurable display threshold $X$, **Then** the finder plots the first $X$ pins and displays an advisory warning prompting the user to provide more location specificity.
5. **Given** an empty search query or a query with zero matches, **When** submitted, **Then** the finder displays an inline warning notification without moving the map view.
6. **Given** a user clicking any point on the map canvas, **When** clicked, **Then** the active pin moves to that exact coordinate and displays formatted decimal coordinates (e.g., `43.8791, -103.4591`).
7. **Given** a selected location, **When** the user clicks "Cancel", **Then** the modal closes and the POI draft coordinates remain completely unchanged.
8. **Given** a selected location, **When** the user clicks "Apply", **Then** the modal closes, the draft coordinates update, and reverse geocoding via the backend geocaching endpoint auto-populates city, state/province, and country in the draft.

---

### User Story 3 - Selective Field-by-Field POI Comparison & Atomic Merge (Priority: P2)

A traveler identifies two duplicate entries for the same viewpoint captured at different times (e.g., one from an Instagram photo folder with tags and one from a web blog with a rich description). On the POI edit page, they click "Merge POI". A dual-column comparison modal opens showing POI A (Source) and POI B (Target). By default, only fields with differing values are displayed. The user toggles "Show all fields" to inspect identical values as well. For the title, description, and parent POI, the user uses radio buttons to select values from POI B. For tags, photo folders, and visited dates, the user checks boxes from both POI A and POI B to combine them. Upon clicking "Confirm Merge", the target POI is updated with the synthesized values, any child POIs referencing the source POI are re-parented to the target POI, and the source POI is deleted from the database.

**Why this priority**: Eliminates library clutter and combines fragmented information from multiple capture sessions into one unified, authoritative POI.

**Independent Test**: Can be tested by initiating a merge between two distinct POIs, toggling the "Show all fields" switch, selecting conflicting single-value fields via radio buttons, selecting multi-value fields via checkboxes, confirming merge, and verifying that the target POI contains the merged dataset, child POIs are re-parented, and the source POI is permanently deleted.

**Acceptance Scenarios**:

1. **Given** the Merge view opened between POI A and POI B, **When** "Show all fields" is toggled off (default), **Then** only attributes where the values of POI A and POI B differ are listed in the comparison table.
2. **Given** the Merge view, **When** "Show all fields" is toggled on, **Then** all attributes across both POIs are listed.
3. **Given** single-value fields (e.g., Name, Star Rating, Description, Primary Coordinates, Parent POI), **When** rendered, **Then** each field displays a radio button group allowing the user to select either POI A's value or POI B's value.
4. **Given** multi-value fields (e.g., Tags, Curated Lists, Addresses, Local Photo Folders, Visited Dates, Image URLs), **When** rendered, **Then** each unique item across both POIs displays a checkbox allowing selection of any combination.
5. **Given** multi-value selections containing identical entries across both POIs, **When** merged, **Then** the target POI de-duplicates items so each distinct value appears exactly once.
6. **Given** confirmation of the merge, **When** submitted, **Then** the system updates the target POI, atomically re-parents all dependent references (`itinerary_items`, `poi_list_memberships` with deduplication, `scanned_paths`, and child POIs referencing source as parent) to the target POI, and deletes the source POI in a single database transaction.

---

### User Story 4 - Intelligent Save Workflow & Duplicate Interception (Priority: P1)

A traveler edits an existing POI or completes a new POI draft and clicks "Save Changes". The application detects that the coordinates have changed, automatically verifying that address fields are synchronized via reverse geocoding. Prior to committing, the system checks for duplicate POIs within the user's library using name standardization and spatial proximity. If a potential duplicate is detected, the system intercepts the save and presents a modal offering three clear options: (a) Create / Save as New POI anyway, (b) Open Merge View to combine the draft with the conflicting POI, or (c) Cancel to return to the editor.

**Why this priority**: Prevents accidental creation of redundant records and prompts user curation at the exact moment of potential collision.

**Independent Test**: Can be tested by modifying a POI's coordinates and name to match an existing POI within 200 meters, clicking "Save Changes", verifying that the duplicate interception modal displays the three choices, selecting "Merge", and asserting that the merge workflow initializes with the conflicting POIs.

**Acceptance Scenarios**:

1. **Given** an altered latitude and longitude upon clicking "Save Changes", **When** validated, **Then** the system automatically derives and populates missing street address, city, state/province, and country fields before saving.
2. **Given** a saved POI whose standardized name and location match an existing tenant POI within spatial deduplication thresholds, **When** the user clicks "Save Changes", **Then** the application interrupts save execution and presents the Duplicate Interception dialog.
3. **Given** the Duplicate Interception dialog, **When** the user chooses "Create as New", **Then** the system proceeds with saving the record as an independent POI.
4. **Given** the Duplicate Interception dialog, **When** the user chooses "Merge", **Then** the application passes the active in-memory draft directly into the POI Merge view as the source POI without persisting an intermediate database record, allowing selective synthesis into the existing target POI.
5. **Given** the Duplicate Interception dialog, **When** the user chooses "Cancel", **Then** the save is aborted and the editor remains open with all draft changes preserved.

---

## 3. Edge Cases

- **Trans-Boundary Multi-Address Sites**: When a POI spans two countries (e.g., Iguazu Falls across Argentina and Brazil, or Niagara Falls across USA and Canada), the system must permit multiple country records on a single POI and must not force a single primary address to overwrite the other.
- **Missing or Ambiguous Reverse Geocoding**: When coordinates represent remote wilderness, open ocean, or unaddressed rural tracks, reverse geocoding may fail to return a street address or municipality. The system shall gracefully degrade to storing only known higher-level administrative boundaries (e.g. state/province, country, or park region) without blocking save.
- **Network Share vs. Local Desktop Paths**: Local photo folder strings may be formatted as Windows drive letters (`C:\Photos`), UNC shares (`\\nas\photos`), or Unix paths (`/home/user/photos`). The editor must store raw normalized paths without operating system validation failures.
- **Chronological Sorting with Incomplete Dates**: When a traveler adds a visit date with only year/month (or full YYYY-MM-DD), the system shall sort records chronologically, placing older dates first.
- **Concurrent POI Deletion During Merge**: If a source or target POI is deleted in another tab/device while the Merge view is open, the atomic transaction must detect the missing record and return an RFC 7807 404/409 error informing the user that one of the records no longer exists.
- **Dependent Reference Re-parenting During Merge**: When a source POI is merged into a target POI and deleted, any active itinerary items, curated list memberships, photo scanned paths, or child POIs referencing the source POI shall be atomically re-parented to the target POI (with list membership deduplication) rather than cascade-deleted or orphaned.
- **Cyclical & Self-Parenting Hierarchy Prevention**: A POI must not be assigned as its own parent, nor assigned to an existing descendant POI. The backend shall reject cyclical hierarchy updates with an RFC 7807 422 Unprocessable Entity error.
- **Duplicate Save Draft Preservation**: When an unsaved new POI draft collides with an existing POI and the user chooses "Merge", all draft fields (description, addresses, photo directories, visit dates) shall be supplied in-memory to the merge comparison engine; if the user cancels out of the merge modal, they shall be returned to the POI editor with the draft state intact.
- **Zero Coordinate Changes**: If "Save Changes" is clicked without modifying coordinates, the system shall not trigger unnecessary reverse-geocoding API requests, preserving rate limits and performance.
- **Extreme High-Cardinality Geocoding Queries**: Queries matching hundreds of locations (e.g. "Subway") must throttle plotted pins to $X$ (default 5) and instruct the user to narrow search terms.

---

## 4. Requirements _(mandatory)_

### 4.1 POI Editor Rich Fields, Hierarchy & Visit Tracking (`REQ-EDIT-xxx`)

- **REQ-EDIT-001 (Ubiquitous):** The POI domain shall persist a multiline free-form description attribute (`description`) supporting up to 10,000 characters for rich contextual notes and semantic discovery.
- **REQ-EDIT-002 (Ubiquitous):** The POI domain shall persist one or more structured address records per POI in a JSONB array column (`addresses: list[AddressRecord]`) on the `pois` table, supported by a GIN index (`jsonb_path_ops`), with each record containing optional street address, optional municipality/city, optional state/province, required country, and optional postal/zip code.
- **REQ-EDIT-003 (Event-Driven):** When an address record is validated or saved, the system shall execute normalization rules standardizing state/province and country entries to official English nomenclature.
- **REQ-EDIT-004 (Unwanted Behaviour):** If an address record omits a country value, then the system shall reject the address with an RFC 7807 422 Unprocessable Entity validation error.
- **REQ-EDIT-005 (Ubiquitous):** The POI domain shall persist an array of local photo folder directory paths (`directory_paths`) and an array of gallery image URLs (`image_urls`), with the UI providing direct text input and an optional "Browse Folder" button utilizing the File System Access API (`window.showDirectoryPicker()`) where supported.
- **REQ-EDIT-006 (Ubiquitous):** The POI domain shall persist estimated visit duration fields in both decimal hours (`recommended_duration_hours`) and integer days (`recommended_visit_days`).
- **REQ-EDIT-007 (State-Driven):** While editing the POI provenance, the source type shall enforce selection from `Web`, `CSV`, `Manual`, and `Photo`:
  - When `Web` is selected, `source_value` shall store the origin webpage URL.
  - When `CSV` is selected, `source_value` shall store the source directory or filename if provided.
  - When `Manual` is selected, `source_value` shall be empty.
  - When `Photo` is selected, `source_value` shall store the uploaded image reference.
- **REQ-EDIT-008 (Ubiquitous):** The POI domain shall store dedicated URL strings for the official website (`official_url`) and Wikipedia entry (`wiki_url`).
- **REQ-EDIT-009 (Ubiquitous):** The POI domain shall persist an array of visited date records (`visited_dates`) and a boolean flag indicating future travel intent (`want_to_visit_again`).
- **REQ-EDIT-010 (Event-Driven):** When visited dates are rendered in the UI, the client shall display records in ascending chronological order with individual deletion controls and a date picker to append new dates.
- **REQ-EDIT-011 (State-Driven):** While computing visit lifecycle state:
  - If `visited_dates` is empty, then `already_visited` shall be `false`.
  - If `visited_dates` contains one or more entries, then `already_visited` shall be `true`.
  - If `visited_dates` is empty, OR if (`want_to_visit_again` is `true`), then `visit_pending` shall be `true`.
  - If `visited_dates` contains one or more entries AND `want_to_visit_again` is `false`, then `visit_pending` shall be `false`.
- **REQ-EDIT-012 (Event-Driven):** When the user interacts with the parent POI input, the client shall provide a searchable typeahead dropdown listing existing tenant POIs, filtering matches by name as the user types.
- **REQ-EDIT-013 (Ubiquitous):** The POI domain shall persist an optional foreign key attribute (`parent_poi_id: Optional[UUID]`) referencing `pois.id` with `ON DELETE SET NULL`, and provide the resolved parent name (`parent_poi_name: Optional[str]`) in read responses.
- **REQ-EDIT-014 (Unwanted Behaviour):** If a user attempts to set `parent_poi_id` to the POI's own identifier or to any descendant POI in the hierarchy tree, then the system shall reject the change with an RFC 7807 422 Unprocessable Entity error preventing circular reference loops.

---

### 4.2 Interactive Latitude/Longitude Map Finder (`REQ-LOC-xxx`)

- **REQ-LOC-001 (Event-Driven):** When a user clicks "Find on Map" in the POI Editor, the client shall open the Location Finder modal containing an interactive map canvas, layer switcher, search bar, and coordinate readout.
- **REQ-LOC-002 (State-Driven):** While initializing the Location Finder:
  - If the POI draft already contains valid coordinates, the map shall center on those coordinates with a pre-placed pin.
  - If the POI draft lacks coordinates, the map shall center on the user's current map viewport.
- **REQ-LOC-003 (Event-Driven):** When the user submits a search query in the Location Finder, the browser client shall query forward geocoding directly with client-side debouncing (minimum 500ms) and adjust map viewport bounds:
  - When the result represents a broad geographic region or city, the map shall zoom to a regional overview (zoom level 10–12).
  - When the result represents a specific monument, landmark, or street address, the map shall zoom to a detailed focal level (zoom level 16–18).
- **REQ-LOC-004 (Event-Driven):** When a search query returns multiple matching locations, the finder shall plot pins for up to $X$ candidates (configurable, default 5).
- **REQ-LOC-005 (Unwanted Behaviour):** If a search query yields more than $X$ candidates, then the finder shall display an informational warning banner advising the user to provide more location specificity (e.g. including city, state, or street).
- **REQ-LOC-006 (Unwanted Behaviour):** If a search query is submitted empty or yields zero matches, then the finder shall display a warning notification without altering the current map center.
- **REQ-LOC-007 (Event-Driven):** When a user clicks anywhere on the map canvas, the client shall move or place an active pin at that exact point and update the displayed latitude and longitude values.
- **REQ-LOC-008 (Event-Driven):** When the user clicks "Cancel", the finder modal shall close without altering the draft POI coordinates.
- **REQ-LOC-009 (Event-Driven):** When the user clicks "Apply", the client shall assign the selected latitude and longitude to the active POI draft, close the finder modal, and trigger reverse geocoding via the backend endpoint (`/api/pois/geocode/reverse`) utilizing PostGIS geocache and Nominatim rate limiting to resolve street, city, state/province, and country without writing to the database.

---

### 4.3 POI Comparison & Selective Merge (`REQ-MERGE-xxx`)

- **REQ-MERGE-001 (Event-Driven):** When a user selects "Merge POI" from the POI Editor, the client shall open the POI Merge workspace displaying the source POI and target POI in side-by-side comparison columns.
- **REQ-MERGE-002 (State-Driven):** While rendering the Merge workspace, the system shall provide a "Show all fields" toggle:
  - While "Show all fields" is disabled (default), the table shall render only rows where attributes between the two POIs differ.
  - While "Show all fields" is enabled, the table shall render all attributes regardless of value equivalence.
- **REQ-MERGE-003 (State-Driven):** While resolving scalar attributes (name, description, rating, duration, source metadata, primary links, parent POI), the UI shall provide mutually exclusive radio buttons allowing the user to select either the source POI's value or the target POI's value.
- **REQ-MERGE-004 (State-Driven):** While resolving multi-value set attributes (tags, list memberships, address records, photo directories, visited dates, image URLs), the UI shall provide individual checkboxes for every unique value across both POIs.
- **REQ-MERGE-005 (Event-Driven):** When a merge is confirmed, the system shall assemble all selected scalar values and unioned multi-value sets, update the target POI, atomically re-parent all dependent references (`itinerary_items` updating `poi_id` to target, `poi_list_memberships` re-parenting with deduplication, `scanned_paths`, and child POIs referencing source), and delete the source POI within a single atomic database transaction.
- **REQ-MERGE-006 (Unwanted Behaviour):** If either the source POI or target POI does not belong to the authenticated user, then the merge endpoint shall reject the request with an RFC 7807 404 Not Found error.

---

### 4.4 Save Workflow & Duplicate Interception (`REQ-SAVE-xxx`)

- **REQ-SAVE-001 (Event-Driven):** When the user clicks "Save Changes", the system shall verify if latitude or longitude has changed; if changed, it shall execute reverse geocoding to automatically populate missing street address, municipality, state/province, and country values.
- **REQ-SAVE-002 (Event-Driven):** When validating a POI save, the system shall execute duplicate detection comparing standardized name similarity (trigram similarity $\ge 0.60$) and spatial proximity (geodesic distance $\le 200$ meters) against the tenant's existing POIs.
- **REQ-SAVE-003 (Event-Driven):** When a potential duplicate is detected during save, the system shall interrupt the save operation and prompt the user with three distinct actions:
  - **Create New**: Persist the POI as an independent entity.
  - **Merge**: Launch the POI Merge view pre-loaded with the conflicting POI as target and the current in-memory draft as source without persisting an intermediate database record.
  - **Cancel**: Abort the save process and retain current draft state in the editor.
- **REQ-SAVE-004 (Ubiquitous):** Every save operation shall enforce strict tenant isolation, verifying `WHERE user_id = :current_user_id` on all database updates and lookups.

---

## 5. Key Entities & Data Models

### 5.1 POI Aggregate Entity Extensions

```text
POI Aggregate
├── id: UUID (Primary Key)
├── user_id: UUID (Tenant Anchor)
├── name: String(255)
├── description: Text (Multiline free-form notes)
├── parent_poi_id: Optional[UUID] (Foreign Key referencing pois.id ON DELETE SET NULL)
├── parent_poi_name: Optional[String(255)] (Resolved name of parent POI for UI display/filtering)
├── addresses: JSONB (Structured array of AddressRecord objects; indexed with GIN jsonb_path_ops)
│   ├── street: Optional[String(255)]
│   ├── city: Optional[String(100)]
│   ├── state_province: Optional[String(100)] (Normalized English standard)
│   ├── country: String(100) (Normalized English standard, Required)
│   └── postal_code: Optional[String(32)]
├── coordinates: Point(Latitude, Longitude) [SRID 4326]
├── recommended_duration_hours: Optional[Decimal(4, 2)]
├── recommended_visit_days: Integer (Default 1)
├── source_type: Enum ['Web', 'CSV', 'Manual', 'Photo']
├── source_value: Optional[String(1000)]
├── official_url: Optional[String(2000)]
├── wiki_url: Optional[String(2000)]
├── directory_paths: List[String] (Local photo folders)
├── image_urls: List[String] (Gallery image links)
├── visited_dates: List[Date] (Chronological ISO-8601 strings)
├── want_to_visit_again: Boolean (Default False)
├── already_visited: Boolean (Derived: len(visited_dates) > 0)
└── visit_pending: Boolean (Derived: len(visited_dates) == 0 OR want_to_visit_again == True)
```

### 5.2 POI Merge Resolution Payload

```json
{
  "source_poi_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "target_poi_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "selected_scalars": {
    "name": "Target Name",
    "description": "Combined notes from source",
    "parent_poi_id": "e0b94c34-7264-4e4b-972a-d68a2bf0625a",
    "rating": 5,
    "recommended_duration_hours": 3.5,
    "recommended_visit_days": 1,
    "official_url": "https://example.com",
    "wiki_url": "https://en.wikipedia.org/wiki/Example"
  },
  "selected_sets": {
    "tags": ["scenic", "overlook", "family-friendly"],
    "list_ids": ["a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"],
    "directory_paths": ["C:\\Photos\\Trip2024", "D:\\ArchivedPhotos"],
    "image_urls": ["https://images.example.com/photo1.jpg"],
    "visited_dates": ["2022-06-15", "2024-08-10"],
    "addresses": [
      {
        "street": "100 Scenic Way",
        "city": "Seattle",
        "state_province": "Washington",
        "country": "United States",
        "postal_code": "98101"
      }
    ]
  }
}
```

---

## 6. Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Travelers can open the Location Finder, search for a landmark, drop a pin, and apply coordinates in under 15 seconds.
- **SC-002**: 100% of reverse-geocoded or manually entered country and state/province names are normalized to standard English spelling and casing before persistence.
- **SC-003**: The POI Merge comparison view reduces field clutter by hiding identical fields by default, reducing visual comparison cognitive load by at least 50%.
- **SC-004**: Merging two POIs executes atomically in under 500 milliseconds, deleting the source record while leaving zero orphaned tags, address records, itinerary items, list memberships, or unlinked child POIs.
- **SC-005**: 100% of potential duplicate collisions within 200 meters and $\ge 0.60$ trigram similarity are successfully intercepted prior to save with clear merge or override options.
- **SC-006**: The visit lifecycle state flags (`already_visited`, `visit_pending`) accurately reflect the presence of visit dates and the visit-again toggle with zero state inconsistencies.
- **SC-007**: The parent POI typeahead dropdown filters a library of up to 1,000 tenant POIs in under 100 milliseconds, excluding the active POI and its descendants to guarantee zero cyclical relationships.

---

## 7. Assumptions

- **Geocoding Architecture & Availability**: Forward destination search executes directly from the browser with client debouncing, whereas reverse geocoding routes through backend PostGIS geocache endpoints respecting the 1 req/second Nominatim rate limit.
- **Client-Side Draft State**: Coordinate changes and reverse-geocoded addresses applied via the Location Finder are stored in the client-side form state and are only committed to the database when the traveler explicitly clicks "Save Changes".
- **Local Photo Folder Access**: Local folder path strings stored in `directory_paths` are captured via text input or `window.showDirectoryPicker()` and integrate with the native messaging host protocol (`com.vistarae.folder_opener`) established in Phase 5 for opening local file explorer windows.
- **Multi-Address Database Strategy**: Addresses are stored in a top-level `addresses` JSONB column on the `pois` table with a GIN index (`jsonb_path_ops`). Alembic migration `0005_poi_edit_enhancements.py` backfills `addresses` from legacy `states` and `countries` arrays while deprecating legacy column usage.
- **Parent POI Hierarchy Rules**: `parent_poi_id` uses an explicit self-referential foreign key constraint to `pois(id)` with `ON DELETE SET NULL`, ensuring child POIs remain safe top-level entities if their parent POI is independently deleted.
