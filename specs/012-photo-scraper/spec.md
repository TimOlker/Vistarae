# Feature Specification: Phase 12 — Photo Scraper CLI & Two-Phase Interactive CSV Ingestion

**Feature Identifier**: `012-photo-scraper`  
**Feature Branch**: `012-photo-scraper`  
**Created**: 2026-10-28  
**Status**: Draft  
**Target Systems**:

- **Standalone Photo Scraper CLI Tool**: `services/scraper/photo_scraper.py`, `services/scraper/path_parser.py`, `services/scraper/metadata_extractor.py`, `services/scraper/location_resolver.py`, `services/scraper/cache.py`
- **Shared Extractor & CSV Formatter Engine**: `packages/core/vistarae_core/services/csv_exporter.py`, `packages/core/vistarae_core/schemas/poi_export.py`
- **Web App CSV Ingestion & Progress Gateway**: `services/ingest/routes/upload.py`, `services/ingest/routes/jobs.py`, `services/ingest/services/csv_parser.py`, `services/worker/processor.py`
- **Two-Phase Interactive Triage & Enrichment Endpoints**: `services/ingest/routes/triage.py`, `services/poi/services/geocoding_service.py`, `services/poi/scraping/orchestrator.py`
- **Web App UI (Import, Review & Triage Modals)**: `frontend/src/components/ingest/CSVUploadModal.tsx`, `frontend/src/components/ingest/CSVProgressModal.tsx`, `frontend/src/components/ingest/CSVTriageModal.tsx`, `frontend/src/components/ingest/CSVPhase2ReviewModal.tsx`, `frontend/src/components/poi/POIEditDrawer.tsx`
- **Database & Domain Models**: PostgreSQL 16+ / PostGIS / `pois` table (`directory_paths`, `visited_dates`, `addresses`, `parent_poi_id`, `reason_to_visit`), `ingest_candidates` staging table (`user_id`, `job_id`, row payload, triage state, enriched attributes), `geocache` table.

**Input**: User description:

> "Photoscraper:
> - enhance the photo scraper a standalone CLI based tool that looks at a directory starting directory and recursively searches through the sub-directories looking photos that have been previously taken to identify POIs to include in the Vistarae application.
> - avoid duplicating logic included in the vistarae CSV import logic. They should work in concert with each other.
> - Assume that each directory holds one POI from a single visit
> - The same POI could have been visited in different years
> - the sub directories are not standardized
> - ignore sub folders (doing a caseless search) that have names like "bad", "thumb", "thumbs", "thumbnails", "RESOURCE.FRK", "misc". Also ignore sub folders that start with a period "." (that indicate a hidden folder). Ignore folders that start with "New Folder" or "New Folder (2)" or "New Folder (5)", etc. Ignore "Tim" and "Maria" since these are people names.
> - If a folder caseless that starts with "Trip To " treats the value after words for example "Trip To India" as "India" (do a lookup to determine that this is a country). Treat the following folders as locations in "India". The location might be a region, state or country. Treat "Japan 4-03" as "Japan" (do a lookup to determine that this is a country). If a number starts with a number or single letter followed by a dash remove it. For example, "1-Tokyo" treat as "Tokyo", treat "A-Kobe" as "Kobe". If a (parenthesis) this may indicate that a location is an alternate name for the location. For example the sub folder "Senso-ji (Asakusa Kannon Temple)" is "Senso-ji" also known as "Asakusa Kannon Temple".
> - attempt to determine the location name by looking at each sub [path].
> - use the LLM to attempt to determine a location name. Provide found latitude/longitude from photo, any found tags from photo, from filtered sub folder names as input to determine a location name. Ask for a confidence on the name match and to get address.
> - The goal is to get as solid of a hit on a location, but if no good address can be determined - for example "M:\Photos\master\Tim\2010\Sledding" is very generic so without a latitude/longitude to determine a POI - this should be given a very low confidence score.
> - cache data to reduce API calls where possible
> - the final output should be a CSV file written in a format that the Vistarae's webapp can import.
> - The CSV export should reuse common logic that other extractor scripts leverage. This should include outputting data to a CSV with a standardized list of columns. If the specific data for a column is not found and no default rules are explicitly given, leave the value for that column empty for a given POI.
> - data for the POI is obtained by looking through images included in the folder. The tags included in the image should be abstracted. If a latitude/longitude is present, use them. Look for the data visited. If multiple photos are found with different dates, use the lowest occurring date found. If no latitude/longitude is found in any photos, leave that blank. Ignore directories that begin with a dot ".".
> - the directories are NEVER to be written to. Never do anything that will alter / modify / delete a directory or file in the scanned directory or sub directories.
> - if there are multiple locations for a detected POI, reduce the confidence score. For example if the most significant location identified is McDonalds, the LLM's predicted location score should be much lower.
> - Add the ability to check with a previous execution of the CLI script's output to make sure an already processed directory is not added.
> - Export the fields at least the following fields, and any others that may be relevant for the CSV import of the web application: POI Name, Street Address (list), Town/City (list), State/Province (list), Zip Code (list), Country (list), Tags, latitude, longitude, dates visited (list), Photo directory, location_confidence_percent.
>
> Vistarae CSV Import:
> - enhance the existing CSV import logic of vistarae
> - The logic should be: read CSV, process each POI, attempt to determine location, attempt to determine if existing POI.
> - merge data together and display phase 1 data to make sure records are valid & associated with correct location before running LLM parsing logic.
> - look at disposition of each POI: ignore, accept, update existing POI, sublocation.
> - phase 2: each POI not skipped executes disposition logic. If new POI, web scrape and use LLM to determine description, reason to visit, tags using user's customized profile prompt.
> - display phase 2 info in a table to review with toggle skip, edit window, map location select, save to DB and cancel buttons.
> - batched processing logic, progress bar, geocoding fallbacks, caching.
>
> Image Metadata & Sidecar Extensions:
> - EXIF should be supported, if there are other supported standards with image meta data, please support them as well.
> - Also support common side car file formats that may contain metadata about an image."

---

## 1. Executive Summary & Context

Phase 12 bridges personal photographic travel archives with the Vistarae discovery engine. Travelers possess vast libraries of historical digital photos organized across irregular folder hierarchies (e.g. `M:\Photos\master\Tim\2003\Japan 4-03\1-Tokyo\Senso-ji (Asakusa Kannon Temple)`). These archives hold genuine Points of Interest (POIs), visit dates, and geographical coordinates, but are frequently cluttered with non-standard naming, ambiguous labels ("Sledding", "New Folder"), personal names, missing coordinate metadata, or metadata stored across various standards (EXIF, IPTC, XMP) and external sidecar files (`.xmp`, `.json`, `.xml`).

Phase 12 addresses this through two interconnected, non-duplicative systems:

1. **Standalone Photo Scraper CLI Tool**: An offline, strictly read-only filesystem scanner that traverses photo directories, filters noise, parses geographic hierarchy heuristics, extracts metadata across all major embedded standards (EXIF, IPTC-IIM, embedded XMP) and companion sidecar formats (Adobe `.xmp`, Google Photos `.json`, `.xml`), queries LLM and geocoding services to resolve ambiguous locations, assigns confidence scores, and produces a standardized RFC 4180 CSV export. The tool supports state-based incremental execution to prevent re-processing directories across runs.
2. **Enhanced Two-Phase Web Application CSV Ingestion Engine**: An interactive ingestion pipeline within the Vistarae web application that consumes standardized CSV exports. Phase 1 performs progressive geocoding fallbacks and deduplication, presenting a triage review interface with interactive map pins and four discrete dispositions (`accept`, `ignore`, `update existing POI`, `sublocation`). Phase 2 triggers downstream web scraping and personalized LLM enrichment (incorporating the traveler's custom travel style prompt directives from Phase 11) exclusively on validated POIs before committing changes to the database.

---

## Clarifications

### Session 2026-10-28

- Q: How should tenant ownership (`user_id`) be bound to POI records extracted by the standalone photo scraper CLI? → A: Session-Bound at Ingestion: The CLI produces a clean, user-agnostic CSV without `user_id`. Tenant ownership is assigned strictly during Web App CSV upload via the authenticated user's JWT context.
- Q: When a user sets or confirms the `sublocation` disposition for a POI during Phase 1 triage, how should the parent POI be selected or overridden if no macro-site was automatically detected? → A: Interactive Map Marker Selection: The user clicks an existing POI marker directly on the Phase 1 interactive map to link it as the parent POI, or confirms the auto-detected parent marker.
- Q: Where should staged candidate records and their Phase 1 triage decisions be persisted while awaiting Phase 2 enrichment and final user confirmation? → A: Database Staging Table: Staged candidates and their Phase 1 edits reside in an `ingest_candidates` table partitioned by `user_id` and `job_id`, enabling resilient async enrichment and recovery on page refresh, purged automatically upon commit or cancellation.
- Q: When merging a record classified as `update existing POI` during final commit, how should differences in coordinates and street addresses between the incoming photo data and the existing database POI be reconciled? → A: Preserve Primary with Opt-In Update: Retain existing primary coordinates and address by default, appending visit dates, directory paths, tags, and new address records to the existing POI, with an explicit "Update Coordinates" toggle available in the edit drawer for intentional coordinate replacements.
- Q: How should the standalone photo scraper CLI behave when running in an offline environment or without an active Google AI API key? → A: Strict Online Requirement: The CLI requires an active network connection and valid `GOOGLE_API_KEY` environment variable, immediately halting execution with an actionable error message if credentials or network connectivity are missing.

---

## 2. User Scenarios & Testing _(mandatory)_

### User Story 1 - Traveler Scans Irregular Photo Archive with CLI Scraper (Priority: P1)

A traveler runs the standalone Photo Scraper CLI against their historical photo repository (`M:\Photos\master`).

The CLI recursively inspects folders, skipping system and noise folders (such as `thumbs`, `.hidden`, `New Folder (2)`, `Tim`, `misc`). When traversing nested paths such as `M:\Photos\master\Tim\2003\Japan 4-03\1-Tokyo\Senso-ji (Asakusa Kannon Temple)`, the CLI recognizes:
- Trip/Country context: `Japan` (stripping `4-03`)
- City context: `Tokyo` (stripping `1-`)
- Location candidate: `Senso-ji` with alternate name `Asakusa Kannon Temple`

Within the leaf folder, the CLI reads image files and companion sidecars without modifying any file timestamps or attributes. It extracts GPS coordinates from embedded EXIF, IPTC, or XMP tags, or from companion sidecars (such as `.xmp` or Google Photos `.json`). It discovers capture dates `2003-04-12` and `2003-04-13` across photos, selecting `2003-04-12` as the earliest visit date. It invokes the location resolver LLM with the path segments, coordinates, and extracted tags. The LLM confirms the location with high confidence (95%) and returns the formatted address. The CLI writes the structured record into `vistarae_pois.csv`.

**Why this priority**: Core engine capability; without accurate directory parsing, multi-standard metadata extraction, sidecar support, and CSV generation, no photo-derived POIs can enter Vistarae.

**Independent Test**: Execute `vistarae-scraper --input-dir ./test_photos --output-csv ./output.csv`, assert no filesystem modifications occur in `./test_photos`, assert noise directories are ignored, and verify `./output.csv` contains standardized columns with correctly parsed POI name, coordinates, earliest visit date, and confidence percentage derived from EXIF, IPTC, XMP, or sidecars.

**Acceptance Scenarios**:

1. **Given** a directory containing valid photo subfolders and ignored noise subfolders (e.g. `bad`, `thumbs`, `New Folder`), **When** the CLI runs, **Then** the CLI skips all noise subfolders and processes only candidate POI directories.
2. **Given** a directory path with numeric prefixes (e.g. `1-Tokyo`, `03 Oaxaca`), **When** path parsing executes, **Then** prefixes are stripped to yield clean locality tokens (`Tokyo`, `Oaxaca`).
3. **Given** photos with missing EXIF GPS coordinates but companion `.xmp` or `.json` sidecar files containing coordinates, **When** metadata extraction executes, **Then** the CLI resolves coordinates from the companion sidecar file.
4. **Given** a directory containing multiple photos taken on different dates across EXIF, IPTC, or sidecars, **When** metadata extraction executes, **Then** the CLI records the earliest date as the visit date.
5. **Given** any directory or file in the scanned tree (including image and sidecar files), **When** the CLI runs, **Then** no file or directory is modified, created, moved, or deleted within the target photo directory.

---

### User Story 2 - Incremental Scanning via Previous Execution Output (Priority: P1)

A traveler previously processed `M:\Photos\master\2002` and generated `scan_2002.csv`. They later add new folders for 2003 and re-run the CLI against `M:\Photos\master`, supplying `--previous-csv scan_2002.csv`.

The CLI reads the previous CSV, loads all already-processed `Photo directory` values into memory, and skips any directory present in the previous execution output. Only unvisited or newly added directories are scanned and queried against LLM and geocoding services, conserving time and API quota.

**Why this priority**: Large photo archives contain thousands of folders; re-scanning entire archives wastes API budget and hours of processing time.

**Independent Test**: Run the CLI with `--previous-csv` pointing to a pre-existing CSV, assert that directories listed in the previous CSV are skipped without executing LLM or geocoding calls, and assert only new directories appear in the output.

**Acceptance Scenarios**:

1. **Given** a previous execution CSV file containing processed directories, **When** the CLI executes with the previous CSV specified, **Then** all directories present in the previous CSV are skipped.
2. **Given** a directory present in the previous CSV with new photos added, **When** the CLI runs with default skip mode, **Then** the directory is skipped; where `--rescan-existing` is passed, the directory is re-evaluated.

---

### User Story 3 - Ambiguous Location Scoring & Low Confidence Flagging (Priority: P2)

A traveler has a folder `M:\Photos\master\Tim\2010\Sledding` containing photos of a neighborhood hill with no EXIF GPS data. Another folder is named `M:\Photos\master\2015\McDonalds`.

When processing `Sledding`, the location resolver detects that the label is a generic activity with no geographic context or GPS coordinates. The LLM assigns `location_confidence_percent = 10` and leaves address fields blank. When processing `McDonalds`, the resolver recognizes a ubiquitous multi-location franchise without distinct identifying coordinates, assigning `location_confidence_percent = 25`.

When imported into the web app, both records automatically default to the `ignore` disposition during Phase 1 triage, preventing low-quality entries from polluting the user's travel map.

**Why this priority**: Photo archives frequently contain generic family activities or ubiquitous brands; without confidence scoring and automatic triage filtering, users are overwhelmed with junk data.

**Independent Test**: Feed a folder named `Sledding` without GPS and a folder named `McDonalds` without GPS to the CLI, verify both receive confidence scores under 30%, import into the web app, and verify both default to `ignore`.

**Acceptance Scenarios**:

1. **Given** a photo directory with a generic label and no GPS coordinates, **When** confidence evaluation runs, **Then** the CLI assigns a low confidence score (< 30%).
2. **Given** a directory matching a multi-location brand without coordinates, **When** confidence evaluation runs, **Then** the CLI penalizes the confidence score relative to unique landmarks.

---

### User Story 4 - Web App Ingestion Progress & Phase 1 Validation Triage (Priority: P1)

A traveler opens the Vistarae web application, navigates to POI Import, and uploads `vistarae_pois.csv`.

The web application displays a real-time progress bar tracking batch preparation, geocoding resolution, and database deduplication:
- For rows with coordinates but missing street addresses, the system executes reverse geocoding to resolve street, city, state, and country.
- For rows with missing coordinates, the system performs structured geocoding matching against available address tokens.
- For each row, the system checks for spatial and name duplicates against the user's existing POIs.

Upon completion, the application opens the **Phase 1 Validation Window**:
- A data table displays all imported candidates with recommended dispositions:
  - `accept`: Valid new POI ready for enrichment.
  - `ignore`: Low-confidence or unmappable record (e.g. `Sledding`).
  - `update existing POI`: Duplicate match identified within spatial threshold.
  - `sublocation`: Candidate detected near or inside an existing macro-site (e.g. `Monte Alban` inside `Oaxaca`).
- The traveler can edit POI name, address fields, dates, and directory path.
- The traveler can click an interactive map to adjust or pinpoint coordinates.
- The traveler changes an erroneous `ignore` to `accept`, edits a misspelled name, and clicks **Proceed to Phase 2**.

**Why this priority**: Solves the user's major pain point: manually cleaning up erroneous POIs from the map is exhausting. Validating records before running expensive LLM enrichment prevents data corruption and quota waste.

**Independent Test**: Upload a CSV with 5 POIs (1 exact duplicate, 1 child site, 1 low-confidence generic, 2 new landmarks), verify progress bar reaches 100%, assert Phase 1 modal opens with correct recommended dispositions, edit 1 record's coordinates via map pin, and verify state advances cleanly.

**Acceptance Scenarios**:

1. **Given** an uploaded CSV, **When** processing begins, **Then** the web app renders an active progress bar reflecting processed row percentages.
2. **Given** rows with coordinates and empty address fields, **When** pre-validation runs, **Then** the system executes reverse geocoding to populate address fields.
3. **Given** rows matching existing database POIs within spatial and trigram thresholds, **When** deduplication runs, **Then** the system assigns `update existing POI` and links the existing POI.
4. **Given** the Phase 1 modal, **When** the user clicks **Cancel**, **Then** the entire staging batch is aborted without creating or modifying database POIs.
5. **Given** the Phase 1 modal, **When** the user clicks **Proceed**, **Then** only non-ignored records advance to Phase 2 enrichment.

---

### User Story 5 - Phase 2 AI Enrichment & Final Confirmation (Priority: P1)

Following Phase 1 approval, the backend initiates Phase 2 processing for accepted and sublocation candidates.

The backend scraper orchestrator gathers external web context for the confirmed POI name and coordinates. The LLM synthesis service receives this scraped text along with the traveler's custom travel style prompt directives (from Phase 11) to generate:
- An objective destination `description`
- A personalized `reason_to_visit` tailored to the traveler's travel preferences
- Contextual travel tags

The application displays the **Phase 2 Review Window**:
- A table lists all enriched POIs with their generated descriptions, reasons to visit, and visit tags.
- For each POI, a toggle allows skipping the record.
- An **Edit** button opens the POI detail drawer to modify generated content.
- An interactive map shows all candidate markers simultaneously.
- A **Save to DB** button executes the final transaction:
  - `accept` entries are inserted as new POIs.
  - `sublocation` entries are inserted with `parent_poi_id` set to the parent POI.
  - `update existing POI` entries merge `visited_dates`, `directory_paths`, and tags into the existing record.

**Why this priority**: Guarantees rich, personalized content while retaining user control before writing to the database.

**Independent Test**: Advance an accepted POI through Phase 2, verify generated `reason_to_visit` incorporates user prompt preferences, toggle skip on one POI, click **Save to DB**, and assert database contains the new POI with correct parent linkages and merged dates.

**Acceptance Scenarios**:

1. **Given** non-ignored candidates advancing from Phase 1, **When** Phase 2 executes, **Then** the system scrapes external data and invokes the LLM with user prompt customizations to synthesize `description` and `reason_to_visit`.
2. **Given** the Phase 2 review table, **When** the user edits a field or toggles skip, **Then** the review state updates immediately.
3. **Given** an entry marked `update existing POI`, **When** the user clicks **Save to DB**, **Then** the system appends new visit dates and directory paths to the existing POI without overwriting existing user-curated descriptions.
4. **Given** an entry marked `sublocation`, **When** saved, **Then** the system creates the child POI with foreign key reference to the parent POI.

---

### User Story 6 - Cross-Year Multi-Visit Merging (Priority: P2)

A traveler visited `Garfield Park Conservatory` in 2002 (stored in `M:\Photos\master\Tim\2002\Garfield Park Conservatory`) and visited again in 2005 (`M:\Photos\master\Tim\2005\Garfield Park Conservatory`).

When the CLI scans both directories, it generates two rows in the CSV with the same POI name, matching address, but different `dates visited` (`2002-06-15` and `2005-09-20`) and different `Photo directory` values.

During Phase 1 import, the deduplication engine recognizes that the second row matches the first row (or an existing database POI). The system recommends `update existing POI`. Upon final confirmation, the POI aggregates both visit dates `['2002-06-15', '2005-09-20']` and both photo directories into its record.

**Why this priority**: Travelers return to favorite places over years; systems must aggregate travel history rather than creating duplicate clutter.

**Independent Test**: Import a CSV containing the same POI across two distinct years, verify the system flags the second as `update existing POI`, commit the import, and verify `visited_dates` and `directory_paths` contain both entries.

**Acceptance Scenarios**:

1. **Given** multiple CSV rows representing the same POI from different years, **When** deduplication evaluates the records, **Then** the second occurrence is classified as `update existing POI`.
2. **Given** merged records, **When** saved to the database, **Then** the POI stores the union of all visit dates and photo directory paths.

---

### Edge Cases

- **Scanned Photo Directory Read-Only Invariant**: If any operation in the CLI attempts to open a file with write access, create a lockfile in the scanned tree, or delete temporary files within the target photo directory, then the CLI shall throw a fatal security error and abort to protect original user media and sidecar files.
- **Hidden and Noise Folders**: Folders starting with a period (`.DS_Store`, `.git`, `.thumbnails`), named `RESOURCE.FRK`, `thumbs`, `thumb`, `bad`, `misc`, or people names (`Tim`, `Maria`), or matching pattern `New Folder*` are pruned from traversal immediately.
- **Path Cleaning with Roman Numerals or Letters**: Subfolders like `1-Tokyo`, `1 - Fussen`, `A-Kobe`, `03 Oaxaca`, `02 Parque Museo De La Venta` have prefixes stripped cleanly, yielding `Tokyo`, `Fussen`, `Kobe`, `Oaxaca`, and `Parque Museo De La Venta`.
- **Parentheses for Alternate Names**: Paths containing parentheses such as `Senso-ji (Asakusa Kannon Temple)` are split into primary name `Senso-ji` and alternate name `Asakusa Kannon Temple`, passing both to the location resolver.
- **Trip and Country Token Extraction**: Paths like `Trip To India` or `Japan 4-03` are normalized by extracting the country token (`India`, `Japan`) via dictionary and gazetteer lookup, establishing a regional boundary context for all nested child folders.
- **Generic Folders without GPS**: Folders labeled `Sledding`, `Beach`, `Picnic`, or `Walk` without GPS coordinates receive a confidence score $\le 10\%$ and are assigned disposition `ignore` by default in Phase 1 triage.
- **Ubiquitous Brand Names**: Folders named `McDonalds`, `Starbucks`, or `Shell` without GPS coordinates are flagged with low confidence ($\le 25\%$) due to spatial ambiguity across thousands of locations.
- **Multi-Standard Metadata & Sidecar Resolution**: When EXIF GPS tags are absent, the CLI inspects embedded IPTC and XMP segments, as well as companion `.xmp` and Google Photos `.json` sidecars (`<file>.xmp`, `<file>.<ext>.xmp`, `<file>.json`, `<file>.<ext>.json`). When valid coordinates are found in any standard or sidecar, the CLI converts coordinates to decimal WGS-84 format. When absent across all sources, latitude and longitude fields are left blank.
- **Multiple Photos with Discrepant Dates**: When photos within a single POI folder contain differing capture timestamps across EXIF, IPTC, XMP, or sidecars, the CLI selects the earliest chronological timestamp as the visit date.
- **Geocoding API Rate Limiting**: Outbound queries to Nominatim are rate-limited to 1 request per second with User-Agent `VistaraeTravelEngine/1.0`, checking local SQLite/PostGIS `geocache` prior to any network dispatch.
- **Missing API Credentials or Offline Network**: If the CLI detects that `GOOGLE_API_KEY` is unset or network connectivity to Google AI Studio is unavailable, the CLI shall immediately abort traversal with an actionable error message instructing the user to configure credentials and check internet access.
- **Batch Processing within AWS Free Tier**: Web app CSV import processing chunks rows into batches of 10 messages dispatched to SQS with visibility timeout 180s, keeping execution within AWS Lambda free tier limits.
- **Address List Alignment**: When a POI contains multiple addresses or multi-tier address records, the CSV export aligns semicolon-delimited lists across `Street Address`, `Town/City`, `State/Province`, `Zip Code`, and `Country` by index.

---

## 3. Requirements _(mandatory)_

### Functional Requirements

#### CLI Photo Scraper & Directory Discovery

- **REQ-SCR-001**: **Ubiquitous**: The photo scraper CLI tool shall operate exclusively with read-only filesystem access permissions, strictly prohibiting any write, rename, create, or delete operation on scanned directories and files.
- **REQ-SCR-002**: **Event-Driven**: When invoked with a starting directory path (`--input-dir`), the photo scraper CLI shall recursively traverse subdirectories to discover candidate POI folders.
- **REQ-SCR-003**: **Ubiquitous**: The photo scraper CLI shall assume each valid leaf photo directory represents one Point of Interest (POI) from a single visit.
- **REQ-SCR-004**: **State-Driven**: While traversing directory trees, the photo scraper CLI shall ignore subfolders matching caseless noise names: `bad`, `thumb`, `thumbs`, `thumbnails`, `resource.frk`, and `misc`.
- **REQ-SCR-005**: **State-Driven**: While traversing directory trees, the photo scraper CLI shall ignore any folder whose name begins with a period (`.`).
- **REQ-SCR-006**: **State-Driven**: While traversing directory trees, the photo scraper CLI shall ignore any folder whose name begins with `New Folder` (including variations such as `New Folder (2)` and `New Folder (5)`).
- **REQ-SCR-007**: **State-Driven**: While traversing directory trees, the photo scraper CLI shall ignore subfolders matching configured personal names, including `Tim` and `Maria`.
- **REQ-SCR-008**: **Event-Driven**: When a previous execution CSV file is supplied via `--previous-csv`, the photo scraper CLI shall inspect the `Photo directory` column of the previous file and skip scanning any directory already recorded therein.
- **REQ-SCR-009**: **Optional Feature**: Where the user specifies `--rescan-existing`, the photo scraper CLI shall re-evaluate directories present in the previous execution output rather than skipping them.

#### Path Cleaning & Contextual Hierarchy Heuristics

- **REQ-SCR-010**: **Event-Driven**: When parsing a directory whose name begins with caseless `Trip To ` (e.g. `Trip To India`), the path parser shall strip the prefix and validate the trailing string against a country and administrative region gazetteer.
- **REQ-SCR-011**: **State-Driven**: While processing nested folders beneath a confirmed trip or country folder, the path parser shall inject the identified country or region as the geographic parent context for all child directories.
- **REQ-SCR-012**: **Event-Driven**: When parsing folder names formatted with a country name followed by date tokens (e.g. `Japan 4-03`), the path parser shall isolate the country token (`Japan`) via gazetteer lookup and strip trailing date qualifiers.
- **REQ-SCR-013**: **Event-Driven**: When parsing a folder name beginning with a number or single letter followed by a dash (e.g. `1-Tokyo`, `1 - Fussen`, `A-Kobe`, `03 Oaxaca`, `03 Monte Alban`), the path parser shall strip the leading prefix and whitespace, extracting the cleaned locality name.
- **REQ-SCR-014**: **Event-Driven**: When parsing a folder name containing parenthetical content (e.g. `Senso-ji (Asakusa Kannon Temple)`), the path parser shall extract the primary name before the parentheses (`Senso-ji`) and record the parenthetical text as an alternate name (`Asakusa Kannon Temple`).
- **REQ-SCR-015**: **Complex**: While traversing hierarchical paths lacking explicit coordinates, when ancestor folder names represent country and city (e.g. `.../Mexico/03 Oaxaca/03 Monte Alban`), the path parser shall construct a qualified geographic hierarchy tuple (`country: Mexico`, `city: Oaxaca`, `poi: Monte Alban`).
- **REQ-SCR-016**: **State-Driven**: While evaluating regional US landmark directories lacking coordinates (e.g. `Garfield Park Conservatory`, `Herrik Lake`), the path parser shall associate the candidate with default state context `Illinois` based on user home region heuristics.

#### Photo Multi-Standard Metadata & Sidecar Extraction (Read-Only)

- **REQ-SCR-017**: **Event-Driven**: When scanning a candidate POI folder, the metadata extractor shall inspect supported image files (`.jpg`, `.jpeg`, `.tiff`, `.heic`, `.png`, `.webp`, `.dng`) and companion sidecar files (`.xmp`, `.json`, `.xml`).
- **REQ-SCR-018**: **State-Driven**: While extracting embedded image metadata, the metadata extractor shall parse EXIF (2.3+), IPTC-IIM, and embedded XMP (RDF/XML) data segments for geographic coordinates, capture dates, and descriptive keywords.
- **REQ-SCR-019**: **Event-Driven**: When companion Adobe or Darktable XMP sidecar files (`<filename>.xmp` or `<filename>.<ext>.xmp`) exist alongside an image, the metadata extractor shall parse RDF/XMP schema fields (`exif:GPSLatitude`, `exif:GPSLongitude`, `photoshop:DateCreated`, `dc:subject`).
- **REQ-SCR-020**: **Event-Driven**: When companion Google Photos or archive JSON sidecar files (`<filename>.json` or `<filename>.<ext>.json`) exist alongside an image, the metadata extractor shall parse structured geographic objects (`geoData.latitude`, `geoData.longitude`) and timestamp objects (`photoTakenTime.timestamp`, `photoTakenTime.formatted`).
- **REQ-SCR-021**: **Complex**: While evaluating coordinates for an image, when embedded EXIF GPS tags are absent but companion sidecar files provide valid coordinates, the metadata extractor shall extract the coordinates from the companion sidecar file.
- **REQ-SCR-022**: **Event-Driven**: When GPS coordinates are extracted from either embedded metadata or companion sidecar files, the metadata extractor shall normalize the values to decimal WGS-84 format (`latitude`, `longitude`).
- **REQ-SCR-023**: **Unwanted Behaviour**: If neither embedded metadata standards (EXIF/IPTC/XMP) nor companion sidecar files contain valid GPS coordinates, then the metadata extractor shall leave the `latitude` and `longitude` fields empty.
- **REQ-SCR-024**: **Event-Driven**: When capture dates are discovered across embedded EXIF (`DateTimeOriginal`, `CreateDate`), IPTC (`DateCreated`), XMP, or companion sidecar files across images in a candidate folder, the metadata extractor shall collect all valid timestamps.
- **REQ-SCR-025**: **Event-Driven**: When multiple differing dates are extracted from images or sidecar files within a single folder, the metadata extractor shall assign the earliest (lowest) chronological date to `dates visited`.
- **REQ-SCR-026**: **Event-Driven**: When image files or companion sidecars contain descriptive keywords or category tags (EXIF `XPKeywords`, IPTC `Keywords`, XMP `dc:subject`, JSON `tags` or `description`), the metadata extractor shall collect and aggregate the tags for location inference.
- **REQ-SCR-027**: **Ubiquitous**: The metadata extractor shall enforce strict read-only access on companion sidecar files, prohibiting any file creation, alteration, rename, or deletion.

#### LLM Location Inference & Confidence Scoring

- **REQ-SCR-028**: **Unwanted Behaviour**: If the photo scraper CLI is executed without a valid `GOOGLE_API_KEY` or without active network connectivity to the AI API, then the CLI shall immediately terminate execution with a non-zero exit code and an actionable error message.
- **REQ-SCR-029**: **Event-Driven**: When candidate directory tokens, GPS coordinates, and abstracted tags are assembled, the location resolver shall invoke the LLM to predict the standardized POI name, street address, and confidence score.
- **REQ-SCR-030**: **Ubiquitous**: The location resolver shall configure LLM calls with `thinking_budget = 0` and structured JSON schema output enforcing deterministic response models.
- **REQ-SCR-031**: **Event-Driven**: When the LLM resolves a location, it shall output `location_confidence_percent` as an integer between 0 and 100, where 0 represents no confidence and 100 represents definitive certainty.
- **REQ-SCR-032**: **Unwanted Behaviour**: If a directory contains generic or unmappable labels (e.g. `Sledding`, `Picnic`) without GPS coordinates, then the location resolver shall assign a low confidence score ($\le 15$) and leave address fields empty.
- **REQ-SCR-033**: **Event-Driven**: When the detected POI represents a multi-location commercial brand (e.g. `McDonalds`, `Starbucks`) without exact GPS coordinates, the location resolver shall penalize the confidence score ($\le 30$) to reflect location ambiguity.
- **REQ-SCR-034**: **State-Driven**: While performing location resolution, the CLI shall query a persistent local cache (`.scraper_cache.db`) before dispatching external LLM or geocoding API requests.

#### Standardized CSV Output Generation

- **REQ-SCR-035**: **Ubiquitous**: The photo scraper CLI shall output results to an RFC 4180 compliant CSV file formatted with standardized column headers:
  1. `POI Name`
  2. `Street Address`
  3. `Town/City`
  4. `State/Province`
  5. `Zip Code`
  6. `Country`
  7. `Tags`
  8. `latitude`
  9. `longitude`
  10. `dates visited`
  11. `Photo directory`
  12. `location_confidence_percent`
- **REQ-SCR-036**: **State-Driven**: While generating CSV output, the photo scraper CLI shall leave `Tags` empty, reserving the column for downstream extractor modules.
- **REQ-SCR-037**: **Complex**: While formatting multi-element address fields, when multiple addresses exist for a single POI, the CSV formatter shall align semicolon-delimited lists across `Street Address`, `Town/City`, `State/Province`, `Zip Code`, and `Country` by index.
- **REQ-SCR-038**: **Unwanted Behaviour**: If specific data for an optional column is not discovered and no explicit default rule exists, then the CSV formatter shall leave that column value empty for the given POI.
- **REQ-SCR-039**: **Event-Driven**: When writing cell values to CSV, the formatter shall neutralize formula injection characters (`=`, `+`, `-`, `@`, `\t`, `\r`) by prepending a single quote (`'`).

#### Web Application CSV Ingestion & Pre-Validation

- **REQ-ING-001**: **Event-Driven**: When a user uploads a CSV file via the Vistarae web application, the ingestion service shall stream and validate the file against constitutional size ($\le 2\text{MB}$) and row ($\le 2,000$) guardrails, binding tenant ownership exclusively to the authenticated user identity (`current_user.id`) from the request JWT context.
- **REQ-ING-002**: **State-Driven**: While the backend processes an ingestion job, the web application shall render a dynamic progress bar displaying current percentage completion and stage description.
- **REQ-ING-003**: **Complex**: While processing imported CSV records, when a row contains `latitude` and `longitude` but lacks address fields, the backend geocoding service shall execute reverse geocoding to determine address hierarchically:
  1. Full street address (`Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`)
  2. Locality level (`Town/City`, `State/Province`, `Country`) if street address unavailable
  3. Region level (`State/Province`, `Country`) if locality unavailable
  4. Country level (`Country`) if regional details unavailable
- **REQ-ING-004**: **Complex**: While processing imported CSV records, when a row lacks coordinates but provides address tokens, the backend geocoding service shall query forward geocoding hierarchically:
  1. Match `POI Name` within `Town/City` + `State/Province` + `Country`
  2. Match `POI Name` within `State/Province` + `Country` if locality yields no hit
  3. Match `POI Name` within `Country` if state/province yields no hit
  4. Match `POI Name` globally if no address context exists
- **REQ-ING-005**: **Unwanted Behaviour**: If forward geocoding yields no reliable geographic match for a record lacking coordinates, then the system shall set the entry's recommended disposition to `ignore`.
- **REQ-ING-006**: **Event-Driven**: When evaluating each imported candidate, the deduplication engine shall check for existing POIs in the user's database using spatial radius ($\le 50\text{m}$) and trigram name similarity ($\ge 0.60$).
- **REQ-ING-007**: **State-Driven**: While evaluating duplicate candidates, if an existing POI matches spatial and name criteria, the deduplication engine shall classify the disposition as `update existing POI` and record the existing POI identifier.
- **REQ-ING-008**: **State-Driven**: While evaluating candidate locations, if a candidate is located within the spatial boundary of an existing macro-site with low name similarity ($< 0.60$), the deduplication engine shall classify the disposition as `sublocation` and link the parent POI identifier.
- **REQ-ING-009**: **State-Driven**: While evaluating candidate locations, if no existing records are detected within the spatial radius and `location_confidence_percent` $\ge 40$, the engine shall classify the disposition as `accept`.
- **REQ-ING-010**: **State-Driven**: While evaluating candidate locations, if `location_confidence_percent` $< 40$, the engine shall classify the disposition as `ignore`.

#### Phase 1 Interactive Validation & Triage Review Window

- **REQ-ING-011**: **Event-Driven**: When pre-validation and deduplication complete, the web application shall open the **Phase 1 Validation Window** displaying all candidate rows with their recommended dispositions (`accept`, `ignore`, `update existing POI`, `sublocation`).
- **REQ-ING-012**: **State-Driven**: While in the Phase 1 Validation Window, the table shall display editable fields: `POI Name`, `Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `Tags`, `Photo directory`, `parent POI`, and `dates visited`.
- **REQ-ING-013**: **Event-Driven**: When the user interacts with the disposition selector for any row in the Phase 1 table, the UI shall update the row's assigned disposition.
- **REQ-ING-014**: **State-Driven**: While reviewing a POI in the Phase 1 window, the UI shall render an interactive map displaying candidate and existing POI markers, allowing the user to reposition the candidate pin, or click an existing POI marker to designate it as the `parent_poi_id` when the disposition is set to `sublocation`.
- **REQ-ING-015**: **Event-Driven**: When the user clicks the **Cancel** button in the Phase 1 window, the web application shall abort the import operation and purge all staged records from `ingest_candidates` for that `job_id` and `user_id` without modifying the database `pois` table.
- **REQ-ING-016**: **Event-Driven**: When the user clicks the **Proceed** button in the Phase 1 window, the web application shall commit triage decisions to `ingest_candidates` and advance only non-ignored records (`accept`, `sublocation`, `update existing POI`) to Phase 2.

#### Phase 2 AI Enrichment & Final Confirmation Window

- **REQ-ING-017**: **Event-Driven**: When non-ignored POIs advance to Phase 2, the backend enrichment orchestrator shall scrape external web context for each candidate based on its confirmed name and coordinates.
- **REQ-ING-018**: **Event-Driven**: When synthesizing POI content for `accept` and `sublocation` entries, the enrichment service shall invoke the LLM using base prompts extended with the traveler's personalized travel style prompt directives (from Phase 11) to generate `description`, `reason_to_visit`, and thematic tags, updating the corresponding `ingest_candidates` row.
- **REQ-ING-019**: **Event-Driven**: When Phase 2 enrichment completes, the web application shall open the **Phase 2 Review Window** displaying all enriched POIs from `ingest_candidates`, their dispositions, and synthesized attributes.
- **REQ-ING-020**: **State-Driven**: While reviewing the Phase 2 table, the UI shall provide a toggle button for each POI allowing the user to skip the entry.
- **REQ-ING-021**: **Event-Driven**: When the user clicks the **Edit POI** button in the Phase 2 window, the UI shall open an edit modal allowing full modification of all POI fields and profile-customized text in `ingest_candidates`.
- **REQ-ING-022**: **State-Driven**: While in the Phase 2 window, the UI shall render an interactive map displaying all candidate markers with active selection synchronization.
- **REQ-ING-023**: **Event-Driven**: When the user clicks the **Save to DB** button in the Phase 2 window, the backend service shall execute the final database transaction:
  1. For `accept` entries: insert a new POI record in the `pois` table.
  2. For `sublocation` entries: insert a new POI record with `parent_poi_id` set to the identified parent POI.
  3. For `update existing POI` entries: retain existing primary coordinates and address by default (unless user explicitly selected 'Update Coordinates' in the edit drawer), and append new `visited_dates`, `directory_paths`, and tags to the existing POI record without overwriting existing user-curated descriptions.
  4. Automatically purge all processed records from `ingest_candidates` for that `job_id`.
- **REQ-ING-024**: **Event-Driven**: When the user clicks the **Cancel** button in the Phase 2 window, the web application shall abort the operation, purge the staged records from `ingest_candidates` for that `job_id`, and make no alterations to `pois`.

---

### Key Entities

- **ScraperJobConfig**: CLI execution parameters, including `--input-dir`, `--output-csv`, `--previous-csv`, `--cache-dir`, and threshold configurations.
- **ScrapedFolderCandidate**: Represents a discovered candidate folder with raw path segments, cleaned geographic tokens (`country`, `city`, `poi_name`, `alt_name`), extracted coordinates (from EXIF, IPTC, XMP, or sidecars), earliest visit date, and raw image tags.
- **POIExportRecord**: Standardized data structure representing an extracted POI row for RFC 4180 CSV export and web app consumption.
- **IngestTriageCandidate**: Staged POI entity within an ingestion job storing initial coordinates, reverse geocoded address, recommended disposition (`accept`, `ignore`, `update existing POI`, `sublocation`), confidence score, and parent POI linkage.
- **EnrichedPOICandidate**: Phase 2 entity containing web-scraped context, AI-generated `description`, personalized `reason_to_visit`, visit tags, and user override modifications ready for database persistence.

---

## 4. Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: The photo scraper CLI scans a directory containing 1,000 subfolders and 10,000 images in under 5 minutes when running with warm cache.
- **SC-002**: 100% of scanned photo directories, image files, and sidecar files remain unaltered with zero filesystem mutations (verified via cryptographic hash comparison before and after scanning).
- **SC-003**: Path cleaning heuristics successfully extract valid city and country tokens from $\ge 95\%$ of standard non-standard test path patterns (`1-Tokyo`, `Trip To India`, `Japan 4-03`, `03 Oaxaca`).
- **SC-004**: The CLI achieves $\ge 90\%$ accuracy in resolving capture dates and coordinates across embedded EXIF, IPTC, XMP, and companion sidecars (`.xmp`, `.json`), correctly assigning the earliest chronological photo timestamp to `dates visited`.
- **SC-005**: 100% of generic folders without coordinates (e.g. `Sledding`) receive confidence scores $\le 15$ and automatically default to the `ignore` disposition in Phase 1 triage.
- **SC-006**: Web application CSV ingestion displays real-time progress updates with $\le 500\text{ms}$ UI latency between processing state changes.
- **SC-007**: Phase 1 triage successfully isolates unmappable or low-confidence records, reducing unwanted POI creation on user maps to 0% when default dispositions are accepted.
- **SC-008**: Phase 2 AI enrichment generates personalized `description` and `reason_to_visit` adhering to user travel style prompts for 100% of accepted POIs.
- **SC-009**: Multi-visit merging combines 100% of distinct visit dates and directory paths into existing POIs without data loss or duplicate POI proliferation.
- **SC-010**: All outbound geocoding queries adhere strictly to the 1 request per second rate limit, with $\ge 80\%$ cache hit rates across recurring locality lookups.

---

## 5. Assumptions

- **Target Image Formats & Embedded Standards**: Photo archives contain standard image formats (`.jpg`, `.jpeg`, `.tiff`, `.heic`, `.png`, `.webp`, `.dng`) embedding EXIF 2.3+, IPTC-IIM, and XMP (RDF/XML) metadata schemas. Non-image media files (e.g. `.mp4`, `.mov`) are scanned for standard creation/location metadata when present or ignored.
- **Companion Sidecar File Standards**: The CLI recognizes companion Adobe/Darktable XMP sidecars (`<file>.xmp`, `<file>.<ext>.xmp`), Google Photos Takeout JSON sidecars (`<file>.json`, `<file>.<ext>.json`), and XML sidecars. Coordinates and dates found in sidecars are ingested when embedded tags are missing or incomplete.
- **Single POI Per Directory**: Consistent with user instructions, each valid leaf directory is assumed to represent one POI from a single visit. Where subfolders represent sublocations (e.g. `Elangovan` inside `Garfield Park Conservatory`), they associate with the primary landmark.
- **Read-Only Verification**: The CLI opens all files (images and sidecars) in binary read mode (`rb`) and will refuse execution if run in an environment attempting to write index files or modify files in the scanned tree.
- **Geocoding Rate Limiting & User-Agent**: Outbound Nominatim requests utilize the custom User-Agent `VistaraeTravelEngine/1.0` and adhere to the 1-second delay requirement, using persistent SQLite caching locally and PostGIS `geocache` in the cloud.
- **Address Delimiter Alignment**: Multi-address lists within CSV export cells are delimited by semicolons (`; `), maintaining 1:1 positional index alignment across `Street Address`, `Town/City`, `State/Province`, `Zip Code`, and `Country`.
- **Default Confidence Thresholds**: Confidence $< 40\%$ defaults to `ignore`, $40\% - 69\%$ prompts review as candidate `accept`, and $\ge 70\%$ with coordinates defaults to `accept` or `update existing POI`.
- **Zero-Cost Free-Tier Operation**: Asynchronous ingestion batches remain bounded to 10 rows per SQS payload, fitting comfortably within the monthly AWS Lambda 1,000,000 free request tier and Neon compute zero-scaling constraints.

