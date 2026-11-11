# Technical Research & Architecture Decisions (016-cli-extractors)

**Feature**: `016-cli-extractors`  
**Date**: 2026-11-03  
**Status**: Completed  

---

## 1. Monorepo Integration & Packaging Structure

### Context
Constitution Principle 2 mandates that all shared domain models, value objects, and schemas reside in the editable `packages/core` workspace package (`vistarae_core`), while the user request requires placing all extractor scripts into a common `/extractor_scripts` directory.

### Decision
Adopt a **Hybrid Monorepo Package Pattern**:
1. **Core Domain & Schemas** (`packages/core/vistarae_core/schemas/extractor.py`):
   - Defines `ExtractorRecord`, `AdditionalAddressRecord`, `WebsiteRecord`, and CSV sanitization functions (`neutralize_formula_injection`).
   - Backed by Pydantic v2 `StrictBaseModel` with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True` (complying with Constitution Principle 5).
2. **Extractor Framework Core** (`extractor_scripts/common/`):
   - `base.py`: Defines `BaseExtractor` abstract base class orchestrating lifecycle stages (`fetch_index`, `parse_index_entry`, `fetch_details`, `build_record`, `export`).
   - `http_client.py`: Resilient HTTP client wrapper around `httpx.Client` providing rate-limiting, custom `User-Agent: VistaraeDataExtractor/1.0`, disk caching, and exponential backoff retry.
   - `exporter.py`: RFC 4180 CSV serializer handling formula neutralization, JSON column encoding (`Websites`, `Additional Address`), and 2,000-row file chunk partitioning.
   - `geo.py`: Optional OSM Nominatim client enforcing 1 req/sec rate limit for the `--geocode` CLI flag.
3. **Specialized CLI Entrypoints** (`extractor_scripts/`):
   - `hillman_wonders.py`: Click CLI for Hillman 1,000 Wonders.
   - `nps_sites.py`: Click CLI for US National Park Service units.
   - `museum_ships.py`: Click CLI for global museum ships.
   - `castles.py`: Click CLI for global castles and fortresses.
   - `aircraft_museums.py`: Click CLI for international aviation museums.

### Rationale
- Completely adheres to Constitution Principle 2 while maintaining a modular, standalone CLI script environment in `/extractor_scripts`.
- Enables Vistarae backend services (`services/ingest`) to directly import and validate `ExtractorRecord` or CSV definitions if needed.
- Prevents duplication of CSV formula neutralization and sanitization routines across multiple scraping scripts.

### Alternatives Considered
- *Everything in `extractor_scripts`*: Rejected because it duplicates CSV schemas outside `packages/core` and prevents type-sharing across backend services.
- *Everything in `packages/core`*: Rejected because scraping scripts belong in operational tooling workspaces rather than the core domain library.

---

## 2. HTTP Politeness, Rate-Limiting & Anti-Scraping Resilience

### Context
Scraping public HTML listings (Wikipedia, Hillman Wonders, CastlesWorld) risks IP bans, HTTP 429 throttling, or silent network failures if requests are dispatched aggressively or lack polite identifying headers.

### Decision
Implement a centralized `ResilientHttpClient` in `extractor_scripts/common/http_client.py`:
1. **Polite Headers**: All outbound requests transmit `User-Agent: VistaraeDataExtractor/1.0 (Travel POI Research Engine; contact: dev@vistarae.local)` and `Accept-Language: en-US,en;q=0.9`.
2. **Domain Rate-Limiting**: Enforce a token-bucket or timestamp delay of $\ge 1.0$s between subsequent requests to the same hostname.
3. **Exponential Backoff Retry**: Catch transient network failures and HTTP 429 / 5xx codes, executing up to 3 retry attempts with exponential delays (1.0s, 2.0s, 4.0s) plus jitter.
4. **Local Response Caching**: When `--cache` is enabled, store raw HTML responses in `.cache/extractors/{domain}/{sha256_hash}.html`. Cached files are served instantly, allowing developers to iterate on parsing logic offline with zero network latency.

### Rationale
- Complies with OSM Nominatim and Wikipedia bot guidelines.
- Guarantees deterministic, reproducible scraping during offline debugging and pipeline testing.

---

## 3. CSV Schema Alignment with Vistarae Ingestion & Workbench

### Context
Vistarae's Import Staging Workbench (Feature 014/015) expects specific column headers and formats. Furthermore, user clarifications established:
1. No dedicated `Official URL` or `Wiki URL` columns; all web pages are serialized in a single JSON-encoded `Websites` column.
2. For multi-location POIs, primary location populates standard address columns, while secondary facilities are serialized into an `Additional Address` JSON column.
3. Spreadsheet formula injection (`=`, `+`, `-`, `@`, `\t`, `\r`) must be neutralized at export time.
4. CSV files must not exceed 2,000 rows to satisfy Constitution Operational Invariant 1.

### Decision
Standardize CSV output headers in `vistarae_core.schemas.extractor`:
```text
POI Name,Street Address,Town/City,State/Province,Zip Code,Country,Country Code,latitude,longitude,Tags,Hero Image URL,Websites,Additional Address,Estimated Visit Hours,Itinerary Days,Description,Reason to Visit,Photo Directory,Dates Visited
```

1. **`Websites` JSON Encoding**:
   Serialized as:
   `[{"name": "Official Website", "url": "https://..."}, {"name": "Wikipedia", "url": "https://..."}]`
2. **`Additional Address` JSON Encoding**:
   Serialized as:
   `[{"street_address": "...", "town_city": "...", "state_province": "...", "zip_code": "...", "country": "...", "latitude": 44.1, "longitude": -110.6}]`
3. **Formula Neutralization**:
   Any cell value starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is automatically prepended with a single quote (`'`).
4. **Automatic Partitioning**:
   If extracted rows $> 2000$ (or if `--split-size` is set), the exporter automatically writes `output_part1.csv`, `output_part2.csv`, ensuring each file satisfies Vistarae's upload limit.

---

## 4. Multi-Tier Extractor Tagging Model

### Context
User clarifications mandated precise tagging rules for each extractor script, forbidding extra speculative classification tags while preserving the ability for future scripts and CLI operators to extend tags.

### Decision
Implement three-tier tag resolution in `BaseExtractor`:
1. **Tier 1 - Script Baseline Default Tag**:
   - `Hillman Wonders`: None (do not assign base `Wonder` tag).
   - `NPS Sites`: `NPS`.
   - `Aircraft Museums`: `Aircraft` (omit collection focus tags).
   - `Castles`: `Fortification` (omit architectural classification tags).
   - `Museum Ships`: `Ship` (omit naval classification tags).
2. **Tier 2 - Conditional Tagging**:
   - `Hillman Wonders`: `HillmanWonder:Gold`, `HillmanWonder:Silver`, or `HillmanWonder:Bronze` based on wonder tier.
   - `NPS Sites`: Official Designation (e.g. `National Park`, `National Historic Site`, `National Battlefield`, `National Monument`).
   - `Museum Ships`: `Military` if the vessel is a warship.
3. **Tier 3 - Operator CLI Tags (`--tag`)**:
   - Any CLI execution can accept `--tag <tag>` repeatedly to append user-defined tags to all records in that run.

All tags are deduplicated, sorted, and joined with semicolons: `Tag1; Tag2; Tag3`.

---

## 5. Testing & CI Determinism Strategy

### Context
Constitution Principle 8 strictly mandates $\ge 90\%$ test coverage in pytest and reproducible CI execution without flaky external dependencies.

### Decision
1. **Local Canned HTML Fixtures**:
   Store realistic HTML snapshots in `tests/unit/extractor_scripts/fixtures/`:
   - `hillman_index.html`, `hillman_detail.html`
   - `nps_directory.html`
   - `museum_ships_wiki.html`
   - `castles_selection.html`
   - `aviation_museums_wiki.html`
2. **Mocked HTTP Transports**:
   Unit tests use `unittest.mock` or `httpx.MockTransport` to intercept outbound HTTP calls and return canned HTML fixtures, validating 100% of HTML parsing, tag resolution, address splitting, and CSV output logic deterministically.
3. **Live Network Marker**:
   Any test issuing live requests against public websites is marked with `@pytest.mark.live_scrape` and skipped by default in local runs and CI.

