# Feature Specification: Extension Capture Bug Fixes & Verification Controls

**Feature Branch**: `010-extension-capture-bug-fix`

**Created**: 2026-10-25

**Status**: Draft

**Input**: User description: "When clicking Ctrl+Shift+S - There are some issues in capturing the destination: - Destination / POI Name - this should not contain ' - Google Maps' it should just focus on the location name and not the capture source - Summary Description - This should be a summary of the location after looking up information from the scraping sources - Below the latitude & Longitude please have a map plotting the location to let the user know if it was plotted correctly - add a button to reselect the location (and after the new location is selected, re-calculate lat/long and address) - Wikipedia article is empty - For the official website and Wikipedia Article entry add 'View' buttons that open a new tab or browser window to display the entry so the user can verify it is correct - Hero image is empty - if a URL is found make sure it is displayed here, add a reload button so a user can paste in a new hero image and make sure it loads before saving to the DB - The address is incorrect, it has an invalid leading character and it lists both Germany and the United States. - No Tags were listed - no duration hours / days was determined"

## Clarifications

### Session 2026-10-25

- Q: How should the traveler interact with the mini-map when reselecting a location in the capture overlay? → A: Both click-to-place and pin-dragging on the mini-map, immediately updating latitude/longitude and triggering reverse-geocoding for the new address on release/confirmation.
- Q: How should multi-source knowledge enrichment (Wikipedia, summary description, hero image, vetted tags, duration) be delivered to the capture overlay? → A: Progressive enrichment: Instant local fields display immediately; backend scraping orchestrator enriches summary, Wikipedia, hero image, tags, and duration asynchronously with field-level loading indicators.
- Q: When latitude and longitude are available during capture, what should be the primary authority for resolving the destination address and sovereign country? → A: Reverse-geocoding priority: Use coordinates to reverse-geocode the authoritative structured address and sovereign country via backend geocache/Nominatim, falling back to regex-cleansed page text only when geocoding is unavailable.
- Q: How should the Hero Image URL reload and load-failure handling behave in the capture overlay? → A: Client-side preflight: Verify image load via an in-memory probe; render thumbnail if valid, or show an inline warning ('Image preview unavailable') without blocking form saving.
- Q: How should estimated visit duration (hours and days) be inferred when not explicitly stated in the source page? → A: Hybrid Category & LLM Heuristic: Derive duration from place category/scale heuristics (e.g. 2 hrs for landmark/castle, 1-2 days for national park), refined by Gemini extraction when secondary text provides explicit visit guidance.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Clean Identity & Multi-Source Knowledge Enrichment (Priority: P1)

A traveler captures a point of interest from a mapping service or travel website (e.g. Google Maps, TripAdvisor, blog) using the extension shortcut (`Ctrl+Shift+S`). The extension automatically sanitizes the destination title by removing source website branding suffixes and populates the capture modal with rich contextual information: a cohesive summary description derived from secondary sources (Wikipedia/Wikidata/search), an accurate Wikipedia article link, recommended vetted tags reflecting the destination category, and estimated visit durations (hours and days).

**Why this priority**: Core value of the capture tool relies on high-fidelity, accurate destination data without requiring manual text editing or source name cleanup on every capture.

**Independent Test**: Trigger capture on a Google Maps place page (such as "Eltz Castle - Google Maps"). Verify that the Destination Name displays cleanly as "Eltz Castle", the Summary Description contains informative details about the landmark, the Wikipedia article URL is populated, vetted tags (e.g. "Castle", "Historic Site") are attached, and duration estimates (e.g., 2.5 hours) are pre-filled.

**Acceptance Scenarios**:

1. **Given** a web page with a title ending with source platform branding (such as " - Google Maps" or " | TripAdvisor"), **When** the traveler triggers capture, **Then** the destination name in the modal shall display only the cleaned place name without the branding suffix.
2. **Given** a recognized geographic destination, **When** capture analysis completes, **Then** the summary description shall provide a concise informational overview of the destination from knowledge sources rather than a placeholder string.
3. **Given** an enriched landmark or attraction with an existing Wikipedia entry, **When** capture details load, **Then** the Wikipedia article field shall contain the full canonical URL to the article.
4. **Given** enriched destination metadata, **When** capture details load, **Then** the vetted tags container shall present matching categorized tags and the duration fields shall present estimated visit hours and days appropriate to the place type.

---

### User Story 2 - Address Sanitation & Geographic Accuracy (Priority: P1)

When a location address is resolved from web page contents or reverse-geocoding, the system purges special glyphs, pushpins, and UI artifact symbols, while validating administrative hierarchy to prevent conflicting multi-country strings.

**Why this priority**: Invalid address characters cause corrupt records and database search defects, while conflicting country labels ("Germany, United States") degrade user trust and spatial accuracy.

**Independent Test**: Capture a location from a page containing leading map icon glyphs (e.g., pushpin symbol `🖈56294 Wierschem, Germany`). Verify that the resolved address strips the symbol completely and formats the administrative hierarchy accurately without duplicate or conflicting country names.

**Acceptance Scenarios**:

1. **Given** a raw address containing leading unicode icons, pushpins (`🖈`, `📍`), bullet points, or control symbols, **When** the address is parsed and displayed, **Then** all non-alphanumeric leading symbols and whitespace shall be cleanly removed.
2. **Given** an address string resolved from reverse-geocoding or page extraction, **When** country and administrative boundaries are assembled, **Then** the system shall assert mutually exclusive single-country resolution and eliminate contradictory multi-nation strings.

---

### User Story 3 - Visual Map Verification & Coordinate Reselection (Priority: P2)

Travelers need visual certainty that the captured latitude and longitude point to the intended physical structure. A lightweight interactive mini-map rendered beneath the coordinate fields plots the detected pin. If the coordinate is slightly off (such as a parking lot or highway exit instead of the castle), the traveler can click a "Reselect Location" control to adjust the pinpoint on the map, which immediately updates the coordinates and refreshes the reverse-geocoded address.

**Why this priority**: Spatial accuracy is foundational to travel itinerary planning. Giving travelers visual confirmation and manual pin-dropping directly inside the capture overlay eliminates bad coordinates before saving.

**Independent Test**: Open capture on a place with coordinates. Observe the interactive mini-map centered on the pinpoint. Click "Reselect Location", click a new spot on the mini-map, and verify that latitude, longitude, and resolved address update immediately to reflect the new position.

**Acceptance Scenarios**:

1. **Given** latitude and longitude coordinates in the capture modal, **When** the capture overlay is displayed, **Then** an interactive mini-map positioned beneath the coordinate inputs shall display a pin marker at the exact coordinates.
2. **Given** the mini-map is visible, **When** the traveler clicks "Reselect Location", **Then** the map enters selection mode allowing the traveler to click or drag the pin to a new position.
3. **Given** a new pin position selected on the mini-map, **When** the placement is confirmed, **Then** the latitude and longitude input fields shall update with the new coordinates and the resolved address field shall re-query reverse-geocoding for the new location.

---

### User Story 4 - Media Preview, Live Reload & Link Verification (Priority: P2)

Travelers can verify external links and hero imagery before committing the POI to their library. "View" verification buttons next to the Official Website and Wikipedia Article fields open the links in a separate browser tab. A visual hero image preview box shows the discovered photo, and a "Reload / Preview" button enables travelers to test and preview alternative image URLs pasted into the input before saving.

**Why this priority**: Prevents broken URLs, missing images, and incorrect references from entering the user's permanent POI collection.

**Independent Test**: Capture a POI where a hero image and links are discovered. Click the "View" button beside Wikipedia to verify it opens the article in a new tab. Paste a new image URL into the Hero Image field and click "Reload / Preview" to verify the thumbnail updates.

**Acceptance Scenarios**:

1. **Given** an official website URL or Wikipedia article URL populated in the capture modal, **When** the traveler clicks the corresponding "View" button, **Then** the destination link shall open in a new browser tab with secure navigation.
2. **Given** a hero image URL detected from scraping sources, **When** the capture overlay renders, **Then** an image preview card shall display the hero image with loading state handling.
3. **Given** a traveler editing or pasting a custom URL into the Hero Image field, **When** the traveler clicks the "Reload / Preview" button, **Then** the system shall attempt to render the updated image and display an error state if the image fails to load.

---

### Edge Cases

- What happens when a destination has no Wikipedia article or secondary knowledge source?
  - The Wikipedia article input shall remain cleanly empty with a placeholder, the summary description shall fallback gracefully to a brief user-editable description derived from page meta-description or title, and the "View" button for Wikipedia shall remain disabled until a valid URL is entered.
- What happens when the traveler reselects a location in the ocean or an unaddressed wilderness area?
  - The latitude and longitude shall update immediately, and reverse-geocoding shall display the nearest administrative boundary (e.g., "North Atlantic Ocean" or regional coordinates) without throwing unhandled errors or reverting coordinates.
- What happens when a pasted hero image URL is blocked by CORS or returns HTTP 404?
  - The preview area shall display an inline non-blocking warning ("Unable to load image preview from this URL") and retain the text URL so the traveler can correct it.
- What happens when a page title has multiple delimiters (e.g. "Eltz Castle - Rhineland-Palatinate - Google Maps")?
  - The sanitization routine shall specifically target known vendor/platform brand suffix tokens (e.g. `- Google Maps`, `| Google Maps`, `Google Maps`, `- TripAdvisor`) while preserving legitimate geographic hyphens.
- What happens when coordinates are not available from the source page?
  - The mini-map shall display a search/placement prompt centered on the default user region until geocoding resolves coordinates from the address or place name.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001** _(Event-Driven)_: When the traveler triggers the capture shortcut, the extension shall strip platform branding suffixes and prefixes (including ` - Google Maps`, ` | Google Maps`, `- TripAdvisor`, and similar capture-source suffixes) from the destination name.
- **FR-002** _(State-Driven)_: While the capture overlay renders instant local parsed fields, the system shall asynchronously invoke the backend multi-source scraping orchestrator to enrich the summary description, Wikipedia article URL, hero image URL, vetted tags, and estimated duration, displaying subtle field-level loading indicators until enrichment completes.
- **FR-003** _(Ubiquitous)_: The system shall populate the Wikipedia Article field with the canonical article URL whenever a matching knowledge entity is resolved.
- **FR-004** _(Ubiquitous)_: The capture interface shall render a dedicated "View" verification button adjacent to both the Official Website and Wikipedia Article input fields.
- **FR-005** _(Event-Driven)_: When the traveler activates a "View" verification button, the browser shall navigate to the specified URL in a new browser tab with `target="_blank"` and `rel="noopener noreferrer"`.
- **FR-006** _(State-Driven)_: While the URL input field for Official Website or Wikipedia Article is empty or invalid, the interface shall disable the corresponding "View" button.
- **FR-007** _(Ubiquitous)_: The capture interface shall render a visual hero image preview thumbnail container adjacent to or above the Hero Image URL input.
- **FR-008** _(State-Driven)_: While a valid image URL is populated or discovered, the interface shall render the visual thumbnail inside the hero image preview container.
- **FR-009** _(Event-Driven)_: When the traveler modifies the Hero Image URL and clicks the "Reload / Preview" button, the interface shall execute an in-memory client-side preflight verification probe to test image loadability before updating the preview thumbnail.
- **FR-010** _(Unwanted Behaviour)_: If the preflight probe fails to load or receives a network error, then the interface shall display an inline non-blocking warning ("Image preview unavailable") while retaining the URL and permitting form submission.
- **FR-011** _(Ubiquitous)_: The capture interface shall embed an interactive mini-map positioned directly beneath the Latitude and Longitude coordinate fields displaying a pinpoint marker at the current coordinates.
- **FR-012** _(Event-Driven)_: When the traveler clicks the "Reselect Location" button on the mini-map, the mini-map shall activate interactive coordinate selection mode supporting both click-to-place anywhere on the map canvas and direct pin-dragging.
- **FR-013** _(Event-Driven)_: When a new position is dropped or dragged on the mini-map, the system shall recalculate the latitude and longitude inputs and automatically execute reverse-geocoding to refresh the resolved address field upon pin release.
- **FR-014** _(Event-Driven)_: When latitude and longitude coordinates are detected or reselected, the system shall execute reverse-geocoding via the backend geocoding engine as the authoritative source of truth for the formatted address and sovereign country, strictly avoiding hardcoded country defaults.
- **FR-015** _(State-Driven)_: While displaying addresses from reverse-geocoding or raw on-page text fallback, the address engine shall strip leading non-alphanumeric icon glyphs (including pushpins `🖈`, `📍`, bullet points, and stray punctuation) and prevent conflicting multi-country concatenations (e.g. retaining exclusively the valid sovereign country).
- **FR-016** _(State-Driven)_: While scraping or analyzing destination place types, the system shall suggest matching vetted tags from the system tag dictionary based on the categorized taxonomy of the destination.
- **FR-017** _(State-Driven)_: While analyzing destination scale and landmark attributes, the system shall infer and pre-fill estimated visit duration fields using a hybrid strategy: applying category/scale heuristics (such as 2.0 hours for landmarks/castles/museums, 6.0 hours for theme parks, 1.0–2.0 days for national parks/regions) refined by Gemini LLM entity extraction whenever secondary text provides explicit visit guidance.

---

### Key Entities _(include if feature involves data)_

- **Captured Destination**: Represents the candidate point of interest in the active extension capture session prior to persistence, comprising clean name, sanitized address, coordinates, summary description, official website, Wikipedia link, hero image URL, estimated duration (hours/days), and vetted tags.
- **Map Viewport Coordinate**: The latitude and longitude point displayed on the mini-map, capable of interactive re-centering and drag/click recalculation.
- **Knowledge Enrichment Result**: The aggregated payload returned by background secondary scraping sources, providing entity summary text, Wikipedia article link, canonical hero image, category tags, and duration estimates.

---

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of captured destination titles from Google Maps and TripAdvisor omit platform branding suffixes (e.g. zero instances of " - Google Maps" in saved POI names).
- **SC-002**: 100% of resolved addresses contain zero leading unicode glyphs, pushpins, or control symbols.
- **SC-003**: 0% of resolved addresses contain conflicting multi-country strings.
- **SC-004**: Over 90% of recognizable landmarks and attractions captured from mapping platforms automatically populate with a non-empty summary description, Wikipedia article link, and at least one relevant vetted tag.
- **SC-005**: Travelers can visually verify their location on the mini-map and successfully adjust their coordinates in under 5 seconds.
- **SC-006**: 100% of valid hero image URLs render a preview thumbnail in the capture overlay, with manual URL changes previewable upon clicking "Reload".
- **SC-007**: External links ("View" buttons) open target destinations in a separate tab without navigation failures or loss of extension modal state.

---

## Assumptions

- **A-001**: Mapping platforms such as Google Maps and TripAdvisor include standard platform branding patterns in the document title that can be deterministically cleaned.
- **A-002**: OpenStreetMap Nominatim or similar geocoding provider delivers administrative hierarchy data sufficient to isolate the single genuine country and prevent conflicting country concatenation.
- **A-003**: The extension environment has permission to render lightweight map tiles (e.g. OpenStreetMap / Leaflet) inside the content script's isolated Shadow DOM.
- **A-004**: Wikipedia and Wikidata APIs allow unauthenticated read-only queries for entity descriptions, thumbnails, and article URLs within standard rate limits.
- **A-005**: Users may occasionally prefer custom hero images from third-party image hosts, justifying an interactive URL input with a manual reload/preview button.
