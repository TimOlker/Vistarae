# Architecture Decisions & Research: Full-Fidelity CSV Export & Roundtrip Re-Import (017-export)

**Feature**: `017-export` | **Date**: 2026-11-11

---

## Decision 1: Canonical Schema Registry for Export & Ingestion

### Context
The Import Staging Workbench and backend `IngestCandidateTable` maintain over 35 attributes. Previously, the frontend modal had a hardcoded 10-column list in `handleExportCsv`, while the backend CSV parser relied on static string dictionaries. Adding any new candidate field required updating multiple independent files with risk of schema drift.

### Decision
Define a centralized, schema-driven field specification in `packages/core/vistarae_core/schemas/export_schema.py` (`ExportFieldDefinition`) mirrored in TypeScript (`frontend/src/types/export-schema.ts`).
Each definition specifies:
- `header_name`: User-facing CSV column name (e.g. `POI Name`, `Street Address`, `Tags`).
- `attribute_key`: Canonical internal candidate attribute name (e.g. `poi_name`, `street_address`, `tags`).
- `data_type`: Type classification (`string`, `number`, `boolean`, `string_list`, `json_object_list`, `uuid`).
- `is_formula_sanitized`: Whether cell text requires leading single-quote prefixing on export.
- `serializer`: Transformation function for CSV representation.
- `deserializer`: Transformation function from raw cell string to staging candidate value.

### Rationale & Alternatives
- *Alternative Considered*: Ad-hoc mapping in route handlers. Rejected because it duplicates logic across frontend and backend.
- *Selected Approach*: Eliminates schema drift, enables dynamic column discovery, and guarantees that future fields registered in the schema are automatically included in export and import logic.

---

## Decision 2: Tolerant Dual-Mode Serialization for Structured Collections

### Context
Candidates contain complex multi-valued fields:
- Simple string lists: `tags` (e.g. `['Volcano', 'Scenic']`), `dates_visited`, `photo_directories`.
- Complex structured pairs: `related_websites` (e.g. `[{name: 'Official Park Site', url: 'https://nps.gov'}]`), `addresses`.
Users editing CSVs in spreadsheet software (Excel, Google Sheets) expect readable, easily editable lists like `Volcano; Scenic`, but JSON structures are needed for object pairs.

### Decision
Implement tolerant dual-mode serialization:
- **On Export**: Serialize simple string lists as semicolon-separated values (`Tag1; Tag2`) and complex pairs as valid JSON strings (`[{"name": "...", "url": "..."}]`) inside RFC 4180 double-quoted CSV cells.
- **On Import**: The CSV parser inspects the cell value. If the string starts with `[` and ends with `]`, it parses it as JSON. If JSON parsing fails or the string lacks brackets, it falls back to semicolon/comma delimiter splitting.

### Rationale & Alternatives
- *Alternative Considered*: Pure JSON for all collections. Rejected because semicolon-separated tags are a fundamental convention in travel CSVs (and feature 016 extractors).
- *Alternative Considered*: Pure semicolon-separated for everything. Rejected because object pairs (`name` and `url`) cannot be cleanly represented without ambiguous custom delimiters.

---

## Decision 3: Spreadsheet Formula Injection Neutralization & Symmetric Stripping

### Context
When exporting data containing user-supplied strings or scraped descriptions that begin with formula trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`), opening the CSV in spreadsheet applications could execute malicious formulas (CSV Injection / Formula Injection).

### Decision
- **On Export**: Prepend a single quote (`'`) to any string value whose first non-whitespace character matches `=|\+|-|@|\t|\r`. Surrounding quotes adhere to RFC 4180.
- **On Import**: When reading string values, check if the value begins with `'` immediately followed by a formula prefix character. If so, strip the leading apostrophe to restore the user's authentic data.

### Rationale & Alternatives
- *Alternative Considered*: Strip the formula character completely. Rejected because legitimate travel notes (e.g. `+1 555-0199`, `-15% entrance discount`) would lose their prefix character.

---

## Decision 4: Intra-Batch Hierarchy & UUID Translation Mapping

### Context
Staging candidates can reference other candidates in the same batch:
- `parent_candidate_id`: Sublocation hierarchy / macro-site nesting (e.g. Yellowstone Grand Prismatic Spring nested under Yellowstone National Park).
- `merge_target_id`: In-batch duplicate merging.
When exporting, these refer to existing `candidate_id` UUIDs. When re-importing the CSV into a fresh staging session, the database generates *new* primary key UUIDs for the staging rows. Without translation, foreign keys would dangle or point to old sessions.

### Decision
- **On Export**: Include `candidate_id`, `parent_candidate_id`, and `merge_target_id` columns.
- **On Import**: Maintain an in-memory dictionary `uuid_translation_map: dict[str, UUID]` mapping `exported_candidate_id -> new_candidate_uuid`. In a two-pass ingestion step (or post-row creation resolution), resolve `parent_candidate_id` and `merge_target_id` to their new session UUIDs.

---

## Decision 5: Export Trigger Scope & Detail Editor Auto-Flushing

### Context
Travelers frequently edit fields (e.g. adjusting coordinates, changing dispositions, editing descriptions) in the active right-hand detail pane of the workbench without immediately saving. If they click "Export", uncommitted changes could be lost. Furthermore, users may want to export only filtered or selected rows.

### Decision
- **State Flush**: When the "Export" button is clicked, the workbench modal triggers an instant flush of the active editor form state into the candidate item in memory before serialization begins.
- **Scope Selection**: If one or more candidate rows have checkboxes selected in the table, export only the selected candidates. If zero checkboxes are selected, export all staged candidates in the active session.

---

## Decision 6: Backend Streaming Export Endpoint

### Context
While client-side export is ideal for interactive work in the browser, automated workflows, CLI integrations, and large sessions require a reliable backend API endpoint.

### Decision
Expose `GET /api/ingest/jobs/{job_id}/candidates/export`:
- Streams RFC 4180 compliant CSV using FastAPI's `StreamingResponse`.
- Prepends UTF-8 Byte Order Mark (`\ufeff`) to ensure international characters render properly in Microsoft Excel.
- Implements chunked database cursor iteration to stream records without holding the entire batch in memory.

