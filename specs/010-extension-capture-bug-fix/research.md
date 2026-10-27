# Research: Extension Capture Bug Fixes & Verification Controls

**Feature**: `010-extension-capture-bug-fix`  
**Date**: 2026-10-26  
**Status**: Completed  

---

## 1. Title Sanitization & Platform Branding Removal (`FR-001`)

### Problem
When capturing destinations from mapping or travel websites (e.g., Google Maps), `document.title` or `<h1>` often includes trailing platform branding (e.g., `"Eltz Castle - Google Maps"`). This pollutes the POI title in both the capture modal and the database.

### Decision
Implement deterministic dual-layer title sanitization:
1. **Client-Side Sanitizer in Extension (`extension/content/parsers/`)**:
   - A dedicated `sanitizeDestinationTitle(rawTitle, platformHint)` utility function in `extension/content/parsers/BasePoiParser.js`.
   - Strips common platform suffixes using comprehensive regex patterns:
     ```javascript
     const BRANDING_SUFFIXES = [
       /\s*[-–—·|•]\s*Google Maps.*$/i,
       /\s*[-–—·|•]\s*Tripadvisor.*$/i,
       /\s*[-–—·|•]\s*Roadtrippers.*$/i,
       /\s*[-–—·|•]\s*Atlas Obscura.*$/i,
       /\s*[-–—·|•]\s*Yelp.*$/i,
       /\s*[-–—·|•]\s*Wikipedia.*$/i,
       /\s*[-–—·|•]\s*Official (Site|Website|Guide).*$/i,
     ];
     ```
   - In `GoogleMapsParser.js`, extract the place title specifically from Google Maps primary headline selectors (`h1.DUwDvf`, `h1.fontHeadlineLarge`, `div.x3AX1-LfntMc-header-title-title`), running the sanitizer before assigning `scrapedPoi.name`.
2. **Backend Normalizer (`services/poi/scraping/orchestrator.py`)**:
   - Expand `clean_page_title()` to strip these patterns alongside Gemini Flash-Lite English entity normalization (`thinking_budget=0`).

### Alternatives Considered
- *Gemini LLM only*: Slower (adds 400-800ms) and fails if offline or when quota exceeded.
- *Simple `.split('-')[0]`*: Breaks legitimately hyphenated destination names (e.g., "Stratford-upon-Avon" or "Baden-Baden").
- **Chosen**: Targeted regex suffix stripping preserving geographic hyphens.

---

## 2. Interactive Mini-Map in Content Script Shadow DOM (`FR-011`, `FR-012`, `FR-013`)

### Problem
Travelers need immediate visual confirmation that the detected coordinates point to the correct structure, plus a simple way to adjust the pinpoint without leaving the page.

### Decision
Embed a lightweight Leaflet map instance inside the content script's isolated Shadow DOM (`vistarae-capture-root`):
1. **Zero-Cost OSM Raster Tiles**:
   - Tile provider: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
   - Adheres to Constitution Operational Invariant 3 (Zero-Cost Architecture). Zero Google Maps API keys or Mapbox tokens required.
2. **Shadow DOM Integration**:
   - Leaflet JavaScript (`leaflet.js`) and CSS (`leaflet.css`) bundled locally in `extension/content/vendor/leaflet/` to comply with Manifest V3 restrictions against remote code execution.
   - Inject `leaflet.css` directly into `shadowRoot` so styles do not leak to the host page and host page styles cannot break map controls.
   - Container: `<div id="vistarae-minimap"></div>` with fixed height (160px). Call `map.invalidateSize()` after modal mount.
3. **Dual Reselection Interaction**:
   - Toggle button: `#vistarae-reselect-map-btn` ("Reselect Location").
   - When active, cursor becomes crosshair.
   - Clicking anywhere on map moves the marker: `map.on('click', (e) => updatePin(e.latlng))`.
   - Marker is draggable: `marker.on('dragend', () => updatePin(marker.getLatLng()))`.
   - `updatePin(latlng)`:
     1. Updates `#vistarae-lat-input` and `#vistarae-lng-input`.
     2. Dispatches reverse-geocoding message (`REVERSE_GEOCODE`) to backend.
     3. Refreshes the resolved address chip.

### Alternatives Considered
- *Static image map (static tile)*: Non-interactive, cannot adjust pin.
- *Google Maps Embed iframe*: Requires API key, violates zero-cost invariant, prone to CSP block.
- **Chosen**: Local Leaflet in Shadow DOM with standard OSM tiles.

---

## 3. Wikipedia 2-Step Search & Multi-Source Knowledge Enrichment (`FR-002`, `FR-003`)

### Problem
Wikipedia lookup for "Eltz Castle" returned empty because direct query to `https://en.wikipedia.org/api/rest_v1/page/summary/Eltz_Castle_-_Google_Maps` returned 404, and even with sanitized title, slight spelling variations cause direct lookup failures.

### Decision
Upgrade `WikipediaAdapter` in `services/poi/scraping/secondary_sources.py`:
1. **Step 1: Direct Summary Lookup**:
   - Try `https://en.wikipedia.org/api/rest_v1/page/summary/{sanitized_title}`.
2. **Step 2: OpenSearch Fallback**:
   - If direct summary returns 404, query Wikipedia OpenSearch API:
     `https://en.wikipedia.org/w/api.php?action=opensearch&search={sanitized_title}&limit=1&namespace=0&format=json`
   - Extract canonical page title from response index `[1][0]`.
   - Re-query `/page/summary/{canonical_title}`.
3. **Data Extracted**:
   - `extract`: Rich 2-3 sentence summary description.
   - `content_urls.desktop.page`: Authoritative Wikipedia article URL.
   - `thumbnail.source` / `originalimage.source`: Hero image candidate.
   - `coordinates`: Lat/Lon verification.

### Alternatives Considered
- *Wikidata SPARQL only*: High latency and complex queries.
- *Direct summary only*: Fails on any redirect or punctuation mismatch.
- **Chosen**: Direct summary + OpenSearch fallback with 3.0s timeout ceiling.

---

## 4. Address Normalization & Reverse-Geocoding Precedence (`FR-014`, `FR-015`)

### Problem
1. Google Maps web scraping extracted raw button text: `"🖈56294 Wierschem, Germany"`. The pushpin symbol (`🖈`, U+1F588) was not stripped.
2. `content_script.js` line 51 hardcoded `{ country: "United States", city: scrapedPoi.address }`, causing the address to render as `"🖈56294 Wierschem, Germany, United States"`.

### Decision
1. **Eliminate Hardcoded Country Default**:
   - Remove `{ country: "United States" }` from `content_script.js`.
   - Default address state initialized from coordinates via reverse-geocoding.
2. **Address Normalization Regex**:
   - In `vistarae_core.services.address_normalizer`:
     - Strip non-alphanumeric leading glyphs:
       ```python
       CLEAN_LEADING_GLYPHS = re.compile(r"^[\s\W\U00010000-\U0010ffff\u2000-\u2bff\u2600-\u27ff]+", re.UNICODE)
       ```
     - Strip specific pushpins: `🖈` (U+1F588), `📍` (U+1F4CD), `📌` (U+1F4CC), `🗺` (U+1F5FA).
3. **Country Conflict Resolution**:
   - When coordinates exist, backend reverse-geocoding via OpenStreetMap Nominatim returns structured fields: `country`, `city`, `postcode`, `road`, `state`.
   - If country in coordinates is Germany (`DE`), discard any extraneous country tokens.
   - Format address cleanly: `"{road}, {postcode} {city}, {country}"`.

---

## 5. Hero Image Preview & Client-Side Preflight (`FR-007` to `FR-010`)

### Problem
Hero Image URL is often empty. When populated or pasted by the user, there was no visual preview and no way to test if the URL works before saving.

### Decision
1. **Extraction Source**:
   - Wikipedia `originalimage.source` or `thumbnail.source`.
   - Google Maps primary header image `img.decoding="async"`.
2. **UI Container in Modal**:
   - An image preview card `<div class="vistarae-hero-preview">` above the URL input.
   - Shows thumbnail when URL is valid.
   - Shows placeholder icon when empty.
3. **Interactive Preflight & Reload Button**:
   - Input row contains: `<input id="vistarae-hero-image-input">` and `<button id="vistarae-hero-reload-btn">Preview</button>`.
   - When clicked (or on blur), runs client-side preflight:
     ```javascript
     const img = new Image();
     img.onload = () => { showPreview(url); };
     img.onerror = () => { showWarning("Image preview unavailable (check URL or CORS)"); };
     img.src = url;
     ```
   - Does NOT block form submission if image fails (non-blocking).

---

## 6. External Link "View" Verification Buttons (`FR-004`, `FR-005`, `FR-006`)

### Problem
Travelers could not verify that official website or Wikipedia links pointed to the right destination without manually copying and pasting URLs into new tabs.

### Decision
- Add dedicated `<button type="button" class="vistarae-view-btn" data-target="vistarae-official-url-input">View ↗</button>` and `<button type="button" class="vistarae-view-btn" data-target="vistarae-wikipedia-url-input">View ↗</button>`.
- Button stays disabled if input is empty or does not start with `http://` / `https://`.
- When clicked, opens link in new tab via `window.open(url, '_blank', 'noopener,noreferrer')`.

---

## 7. Hybrid Visit Duration Inference (`FR-017`)

### Problem
Duration (hours and days) was always unassigned because neither raw Google Maps text nor basic Wikipedia summaries specify numeric hours.

### Decision
Implement a 2-tier hybrid duration estimator:
1. **Tier 1: Category & Scale Heuristic Table**:
   - Castle / Fortress / Palace: 2.5 hours, 0 days.
   - Museum / Gallery: 2.0 hours, 0 days.
   - Landmark / Monument / Viewpoint: 1.0 hour, 0 days.
   - Church / Cathedral / Historic Site: 1.5 hours, 0 days.
   - Theme Park / Amusement Park: 6.0 hours, 0 days.
   - National Park / Wilderness / Mountain: 4.0 hours, 1 day.
   - City / Historic District: 4.0 hours, 1 day.
2. **Tier 2: Gemini Entity Refinement**:
   - When Gemini Flash-Lite synthesizes the summary description, include structured prompt guidance to infer realistic visit duration if mentioned in text.

---

## 8. Vetted Tag Recommendation & System Seed Availability (`FR-016`)

### Problem
Vetted Tags container was empty because the user's custom tag list had 0 entries in the local database.

### Decision
1. **System Tag Fallback**:
   - In `routes/triage.py`, when `tag_repo.list_by_user(current_user.id)` returns empty, fall back to system standard tags (or auto-seed default tags for the user via `TagSeeder.seed_default_tags(user_id)`).
2. **Taxonomy Matching**:
   - `TagMatcher` maps scraped category + title + summary to standard tags (e.g., "castle", "historic", "scenic-overlook").
   - Extension renders these as interactive toggleable pills in `#vistarae-tag-pills`.
