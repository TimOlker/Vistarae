# Feature Specification: Unified POI Import Staging Workbench

**Feature Branch**: `014-unified-import-staging-workbench`  
**Created**: 2026-11-02  
**Status**: Draft  
**Input**: User description: "Unified POI Import Staging Workbench: Replace the split Phase 1 (Triage) and Phase 2 (Enrichment Review) modal workflow with a single, unified Import Staging Workbench using strict EARS syntax."

---

## Clarifications

### Session 2026-11-02
- Q: When secondary candidates are marked for "In-Batch Merge" into a primary candidate, how should their unique attributes (such as distinct website links, photos, tags, or notes) be combined upon saving or committing to the database? → A: Attribute Aggregation: Combine unique related websites, merge tags, and append notes from secondary candidates into the primary candidate without overwriting primary name or coordinates.
- Q: What hierarchy depth should be supported when designating a POI as a "Sublocation", and how should nested parent-child relationships be constrained? → A: Multi-Level Hierarchy with Cycle Detection: Allow sublocations to be nested arbitrarily deep (e.g., Site → District → Landmark), with validation preventing circular parent references.
- Q: How should the system handle concurrency and progress feedback when "AI Enrich All" is running on a large batch of candidates? → A: Asynchronous Background Processing with Non-Blocking UI: Enrich candidates in the background adhering to 1 req/sec external limits; rows in the workbench table update dynamically as they finish, allowing continuous user editing.
- Q: What should happen if a user attempts to upload a new CSV file while an uncommitted staging session already exists with pending candidates? → A: Strict Guard: Prevent uploading a new file until the user explicitly commits or discards the active session.
- Q: When a traveler manually overrides a system-recommended disposition (e.g. changing an automated "In-Batch Merge" to "Accept"), how should the disposition justification be displayed? → A: Adaptive Justification with Override Badge: Retain the original automated match rationale and add a visual indicator: "User Overridden (Original recommendation: In-Batch Merge based on 94% match with Row #1)".

---

## 1. User Scenarios & Testing *(mandatory)*

### User Story 1 - Single-Stage Workbench Navigation & Inspection (Priority: P1)

As a traveler importing places from a travel spreadsheet or guide, I want a single unified workbench to inspect, triage, edit, and review all imported POIs in one screen, so that I never have to navigate back and forth between separate Phase 1 (Triage) and Phase 2 (Enrichment) modals.

**Why this priority**: Eliminates the primary cognitive friction and workflow interruption of the current multi-stage import wizard, providing immediate visibility and full editability of all POI fields.

**Independent Test**: Can be tested by uploading a multi-row CSV, viewing all candidate records in a single table, selecting any record to open its details, editing both geocoding/location fields and enriched fields (websites, photos, descriptions), and saving changes directly without modal transitions.

**Acceptance Scenarios**:

1. **Given** a user uploads a CSV file and confirms column mappings,  
   **When** staging processing completes,  
   **Then** the system shall present a single unified Import Staging Workbench displaying all candidate POIs in an interactive table with a right-hand candidate details panel.
2. **Given** a candidate POI displayed in the workbench table,  
   **When** the user clicks the row,  
   **Then** the system shall populate the right-hand editor panel with all candidate attributes (name, coordinates, address, disposition, hero image, related websites, duration, notes, tags, description, and interactive map) while keeping the "Save Candidate Changes" button permanently visible in the pinned editor footer.
3. **Given** the user is viewing the workbench table,  
   **When** the user filters by completeness or disposition,  
   **Then** the system shall dynamically filter the candidate list to show only records matching the criteria (e.g., Incomplete, Missing Photo, Missing Location, Duplicates, Excluded).

---

### User Story 2 - Targeted Single-POI and Batch AI Enrichment (Priority: P1)

As a user reviewing imported places, I want to trigger AI enrichment either for a single selected POI on-demand or in bulk for all non-excluded candidates, so that I can quickly fill in missing photos, websites, descriptions, and durations without wasting time or API quotas.

**Why this priority**: Empowers the user to test and refine enrichment on individual difficult records instantly without having to re-run the entire batch.

**Independent Test**: Can be tested by selecting an incomplete candidate, clicking "AI Enrich POI", verifying that only blank fields are populated within seconds, and verifying that clicking "AI Enrich All" processes all eligible candidates in the background.

**Acceptance Scenarios**:

1. **Given** an active candidate in the right-hand editor with missing fields,  
   **When** the user clicks "AI Enrich POI",  
   **Then** the system shall immediately query Wikidata, secondary scraping, and Gemini extraction for that specific POI and update its missing fields in the editor and table without resetting table state or scroll position.
2. **Given** multiple staging candidates with incomplete data,  
   **When** the user clicks "AI Enrich All",  
   **Then** the system shall asynchronously dispatch enrichment tasks for all candidates whose disposition is not Ignore or Exclude and whose fields remain incomplete.
3. **Given** an enriched POI where existing fields were already populated or manually edited,  
   **When** enrichment executes (single or batch),  
   **Then** the system shall preserve all existing user-provided values and only populate empty fields.

---

### User Story 3 - "No Websites" Idempotency & State Tracking (Priority: P2)

As a user managing POI research, I want the system to track when a POI genuinely has no web presence, so that subsequent enrichment runs do not repeatedly waste rate limits or time querying external services for non-existent websites.

**Why this priority**: Prevents redundant external scraping requests and OSM/Wikidata rate-limit penalties across enrichment cycles.

**Independent Test**: Can be tested by running enrichment on an obscure POI with no websites, verifying that "No Websites" is automatically checked, verifying that re-running enrichment skips website queries, and verifying that adding a website unchecks and disables the checkbox.

**Acceptance Scenarios**:

1. **Given** an enrichment process runs for a POI and discovers 0 websites,  
   **When** enrichment completes,  
   **Then** the system shall set `no_websites` to true and check the "No Websites" checkbox.
2. **Given** a candidate POI has one or more related websites in its list,  
   **When** the editor renders the related websites section,  
   **Then** the system shall uncheck and disable the "No Websites" checkbox.
3. **Given** all related websites are removed from a candidate POI,  
   **When** the list becomes empty,  
   **Then** the system shall enable the "No Websites" checkbox, allowing the user to check or uncheck it manually.
4. **Given** a candidate POI has `no_websites` checked,  
   **When** single-POI or batch AI enrichment is executed,  
   **Then** the system shall skip external website lookups and Wikidata searches for that candidate.
5. **Given** a candidate POI has `no_websites` checked,  
   **When** the user adds a new website URL,  
   **Then** the system shall automatically uncheck and disable the `no_websites` checkbox.

---

### User Story 4 - Duplicate Detection, In-Batch Merging & Exclusion Zones (Priority: P2)

As a traveler importing large lists, I want duplicate entries within the same CSV batch to be automatically linked as "In-Batch Merge" to the first detected primary entry, and points in user exclusion zones to be flagged as "Exclude", so that I do not waste time or AI resources on redundant places.

**Why this priority**: Avoids duplicate enrichment spend and prevents unwanted places from polluting the user's permanent map.

**Independent Test**: Can be tested by importing a CSV containing identical or near-duplicate POIs and POIs within a configured exclusion zone, verifying that the first instance is marked "New POI" (Accept) and subsequent instances are marked "In-Batch Merge" pointing to the first, with a read-only explanation of the match.

**Acceptance Scenarios**:

1. **Given** a CSV batch contains multiple records matching the same physical location or name,  
   **When** duplicate detection runs,  
   **Then** the system shall set the first detected instance as the primary candidate and set subsequent matching instances to disposition `In-Batch Merge` with a reference to the primary candidate.
2. **Given** a candidate POI falls within a user-defined Exclusion Zone,  
   **When** staging evaluation runs,  
   **Then** the system shall set its disposition to `Exclude` and populate a read-only disposition justification explaining the zone match.
3. **Given** a candidate POI has a system-recommended disposition,  
   **When** the user views the editor,  
   **Then** the system shall display a read-only explanation detailing why the disposition was selected (e.g., trigram similarity score, distance threshold, or exclusion zone name).
4. **Given** a candidate POI with an automated disposition,  
   **When** the user desires a different outcome,  
   **Then** the system shall allow the user to override the disposition to any valid option (e.g., Accept, Ignore, Sublocation).

---

### User Story 5 - Spatial Proximity, Parent-Child Linking & Commit (Priority: P2)

As a traveler organizing an itinerary, I want to view nearby existing POIs on an interactive map with an adjustable distance radius (100 ft to 100 miles) and set parent-child sublocations, so that complex sites (like museums inside parks) are properly structured before committing to the database.

**Why this priority**: Ensures spatial accuracy, proper hierarchical relationships, and clean data integrity upon database insertion.

**Independent Test**: Can be tested by adjusting the radius slider, picking a location on the map, selecting a parent POI, attempting to save a Sublocation without a parent (verifying rejection), and finally clicking "Save POI(s) to DB" to commit records to PostGIS.

**Acceptance Scenarios**:

1. **Given** a candidate selected in the editor,  
   **When** the user adjusts the proximity radius slider (from 100 ft to 100 miles),  
   **Then** the system shall display all existing database POIs and staged batch candidates within that radius on the map, updating a badge count of matching nearby points.
2. **Given** the user sets a candidate's disposition to `Sublocation`,  
   **When** the user attempts to save without designating a parent POI,  
   **Then** the system shall reject the save and display an inline validation error indicating that a parent POI is required for sublocations.
3. **Given** the user selects a parent POI via map or selector,  
   **When** the user saves the candidate,  
   **Then** the system shall store the parent POI reference and allow the disposition to persist.
4. **Given** the user has reviewed and completed editing staging candidates,  
   **When** the user clicks "Save POI(s) to DB",  
   **Then** the system shall commit all active accepted candidates to the permanent database, associate parents/children, and purge the temporary staging records.

---

### User Story 6 - In-Batch Merges, Dual-Scope Parent Hierarchy & Orphan Safety (Priority: P2)

As a user importing complex datasets, I want the system to handle both intra-batch parent/child relationships and prevent orphaned records if a primary candidate is excluded or ignored, so that my travel data hierarchy remains clean and reliable.

**Why this priority**: Eliminates data corruption, broken foreign keys, or stranded child/duplicate POIs when users manipulate batch records in staging.

**Independent Test**: Can be tested by setting Candidate B as a Sublocation or In-Batch Merge of Candidate A (both in the same batch), changing Candidate A to Exclude, and verifying the system guides the user to reassign or promote Candidate B before saving.

**Acceptance Scenarios**:

1. **Given** Candidate B is marked `In-Batch Merge` into Candidate A,  
   **When** the user changes Candidate A's disposition to `Ignore` or `Exclude`,  
   **Then** the system shall alert the user and require reassigning Candidate B's merge target or promoting Candidate B to `Accept`.
2. **Given** the user searches for a parent POI for a `Sublocation` candidate,  
   **When** the parent selector modal opens,  
   **Then** the system shall search and display matches from both the user's permanent database and active eligible candidates in the current import batch.
3. **Given** the user selects multiple candidates across the table,  
   **When** the user opens the batch edit panel,  
   **Then** the system shall allow applying Country, State/Province, City/Town, and Visit Date simultaneously across all selected records.

---

### Edge Cases

- **Network interruption during single-POI enrichment**: The editor displays an inline error toast, restores the "AI Enrich POI" button, and preserves existing data without leaving the row in a locked state.
- **Saving a Sublocation with an invalid or deleted parent**: The system validates that the selected parent exists in the database or active batch; if not, the save is blocked with a descriptive error.
- **In-Batch Merge where primary candidate is skipped or excluded**: If the user marks the primary candidate as "Ignore" or "Exclude", the system alerts the user and prompts to reassign the primary candidate or make the secondary candidate an independent POI.
- **Batch CSV with missing coordinates**: The candidate row is flagged with a warning pill "Missing Location", and the user can click on the map to set coordinates or run address geocoding directly in the editor.
- **User closes browser during batch enrichment**: Staging records persist on the backend; upon reopening the workbench via active session, the enriched data is loaded seamlessly.

---

## 2. Requirements *(strict EARS syntax)*

### Ubiquitous Requirements
- **FR-001**: The system shall provide a single unified Import Staging Workbench interface replacing the separate Phase 1 Triage and Phase 2 Enrichment Review modals.
- **FR-002**: The system shall display all imported candidates in an interactive table supporting multi-column sorting, text search, completeness status badges, and disposition selectors.
- **FR-003**: The system shall provide a right-hand candidate editor panel containing a fixed header, a scrollable body for all candidate attributes, and a permanently pinned footer containing the "Save Candidate Changes" action.
- **FR-004**: The system shall store a `no_websites` boolean property on each staging candidate record.

### Event-Driven Requirements
- **FR-005**: WHEN the user selects a candidate row in the workbench table, the system shall load all candidate attributes into the right-hand editor panel and center the interactive mini-map on the candidate's coordinates.
- **FR-006**: WHEN the user clicks "AI Enrich POI" in the candidate editor, the system shall asynchronously retrieve missing hero photo, related websites, visit duration, tags, and description for that specific candidate only.
- **FR-007**: WHEN the user clicks "AI Enrich All", the system shall enqueue background enrichment for all candidates in the batch whose disposition is eligible (not Ignore or Exclude) and whose data is incomplete.
- **FR-008**: WHEN an enrichment run discovers no official or third-party websites for a candidate, the system shall set `no_websites` to true and check the "No Websites" checkbox.
- **FR-009**: WHEN one or more related websites are present in a candidate's list, the system shall uncheck and disable the "No Websites" checkbox.
- **FR-010**: WHEN all related websites are removed from a candidate, the system shall enable the "No Websites" checkbox for manual user selection.
- **FR-011**: WHEN the user clicks "Save Candidate Changes", the system shall validate the candidate data, persist the updates to the staging store, update the row in the table, and display a confirmation toast.
- **FR-012**: WHEN the user clicks "Save POI(s) to DB", the system shall commit all accepted candidates to the permanent PostGIS database, create hierarchy relationships, and remove the temporary staging session.
- **FR-013**: WHEN the user adjusts the proximity slider, the system shall update the map view and count label to reflect all POIs in the database and import batch within the selected radius (100 feet to 100 miles).
- **FR-014**: WHEN the user selects multiple candidates, the system shall provide batch actions to edit Country, State/Province, City/Town, Date Visited, or Export selected records.
- **FR-022**: WHEN the user adds a website URL to a candidate whose `no_websites` flag is true, the system shall automatically uncheck and disable the `no_websites` flag.
- **FR-023**: WHEN the user searches for or selects a parent POI for a `Sublocation` candidate, the system shall include both existing database POIs and active eligible staging candidates from the current batch in the candidate selection list.
- **FR-024**: WHEN the user applies batch edits for Country, State/Province, City/Town, or Date Visited across selected candidates, the system shall update all selected candidates in the staging store and reflect the updated values in the table.
- **FR-028**: WHEN an In-Batch Merge candidate is committed with its primary candidate, the system shall aggregate unique related websites, combine non-duplicate tags, and append visit notes from the secondary candidate into the primary candidate without overwriting the primary candidate's authoritative name, coordinates, or core description.
- **FR-029**: WHEN the user assigns a parent to a candidate with disposition Sublocation, the system shall permit multi-level parent-child nesting across database and batch POIs while enforcing acyclic validation to reject any assignment that would create a circular dependency loop.

### State-Driven Requirements
- **FR-015**: WHILE `no_websites` is true for a candidate, the system shall skip external website queries during all subsequent AI enrichment executions.
- **FR-016**: WHILE a candidate's disposition is set to `Accept` or `Sublocation`, the system shall highlight missing required fields (Country, State/Province, City/Town, Location coordinates, Hero photo) with visual warning indicators.
- **FR-017**: WHILE single-POI enrichment is actively executing, the system shall display an active loading spinner on the "AI Enrich POI" button and disable redundant clicks.
- **FR-025**: WHILE a candidate is selected in the editor, the system shall display a read-only disposition justification stating the exact matching criteria (trigram similarity score, distance threshold, or exclusion zone identifier) that prompted the recommended disposition, and IF the user overrides the disposition, THEN the system shall retain the original criteria alongside a visible 'User Overridden' badge.
- **FR-026**: WHILE the map view is active in the candidate editor, the system shall display a live badge indicating the count of nearby database POIs and staged candidates within the active radius threshold.
- **FR-030**: WHILE background batch enrichment is active, the system shall process candidates asynchronously respecting external service rate limits, stream completion updates to the workbench table without blocking user interaction, and allow uninterrupted inspection and manual editing of other candidate rows.

### Unwanted Behavior & Validation Requirements
- **FR-018**: IF the user attempts to save a candidate with disposition `Sublocation` when no parent POI is designated, THEN the system shall reject the save and display an error message stating that a parent POI must be selected.
- **FR-019**: IF a candidate falls within a user-configured Exclusion Zone, THEN the system shall set its default disposition to `Exclude` and populate a read-only justification specifying the matching exclusion zone.
- **FR-020**: IF duplicate candidates are detected within the same import batch, THEN the system shall designate the first occurrence as the primary candidate, designate subsequent occurrences as `In-Batch Merge`, and display a read-only justification specifying the matching fields and similarity score.
- **FR-021**: IF the user saves edits on an `In-Batch Merge` candidate, THEN the system shall allow the user to override the disposition to `Accept` (New POI), `Ignore`, or `Sublocation`.
- **FR-027**: IF a primary candidate is changed to `Ignore` or `Exclude` when secondary candidates are designated to merge into it, THEN the system shall block the change and prompt the user to reassign the primary merge target or promote the secondary candidate to `Accept`.
- **FR-031**: IF a user attempts to upload a new CSV file while an uncommitted staging session exists, THEN the system shall block the upload and instruct the user to either commit accepted candidates or discard the active session first.

---

## 3. Key Entities

- **IngestStagingJob**: Represents the active import session; contains total rows, candidate count, job status, user ID, and timestamps.
- **IngestCandidate**: Represents a staged POI record prior to final DB commitment.
  - *Attributes*: `id`, `job_id`, `row_index`, `poi_name`, `latitude`, `longitude`, `street_address`, `city`, `state_province`, `country`, `postal_code`, `hero_image_url`, `related_websites` (list of name + url), `no_websites` (boolean), `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `tags`, `description`, `reason_to_visit`, `disposition` (`Accept`, `Sublocation`, `In-Batch Merge`, `Update Existing`, `Exclude`, `Ignore`), `disposition_justification` (string), `parent_poi_id` (optional), `merge_target_id` (optional), `is_duplicate` (boolean), `confidence_score` (float).
- **ExclusionZone**: User-configured geographic boundary polygon; triggers automatic `Exclude` disposition for intersecting coordinates.

---

## 4. Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: 100% of candidate inspection, triage, geocoding correction, and enrichment review tasks can be completed in a single workbench screen without navigating across modal phases.
- **SC-002**: Targeted single-POI enrichment ("AI Enrich POI") executes and updates the candidate in under 3.5 seconds.
- **SC-003**: 0 redundant external website requests are made for candidates with `no_websites` checked during subsequent batch or single enrichment executions.
- **SC-004**: The "Save Candidate Changes" button is visible 100% of the time in the editor view without scrolling, regardless of form content length or screen resolution.
- **SC-005**: 100% of candidates set to `Sublocation` without an assigned parent are blocked from being saved or committed to the database.
- **SC-006**: Users can batch edit administrative location fields (Country, State/Province, City/Town) across 50+ candidates in under 3 clicks.
- **SC-007**: 0 orphaned candidates can be created; changing a primary candidate's disposition to `Ignore` or `Exclude` forces resolution of all secondary in-batch merge candidates.
- **SC-008**: Parent POI selector resolves matches across both existing database records and current-batch candidates in under 1 second.

---

## 5. Assumptions

- **A-001**: Existing geocoding and deduplication algorithms (trigram matching, PostGIS spatial radius queries) will be reused for initial candidate staging scoring.
- **A-002**: Nominatim rate limits (1 req/sec) and Google Gemini quota boundaries continue to be enforced by the backend enricher service.
- **A-003**: The user interface targets desktop viewport widths ($\ge 1280\text{px}$) suitable for side-by-side data table and detail editing workbenches.
- **A-004**: Temporary staging records are retained in PostgreSQL staging tables until the user explicitly commits or discards the job.

---

## 6. Architectural Analysis: Contradictions, Missing Logic & Recommended Enhancements

### A. Contradictions with Previous Logic to Address
1. **Multi-Phase API Status**:
   - *Previous Logic*: Ingest jobs moved sequentially through `phase_1_triaged` $\rightarrow$ `phase_2_enriching` $\rightarrow$ `phase_2_enriched`.
   - *Resolution*: Unify staging into a single state machine where candidates have independent statuses (`staged`, `enriching`, `ready_to_commit`, `committed`). A job is simply active until committed or discarded.
2. **Dedicated vs Unified Websites**:
   - *Previous Logic*: Separate database and schema fields existed for `official_url` and `wiki_url`.
   - *Resolution*: Retain `official_url` and `wiki_url` on backend schemas as derived properties from `related_websites`, ensuring full backward compatibility with export formats while presenting a unified list in the UI.

### B. Missing Logic Identified & Handled
1. **Primary Candidate Deletion/Exclusion in In-Batch Merges**:
   - If candidate B is marked `In-Batch Merge` into candidate A, but the user subsequently marks candidate A as `Ignore` or `Exclude`, candidate B would be orphaned.
   - *Logic Added (FR-027)*: When candidate A is excluded or ignored, the system prompts the user to either promote candidate B to `Accept` (primary) or reassign the merge target.
2. **Parent POI Resolution Scope**:
   - Parents for `Sublocation` can be either an *existing database POI* OR *another accepted candidate in the current batch*.
   - *Logic Added (FR-023)*: The parent selector search includes both existing database POIs and valid staging candidates in the active batch.
3. **No Websites Reversal**:
   - If `no_websites` was set to true (either automatically or manually), and the user later manually adds a link or pastes a URL, the system must automatically uncheck and disable the `no_websites` flag to maintain state consistency (FR-022).

### C. Recommended High-Value Features Included
1. **Disposition Reasoning & Confidence Log**:
   - A dedicated read-only justification box in the editor explaining exactly why a recommendation was made (FR-025).
2. **Dynamic Nearby POI Radius Slider**:
   - Logarithmic radius selector ranging from 100 ft to 100 miles, with live counter badges showing how many existing POIs and batch candidates fall within that radius (FR-013, FR-026).
3. **Multi-Row Batch Location Editing**:
   - Direct batch updating for Country, State/Province, City/Town, and Visit Date across selected rows (FR-014, FR-024).
