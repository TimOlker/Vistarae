<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Research & Technical Decisions: Phase 13 — Multi-Stage POI Export, Flexible Multi-Fidelity Import & Ingestion Enhancements

**Feature Identifier**: `013-poi-export-import-enhancements`  
**Date**: 2026-10-31  
**Spec Reference**: [spec.md](./spec.md)

---

## 1. Dynamic Schema Introspection & Export Serialization

### Unknown / Decision Area
How should the export engine dynamically introspect the application's core POI data model so that newly added fields in future releases are automatically included in CSV, JSON, and YAML exports without maintaining hardcoded column arrays?

### Decision: Pydantic v2 Model Field Introspection via `POIExchangeRecord`
Define `POIExchangeRecord` in `packages/core/vistarae_core/schemas/poi_exchange.py` inheriting from `StrictBaseModel`.
- At runtime, `poi_exporter.py` extracts field names and serialization metadata dynamically using Pydantic v2's `model_fields` dictionary:
  ```python
  export_columns = [field_name for field_name in POIExchangeRecord.model_fields.keys()]
  ```
- **CSV Serialization**: DictWriter initialized with `POIExchangeRecord.model_fields.keys()`. Fields default to empty string `""` when null. UTF-8 Byte Order Mark (`\xef\xbb\xbf`) prepended directly to the byte stream.
- **JSON Serialization**: Pydantic's `model_dump_json(by_alias=True)` or streaming generator outputting a JSON array of objects.
- **YAML Serialization**: `yaml.safe_dump()` streaming generator emitting a list of YAML documents/mappings.
- **Formula Injection Defense**: For CSV output, any string value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is escaped with a leading single quote (`'`).

### Rationale
- Decouples export formats from static code lists.
- Guarantees 100% field parity across backend models, OpenAPI schemas, and export files.
- Automatically supports any future database columns or enrichment attributes added to `POIExchangeRecord`.

### Alternatives Considered
- *Static Tuple/List of Column Names*: Fragile; leads to immediate schema drift whenever new fields are added to the POI table or staging candidates.
- *Raw Database Reflection (`inspector.get_columns`)*: Exposes internal database column naming rather than domain API contract naming, breaking clean separation of concerns and leaking storage details.

---

## 2. Multi-Format Flexible Ingestion & Canonical Header Aliasing

### Unknown / Decision Area
How should the ingestion engine recognize diverse third-party file formats (`.csv`, `.json`, `.yaml`, `.yml`) and reconcile non-standard header names without requiring manual file edits?

### Decision: Multi-Format Parser with Two-Tier Header Resolution & Interactive Fallback
1. **Format Sniffer**:
   - Inspects file extension and MIME type.
   - For CSVs, uses Python's `codecs.getreader("utf-8-sig")` to transparently handle files with or without BOM.
   - For JSON, parses root array of objects or GeoJSON `FeatureCollection` (extracting `properties` and `geometry.coordinates`).
   - For YAML, parses via `yaml.safe_load()`.
2. **Canonical Alias Dictionary**:
   - Normalizes incoming keys (lowercase, stripped of whitespace, underscores, and dashes).
   - Maps known third-party synonyms to canonical `POIExchangeRecord` fields:
     - `lat`, `y`, `latitude`, `lat_wgs84` $\rightarrow$ `latitude`
     - `lon`, `lng`, `long`, `x`, `longitude`, `lon_wgs84` $\rightarrow$ `longitude`
     - `title`, `name`, `place`, `waypoint`, `poi` $\rightarrow$ `poi_name`
     - `desc`, `description`, `notes`, `summary` $\rightarrow$ `ai_description`
     - `category`, `categories`, `tag`, `labels` $\rightarrow$ `tags`
3. **Interactive Column Mapping Dialog**:
   - If any column in the uploaded file does not match an alias or canonical field, the backend returns an HTTP 200 payload with `status: "NEEDS_COLUMN_MAPPING"`, returning:
     - `unmapped_columns`: list of raw headers
     - `sample_rows`: first 3 rows of data
     - `available_target_fields`: list of unassigned `POIExchangeRecord` fields
   - Frontend displays the `ColumnMappingModal.tsx` allowing the user to map or ignore columns, then re-submits with `column_mappings: Record<string, string>`.

### Rationale
- Completely eliminates spreadsheet preprocessing for standard mapping tools.
- Provides a frictionless, guided UX when dealing with custom exports.

---

## 3. Pre-Import Format & Type Sanity Validation

### Unknown / Decision Area
How should pre-import validation catch malformed data (such as booleans or text strings in coordinate columns) while avoiding all-or-nothing friction for large files where only a few rows are corrupted?

### Decision: Row-Level Type Sanity Verification with Interactive Skip/Abort Choice
1. **Pre-Flight Type Checker**:
   - Executes immediately after column alignment and before writing to `ingest_candidates`.
   - Validates:
     - `latitude`: Float between -90.0 and 90.0.
     - `longitude`: Float between -180.0 and 180.0.
     - `dates_visited`: Valid ISO-8601 or common date formats (`YYYY-MM-DD`, `MM/DD/YYYY`).
     - `recommended_duration_hours`: Non-negative float.
     - `itinerary_days`: Non-negative integer.
2. **Error Diagnostic & Interactive Resolution**:
   - If violations are found, backend returns HTTP 422 with a structured payload:
     ```json
     {
       "error_type": "VALIDATION_ERROR",
       "total_rows": 500,
       "invalid_row_count": 3,
       "issues": [
         {
           "row_number": 7,
           "column": "longitude",
           "raw_value": "true",
           "expected": "Float between -180 and 180"
         }
       ]
     }
     ```
   - Frontend launches `ImportValidationErrorModal.tsx` with two actions:
     - **"Skip [N] Invalid Rows & Continue"**: Submits the job with `skip_invalid_rows: true`, staging only the 497 valid rows.
     - **"Abort Import"**: Cancels the session immediately so the user can clean their file.

### Rationale
- Protects database and spatial query engines from corrupted entries.
- Empowers the user to decide whether a small number of malformed rows justifies halting an entire large import.

---

## 4. Decoupled Parallel Ingest Processing & Rate-Limiter Throttling

### Unknown / Decision Area
How can individual POIs be processed in parallel to accelerate ingestion without overwhelming external geocoding APIs (Nominatim's strict 1 req/sec policy) or triggering Gemini API rate quotas?

### Decision: Async Worker Pool with Centralized Token Bucket Rate Limiter
1. **Decoupled Task Decomposition**:
   - Staging service writes candidates to `ingest_candidates` with `phase_state = "PENDING"`.
   - Each POI candidate is evaluated independently for missing fields (dynamic per-field granularity).
2. **Rate Limiting Architecture**:
   - **Nominatim Geocoding**: Controlled by an `AsyncTokenBucket` singleton:
     - Capacity: 1 token
     - Refill rate: 1.0 token per second
     - User-Agent: `VistaraeTravelEngine/1.0`
     - PostGIS / SQLite `geocache` probe executes *before* token acquisition.
   - **Gemini LLM Enrichment**: Controlled by an `asyncio.Semaphore(5)` to bound concurrent API calls within Google AI Studio free/tier rate limits, running with `thinking_budget = 0`.

### Rationale
- Prevents 429 rate limit bans from OpenStreetMap and Google AI Studio.
- Maximizes parallel throughput: fully enriched candidates (Tier E) complete instantly, while candidates requiring geocoding are systematically paced through the token bucket.

---

## 5. Tenant-Scoped ID Reconciliation & Cross-User Sharing

### Unknown / Decision Area
How should internal identifiers (`poi_id`) be handled when exporting POIs, so that same-user backups preserve identity while cross-user community sharing cannot cause ID collisions or tenant contamination?

### Decision: Tenant-Scoped Ownership Check (`WHERE id = :poi_id AND user_id = :current_user_id`)
1. **Export**: Include `poi_id` as the first column for all committed POIs (empty for uncommitted staged candidates).
2. **Import**:
   - When a row contains a `poi_id`, the repository executes:
     ```sql
     SELECT id, name FROM pois WHERE id = :poi_id AND user_id = :current_user_id;
     ```
   - **Match Found**: Candidate is classified as `user_disposition = "update_existing"` with `matched_existing_poi_id = poi_id`.
   - **No Match Found** (different user or deleted POI): Foreign ID is discarded; record is treated as a new POI, evaluated for spatial duplicate candidates, and assigned a freshly generated UUID upon commit.

### Rationale
- Completely adheres to Vistarae Constitution Principle 3 (`WHERE user_id = :current_user_id`).
- Supports flawless restore of personal backups while allowing risk-free sharing across the user community.

---

## 6. POI Creation Timestamp Auditing (`created_at`)

### Unknown / Decision Area
How should POI creation time be tracked and indexed across all ingest sources (CSV, Chrome extension, manual drawer)?

### Decision: Database Default Timestamp with Compound B-tree Index
1. **Schema Migration**:
   ```sql
   ALTER TABLE pois ADD COLUMN created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();
   CREATE INDEX idx_pois_user_created_at ON pois (user_id, created_at DESC);
   ```
2. **Repository & Query Layer**:
   - Repository queries include optional `created_after: datetime | None` and `created_before: datetime | None`.
   - Index supports fast range scans and sorting by date added.
3. **Frontend**:
   - `POITable.tsx` renders localized "Date Added" column (`MMM D, YYYY, h:mm A`).
   - `POIFilterBar.tsx` offers presets: `All Time`, `Today`, `Last 7 Days`, `Last 30 Days`, `Custom Date Range`.

