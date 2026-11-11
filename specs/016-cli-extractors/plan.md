# Implementation Plan: Unified CLI Extractors & Scraper Toolkit (016-cli-extractors)

**Branch**: `016-cli-extractors` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/016-cli-extractors/spec.md`

---

## Summary

The Unified CLI Extractors toolkit delivers a suite of modular, specialized Click-based scraping tools in `/extractor_scripts` backed by a shared framework and core schemas in `packages/core`. The toolkit extracts points of interest from 5 external directories (Hillman 1,000 Wonders, US National Park System Sites, Museum Ships, Castles of the World, and Aircraft Museums) and serializes them into RFC 4180 CSV datasets that align directly with Vistarae's Import Staging Workbench. 

The architecture guarantees:
1. Standardized CLI options (`--output`, `--limit`, `--delay`, `--deep/--shallow`, `--split-size`, `--geocode`, `--cache`, `--tag`, `--dry-run`).
2. Automatic 2,000-row file partitioning to enforce Vistarae's upload limit without manual splitting.
3. Strict spreadsheet formula injection neutralization (`=`, `+`, `-`, `@`, `\t`, `\r`).
4. Semicolon-delimited tagging with precise baseline defaults per scraper and conditional tagging.
5. Consolidated JSON-encoded `Websites` array (no dedicated URL columns) and primary address columns + JSON `Additional Address` array for multi-location attractions.
6. Offline deterministic unit testing via canned local HTML fixtures in `tests/unit/extractor_scripts/fixtures/` with $\ge 90\%$ pytest coverage.

---

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**:
- `click>=8.1.0` (CLI interface framework)
- `beautifulsoup4>=4.12.0` (HTML table/document parsing)
- `httpx>=0.27.0` (Resilient HTTP client with retry and headers)
- `pydantic>=2.8.0` (`StrictBaseModel` schemas in `vistarae-core`)
- `vistarae-core` (Monorepo core domain and validation library)

**Storage**: Local filesystem: RFC 4180 CSV export files; `.cache/extractors/` for raw HTML response caching.  
**Testing**: `pytest`, `pytest-cov`, with static HTML mock fixtures in `tests/unit/extractor_scripts/fixtures/`. Live integration tests gated behind `@pytest.mark.live_scrape`.  
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows PowerShell / Command Prompt).  
**Project Type**: CLI Toolkit / Data Extraction Utility Suite within a Python Monorepo.  
**Performance Goals**:
- $\ge 1.0$s politeness delay between remote requests to avoid throttling.
- Instant cached HTML replay ($\le 5$ms per document) for local iteration.
- Linear CSV generation streaming without unbounded memory growth.

**Constraints**:
- Max 2,000 rows per output CSV file (auto-partitioned if larger).
- Max 2MB file payload.
- No live network requests during CI / default test runs.
- Max 3 nesting levels; Cognitive Complexity $\le 15$ per function/method.
- Standardized copyright header on all `.py` files.

**Scale/Scope**: 5 specialized CLI scripts, 1 shared extractor framework, 1 core schema module, comprehensive test fixtures, ~1,500 LOC.

---

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle / Rule | Compliance Status | Analysis & Verification |
| :--- | :--- | :--- |
| **1. File Header & Pre-Commit** | **PASS** | Every new `.py` file includes the Apache 2.0 copyright header banner. Google-style docstrings with `Args:`, `Returns:`, and `Raises:` implemented for all public methods. Cognitive complexity ceiling $\le 15$ enforced. |
| **2. Monorepo & Ports/Adapters** | **PASS** | Shared DTOs (`ExtractorRecord`, `AdditionalAddressRecord`, `WebsiteRecord`) and CSV sanitization functions reside in `packages/core/vistarae_core/schemas/extractor.py`. Scraper base classes and HTTP helpers reside in `extractor_scripts/common/`. |
| **3. Database & Tenancy** | **N/A** | CLI extractors are offline harvesting tools generating importable CSV files; no direct database connection or tenancy logic required. |
| **4. Alembic & Migrations** | **N/A** | No database schema migrations required. |
| **5. API Contract & Validation** | **PASS** | Models derive from `StrictBaseModel` (`extra="forbid"`, `validate_assignment=True`, `str_strip_whitespace=True`). CLI interface contract and CSV schema formally documented in `contracts/`. |
| **6. Middleware & Security** | **PASS** | Formula injection characters neutralized at extraction time before CSV creation. No hardcoded credentials or secrets. |
| **7. Observability & Logging** | **PASS** | Extractor CLI outputs clean progress text to stdout and diagnostic warnings to stderr. |
| **8. PyTest & SDD Governance** | **PASS** | Automated test suite in `tests/unit/extractor_scripts/` mirrors production scripts 1:1. Offline execution via canned HTML fixtures ensures deterministic runs and $\ge 90\%$ branch/line test coverage. |
| **Operational Invariant 1 (CSV Limits)** | **PASS** | Automatic 2,000-row file partitioning enforces compliance with Vistarae's 2MB / 2,000-row upload limit. Formula injection neutralization enforced. |
| **Nominatim Geocoding Policy** | **PASS** | Offline-first default; optional `--geocode` flag enforces 1 req/sec rate limit and custom `User-Agent`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/016-cli-extractors/
├── spec.md              # Feature specification in strict EARS syntax
├── plan.md              # Implementation plan (this file)
├── research.md          # Architecture decisions & trade-off analysis (Phase 0)
├── data-model.md        # Domain entities, DTOs & CSV column mappings (Phase 1)
├── quickstart.md        # Verification & runnable execution guide (Phase 1)
├── contracts/           # External interface contracts (Phase 1)
│   ├── cli-interface.md # CLI arguments, options & stream specs
│   └── csv-schema.json  # Output CSV row validation schema
├── checklists/
│   └── requirements.md  # Spec quality validation checklist
└── tasks.md             # Work breakdown & dependency tasks (Phase 2, via /speckit-tasks)
```

### Source Code (repository root)

```text
packages/core/
└── vistarae_core/
    └── schemas/
        └── extractor.py                     # ExtractorRecord, AdditionalAddressRecord, WebsiteRecord, formula neutralization

extractor_scripts/
├── common/
│   ├── __init__.py                          # Package exports
│   ├── base.py                              # BaseExtractor abstract base class & Click option decorators
│   ├── http_client.py                       # ResilientHttpClient with rate limiting, caching & retries
│   ├── exporter.py                          # CSVExporter with formula defense & 2,000-row partitioning
│   ├── models.py                            # ExtractorConfig and ExtractionResult models
│   └── geo.py                               # Nominatim optional geocoding client (1 req/sec)
├── hillman_wonders.py                       # Hillman 1,000 Wonders scraper CLI
├── nps_sites.py                             # US National Park System Sites scraper CLI
├── museum_ships.py                          # Global Museum Ships scraper CLI
├── castles.py                               # Global Castles scraper CLI
└── aircraft_museums.py                      # Aircraft & Aviation Museums scraper CLI

tests/unit/extractor_scripts/
├── __init__.py
├── fixtures/                                # Canned static HTML test responses
│   ├── hillman_index.html
│   ├── hillman_detail.html
│   ├── nps_directory.html
│   ├── museum_ships_wiki.html
│   ├── castles_selection.html
│   └── aviation_museums_wiki.html
├── test_common_exporter.py                  # CSV formatting, formula defense & 2000-row chunk tests
├── test_common_http_client.py               # Rate limiting, retry & disk caching tests
├── test_hillman_wonders.py                  # Hillman Wonders parsing & tagging tests
├── test_nps_sites.py                        # NPS sites, multi-location & official designation tests
├── test_museum_ships.py                     # Museum ships, Ship/Military tagging tests
├── test_castles.py                          # Castles Fortification tagging tests
└── test_aircraft_museums.py                 # Aircraft museums tagging tests
```

**Structure Decision**:
Follows the Hybrid Monorepo Package Pattern. Domain transfer schemas and security sanitization reside within `packages/core`, while scraper base classes, utilities, and executable CLI tools reside in `/extractor_scripts`. Unit tests mirror the directory structure 1:1 inside `tests/unit/extractor_scripts/` with dedicated local test fixtures.

---

## Complexity Tracking

> **Constitution Check passed with zero violations.** No architectural exemptions or complexity trade-offs required.
