# Feature Specification: Phase 9 — Extension Enhancements & Web App Tag Management (Tag Governance, Rich Web Scraping & Multi-Source Augmentation, Duplicate Triage)

**Feature Identifier**: `009-extension-enhancements`  
**Feature Branch**: `009-extension-enhancements`  
**Created**: 2026-10-22  
**Status**: Approved  
**Target Systems**:

- **Web App Tag Governance & Preferences**: `frontend/src/pages/SettingsPage.tsx`, `frontend/src/components/tags/TagManager.tsx`, `frontend/src/context/PreferencesContext.tsx`
- **Web App POI Synchronization**: `frontend/src/components/poi/POIEditDrawer.tsx`, `frontend/src/components/poi/POITable.tsx`
- **Chrome Extension UI & Architecture**: `extension/manifest.json`, `extension/browser/browser.html`, `extension/browser/browser.js`, `extension/browser/browser.css`, `extension/content/content_script.js`, `extension/content/overlay.css`, `extension/background/service_worker.js`, `extension/background/auth.js`
- **Scraping & Augmentation Backend Services**: `services/poi/` (`/api/pois/extract-and-check`, `/api/pois/tags`, `/api/pois/tags/{tag_id}`, `/api/user/preferences/scraping-sources`), `services/poi/scraping/` (Multi-source orchestrator, Wikipedia/TripAdvisor adapter, Gemini summary synthesizer), `packages/core/vistarae_core/` (Tag domain entities, slugification/alias value objects, extraction schemas, spatial scale classifier)
- **Database & Persistence**: PostgreSQL 16+ / PostGIS / Alembic migration `0007_tag_governance_and_scraping_preferences.py` adding `valid_scraping_domains` JSONB array column to `user_preferences` table, updating `tags` table with `slug` (unique per user) and `aliases` (`list[str]`), and enforcing referential integrity preventing deletion of referenced tags.

**Input**: User description:

> "/speckit.specify Create the specification for Phase 9 (009-extension-enhancements) using strict EARS syntax.
> 
> Scope to cover webapp enhancements:
> 1. Web App Tag Management - avoid having an extensive set of unmanageable tags associated with a POI
>    - each user should be able to define their own list of what Tags they want to capture independent of other users.
>    - the list should be displayed in alphabetical order in the web app in the user's preferences page.
>    - the user should be able to add new Tags
>    - the user should be able to remove a Tag, but first the Tag must be removed from all POIs before allowing this to happen.
>    - Store each tag as a slugified ID (e.g., fortification, museum_ship) and map natural search terms as aliases (castle -> fortification, submarine -> museum_ship) so search remains flexible without fragmenting your database. 
>    - a default list of Tags should be provided, but the user can override. The list includes:
>       - Fortification, Landmark, Ship, Aircraft, Military, Rail, Historic, Memorial, Building, Church, Temple, Museum, Scenic, Waterfall, Water, Park, Wilderness, Coast, Mountain, Food, NPS, UNESCO, Culture, Lighthouse, Zoo, Animal, Shopping, Entertainment, Film Location, Humorous
> 
> Scope to cover extension enhancements:
> 2. Extension POI List
>    - if no data is found, do not display demo samples.
> 
> 3. Display currently logged in user for the extension
>    - Before allowing the key stroke to save a POI, continue to confirm that the user is logged in, if not direct to login.
>    - If logged in, ensure the user is displayed.
> 
> 4. Remove extension functionality
>    - currently an export CSV option is displayed. This is redundant duplication of what is done on the web app and should be removed.
>    - currently a list of POIs is displayed. This is redundant duplication of what is done on the web app and should be removed.
>    - the list of POIs should be replaced with a brief summary of what Vistarae, and more specifically the extension does.
> 
> 5. Extension - Web scraping fields
>    - when the key stroke is provided the logic to scrape information from the currently selected page is triggered.
>    - the design should be updated to make sure the fields in the DB / fields on the POI edit are synchronized with the fields that can be populated when capturing a POI.
>    - make sure there are inputs that make sure it is aligned with the web apps edit POI page.
> 
> 6. Extension - Web scraping logic
>    - first run the logic to determine the name. The POI name should be the english version of a POI. A normalization of location names should be applied to standardized POI names.  
>    - if the page does not have the information needed to scrape data, attempt to look to other sources to scrape data from. For example wikipedia entry, a tripadvisor or other well regarded sites could be used. For each POI please record which sites were used to extract information from. If no information is found, leave the field blank. The list of valid sites to extract information from should be configurable on the web app in the user's preferences. This list is then made available to the extension by an API call for an authorized user. Each user can have their own list. They should be able to add/remove/edit which sites are on the list.
>    - attempt to determine the location's lat & long. If it can not be determined from the sources, but an address is available, check the cache and if no hit then attempt to query a geocoding service to map.
>    - attempt to determine the location's address. If not present, attempt to geocode an address from the lat & long. Note there may be multiple addresses, or a larger location that is a region may not have a specific street address and only have a city, state/province and country. Alternatively a larger location may not have a town/city or state/province. Some may span multiple town/city, state/province, country, in which case create multiple address entries. Locations should be standardized to english versions of location names, and normalized into the standardized format. (for example if a country standard hasn't been selected, use an open source distribution of ISO 3166-1).
>    - save the location that was scraped into the source data and set the source type to the enumerated value that it came from the web scraping.
>    - if the POI's official website can be determined, populate that field
>    - if the POI's wikipedia page can be determined, populate that field
>    - if a default image can be determined for the POI please populate it.
>    - attempt to determine the number of hours or days required to visit a location by looking at the source page, and then looking at the extra sources of information configured by the user.
>    - a representative image url for the POI should be attempted to be detected for the POI.
>    - from the web app the user's preferred list of POI Tags should be retrieved. If the tags match the site they should be presented to the user, but an option should be given to the user to deselect a recommended tag, or to add a tag that web scraping logic did not determine to be associated with the POI. Only tags that match a user's preferred tags should be used (retrieve and then cache the user's list of valid tags they want to use). The goal is to avoid a massive number of non-standardized tags, so only use tags the user has vetted out.
>    - if information is rate limited, or charged for access, it should be cached to prevent accessing that resource multiple times.
>    - other fields should be attempted to be determined as needed.
>    - the user should be responsible for assigning a star rating when web scraping
>    - the local photo folder field should not be populated when web scraping.
>    - the information from the different found websites should attempt to be summarized into a tight summary.
>    - attempt to determine if the location is a duplicate of an existing POI in Vistarae as early as possible in this process. If it is a duplicate, prompt the user to see if they want to proceed. Or to make this a child entry of the found location. or to abort the process and not create the POI. When determining a duplicate entry, attempt to determine the size of the location. For example, Yellowstone national park spans multiple states and is very large. But the chicago art institute is only a couple of blocks away. A particular sculpture in the art institute is only a couple of feet of space. If making a child of another POI, make sure the parent POI name and parent POI ID are inserted into the DB."

---

## 1. Executive Summary & Context

Phase 9 (`009-extension-enhancements`) establishes a unified, high-integrity capture workflow connecting the Vistarae Chrome Extension (Manifest V3) with the Vistarae Web Application and core geospatial backend. In previous releases, the extension contained redundant tabular UI and disconnected mock datasets while POI tags suffered from unconstrained user fragmentation. Phase 9 refactors the extension into a dedicated, authenticated capture companion backed by robust tag governance and automated multi-source enrichment.

The feature delivers six cohesive capability pillars:

1. **User-Scoped Tag Governance & Alias Normalization (Web App & Backend)**:
   - Eliminates database tag fragmentation by introducing controlled user tag libraries managed within the Web App Preferences page (`/settings`).
   - Every tag is identified by an immutable slugified ID (e.g. `fortification`, `museum_ship`) and associated with a human-readable display name and an array of alias terms (e.g. `["castle", "fort", "citadel"]` mapped to `fortification`).
   - Tags are rendered in strict alphabetical order.
   - Deletion protection enforces referential integrity: a user cannot delete a tag until it has been removed from all POIs in their library. The Web App provides a direct remediation link to view affected POIs in the table for instant batch removal.
   - Seeds 30 standardized default tags upon user registration, which users can customize, extend, or alias.

2. **Extension Streamlining & Informational Overhaul**:
   - Removes redundant features from the extension: the CSV export button, full POI table, search toolbar, and category filters are eliminated in favor of the full Web App.
   - Removes all hardcoded demo fallback records (`Glacier Point Overlook`, `Mist Trail`), ensuring that offline or empty states never display fake travel data.
   - Replaces the extension browser tab/popup with a polished, branded landing dashboard summarizing Vistarae's mission, explaining the capture keystroke (`Ctrl+Shift+S` / `Cmd+Shift+S`), displaying active system health, and linking directly to the Web App.

3. **Strict Authentication Gate & Identity Context**:
   - Enforces pre-capture authentication: pressing `Ctrl+Shift+S` or invoking the capture menu verifies active Cognito tokens.
   - If unauthenticated, the extension immediately halts capture and directs the traveler to the Web App login page with a return redirect.
   - If authenticated, the extension prominently displays the logged-in user's email/display name in both the extension overview and the Shadow DOM capture overlay.

4. **1:1 Field Parity Across Extension, Web App, and Database**:
   - Updates the capture overlay inputs to mirror the fields present in the database and the Web App POI Editor:
     - Standardized English POI Name
     - Multiline Freeform Description / Synthesized Summary
     - Multi-Address Support (Street, City/Town, State/Province, Country [ISO 3166-1], Postal Code)
     - Geospatial Coordinates (Latitude, Longitude)
     - Official Website URL & Wikipedia Article URL
     - Representative Hero Image URL
     - Estimated Visit Duration (Decimal Hours and Integer Days)
     - User Star Rating (0 to 5 stars, explicitly assigned by the user; never automated)
     - Provenance Source (`source_type = "Web"`, `source_value = <page_url>`)
     - Extraction Provenance (`extraction_sources = ["<domain1>", "<domain2>", ...]`)
     - Hierarchical Parent POI (`parent_poi_id`, `parent_poi_name`)
     - Vetted User Tags (pre-selected from recommendations with manual toggle)
   - Guarantees that local photo folder paths are strictly excluded and never populated during web scraping.

5. **Multi-Source Scraping, English Normalization & Intelligent Geocoding**:
   - When a capture is initiated, the scraping engine extracts primary page metadata and determines the standardized English name.
   - If critical information is missing, the engine queries authorized secondary sources (e.g., Wikipedia API, TripAdvisor) configured in the user's preferences (`valid_scraping_domains`), recording each source domain used.
   - If secondary sources fail, timeout, or hit rate limits, the system executes a graceful partial fallback, returning primary page data without blocking.
   - Coordinates and addresses are resolved via a multi-tier pipeline: source extraction -> PostGIS `geocoding_cache` table (SHA256 lookup) -> rate-limited OpenStreetMap Nominatim geocoding (1 req/sec with custom `User-Agent: VistaraeTravelEngine/1.0`). Reverse geocoding resolves addresses from coordinates when street data is omitted.
   - Spanning entities (e.g. parks or waterfalls crossing state or national boundaries) generate multiple normalized address records.
   - Information from multiple sources is distilled into a tight, cohesive summary via Gemini Flash-Lite (`thinking_budget = 0`).

6. **Scale-Aware Early Duplicate & Nesting Triage**:
   - Evaluates the spatial footprint and physical scale of the destination (e.g., vast national parks vs. multi-block museums vs. discrete monuments or exhibits).
   - Queries PostGIS spatial indexes and pg_trgm similarity early during page analysis.
   - Employs a dual-threshold heuristic: classifies as `POTENTIAL_DUPLICATE` if distance $\le$ scale-adjusted radius AND trigram similarity $\ge 0.60$; classifies as `NEARBY_PARENT` if distance $\le$ scale-adjusted radius AND similarity $< 0.60$ with the existing POI having a larger scale footprint.
   - The capture overlay presents the traveler with three explicit actions:
     1. **Proceed**: Save as an independent POI.
     2. **Make Child**: Nest under the discovered parent (persisting `parent_poi_id` and `parent_poi_name`).
     3. **Abort**: Cancel the capture without persisting any records.

---

## 2. Clarifications

### Session 2026-10-22

- Q: Where should the traveler's custom list of authorized secondary scraping domains be persisted and managed? (REQ-EXT-019) → A: Add a `valid_scraping_domains` JSONB array column to the existing `user_preferences` table, initialized with default domains (`['wikipedia.org', 'tripadvisor.com', 'atlasobscura.com', 'google.com/maps', 'roadtrippers.com']`) and managed via the existing preferences API.
- Q: When a user configures aliases for a tag, how strictly should the system enforce alias uniqueness across that user's tag library? (REQ-EXT-004) → A: Allow overlapping aliases across different tags. If a scraped page matches an overlapping alias, the system recommends all matching candidate tags for manual confirmation in the capture overlay.
- Q: If secondary scraping sources fail, timeout, or return rate-limit errors during capture, how should the extraction pipeline handle the failure? (REQ-EXT-018) → A: Graceful partial fallback. Return primary page data immediately without blocking, leave unretrieved secondary fields blank, and display an informational banner in the overlay ("Secondary sources unavailable; primary data captured").
- Q: When a user attempts to delete a tag that is still assigned to POIs, how should the Web App guide the user to remove the tag? (REQ-EXT-006) → A: Conflict modal with direct filter link. Block deletion (RFC 7807 409 Conflict) and display a button "View Affected POIs in Table", pre-filtering the POI table to that tag so the user can bulk-remove it via Phase 8 bulk edit.
- Q: How should the early triage engine distinguish between a potential duplicate versus a parent-child nesting candidate? (REQ-EXT-029) → A: Dual-threshold heuristic combining spatial scale and name similarity: classify as `POTENTIAL_DUPLICATE` if distance $\le$ scale radius AND name similarity $\ge 0.60$ (recommending Abort/Proceed); classify as `NEARBY_PARENT` if distance $\le$ scale radius AND name similarity $< 0.60$ with existing POI at larger scale (recommending "Make Child").

---

## 3. User Scenarios & Testing _(mandatory)_

### User Story 1 - Web App Tag Management & Vetted Tag Governance (Priority: P1) 🎯 MVP

A traveler wants to organize their saved destinations without accumulating hundreds of inconsistent, messy tags (e.g., "castles", "Castle", "forts", "chateaux"). In the Web App, they navigate to Preferences (`/settings`) and click the **Tags** tab. They see a clean, alphabetically sorted list of 30 standard default tags (Aircraft, Animal, Building, Church, Coast, Culture, Entertainment, Film Location, Food, Fortification, Historic, Humorous, Landmark, Lighthouse, Memorial, Military, Mountain, Museum, NPS, Park, Rail, Scenic, Ship, Shopping, Temple, UNESCO, Water, Waterfall, Wilderness, Zoo). 

The traveler notices `Fortification` has aliases `castle`, `fort`, `citadel`. They also add `fort` as an alias on `Military`. They add a new custom tag with display name `Historic Railway`, slug `historic_railway`, and aliases `steam train`, `cog railway`, `funicular`. Later, when attempting to delete `Historic`, the system detects that 12 POIs currently use `Historic` and blocks deletion, returning a 409 Conflict modal with a button: "View 12 Affected POIs in Table". Clicking the button takes them to the main POI table pre-filtered by `Historic`, where they use bulk edit to remove the tag, and then successfully delete `Historic`.

**Why this priority**: Foundational data integrity. Without controlled, alias-mapped tag taxonomies, downstream search, filtering, and extension tagging become chaotic and fragmented.

**Independent Test**: Navigate to `/settings` -> Tags tab, verify 30 seeded tags render in alphabetical order, create a new tag with aliases, verify slugification, assign to a test POI, attempt deletion (verify 409 error modal with table filter button), remove tag from test POI, and delete tag (verify success).

**Acceptance Scenarios**:

1. **Given** an authenticated user on `/settings`, **When** the user selects the Tags tab, **Then** all user tags are displayed in strict ascending alphabetical order by display name.
2. **Given** the tag management interface, **When** the user inputs a name "Museum Ship" and aliases "submarine, warship, battleship", **Then** the system creates a tag with slug `museum_ship` and associated normalized aliases under the user's account.
3. **Given** an existing tag assigned to 3 POIs, **When** the user clicks "Delete Tag", **Then** the system rejects deletion (RFC 7807 409 Conflict) and renders a modal: "Cannot delete tag: currently used by 3 POIs. [View 3 Affected POIs in Table]".
4. **Given** a tag assigned to 0 POIs, **When** the user clicks "Delete Tag" and confirms, **Then** the tag is permanently deleted from the user's library.
5. **Given** a newly registered user, **When** their account is provisioned, **Then** the system automatically seeds the 30 standardized default travel tags into their library.

---

### User Story 2 - Extension Streamlining & Authenticated User Context (Priority: P1) 🎯 MVP

A traveler clicks the Vistarae Chrome Extension toolbar icon or opens its extension page. Instead of viewing a duplicate, clunky copy of the POI table with fake demo items ("Glacier Point Overlook", "Mist Trail") and an export CSV button, they are greeted by an elegant, focused Vistarae Extension Companion dashboard. 

The dashboard prominently displays their authenticated profile banner (`Signed in as: alex.traveler@example.com`), active backend connectivity status, a visual cheat sheet explaining how to capture destinations using `Ctrl+Shift+S` (or `Cmd+Shift+S` on Mac), and a direct button "Open Vistarae Web App" linking to the main discovery canvas. If the traveler is logged out, the dashboard clearly states "Session Expired / Not Logged In" with a prominent "Log In with Vistarae" button, and disables capture hotkeys until authenticated.

**Why this priority**: Eliminates confusing redundancy between extension and webapp, establishes secure identity context, and prevents user confusion from fake placeholder data.

**Independent Test**: Load the extension without an active session (verify login prompt appears and capture keystroke opens login), authenticate via Web App, re-open extension (verify user email is displayed, no demo POIs appear, no CSV export button exists, and overview guide is visible).

**Acceptance Scenarios**:

1. **Given** an unauthenticated browser session, **When** the user presses `Ctrl+Shift+S`, **Then** the extension prevents capture and directs the active tab to the Vistarae Web App login page with a return redirect parameter.
2. **Given** an authenticated user, **When** the user opens the extension companion page, **Then** the top banner displays the user's verified email and authentication state badge.
3. **Given** the extension companion page, **When** rendered, **Then** no POI table, search toolbar, category filter, or "Export to CSV" buttons exist in the DOM.
4. **Given** the extension companion page, **When** rendered, **Then** no mock or demo records (e.g. Glacier Point Overlook) are rendered under any offline or empty state.
5. **Given** the extension companion page, **When** the user clicks "Open Vistarae Web App", **Then** the browser navigates to the web app dashboard in a new or focused tab.

---

### User Story 3 - Full-Spectrum Synchronized Web Scraping & Multi-Source Augmentation (Priority: P1)

A traveler is browsing a travel blog article discussing the "Bamburgh Castle" on the Northumberland coast. They highlight the name and press `Ctrl+Shift+S`. The extension triggers its isolated Shadow DOM overlay. 

The extension first extracts the primary page data, normalizing the name to standardized English ("Bamburgh Castle"). Because the blog article lacks physical address details and estimated duration, the backend scraping engine queries authorized secondary sources from the user's preferences (such as the English Wikipedia entry and TripAdvisor summary). 

The system extracts the official website (`https://www.bamburghcastle.com`), Wikipedia article (`https://en.wikipedia.org/wiki/Bamburgh_Castle`), hero image URL, and estimates visit duration as 3.5 hours (0 days). It distills the combined text into a tight, two-sentence summary. If secondary sources fail or timeout (> 3.0s), the system performs a graceful partial fallback, displaying a soft notice without aborting capture. Because the text matches the alias "fort", which belongs to both `Fortification` and `Military`, the capture overlay recommends both tags with opt-out badges. The star rating is left blank for the traveler to evaluate. Local photo folders remain completely unpopulated. The traveler adjusts the rating to 5 stars and clicks "Save to Vistarae".

**Why this priority**: Core value proposition of the extension. Provides frictionless, high-fidelity capture with automated enrichment while keeping human travelers in control of ratings and tags.

**Independent Test**: On a third-party webpage, press `Ctrl+Shift+S`, observe Shadow DOM overlay populate with standardized English name, synthesized summary, official URL, Wikipedia URL, hero image thumbnail, estimated hours/days, and recommended vetted tags. Assert star rating is empty, local photo folder is null/absent, and simulate secondary timeout to verify graceful partial fallback.

**Acceptance Scenarios**:

1. **Given** a webpage with an active selection, **When** the user presses `Ctrl+Shift+S`, **Then** the scraping pipeline determines the standardized English location name as the primary entity identifier.
2. **Given** missing coordinates or address on the primary page, **When** secondary augmentation executes, **Then** the backend queries only the domains present in `user_preferences.valid_scraping_domains` and records them in `extraction_sources`.
3. **Given** secondary sources timeout (> 3.0s) or return HTTP 429/403, **When** extraction completes, **Then** the system returns primary page data without blocking and displays an informational banner: "Secondary sources unavailable; primary data captured".
4. **Given** tag extraction, **When** page content matches an alias shared across multiple tags (e.g. "fort"), **Then** all matching candidate tags (`Fortification`, `Military`) are recommended with toggle badges, and only tags belonging to the user's vetted preferences can be selected.
5. **Given** any web scraping capture, **When** the form initializes, **Then** the star rating input requires manual traveler selection and the local photo folder field is excluded.

---

### User Story 4 - Intelligent Geocoding, Boundary-Aware Addressing & Rate-Limit Caching (Priority: P2)

A traveler captures "Iguazu Falls" from an international travel portal. The falls span both Argentina (Misiones Province) and Brazil (Paraná State) and lack a traditional street number. 

The scraping engine extracts latitude `-25.6953` and longitude `-54.4367`. The geocoding subsystem first checks the local PostGIS `geocoding_cache` table by SHA256 query hash. On cache miss, it executes a rate-limited query to OSM Nominatim (adhering strictly to 1 req/sec with `User-Agent: VistaraeTravelEngine/1.0`). Detecting that the geographic boundary spans two countries, the engine produces two structured address records: Address 1 (`Puerto Iguazú, Misiones, Argentina`, ISO `ARG`) and Address 2 (`Foz do Iguaçu, Paraná, Brazil`, ISO `BRA`). Subsequent requests for Iguazu Falls hit the internal `geocoding_cache` without invoking Nominatim.

**Why this priority**: Prevents geocoding failures on complex natural attractions and respects external API rate limits and terms of service.

**Independent Test**: Trigger capture for a multi-state or multi-country POI (e.g. Yellowstone National Park or Iguazu Falls), verify multiple address entries are created with English normalized countries (ISO 3166-1), verify the SHA256 cache entry is written to `geocoding_cache`, and assert subsequent captures reuse cache without HTTP calls.

**Acceptance Scenarios**:

1. **Given** a captured POI with coordinates but no street address, **When** geocoding executes, **Then** the system queries the internal PostGIS `geocoding_cache` table before making any outbound network requests.
2. **Given** a geocache miss, **When** querying OSM Nominatim, **Then** outbound calls are throttled to a maximum rate of 1 request per second with user agent `VistaraeTravelEngine/1.0`.
3. **Given** a natural landmark spanning multiple administrative regions, **When** geocoding finishes, **Then** the POI is populated with multiple distinct address objects, each standardized to official English names and ISO 3166-1 country codes.
4. **Given** any external rate-limited or billed lookup, **When** completed successfully, **Then** the response is cached in `geocoding_cache` to eliminate duplicate external calls.

---

### User Story 5 - Early Scale-Aware Duplicate & Parent-Child Nesting Triage (Priority: P2)

A traveler visits the Chicago Art Institute website and captures the famous outdoor sculpture "Cloud Gate" (The Bean) in Millennium Park. 

During the initial extraction phase, the backend analyzes coordinates and computes trigram similarity against the traveler's existing POIs. It discovers that the traveler already saved "Millennium Park" at the same coordinates. The system evaluates the physical scale: "Millennium Park" is classified as a Macro/Site-scale park (24.5 acres), whereas "Cloud Gate" is classified as a Micro-scale sculpture (33 feet high). Because trigram similarity is $< 0.60$ and the existing POI is at a larger spatial scale, the system classifies the match as a `NEARBY_PARENT`. 

The capture overlay displays an early triage banner:  
`"Discovered existing location: Millennium Park (25m away). Cloud Gate appears to be located within Millennium Park."`  
The banner highlights **Make Child** as the primary recommendation alongside **Proceed** and **Abort**:  
- **Proceed**: Save Cloud Gate as a standalone, unlinked POI.  
- **Make Child** (Recommended): Save Cloud Gate as a child of Millennium Park (automatically setting `parent_poi_id` to Millennium Park's ID and `parent_poi_name` to "Millennium Park").  
- **Abort**: Close the overlay and cancel capture.  
The traveler clicks **Make Child**, and the POI is persisted with the correct hierarchy.

**Why this priority**: Eliminates duplicate clutter and builds structured attraction hierarchies (parks containing monuments; museums containing galleries).

**Independent Test**: Create POI "Millennium Park" in database, trigger capture for "Cloud Gate" at identical coordinates, assert early triage modal appears with 3 buttons and recommends "Make Child", click "Make Child", and assert new POI has `parent_poi_id` set to Millennium Park.

**Acceptance Scenarios**:

1. **Given** an active capture, **When** extraction begins, **Then** the system checks for existing proximate POIs and name similarity within the first 500ms of analysis.
2. **Given** an existing proximate candidate, **When** distance $\le$ scale radius AND similarity $\ge 0.60$, **Then** the engine classifies the candidate as `POTENTIAL_DUPLICATE` and recommends Abort or Proceed.
3. **Given** an existing proximate candidate, **When** distance $\le$ scale radius AND similarity $< 0.60$ with the existing POI having a larger scale footprint, **Then** the engine classifies the candidate as `NEARBY_PARENT` and recommends "Make Child".
4. **Given** the user selects "Make Child", **When** saved, **Then** the new POI record stores `parent_poi_id` and `parent_poi_name` pointing to the discovered parent record.
5. **Given** the user selects "Abort", **When** clicked, **Then** the capture overlay closes immediately without saving any record to the database.

---

### Edge Cases

- **Session Expiration During Page Inspection**: If a traveler keeps a page open for hours and triggers capture after token expiry, the background service worker attempts an in-memory refresh via Cognito refresh token. If refresh fails, it surfaces a clear modal: "Session Expired. Please log in to continue" with a one-click re-auth flow that preserves the scraped draft data in `chrome.storage.local`.
- **Primary Source Blocked by Paywall or Anti-Scraping**: If the host page blocks DOM text access or is a dynamic canvas/SPA with obfuscated classes, the engine gracefully falls back to extracting `document.title`, `canonical` link, and the selected text, relying on secondary sources from the user's configured list.
- **Secondary Source Failure or Rate Limiting**: If Wikipedia or TripAdvisor APIs timeout (> 3.0s) or return 429 Too Many Requests, the system executes graceful partial fallback, returning primary page data without blocking the user.
- **Trans-boundary Regions Without Street Numbers**: When scraping vast wilderness areas (e.g., Death Valley National Park or Iguazu Falls), street address fields are left null while City/State/Country are populated across multiple address objects.
- **Circular Parenting Prevention**: If an existing POI is proposed as a parent, the system verifies that the proposed parent is not already a descendant of the POI being edited or captured.
- **Overlapping Tag Aliases**: If an alias is mapped to multiple tags (e.g., "fort" on both "Fortification" and "Military"), the extraction pipeline presents all matching candidate tags with opt-out badges for the user to select.
- **Tag Deletion with Referencing POIs**: Attempting to delete an assigned tag is hard-blocked with RFC 7807 409 Conflict; the UI provides a direct one-click link to filter the POI Table by that tag for instant bulk removal.

---

## 4. Requirements _(mandatory)_

### Functional Requirements

#### Web App Tag Governance & Management

- **REQ-EXT-001**: **Ubiquitous**: The system shall isolate tag libraries by tenant, ensuring each user independently owns, customizes, and queries their tag definitions via `WHERE user_id = :current_user_id` without cross-tenant interference.
- **REQ-EXT-002**: **State-Driven**: While rendering the Tag Management view on the Web App Preferences page (`/settings`), the frontend shall display all user tags in strict ascending alphabetical order by display name.
- **REQ-EXT-003**: **Event-Driven**: When a user registers a new account, the system shall automatically seed 30 default standardized tags with predetermined slug IDs and search aliases:
  1. `fortification` ("Fortification" — aliases: castle, fort, citadel, fortress)
  2. `landmark` ("Landmark" — aliases: monument, obelisk, tower)
  3. `ship` ("Ship" — aliases: boat, vessel, submarine, warship, museum ship)
  4. `aircraft` ("Aircraft" — aliases: airplane, plane, jet, aviation)
  5. `military` ("Military" — aliases: battlefield, base, bunker, armory, fort)
  6. `rail` ("Rail" — aliases: train, railway, locomotive, funicular, tram)
  7. `historic` ("Historic" — aliases: history, heritage, ancient, antique)
  8. `memorial` ("Memorial" — aliases: shrine, cenotaph, tribute, cemetery)
  9. `building` ("Building" — aliases: skyscraper, hall, palace, estate)
  10. `church` ("Church" — aliases: cathedral, chapel, basilica)
  11. `temple` ("Temple" — aliases: pagoda, shrine, sanctuary, mosque, synagogue)
  12. `museum` ("Museum" — aliases: gallery, exhibition, archive)
  13. `scenic` ("Scenic" — aliases: overlook, view, vista, panoramic)
  14. `waterfall` ("Waterfall" — aliases: falls, cascade, cataract)
  15. `water` ("Water" — aliases: lake, river, spring, reservoir, lagoon)
  16. `park` ("Park" — aliases: public park, gardens, arboretum, botanic)
  17. `wilderness` ("Wilderness" — aliases: nature reserve, wildlife refuge, canyon)
  18. `coast` ("Coast" — aliases: beach, shoreline, cliff, cove, bay)
  19. `mountain` ("Mountain" — aliases: peak, summit, ridge, pass, volcano)
  20. `food` ("Food" — aliases: dining, restaurant, cafe, bakery, market, brewery)
  21. `nps` ("NPS" — aliases: national park, national monument, national seashore)
  22. `unesco` ("UNESCO" — aliases: world heritage, unesco site)
  23. `culture` ("Culture" — aliases: art, folklore, theater, music, festival)
  24. `lighthouse` ("Lighthouse" — aliases: light station, beacon)
  25. `zoo` ("Zoo" — aliases: zoological park, safari, menagerie)
  26. `animal` ("Animal" — aliases: wildlife, sanctuary, aquarium, aviary)
  27. `shopping` ("Shopping" — aliases: mall, bazaar, boutique, antique shop)
  28. `entertainment` ("Entertainment" — aliases: theme park, amusement, casino)
  29. `film_location` ("Film Location" — aliases: movie location, filming site, cinema)
  30. `humorous` ("Humorous" — aliases: quirky, roadside attraction, novelty, oddity)
- **REQ-EXT-004**: **Ubiquitous**: The system shall store every tag using an immutable slugified identifier (`slug`), a human-readable display name (`name`), and an array of searchable aliases (`aliases`), permitting overlapping aliases across distinct tags within a user's library.
- **REQ-EXT-005**: **Event-Driven**: When a user creates a new tag, the system shall validate that the slug is unique within the user's library and generate the slug from the display name if not explicitly provided.
- **REQ-EXT-006**: **Unwanted Behaviour**: If a user attempts to delete a tag that is currently associated with one or more POIs, then the system shall reject the request with an RFC 7807 409 Conflict response detailing the count of referencing POIs and providing a filter link to view the affected POIs in the table.
- **REQ-EXT-007**: **Event-Driven**: When a tag has zero associated POIs and the user requests deletion, the system shall permanently remove the tag from the user's library.

#### Extension Streamlining & Authentication Gate

- **REQ-EXT-008**: **Event-Driven**: When the user triggers the capture shortcut (`Ctrl+Shift+S` / `Cmd+Shift+S`) or context menu, the extension shall verify the presence of a valid, unexpired access token.
- **REQ-EXT-009**: **Unwanted Behaviour**: If the user is unauthenticated when capture is triggered, then the extension shall open the Vistarae Web App login page in a new browser tab with a return redirect parameter and abort overlay injection.
- **REQ-EXT-010**: **State-Driven**: While the user is authenticated, the extension companion dashboard and the Shadow DOM capture overlay shall prominently display the user's email address and authentication state badge.
- **REQ-EXT-011**: **Ubiquitous**: The extension companion page (`browser.html`) shall omit all tabular POI lists, search boxes, category filter dropdowns, and "Export to CSV" buttons.
- **REQ-EXT-012**: **Unwanted Behaviour**: If the extension companion page or background worker experiences empty data or backend offline states, then the extension shall not render or load any mock or demo destinations.
- **REQ-EXT-013**: **Ubiquitous**: The extension companion page shall render an educational overview presenting Vistarae's purpose, keyboard capture shortcut instructions (`Ctrl+Shift+S`), current server connectivity status, and a navigation button opening the Web App dashboard.

#### Web Scraping Fields & Schema Parity

- **REQ-EXT-014**: **Ubiquitous**: The capture overlay form inputs shall maintain 1:1 schema parity with the Web App POI Editor, supporting:
  1. POI Name (Standardized English)
  2. Description (Multiline tight summary)
  3. Addresses (Array of address objects with street, city/town, state/province, country, postal code)
  4. Coordinates (Latitude and Longitude)
  5. Official Website URL
  6. Wikipedia Article URL
  7. Hero Image URL
  8. Estimated Duration Hours (Decimal)
  9. Estimated Duration Days (Integer)
  10. Star Rating (0 to 5 integer or null)
  11. Parent POI (`parent_poi_id` and `parent_poi_name`)
  12. Tags (Multi-select from vetted user tags)
  13. Source Metadata (`source_type = "Web"`, `source_value = <page_url>`, `extraction_sources = list[str]`)
- **REQ-EXT-015**: **Ubiquitous**: The web scraping extraction pipeline shall never populate the local photo folder field (`photo_folders`), leaving it null during web capture.
- **REQ-EXT-016**: **Ubiquitous**: The web scraping extraction pipeline shall require the human traveler to assign star ratings manually, leaving the star rating input unassigned by default.

#### Multi-Source Augmentation, Geocoding & Caching Logic

- **REQ-EXT-017**: **Event-Driven**: When page capture is triggered, the engine shall first extract the primary location name and normalize it to its standardized English representation.
- **REQ-EXT-018**: **State-Driven**: While extracting POI attributes, if the active webpage lacks necessary data, the backend shall query authorized secondary sources defined in `user_preferences.valid_scraping_domains`.
- **REQ-EXT-019**: **Ubiquitous**: The backend database shall persist the user-configurable list of authorized scraping domains as a `valid_scraping_domains` JSONB array column on the `user_preferences` table, initialized with default domains (`wikipedia.org`, `tripadvisor.com`, `atlasobscura.com`, `google.com/maps`, `roadtrippers.com`) and exposed via `GET /api/user/preferences/scraping-sources`.
- **REQ-EXT-020**: **Unwanted Behaviour**: If any secondary scraping source fails, times out (> 3.0s), or returns an HTTP 429/403 rate-limit error, then the extraction engine shall gracefully fall back to the primary page extraction data, leave missing secondary fields blank, and display an informational banner without aborting capture.
- **REQ-EXT-021**: **Event-Driven**: When extraction completes, the system shall record all domains queried during the session in the POI's `extraction_sources` metadata array.
- **REQ-EXT-022**: **Event-Driven**: When coordinates are not present on the scraped page but address details are available, the system shall query the internal PostGIS `geocoding_cache` table by SHA256 of the normalized address before dispatching external HTTP requests.
- **REQ-EXT-023**: **Event-Driven**: When a geocache miss occurs, the system shall query OpenStreetMap Nominatim throttled to a maximum rate of 1 request per second with `User-Agent: VistaraeTravelEngine/1.0`.
- **REQ-EXT-024**: **Event-Driven**: When coordinates are present but street or administrative addresses are missing, the system shall execute reverse geocoding via Nominatim to populate city, state/province, and country.
- **REQ-EXT-025**: **Ubiquitous**: The geocoding subsystem shall normalize all country names to standardized English versions backed by ISO 3166-1 alpha-3 / country standards.
- **REQ-EXT-026**: **Event-Driven**: When a captured POI spans multiple administrative areas (multi-state or multi-country), the system shall instantiate multiple distinct address records within the POI's `addresses` array.
- **REQ-EXT-027**: **Ubiquitous**: The system shall cache external API responses subject to rate limits or commercial quotas in `geocoding_cache` to eliminate redundant outbound requests.
- **REQ-EXT-028**: **Event-Driven**: When content is gathered from primary and secondary sources, the extraction engine shall invoke Gemini Flash-Lite with `thinking_budget = 0` to synthesize a concise, factual summary into the `description` field.
- **REQ-EXT-029**: **State-Driven**: While suggesting tags in the capture overlay, the system shall match scraped page text and entity metadata against the user's vetted tag slugs and aliases; where an alias maps to multiple tags, the system shall recommend all matching tags with toggle badges, permitting manual selection strictly from the user's vetted library.

#### Early Duplicate Detection & Nesting Triage

- **REQ-EXT-030**: **Event-Driven**: When capture begins, the backend shall evaluate spatial proximity and trigram name similarity against the user's existing POIs within the initial 500ms of analysis.
- **REQ-EXT-031**: **Event-Driven**: When evaluating proximate candidates, the system shall apply a dual-threshold heuristic:
  1. Classify as `POTENTIAL_DUPLICATE` if distance $\le$ scale-adjusted radius (Macro: 5,000m; Medium: 500m; Micro: 50m) AND trigram similarity $\ge 0.60$, recommending Abort or Proceed.
  2. Classify as `NEARBY_PARENT` if distance $\le$ scale-adjusted radius AND trigram similarity $< 0.60$ with the existing POI having a larger spatial scale, recommending "Make Child".
- **REQ-EXT-032**: **State-Driven**: While a proximate match or potential duplicate is detected, the capture overlay shall present the traveler with three mutually exclusive choices:
  1. `Proceed`: Persist the candidate as an independent POI.
  2. `Make Child`: Persist the candidate as a child of the discovered location, populating `parent_poi_id` and `parent_poi_name`.
  3. `Abort`: Terminate the capture process and discard all in-memory draft state.

#### Observability, Telemetry & Boundary Validation (Constitutional Standards)

- **REQ-EXT-033**: **Ubiquitous**: Every HTTP request initiated by the Chrome Extension to backend services shall include standard W3C distributed tracing headers (`traceparent: 00-{trace_id}-{client_span_id}-01`, `X-Source: extension`, `X-Destination: backend`), and the backend shall log directional message tags (`MSG ->|`, `MSG <-|`, `MSG |->`, `MSG |<-`) per Vistarae constitution.
- **REQ-EXT-034**: **Ubiquitous**: The backend boundary layer shall validate all incoming payloads using Pydantic v2 `StrictBaseModel` configured with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True`, returning RFC 7807 / RFC 9457 `ProblemDetails` on any validation failure.

---

### Key Entities

- **`UserTag`**:
  - `id`: UUID (Primary Key)
  - `user_id`: UUID (Foreign Key -> `users.id`, Tenant isolation via `WHERE user_id = :current_user_id`)
  - `slug`: String(64) (Immutable slugified key, unique per user: `[a-z0-9_]+`)
  - `name`: String(64) (Display label, e.g. "Fortification")
  - `aliases`: List[String] (Array of search synonyms, e.g. `["castle", "fort", "citadel"]`, allowing shared aliases across tags)
  - `created_at`: DateTime(timezone=True)
- **`UserPreferencesTable` Extension**:
  - `valid_scraping_domains`: List[String] (JSONB array column, defaulting to `['wikipedia.org', 'tripadvisor.com', 'atlasobscura.com', 'google.com/maps', 'roadtrippers.com']`)
- **`POIExtractionPayload`**:
  - `name`: String (Standardized English name)
  - `description`: String (Synthesized concise summary via Gemini Flash-Lite `thinking_budget = 0`)
  - `addresses`: List[AddressRecord] (Multi-address objects with English normalized country backed by ISO 3166-1)
  - `latitude`: Float | None
  - `longitude`: Float | None
  - `official_website_url`: String | None
  - `wikipedia_url`: String | None
  - `image_urls`: List[String] (Representative gallery & hero image)
  - `estimated_duration_hours`: Decimal | None
  - `estimated_duration_days`: Integer | None
  - `rating`: Integer | None (User-assigned 0-5)
  - `source_type`: String ("Web")
  - `source_value`: String (Source page URL)
  - `extraction_sources`: List[String] (Domains queried)
  - `parent_poi_id`: UUID | None
  - `parent_poi_name`: String | None
  - `tags`: List[String] (Vetted tag slugs)
  - `photo_folders`: List[String] (Always empty/omitted on web capture)

---

## 5. Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: **Tag Fragmentation Reduction**: 100% of newly assigned tags across user POIs strictly conform to the user's vetted tag library, eliminating uncurated tag drift.
- **SC-002**: **Zero Data Loss on Tag Deletion**: 0% of active POIs lose tag associations unexpectedly due to deletion, verified by 100% enforcement of the referential integrity pre-check and direct table remediation link.
- **SC-003**: **Keystroke-to-Overlay Latency**: Pressing `Ctrl+Shift+S` on any supported webpage opens the Shadow DOM capture overlay in under 400 milliseconds.
- **SC-004**: **Multi-Source Enrichment Speed & Resilience**: Multi-source background augmentation settles in under 2.5 seconds on broadband connections, with 100% graceful fallback to primary data if secondary sources exceed 3.0s.
- **SC-005**: **Geocoding Policy Compliance**: 100% of outbound OpenStreetMap Nominatim requests honor the 1 request per second ceiling and custom User-Agent policy, with over 80% of repeat lookups served instantly from the PostGIS `geocoding_cache` table.
- **SC-006**: **Zero Demo Data Leakage**: 0 demo or mock travel records are rendered in the extension under unauthenticated, offline, or empty catalog conditions.
- **SC-007**: **User Triage Task Completion**: 95% of users confronted with a duplicate or nested location complete triage (Proceed, Make Child, or Abort) in under 5 seconds without form abandonment.

---

## 6. Assumptions

- **A-001**: Users possess internet connectivity during web scraping captures to communicate with the Vistarae backend API and Cognito authentication endpoints.
- **A-002**: The user's browser supports Chrome Manifest V3 service workers, chrome storage APIs, and standard Shadow DOM v1 encapsulation.
- **A-003**: OpenStreetMap Nominatim service remains operational for external geocoding fallbacks, subject to standard 1 req/sec rate constraints.
- **A-004**: Authentication tokens are issued by AWS Cognito and verified via existing JWT validation middleware on the FastAPI backend.
- **A-005**: English localization standards for countries adhere to ISO 3166-1 alpha-3 / English common names, matching the normalization rules implemented in Phase 7 (`007-ui-edit-poi-enhancements`).
