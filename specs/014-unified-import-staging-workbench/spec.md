# Feature Specification: Unified POI Import Staging Workbench

**Feature Branch**: `014-poi-export-import-enhancements-v2`  
**Created**: 2026-11-02  
**Status**: Clarified  
**Input**: User description: "Unified POI Import Staging Workbench: Replace the split Phase 1 (Triage) and Phase 2 (Enrichment Review) modal workflow with a single, unified Import Staging Workbench using strict EARS syntax. In merging the phase 1 & phase 2 data together, restore lost fields and pivot from US-centric city/state/country to a flexible international ISO-based administrative address format across DB, photo scraper, staging, and UI."

---

## Clarifications & Architectural Alignment

### Session 2026-11-02

- **Q (Address Schema Evolution)**: How should the database and domain entities transition from US-centric `city`/`state_province`/`country` to the international ISO model without breaking existing query APIs?
  - **Decision**: Non-Destructive Extension. Add `country_code` (CHAR(2) ISO 3166-1 alpha-2), `admin_level_1` (State/Province/Region), `admin_level_2` (County/District/Department), `locality` (City/Town/Municipality), and `raw_geocoding` (JSONB) to both `pois` and `ingest_candidates`. Existing API response aliases (`city` $\leftrightarrow$ `locality`, `state_province` $\leftrightarrow$ `admin_level_1`) are retained as computed property getters for backward compatibility.
- **Q (Street Address Language)**: What happens if OpenStreetMap Nominatim only has native non-Latin road names (e.g. Chinese characters)?
  - **Decision**: Strict English Prioritization with Fallback. All forward/reverse Nominatim calls explicitly negotiate `Accept-Language: en`. If a road name lacks an English tag and contains non-Latin scripts, the system preserves provider output in `raw_geocoding` while attempting title-cased Latin transliteration or omitting local street names for natural landmarks.
- **Q (Dynamic Websites vs "No Websites" Guard)**: How does the new arbitrary `{ name, url }` website list interact with the `no_websites` anti-scraping guard?
  - **Decision**: Automatic State Alignment. When the website list has $\ge 1$ item, `no_websites` is forced to `false` and the checkbox is disabled. When the list is empty, `no_websites` is enabled and can be toggled manually or set automatically by AI enrichment when 0 external sources are found.
- **Q (Local Photo Directory Browser)**: How should local directory selection work within web security constraints?
  - **Decision**: Modern Web Directory Picker (`window.showDirectoryPicker()`) with fallback to `<input type="file" webkitdirectory />` or Native Messaging host (`nativeHostService.ts`) to retrieve directory path strings without requiring full file upload.
- **Q (Table View Modes)**: How do the "POI" and "Location" column view modes interact with individual column header sorting?
  - **Decision**: Perspective Presets. Selecting "POI" defaults sorting to `poi_name ASC` and arranges columns starting with POI Name. Selecting "Location" defaults sorting to `country_code ASC, admin_level_1 ASC, locality ASC, poi_name ASC` and arranges columns starting with Country/Location. Clicking any individual column header immediately overrides sort order while maintaining the selected column arrangement.

---

## 1. User Scenarios & Testing *(mandatory)*

### User Story 1 - Single-Stage Workbench Navigation & Column Perspectives (Priority: P1)

As a traveler importing places from a travel spreadsheet or photo collection, I want a single unified workbench with configurable column views ("POI" vs "Location"), so that I can inspect and triage candidates either alphabetically or geographically without navigating between separate triage and enrichment dialogs.

**Why this priority**: Eliminates cognitive friction and modal fragmentation, allowing users to instantly group POIs by geographic region or inspect them alphabetically.

**Independent Test**: Upload a CSV with 10+ international places. Verify the workbench displays all candidates in one interactive table. Switch view dropdown from "POI" to "Location", verifying that columns re-order and rows re-sort by country/admin level/locality. Verify clicking column headers sorts dynamically.

**Acceptance Scenarios**:

1. **Given** a user uploads a CSV file and confirms column mappings,  
   **When** staging completes,  
   **Then** the system shall present a single unified Import Staging Workbench displaying all candidates in an interactive table with a right-hand detail editor.
2. **Given** the workbench table view selector is set to "POI",  
   **When** the table renders,  
   **Then** the system shall display columns in order: Checkbox, `#`, Photo, **POI Name** (bolded), Country, State/Province (`admin_level_1`), Town/City (`locality`), Completeness, Disposition, with default primary sort by POI Name ascending.
3. **Given** the workbench table view selector is set to "Location",  
   **When** the user switches to this view,  
   **Then** the system shall reorder columns to: Checkbox, `#`, Photo, Country, State/Province (`admin_level_1`), Town/City (`locality`), **POI Name** (bolded), Completeness, Disposition, with default sort ordered by Country $\rightarrow$ State/Province $\rightarrow$ Locality $\rightarrow$ POI Name.
4. **Given** either view mode is active,  
   **When** the user clicks any column header (e.g. `#`, POI Name, Location, Completeness, Disposition),  
   **Then** the system shall sort rows by that column, overriding the view mode's default sort.

---

### User Story 2 - Comprehensive International Candidate Detail Editing (Priority: P1)

As a traveler reviewing a staged place, I want to view and edit all its core attributes—including an interactive location map, Hero Photo uncropped preview, dynamic website pairs, account Tags Library chips, local photo directories, visit dates, and a rich "Reason to Visit" text box—so that the final committed POI contains complete, accurate information.

**Why this priority**: Ensures that rich data captured during triage or AI enrichment is never lost, and provides visual confirmation of location and imagery before committing to the map.

**Independent Test**: Select a candidate in the workbench. Verify the right-hand panel displays Hero Photo without cropping, an interactive map with marker, dynamic website list, tag selector pills from the account Tags Library, dates visited list, directory paths list, reason to visit textarea, and a color-coded confidence score badge with justification text. Edit fields, move marker on map, and click "Save Candidate Changes". Verify updates persist.

**Acceptance Scenarios**:

1. **Given** an active candidate has a valid `hero_image_url`,  
   **When** the editor renders,  
   **Then** the system shall display the hero photo uncropped below the URL input field.
2. **Given** an active candidate has coordinates set,  
   **When** the editor renders the location section,  
   **Then** the system shall display an interactive map centered on the coordinates with a draggable pin, and updating pin position on the map shall automatically update latitude and longitude input fields.
3. **Given** the candidate editor renders the map,  
   **When** the user adjusts the "Nearby Search Radius" slider,  
   **Then** the system shall render nearby markers on the map for both existing database POIs and active batch candidates (excluding ignored or excluded items) within that radius.
4. **Given** an active candidate,  
   **When** the editor renders related websites,  
   **Then** the system shall display a list of `{ name, url }` pairs with an "Add Website" action and a "Delete" button per pair that prompts for confirmation before removing.
5. **Given** the candidate editor renders the tags section,  
   **When** displaying available tags,  
   **Then** the system shall fetch and display each tag defined in the user's account "Tags Library" as selectable chips, rendering attached tags as selected and unattached tags as unselected.
6. **Given** the candidate editor renders photo directories,  
   **When** the user clicks "Add Directory",  
   **Then** the system shall open a native directory picker to add the folder path, and provide a delete button for each associated path.
7. **Given** an active candidate,  
   **When** the editor renders experiential notes,  
   **Then** the system shall provide a multiline text box for "Reason to Visit".
8. **Given** an active candidate,  
   **When** the editor renders the disposition rationale,  
   **Then** the system shall display a readonly multiline text box containing the assigned disposition justification, with a label including the confidence score color-coded: green for $\ge 90\%$, light green for $80-89\%$, amber/yellow for $70-79\%$, and orange/red for $<70\%$.
9. **Given** an active candidate,  
   **When** the editor renders the visit history,  
   **Then** the system shall provide an interactive dates visited list allowing the user to view, add, and remove individual visit dates.

---

### User Story 3 - ISO-3166 International Administrative Addressing & Geocoding (Priority: P1)

As a traveler importing places worldwide, I want the system to store addresses according to international administrative hierarchy (`country_code`, `admin_level_1`, `admin_level_2`, `locality`, `street_address`, `postal_code`), so that cities in the US, UK, Japan, Jordan, Peru, and city-states like Singapore are accurately represented without US-specific assumptions.

**Why this priority**: Resolves data loss and misclassification for international destinations where "City/State/Country" fails (e.g. UK constituent countries, French departments, Jordan districts, city-states, remote mountain peaks).

**Independent Test**: Geocode and stage urban places (Chicago), UK places (Bath/Edinburgh), city-states (Singapore), and remote natural landmarks (Petra, Great Wall, Machu Picchu). Verify database records store ISO-2 `country_code`, appropriate `admin_level_1`/`admin_level_2`/`locality`, and English street names.

**Acceptance Scenarios**:

1. **Given** an address string or coordinates processed by Nominatim geocoding,  
   **When** the address components are parsed,  
   **Then** the system shall populate:
     - `country_code`: uppercase ISO 3166-1 alpha-2 (e.g., "US", "GB", "CN", "JO", "EG", "PE").
     - `admin_level_1`: State, Province, Region, or Constituent Country (fallback: state $\rightarrow$ province $\rightarrow$ region $\rightarrow$ state_district).
     - `admin_level_2`: County, Department, Prefecture, or District (fallback: county $\rightarrow$ district $\rightarrow$ department).
     - `locality`: City, Town, Municipality, Village, Hamlet, or Suburb (fallback: city $\rightarrow$ town $\rightarrow$ municipality $\rightarrow$ village $\rightarrow$ hamlet $\rightarrow$ suburb).
     - `street_address`: house_number + road/pedestrian/footway in English.
     - `postal_code`: alphanumeric postal code.
     - `raw_geocoding`: full JSON response payload.
2. **Given** a remote natural landmark or wilderness POI (e.g. mountain peak),  
   **When** geocoding resolves,  
   **Then** the system shall persist the record with `street_address`, `postal_code`, and `locality` as `None`/`NULL` without validation failure.
3. **Given** a city-state POI (e.g. Singapore, Monaco, Vatican City),  
   **When** geocoding resolves,  
   **Then** the system shall persist with `admin_level_1` and `admin_level_2` as `None`/`NULL` and `locality` populated.
4. **Given** any geocoding request to Nominatim,  
   **When** the request is dispatched,  
   **Then** the request shall include `accept-language=en` parameter and `Accept-Language: en` header to enforce English street and administrative names.

---

### User Story 4 - Photo Scraper Output Alignment with ISO Model (Priority: P2)

As a traveler using the photo scraper CLI to extract metadata from local vacation photos, I want the scraper CSV output to directly use the new ISO address columns, so that uploading photo scraper CSVs maps automatically into the workbench without manual column tweaking.

**Why this priority**: Eliminates unmapped column warnings when importing photo collections.

**Independent Test**: Run photo scraper CLI on a test folder containing geotagged photos. Verify generated CSV headers include `POI Name`, `Street Address`, `Locality`, `Admin Level 2`, `Admin Level 1`, `Country Code`, `Postal Code`, `Latitude`, `Longitude`, `Dates Visited`, `Photo Directory`. Upload the CSV and verify all fields populate without unmapped header prompts.

**Acceptance Scenarios**:

1. **Given** the photo scraper CLI executes metadata extraction on local photos,  
   **When** exporting candidate CSV rows,  
   **Then** the CSV header shall output `POI Name`, `Street Address`, `Locality`, `Admin Level 2`, `Admin Level 1`, `Country Code`, `Postal Code`, `Latitude`, `Longitude`, `Dates Visited`, `Photo Directory`, `Confidence Score`, `Tags`.
2. **Given** the backend CSV parser receives a photo scraper CSV,  
   **When** column validation runs,  
   **Then** the parser shall automatically recognize and map these headers to their corresponding candidate schema fields.

---

### User Story 5 - Multi-Tier Deduplication & Uniqueness Detection (Priority: P2)

As a traveler importing travel records, I want the system to detect duplicates and suggest nesting using multi-tier signals (`country_code`, `admin_level_1`, `admin_level_2`, `locality`, `poi_name`, and spatial distance), so that duplicate detection is reliable across international naming conventions.

**Why this priority**: Prevents redundant records and incorrect duplicate flags for places with identical names in different administrative districts or countries.

**Independent Test**: Upload a CSV containing two places with the same name in different countries/states (e.g. "Paris, France" vs "Paris, Texas") and places within 50m of existing POIs. Verify same-name different-location entries are marked `Accept (New POI)`, while true spatial duplicates are marked `Potential Duplicate` or `In-Batch Merge`.

**Acceptance Scenarios**:

1. **Given** two candidates share identical or similar POI names but differ in `country_code` or `admin_level_1`,  
   **When** duplicate triage evaluates them,  
   **Then** the system shall classify them as independent unique POIs (`Accept`).
2. **Given** a candidate matches an existing database POI with spatial distance $\le 200$m and trigram similarity $\ge 0.60$,  
   **When** triage evaluates,  
   **Then** the system shall recommend `Update Existing POI` (`POTENTIAL_DUPLICATE`).
3. **Given** two candidates in the same batch match within the spatial and similarity threshold,  
   **When** triage evaluates,  
   **Then** the second candidate shall be recommended as `In-Batch Merge` targeting the primary candidate's row, and the target candidate shall be visibly selected in the editor.

---

### User Story 6 - AI Enrichment Supporting Dynamic Websites & Rich Notes (Priority: P2)

As a user running AI enrichment in the workbench, I want enrichment to populate the new dynamic website list, discover hero photos, synthesize descriptions, and calculate recommended durations, so that my travel records become rich, comprehensive guides.

**Why this priority**: Fills out incomplete POI details automatically while respecting user-edited fields.

**Independent Test**: Click "AI Enrich POI" on a landmark candidate. Verify discovered official websites and Wikipedia links append to `related_websites`, uncropped hero photo URL is found, reason to visit is populated, and duration notes are added.

**Acceptance Scenarios**:

1. **Given** AI enrichment runs on a candidate,  
   **When** external sources (Wikidata, Wikipedia, secondary sources) return websites,  
   **Then** the system shall add them to the candidate's `related_websites` list as `{ name: "Official Website" | "Wikipedia" | provider_name, url: string }` without overwriting existing user links.
2. **Given** an enriched candidate with 0 discovered websites,  
   **When** enrichment completes,  
   **Then** the system shall set `no_websites` to true and preserve the empty website list.
3. **Given** AI enrichment executes,  
   **When** synthesizing travel context,  
   **Then** the system shall populate `reason_to_visit`, `description`, `recommended_duration_hours`, and `hero_image_url` if those fields were previously empty.

---

## 2. Requirements *(strict EARS syntax)*

### Ubiquitous Requirements

- **REQ-WB-001 (Ubiquitous)**: The system shall store POI spatial coordinates in `geom` as `Geometry(Point, 4326)` with a GiST spatial index.
- **REQ-WB-002 (Ubiquitous)**: The system shall store international address fields on `pois` and `ingest_candidates` as `country_code` (CHAR(2) uppercase ISO 3166-1 alpha-2, NOT NULL), `admin_level_1` (VARCHAR(100), NULLABLE), `admin_level_2` (VARCHAR(100), NULLABLE), `locality` (VARCHAR(150), NULLABLE), `street_address` (VARCHAR(255), NULLABLE), `postal_code` (VARCHAR(20), NULLABLE), and `raw_geocoding` (JSONB, NULLABLE).
- **REQ-WB-003 (Ubiquitous)**: The system shall maintain a composite B-tree index on `(country_code, admin_level_1, locality)` on both `pois` and `ingest_candidates`.
- **REQ-WB-004 (Ubiquitous)**: The system shall enforce English language output (`accept-language=en` query parameter and `Accept-Language: en` HTTP header) across all Nominatim forward and reverse geocoding requests.
- **REQ-WB-005 (Ubiquitous)**: The system shall maintain tenant isolation by scoping all candidate, job, POI, exclusion zone, and tag queries by `user_id`.

### Event-Driven Requirements

- **REQ-WB-006 (Event-driven)**: When Nominatim returns geocoding address components, the system shall assemble `street_address` from house number and road/pedestrian/footway, extract alphanumeric `postal_code`, uppercase `country_code`, resolve `admin_level_1` via fallback chain (state $\rightarrow$ province $\rightarrow$ region $\rightarrow$ state_district), resolve `admin_level_2` via fallback chain (county $\rightarrow$ district $\rightarrow$ department), and resolve `locality` via fallback chain (city $\rightarrow$ town $\rightarrow$ municipality $\rightarrow$ village $\rightarrow$ hamlet $\rightarrow$ suburb).
- **REQ-WB-007 (Event-driven)**: When geocoding a remote or wilderness POI lacking street or locality details, the system shall assign `NULL` to `street_address`, `postal_code`, and `locality` without raising an error.
- **REQ-WB-008 (Event-driven)**: When geocoding a city-state POI, the system shall assign `NULL` to `admin_level_1` and `admin_level_2` and populate `locality`.
- **REQ-WB-009 (Event-driven)**: When the user toggles the workbench table view dropdown between "POI" and "Location", the system shall reorder the table columns and sort order accordingly.
- **REQ-WB-010 (Event-driven)**: When the user clicks any column header in the workbench table, the system shall sort the candidates by that column in ascending or descending order, overriding the view mode default sort.
- **REQ-WB-011 (Event-driven)**: When a candidate row is selected, the system shall render its details in the right-hand editor panel, displaying uncropped hero photo preview, interactive map, dynamic websites, tag selector chips, photo directories, visit dates, reason to visit, and disposition justification.
- **REQ-WB-012 (Event-driven)**: When the user moves the pin on the editor map, the system shall update the candidate's latitude and longitude coordinates.
- **REQ-WB-013 (Event-driven)**: When the user adjusts the "Nearby Search Radius" slider, the system shall update the map to render all database POIs and active batch candidates located within that radius distance.
- **REQ-WB-014 (Event-driven)**: When the user clicks "Delete" on a website in the related websites list, the system shall display a confirmation dialog before removing the website pair.
- **REQ-WB-015 (Event-driven)**: When the user clicks "Add Website", the system shall add a new `{ name: "", url: "" }` input row to the list and disable the `no_websites` flag.
- **REQ-WB-016 (Event-driven)**: When the candidate editor loads tags, the system shall fetch the user's account Tags Library and render each tag as an interactive chip showing selected or unselected state.
- **REQ-WB-017 (Event-driven)**: When the user clicks "Add Directory", the system shall invoke the directory browser to capture the folder path and append it to the candidate's directory paths list.
- **REQ-WB-018 (Event-driven)**: When the user clicks "Delete" on a photo directory, the system shall remove the directory path from the list.
- **REQ-WB-019 (Event-driven)**: When the user adds a visit date, the system shall append the date to the candidate's visit dates list.
- **REQ-WB-020 (Event-driven)**: When the user clicks "AI Enrich POI", the system shall synchronously query external sources for the selected candidate and populate empty fields including websites, hero photo, description, and duration notes.
- **REQ-WB-021 (Event-driven)**: When the photo scraper exports metadata, the system shall output CSV columns aligned with the ISO address format (`POI Name`, `Street Address`, `Locality`, `Admin Level 2`, `Admin Level 1`, `Country Code`, `Postal Code`, `Latitude`, `Longitude`, `Dates Visited`, `Photo Directory`).

### State-Driven Requirements

- **REQ-WB-022 (State-driven)**: While a candidate has `disposition = in_batch_merge`, the system shall display the target primary candidate row in the editor and require a valid target reference before saving.
- **REQ-WB-023 (State-driven)**: While the candidate editor displays the disposition justification, the system shall style the confidence score badge green ($\ge 90\%$), light green ($80-89\%$), amber/yellow ($70-79\%$), or orange/red ($<70\%$).
- **REQ-WB-024 (State-driven)**: While `no_websites` is true, the system shall skip external website lookups during AI enrichment.
- **REQ-WB-025 (State-driven)**: While a candidate's related websites list contains at least one entry, the system shall uncheck and disable the `no_websites` checkbox.

### Unwanted Behavior Requirements

- **REQ-WB-026 (Unwanted behavior)**: If an address string contains leading/trailing whitespace or empty strings, the system shall trim whitespace and convert empty strings to `NULL`.
- **REQ-WB-027 (Unwanted behavior)**: If circular parenting is attempted when assigning a parent POI or sublocation, the system shall reject the assignment with a descriptive error.
- **REQ-WB-028 (Unwanted behavior)**: If an uncommitted staging session exists when the user attempts a new upload, the system shall block the upload with a `409 Conflict` until the session is committed or discarded.

---

## 3. Success Criteria *(measurable outcomes)*

- **SC-001**: 100% of forward and reverse geocoded POIs persist ISO-compliant `country_code`, `admin_level_1`, `admin_level_2`, and `locality` fields.
- **SC-002**: 100% of geocoding results for international landmarks (e.g. Great Wall of China, Petra, Giza) return English administrative and street names.
- **SC-003**: Workbench table allows toggling between "POI" and "Location" perspectives with $<100$ms UI rendering latency.
- **SC-004**: Users can complete inspection, editing, AI enrichment, and commitment of an 8-candidate batch without leaving the single workbench screen.
- **SC-005**: Dynamic website lists allow arbitrary Name/URL additions with zero schema errors or data loss upon commit.
- **SC-006**: Tag assignment from the account Tags Library functions as single-click chip toggles for 100% of registered tags.
- **SC-007**: Photo scraper CSV output maps with 100% column parity to the staging import engine.
- **SC-008**: Existing database records migrate non-destructively with zero data loss and automated backfill of ISO country codes and administrative levels.

---

## 4. Key Entities & Database Schema Changes

```
┌─────────────────────────────────────────────────────────────┐
│                          POIs                               │
├─────────────────────────────────────────────────────────────┤
│ id: UUID (PK)                                               │
│ user_id: UUID (FK)                                          │
│ name: VARCHAR(255)                                          │
│ geom: GEOGRAPHY(Point, 4326) [GIST INDEX]                   │
│ country_code: CHAR(2) [INDEX]                               │
│ admin_level_1: VARCHAR(100) [INDEX]                         │
│ admin_level_2: VARCHAR(100)                                 │
│ locality: VARCHAR(150) [INDEX]                              │
│ street_address: VARCHAR(255)                                │
│ postal_code: VARCHAR(20)                                    │
│ raw_geocoding: JSONB                                        │
│ related_websites: JSONB                                     │
│ hero_image_url: VARCHAR(2000)                               │
│ photo_directories: JSONB                                    │
│ visited_dates: JSONB                                        │
│ reason_to_visit: TEXT                                       │
│ description: TEXT                                           │
│ tags: JSONB                                                 │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Committed from
┌─────────────────────────────┴───────────────────────────────┐
│                    Ingest Candidates                        │
├─────────────────────────────────────────────────────────────┤
│ id: UUID (PK)                                               │
│ job_id: UUID (FK)                                           │
│ user_id: UUID (FK)                                          │
│ row_index: INT                                              │
│ poi_name: VARCHAR(255)                                      │
│ latitude: NUMERIC(10, 7)                                    │
│ longitude: NUMERIC(10, 7)                                   │
│ country_code: CHAR(2)                                       │
│ admin_level_1: VARCHAR(100)                                 │
│ admin_level_2: VARCHAR(100)                                 │
│ locality: VARCHAR(150)                                      │
│ street_address: VARCHAR(255)                                │
│ postal_code: VARCHAR(20)                                    │
│ raw_geocoding: JSONB                                        │
│ recommended_disposition: VARCHAR(50)                        │
│ user_disposition: VARCHAR(50)                               │
│ disposition_justification: TEXT                             │
│ confidence_score: INT                                       │
│ related_websites: JSONB                                     │
│ no_websites: BOOLEAN                                        │
│ hero_image_url: VARCHAR(2000)                               │
│ photo_directory: VARCHAR(1000)                              │
│ photo_directories: JSONB                                    │
│ dates_visited: JSONB                                        │
│ reason_to_visit: TEXT                                       │
│ description: TEXT                                           │
│ tags: JSONB                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Non-Destructive Migration Plan (Alembic)

1. **Migration Script**: `20261102_add_iso_address_fields.py`
2. **Table `pois` Alterations**:
   - Add `country_code CHAR(2) NULLABLE` (temporarily nullable for backfill).
   - Add `admin_level_1 VARCHAR(100) NULLABLE`.
   - Add `admin_level_2 VARCHAR(100) NULLABLE`.
   - Add `locality VARCHAR(150) NULLABLE`.
   - Add `raw_geocoding JSONB NULLABLE`.
   - Add `related_websites JSONB DEFAULT '[]'::jsonb`.
   - Add `photo_directories JSONB DEFAULT '[]'::jsonb`.
   - Backfill:
     - `UPDATE pois SET locality = city WHERE locality IS NULL AND city IS NOT NULL;`
     - `UPDATE pois SET admin_level_1 = state_province WHERE admin_level_1 IS NULL AND state_province IS NOT NULL;`
     - `UPDATE pois SET country_code = UPPER(SUBSTRING(country, 1, 2)) WHERE country_code IS NULL AND country IS NOT NULL;`
     - `UPDATE pois SET country_code = 'US' WHERE country_code IS NULL;`
   - Set `country_code NOT NULL`.
   - Create composite index: `CREATE INDEX idx_pois_iso_location ON pois (country_code, admin_level_1, locality);`.
3. **Table `ingest_candidates` Alterations**:
   - Add `country_code CHAR(2) NULLABLE`.
   - Add `admin_level_1 VARCHAR(100) NULLABLE`.
   - Add `admin_level_2 VARCHAR(100) NULLABLE`.
   - Add `locality VARCHAR(150) NULLABLE`.
   - Add `raw_geocoding JSONB NULLABLE`.
   - Add `photo_directories JSONB DEFAULT '[]'::jsonb`.
   - Create composite index: `CREATE INDEX idx_candidates_iso_location ON ingest_candidates (country_code, admin_level_1, locality);`.
