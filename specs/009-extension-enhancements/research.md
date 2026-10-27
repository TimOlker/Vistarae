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

# Phase 0 Research: Extension Enhancements, Tag Governance & Multi-Source Scraping

**Feature**: `009-extension-enhancements`  
**Date**: 2026-10-22  
**Status**: Completed

---

## 1. Technical Decisions & Research Matrix

### Decision 1: Tag Taxonomy Storage, Slugification & Alias Mapping

- **Context**: The user requires a controlled, user-scoped tag library displayed alphabetically on the Web App Preferences page (`/settings`). Each tag must be stored as an immutable slugified ID (e.g. `fortification`, `museum_ship`) with display name and search alias terms (e.g. `["castle", "fort", "citadel"]` mapped to `fortification`). Deletion must be blocked if the tag is referenced by any POIs.
- **Decision**: Update `TagTable` in `packages/core/vistarae_core/adapters/db/tables.py` to add `slug: Mapped[str] = mapped_column(String(64), nullable=False)` and `aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))`. Add a unique constraint `UniqueConstraint("user_id", "slug", name="uq_tags_user_slug")`.
- **Slug Generation**: Lowercase alphanumeric with underscores `re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')`.
- **Alias Handling**: Aliases are stored as an array of lowercase trimmed strings. Per User Clarification Q2, overlapping aliases across different tags of the same user are explicitly permitted; if scraped content matches an overlapping alias, the system recommends all candidate tags for manual confirmation.
- **Deletion Protection**: When `DELETE /api/pois/tags/{tag_id}` is invoked, the repository checks `SELECT COUNT(*) FROM poi_tags WHERE tag_id = :tag_id`. If `count > 0`, the service raises a `TagInUseError`, returning RFC 7807 409 Conflict with the count and an actionable remediation link.
- **Seeding 30 Default Tags**: A domain service `seed_default_tags(user_id, session)` is executed on user creation and during migration, inserting the 30 standardized default tags (`ON CONFLICT (user_id, slug) DO NOTHING`).
- **Alternatives Considered**:
  - _Storing tags as freeform text strings in a JSONB array on POIs_: Rejected because it leads to fragmentation, duplicate variations ("castle", "Castle", "Castles"), and makes global tag management and renaming impossible.
  - _Global system-wide tags table_: Rejected because the specification mandates each user define their own list independent of other users.

---

### Decision 2: Secondary Scraping Sources Storage & Configuration

- **Context**: The user needs a configurable list of valid domains to extract secondary information from when the active webpage lacks necessary data. Each user can configure their own list in Web App Preferences, and the list must be made available to the extension via an authenticated API call.
- **Decision**: Add `valid_scraping_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[\"wikipedia.org\", \"tripadvisor.com\", \"atlasobscura.com\", \"google.com/maps\", \"roadtrippers.com\"]'::jsonb"))` to the existing `user_preferences` table via Alembic migration `0007_tag_governance_and_scraping_preferences.py`.
- **API Surface**: Expose `GET /api/user/preferences/scraping-sources` and `PUT /api/user/preferences/scraping-sources` within the existing user preferences router.
- **Extension Caching**: The Chrome Extension queries this endpoint upon initialization and caches the list in `chrome.storage.local` with a 24-hour TTL, updating whenever the user visits the preferences page or triggers a manual sync.
- **Alternatives Considered**:
  - _Dedicated `user_scraping_sources` table_: Evaluated in Clarification Q1 and rejected by the user in favor of extending `user_preferences` to reduce relational overhead and simplify atomic preference updates.
  - _Client-only `chrome.storage.sync`_: Rejected because it fails to synchronize with backend scraping tasks or across browser profiles.

---

### Decision 3: Multi-Source Scraping Orchestration & Graceful Degradation

- **Context**: When `Ctrl+Shift+S` is pressed, the extension extracts primary page text and passes it to `/api/pois/extract-and-check`. If required fields (coordinates, address, duration, official site, Wikipedia link) are missing, the backend queries authorized secondary sources.
- **Decision**: Implement a modular `ScrapingOrchestrator` in `services/poi/scraping/orchestrator.py`:
  1. **Primary Extraction**: Extracts page title, selection, OpenGraph tags (`og:title`, `og:image`, `og:description`), JSON-LD schema (`Place`, `TouristAttraction`, `CivicStructure`), and canonical URL.
  2. **Name Determination & English Normalization**: Normalizes the destination name to standard English using `google-genai` SDK (`gemini-2.0-flash-lite`, `thinking_budget = 0`).
  3. **Secondary Source Augmentation**: Checks `user_preferences.valid_scraping_domains`. If `wikipedia.org` is authorized, queries the Wikipedia REST API (`/api/rest_v1/page/summary/{title}`) to retrieve coordinates, extract summary, hero thumbnail, and Wikidata ID. If `tripadvisor.com` or other sources are authorized, queries available search/summary endpoints.
  4. **Timeout & Partial Fallback Policy**: Every secondary HTTP request is bounded by a strict `asyncio.wait_for(timeout=3.0)` ceiling. If any secondary source times out or returns HTTP 429/403, the orchestrator catches the exception, logs `MSG <-| Scraping source failed`, and continues with primary data (Clarification Q3).
  5. **Tight Summary Synthesis**: Invokes Gemini Flash-Lite with structured output enforcing `POIExtractionPayload` to distill multi-source content into a concise 2–3 sentence description.
- **Alternatives Considered**:
  - _Full headless browser (Playwright/Puppeteer) on backend_: Rejected due to AWS Lambda 250MB deployment size limit, high cold-start latency (3–5s), and constitutional zero-cost architecture principles. Direct lightweight HTTP APIs (`httpx.AsyncClient`) are fast (< 400ms) and stateless.

---

### Decision 4: Intelligent Geocoding, Boundary-Aware Addressing & PostGIS Cache

- **Context**: Lat/long and address resolution must respect OpenStreetMap Nominatim's strict usage policy (1 req/sec max, custom `User-Agent: VistaraeTravelEngine/1.0`, internal cache lookup prior to outbound calls). Trans-boundary landmarks (e.g. Yellowstone across WY/MT/ID or Iguazu Falls across Argentina/Brazil) require multiple address entries.
- **Decision**:
  - **Cache Lookup**: Before any outbound geocode, compute SHA-256 of the normalized address or coordinate pair (`f"{lat:.5f},{lon:.5f}"`) and query `geocoding_cache` (Constitutional Invariant 3).
  - **Rate Limiting**: Enforce a backend token-bucket rate limiter ensuring at least 1,000ms between consecutive outbound Nominatim calls.
  - **Boundary Spanning**: If reverse geocoding returns multiple administrative parent polygons, or if Gemini identifies multi-state/multi-country boundaries, generate distinct `AddressRecord` items in the `addresses` JSONB array.
  - **English Country Standardization**: Normalize country names to ISO 3166-1 alpha-3 and English common names via `pycountry` or internal ISO mapping, matching Phase 7 (`007-ui-edit-poi-enhancements`).
- **Alternatives Considered**:
  - _Google Maps Geocoding API_: Rejected due to commercial API costs violating the project's zero-cost architectural guardrails.

---

### Decision 5: Scale-Aware Duplicate & Parent-Child Nesting Triage

- **Context**: Early triage must distinguish between an accidental duplicate and a sub-attraction located within a larger entity (e.g., "Cloud Gate" inside "Millennium Park").
- **Decision**:
  - **Spatial Footprint Scale Classification**: Heuristic scale tagging:
    - `Macro` (National/State Park, Mountain Range, Forest): spatial radius $5,000$m.
    - `Medium` (Museum, Zoo, Theme Park, Architectural Campus): spatial radius $500$m.
    - `Micro` (Sculpture, Monument, Room, Exhibit, Plaque): spatial radius $50$m.
  - **Dual-Threshold Classification (Clarification Q5)**:
    - `POTENTIAL_DUPLICATE`: Distance $\le$ scale-adjusted radius AND Trigram Similarity $\ge 0.60$. UI highlights "Proceed" or "Abort".
    - `NEARBY_PARENT`: Distance $\le$ scale-adjusted radius AND Trigram Similarity $< 0.60$ AND existing candidate has a larger spatial footprint scale (Macro/Medium vs. Micro). UI highlights "Make Child".
    - `UNIQUE_LOCATION`: No matches within scale-adjusted radius.
  - **Triage Action Execution**:
    - "Proceed": Saves as independent root POI.
    - "Make Child": Sets `parent_poi_id = existing_poi.id` and `parent_poi_name = existing_poi.name`.
    - "Abort": Closes overlay and discards in-memory draft.

---

### Decision 6: Extension UI Streamlining & Authentication Safeguards

- **Context**: The extension currently displays a redundant POI table, search bar, CSV export, and demo placeholder destinations. The keystroke capture must verify authentication before initiating capture.
- **Decision**:
  - **Remove Redundant UI**: Deprecate and remove `#btn-export-csv`, `#poi-tbody`, `#input-search`, and category filters from `extension/browser/browser.html` and `browser.js`.
  - **Branded Overview**: Replace `browser.html` with an informational landing hub displaying:
    - User account badge (`Signed in as: <email>`)
    - Keystroke cheat sheet (`Ctrl+Shift+S` on Windows/Linux; `Cmd+Shift+S` on Mac)
    - Active server connectivity indicator (`Connected to http://localhost:8000` / production gateway)
    - Direct "Open Vistarae Web App" action button linking to `http://localhost:5173` or CloudFront production origin.
  - **Demo Data Purge**: Completely delete fake fallback items (`Glacier Point Overlook`, `Mist Trail`) from `browser.js`.
  - **Authentication Gate**: `service_worker.js` checks `getValidAccessToken()`. If null or expired, opens `https://app.vistarae.com/login?return_to=extension` and broadcasts an auth challenge without injecting the capture overlay.

---

## 2. Constitutional Verification Matrix

| Constitutional Rule                     | Compliance Status | Implementation Strategy                                                                                                |
| :-------------------------------------- | :---------------: | :--------------------------------------------------------------------------------------------------------------------- |
| **1. Copyright Headers & Pre-Commit**   |       PASS        | Standard Apache-2.0 header on all `.py`, `.ts`, `.tsx`, and `.sql` files. Cognitive complexity $\le 15$.               |
| **2. Ports & Adapters Architecture**    |       PASS        | Domain models and interfaces in `packages/core/vistarae_core/`. No AWS SDK or HTTP imports in domain layer.            |
| **3. Tenancy Invariants (No RLS)**      |       PASS        | `WHERE user_id = :current_user_id` enforced on all tag and preference lookups. Zero PostgreSQL RLS used.               |
| **4. Alembic & Environment Isolation**  |       PASS        | Migration `0007_tag_governance_and_scraping_preferences.py` implements reversible `downgrade()`. Zero native DB ENUMs. |
| **5. API Contract & Pydantic v2**       |       PASS        | All payloads use `StrictBaseModel` with `extra="forbid"`. Non-2XX responses use RFC 7807 `ProblemDetails`.             |
| **6. Middleware & Security Guardrails** |       PASS        | Extension origin whitelisted in `CORSMiddleware`. Idempotency and rate-limiting middleware configured.                 |
| **7. Observability & Tracing**          |       PASS        | Standard W3C `traceparent` headers sent by extension; directional `MSG ->\|` logging in local development.             |
| **8. PyTest Governance (90% Coverage)** |       PASS        | Full test suite mirroring in `tests/unit/services/poi/` and `tests/unit/packages/core/` with `--cov-fail-under=90`.    |
