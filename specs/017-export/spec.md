# Feature Specification: Full-Fidelity CSV Export & Roundtrip Re-Import (017-export)

**Feature Branch**: `017-export`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Export (017-export) unified Import Staging Workbench using strict EARS syntax. In the POI Import Staging Workbench export to CSV logic: support all fields in the POI Import Staging Workbench so that an exported file contains everything needed to re-import the CSV and rebuild the list of POIs. If additional fields are added in the future to the intake processing, make sure they are included in the export / import logic."

## Clarifications

### Session 2026-11-11

- Q: When a traveler clicks the "Export" button in the workbench header while table filters, search queries, or candidate row selections are active, which candidates should the generated CSV include? → A: Option A: Complete session by default, row-selection when checked: exports all candidates in the job by default; if one or more candidate checkboxes are selected, exports only the selected candidates.
- Q: How should multi-valued list attributes (tags, dates_visited, photo_directories) and structured pairs (related_websites) be formatted in the exported CSV cells, and how should the intake parser interpret them upon re-import? → A: Option A: Tolerant dual-mode: export simple lists as semicolon-separated (e.g. "Volcano; Scenic") and complex pairs as JSON; on re-import, accept both valid JSON arrays and semicolon/comma-delimited strings.
- Q: When re-importing an exported CSV into a new staging session, how should intra-batch linkages between candidates (such as parent_candidate_id for macro-site nesting and merge_target_id for in-batch duplicates) be reconnected when new database UUIDs are generated for the newly created staging rows? → A: Option A: UUID Translation Mapping: export previous candidate_id; on re-import, map old_candidate_id to new_candidate_id so that parent_candidate_id and merge_target_id re-link seamlessly.
- Q: When a traveler clicks "Export" while actively editing candidate fields in the detail pane, how should the export handle uncommitted in-memory edits versus persisted database records? → A: Option A: Flush & hybrid export: automatically flush active editor inputs into the candidate state before generating the CSV, and provide both client-side instant export and a backend API export endpoint.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Full-Fidelity Workbench CSV Export (Priority: P1)

As a traveler curating points of interest in the Import Staging Workbench, I want to export my entire staged session into a comprehensive CSV containing every edited and enriched candidate field, so that I have a complete, offline portable backup of my triage and curation work.

**Why this priority**: The existing workbench export only outputs 10 basic fields, stripping vital metadata including admin subdivisions, descriptions, visit reasons, tags, website lists, photo directories, visit dates, parent hierarchies, and disposition rationales. Providing full-fidelity export prevents irreversible data loss when saving or pausing import sessions.

**Independent Test**: Can be tested by opening the workbench with a diverse set of staged candidates (containing all address tiers, tags, multiple websites, photo directories, visit dates, parent linkages, and manual overrides), clicking "Export", and verifying that the downloaded CSV contains all headers, formatted data, and escaped fields matching the active workbench state.

**Acceptance Scenarios**:

1. **Given** a staging session with candidates containing complete metadata, **When** the traveler clicks the "Export" button in the workbench header, **Then** the system shall generate and trigger the download of an RFC 4180 compliant CSV named `vistarae_staging_<job_id>.csv` containing columns for all candidate attributes.
2. **Given** candidates with multi-valued or structured attributes (e.g., related website pairs, tags, local photo directories, and dates visited), **When** the CSV export is generated, **Then** the system shall serialize simple string lists (`tags`, `photo_directories`, `dates_visited`) as human-readable semicolon-separated values and complex pairs (`related_websites`) as JSON arrays within quoted CSV cells.
3. **Given** uncommitted edits actively present in the candidate detail editor, **When** the traveler clicks "Export", **Then** the system shall flush active editor values into the candidate dataset prior to serialization so no pending edits are lost.
4. **Given** candidates with text fields containing commas, line breaks, or quotation marks (e.g., descriptions or visit notes), **When** exported, **Then** the system shall surround cells with double quotes and escape internal quotes by doubling them (`""`) in strict compliance with RFC 4180.
5. **Given** candidates with leading formula characters (`=`, `+`, `-`, `@`), **When** exported, **Then** the system shall prepend a safe apostrophe (`'`) to neutralize spreadsheet formula injection vulnerabilities.
6. **Given** candidates with intra-batch parent associations (`parent_candidate_id`) or merge references (`merge_target_id`), **When** exported, **Then** the CSV shall include the candidate's unique identifier (`candidate_id`) and referenced IDs to preserve hierarchy across sessions.

---

### User Story 2 - Lossless Re-Import & Session Rebuild (Priority: P1)

As a traveler who previously exported a staging workbench CSV, I want to upload the exported CSV file back into Vistarae, so that the staging workbench accurately rebuilds the exact list of candidates with all previous edits, dispositions, coordinates, and rich metadata preserved without degradation.

**Why this priority**: An export file is only as useful as its ability to restore state. Enabling full-fidelity re-import allows travelers to pause work, edit candidates externally in spreadsheet software, and restore their curated session seamlessly.

**Independent Test**: Can be tested by taking a freshly exported workbench CSV, starting a new intake job with that CSV file, and verifying that the resulting workbench candidates match the original candidate attributes, dispositions, and hierarchy 100%.

**Acceptance Scenarios**:

1. **Given** a full-fidelity exported workbench CSV file, **When** the traveler uploads the file through the intake upload modal, **Then** the ingestion parser shall automatically detect the full-fidelity header schema and map all exported columns into candidate staging records.
2. **Given** exported records containing previously assigned dispositions (e.g., `accept`, `sublocation`, `in_batch_merge`, `exclude`, `ignore`), **When** re-imported, **Then** the workbench shall restore the traveler's explicit user dispositions and justifications instead of resetting them to initial heuristic defaults.
3. **Given** exported records containing structured website lists (`[{"name":"Skate Park","url":"https://example.com"}]`), tags, photo directories, and visit dates, **When** re-imported, **Then** the intake parser shall deserialize structured strings—accepting both JSON arrays and semicolon/comma-delimited text—into candidate arrays and entities with zero data corruption.
4. **Given** exported records with intra-batch parent candidate or merge target associations, **When** re-imported, **Then** the intake processor shall translate the exported candidate IDs into the newly generated database UUIDs, seamlessly reconstructing the parent-child nesting and merge links.

---

### User Story 3 - Schema-Driven Extensibility for Future Intake Fields (Priority: P2)

As a developer or system administrator evolving the Vistarae platform, I want the export and import subsystems to use a centralized, schema-driven field registry, so that any new candidate attribute added to intake processing is automatically included in export and import without requiring disparate manual changes across multiple files.

**Why this priority**: Eliminates brittle hardcoded column arrays, prevents schema drift between the frontend modal and backend ingestion services, and guarantees that future feature additions remain roundtrip-compatible.

**Independent Test**: Can be tested by registering a mock or newly added candidate attribute in the schema registry and verifying that both CSV export and intake parser include the new field in columns and entity mapping automatically.

**Acceptance Scenarios**:

1. **Given** the centralized schema definition of candidate attributes, **When** the export generator or intake parser initializes, **Then** both subsystems shall derive their column definitions, headers, and serialization formats dynamically from the schema registry.
2. **Given** an exported CSV containing newly added or unexpected extension columns, **When** processed by the intake parser, **Then** the parser shall ingest known schema fields into first-class candidate attributes while preserving unknown extension columns in a dynamic metadata dictionary.

---

### Edge Cases

- **What happens when a candidate contains empty or null values for optional attributes?**
  The exporter shall emit empty values (`""`) between commas without emitting string literals like `"None"`, `"null"`, or `"undefined"`. On re-import, empty strings shall deserialize to `null` or empty collections as appropriate.
- **What happens when a traveler modifies column headers or reorders columns in an external spreadsheet editor (e.g., Excel)?**
  The intake parser shall match columns using case-insensitive header names and known aliases rather than rigid column index positions, permitting safe column reordering.
- **What happens when a text cell starts with a formula character (`=SUM(...)`)?**
  The exporter shall prefix the cell with `'` to prevent spreadsheet code execution; the importer shall strip the leading formula-neutralization apostrophe so the user's raw text is faithfully restored.
- **What happens when website lists or tag arrays contain commas or quotes?**
  The system shall serialize complex nested structures using JSON stringification within RFC 4180 quoted CSV cells, ensuring internal delimiters do not split columns.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: _Ubiquitous_: The export subsystem shall define a canonical, schema-driven field specification covering all candidate attributes: `candidate_id`, `row_index`, `poi_name`, `street_address`, `city`, `locality`, `admin_level_2`, `admin_level_1`, `state_province`, `postal_code`, `country`, `country_code`, `latitude`, `longitude`, `recommended_disposition`, `user_disposition`, `confidence_score`, `disposition_justification`, `description`, `reason_to_visit`, `hero_image_url`, `official_url`, `wiki_url`, `related_websites`, `no_websites`, `tags`, `photo_directory`, `photo_directories`, `dates_visited`, `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `parent_candidate_id`, `parent_poi_id`, `matched_existing_poi_id`, `merge_target_id`, and `is_user_overridden`.
- **FR-002**: _Event-Driven_: When the traveler clicks the "Export" button in the Import Staging Workbench, the export subsystem shall serialize all staged candidates in the active job into an RFC 4180 CSV document adhering to the canonical field specification, unless one or more candidate rows are explicitly selected via checkboxes, in which case the subsystem shall export only the selected candidate rows.
- **FR-003**: _State-Driven_: While serializing complex structured fields, the export subsystem shall format simple string lists (`tags`, `photo_directories`, `dates_visited`) as human-readable semicolon-separated values (e.g. `Volcano; Scenic`) and structured pairs (`related_websites`) as valid JSON strings safely enclosed within double-quoted CSV cells.
- **FR-004**: _Event-Driven_: When serializing text values that begin with formula trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`), the export subsystem shall sanitize the value by prepending a neutralizing single quote (`'`) to protect spreadsheet consumers against formula injection.
- **FR-005**: _Event-Driven_: When parsing an uploaded CSV file during intake processing, the CSV parser shall inspect header rows case-insensitively and bind recognized column names to candidate attributes based on the canonical field specification.
- **FR-006**: _State-Driven_: While deserializing imported collection fields, the CSV parser shall strip formula-neutralizing leading quotes from text fields and parse collection columns (`tags`, `photo_directories`, `dates_visited`, `related_websites`) by first attempting JSON parsing if enclosed in brackets (`[...]`), falling back to semicolon or comma delimiter splitting for simple lists.
- **FR-007**: _Event-Driven_: When an imported record contains explicit values for `user_disposition`, `disposition_justification`, or `is_user_overridden`, the ingestion engine shall preserve those user selections, bypassing heuristic reassignment.
- **FR-008**: _Optional Feature_: Where an uploaded CSV file contains unknown or unmapped columns not present in the current schema, the intake parser shall capture those excess columns in the candidate's raw metadata dictionary so that no data is permanently lost.
- **FR-009**: _Ubiquitous_: The engineering architecture shall synchronize candidate field definitions between the backend ingestion model and the frontend workbench schema, ensuring that adding a new attribute to the intake schema automatically registers the attribute in both export and import workflows.
- **FR-010**: _Unwanted Behaviour_: If an exported CSV contains special characters, non-Latin scripts, or accented glyphs (e.g., German umlauts, French accents, Chinese characters), the export subsystem shall encode the output file in UTF-8 with a Byte Order Mark (BOM) to ensure correct rendering in Microsoft Excel and other international spreadsheet viewers.
- **FR-011**: _Event-Driven_: When re-importing an exported CSV into a new staging session, the intake parser shall record an in-memory translation table mapping each record's exported `candidate_id` to its newly generated database UUID, and resolve `parent_candidate_id` and `merge_target_id` references using this mapping to reconstruct intra-batch hierarchies and merge targets accurately.
- **FR-012**: _Event-Driven_: When the traveler triggers CSV export from the workbench UI while uncommitted changes exist in the active candidate detail editor, the workbench shall automatically flush the editor form state into the in-memory candidate record prior to generating the export payload.
- **FR-013**: _Ubiquitous_: The backend service layer shall expose a dedicated export endpoint (`GET /api/ingest/jobs/{job_id}/candidates/export`) that streams an RFC 4180 CSV containing all staged candidates for headless, CLI, or large-batch export operations.

### Key Entities _(include if feature involves data)_

- **ExportFieldDefinition**: Metadata descriptor specifying column header name, canonical attribute key, data type (string, numeric, boolean, json_array, json_object), formula-sanitization requirement, and deserialization transformer.
- **StagingCandidateExportRow**: Serialized tabular representation of a single `IngestCandidateTable` record containing all 35+ first-class attributes and extensions.
- **IntakeColumnMappingRegistry**: Bidirectional mapping registry connecting raw CSV header variants to canonical candidate attributes.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of candidate attributes present in the staging workbench and database are included in the generated CSV export.
- **SC-002**: Roundtrip fidelity achieves 100% parity: exporting a staged session and immediately re-importing the resulting CSV reproduces identical candidate attributes, coordinates, dispositions, tags, photo directories, and website lists without data loss.
- **SC-003**: 100% of exported CSV files open in standard spreadsheet applications (Excel, Google Sheets, LibreOffice Calc) without character encoding corruption, delimiter splitting, or security formula execution warnings.
- **SC-004**: Adding a new candidate field to the centralized schema registry requires zero manual alterations to separate column serialization or parser mapping files.
- **SC-005**: Re-import processing of a 1,000-candidate exported CSV completes within 5 seconds.

## Assumptions

- Travelers use standard spreadsheet applications (Excel, Google Sheets, LibreOffice) that conform to RFC 4180 CSV handling with UTF-8 encoding.
- Structured fields such as `related_websites` and `photo_directories` can be safely represented as JSON within quoted CSV cells without exceeding maximum cell length limitations (typically 32,767 characters in Excel).
- When re-importing an exported CSV into a new session, foreign key references to database POIs (`matched_existing_poi_id`, `parent_poi_id`) remain valid if the target POIs exist in the user's account; if not found, the parser safely logs a warning and stores the reference in metadata without aborting ingestion.
