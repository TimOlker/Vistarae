# Feature Specification: Phase 13 — Multi-Stage POI Export, Flexible Multi-Fidelity Import & Ingestion Enhancements

**Feature Identifier**: `013-poi-export-import-enhancements`  
**Feature Branch**: `013-poi-export-import-enhancements`  
**Created**: 2026-10-31  
**Status**: Draft  
**Target Systems**:
- **Shared Extractor, Exporter & Serializer Engine**: `packages/core/vistarae_core/services/poi_exporter.py`, `packages/core/vistarae_core/services/poi_importer.py`, `packages/core/vistarae_core/schemas/poi_exchange.py`
- **Web App Ingestion Gateway & Triage Services**: `services/ingest/routes/upload.py`, `services/ingest/routes/export.py`, `services/ingest/routes/triage.py`, `services/ingest/routes/phase2.py`, `services/ingest/services/flexible_parser.py`, `services/ingest/services/staging_service.py`
- **Worker & Parallel Enrichment Pipeline**: `services/worker/candidate_enricher.py`, `services/worker/processor.py`
- **Web App Frontend (Explorer & Ingestion Modals)**: `frontend/src/components/poi/POITable.tsx`, `frontend/src/components/poi/POIFilterBar.tsx`, `frontend/src/components/poi/POIEditDrawer.tsx`, `frontend/src/components/ingest/CSVUploadModal.tsx`, `frontend/src/components/ingest/ColumnMappingModal.tsx`, `frontend/src/components/ingest/CSVTriageModal.tsx`, `frontend/src/components/ingest/CSVPhase2ReviewModal.tsx`, `frontend/src/components/ingest/TagValidationWarningModal.tsx`, `frontend/src/components/ingest/ImportValidationErrorModal.tsx`
- **Database & Domain Entities**: `pois` table (`created_at` timestamp with time zone, spatial indexes, tag bindings), `ingest_candidates` staging table.

**Input**: User description:
> "Create the specification for Phase 13 (013-poi-export-import-enhancements) using strict EARS syntax.
>
> Importing POIs is time consuming. It takes a significant amount of time (even with automated tools) to validate that POIs have been properly classified, this is made even worse by the potentially large volume of records that may need to be processed. This enhancement makes it possible to export POI data at each incremental step in the process. This allows for there to be an incremental backup incase something goes wrong, but it will also make it easier to import POI data from different tools that are not related to vistarae and make it simple to import the data without needing to do a lot of massaging the data to make it fit in with what vistarae supports. Vistare should be able to import structured data in different common formats (like CSV, JSON and YAML), but by default CSV will be the format used since it is prevalent and easy to use. This should also help a user community share data with each other. This should support data at different levels of processing. If data has already been calculated (like the wikipedia URL / description / tags / etc have already been calculated, then there is no need to re-calculate unless explicitly requested).
>
> POI Import Logic:
> - the POI import logic should support importing various levels of details from imported data (like a CSV). The goal is to be flexible in mapping the user's data into the fields vistarae supports. The tool will map what it can, then attempt to determine the POI location, then attempt to fill in whatever data is missing using other data sources available. Some scenarios are:
>   a) POI import data could be a list of POI names with no location, and then the phase 1 logic is executed to attempt to determine only on POI name - this will give the user best guess of a latitude/longitude and address - if it can not determine, or there are too many options, do not assign a result and indicate the reasoning in phase 1 output. The data that is mapped should be able to flow into phase 2.
>   b) POI import data could be a list of POI names with latitude/longitude, then using the latitude/longitude, find the most likely POI near that latitude/longitude and determine the address - and other details.
>   c) POI import data could be a list of POI names with address, then using the address, find the most likely POI nearby and determine the latitude/longitude and other details.
>   d) POI import data could be a list of POI names with latitude/longitude and address data (all the fields from phase 1). As long as the values pass the range check logic, then phase 1 does not need to do any mapping, it will just need to check to make sure there are no duplicates. The user can then pick & choose which POIs to exclude (if any) then progress on to phase 2.
>   e) POI import data could be a list of POI names with latitude/longitude, address data, description, reason to visit, tags, etc (all the fields from phase 1 and phase 2). As long as the values pass the range check logic, then phase 1 does not need to do any mapping, it will just need to check to make sure there are no duplicates. The user can then pick & choose which POIs to exclude (if any) then progress to phase 2 which will see all the fields are populated and no need to do any LLM queries to derive the data.
> - range checking - make sure the data is well formed - make sure the date is valid, if tags are provided in the import data, only accept the ones that are in the user's tag library defined in the user's preferences. Have a popup displayed to the user as early in the process as possible so the user can abort and add tags to their library and then re-attempt the import.
> - by default use all fields, but provide the option to specify certain fields to re-calculate - for example the POI description field may be provided in the import data, but the user wants it to be re-generated.
>
> POI Export Logic:
> The user should be able to export the data at different phases
> a) In the vistarae explorer - the multiple-select logic can be used to select which records to include, and then click an export button 
> b) on the import phase 1 window - export all selected records - if no records are selected then export all records
> c) on the import phase 2 window - export all selected records - if no records are selected then export all records
> - The export logic will generate a POI file (initially a CSV file) that can then be used to backup data, be processed by other tools or be used to share with other users. This file should be well formatted and be able to be imported back into vistarae and minimize the loss of data.
>
> General:
> Whenever a POI is added (no matter the mechanism POI import/browser extension/manual add/etc), include the date/time the POI was added into vistarae. This should be a field displayed in vistarae explorer and can be used to filter the POIs.
>
> User Adjustments & Refinements:
> - change the logic: if 0 checked rows, display a prompt to the user and abort - only export what is selected
> - implement a canonical alias dictionary in the ingestion parser mapping common variants automatically to vistarae's fields - when importing - if not an exact match, prompt the user to define what columns in their input data align with columns vistarae is looking for - before importing make sure a column contains data that is correctly formatted (for example if a column is identified as holding longitude and it contains boolean values - abort and notify the user of the issue(s) found
> - When exporting data - include all columns, even if data is not present for them so they can seamlessly be imported. Do not use a static or hardcoded list of columns; instead, dynamically reflect whatever core fields the application supports so as new data points are added to the POI model, exports automatically include them.
> - Closing the modal, navigating to Preferences -> Tag Library to add missing tags, and re-uploading the CSV causes user friction. Resolution: The Early Tag Validation Dialog provides 3 one-click actions: Abort Import, Strip Unapproved Tags, or Approve & Add All to Library (which immediately persists them to the user's tags table and continues the import).
> - Exporting large collections (≥2,000 POIs) into JSON/YAML/CSV could spike serverless memory. Resolution: Mandated streaming chunk HTTP responses to keep memory consumption under ≤ 128MB.
> - when importing a POI file ensure that processing is broken up so that the heavy processing of each POI is done individually so multiple can be done in parallel, but it is throttled so processing does not exceed resources
> - make sure the amount of input data is flexible, not just listed to the scenarios (Section 2: Tier-A - Tier E). These example scenarios were just given as reference and should not be limited to them.
>
> Please flag any contradictions or missing logic or features to include that might be useful."

---

## 1. Executive Summary & Context

Phase 13 establishes an industrial-grade, bi-directional POI Data Exchange architecture for Vistarae. It removes the operational friction and processing latency associated with large-scale POI import, verification, and migration.

Phase 13 delivers:
1. **Strictly Selective, Multi-Stage Incremental Data Export**:
   - Available across the **Vistarae Explorer**, **Phase 1 Ingestion Triage**, and **Phase 2 Ingestion Review**.
   - **Selection Gate**: If 0 rows are checked, the system aborts the export and displays a user notification (`"No records selected. Please select at least one record to export."`). Only explicitly checked records are exported.
   - **Dynamically Derived Schema-Driven Export**: All exported files (CSV default, JSON, and YAML) dynamically derive their columns from the core POI schema contract rather than maintaining a static or hardcoded column list. As new data points are introduced to the core application model, the export engine automatically introspects the schema and includes them in all outputs—emitting all core columns (even when specific values are empty)—ensuring future-proof, flawless round-trip re-ingestion without manual column maintenance.
   - **Chunked HTTP Response Streaming**: Keeps server memory strictly under $\le 128\text{MB}$ regardless of dataset size.
2. **Flexible, Dynamic Per-Field Import Engine**:
   - Ingests structured datasets with arbitrary field presence (not constrained to fixed scenario archetypes). Every candidate record is evaluated independently for missing attributes.
   - **Canonical Alias Dictionary & Interactive Column Mapping**: Automatically resolves third-party headers; if any column cannot be definitively matched, prompts the user with an **Interactive Column Mapping Dialog** displaying live data previews.
   - **Pre-Import Type & Format Sanity Gate**: Inspects column data types before ingestion starts (e.g., verifying that a column mapped to `longitude` contains valid floating-point numbers between -180 and 180, not booleans or arbitrary text). If format violations are detected, processing aborts immediately with an actionable error modal detailing offending row numbers and invalid values.
3. **Decoupled, Parallel & Throttled Processing Pipeline**:
   - Decomposes bulk import jobs into isolated, per-POI units of work executed concurrently via an asynchronous worker pool.
   - Strictly throttles outbound external requests (enforcing Nominatim's 1 req/sec policy via a global token bucket and bounding concurrent LLM API quotas) to avoid rate limits or compute exhaustion.
4. **Early Tag Library Gatekeeper**:
   - Validates incoming tags against the user's active Tag Library prior to writing candidate records to the database.
   - Displays the **Early Tag Validation Dialog** with 3 instant resolution options: **Abort Import**, **Strip Unapproved Tags**, or **Approve & Add All to Library** (persisting new tags directly to the database without forcing manual navigation to Preferences).
5. **Selective Re-Calculation Overrides**:
   - Preserves all pre-calculated values by default. Provides granular user toggles to force re-calculation of specific fields (such as AI Description or Personalized Reason to Visit) using the user's Travel Style Profile directives.
6. **Universal Creation Audit Timestamp (`created_at`)**:
   - Records UTC creation timestamps for every POI regardless of ingestion channel (file upload, Chrome extension, or manual drawer), exposed as a visible table column and date filter in the Explorer.

---

## Clarifications

### Session 2026-10-31

- Q: When pre-import validation detects format or type errors on a subset of rows (for example, 3 out of 500 rows contain invalid coordinates or unparseable dates), how should the system handle the valid remaining records? → A: Option A (Interactive Choice: Display the error modal with specific row/column errors and provide two buttons: *"Skip [N] Invalid Rows & Continue"* or *"Abort Import"*).
- Q: When POIs are exported from Vistarae, should the exported file include internal record identifiers (`poi_id`), and how should the system handle them during re-import? → A: Option A (Tenant-Scoped ID Reconciliation: Include `poi_id` in exports; upon re-import, if the ID matches an existing record owned by the current user (`WHERE poi_id = :poi_id AND user_id = :current_user_id`), treat as an update candidate; if imported by a different user, disregard the foreign ID and assign fresh tenant-owned IDs upon commit).
- Q: Should CSV exports include a UTF-8 Byte Order Mark (BOM) to ensure international characters (such as accented letters or Japanese kanji) display properly in Microsoft Excel on Windows? → A: Option A (Include UTF-8 BOM: Automatically prepend `\xef\xbb\xbf` to CSV exports to ensure immediate compatibility with Excel on Windows while retaining standard UTF-8 parsing in other tools).

---

## 2. Analysis of Contradictions, Missing Logic & Useful Recommendations

### Items Flagged & Resolved

1. **Contradiction / UX Barrier: Strict Selection Export vs Large Paginated Lists**
   - *Issue*: Because exporting now strictly requires checked rows (aborting on 0 checked rows), users wishing to export hundreds of filtered records across paginated tables would face tedious manual clicking.
   - *Resolution / Requirement*: The UI shall provide a prominent **"Select All [N] Records"** header checkbox in Explorer, Phase 1, and Phase 2. When filters are active, it offers **"Select all [N] matching current filter"**, allowing users to check all desired records with a single click before exporting.
2. **Missing Logic: Interactive Column Mapping Preview & Unmapped Columns**
   - *Issue*: When input headers are non-standard and prompt the user to map columns, the user cannot easily tell what data a column holds without seeing samples.
   - *Resolution / Requirement*: The **Interactive Column Mapping Dialog** shall display the first 3 sample values for each uploaded column alongside a dropdown of Vistarae target fields, with an explicit `[Ignore / Do Not Import]` option for irrelevant columns.
3. **Missing Logic: Pre-Import Validation Scope & Granular Error Diagnostics**
   - *Issue*: If a file of 500 rows contains a single boolean or text string in `longitude`, simply saying "invalid data" forces frustrating manual debugging.
   - *Resolution / Requirement*: The **Import Validation Error Modal** shall identify the exact column name, expected data type, and a diagnostic list of up to the first 5 offending row numbers with their invalid values (e.g. `Row 14: expected numeric longitude between -180 and 180, found 'true'`).
4. **Missing Logic: Global Token Bucket Throttling across Parallel Workers**
   - *Issue*: Processing each POI individually in parallel tasks could easily overwhelm Nominatim's strict 1 request per second policy or trigger Gemini API 429 rate limit errors.
   - *Resolution / Requirement*: Parallel POI workers shall consume from a shared centralized rate limiter (token bucket algorithm enforcing $\le 1.0\text{ req/sec}$ for Nominatim and a concurrency semaphore of $\le 5$ simultaneous LLM tasks).
5. **Useful Addition: Lossless Export Schema Versioning**
   - *Issue*: As Vistarae evolves in future phases, export schemas could drift.
   - *Resolution / Requirement*: Every exported file shall include an optional metadata header or schema declaration field (`schema_version: "1.3"`) allowing the parser to guarantee backward-compatible import.

---

## 3. User Scenarios & Testing _(mandatory)_

### User Story 1 - Traveler Selectively Exports Incremental POIs Across Workflow Phases (Priority: P1)

A traveler reviewing 150 POIs in Phase 1 Triage selects 12 specific candidates. They click the "Export" button in the modal header and choose "CSV". The browser downloads a standardized CSV containing exactly those 12 candidates, with all core application fields dynamically emitted as columns (including their current `user_disposition`, coordinates, and addresses, while uncomputed Phase 2 columns like `ai_description` remain cleanly empty).

If the traveler accidentally clicks "Export" without checking any boxes, the system does not download anything; instead, it displays an alert banner: `"No records selected. Please check at least one record to export."` 

Later, after committing the POIs to the database, the traveler navigates to the Vistarae Explorer, checks 25 POIs, and exports them to YAML. The downloaded YAML file dynamically includes all core POI fields (including the newly added `created_at` timestamp and enriched tags). When a future application update adds new fields (such as accessibility ratings or seasonal opening hours) to the core POI schema, subsequent exports automatically include these new fields without requiring changes to the export formatter.

**Why this priority**: Eliminates accidental mass exports, guarantees user intent, and ensures future-proof, schema-driven data snapshots across all stages of the travel planning lifecycle.

**Independent Test**:
- Attempt export with 0 rows checked in Explorer, Phase 1, and Phase 2; verify export aborts and displays the user notification banner.
- Select 3 rows in Phase 1; export to CSV; assert that the downloaded file contains exactly 3 data rows plus 1 header row, with all core schema fields present as columns.

**Acceptance Scenarios**:

1. **Given** 0 rows are checked in Explorer, Phase 1, or Phase 2, **When** the user clicks "Export", **Then** the system aborts the export and displays a warning prompt notifying the user to select at least one record.
2. **Given** $N$ rows are explicitly checked, **When** the user confirms export to CSV, JSON, or YAML, **Then** the system serializes and downloads exactly those $N$ records.
3. **Given** any export operation in Explorer, Phase 1, or Phase 2, **When** the file is generated, **Then** the output dynamically reflects all fields defined in the application's core POI schema, leaving non-applicable or uncomputed attributes as empty values.

---

### User Story 2 - Importing Third-Party Files with Interactive Column Alignment & Type Validation (Priority: P1)

A traveler exports a hiking itinerary from an external mapping application (`trails.csv`). The CSV uses non-standard headers: `Waypoint`, `Lon`, `Lat`, `Notes`, `Category`.

Upon upload, Vistarae's parser automatically recognizes `Lat` as `latitude`, `Lon` as `longitude`, and `Category` as `tags` via the canonical alias dictionary. However, `Waypoint` and `Notes` are ambiguous. The system opens the **Interactive Column Mapping Dialog**, showing:
- `Waypoint` (Samples: "Old Faithful", "Grand Prismatic") -> User selects `POI Name`.
- `Notes` (Samples: "Steep climb", "Geyser basin") -> User selects `AI Description` or `[Ignore]`.

Before advancing to staging, the pre-import validation engine scans the mapped columns:
- If `Lon` contains a malformed boolean or string on row 7 (e.g. `'true'`), the import immediately halts and displays the **Import Validation Error Modal** stating: `"Invalid data in column 'Lon' (mapped to Longitude). Row 7 contains 'true'. Expected numeric coordinate between -180 and 180."` The modal presents two options: *"Skip 1 Invalid Row & Continue"* or *"Abort Import"*. The traveler can click "Skip" to discard row 7 and safely proceed with the remaining valid records, or "Abort" to fix their source file.
- If all values are valid floats, the import proceeds immediately to Tag Library validation.

**Why this priority**: Empowers users to bring in data from any external travel software without manually editing spreadsheet headers in Excel, while providing strict pre-flight protection against corrupted data and flexible handling of isolated row flaws.

**Independent Test**:
- Upload a CSV with headers `Place`, `X`, `Y`; verify that `X` and `Y` are mapped or presented for mapping with sample values.
- Upload a file where a longitude column contains text `"invalid"` on 1 row; verify that the validation modal provides "Skip Invalid Row & Continue" and "Abort Import" actions; select "Skip" and verify valid rows proceed to staging.

**Acceptance Scenarios**:

1. **Given** an uploaded file with headers not found in the alias dictionary, **When** parsing executes, **Then** the system displays the Interactive Column Mapping Dialog with sample row values.
2. **Given** a mapped column contains values incompatible with the target field's type constraints (e.g., boolean in longitude), **When** pre-import validation runs, **Then** the system displays the Import Validation Error Modal detailing the column, row numbers, and sample invalid values, allowing the user to skip the invalid rows or abort the import.
3. **Given** the user selects "Skip Invalid Rows & Continue", **When** staging commences, **Then** only rows passing format validation are queued for staging.
4. **Given** all mapped columns satisfy type and range constraints, **When** validation completes, **Then** the system advances to Tag Library verification.

---

### User Story 3 - Early Tag Library Resolution Dialog (Priority: P2)

A traveler uploads an overseas itinerary containing tags `Historical`, `Ramen`, and `Onsen`. The traveler's existing Vistarae Tag Library only includes `Historical` and `Food`.

Before any candidate records are written to the database or sent to geocoders, the system displays the **Early Tag Validation Dialog**:
`"Found 2 tags not in your library: 'Ramen' (8 POIs), 'Onsen' (5 POIs)"`.

The dialog provides three buttons:
1. `Approve & Add All to Library`: Directly inserts `Ramen` and `Onsen` into the user's `tags` table and continues import without leaving the modal.
2. `Strip Unapproved Tags`: Drops `Ramen` and `Onsen` from candidate records, keeping only `Historical`.
3. `Abort Import`: Cancels the upload session immediately.

The traveler clicks `Approve & Add All to Library`. The modal saves the tags to the user's preferences, binds them to the candidate rows, and advances to processing.

**Why this priority**: Eliminates user friction by removing the need to navigate back and forth to Preferences while preserving complete taxonomy discipline.

**Independent Test**: Upload a dataset with unapproved tags; choose "Approve & Add All"; assert new tags exist in the user's `tags` table and are attached to staged candidates.

**Acceptance Scenarios**:

1. **Given** unvetted tags in an uploaded dataset, **When** pre-flight validation runs, **Then** the system presents the Early Tag Validation Dialog detailing unapproved tags and counts.
2. **Given** the user selects "Approve & Add All to Library", **When** processed, **Then** the system creates the tags in the database and preserves them on the candidate records.
3. **Given** the user selects "Strip Unapproved Tags", **When** processed, **Then** only existing library tags are retained.
4. **Given** the user selects "Abort Import", **When** clicked, **Then** the upload is terminated cleanly.

---

### User Story 4 - Decoupled Parallel & Throttled Processing of Arbitrary Fields (Priority: P2)

A traveler imports 100 POIs with arbitrary, non-uniform data:
- 30 POIs have names and addresses, but no coordinates.
- 20 POIs have coordinates, but no addresses.
- 50 POIs have complete coordinates, addresses, descriptions, and tags.

The ingestion engine processes each of the 100 POIs as an independent task via an async worker pool:
- The 50 fully populated POIs bypass geocoding and LLM workers instantly.
- The 30 address-only POIs and 20 coordinate-only POIs are queued for forward/reverse geocoding.
- A centralized token bucket throttles outbound geocoding queries strictly to 1 request per second, while LLM enrichment tasks run with bounded concurrency ($\le 5$).

The user observes the progress bar update smoothly as individual POIs finish, and the entire job completes without exceeding API rate limits or server memory.

**Why this priority**: Ensures rock-solid reliability and speed when processing large, heterogeneous travel lists.

**Independent Test**: Ingest a mixed dataset of 50 POIs; assert that geocoding queries never exceed 1 req/sec; verify that each POI dynamically resolves only its missing fields.

**Acceptance Scenarios**:

1. **Given** imported records with arbitrary combinations of populated fields, **When** ingestion runs, **Then** the system dynamically resolves only the missing attributes per individual POI.
2. **Given** concurrent geocoding requests across parallel POI workers, **When** outbound HTTP calls are dispatched, **Then** the shared rate limiter enforces a maximum rate of 1 request per second.

---

### User Story 5 - Tracking and Filtering POIs by Creation Date (`created_at`) (Priority: P3)

A traveler wants to inspect only the POIs added during a recent import session. In the Vistarae Explorer, the traveler selects `Date Added: Today` from the filter bar. The table updates instantly to display the 45 POIs added today, with the formatted timestamp visible in the "Date Added" column.

**Acceptance Scenarios**:

1. **Given** any newly created POI, **When** saved to the database, **Then** `created_at` is populated with the current UTC timestamp.
2. **Given** an active `created_at` filter in Explorer, **When** the view renders, **Then** only POIs created within the specified range are displayed.

---

## 4. Requirements _(mandatory)_

### Functional Requirements

#### Multi-Stage Incremental POI Export Engine

- **REQ-EXP-001**: **Ubiquitous**: The system shall provide POI export capabilities across three distinct application workflows: Vistarae Explorer, Phase 1 Ingestion Triage, and Phase 2 Ingestion Review.
- **REQ-EXP-002**: **Ubiquitous**: The export engine shall support serialization into RFC 4180 CSV (default), structured JSON, and YAML formats. For all CSV exports, the serializer shall prepend a UTF-8 Byte Order Mark (`\xef\xbb\xbf`) to ensure that international non-ASCII characters display accurately in Microsoft Excel on Windows without character corruption.
- **REQ-EXP-003**: **Unwanted Behaviour**: If a user initiates an export in Explorer, Phase 1, or Phase 2 when zero (0) records are checked, then the system shall abort the export operation and display an alert prompt instructing the user to select at least one record.
- **REQ-EXP-004**: **Event-Driven**: When a user initiates an export with one or more records checked, the export engine shall serialize exclusively the checked records.
- **REQ-EXP-005**: **Ubiquitous**: The export engine shall dynamically introspect and serialize the complete superset of core domain fields defined in the application's central POI data model (`POIExchangeRecord` in `packages/core`), guaranteeing that newly added POI attributes are automatically discovered and included in exported files without requiring hardcoded static column lists or modifications to export formatters.
- **REQ-EXP-006**: **Ubiquitous**: The export engine shall emit all core schema columns across all export phases and formats, outputting an empty representation (or null) for any fields that are uncomputed or not yet populated for a given record, including the baseline core schema attributes:
  1. `poi_id` (string/UUID, populated for committed POIs; empty for raw staged candidates)
  2. `poi_name` (string)
  3. `latitude` (float, WGS-84)
  4. `longitude` (float, WGS-84)
  5. `street_address` (string)
  6. `city` (string)
  7. `state_province` (string)
  8. `postal_code` (string)
  9. `country` (string)
  10. `tags` (semicolon-delimited string or array)
  11. `dates_visited` (semicolon-delimited ISO dates or array)
  12. `photo_directory` (string)
  13. `location_confidence_percent` (integer, 0-100)
  14. `user_disposition` (string: `accept`, `ignore`, `update_existing`, `sublocation`)
  15. `rejection_reason` (string)
  16. `ai_description` (string)
  17. `reason_to_visit` (string)
  18. `recommended_duration_hours` (float)
  19. `itinerary_days` (integer)
  20. `hero_image_url` (string)
  21. `official_website` (string)
  22. `wikipedia_url` (string)
  23. `created_at` (ISO 8601 UTC timestamp)
  ... and any future attributes added to `POIExchangeRecord`.
- **REQ-EXP-007**: **Unwanted Behaviour**: If an exported cell value begins with formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`), then the CSV serializer shall prepend a single quote (`'`) to neutralize formula injection vulnerabilities.
- **REQ-EXP-008**: **Ubiquitous**: The export engine shall stream response data in chunked HTTP streams, maintaining memory usage $\le 128\text{MB}$ regardless of dataset size.
- **REQ-EXP-009**: **State-Driven**: While displaying selectable POI lists in Explorer, Phase 1, and Phase 2, the UI shall provide a "Select All" header toggle that allows selecting all currently visible or filtered records in a single action.

#### Flexible Ingestion Parser, Column Mapping & Format Sanity Check

- **REQ-IMP-001**: **Event-Driven**: When a file is uploaded, the parser shall detect format by file extension and MIME type (`.csv`, `.json`, `.yaml`, `.yml`), defaulting to RFC 4180 CSV with automatic handling for files with or without a UTF-8 Byte Order Mark (`utf-8-sig`).
- **REQ-IMP-002**: **Ubiquitous**: The ingestion parser shall map incoming headers using a canonical alias dictionary:
  - `latitude`: `lat`, `y`, `latitude`, `lat_wgs84`
  - `longitude`: `lon`, `lng`, `long`, `x`, `longitude`, `lon_wgs84`
  - `poi_name`: `name`, `title`, `place`, `poi`, `poi_name`, `waypoint`
  - `street_address`: `address`, `street`, `addr`, `street_address`
  - `city`: `town`, `locality`, `city`, `municipality`
  - `state_province`: `state`, `province`, `region`, `state_province`
  - `postal_code`: `zip`, `zipcode`, `postal_code`, `postcode`
  - `country`: `nation`, `country`
  - `tags`: `tag`, `categories`, `keywords`, `labels`, `tags`
  - `ai_description`: `description`, `desc`, `notes`, `summary`, `ai_description`
  - `reason_to_visit`: `why_visit`, `reason_to_visit`
  - `dates_visited`: `visit_date`, `date_visited`, `dates_visited`, `dates`
- **REQ-IMP-003**: **Complex**: While parsing an uploaded file, when one or more columns do not match canonical names or alias dictionary entries, the system shall display the Interactive Column Mapping Dialog showing column names, 3 sample values per column, and a field mapping dropdown.
- **REQ-IMP-004**: **Event-Driven**: When the user confirms column mappings in the Interactive Column Mapping Dialog, the pre-import validator shall execute type and format sanity verification on all mapped columns.
- **REQ-IMP-005**: **Unwanted Behaviour**: If a mapped column contains data incompatible with its target schema type (e.g., boolean or non-numeric text values in a column mapped to `latitude` or `longitude`), then the system shall halt staging and display the Import Validation Error Modal detailing the column name, offending row numbers, and sample invalid values, offering the user two actionable resolution paths:
  1. *"Skip [N] Invalid Rows & Continue"*: Discard the invalid rows, proceed with staging the remaining valid records, and log the skipped rows.
  2. *"Abort Import"*: Terminate the import session cleanly without persisting any candidate rows.
- **REQ-IMP-006**: **Complex**: While processing imported POIs, the ingestion engine shall evaluate field presence dynamically per individual record:
  - If coordinates are missing but address is present, query forward geocoding.
  - If address is missing but coordinates are present, query reverse geocoding.
  - If both coordinates and address are missing, query forward geocoding by POI name.
  - If both coordinates and address are present, bypass geocoding.
  - If rich enrichment attributes (`ai_description`, `reason_to_visit`, tags) are present, bypass LLM workers unless explicitly flagged for re-calculation.
- **REQ-IMP-007**: **State-Driven**: While matching imported records against existing database records, if an imported record contains a `poi_id`, the repository shall verify ownership via `WHERE id = :poi_id AND user_id = :current_user_id`:
  - If a matching record is found under `:current_user_id`, the ingestion engine shall classify the candidate with `user_disposition = "update_existing"` and link `matched_existing_poi_id = poi_id`.
  - If no matching record is found under `:current_user_id` (e.g. cross-user shared export), the ingestion engine shall disregard the foreign ID, execute standard spatial/trigram deduplication, and assign a newly generated UUID upon database commit.

#### Decoupled Parallel & Throttled Worker Execution

- **REQ-WRK-001**: **Ubiquitous**: The backend ingestion service shall decompose bulk import jobs into discrete, per-POI tasks processed concurrently via an asynchronous worker pool.
- **REQ-WRK-002**: **State-Driven**: While executing concurrent geocoding tasks across worker threads, the geocoding service shall route all outbound requests through a shared rate limiter enforcing a strict maximum rate of 1.0 request per second for Nominatim.
- **REQ-WRK-003**: **State-Driven**: While executing concurrent LLM enrichment tasks, the worker pool shall enforce an upper concurrency ceiling of 5 simultaneous LLM requests to stay within API rate quotas.

#### Early Tag Library Gatekeeper

- **REQ-VAL-001**: **Event-Driven**: When pre-import validation completes, the system shall compare all incoming tags against the user's active Tag Library (`tags` table) using case-insensitive matching.
- **REQ-VAL-002**: **State-Driven**: While checking tags, if any unvetted tags are discovered, the system shall halt processing before writing candidate rows to `ingest_candidates` and display the Early Tag Validation Dialog.
- **REQ-VAL-003**: **Event-Driven**: When the user clicks "Approve & Add All to Library", the system shall insert the missing tags into the user's `tags` repository, attach them to the candidate records, and proceed with ingestion.
- **REQ-VAL-004**: **Event-Driven**: When the user clicks "Strip Unapproved Tags", the system shall discard unapproved tags from candidate records and proceed with ingestion.
- **REQ-VAL-005**: **Event-Driven**: When the user clicks "Abort Import", the system shall terminate the import session immediately.

#### Selective Re-Calculation Overrides

- **REQ-REC-001**: **Ubiquitous**: The ingestion engine shall preserve pre-calculated values present in uploaded files by default.
- **REQ-REC-002**: **Optional Feature**: Where the user checks specific re-calculation overrides during upload (Description, Reason to Visit, Tags, Duration, or Links), the worker pool shall regenerate exclusively those selected fields via AI enrichment.

#### Creation Timestamp Auditing (`created_at`)

- **REQ-AUD-001**: **Ubiquitous**: Every POI inserted into PostgreSQL shall record its UTC creation timestamp in `created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`.
- **REQ-AUD-002**: **Ubiquitous**: The Vistarae Explorer shall render "Date Added" as a sortable table column and provide date range filtering options in the Explorer filter bar.

---

## 5. Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: **Zero-Selection Export Prevention**: 100% of export attempts with 0 checked rows are prevented, displaying the user notification banner without triggering file downloads.
- **SC-002**: **Lossless Round-Trip Schema Parity**: 100% of files exported from Explorer, Phase 1, or Phase 2 dynamically include all core POI fields defined in the application data contract and can be re-imported into Vistarae without missing data or column realignment.
- **SC-003**: **Type Violation Abort Speed**: The Import Validation Error Modal displays within 1 second of upload when type violations occur (such as non-numeric coordinates), preventing invalid database writes.
- **SC-004**: **Throttling Compliance**: Under maximum parallel load of 100 concurrent candidate workers, outbound requests to Nominatim strictly observe the $\le 1.0\text{ req/sec}$ rate limit.
- **SC-005**: **One-Click Tag Library Approval**: Approving unvetted tags via the Early Tag Validation Dialog updates the user's Tag Library and stages candidates in under 1.5 seconds.
- **SC-006**: **Streaming Memory Efficiency**: Exporting datasets up to 5,000 POIs maintains backend process memory consumption under $\le 128\text{MB}$.
