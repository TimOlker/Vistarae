# Implementation Plan: Full-Fidelity CSV Export & Roundtrip Re-Import (017-export)

**Branch**: `017-export` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/017-export/spec.md`

---

## Summary

Feature 017 delivers full-fidelity CSV export and roundtrip re-import for the POI Import Staging Workbench. The existing workbench export is limited to 10 basic fields, losing vital metadata (admin subdivisions, descriptions, visit reasons, tags, website lists, photo directories, visit dates, parent hierarchies, and disposition rationales). 

This feature introduces:
1. **Schema-Driven Field Registry**: A canonical field specification covering all 35+ candidate attributes (`candidate_id`, `row_index`, `poi_name`, `street_address`, `city`, `locality`, `admin_level_2`, `admin_level_1`, `state_province`, `postal_code`, `country`, `country_code`, `latitude`, `longitude`, `recommended_disposition`, `user_disposition`, `confidence_score`, `disposition_justification`, `description`, `reason_to_visit`, `hero_image_url`, `official_url`, `wiki_url`, `related_websites`, `no_websites`, `tags`, `photo_directory`, `photo_directories`, `dates_visited`, `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `parent_candidate_id`, `parent_poi_id`, `matched_existing_poi_id`, `merge_target_id`, `is_user_overridden`).
2. **Dual-Mode Structured Serialization**: Semicolon-delimited simple string lists (`tags`, `photo_directories`, `dates_visited`) and JSON-encoded complex pairs (`related_websites`, `additional_addresses`) safely quoted in RFC 4180 CSV cells.
3. **Security & Formula Injection Neutralization**: Prepending single-quote (`'`) to cells starting with `=`, `+`, `-`, `@`, `\t`, `\r` on export; symmetric desanitization on re-import.
4. **Intra-Batch Hierarchy Reconstruction**: UUID translation table re-linking `parent_candidate_id` and `merge_target_id` upon re-import.
5. **Dynamic Scope & State Flushing**: Auto-flushes active candidate detail editor state before export; exports all candidates by default or only checked rows if checkboxes are active.
6. **Backend Streaming Endpoint**: `GET /api/ingest/jobs/{job_id}/candidates/export` for headless, CLI, and large-batch export operations with UTF-8 BOM encoding.

---

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript 5.4+ / React 18+ (Frontend)  
**Primary Dependencies**:
- Backend: `fastapi>=0.111.0`, `pydantic>=2.8.0` (`StrictBaseModel`), `sqlalchemy>=2.0.30`, `geoalchemy2`
- Frontend: React 18, Tailwind CSS, Lucide icons
- Shared: `vistarae-core` (schema definitions, formula sanitization)

**Storage**: PostgreSQL 16+ with PostGIS 3.4+ (`ingest_candidates` table).  
**Testing**: `pytest`, `pytest-asyncio`, `pytest-cov` (Backend); Vitest / React Testing Library (Frontend).  
**Target Platform**: Modern web browsers (Chrome, Edge, Firefox, Safari) and Linux/macOS/Windows servers.  
**Project Type**: Full-stack web application feature (FastAPI backend + React frontend).  
**Performance Goals**:
- $\le 5$ seconds re-import processing of a 1,000-candidate exported CSV.
- Sub-second client-side CSV generation for standard workbench batches ($\le 2,000$ rows).
- Streaming backend export without buffering whole datasets in server memory.

**Constraints**:
- Max 2,000 rows per CSV partition; $\le 2\text{MB}$ payload per Constitution Invariant 1.
- RFC 4180 compliance with UTF-8 BOM for Microsoft Excel compatibility.
- Zero data loss across roundtrip export and re-import (100% attribute parity).
- Strict formula injection neutralization on export and clean stripping on re-import.

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle / Rule | Compliance Status | Analysis & Verification |
| :--- | :--- | :--- |
| **1. File Header & Docstrings** | **PASS** | All new/modified Python files will include the Apache 2.0 license banner and Google-style docstrings (`Args:`, `Returns:`, `Raises:`). TypeScript files will include standard JSDoc. |
| **2. Monorepo & Ports/Adapters** | **PASS** | Shared export/import schemas, DTOs, and formula sanitizers reside in `packages/core/vistarae_core/schemas/`. Ingest routes reside in `services/ingest/routes/`, services in `services/ingest/services/`. |
| **3. Database & Tenancy** | **PASS** | Candidate queries filter strictly by `user_id` and `job_id`. No cross-tenant leakage. |
| **4. Alembic & Migrations** | **PASS** | `IngestCandidateTable` already has all required columns; no new database migration required. |
| **5. API Contract & Validation** | **PASS** | Pydantic models inherit from `StrictBaseModel`. OpenAPI schemas synchronized with frontend TypeScript types. |
| **6. Middleware & Security** | **PASS** | Spreadsheet formula injection defense prepends `'` to leading formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`). Input sanitized against raw HTML. |
| **7. Observability & Logging** | **PASS** | Export requests log with W3C trace context and exact `MSG ->|` / `MSG <-|` tags. |
| **8. PyTest Coverage** | **PASS** | Comprehensive unit and integration test coverage ($\ge 90\%$) for export serializer, CSV parser, and roundtrip fidelity. |
| **Operational Invariant 1 (CSV Limits)** | **PASS** | $\le 2,000$ rows, $\le 2\text{MB}$ boundary enforced during re-import ingestion. |

---

## Project Structure

### Documentation (this feature)

```text
specs/017-export/
├── spec.md              # Feature specification in strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Architecture decisions & trade-offs (Phase 0)
├── data-model.md        # Entities, schemas & column registries (Phase 1)
├── quickstart.md        # Verification & runnable execution guide (Phase 1)
├── contracts/           # External interface contracts (Phase 1)
│   ├── export-api.md    # Streaming export endpoint specification
│   └── csv-schema.json  # Full-fidelity CSV schema specification
├── checklists/
│   ├── requirements.md  # Spec quality validation checklist
│   └── cli-extractors.md# CLI extractor interop quality checklist
└── tasks.md             # Work breakdown & dependency tasks (Phase 2)
```

### Source Code Layout

```text
packages/core/
└── vistarae_core/
    ├── schemas/
    │   └── export_schema.py             # Canonical ExportFieldDefinition, StagingCandidateExportRow, serializer
    └── services/
        └── poi_exporter.py              # Extended streaming chunk generator for staging candidates

services/ingest/
├── routes/
│   └── export.py                        # GET /api/ingest/jobs/{job_id}/candidates/export
└── services/
    └── csv_parser.py                    # Extended parser: dynamic mappings, dual-mode deserialization, formula stripping, UUID translation

frontend/
└── src/
    ├── types/
    │   └── export-schema.ts             # Canonical TypeScript candidate field registry & types
    ├── utils/
    │   └── csvExport.ts                 # Full-fidelity RFC 4180 CSV serializer with UTF-8 BOM & formula defense
    └── components/
        └── ingest/
            └── CSVImportWorkbenchModal.tsx # Updated export handler (auto-flush, scope selection, full-fidelity export)
```
