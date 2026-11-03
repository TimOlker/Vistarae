# Feature Specification: Unified CLI Extractors & Scraper Toolkit (016-cli-extractors)

**Feature Branch**: `016-cli-extractors`  
**Created**: 2026-11-03  
**Status**: Clarified  
**Input**: User description: "CLI extractor (016-cli-extractors) unified Import Staging Workbench using strict EARS syntax. All extractor scripts should be placed into a common directory /extractor_scripts. 1. Common Logic: specialized click CLI scripts scraping data from different sources with a re-usable package standardizing logic, aligning output columns with CSV import logic (POI Name, lat/long, ISO address, tags, dates visited, photo directory, web pages with Name & URL, estimated hours/days, hero image URL, notes). 2. Hillman Wonder Extractor script. 3. National Park System Sites. 4. Museum Ships. 5. Castles. 6. Air Craft Museums. Flag contradictions with previous logic or missing logic or features to include."

---

## Clarifications

### Session 2026-11-03

- Q: Where should the reusable extractor framework and data structures reside within the Vistarae monorepo? → A: Option A (Hybrid: Place core export schemas, DTOs, and CSV formula sanitization utilities in `packages/core/vistarae_core/schemas/extractor.py`, and place scraper base classes, HTTP politeness clients, and Click CLI entrypoints in `extractor_scripts/common/` and `extractor_scripts/`).
- Q: How should the extractor framework handle datasets that exceed Vistarae's 2,000-row CSV upload limit? → A: Option A (Automatic Partitioning: Automatically split output into sequentially numbered CSV files of $\le 2,000$ rows, e.g. `filename_part1.csv`, whenever records exceed 2,000 rows or when configured via `--split-size`, ensuring direct compatibility with Vistarae ingestion).
- Q: How should the CLI extractors handle missing geographic coordinates when source websites only provide place names and addresses? → A: Option A (Offline-First with Optional Flag: Default to leaving coordinates empty when missing in source data, allowing Vistarae's import staging engine to geocode them; provide an opt-in `--geocode` flag with 1 req/sec throttling for small runs).
- Q: How should multiple website name and URL pairs be serialized within the CSV export for ingestion by Vistarae? → A: Single JSON-Encoded Websites Column (No Dedicated Columns): Do not output dedicated columns for Wikipedia URL or Official Website URL; instead, all web links (including official sites, Wikipedia, and external references) shall be serialized together in a JSON-encoded `Websites` column formatted as `[{"name": "<Website Name>", "url": "<URL>"}]`.
- Q: How should multi-location POIs (such as national parks with multiple satellite locations or visitor centers) serialize address data? → A: Primary Location + JSON-Encoded Additional Address: The primary/first location populates the standard address columns (`Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `latitude`, `longitude`), and any secondary or satellite locations are JSON-encoded as an array of address dictionaries into an `Additional Address` column.
- Q: How should unit and integration tests for the extractor scripts handle external HTTP dependencies within CI/CD pipelines? → A: Option A (Canned HTML Fixtures: Unit tests execute against local static HTML snapshots using mocked HTTP transports in `tests/unit/extractor_scripts/fixtures/` for fast, deterministic CI; live network tests are gated behind `@pytest.mark.live_scrape`).
- Q: How should extractor scripts assign and configure tags for extracted POIs? → A: Precise Extractor Tagging Rules:
  - **Hillman Wonders**: Assign `HillmanWonder:Gold`, `HillmanWonder:Silver`, or `HillmanWonder:Bronze` based on wonder tier. Do NOT assign the base `Wonder` tag.
  - **NPS Sites**: Assign baseline `NPS` tag to all records, plus a conditional tag based on the official designation (e.g. `National Park`, `National Historic Site`, `National Battlefield`, `National Monument`).
  - **Aircraft Museums**: Assign baseline `Aircraft` tag only. Do NOT assign collection focus tags (e.g. no "Aviation Museum", "Aerospace").
  - **Castles**: Assign baseline `Fortification` tag only. Do NOT assign architectural classification tags (e.g. no "Medieval", "Château", "Ruin").
  - **Museum Ships**: Assign baseline `Ship` tag to all records, and conditionally assign `Military` if the POI is a warship. Do NOT assign naval vessel classification tags (e.g. no "Battleship", "Submarine").
  - **Framework Extensibility**: Future CLI scripts can configure zero to many default tags applied to all POIs or conditional tags applied to specific POIs, and CLI users can append run-time tags via `--tag`.

---

## Architectural Alignment & Flagged Items

### 1. Flagged Contradictions in Input Prompts

- **Museum Ships Specification Copy-Paste Contradiction**:
  - *Observed in Prompt*: Item 4 states "The Park name the POI name column, country is a column (should be USA)... Park Type (National Battlefield, National Park, etc)... NPS website" for Museum Ships.
  - *Resolution*: This was recognized as an accidental copy-paste from Item 3 (National Parks). Museum ships are global (not restricted to the USA), classified by vessel type / warship class (e.g., Battleship, Aircraft Carrier, Submarine, Cruiser, Destroyer), and reference museum or naval heritage websites rather than the US National Park Service.
- **Aircraft Museums Castle Copy-Paste Contradiction**:
  - *Observed in Prompt*: Item 6 states "list the POI name and as much data as possible about the castle".
  - *Resolution*: Corrected to "about the aircraft / aviation museum".
- **CSV Column Schema Alignment (12-Column Legacy vs. Staging Workbench)**:
  - *Observed Difference*: Vistarae core export (`POIExportRecord`) uses 12 legacy columns (`POI Name`, `Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `Tags`, `latitude`, `longitude`, `dates visited`, `Photo directory`, `location_confidence_percent`, `confidence_source`), whereas Feature 014/015 Unified Import Staging Workbench introduced extended fields (`hero_image_url`, `official_url`, `wiki_url`, `related_websites`, `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `description`, `reason_to_visit`, `country_code`, `admin_level_1`, `admin_level_2`, `locality`).
  - *Resolution*: The common extractor framework shall format CSV columns to align directly with Vistarae's import ingestion: no dedicated Wikipedia or Official Website columns are exported; all web pages are consolidated into a single JSON-encoded `Websites` column (`[{"name": "...", "url": "..."}]`). For multi-location POIs, the primary address populates standard address columns, while all secondary locations are JSON-encoded into an `Additional Address` column.

### 2. Missing Logic & Recommended Features

- **Rate-Limiting & Politeness**: Scraping public web pages (especially Wikipedia, CastlesWorld, and Hillman Wonders) requires disciplined rate-limiting (default $\ge 1.0$s delay between outbound HTTP requests), exponential backoff, and identifiable `User-Agent` headers (`VistaraeDataExtractor/1.0`) to avoid IP blocking and comply with web etiquette.
- **Local HTTP Response Caching**: To prevent redundant network requests and enable reproducible, idempotent CLI runs during offline development or testing, the common framework shall support local caching of raw HTTP responses.
- **Two-Pass Scraping (Index vs. Detail Subpages)**: Most source catalogs (e.g. Hillman Wonders, CastlesWorld, Aviation Museums) provide high-level lists on index pages while embedding precise coordinates, hero images, and detailed histories on individual subpages. The CLI framework shall provide a configurable flag (`--deep` / `--shallow`) allowing users to scrape shallow index summaries rapidly or deep-scrape individual subpages for maximum metadata completeness.
- **Formula Injection Defense at Extraction Time**: To maintain system security before files ever touch Vistarae's import ingestion, the common extractor exporter shall sanitize cell values by neutralizing formula injection prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Standardized Common Extractor Framework Execution (Priority: P1)

As a data curator or travel researcher, I want a standardized CLI toolchain located in `/extractor_scripts` built upon a reusable extractor framework, so that every scraping script presents a consistent command-line interface, shared output formatting, robust error handling, and direct compatibility with Vistarae CSV import.

**Why this priority**: Forms the foundational architecture for all current and future extractors, preventing duplicate networking, parsing, and serialization logic across scraping tools.

**Independent Test**: Run any extractor CLI using standard flags (e.g. `--help`, `--output <path>`, `--limit 5`, `--format csv`). Verify the CLI produces a valid RFC 4180 CSV with Vistarae-compliant headers and formula-neutralized values.

**Acceptance Scenarios**:

1. **Given** a user invokes any extractor CLI script with the `--help` flag,  
   **When** the command executes,  
   **Then** the system shall display a standardized Click CLI help interface detailing common flags (`--output`, `--limit`, `--delay`, `--deep/--shallow`, `--format`, `--dry-run`).
2. **Given** an extractor script extracts raw records,  
   **When** writing to the specified output file,  
   **Then** the system shall format output using Vistarae-aligned column headers (`POI Name`, `Country`, `Country Code`, `State/Province`, `Town/City`, `Street Address`, `Zip Code`, `latitude`, `longitude`, `Tags`, `Hero Image URL`, `Websites`, `Additional Address`, `Estimated Visit Hours`, `Itinerary Days`, `Description`, `Reason to Visit`, `Photo Directory`, `Dates Visited`).
3. **Given** any extracted cell value starts with a spreadsheet formula prefix (`=`, `+`, `-`, `@`, `\t`, `\r`),  
   **When** formatting CSV rows,  
   **Then** the system shall neutralize formula injection by prepending a single quote (`'`).

---

### User Story 2 - Hillman 1,000 Wonders Extraction (Priority: P1)

As a traveler compiling global bucket-list destinations, I want to execute a CLI extractor against Hillman Wonders (`https://www.hillmanwonders.com/top_1000/index.htm`), so that I generate an importable CSV containing all ranked wonders with standardized country names, wonder tiers (Gold, Silver, Bronze), rank numbers, and descriptive overviews.

**Why this priority**: Hillman Wonders represents one of the premier curated global travel inventories, serving as an ideal benchmark for international landmark capture.

**Independent Test**: Execute `python extractor_scripts/hillman_wonders.py --limit 20 --output hillman_test.csv`. Verify the generated CSV contains 20 rows, accurately parses wonder tiers into tags, maps country names to recognized formats, and populates POI names correctly.

**Acceptance Scenarios**:

1. **Given** the Hillman Wonders extractor is executed,  
   **When** parsing the Top 1,000 index pages,  
   **Then** the system shall extract the wonder title as `POI Name`, wonder rank (1-1000), award tier (Gold, Silver, Bronze), country/region, and Hillman URL.
2. **Given** an extracted wonder record,  
   **When** standardizing metadata,  
   **Then** the system shall format the award tier as a tag (`HillmanWonder:Gold`, `HillmanWonder:Silver`, `HillmanWonder:Bronze`) based on the type of wonder without assigning a base `Wonder` tag, standardize the country to recognized ISO English names, and assign `Reason to Visit` from the wonder summary.
3. **Given** the deep-scrape flag (`--deep`) is supplied,  
   **When** processing each wonder,  
   **Then** the system shall fetch the individual wonder detail page to extract hero photos, estimated visit durations, and geographic coordinates if present.

---

### User Story 3 - US National Park System Sites Extraction (Priority: P2)

As a domestic traveler exploring public lands, I want to execute a CLI extractor that harvests all US National Park System units, so that I can generate a clean CSV including park names, park designations (National Park, National Monument, National Historic Site), state, town, coordinates, and official NPS websites.

**Why this priority**: National Park System sites have well-defined coordinates, administrative hierarchies, and standardized designations, providing rich geospatial data for US travel planning.

**Independent Test**: Execute `python extractor_scripts/nps_sites.py --limit 15 --output nps_test.csv`. Verify that entries contain accurate WGS-84 coordinates, country set to "United States" (`US`), state administrative codes, designation tags, and official NPS URLs.

**Acceptance Scenarios**:

1. **Given** the National Park System extractor runs,  
   **When** harvesting park data,  
   **Then** the system shall extract Park Name as `POI Name`, set Country to "United States" (`country_code: US`), capture state/territory as `admin_level_1`, and extract locality/town where available.
2. **Given** an extracted park site,  
   **When** processing the site designation,  
   **Then** the system shall assign the baseline "NPS" tag alongside the specific official park type (e.g., "National Park", "National Monument", "National Historic Site", "National Battlefield") to the `Tags` column and classify estimated visit hours based on park type.
3. **Given** an extracted park site,  
   **When** coordinates are available,  
   **Then** the system shall record decimal latitude and longitude within valid ranges ($-90 \le \text{lat} \le 90$, $-180 \le \text{lon} \le 180$) and attach the official `.nps.gov` portal URL inside the JSON-encoded `Websites` column.
4. **Given** a national park system site with multiple locations or visitor centers,  
   **When** serializing the record,  
   **Then** the system shall record the primary location in standard address columns and serialize any additional locations as a JSON-encoded array into the `Additional Address` column.

---

### User Story 4 - Global Museum Ships & Historic Warships Extraction (Priority: P2)

As a naval history enthusiast, I want to extract global museum ships and preserved warships into a standardized CSV, so that I can import vessel locations, ship classes, commissioning nations, home ports, and museum website links into Vistarae.

**Why this priority**: Preserved warships represent specialized historical maritime POIs worldwide with unique categorization needs (ship type, hull number, era).

**Independent Test**: Execute `python extractor_scripts/museum_ships.py --limit 20 --output ships_test.csv`. Verify extracted ships feature vessel names, host countries, port cities, vessel classifications as tags (e.g., "Aircraft Carrier", "Battleship", "Submarine"), and Wikipedia/museum reference URLs.

**Acceptance Scenarios**:

1. **Given** the Museum Ships extractor runs,  
   **When** harvesting data from global ship registries or Wikipedia lists,  
   **Then** the system shall extract the ship name (and hull classification where present) as `POI Name`, its berthing port as `Town/City`, its host nation as `Country`, assign the baseline "Ship" tag to all records, conditionally append the "Military" tag if the vessel is a warship, and omit naval vessel classification tags.
2. **Given** a museum ship with known geographic coordinates,  
   **When** serializing the record,  
   **Then** the system shall populate `latitude` and `longitude` corresponding to the vessel's permanent museum berth or drydock.
3. **Given** an extracted ship entry,  
   **When** formatting related websites,  
   **Then** the system shall record the official museum page and reference encyclopedia URLs inside the JSON-encoded `Websites` column.

---

### User Story 5 - Castles of the World Extraction (Priority: P3)

As a traveler exploring historic architecture, I want to extract castles, fortresses, and châteaux across the globe from CastlesWorld and architectural registries, so that I can import castle names, architectural eras, regional locations, coordinates, and photo links into Vistarae.

**Why this priority**: Castles represent high-density scenic and cultural POIs with rich international administrative distributions across Europe, Asia, and the Middle East.

**Independent Test**: Execute `python extractor_scripts/castles.py --limit 20 --output castles_test.csv`. Verify records contain castle names, sovereign countries, administrative regions, castle types/eras as tags, and hero image URLs where available.

**Acceptance Scenarios**:

1. **Given** the Castles extractor runs,  
   **When** querying castle directory listings,  
   **Then** the system shall record Castle Name as `POI Name`, Country, Administrative Region/Province as `admin_level_1`, and nearest town as `locality`.
2. **Given** a castle entry includes imagery,  
   **When** serializing the record,  
   **Then** the system shall populate `Hero Image URL` with the primary exterior photo link.
3. **Given** a castle listing is processed,  
   **When** building metadata,  
   **Then** the system shall assign the baseline "Fortification" tag to all castle records, omit architectural classification tags (e.g. no "Castle", "Ruin", "Château" in tags), and compile historical highlights into `Description`.

---

### User Story 6 - Aircraft & Aviation Museums Extraction (Priority: P3)

As an aviation enthusiast, I want to extract aviation and aerospace museums worldwide from comprehensive encyclopedic directories, so that I can import flight museums, air bases with public collections, and aerospace centers with verified coordinates and links into Vistarae.

**Why this priority**: Aviation museums are popular regional travel destinations spanning national air force collections, space centers, and private vintage aircraft hangars worldwide.

**Independent Test**: Execute `python extractor_scripts/aircraft_museums.py --limit 25 --output aviation_test.csv`. Verify output includes museum names, sovereign countries, airport/base locations, tags indicating aviation focus, and official links.

**Acceptance Scenarios**:

1. **Given** the Aircraft Museums extractor runs,  
   **When** processing aviation museum indexes,  
   **Then** the system shall extract Museum Name as `POI Name`, Country, State/Province, City/Town/Airfield, assign the baseline "Aircraft" tag to all records, and omit collection focus tags.
2. **Given** an aviation museum entry has geographic coordinates,  
   **When** formatting coordinates,  
   **Then** the system shall capture `latitude` and `longitude` in standard decimal format.
3. **Given** an aviation museum record,  
   **When** formatting notes and websites,  
   **Then** the system shall capture notable exhibits or collection highlights into `Reason to Visit` and link official museum and reference websites inside the JSON-encoded `Websites` column.

---

### Edge Cases

- **Rate-Limiting & HTTP 429 / 403 Response**: When an external source website blocks or rate-limits requests, the framework shall retry with exponential backoff up to 3 times before gracefully skipping or logging a warning without crashing the entire batch.
- **Missing Geographic Coordinates**: When a source listing lacks latitude and longitude, the extractor shall output empty strings for `latitude` and `longitude` without validation errors, leaving coordinate enrichment to Vistarae's geocoding engine.
- **Non-Latin Characters in Place Names**: When a castle or museum name is written in non-Latin scripts (e.g., Cyrillic, Kanji, Arabic), the extractor shall preserve the native name and include the romanized transliteration where available in `Description` or aliases.
- **International Country Name Discrepancies**: When sources use colloquial or archaic country names (e.g., "Burma", "Holland", "Great Britain"), the framework shall normalize country names to standard ISO 3166-1 English names and two-letter country codes.
- **Multiple Addresses or Satellite Facilities**: When a national park, landmark, or museum has multiple visitor centers, entrances, or physical facilities, the extractor shall record the primary/first address in the standard address columns (`Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `latitude`, `longitude`) and serialize all additional locations as a JSON-encoded array of address objects into the `Additional Address` column.

---

## Requirements *(mandatory)*

### Functional Requirements (Strict EARS Syntax)

#### Common Extractor Framework Requirements

- **FR-001 (Ubiquitous)**: The extractor toolkit shall place shared domain models (`ExtractorRecord`) and CSV sanitization utilities in `packages/core/vistarae_core/schemas/extractor.py`, scraper base classes and HTTP politeness utilities in `extractor_scripts/common/`, and specialized Click CLI execution scripts in `/extractor_scripts`.
- **FR-002 (Ubiquitous)**: The extractor toolkit shall implement all CLI interfaces using the `click` library with standard options for `--output`, `--limit`, `--delay`, `--deep/--shallow`, `--format`, and `--dry-run`.
- **FR-003 (Ubiquitous)**: The extractor framework shall export data in RFC 4180 compliant CSV format with headers aligned directly with Vistarae's CSV import parser (`POI Name`, `Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `Tags`, `latitude`, `longitude`, `dates visited`, `Photo directory`, `Hero Image URL`, `Websites`, `Additional Address`, `Estimated Visit Hours`, `Itinerary Days`, `Description`, `Reason to Visit`).
- **FR-004 (Ubiquitous)**: The extractor framework shall mandate `POI Name` as a non-empty string for every exported record.
- **FR-005 (Event-Driven)**: When geographic coordinates are available in the source data, the extractor framework shall serialize `latitude` and `longitude` as WGS-84 decimal numbers rounded to 6 decimal places.
- **FR-006 (State-Driven)**: While coordinate or address components are absent from source data, the extractor framework shall represent missing fields as empty strings without raising validation exceptions.
- **FR-007 (Event-Driven)**: When extracting address components, the extractor framework shall extract and map country, administrative level 1 (state/province), administrative level 2 (county/district), locality (town/city), street address, and postal code wherever available. When a POI possesses multiple physical locations or visitor facilities, the extractor framework shall record the primary location in standard address columns and serialize secondary locations as a JSON-encoded array into the `Additional Address` column.
- **FR-008 (Event-Driven)**: When exporting tags, the extractor framework shall serialize tags as a semicolon-separated string (e.g. `Tag1; Tag2; Tag3`), combining script-level baseline default tags, record-specific conditional tags, and any user-supplied tags provided via CLI flag (`--tag`). Future and custom extractor scripts shall be able to configure zero to many baseline default tags applied to all POIs or conditional tags applied to specific POIs.
- **FR-009 (Event-Driven)**: When extracting web links, the extractor framework shall not export dedicated `Official URL` or `Wiki URL` columns; all web links (including official portals, Wikipedia pages, and secondary references) shall be serialized as a JSON-encoded array of `{"name": "...", "url": "..."}` objects in the `Websites` column.
- **FR-010 (Event-Driven)**: When visit duration estimates can be inferred from the POI category or source content, the extractor framework shall populate `Estimated Visit Hours` and `Itinerary Days`.
- **FR-011 (Event-Driven)**: When writing any cell value to CSV, the extractor framework shall neutralize formula injection by prepending a single quote (`'`) to any string that begins with `=`, `+`, `-`, `@`, `\t`, or `\r`.
- **FR-012 (State-Driven)**: While executing network HTTP requests against remote servers, the extractor framework shall enforce a minimum politeness delay (default 1.0 second per domain) and transmit an identifiable `User-Agent` header (`VistaraeDataExtractor/1.0`).
- **FR-013 (Unwanted Behaviour)**: If an external HTTP request returns a 429, 500, 502, 503, or 504 status code, then the extractor framework shall execute up to 3 retry attempts with exponential backoff before logging an error and continuing extraction.
- **FR-014 (Optional Feature)**: Where local caching is enabled via CLI flag (`--cache`), the extractor framework shall store downloaded raw HTML responses on the local filesystem to avoid duplicate network roundtrips.
- **FR-015 (Event-Driven)**: When total extracted records exceed 2,000 rows or when configured via `--split-size`, the extractor framework shall partition output into sequentially numbered CSV files (`{basename}_part{n}.csv`) with each partition containing at most 2,000 rows (or the specified `--split-size`), ensuring compliance with Vistarae's ingestion upload limits.

#### Hillman Wonders Extractor Requirements

- **FR-016 (Event-Driven)**: When the Hillman Wonders extractor executes, the script shall parse the Hillman 1,000 index pages (`https://www.hillmanwonders.com/top_1000/index.htm`) to extract each wonder's title, rank number, award tier, country/region, and overview text.
- **FR-017 (Ubiquitous)**: The Hillman Wonders extractor shall map the wonder title to `POI Name`, normalize country names to ISO English standards, and assign the wonder level tag (`HillmanWonder:Gold`, `HillmanWonder:Silver`, or `HillmanWonder:Bronze`) based on the type of wonder, without assigning a base "Wonder" tag.
- **FR-018 (Optional Feature)**: Where the `--deep` flag is active, the Hillman Wonders extractor shall navigate to individual wonder detail pages to extract extended commentary into `Reason to Visit`, hero photo URLs, and estimated visit durations.

#### US National Park System Sites Extractor Requirements

- **FR-019 (Event-Driven)**: When the National Park System extractor executes, the script shall harvest all recognized US National Park Service units into POI records.
- **FR-020 (Ubiquitous)**: The National Park System extractor shall set `Country` to "United States", `country_code` to "US", extract state abbreviations into `State/Province`, and assign the baseline tag "NPS" to all records along with a conditional tag based on the official designation (e.g. "National Park", "National Historic Site", "National Battlefield", "National Monument") in `Tags`.
- **FR-021 (Ubiquitous)**: The National Park System extractor shall populate `latitude`, `longitude`, record the official `.nps.gov` site inside the `Websites` JSON array, and serialize any secondary park units or visitor centers into `Additional Address`.

#### Museum Ships Extractor Requirements

- **FR-022 (Event-Driven)**: When the Museum Ships extractor executes, the script shall harvest global museum ships and preserved warships.
- **FR-023 (Ubiquitous)**: The Museum Ships extractor shall record the vessel name as `POI Name`, normalize host country to standard ISO format, record berthing city or port under `Town/City`, assign the baseline tag "Ship" to all records, conditionally append the tag "Military" if the vessel is a warship, omit naval classification tags, and attach museum/reference links in the `Websites` JSON array.
- **FR-024 (Event-Driven)**: When ship coordinates are cataloged in source registries or encyclopedic lists, the Museum Ships extractor shall serialize decimal `latitude` and `longitude`.

#### Castles of the World Extractor Requirements

- **FR-025 (Event-Driven)**: When the Castles extractor executes, the script shall harvest international castles and fortresses from directory sources (`https://www.castlesworld.com/selection/list.php` and encyclopedic registries).
- **FR-026 (Ubiquitous)**: The Castles extractor shall record the castle name as `POI Name`, normalize sovereign country, record province/region as `State/Province`, record municipality as `Town/City`, assign the baseline tag "Fortification" to all records, and omit architectural classification tags.
- **FR-027 (Event-Driven)**: When high-resolution imagery is present on the castle listing, the Castles extractor shall capture the primary image link into `Hero Image URL`.

#### Aircraft Museums Extractor Requirements

- **FR-028 (Event-Driven)**: When the Aircraft Museums extractor executes, the script shall harvest aviation and aerospace museums worldwide from encyclopedic directories (`https://en.wikipedia.org/wiki/List_of_aviation_museums`).
- **FR-029 (Ubiquitous)**: The Aircraft Museums extractor shall record the museum name as `POI Name`, normalize sovereign country, record state/province and city/airfield, assign the baseline tag "Aircraft" to all records, and omit collection focus tags.
- **FR-030 (Event-Driven)**: When museum coordinates and official portals are available in source tables, the Aircraft Museums extractor shall record `latitude`, `longitude`, and serialize official/Wikipedia portals inside the `Websites` JSON array.
- **FR-031 (Optional Feature)**: Where the user supplies the `--geocode` CLI flag, the extractor framework shall invoke OpenStreetMap Nominatim for records lacking coordinates, strictly adhering to the 1 request/second rate-limiting policy and transmitting `User-Agent: VistaraeDataExtractor/1.0`.
- **FR-032 (State-Driven)**: While executing automated test suites under CI, the extractor test suite shall mock external network transports using canned local HTML fixtures in `tests/unit/extractor_scripts/fixtures/` to achieve deterministic execution and maintain $\ge 90\%$ test coverage in compliance with Constitution Principle 8.

---

### Key Entities

- **`ExtractorRecord`**: The canonical in-memory data transfer object representing a captured point of interest before export.
  - Attributes: `poi_name` (str, required), `country` (str | None), `country_code` (str | None), `state_province` (str | None), `city` (str | None), `street_address` (str | None), `postal_code` (str | None), `additional_addresses` (list[dict[str, Any]]), `latitude` (Decimal | None), `longitude` (Decimal | None), `tags` (list[str]), `websites` (list[dict[str, str]]), `hero_image_url` (str | None), `description` (str | None), `reason_to_visit` (str | None), `estimated_visit_hours` (Decimal | None), `itinerary_days` (int | None), `dates_visited` (list[str]), `photo_directory` (str | None).
- **`BaseExtractor`**: Abstract base class defining common lifecycle methods for all specialized scrapers.
  - Responsibilities: CLI argument parsing, rate-limited HTTP dispatch, caching, HTML soup parsing, baseline and conditional tag resolution, record validation, and CSV/JSON output generation.
- **`ExtractorConfig`**: Configuration dataclass encapsulating execution options.
  - Attributes: `output_path` (Path), `limit` (int | None), `delay_seconds` (float), `deep_scrape` (bool), `cache_enabled` (bool), `output_format` (str), `dry_run` (bool), `user_tags` (list[str]).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of extractor CLI scripts reside in `/extractor_scripts` and share the reusable `extractor_scripts/common` package without duplicate HTTP or CSV serialization routines.
- **SC-002**: Every generated CSV file imports seamlessly into Vistarae's Import Staging Workbench without header parsing errors or schema rejections.
- **SC-003**: 100% of output CSV files pass automated formula injection safety checks, ensuring no unescaped cell starts with `=`, `+`, `-`, `@`, `\t`, or `\r`.
- **SC-004**: Each of the 5 specialized extractors (Hillman Wonders, National Parks, Museum Ships, Castles, Aircraft Museums) successfully executes against its target dataset, producing at least 95% valid records with populated POI names and standardized country values.
- **SC-005**: All CLI scripts support standard terminal help, limit constraints, and progress reporting, allowing non-technical operators to execute sample scrapes in under 30 seconds.

---

## Assumptions

- Target websites remain publicly accessible without requiring paid API keys or interactive CAPTCHA completion.
- Network access is available during live scraping runs, with local disk caching used for offline replay and unit testing.
- Missing geographic coordinates in raw source tables do not prevent record export; Vistarae's internal OpenStreetMap Nominatim geocoder will enrich coordinates during import triage.
- Standard ISO 3166-1 country normalization uses a local lookup table or python library (`pycountry` or static mapping dict) without requiring external network calls.

