# Feature Specification: Unified POI Import Staging Workbench (015-poi-export-import-enhancements-v3)

**Feature Branch**: `015-poi-export-import-enhancements-v3`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Unified POI Import Staging Workbench: Replace the split Phase 1 (Triage) and Phase 2 (Enrichment Review) modal workflow with a single, unified Import Staging Workbench using strict EARS syntax. Enhancement: (015-poi-export-import-enhancements-v3)"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Unified Staging Workbench Inspection & Perspective Sorting (Priority: P1)

As a traveler importing points of interest from web captures, travel CSVs, or photo collections, I want a single unified workbench modal that displays staged candidates in a split-screen master-detail layout with flexible perspective sorting (by POI name or geographic location), so that I can efficiently triage duplicates, review completeness, and edit attributes in one cohesive workflow without disjointed modal steps.

**Why this priority**: Consolidating Phase 1 (triage) and Phase 2 (enrichment review) into a single unified workbench eliminates redundant confirmation steps, restores all phase 1 and 2 field data in a persistent UI, and provides immediate visual perspective across imported records.

**Independent Test**: Can be fully tested by uploading a multi-item CSV (e.g., wonders of the world or regional landmarks), opening the unified workbench, switching between "POI" and "Location" perspectives, verifying column ordering and alphabetical vs geographic sorting, and inspecting individual candidates in the detail pane.

**Acceptance Scenarios**:

1. **Given** a staged ingestion job with candidates across multiple countries and regions, **When** the traveler opens the Import Staging Workbench, **Then** the workbench shall render a split-screen interface featuring a master candidate table on the left and a reactive detail editor on the right with the first candidate selected.
2. **Given** the master candidate table is displayed with the perspective dropdown set to "POI", **When** the table renders, **Then** columns shall appear in order `[Select, Status, Photo, POI Name, Country, State/Province, City/Town, Completeness, Disposition]` with the candidate POI name displayed in bold text and sorted alphabetically.
3. **Given** the master candidate table is displayed with the perspective dropdown changed to "Location", **When** the traveler selects "Location", **Then** the table shall dynamically reorder its columns to `[Select, Status, Photo, Country, State/Province, City/Town, POI Name, Completeness, Disposition]` with records grouped geographically by country, state/province, and city/town.
4. **Given** any active perspective view, **When** the traveler clicks a specific column header (e.g., Country or Completeness), **Then** the table shall sort by that clicked column, overriding the perspective default sort while preserving the active column order.

---

### User Story 2 - International ISO Administrative Geocoding & English Translation (Priority: P1)

As an international traveler capturing points of interest across diverse global jurisdictions, I want address data normalized into standardized ISO administrative layers (`country_code`, `admin_level_1`, `admin_level_2`, `locality`, `street_address`, `postal_code`) and negotiated in English, so that points of interest in countries with varied territorial subdivisions (e.g., UK constituent countries, French departments, Japanese prefectures) and non-Latin alphabets parse accurately and predictably.

**Why this priority**: The legacy US-centric `street_address/city/state/country` structure fails on international landmarks, natural attractions, and city-states. Migrating to standard ISO administrative layers with English translation ensures reliable deduplication and presentation worldwide.

**Independent Test**: Can be tested by staging diverse international locations (e.g., an urban museum in Chicago, a natural landmark in Mount Fuji, the Great Wall in China, Petra in Jordan, Singapore city-state, and a post town in the UK) and verifying that administrative tiers and English translations populate correctly without failure.

**Acceptance Scenarios**:

1. **Given** an urban POI with street numbers and named roadways (e.g., a museum in Chicago), **When** reverse geocoding executes against Nominatim, **Then** the system shall parse a combined street address (`house_number` + road/pedestrian/footway), standard postal code, locality, admin_level_2 (county), admin_level_1 (state), and 2-letter uppercase ISO country code (`US`).
2. **Given** a remote or wilderness POI lacking street roadways (e.g., a mountain peak or national park trailhead), **When** geocoding executes, **Then** the system shall persist the candidate with `NULL` for `street_address`, `postal_code`, and `locality` while populating spatial `geom`, `country_code`, and `admin_level_1` without validation errors.
3. **Given** a city-state POI (e.g., Singapore), **When** reverse geocoding executes, **Then** the system shall persist the candidate with `country_code = 'SG'` and `NULL` for `admin_level_1` and `admin_level_2`.
4. **Given** a UK point of interest, **When** reverse geocoding executes, **Then** the system shall map the constituent country (e.g., England, Scotland, Wales) into `admin_level_1` and the post town into `locality`.
5. **Given** any outbound geocoding HTTP request to Nominatim, **When** dispatched, **Then** the system shall attach headers `Accept-Language: en` and query parameter `accept-language=en` to ensure address and place names return in English.

---

### User Story 3 - Interactive Mapping & Proximity Spatial Clustering (Priority: P2)

As a traveler reviewing staged candidates, I want an interactive map for each candidate that displays its plotted coordinate pin, allows dragging or clicking to reposition the coordinates, and visually plots nearby POIs within an adjustable search radius slider, so that I can verify location accuracy and identify duplicates or parent-child nesting geographically.

**Why this priority**: Visual spatial inspection prevents coordinate errors and empowers users to quickly detect when a staged record is a sublocation of a nearby macro-site or an in-batch duplicate.

**Independent Test**: Can be tested by opening a staged candidate with coordinates, dragging the pin on the map, observing latitude/longitude updates, adjusting the "Nearby Search Radius" slider, and verifying that nearby points from both the active import batch and the database render on the map.

**Acceptance Scenarios**:

1. **Given** a candidate with latitude and longitude, **When** selected in the detail pane, **Then** the detail editor shall render an interactive map centered on the candidate with a prominent primary pin.
2. **Given** the interactive map is rendered, **When** the traveler drags the primary pin or clicks a new location on the map, **Then** the latitude and longitude input fields shall update immediately to reflect the new coordinates.
3. **Given** the candidate is displayed on the map, **When** the traveler adjusts the "Nearby Search Radius" slider (e.g. from 1 mi to 10 mi), **Then** the map shall dynamically plot markers for all nearby points from both the existing database and the staged import batch (excluding records marked as ignore or exclude) located within that radius, and display the total count in a nearby points badge.

---

### User Story 4 - Rich Media, Tags Library & Dynamic Website Management (Priority: P2)

As a traveler enriching my captured POIs, I want to manage dynamic website pairs, select tags from my account's Tag Library, associate local photo directories, and review uncropped hero images and visit rationales, so that all rich experiential data captured across Phase 1 and Phase 2 is preserved.

**Why this priority**: Restores missing capabilities identified in Phase 1 and Phase 2 review, replacing static URL fields with flexible website lists, providing vetted tag selection, and enabling local photo directory tracking.

**Independent Test**: Can be tested by adding and removing dynamic website pairs with confirmation dialogs, toggling Tag Library chips, managing local photo directory paths, adding visit dates, and viewing uncropped hero images and color-coded confidence score rationales.

**Acceptance Scenarios**:

1. **Given** a candidate with a hero photo URL, **When** displayed in the detail editor, **Then** the editor shall render an uncropped photo preview directly below the URL input.
2. **Given** a candidate's related websites section, **When** the traveler clicks "Add Website", **Then** the system shall add the `{ name, url }` pair to the candidate; **When** the traveler clicks "Delete" on a website pair, **Then** the system shall prompt the traveler for confirmation (`"Are you sure you want to remove this website?"`) and remove it only upon confirmation.
3. **Given** the traveler has vetted tags in their account "Tags Library", **When** viewing the detail editor, **Then** the system shall render clickable chip pills for each library tag, showing tags active on the candidate as selected and unassociated tags as unselected, toggling selection upon click.
4. **Given** a candidate's local photo directories, **When** the traveler adds a folder path or removes an existing directory, **Then** the system shall update the candidate's `photo_directories` array and persist the change upon save.
5. **Given** a candidate's assigned disposition, **When** rendered in the detail editor, **Then** the editor shall display a readonly text box containing the disposition and text rationale, with a confidence score badge color-coded by tier ($\ge 90\%$ green, $80\text{–}89\%$ lime, $70\text{–}79\%$ yellow, $< 70\%$ orange/red).
6. **Given** an "in_batch_merge" disposition, **When** active on the candidate, **Then** the editor shall display the target candidate being merged into and provide a dropdown to select or change the target merge record.

---

### User Story 5 - AI Enrichment Idempotency & "No Websites" Policy (Priority: P3)

As a traveler executing AI enrichment across a batch of candidates, I want the enrichment engine to respect my manual inputs and skip website scraping if websites already exist or if "No Websites" is verified, so that unnecessary API calls and redundant scraping are avoided.

**Why this priority**: Prevents overwriting user-curated URLs, avoids redundant external lookups for remote landmarks with no web presence, and enforces deterministic idempotency.

**Independent Test**: Can be tested by checking "No Websites" or adding a website to a candidate, triggering "AI Enrich All", and verifying that external website lookup is bypassed for that candidate.

**Acceptance Scenarios**:

1. **Given** a candidate with one or more websites already defined OR with the "No Websites" checkbox enabled, **When** the traveler triggers AI enrichment (single or batch), **Then** the enrichment service shall skip external website lookup and preserve existing links.
2. **Given** a candidate with zero websites and "No Websites" unchecked, **When** AI enrichment runs and finds zero relevant websites, **Then** the system shall automatically set `no_websites = True`.

---

### Edge Cases

- **Non-Latin Alphabetic Place Names**: When geocoding addresses in non-Latin scripts (e.g., Arabic, Cyrillic, Chinese, Japanese, Greek), the system sends `Accept-Language: en` to ensure administrative tiers and streets resolve in English where available, falling back to canonical transliteration if no English name exists.
- **Natural/Wilderness POIs Without Postal Codes**: Mountains, national parks, and offshore reefs lacking postal codes and road names shall store `NULL` for `street_address`, `postal_code`, and `locality` while storing valid `geom` points and country codes without throwing database constraint errors.
- **City-States & Crown Dependencies**: Jurisdictions without administrative level 1 (e.g., Monaco, Vatican City, Singapore) store `NULL` for `admin_level_1` and `admin_level_2` while maintaining `country_code` integrity.
- **In-Batch Duplicate Deletions**: If an in-batch merge target candidate is excluded or ignored, dependent merge sources shall be flagged with a validation warning prompting reassignment before commit.
- **Extremely Tall Hero Images**: Hero images rendered uncropped must have a maximum height limit (e.g. 240px) with `object-fit: contain` to prevent layout reflow from pushing other editor controls off the screen.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: _Ubiquitous_: The database schema shall persist Points of Interest (`pois`) and staged candidates (`ingest_candidates`) using a normalized ISO administrative model consisting of `street_address` (VARCHAR(255), NULLABLE), `postal_code` (VARCHAR(20), NULLABLE), `geom` (Geometry(Point, 4326), NOT NULL), `country_code` (CHAR(2), NOT NULL, uppercase ISO 3166-1 alpha-2), `admin_level_1` (VARCHAR(100), NULLABLE), `admin_level_2` (VARCHAR(100), NULLABLE), `locality` (VARCHAR(150), NULLABLE), `raw_geocoding` (JSONB, NULLABLE), and `photo_directories` (JSONB/array of strings).
- **FR-002**: _Ubiquitous_: The database shall maintain a spatial GiST index on `geom` and a composite B-tree index on `(country_code, admin_level_1, locality)` across both `pois` and `ingest_candidates` tables.
- **FR-003**: _Event-Driven_: When processing Nominatim reverse geocoding responses, the ingestion engine shall assemble `street_address` by combining `address.house_number` and (`address.road` or `address.pedestrian` or `address.footway`), returning `None` if no road element exists.
- **FR-004**: _Event-Driven_: When parsing administrative layers from geocoder responses, the ingestion engine shall resolve:
  - `country_code` as uppercase 2-letter ISO code (`upper(address.country_code)`);
  - `admin_level_1` via fallback chain: `address.state` $\rightarrow$ `address.province` $\rightarrow$ `address.region` $\rightarrow$ `address.state_district` $\rightarrow$ `None`;
  - `admin_level_2` via fallback chain: `address.county` $\rightarrow$ `address.district` $\rightarrow$ `address.department` $\rightarrow$ `None`;
  - `locality` via fallback chain: `address.city` $\rightarrow$ `address.town` $\rightarrow$ `address.municipality` $\rightarrow$ `address.village` $\rightarrow$ `address.hamlet` $\rightarrow$ `address.suburb` $\rightarrow$ `None`.
- **FR-005**: _Ubiquitous_: The geocoding service shall send `Accept-Language: en` headers and query parameter `accept-language=en` on all external Nominatim requests to enforce English place and address representation.
- **FR-006**: _State-Driven_: While the Unified Staging Workbench is open, the user interface shall provide a perspective dropdown switcher with "POI" and "Location" modes.
  - In "POI" mode, the table shall present columns `[Select, Status, Photo, POI Name, Country, State/Province, City/Town, Completeness, Disposition]` sorted alphabetically by POI name.
  - In "Location" mode, the table shall present columns `[Select, Status, Photo, Country, State/Province, City/Town, POI Name, Completeness, Disposition]` sorted geographically by country, state/province, and city/town.
  - POI Name shall always be rendered in bold font.
- **FR-007**: _Event-Driven_: When the traveler clicks any table column header, the workbench shall sort candidates by that column, overriding the perspective's default sort while maintaining active column order.
- **FR-008**: _State-Driven_: While candidate disposition is set to `in_batch_merge`, the detail editor shall display a merge target card indicating the selected merge target row index and name, and provide a dropdown selector to choose another candidate in the current batch.
- **FR-009**: _State-Driven_: While a candidate has a valid hero photo URL, the detail editor shall display an uncropped image preview directly beneath the URL input.
- **FR-010**: _Ubiquitous_: The detail editor shall embed an interactive map displaying the candidate's coordinates with a draggable pin and click-to-relocate handler that updates `latitude` and `longitude` inputs reactively.
- **FR-011**: _State-Driven_: While viewing the candidate map, the system shall plot nearby POIs from both the user's database and the active batch (excluding ignored or excluded records) located within the distance range of the "Nearby Search Radius" slider, displaying a reactive count badge.
- **FR-012**: _Ubiquitous_: The detail editor shall display related websites as dynamic `{ name, url }` pairs with "Add Website" and "Delete" actions.
- **FR-013**: _Event-Driven_: When the traveler clicks the delete action on a website pair, the interface shall prompt the traveler for confirmation (`"Are you sure you want to remove this website?"`) before removing the record.
- **FR-014**: _State-Driven_: While candidate websites count is $\ge 1$ or the "No Websites" checkbox is checked, the AI enrichment worker shall skip external website lookup; if website count is 0 and "No Websites" is unchecked, the worker shall query external sources and automatically set `no_websites = True` if no websites are found.
- **FR-015**: _Ubiquitous_: The detail editor shall display all tags defined in the traveler's account Tag Library (`/api/tags`) as interactive chip pills, highlighting active tags as selected and toggling tag assignment upon click.
- **FR-016**: _Ubiquitous_: The detail editor shall render associated local photo directories with actions to add directory paths and delete existing directory references.
- **FR-017**: _Ubiquitous_: The detail editor shall provide a dedicated multiline textarea for "Reason to Visit" experiential rationale.
- **FR-018**: _Ubiquitous_: The detail editor shall render a readonly textarea displaying the assigned disposition and justification rationale, labeled with a confidence score badge color-coded by threshold ($\ge 90\%$ green, $80\text{–}89\%$ lime, $70\text{–}79\%$ yellow, $< 70\%$ orange/red).
- **FR-019**: _Ubiquitous_: The detail editor shall include an interactive visit dates manager allowing travelers to append and remove ISO-formatted visit dates.
- **FR-020**: _Ubiquitous_: The Photo Scraper CLI and ingestion parser shall format addresses and CSV export headers in alignment with the ISO administrative fields (`country_code`, `admin_level_1`, `admin_level_2`, `locality`, `street_address`, `postal_code`).

---

### Key Entities

- **POI (`pois`)**: The canonical user point of interest entity storing geographic coordinates (`geom`), international ISO administrative boundary tiers (`country_code`, `admin_level_1`, `admin_level_2`, `locality`), micro street address, postal code, related websites list, photo directories list, tags, dates visited, and visit rationale.
- **IngestCandidate (`ingest_candidates`)**: Staged POI record in the import workbench containing pre-commit attributes, calculated confidence scores, recommended disposition, in-batch merge target references, raw geocoder responses, and UI triage state.
- **AddressRecord**: Canonical structured value object encapsulating physical and administrative address attributes with deterministic conversion methods between raw provider payloads and ISO tiers.
- **TagEntity (`tags`)**: Account-scoped classification labels managed in the user's Tag Library and associated to POIs via many-to-many junction tables.

---

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of standard urban, remote natural, UK constituent country, and city-state benchmark POIs parse into valid ISO administrative records without database constraint errors or geocoding failures.
- **SC-002**: 100% of external Nominatim geocoding requests negotiate English place names via `Accept-Language: en`.
- **SC-003**: Travelers can toggle between "POI" and "Location" perspectives in under 100 milliseconds without page reload or loss of staged edits.
- **SC-004**: Staged candidates can be repositioned via map pin dragging or map clicking with coordinates updated immediately in the detail editor.
- **SC-005**: Deleting a website pair prompts confirmation and prevents accidental removal in 100% of deletion attempts.
- **SC-006**: AI enrichment worker executes zero redundant external website lookups for candidates having $\ge 1$ website or `no_websites = True`.
- **SC-007**: 100% of account Tag Library tags display as clickable interactive chips reflecting real-time selection state.

---

## Assumptions

- **Geocoder Availability**: Deterministic geocoding relies on OpenStreetMap Nominatim, respecting the 1 req/sec rate limit with internal PostGIS geocache lookup by normalized address hash.
- **English Language Availability in Nominatim**: OSM Nominatim provides English name aliases for major international landmarks; where English names are absent, Nominatim returns canonical names or standard Latin transliterations.
- **Map Tile Source**: Interactive map rendering in the staging workbench utilizes MapLibre GL with vector or raster base tiles configured in the frontend environment.
- **Browser File Directory Access**: Local photo directory picking relies on standard browser file directory picker APIs (`webkitdirectory` / Directory Picker) where supported, with manual path entry fallback.
