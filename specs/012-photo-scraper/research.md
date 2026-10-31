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

# Research & Technical Decisions: Phase 12 — Photo Scraper CLI & Two-Phase Interactive CSV Ingestion

**Feature Identifier**: `012-photo-scraper`  
**Feature Branch**: `012-photo-scraper`  
**Date**: 2026-10-28  
**Status**: Completed  

---

## 1. Overview & Research Objectives

Phase 12 requires two major technical subsystems that work in close coordination without duplicating logic:
1. **Standalone Photo Scraper CLI**: An offline-portable, read-only filesystem traversal tool that parses irregular directory paths, extracts image metadata across embedded standards (EXIF, IPTC, XMP) and companion sidecars (`.xmp`, `.json`, `.xml`), resolves location candidates via Google Gemini Flash-Lite with local SQLite caching, and exports an RFC 4180 CSV with formula injection sanitization.
2. **Two-Phase Interactive Web Application Ingestion Engine**: An asynchronous ingestion pipeline that pre-validates and stages CSV rows in an `ingest_candidates` table, presents a Phase 1 triage modal with interactive map marker selection for parent-child sublocations, runs Phase 2 web scraping and personalized LLM enrichment (using Phase 11 travel style prompt directives), and executes an atomic multi-visit merge and database commit.

---

## 2. Technical Decisions & Architectural Rationales

### Decision 1: Pure-Python Multi-Standard Metadata & Sidecar Extraction Engine

- **Context**: The photo scraper CLI must extract GPS coordinates, earliest capture timestamps, and descriptive tags from image files (`.jpg`, `.jpeg`, `.tiff`, `.heic`, `.png`, `.webp`, `.dng`) and companion sidecar files (`.xmp`, `.json`, `.xml`) across diverse operating systems (Windows, macOS, Linux) without requiring external binary runtimes or system package dependencies.
- **Decision**: Implement `services/scraper/metadata_extractor.py` using:
  1. **Pillow (`PIL.Image`) + `exifread`**: Extracts EXIF tags (`GPSLatitude`, `GPSLongitude`, `DateTimeOriginal`, `CreateDate`, `XPKeywords`) directly from image binary headers. Converts degrees/minutes/seconds rational tuples to decimal WGS-84 degrees.
  2. **`defusedxml`**: Securely parses embedded XMP packets (RDF/XML) and companion `.xmp` / `.xml` sidecars without vulnerability to XML entity expansion attacks, extracting `exif:GPSLatitude`, `exif:GPSLongitude`, `photoshop:DateCreated`, and `dc:subject`.
  3. **Standard Python `json`**: Parses Google Photos Takeout sidecar files (`<filename>.json` and `<filename>.<ext>.json`), extracting `geoData.latitude`, `geoData.longitude`, `photoTakenTime.timestamp`, and tags.
  4. **Strict Binary Read-Only Access**: All file handlers strictly utilize `open(file_path, "rb")` inside context managers. No lockfiles, hidden state files, or index files are ever written to the scanned target directory.
- **Alternatives Considered**:
  - *External Perl `exiftool` binary*: Rejected because it requires users to install Perl and the external ExifTool binary, introducing complex cross-platform distribution and path dependencies.
  - *OS Native Windows/macOS APIs*: Rejected because native APIs lack cross-platform uniformity between Windows (`System.Drawing`) and Linux.

---

### Decision 2: Contextual Path Cleaning & Gazetteer Hierarchy Heuristics

- **Context**: Photo archives possess non-standard folder structures with prefixes (e.g. `1-Tokyo`, `1 - Fussen`, `A-Kobe`, `03 Oaxaca`), trip containers (e.g. `Trip To India`), date suffixes (e.g. `Japan 4-03`), parenthetical alternate names (e.g. `Senso-ji (Asakusa Kannon Temple)`), and personal noise folders (`Tim`, `Maria`, `bad`, `thumbs`).
- **Decision**: Implement a modular deterministic path pipeline in `services/scraper/path_parser.py`:
  1. **Noise Pruning**: Filter folders starting with `.`, matching `New Folder*`, caseless noise keywords (`bad`, `thumb`, `thumbs`, `thumbnails`, `resource.frk`, `misc`), and personal names (`Tim`, `Maria`).
  2. **Prefix & Token Stripping**: Regex regex patterns `^(?:[0-9]+|[a-zA-Z])\s*-\s*` and `^[0-9]{2,}\s+` strip sequence prefixes (e.g. `1-Tokyo` -> `Tokyo`, `03 Oaxaca` -> `Oaxaca`, `02 Parque Museo De La Venta` -> `Parque Museo De La Venta`).
  3. **Trip & Country Normalization**: Detect `Trip To <Name>` and `<Name> <date-token>` patterns. Validate tokens against a lightweight embedded ISO-3166 country and regional gazetteer. When a country is identified, propagate it as the default ambient country context for all descendant subfolders.
  4. **Alternate Name Splitting**: Detect `Name (AltName)` syntax via `^(.*?)\s*\((.*?)\)$`, splitting into primary landmark name and alternate candidate name.
  5. **Regional Heuristics**: Regional landmarks lacking coordinates (e.g. `Garfield Park Conservatory`, `Herrik Lake`) default to ambient state `Illinois` when no contrary context is discovered.
- **Alternatives Considered**:
  - *Relying entirely on LLM for path parsing*: Rejected because running LLMs over every single raw folder string is slow, expensive, and non-deterministic for obvious pattern pruning (such as `.DS_Store` or `thumbs`).

---

### Decision 3: LLM Location Resolution, Confidence Scoring & Local SQLite Caching

- **Context**: Candidate directory tokens, GPS coordinates, and abstracted image tags must be resolved into standardized POI names, addresses, and confidence scores. Ambiguous brands (e.g. `McDonalds`) and generic activities without GPS (e.g. `Sledding`) must receive low confidence scores.
- **Decision**: Implement `services/scraper/location_resolver.py`:
  1. **Model & SDK**: Google Gemini Flash-Lite via `google-genai` SDK with `thinking_budget = 0`.
  2. **Structured Output**: Enforce Pydantic schema `POIStandardizedLocationSchema` returning `poi_name`, `street_address`, `city`, `state_province`, `zip_code`, `country`, and `location_confidence_percent` (0-100).
  3. **Ambiguity Penalties**: System prompt instructs the model to assign low confidence ($\le 15\%$) for generic labels without GPS (e.g. `Sledding`) and penalize ubiquitous multi-location chains ($\le 30\%$) lacking exact coordinates.
  4. **Strict Online Requirement**: Per clarified requirement, the CLI verifies `GOOGLE_API_KEY` and network access prior to processing, immediately halting with an actionable message if missing.
  5. **Local Persistent Cache**: Implement a local SQLite cache `.scraper_cache.db` storing SHA-256 hashes of `(path_tokens, coords, tags)` -> JSON response, guaranteeing zero redundant external calls on repeated scans.
- **Alternatives Considered**:
  - *Unstructured text completion*: Rejected per Constitution Principle 5 and Core Rules (structured JSON with Pydantic is required).

---

### Decision 4: Two-Phase Ingestion Architecture & `ingest_candidates` Staging Lifecycle

- **Context**: Importing unvalidated POIs directly into the main `pois` database table leads to map pollution and expensive wasted LLM web scraping calls on invalid records.
- **Decision**: Structure the web application ingestion into two clean stages:
  1. **Stage 1 (Upload & Pre-Validation)**:
     - The user uploads a CSV file via `CSVUploadModal.tsx`.
     - Fast parsing and validation via `services/ingest/services/csv_parser.py` (file $\le 2\text{MB}$, rows $\le 2,000$, formula sanitization).
     - Asynchronous worker resolves reverse geocoding for rows with coordinates and forward geocoding fallbacks for rows without coordinates.
     - Spatial ($\le 50\text{m}$) and trigram ($\ge 0.60$) deduplication evaluates match against existing user POIs.
     - Staged rows are inserted into `ingest_candidates` table with `job_id`, `user_id`, initial address, coordinates, confidence, and recommended disposition (`accept`, `ignore`, `update existing POI`, `sublocation`).
  2. **Phase 1 Validation Modal (`CSVTriageModal.tsx`)**:
     - Displays all rows from `ingest_candidates`.
     - User edits details, alters dispositions, and clicks existing POI map markers to link `parent_poi_id` for sublocations.
     - Clicking **Cancel** purges `ingest_candidates` for that `job_id`.
     - Clicking **Proceed** updates `ingest_candidates` and advances only non-ignored rows.
  3. **Stage 2 (AI Enrichment & Review Modal `CSVPhase2ReviewModal.tsx`)**:
     - Backend scraper orchestrator fetches external web context for accepted and sublocation candidates.
     - Gemini Flash-Lite synthesizes `description`, `reason_to_visit` (using traveler prompt directives from Phase 11 `user_prompts`), and tags, updating `ingest_candidates`.
     - UI presents enriched table with skip toggles, edit modal, interactive map, and **Save to DB** button.
     - Atomic transaction: inserts new POIs, inserts child sublocations with `parent_poi_id`, merges visit dates/paths/tags into existing POIs (preserving primary coordinates unless user toggled coordinate update), and purges `ingest_candidates`.
- **Alternatives Considered**:
  - *Browser-only state between Phase 1 and Phase 2*: Rejected in clarification session (Option A selected); server-side staging in PostgreSQL `ingest_candidates` guarantees persistence against accidental browser refreshes during long-running enrichment.

---

### Decision 5: Shared RFC 4180 CSV Exporter Engine & Aligned Multi-Address Lists

- **Context**: The photo scraper and future extractors must emit identical CSV column structures that the web application ingestion parser natively consumes. Multi-address records must be represented cleanly in tabular form.
- **Decision**: Implement `packages/core/vistarae_core/services/csv_exporter.py`:
  1. Standardized 12-column header list: `POI Name`, `Street Address`, `Town/City`, `State/Province`, `Zip Code`, `Country`, `Tags`, `latitude`, `longitude`, `dates visited`, `Photo directory`, `location_confidence_percent`.
  2. Semicolon-delimited lists for multi-address fields, ensuring positional 1:1 index alignment (e.g. index 0 in `Street Address` matches index 0 in `Town/City`, `State/Province`, etc.).
  3. Semicolon-delimited list for `dates visited`.
  4. Formula injection neutralization: prepends single quote `'` to cells starting with `=`, `+`, `-`, `@`, `\t`, `\r`.
  5. Shared schema `POIExportRecord` in `vistarae_core.schemas.poi_export` used across both CLI export and webapp ingest parsing.
- **Alternatives Considered**:
  - *JSON arrays inside CSV cells*: Rejected because semicolons provide cleaner visual readability in spreadsheet editors (Excel, LibreOffice) while preserving RFC 4180 parsing simplicity.

---

## 3. Constitution & Operational Invariants Mapping

| Invariant / Constitutional Principle | Project Requirement | Implementation Mechanism |
| :--- | :--- | :--- |
| **Principle 1: File Headers & Formatting** | Copyright banner, docstrings, cognitive complexity $\le 15$. | Standard Apache 2.0 header on all `.py`, `.ts`, `.tsx`, `.sql` files. Ruff and Prettier checks. |
| **Principle 2: Monorepo & Ports/Adapters** | Core domain in `packages/core`, dependency inversion. | Shared schemas (`POIExportRecord`) and CSV services in `packages/core`. Pure domain decoupled from HTTP/boto3. |
| **Principle 3: Database & Tenancy** | Pure Async SQLAlchemy, `WHERE user_id = :current_user_id`, no RLS. | `ingest_candidates` table has `user_id` FK. Every query filters by `user_id`. Cascade on user delete. |
| **Principle 4: Alembic Migrations** | Reversible migrations, `StrEnum` backed by `VARCHAR`. | Alembic migration for `ingest_candidates` with reversible `downgrade()`. Dispositions typed via `StrEnum`. |
| **Principle 5: API Contracts & Validation** | OpenAPI 3.1, TypeScript sync, Pydantic `StrictBaseModel`. | Contracts defined in `contracts/photo-scraper-api.yaml`. Strict Pydantic models with `extra="forbid"`. |
| **Principle 6: Middleware & Security** | Formula neutralization, rate limiting, no credential leaks. | CSV cell sanitization. Read-only filesystem operations. |
| **Principle 7: Observability & Tracing** | Directional `MSG` logging markers in dev, W3C traceparent. | Directional logging tags for SQS worker, geocoder, and Gemini extraction calls. |
| **Principle 8: PyTest Governance** | $\ge 90\%$ test coverage, unit tests mirror production tree. | Comprehensive unit tests for path parsing, EXIF extraction, CSV export, and two-phase ingest routes. |
| **Operational Invariant 1: SQS Ingestion** | Batch size 10, file $\le 2\text{MB}$, rows $\le 2000$, visibility 180s. | Enforced in `csv_parser.py` and `services/worker/processor.py`. |
| **Operational Invariant 3: Zero-Cost Arch** | Neon scale-to-zero, free-tier limits, Nominatim 1 req/sec. | Rate-limited Nominatim geocoder with SQLite (CLI) and PostGIS `geocache` (backend). |

