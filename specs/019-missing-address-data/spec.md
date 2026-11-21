# Feature Specification: Incomplete Data Acknowledgment & Exemption Checkboxes (019-missing-address-data)

**Feature Branch**: `019-missing-address-data`

**Created**: 2026-11-18

**Status**: Clarified

**Input**: User description: "When importing POIs, some addresses, either detected by the vistarae logic or by user manually creating a POI may not have some information available. This then results in a user having a POI flagged as incomplete on the import logic. A checkbox should be provided on the import information to allow a user to manually specify that data is not available or whatever is flagging the data as incomplete is acceptable. There should be a checkbox for each type of incomplete data rule. For example no address should have one and missing websites should have another one. In the import page, there should be a way to filter out records with one or more of these checkboxes set. When these checkboxes are set they should not be marked as incomplete for that specific field. These checkboxes should never be automatically set. This will help users in finding records that need to be fixed, and not need to keep seeing POIs that are known to be missing data. These new fields should be included with the POI. Please flag any contradictions with previous logic or missing logic or features to include that might be useful."

---

## Clarifications

### Session 2026-11-18

- **Q (Exemption Scope & Rules)**: Which incomplete data rules should feature exemption checkboxes?
  - **Decision**: **Option B — Strictly `no_address` and `no_websites` only**. Exemptions are scoped to missing street address (`no_address`) and missing official/related websites (`no_websites`). Photo and coordinates follow standard completeness and mapping constraints without custom exemption checkboxes.
- **Q (Workbench Filter Presentation)**: How should the filter to hide or isolate exempted records be surfaced in the workbench UI?
  - **Decision**: **Option B — Completeness Dropdown Options Only**. The existing Completeness dropdown is expanded to include `"Needs Action"` (candidates that are incomplete and possess zero exemptions) and `"Exempted"` (candidates having `no_address = true` or `no_websites = true`), allowing users to instantly filter out records where data absence has already been acknowledged.
- **Q (Batch Exemption Application)**: Should travelers be able to apply exemption checkboxes across multiple staged candidates simultaneously?
  - **Decision**: **Option A — Include Batch Exemption Action in Multi-Row Toolbar**. When two or more candidates are selected in the workbench table, the multi-row bulk action toolbar exposes quick actions to "Mark Selected: No Address", "Mark Selected: No Websites", and "Clear Selected Exemptions".
- **Q (Needs Action Filter Semantics)**: When a candidate has an exemption checkbox enabled (e.g. `no_address = true`) but is still missing another unexempted required field (such as a photo), should the "Needs Action" filter continue to display this candidate?
  - **Decision**: **Option A — Display in "Needs Action" if ANY required field is unfulfilled and unexempted**. A candidate remains in the "Needs Action" filtered view as long as it has at least one missing field that lacks an active exemption, ensuring no actionable defects are hidden.
- **Q (Exemption Reset on Data Entry)**: When a traveler inputs or saves a valid street address or website URL on a candidate or POI where that exemption checkbox was previously checked, how should the system handle the exemption flag?
  - **Decision**: **Option A — Automatically uncheck the exemption flag**. Entering or updating a non-empty street address resets `no_address` to `false`, and populating an official URL or related website resets `no_websites` to `false`, preventing conflicting data states.

---

## Architecture Alignment & Contradictions with Previous Logic

The following contradictions, superseded legacy behaviors, and architectural gaps have been identified between this feature and previous specifications:

1. **Automatic Flag Assignment vs. Strict User-Only Control (Contradiction)**:
   - _Previous Logic (Spec 014, Line 19)_: `no_websites` could be toggled manually or set automatically by AI enrichment when 0 external sources were discovered.
   - _New Specification_: Exemption checkboxes (`no_address` and `no_websites`) **MUST NEVER** be set or checked automatically by AI scrapers, geocoders, or heuristic parsers. They represent explicit human intent acknowledging that missing data is acceptable or unavailable.

2. **Database Persistence on Permanent POIs (Architectural Gap)**:
   - _Previous Logic (Spec 014, DB Schema)_: `no_websites` existed only on `ingest_candidates`. It did not exist on `pois`. When candidates were committed to the permanent database, the user's manual acknowledgment was discarded.
   - _New Specification_: Exemption attributes (`no_address` and `no_websites`) must be first-class columns on both `ingest_candidates` and `pois` tables, and included in `POICreate`, `POIUpdate`, and `POIResponse` schemas, as well as CSV/JSON import/export routines.

3. **Completeness Scoring and Status Recalculation (Superseded Logic)**:
   - _Previous Logic (Frontend `getCandidateMissingFields`)_: Missing street address or missing websites unconditionally added `"Street Address"` or `"Websites"` to the missing fields list, causing the candidate to be permanently badged as "Incomplete".
   - _New Specification_: Setting an exemption checkbox satisfies that rule's completeness requirement. A candidate missing a street address with `no_address = true` and having all other required fields shall evaluate to **Complete**.

4. **AI Bulk Enrichment Interaction (Spec 018 Optimization)**:
   - _Previous Logic_: "AI Enrich All" enqueued candidates to scrape websites and query search engines regardless of whether the user had already acknowledged that no website exists.
   - _New Specification_: When `no_websites = true`, AI enrichment workers must skip web-scraping queries for that candidate. When `no_address = true`, workers must skip reverse-geocoding street address lookups, conserving Gemini tokens and scraping rate limits.

---

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Candidate Incomplete Data Exemption in Staging Workbench (Priority: P1)

As a traveler triaging imported points of interest in the Import Staging Workbench, I want to manually check individual exemption checkboxes ("No address available" and "No website available") on staged candidates that naturally lack physical street addresses (e.g. mountain peaks, wilderness overlooks) or official websites, so that they are no longer flagged as incomplete and do not clutter my incomplete triage queue.

**Why this priority**: Without manual exemption checkboxes, legitimate natural attractions, scenic viewpoints, and small local spots remain permanently flagged as incomplete, preventing travelers from distinguishing between genuinely deficient records and records where data absence is expected.

**Independent Test**: Can be tested by importing a CSV containing a wilderness peak with coordinates and photo but no street address and no website. Observe that it initially displays "Incomplete" (missing Street Address and Websites). Open the candidate editor, select "No address available" and "No website available", and click "Save Changes". Verify that the candidate completeness status transitions to "Complete" and individual missing badges are cleared.

**Acceptance Scenarios**:

1. **Given** a staged candidate with no street address and `no_address = false`, **When** the workbench calculates completeness, **Then** the candidate shall be flagged as incomplete with "Street Address" listed under missing fields.
2. **Given** a staged candidate with no street address, **When** the user checks "No address available" and saves the candidate, **Then** the candidate shall no longer flag "Street Address" as missing.
3. **Given** a staged candidate with no websites and `no_websites = false`, **When** the workbench calculates completeness, **Then** the candidate shall be flagged as incomplete with "Websites" listed under missing fields.
4. **Given** a staged candidate with no websites, **When** the user checks "No website available" and saves the candidate, **Then** the candidate shall no longer flag "Websites" as missing.
5. **Given** a staged candidate whose only missing data points have their corresponding exemption checkboxes enabled, **When** completeness is evaluated, **Then** the candidate overall completeness status shall display as "Complete".
6. **Given** an automated ingestion job, CSV parse, or AI enrichment run, **When** processing candidate records, **Then** the system shall never automatically enable any exemption checkbox.

---

### User Story 2 - Workbench Filtering for Action-Required vs. Exempted Records (Priority: P1)

As a traveler managing a large import batch with hundreds of candidates, I want to filter the workbench table using dedicated Completeness dropdown options ("Needs Action" and "Exempted"), so that I can filter out records with one or more checkboxes set and focus strictly on records that require attention and action.

**Why this priority**: When triaging large batches, seeing already-acknowledged records repeatedly wastes time. Travelers need a one-click mechanism to surface only actionable, non-exempted incomplete candidates.

**Independent Test**: Can be tested on a batch of 10 candidates where 4 are complete, 3 are incomplete with no exemptions, 2 are missing an address with `no_address` checked and all other fields present (thus fully complete), and 1 is missing both an address (with `no_address` checked) and a photo (unexempted). Select "Needs Action" in the Completeness dropdown. Verify that exactly the 4 actionable incomplete candidates (the 3 unexempted + the 1 missing a photo) are shown. Select "Exempted" and verify that all 3 candidates having exemptions appear.

**Acceptance Scenarios**:

1. **Given** the workbench table displaying candidate rows, **When** the user selects `"Needs Action"` from the Completeness filter dropdown, **Then** the table shall display exclusively those candidates that have at least one unfulfilled required field that is not exempted.
2. **Given** the workbench table displaying candidate rows, **When** the user selects `"Exempted"` from the Completeness filter dropdown, **Then** the table shall display exclusively those candidates that have `no_address = true` OR `no_websites = true`.
3. **Given** a candidate that is currently visible in the `"Needs Action"` filtered view, **When** the user fulfills or exempts all remaining missing fields on that candidate and saves, **Then** the candidate shall immediately be removed from the filtered `"Needs Action"` view.
4. **Given** the filter is toggled back to `"All"`, **When** the table refreshes, **Then** all candidates including exempted records shall be visible with visual exemption indicator badges.

---

### User Story 3 - Multi-Row Batch Exemption in Staging Workbench (Priority: P2)

As a traveler importing dozens of remote natural landmarks or trailheads, I want to select multiple candidate rows and mark them as "No Address" or "No Websites" in a single batch operation, so that I do not have to edit each candidate individually.

**Why this priority**: Triaging large imported batches one-by-one is tedious. Batch actions enable travelers to process large sets of similar places in seconds.

**Independent Test**: Select 5 candidate rows lacking street addresses via table checkboxes. Click "Mark Selected: No Address" on the multi-row action toolbar. Verify that all 5 candidates immediately have `no_address = true` persisted and their completeness status recalculated.

**Acceptance Scenarios**:

1. **Given** two or more candidate rows are selected in the workbench table, **When** the selection changes, **Then** the system shall display the multi-row batch action bar with buttons for "Mark Selected: No Address", "Mark Selected: No Websites", and "Clear Selected Exemptions".
2. **Given** candidate rows are selected, **When** the user clicks "Mark Selected: No Address", **Then** the system shall persist `no_address = true` across all selected candidates and refresh their completeness statuses.
3. **Given** candidate rows are selected, **When** the user clicks "Mark Selected: No Websites", **Then** the system shall persist `no_websites = true` across all selected candidates and refresh their completeness statuses.
4. **Given** candidate rows with existing exemptions are selected, **When** the user clicks "Clear Selected Exemptions", **Then** the system shall reset both `no_address = false` and `no_websites = false` across all selected candidates and refresh their completeness statuses.

---

### User Story 4 - Persistence Across Promotion and POI Lifecycle (Priority: P1)

As a traveler committing reviewed candidates to my permanent points of interest library, I want the exemption flags to be saved on the created POI records and editable in the main POI editor, so that my permanent POIs remember that data was intentionally omitted and do not re-flag as incomplete during future exports or reviews.

**Why this priority**: Staging decisions must not be lost upon committing. If exemption flags only live in staging, exporting and re-importing or viewing POIs in the main library would regress back to flagging missing data.

**Independent Test**: Can be tested by committing an ingest candidate with `no_address = true` to the database. Verify via API and database query that the resulting `pois` row contains `no_address = true`. Open the POI in the main library `EditPOIModal` and verify the "No address available" checkbox is checked and editable.

**Acceptance Scenarios**:

1. **Given** an ingest candidate with `no_address = true` and `no_websites = true`, **When** the candidate is committed to the POI library, **Then** the system shall persist `no_address = true` and `no_websites = true` on the created `pois` record.
2. **Given** an existing POI viewed in the main application `EditPOIModal`, **When** the modal renders, **Then** the system shall display editable checkboxes for "No address available" and "No website available".
3. **Given** an existing POI, **When** the user toggles an exemption checkbox and saves the POI, **Then** the system shall update the `pois` record and maintain the updated state in future queries.
4. **Given** a user exporting POIs to CSV or JSON, **When** the export file is generated, **Then** the export shall include the exemption flags (`no_address`, `no_websites`) as distinct fields.

---

### User Story 5 - AI Bulk Enrichment Skip Optimization (Priority: P2)

As a traveler running AI Bulk Enrichment on an import batch, I want the enrichment engine to respect my manual exemption checkboxes by skipping web-scraping for candidates marked `no_websites` and skipping address lookup for candidates marked `no_address`, so that AI tokens and external API rate limits are not squandered attempting to find data I already know does not exist.

**Why this priority**: Avoids redundant external HTTP calls and LLM token usage, speeding up batch enrichment runs and preventing AI from hallucinating or overwriting user intentions.

**Independent Test**: Can be tested by executing bulk enrichment on a candidate with `no_websites = true`. Verify in the worker audit log that website search and scraping phases are skipped for this candidate while preserving other enrichment attributes (description, category, tags).

**Acceptance Scenarios**:

1. **Given** a queued candidate with `no_websites = true`, **When** the enrichment worker processes the candidate, **Then** the worker shall bypass external website discovery and scraping steps.
2. **Given** a queued candidate with `no_address = true`, **When** the enrichment worker processes the candidate, **Then** the worker shall bypass reverse geocoding address backfill steps.
3. **Given** an enrichment worker finishes processing a candidate, **When** candidate updates are persisted, **Then** the worker shall preserve all existing user exemption flags without modification.

---

### Edge Cases

- What happens if a user enters or updates a valid `street_address` when `no_address` is `true`?
  - The system shall automatically reset `no_address` to `false` upon entering or saving a non-empty street address, ensuring the exemption is cleared when data becomes available.
- What happens if a user enters or updates an official website URL or adds a related website when `no_websites` is `true`?
  - The system shall automatically reset `no_websites` to `false` upon adding or saving valid website data.
- What happens if coordinates are missing? Can a user check an exemption for coordinates?
  - Coordinates are structurally required by PostGIS for all permanent POIs (`geom NOT NULL`). As decided in Clarification Q1, coordinates do not have an exemption checkbox and remain strictly mandatory for map rendering.
- What happens if a CSV is imported with legacy columns that lack exemption fields?
  - The system shall default all exemption fields to `false` for imported records lacking explicit values.
- What happens during in-batch merge or duplicate resolution?
  - When merging candidate A into candidate B, if either candidate has an exemption checkbox set, the merged candidate shall retain `true` for that exemption unless populated data overrides it.

---

## Requirements _(mandatory)_

The following functional requirements are specified using strict EARS (Easy Approach to Requirements Syntax) patterns:

### Functional Requirements

#### Core Data Model & Persistence
- **REQ-EXM-001**: _Ubiquitous_: The database schema shall persist `no_address` and `no_websites` as non-nullable boolean columns with default `FALSE` on both the `ingest_candidates` and `pois` tables.
- **REQ-EXM-002**: _Ubiquitous_: The backend domain models (`POIBase`, `POICreate`, `POIUpdate`, `POIResponse`, `CandidateBase`, `CandidateUpdate`) shall expose `no_address` and `no_websites` as boolean fields.
- **REQ-EXM-003**: _Event-Driven_: When promoting an ingest candidate to a permanent point of interest during workbench commit, the system shall copy the candidate's `no_address` and `no_websites` values directly to the corresponding `pois` table columns.
- **REQ-EXM-004**: _Unwanted Behaviour_: If any automated ingestion, geocoding, file parsing, or AI enrichment process executes on a candidate or point of interest, then the system shall not automatically set `no_address`, `no_websites`, or any other exemption flag to `true`.
- **REQ-EXM-005**: _Ubiquitous_: The system shall require explicit human user interaction to enable any data exemption checkbox.

#### Completeness Evaluation Logic
- **REQ-EXM-006**: _State-Driven_: While evaluating candidate or POI completeness, the system shall treat the street address completeness requirement as satisfied if `street_address` is non-empty OR `no_address` is `true`.
- **REQ-EXM-007**: _State-Driven_: While evaluating candidate or POI completeness, the system shall treat the website completeness requirement as satisfied if `official_url` is non-empty OR `related_websites` contains at least one item OR `no_websites` is `true`.
- **REQ-EXM-008**: _Event-Driven_: When a candidate has all missing fields covered either by populated data or by active exemption checkboxes, the system shall classify the candidate's overall completeness status as `Complete`.
- **REQ-EXM-009**: _State-Driven_: While rendering the candidate completeness column in the workbench table, the system shall display a distinct visual indicator showing that specific missing fields have been manually exempted.

#### Workbench User Interface & Candidate Editor
- **REQ-EXM-010**: _Ubiquitous_: The workbench candidate detail editor panel shall provide a dedicated "Data Availability" section containing independent checkboxes for "No address available / Acceptable" (`no_address`) and "No website available / Acceptable" (`no_websites`).
- **REQ-EXM-011**: _Event-Driven_: When the user toggles any exemption checkbox in the candidate detail editor and clicks save, the system shall persist the updated boolean values to the candidate record and immediately recalculate the candidate completeness status.
- **REQ-EXM-012**: _Ubiquitous_: The main application point of interest creation and edit dialogs (`CreatePOIModal`, `EditPOIModal`) shall provide the identical exemption checkboxes for `no_address` and `no_websites`.

#### Workbench Filtering
- **REQ-EXM-013**: _State-Driven_: While viewing the Import Staging Workbench, the completeness filter dropdown shall provide options for `All`, `Complete`, `Incomplete`, `Needs Action` (candidates having at least one unexempted missing required field), and `Exempted` (candidates having `no_address = true` or `no_websites = true`).
- **REQ-EXM-014**: _Event-Driven_: When the traveler selects `"Needs Action"` from the completeness filter dropdown, the workbench table shall display exclusively those candidate rows that possess at least one unfulfilled required field that is not exempted.
- **REQ-EXM-015**: _Event-Driven_: When the traveler selects `"Exempted"` from the completeness filter dropdown, the workbench table shall display exclusively those candidate rows where `no_address` is `true` OR `no_websites` is `true`.

#### Multi-Row Batch Exemption
- **REQ-EXM-016**: _State-Driven_: While two or more candidate rows are selected in the workbench table, the multi-row bulk action toolbar shall display actions for "Mark Selected: No Address", "Mark Selected: No Websites", and "Clear Selected Exemptions".
- **REQ-EXM-017**: _Event-Driven_: When the user clicks "Mark Selected: No Address", the system shall set `no_address = true` across all currently selected candidate rows, persist the changes, and recalculate their completeness statuses.
- **REQ-EXM-018**: _Event-Driven_: When the user clicks "Mark Selected: No Websites", the system shall set `no_websites = true` across all currently selected candidate rows, persist the changes, and recalculate their completeness statuses.
- **REQ-EXM-019**: _Event-Driven_: When the user clicks "Clear Selected Exemptions", the system shall set both `no_address = false` and `no_websites = false` across all currently selected candidate rows, persist the changes, and recalculate their completeness statuses.

#### AI Bulk Enrichment Integration
- **REQ-EXM-020**: _State-Driven_: While an AI Bulk Enrichment worker executes for a candidate with `no_websites = true`, the worker shall skip all external search engine and web-scraping calls targeted at discovering websites.
- **REQ-EXM-021**: _State-Driven_: While an AI Bulk Enrichment worker executes for a candidate with `no_address = true`, the worker shall skip all reverse-geocoding street address queries for that candidate.
- **REQ-EXM-022**: _Ubiquitous_: The AI Bulk Enrichment worker shall preserve all existing user-configured exemption flags across candidate update operations.

#### Export & Import Alignment
- **REQ-EXM-023**: _Event-Driven_: When exporting points of interest to CSV or JSON formats, the system shall include `no_address` and `no_websites` as distinct export attributes.
- **REQ-EXM-024**: _Event-Driven_: When importing points of interest from CSV or JSON files containing `no_address` or `no_websites` columns, the system shall map those values into the corresponding candidate attributes.
- **REQ-EXM-025**: _State-Driven_: While importing files lacking `no_address` or `no_websites` columns, the parser shall default both fields to `false`.

#### Automatic Exemption Reset on Data Entry
- **REQ-EXM-026**: _Event-Driven_: When a user inputs or updates a non-empty `street_address` on a candidate or point of interest where `no_address` is `true`, the system shall automatically reset `no_address` to `false`.
- **REQ-EXM-027**: _Event-Driven_: When a user inputs or updates a non-empty `official_url` or adds an item to `related_websites` on a candidate or point of interest where `no_websites` is `true`, the system shall automatically reset `no_websites` to `false`.

---

### Key Entities

- **IngestCandidate**: Represents a staged POI record prior to final commit.
  - Attributes updated: `no_address` (Boolean, default: false), `no_websites` (Boolean, default: false).
- **PointOfInterest (POI)**: The permanent domain entity stored in PostGIS.
  - Attributes updated: `no_address` (Boolean, default: false), `no_websites` (Boolean, default: false).
- **CompletenessEvaluation**: The rule engine calculating whether a candidate or POI is complete.
  - Attributes: `missing_fields` (List of unfulfilled rules excluding exempted ones), `exempted_fields` (List of rules satisfied via manual user exemption), `is_complete` (Boolean).

---

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of candidates missing only fields that have active exemption checkboxes evaluate to "Complete" status without error.
- **SC-002**: Zero (0%) exemption checkboxes are automatically checked or modified by backend AI, scraper, or geocoding services during ingestion or enrichment.
- **SC-003**: Filtering by "Needs Action" or "Exempted" updates the visible candidate list in under 100 milliseconds for batches of up to 1,000 candidates.
- **SC-004**: 100% of candidate exemption states (`no_address`, `no_websites`) are faithfully preserved when committed to the permanent `pois` table and when round-tripped through CSV/JSON export and import.
- **SC-005**: AI Bulk Enrichment token and web-query consumption is reduced by at least 30% on batches where `no_websites` is flagged, due to skipped scraping phases.
- **SC-006**: Applying multi-row batch exemptions completes and updates the UI for 50 selected candidates in under 1 second.
- **SC-007**: 100% of candidates with active exemptions automatically reset their respective exemption flag when valid data is entered for that field.

---

## Assumptions

- Users understand that enabling an exemption checkbox indicates that missing data is intentionally acceptable and will satisfy that specific completeness rule.
- Physical coordinates (`latitude`, `longitude`, and PostGIS `geom`) remain mandatory for committing POIs to the database, because a point of interest cannot be rendered or spatially indexed on the travel map without geographic coordinates.
- Address components other than street address (such as `country_code`, `locality`, and `admin_level_1`) continue to be derived from reverse geocoding when coordinates are provided, but lack of a specific street number/name is exempted when `no_address` is set.
- Existing candidate and POI records currently in the database will have `no_address = false` and `no_websites = false` via database migration defaults.
