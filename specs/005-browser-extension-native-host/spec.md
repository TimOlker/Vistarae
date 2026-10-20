# Feature Specification: Phase 5 — Manifest V3 Browser Extension & Native Messaging Host

**Feature Identifier**: `005-browser-extension-native-host`  
**Feature Branch**: `005-browser-extension-native-host`  
**Created**: 2026-10-20  
**Status**: Draft  
**Target Systems**: Chrome Browser (Manifest V3), Content Script & Isolated Shadow DOM Container, Background Service Worker, OOP Page Scrapers (`BasePoiParser`, `GoogleMapsParser`, `RoadtrippersParser`, `TripAdvisorParser`), Full-Tab POI Explorer (`browser/browser.html`), Python Native Messaging Host (`native_host/folder_dispatcher.py`), Host Registration Script (`scripts/register_native_host.py`), Backend API Services (`services/user`, `services/poi`), AWS Cognito Identity Provider (`REFRESH_TOKEN_AUTH`), PostGIS Geospatial Database

**Input**: User description: "/speckit.specify Create the specification for Phase 5 (005-browser-extension-native-host) using strict EARS syntax (REQ-EXT-xxx, REQ-NATIVE-xxx)."

---

## 1. Executive Summary & Context

Phase 5 (`005-browser-extension-native-host`) delivers the unified web capture engine and native desktop integration bridge for Vistarae travelers:
1. **Manifest V3 Chrome Extension (`extension/`)**:
   - **Scoped Permissions & External Connectability**: Declares `"nativeMessaging"`, tightly scoped host permissions targeting AWS Cognito endpoints, CloudFront, and the API Gateway origin, alongside `"externally_connectable": { "matches": ["https://*.cloudfront.net/*", "http://localhost:5173/*"] }` to enable bidirectional communication between the Vistarae Single-Page Application (SPA) and the extension.
   - **Silent Token Refresh & Single-Flight Mutex**: Persists Access, ID, and `refresh_token` credentials securely in `chrome.storage.local`. Pre-flight checks inspect the JWT `exp` claim before every capture or API request. If expired or within 5 minutes of expiration, the service worker silently invokes AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`) via the public App Client ID. Concurrent requests share an in-memory `refreshPromise` (single-flight mutex) to eliminate parallel refresh race conditions. All mutation requests attach a unique `Idempotency-Key` (UUIDv4) and W3C `traceparent` headers.
   - **Object-Oriented Page Scrapers**: An extensible, object-oriented parser architecture featuring an abstract base class (`BasePoiParser`) and specialized inherited extractors for **Google Maps** (`GoogleMapsParser`), **Roadtrippers** (`RoadtrippersParser`), and **TripAdvisor** (`TripAdvisorParser`), triggered seamlessly by keyboard shortcut (`Ctrl+Shift+S` / `Command+Shift+S`) or context menu.
   - **Encapsulated In-Page Capture & Shadow DOM**: Injects an isolated open Shadow DOM container (`<vistarae-capture-root>`) with reset styles (`all: initial`) and scoped styling (`overlay.css`), eliminating CSS bleeding and layout disruption on complex host websites.
   - **AI Extraction & PostGIS Spatial Deduplication**: Dispatches captured content to Google Gemini Flash-Lite (`thinking_budget: 0`) and Nominatim geocoding (1 req/s, PostGIS `geocache`), evaluating geodesic distance and trigram similarity to categorize locations into `UNIQUE_LOCATION`, `POTENTIAL_DUPLICATE` (with side-by-side comparison), or `NEARBY_PARENT` (with 1-click nesting).
   - **Full-Tab POI Explorer (`browser/browser.html`)**: An offline/online catalog browser supporting real-time search, multi-faceted filtering, geoproximity queries, inline editing, bulk deletions, and RFC 4180 CSV export with neutralized formula injection prefixes.
2. **Chrome Native Messaging Local Folder Subsystem (`native_host/` & `scripts/register_native_host.py`)**:
   - **SPA-to-Extension-to-Host Bridge**: When a traveler clicks "Reveal Folder" or "Open Photo Directory" in the SPA web client, the SPA dispatches `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: directory_path })`. The extension service worker validates the request and forwards it to `chrome.runtime.sendNativeMessage('com.vistarae.folder_opener', ...)`, gracefully degrading to a setup toast banner if the host is missing.
   - **Pure Python Dispatcher (`folder_dispatcher.py`)**: Communicates over unbuffered binary standard I/O (`sys.stdin.buffer`, `sys.stdout.buffer`) using 4-byte native endian integer framing (`struct.unpack('=I', ...)`, `struct.pack('=I', len(payload))` + `flush()`). On Windows, enforces `msvcrt.setmode(..., os.O_BINARY)` to suppress CRLF translation, reading via an exact-byte accumulation loop. Normalizes `file:///` URIs, rejects shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`), restricts UNC network shares to private subnets with a 1.0s reachability probe (preventing NTLM hash leakage), and opens the native file explorer safely (`os.startfile` on Windows, `xdg-open` on Linux, `open` on macOS).
   - **User-Level Cross-Platform Registration (`scripts/register_native_host.py`)**: Registers the native host manifest without requiring administrator or root rights (Windows batch launcher `run_dispatcher.bat` with `python -u` + `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`; macOS/Linux `chmod +x` + JSON manifest in the user's `NativeMessagingHosts` folder with `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]`).

---

## Clarifications

### Session 2026-10-20
- Q: How does the SPA communicate with the Chrome Extension to open local folders? → A: Option A (Externally Connectable Messaging): The extension manifest specifies `"externally_connectable": { "matches": ["https://*.cloudfront.net/*", "http://localhost:5173/*"] }`. The SPA invokes `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: directory_path })`. The background service worker intercepts via `chrome.runtime.onMessageExternal` and calls `chrome.runtime.sendNativeMessage('com.vistarae.folder_opener', ...)`. If uninstalled or missing, the SPA renders an actionable setup toast.
- Q: How should token expiration be managed during capture workflows? → A: Option A (Pre-flight Silent Refresh): The extension inspects the `exp` claim of the cached JWT. If `Date.now() / 1000 >= exp - 300` (within 5 minutes of expiration), the service worker silently calls Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`) via the public App Client ID to refresh credentials before sending the request. If the refresh token is revoked, it triggers an in-page login modal inside the Shadow DOM.
- Q: How are specialized scrapers organized in the content script layer? → A: Option A (OOP Parser Hierarchy): An abstract `BasePoiParser` defines contract methods `canParse(url, document)` and `parse(document, selection)`. Concrete subclasses (`GoogleMapsParser`, `RoadtrippersParser`, `TripAdvisorParser`) implement site-specific DOM/JSON-LD traversal, while a `GenericSelectionParser` handles general web pages.
- Q: How does `folder_dispatcher.py` handle Windows paths vs. `file:///` URIs vs. UNC shares? → A: Option A (Universal Canonical Normalization): The dispatcher strips `file:///` schemes, decodes percent-encoded characters via `urllib.parse.unquote`, normalizes separators to OS standards, and verifies existence using `os.path.exists()` for both local disk drives (e.g. `C:\Photos`) and UNC shares (e.g. `\\server\share`).
- Q: How should the Manifest V3 service worker resolve concurrent token refresh race conditions when multiple capture requests fire near token expiration? → A: In-flight Promise Reuse (Single-Flight Mutex): Maintain an in-memory `refreshPromise` in the service worker; concurrent requests await the identical promise, updating `chrome.storage.local` once and re-reading fresh tokens before dispatch.
- Q: How should folder_dispatcher.py guarantee 4-byte binary stdio framing integrity and prevent CRLF corruption on Windows? → A: Explicit msvcrt.setmode Binary Enforcement & Chunked Buffer Accumulator: Set `sys.stdin`/`sys.stdout` to `os.O_BINARY` on Windows, launch Python with `-u` (unbuffered), and read from `sys.stdin.buffer` in an exact-byte accumulation loop (`while len(chunk) < target`).
- Q: What validation, scope restrictions, and timeout guardrails should folder_dispatcher.py enforce on UNC network share paths? → A: Private Subnet Allowlist & 1.0s Reachability Probe: Restrict UNC hosts to `localhost`, `127.0.0.1`, RFC 1918 private IP addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), or `.local` domains (preventing NTLM hash leakage), and probe share reachability with a 1.0-second timeout before launching the native file explorer.

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 - In-Page Web POI Capture & OOP Specialized Scrapers (Priority: P1)

A traveler browses a travel destination on Google Maps, Roadtrippers, TripAdvisor, or a general travel blog. When the user highlights text or presses `Ctrl+Shift+S` (or `Command+Shift+S` on macOS), the content script dispatches the page context through an object-oriented scraper registry. If the domain matches Google Maps, Roadtrippers, or TripAdvisor, the specialized parser extracts structured POI attributes directly from site DOM elements, microdata, and URL parameters; otherwise, it extracts highlighted text and OpenGraph metadata. The capture overlay renders immediately in an isolated Shadow DOM container (`<vistarae-capture-root>`), protected from host CSS style bleed.

**Why this priority**: High-fidelity data capture from the top three travel planning platforms (Google Maps, Roadtrippers, TripAdvisor) represents the primary user workflow for collecting travel destinations.

**Independent Test**: Can be fully tested by loading a Google Maps place URL (e.g., `https://www.google.com/maps/place/...`), pressing `Ctrl+Shift+S`, and asserting that the `GoogleMapsParser` extracts the exact place name, address, category, and canonical coordinates, rendering them inside the Shadow DOM overlay without manual text selection.

**Acceptance Scenarios**:

1. **Given** a user viewing a POI on Google Maps, **When** they press `Ctrl+Shift+S` or click "Capture to Vistarae", **Then** the `GoogleMapsParser` extracts the title from `h1.DUwDvf`, category from `button[jsaction*="category"]`, address from `button[data-item-id*="address"]`, and coordinates from the URL pathname or DOM, populating the capture form automatically.
2. **Given** a user viewing a trip or waypoint on `roadtrippers.com`, **When** capture is triggered, **Then** the `RoadtrippersParser` extracts waypoint titles, descriptions, category tags, and embedded coordinates from state/metadata attributes.
3. **Given** a user viewing an attraction or restaurant on `tripadvisor.com`, **When** capture is triggered, **Then** the `TripAdvisorParser` extracts the place title, bubble rating, address, and coordinates from embedded `schema.org/Place` JSON-LD metadata.
4. **Given** any general travel blog or website, **When** the user highlights text and presses `Ctrl+Shift+S`, **Then** the `GenericSelectionParser` extracts the selection, page URL, and OpenGraph metadata, displaying the capture form in `<vistarae-capture-root>`.
5. **Given** an active capture overlay, **When** the user presses the `Escape` key or clicks outside the dialog, **Then** the overlay closes cleanly and removes the `<vistarae-capture-root>` container.

---

### User Story 2 - Silent Cognito Token Refresh, Concurrency Mutex & Idempotent API Dispatch (Priority: P1)

An authenticated traveler captures several destinations throughout an extended browsing session across multiple tabs. As JWT access tokens approach expiration, the extension service worker inspects the `exp` claim before dispatching API requests. If the token is within 5 minutes of expiration, the service worker uses an in-flight promise mutex to ensure only a single silent call to AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`) is dispatched. Subsequent concurrent requests await the identical promise. Once refreshed, tokens in `chrome.storage.local` are updated, and each request attaches the fresh token, a new `Idempotency-Key` (UUIDv4), and W3C `traceparent` headers. The user captures places continuously without race conditions, token rotation errors, or duplicate database entries.

**Why this priority**: Uninterrupted, silent token refresh with race condition elimination prevents broken capture sessions during multi-tab or rapid capturing. Idempotency guarantees that network retries never create duplicate POIs.

**Independent Test**: Can be fully tested by triggering two simultaneous capture requests with a token expiring in 2 minutes, verifying in network DevTools that exactly one call to Cognito `InitiateAuth` is made, asserting both requests await the result, and confirming both requests succeed with identical new access tokens and unique UUIDv4 idempotency keys.

**Acceptance Scenarios**:

1. **Given** stored tokens in `chrome.storage.local` where the access token expires in under 5 minutes (`Date.now() / 1000 >= exp - 300`), **When** the extension initiates an API request, **Then** the service worker silently dispatches `InitiateAuth` with `AuthFlow: "REFRESH_TOKEN_AUTH"` to the Cognito endpoint and updates cached tokens before sending the request.
2. **Given** multiple concurrent requests detecting an expired or near-expired token simultaneously, **When** evaluated by the service worker, **Then** the first request creates an in-memory `refreshPromise` and subsequent requests await that identical promise without dispatching duplicate Cognito calls.
3. **Given** any outbound mutation request (`POST`, `PUT`, `PATCH`, `DELETE`), **When** dispatched by the service worker, **Then** the request includes header `Idempotency-Key: <uuidv4>` alongside `traceparent: 00-{trace_id}-{client_span_id}-01`.
4. **Given** an invalid or revoked `refresh_token`, **When** silent refresh fails with a 400 error from Cognito, **Then** the extension clears stored credentials and presents an in-page login form within the Shadow DOM modal so the user can re-authenticate without losing their pending capture.

---

### User Story 3 - SPA-to-Extension Folder Opener Bridge with Graceful Degradation (Priority: P1)

A traveler browsing their saved POIs or photo collections in the Vistarae Single-Page Application (running on `localhost:5173` in development or CloudFront in production) clicks "Open Photo Directory" on a POI card. The SPA dispatches a message via `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: directory_path })`. The extension service worker validates the caller origin against `"externally_connectable"`, forwards the request to the Native Messaging Host (`com.vistarae.folder_opener`), and the local folder opens in the operating system's file manager. If the extension or native host is not installed, the SPA displays an actionable setup banner.

**Why this priority**: Seamlessly opening local photo directories directly from the web application connects the cloud travel database to the user's desktop files while respecting browser sandbox security.

**Independent Test**: Can be fully tested by clicking "Open Photo Directory" on the SPA web page, observing the message dispatched to the extension, verifying the native host opens the folder, and testing in an incognito window without the extension to assert the setup banner appears.

**Acceptance Scenarios**:

1. **Given** the Vistarae SPA running on `http://localhost:5173` or `https://*.cloudfront.net`, **When** the user clicks "Open Photo Directory", **Then** the SPA dispatches `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: directory_path })`.
2. **Given** the extension service worker receives the message via `chrome.runtime.onMessageExternal`, **When** the origin matches `"externally_connectable"`, **Then** it forwards the message to `com.vistarae.folder_opener` via `chrome.runtime.sendNativeMessage`.
3. **Given** the extension is not installed in the user's browser, **When** the SPA attempts `chrome.runtime.sendMessage`, **Then** the SPA catches `chrome.runtime.lastError` and displays an actionable banner: "Vistarae Extension required for local folder opening. Click to install."
4. **Given** the native host is not registered on the user's machine, **When** `sendNativeMessage` fails, **Then** the extension returns an RFC 7807 error payload and the SPA displays a toast instructing the user to run `python scripts/register_native_host.py`.

---

### User Story 4 - Pure Python Binary Native Messaging Host (`folder_dispatcher.py`) with Windows stdio & UNC Guards (Priority: P2)

The Chrome browser launches `native_host/folder_dispatcher.py` to handle native folder requests. On Windows, the dispatcher explicitly configures standard streams to `os.O_BINARY` via `msvcrt.setmode` and reads bytes in an exact-byte accumulation loop to prevent CRLF corruption and packet fragmentation. It normalizes `file:///` URIs to native OS paths, strictly rejects shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`), restricts UNC network shares to private network subnets with a 1.0s reachability probe (preventing NTLM hash leakage), and safely launches the native file manager (`os.startfile` on Windows, `xdg-open` on Linux, `open` on macOS) without spawning a shell.

**Why this priority**: Adherence to binary stdio framing, exact read loops, and UNC security guards prevents host crashes, stream desynchronization, and NTLM capture vulnerabilities.

**Independent Test**: Can be fully tested by executing `folder_dispatcher.py` on Windows with mock binary stdio containing `\n` bytes (0x0A), verifying that `msvcrt.setmode` prevents `0x0D 0x0A` conversion, asserting that external UNC paths (`\\attacker.com\share`) are rejected with `UNTRUSTED_NETWORK_HOST`, and verifying private UNC shares launch within 1.0s.

**Acceptance Scenarios**:

1. **Given** an inbound message on `stdin` framed with a 4-byte native endian integer length prefix, **When** read by `folder_dispatcher.py`, **Then** the dispatcher reads in an accumulation loop until all 4 length bytes and payload bytes are retrieved from `sys.stdin.buffer` and decodes the UTF-8 JSON payload.
2. **Given** execution on Windows (`sys.platform == 'win32'`), **When** `folder_dispatcher.py` initializes, **Then** it sets `sys.stdin` and `sys.stdout` file descriptors to `os.O_BINARY` via `msvcrt.setmode` to ensure zero CRLF byte alteration.
3. **Given** an inbound path with a `file:///` scheme (e.g. `file:///C:/Users/Traveler/Photos`), **When** processed by the dispatcher, **Then** the dispatcher strips the scheme and decodes percent-encoded characters into canonical native format (`C:\Users\Traveler\Photos`).
4. **Given** an input path pointing to an external UNC network share (e.g. `\\evil-server.com\share`), **When** evaluated, **Then** the dispatcher rejects the host with `UNTRUSTED_NETWORK_HOST` to safeguard against NTLM authentication reflection.
5. **Given** an input path pointing to a private UNC share (e.g. `\\192.168.1.100\photos` or `\\nas.local\travel`), **When** evaluated, **Then** the dispatcher probes share reachability with a 1.0-second timeout thread; if responsive, it launches the folder; if unreachable, it returns `NETWORK_TIMEOUT`.
6. **Given** an input path containing prohibited shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`), **When** validated, **Then** the dispatcher immediately rejects the request and transmits `{"status": "error", "code": "ILLEGAL_CHARACTERS"}` over `sys.stdout.buffer` with 4-byte length framing and `flush()`.

---

### User Story 5 - User-Level Cross-Platform Native Host Registration Script (`register_native_host.py`) (Priority: P2)

A developer or traveler registers the native messaging host on Windows, macOS, or Linux by running `python scripts/register_native_host.py`. The script requires no administrator or root privileges: on Windows, it creates a batch launcher `run_dispatcher.bat` with `python -u` and writes to user registry key `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`; on macOS/Linux, it makes the dispatcher executable (`chmod +x`) and places the JSON manifest in the user's Chrome `NativeMessagingHosts` directory with `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]`.

**Why this priority**: Seamless user-level installation eliminates permission hurdles and ensures standard non-admin users can set up desktop integration effortlessly.

**Independent Test**: Can be fully tested by executing `python scripts/register_native_host.py --extension-id <ID>` on a standard non-admin user account, verifying the manifest and launcher files are created with absolute paths, and testing a round-trip ping message from the extension.

**Acceptance Scenarios**:

1. **Given** a Windows environment without administrator rights, **When** `register_native_host.py` runs, **Then** it generates `run_dispatcher.bat` invoking `python -u native_host/folder_dispatcher.py`, creates `com.vistarae.folder_opener.json` referencing the `.bat` launcher, and registers the manifest path in `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`.
2. **Given** a macOS environment, **When** `register_native_host.py` runs, **Then** it applies `chmod +x` to `folder_dispatcher.py` and copies the manifest to `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.vistarae.folder_opener.json`.
3. **Given** a Linux environment, **When** `register_native_host.py` runs, **Then** it applies `chmod +x` to `folder_dispatcher.py` and copies the manifest to `~/.config/google-chrome/NativeMessagingHosts/com.vistarae.folder_opener.json`.
4. **Given** the generated manifest, **When** inspected, **Then** it contains `"name": "com.vistarae.folder_opener"`, `"type": "stdio"`, absolute launcher path, and `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]`.

---

### User Story 6 - Full-Tab POI Explorer & Database Browser with CSV Export (Priority: P3)

A traveler opens the full-tab POI Explorer (`browser/browser.html`) from the extension toolbar or context menu. The traveler searches by keyword, filters by city/country, category tags, lists, or geographic proximity (via browser geolocation), edits POI details, deletes entries individually or in bulk, and exports filtered results to an RFC 4180 CSV spreadsheet.

**Why this priority**: Comprehensive catalog management in a dedicated browser tab provides an expansive workstation for reviewing saved destinations and generating offline travel spreadsheets.

**Independent Test**: Can be fully tested by opening `browser/browser.html`, applying filters, sorting table columns, editing a POI, and clicking "Export to CSV" to confirm that an RFC 4180 compliant spreadsheet downloads with all formula injection characters neutralized.

**Acceptance Scenarios**:

1. **Given** the user clicks the toolbar icon or context menu item "Browse Saved POIs", **When** triggered, **Then** the extension opens `browser/browser.html` in a new browser tab and populates the table via `GET /api/pois`.
2. **Given** the POI Explorer table, **When** the user applies filters (City, Country, Tag, List, Rating) or enters search keywords, **Then** the table updates instantly to display matching records.
3. **Given** filtered POI rows, **When** the user clicks "Export to CSV", **Then** the browser downloads an RFC 4180 compliant CSV file with formula characters (`=`, `+`, `-`, `@`) neutralized.
4. **Given** a user clicks "Reveal Folder" on a POI row with a local photo directory, **When** clicked, **Then** the extension calls the native host to open the local folder on disk.

---

### Edge Cases

- **Concurrent Token Refresh Race in MV3**: If two or more capture requests trigger while the JWT is within 5 minutes of expiration, the service worker binds them to a single in-flight `refreshPromise`, preventing parallel Cognito calls, token rotation conflicts, or redundant network roundtrips.
- **Windows Binary Framing CRLF Alteration**: If Python is executed without binary mode on Windows, newline characters `0x0A` in binary length prefixes or JSON strings are silently expanded to `0x0D 0x0A`. The dispatcher eliminates this by calling `msvcrt.setmode(..., os.O_BINARY)` on both standard descriptors and launching via `python -u`.
- **Fragmented Stdio Pipe Packets**: In heavy pipe traffic, standard input reads may return partial chunks. The dispatcher executes a `while len(accumulated) < target_length` loop for both the 4-byte prefix and the payload body to guarantee complete frame retrieval.
- **External UNC NTLM Hash Capture Attack**: If a malicious web script attempts to send `\\external-attacker.com\share` to trigger SMB authentication reflection, the dispatcher inspects the hostname and rejects non-private targets with `UNTRUSTED_NETWORK_HOST`.
- **Unresponsive or Offline UNC Shares**: If a private UNC share (e.g. `\\192.168.1.50\photos`) is offline, standard `os.path.exists` can hang for up to 30 seconds. The dispatcher executes the existence check in a worker thread guarded by a 1.0-second timeout, returning `NETWORK_TIMEOUT` if unresponsive.
- **Host Website Stacking Context & Max Z-Index**: If a host website uses extreme z-index values (`z-index: 2147483647`), the Shadow DOM container applies `z-index: 2147483647 !important` and mounts directly to `document.body` or `document.documentElement` to prevent occlusion.
- **Dynamic Content Script Injection on Pre-Existing Tabs**: If capture is triggered on a tab loaded before extension installation/reload, the service worker catches `"Receiving end does not exist"`, dynamically injects `content_script.js` via `chrome.scripting.executeScript`, and re-dispatches the capture trigger after 150ms.
- **Uninstalled Extension when Called from SPA**: If the SPA calls `chrome.runtime.sendMessage(EXTENSION_ID, ...)`, it wraps the call in a timeout and catches `chrome.runtime.lastError`, smoothly rendering an installation banner if the extension is not present.

---

## 3. Requirements *(mandatory)*

### Chrome Extension Core, Auth & Scraper Requirements (`REQ-EXT-xxx`)

- **REQ-EXT-001 (Ubiquitous):** The Chrome Extension manifest (`extension/manifest.json`) shall declare Manifest V3 (`manifest_version: 3`) with permissions for `activeTab`, `scripting`, `contextMenus`, `storage`, and `nativeMessaging`.
- **REQ-EXT-002 (Ubiquitous):** The Chrome Extension manifest shall declare scoped host permissions for:
  - AWS Cognito identity endpoints (`https://cognito-idp.*.amazonaws.com/*`)
  - Vistarae API Gateway and CloudFront origins (`https://*.cloudfront.net/*`)
  - Local development gateways (`http://localhost:8000/*`, `http://127.0.0.1:8000/*`, `http://localhost:8030/*`)
  - Target travel sites (`https://*.google.com/maps/*`, `https://*.roadtrippers.com/*`, `https://*.tripadvisor.com/*`, `https://*.atlasobscura.com/*`, `https://*.wikipedia.org/*`)
- **REQ-EXT-003 (Ubiquitous):** The Chrome Extension manifest shall declare an `"externally_connectable"` stanza matching `["https://*.cloudfront.net/*", "http://localhost:5173/*"]` allowing the Vistarae Single-Page Application (SPA) to send messages directly to the extension background service worker via `chrome.runtime.sendMessage`.
- **REQ-EXT-004 (Ubiquitous):** The Chrome Extension manifest shall declare a command shortcut `capture-to-vistarae` mapped to `Ctrl+Shift+S` on Windows/Linux and `Command+Shift+S` on macOS.
- **REQ-EXT-005 (Event-Driven):** When the extension is installed or updated (`chrome.runtime.onInstalled`), the background service worker shall register context menu items for "Capture to Vistarae (Ctrl+Shift+S)" (`contexts: ["selection", "page", "link"]`) and "Browse Saved POIs" (`contexts: ["all"]`).
- **REQ-EXT-006 (State-Driven):** While an authenticated user session is active, the extension shall persist the Cognito Access Token, ID Token, and `refresh_token` in `chrome.storage.local`.
- **REQ-EXT-007 (State-Driven):** While preparing to dispatch any authenticated API request, the background service worker shall inspect the JWT `exp` claim of the stored access token.
- **REQ-EXT-008 (Event-Driven):** When the stored access token is expired or within 5 minutes of expiration (`Date.now() / 1000 >= exp - 300`), the service worker shall silently call AWS Cognito `InitiateAuth` with `AuthFlow: "REFRESH_TOKEN_AUTH"` using the public App Client ID and update `chrome.storage.local` with the new tokens before dispatching the pending request.
- **REQ-EXT-008a (State-Driven):** While a token refresh operation is in flight, the background service worker shall maintain an in-memory `refreshPromise`; all concurrent capture or API requests detecting expiration shall await this identical promise without initiating parallel `InitiateAuth` requests to Cognito.
- **REQ-EXT-008b (Unwanted Behaviour):** If a silent token refresh fails due to transient network disconnection or an HTTP 5xx error from AWS Cognito, then the background service worker shall retain the existing `refresh_token` in `chrome.storage.local`, clear the active `refreshPromise`, and return an RFC 7807 network error to the capture overlay, enabling the traveler to retry without forcing re-authentication.
- **REQ-EXT-009 (Unwanted Behaviour):** If silent token refresh fails due to a revoked or invalid refresh token, then the service worker shall purge stored credentials from `chrome.storage.local` and trigger the capture overlay to render an in-page login form inside the Shadow DOM without losing the traveler's current selection.
- **REQ-EXT-010 (Ubiquitous):** Every mutation request (`POST`, `PUT`, `PATCH`, `DELETE`) dispatched to the backend by the background service worker shall attach an `Idempotency-Key` header with a newly generated UUIDv4.
- **REQ-EXT-011 (Ubiquitous):** Every outbound HTTP request dispatched by the background service worker shall inject W3C Trace Context headers:
  - `traceparent: 00-{trace_id}-{client_span_id}-01`
  - `X-Source: extension`
  - `X-Destination: backend`
- **REQ-EXT-012 (State-Driven):** While logging messages across extension boundaries, the service worker and content script loggers shall prefix console messages with exact microservice directional tags:
  - `MSG ->|  `: Inbound message received from content script, SPA, or tab
  - `MSG <-|  `: Response message returned to content script, SPA, or tab
  - `MSG   |->`: Outbound HTTP request dispatched to backend API or Cognito
  - `MSG   |<-`: Inbound HTTP response received from backend API or Cognito
- **REQ-EXT-013 (Ubiquitous):** The content script layer shall implement an object-oriented scraper architecture anchored by an abstract base parser class `BasePoiParser` defining contract methods `canParse(url: URL, document: Document): boolean` and `parse(document: Document, selection: string | null): ExtractedPoiData`.
- **REQ-EXT-014 (Ubiquitous):** The scraper registry shall implement `GoogleMapsParser` (inheriting from `BasePoiParser`) activating on Google Maps URLs (`google.com/maps`), extracting POI title from `h1.DUwDvf`, category from `button[jsaction*="category"]`, address from `button[data-item-id*="address"]`, coordinates from URL pathname (`@lat,lng,zoom` or `!3dlat!4dlng`), opening hours, and place photos.
- **REQ-EXT-015 (Ubiquitous):** The scraper registry shall implement `RoadtrippersParser` (inheriting from `BasePoiParser`) activating on `roadtrippers.com` domains, extracting waypoint titles, descriptions, category tags, and embedded coordinates from state/metadata attributes.
- **REQ-EXT-016 (Ubiquitous):** The scraper registry shall implement `TripAdvisorParser` (inheriting from `BasePoiParser`) activating on `tripadvisor.com` domains, extracting attraction/restaurant titles (`h1`), bubble ratings, street address, geocodes from embedded `schema.org/Place` JSON-LD, and review summaries.
- **REQ-EXT-017 (Event-Driven):** When the active webpage URL does not match specialized scrapers, the parsing dispatcher shall invoke `GenericSelectionParser` harvesting the selected text, canonical URL, document title, and OpenGraph metadata (`og:title`, `og:description`, `place:location:latitude`, `place:location:longitude`).
- **REQ-EXT-018 (Event-Driven):** When the user triggers capture via keyboard shortcut or context menu, the content script shall execute the appropriate parser and render the capture form inside an isolated open Shadow DOM container (`<vistarae-capture-root>`).
- **REQ-EXT-019 (Ubiquitous):** The in-page capture overlay shall encapsulate all modal DOM elements inside `<vistarae-capture-root>` with scoped styles (`overlay.css`) and CSS reset rule `all: initial` to eliminate host styling bleed.
- **REQ-EXT-020 (State-Driven):** While the capture overlay is active, the content script shall style the Shadow DOM root container with `position: fixed`, `top: 0`, `left: 0`, `width: 100vw`, `height: 100vh`, and `z-index: 2147483647` to maintain top-level stacking context over host page elements.
- **REQ-EXT-021 (Event-Driven):** When the user presses the `Escape` key or clicks outside the modal dialog, the content script shall dismiss the overlay and remove `<vistarae-capture-root>` from the document.
- **REQ-EXT-022 (Event-Driven):** When `sendMessageToTab` encounters a missing receiver error (`Receiving end does not exist` or `Could not establish connection`), the background service worker shall dynamically inject `content/content_script.js` via `chrome.scripting.executeScript` and retry the capture message after a 150ms delay.
- **REQ-EXT-023 (Event-Driven):** When text or page data is captured, the service worker shall dispatch `POST /api/pois/extract-and-check` using Google Gemini Flash-Lite (`thinking_budget: 0`) and OpenStreetMap Nominatim geocoding (1 req/s, PostGIS `geocache`).
- **REQ-EXT-024 (Event-Driven):** When candidate coordinates and name are resolved, the backend engine shall evaluate geodesic distance (`ST_DWithin` on `geography(Point, 4326)`) and trigram string similarity (`similarity(name, cand_name)`) against the user's POI collection, returning `UNIQUE_LOCATION`, `POTENTIAL_DUPLICATE`, or `NEARBY_PARENT`.
- **REQ-EXT-025 (Event-Driven):** When extraction returns a `POTENTIAL_DUPLICATE` classification (distance $\le$ 500ft, similarity $\ge 0.60$), the Shadow DOM overlay shall render a side-by-side comparison displaying distance, similarity percentage, existing POI attributes, and buttons to "Merge with Existing" or "Save as Distinct POI".
- **REQ-EXT-026 (Event-Driven):** When extraction returns a `NEARBY_PARENT` classification, the Shadow DOM overlay shall render an advisory banner offering 1-click parent nesting under the nearby macro-site.
- **REQ-EXT-027 (Event-Driven):** When the user clicks "Save to Vistarae", the service worker shall submit `POST /api/pois` with W3C trace headers and `Idempotency-Key`, display a success toast, and dismiss the overlay after 1.5 seconds.
- **REQ-EXT-028 (Event-Driven):** When the SPA (matching `"externally_connectable"`) calls `chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: directory_path })`, the background service worker `onMessageExternal` listener shall validate the action and invoke `chrome.runtime.sendNativeMessage('com.vistarae.folder_opener', { action: "open_folder", path: directory_path })`.
- **REQ-EXT-029 (Unwanted Behaviour):** If `chrome.runtime.sendNativeMessage` returns an error (e.g. native host not registered or binary missing), then the service worker shall return an RFC 7807 error payload `{"type": "native_host_not_found", "title": "Native Host Not Installed", "detail": "Run python scripts/register_native_host.py to register folder opener"}` to the calling SPA.
- **REQ-EXT-030 (Ubiquitous):** The extension shall provide a full-tab POI Explorer (`browser/browser.html`) accessible via toolbar action icon, context menu "Browse Saved POIs", or capture modal header link.
- **REQ-EXT-031 (Event-Driven):** When the user applies search keywords, geographic proximity filters (`navigator.geolocation`), or faceted filters (City, Country, Tag, List, Rating) in the POI Explorer, the table shall query `/api/pois` and render matching entries.
- **REQ-EXT-032 (Event-Driven):** When the user clicks "Export to CSV" in the POI Explorer, the browser shall export all currently filtered records into an RFC 4180 compliant CSV file with neutralized formula prefixes (`=`, `+`, `-`, `@`) and trigger a download.
- **REQ-EXT-033 (Event-Driven):** When the user clicks "Reveal Folder" on a POI row in the Explorer, the service worker shall dispatch `open_folder` to `com.vistarae.folder_opener` and report execution status via toast.

---

### Chrome Native Messaging Host & Registration Requirements (`REQ-NATIVE-xxx`)

- **REQ-NATIVE-001 (Ubiquitous):** The Native Messaging Host shall register with Google Chrome using the unique host identifier `com.vistarae.folder_opener` implemented in pure Python in `native_host/folder_dispatcher.py`.
- **REQ-NATIVE-002 (Ubiquitous):** The Native Messaging Host shall communicate exclusively over unbuffered binary standard input (`sys.stdin.buffer`) and standard output (`sys.stdout.buffer`) using Chrome's 4-byte native-endian unsigned integer framing (`struct.unpack('=I', ...)` and `struct.pack('=I', len(payload))` + `sys.stdout.buffer.flush()`).
- **REQ-NATIVE-002a (State-Driven):** While executing on Windows (`sys.platform == 'win32'`), `folder_dispatcher.py` shall explicitly invoke `msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)` and `msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)` to suppress CRLF translation, and the batch launcher `run_dispatcher.bat` shall invoke Python with the `-u` unbuffered flag.
- **REQ-NATIVE-002b (Ubiquitous):** The Native Messaging Host shall direct all diagnostic, debug, and error logs exclusively to `sys.stderr`, and shall strictly avoid writing unformatted text or stray characters to `sys.stdout` to preserve binary frame parsing integrity in Google Chrome.
- **REQ-NATIVE-003 (Event-Driven):** When receiving an incoming message on `stdin`, the Native Messaging Host shall read exactly 4 bytes to determine the message payload length in bytes.
- **REQ-NATIVE-003a (Event-Driven):** When reading byte streams from `sys.stdin.buffer`, the Native Messaging Host shall execute a chunked accumulation loop (`while len(chunk) < target`) until all requested bytes are retrieved, preventing message truncation from fragmented pipe packets.
- **REQ-NATIVE-004 (Unwanted Behaviour):** If `stdin` reads 0 bytes or encounters an end-of-file (EOF) condition, then the Native Messaging Host shall terminate execution cleanly with exit code 0.
- **REQ-NATIVE-005 (Event-Driven):** When the length prefix is parsed, the Native Messaging Host shall read the specified byte length from `stdin` and decode the UTF-8 JSON payload into an action dictionary.
- **REQ-NATIVE-006 (Unwanted Behaviour):** If the inbound payload cannot be decoded as valid UTF-8 JSON, then the Native Messaging Host shall transmit an error response `{"status": "error", "code": "MALFORMED_JSON", "message": "Failed to decode JSON payload"}` over `stdout` and await the next message.
- **REQ-NATIVE-007 (Event-Driven):** When an inbound message specifies `{"action": "ping"}`, the Native Messaging Host shall immediately return `{"status": "ok", "action": "pong", "version": "1.0.0", "platform": sys.platform}`.
- **REQ-NATIVE-008 (Event-Driven):** When an input `path` property begins with a `file:///` or `file://` scheme, the Native Messaging Host shall strip the file scheme and decode percent-encoded characters using `urllib.parse.unquote` into canonical native OS paths or UNC share paths before validation.
- **REQ-NATIVE-008a (Unwanted Behaviour):** If an input UNC network share path (`\\` or `//`) specifies an external or public internet host outside `localhost`, `127.0.0.1`, RFC 1918 private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), or `.local` domains, then the Native Messaging Host shall reject the request and return `{"status": "error", "code": "UNTRUSTED_NETWORK_HOST", "message": "External UNC hosts are prohibited to prevent NTLM reflection"}` over `stdout`.
- **REQ-NATIVE-009 (Unwanted Behaviour):** If an input `path` contains any shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`), then the Native Messaging Host shall immediately reject the request and return `{"status": "error", "code": "ILLEGAL_CHARACTERS", "message": "Prohibited shell metacharacters detected in path"}` over `stdout`.
- **REQ-NATIVE-010 (Unwanted Behaviour):** If an input `path` contains a null byte (`\0`), then the Native Messaging Host shall reject the request and return `{"status": "error", "code": "NULL_BYTE_DETECTED", "message": "Prohibited null byte in path"}` over `stdout`.
- **REQ-NATIVE-011 (Event-Driven):** When an input path passes character validation, the Native Messaging Host shall normalize the path using `os.path.realpath(os.path.expanduser(path))` and verify existence on the local filesystem or UNC network share using `os.path.exists()`.
- **REQ-NATIVE-011a (Event-Driven):** When verifying the existence of a UNC network share, the Native Messaging Host shall execute the check with a 1.0-second timeout guard; if the network host does not respond within 1.0 second, the host shall return `{"status": "error", "code": "NETWORK_TIMEOUT", "message": "UNC network share probe timed out"}` over `stdout`.
- **REQ-NATIVE-012 (Unwanted Behaviour):** If the target directory or UNC share does not exist on disk, then the Native Messaging Host shall return `{"status": "error", "code": "PATH_NOT_FOUND", "message": "Directory or share does not exist on disk"}` over `stdout`.
- **REQ-NATIVE-013 (Event-Driven):** When the target path points to an existing file rather than a directory, the Native Messaging Host shall resolve the containing parent directory (`os.path.dirname(target_path)`) before launching the file explorer.
- **REQ-NATIVE-014 (State-Driven):** While operating on Windows (`sys.platform == 'win32'`), the Native Messaging Host shall launch the native file explorer using `os.startfile(target_dir)` or `subprocess.Popen(["explorer.exe", target_dir], shell=False)`.
- **REQ-NATIVE-015 (State-Driven):** While operating on macOS (`sys.platform == 'darwin'`), the Native Messaging Host shall launch Finder using `subprocess.Popen(["open", target_dir], shell=False)`.
- **REQ-NATIVE-016 (State-Driven):** While operating on Linux (`sys.platform.startswith('linux')`), the Native Messaging Host shall launch the default desktop file manager using `subprocess.Popen(["xdg-open", target_dir], shell=False)`.
- **REQ-NATIVE-017 (Event-Driven):** When the native file manager process launches successfully, the Native Messaging Host shall pack a 4-byte length prefix and transmit `{"status": "ok", "action": "open_folder", "path": target_dir}` over `stdout`.
- **REQ-NATIVE-018 (Ubiquitous):** The repository shall provide an automated cross-platform installation script `scripts/register_native_host.py` capable of registering the native messaging host without requiring administrator or root privileges.
- **REQ-NATIVE-019 (State-Driven):** While running on Windows, `register_native_host.py` shall generate a batch launcher `native_host/run_dispatcher.bat` executing Python against `native_host/folder_dispatcher.py` with `python -u`, write `com.vistarae.folder_opener.json` with absolute paths and `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]`, and register the manifest path in the user registry under `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`.
- **REQ-NATIVE-020 (State-Driven):** While running on macOS or Linux, `register_native_host.py` shall apply execute permissions (`chmod +x`) to `native_host/folder_dispatcher.py`, write `com.vistarae.folder_opener.json` with absolute paths and `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]`, and place it in the user's Chrome `NativeMessagingHosts` folder (`~/Library/Application Support/Google/Chrome/NativeMessagingHosts/` on macOS, `~/.config/google-chrome/NativeMessagingHosts/` on Linux).

---

## 4. Key Entities & Communication Protocols

### 4.1 SPA-to-Extension-to-Native-Host Flow

```
+----------------------------------------------------------------------------------------------------+
|                                    COMMUNICATION FLOW ARCHITECTURE                                 |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Vistarae SPA Web App]                                                                            |
|  (localhost:5173 / cloudfront.net)                                                                 |
|         |                                                                                          |
|         | 1. chrome.runtime.sendMessage(EXTENSION_ID, { action: "open_folder", path: "/..." })    |
|         v                                                                                          |
|  [Chrome Extension Service Worker]                                                                 |
|  (manifest.json: "externally_connectable")                                                         |
|         |                                                                                          |
|         | 2. chrome.runtime.sendNativeMessage('com.vistarae.folder_opener', { ... })               |
|         v                                                                                          |
|  [Chrome Native Messaging Host]                                                                    |
|  (native_host/folder_dispatcher.py)                                                                |
|         |                                                                                          |
|         | 3. Unbuffered stdin (4-byte length prefix + UTF-8 JSON)                                  |
|         | 4. Security validation (reject shell chars ; & | ` $ > <, verify existence)              |
|         | 5. OS File Explorer spawn (os.startfile / explorer.exe / open / xdg-open)                  |
|         | 6. Unbuffered stdout (4-byte length prefix + UTF-8 JSON status response)                 |
|         v                                                                                          |
|  [OS Native File Manager Window Opens]                                                             |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

### 4.2 OOP Scraper Architecture

```
                       +---------------------------------------+
                       |             BasePoiParser             |
                       +---------------------------------------+
                       | + canParse(url, doc): boolean         |
                       | + parse(doc, selection): ExtractedPoi |
                       +---------------------------------------+
                                           ^
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
+-----------------------+       +-----------------------+       +-----------------------+
|   GoogleMapsParser    |       |   RoadtrippersParser  |       |   TripAdvisorParser   |
+-----------------------+       +-----------------------+       +-----------------------+
| - h1.DUwDvf (title)   |       | - waypoint metadata   |       | - h1 (title)          |
| - category button     |       | - state attributes    |       | - bubble rating       |
| - address button      |       | - coordinates state   |       | - schema.org/Place    |
| - URL @lat,lng coords |       | - category tags       |       | - review summaries    |
+-----------------------+       +-----------------------+       +-----------------------+
                                           |
                                           v
                               +-----------------------+
                               | GenericSelectionParser|
                               +-----------------------+
                               | - window.getSelection |
                               | - document.title      |
                               | - OpenGraph og:tags   |
                               +-----------------------+
```

---

### 4.3 Native Messaging Binary Framing Protocol

Chrome Native Messaging frames stdio with 32-bit (4-byte) integers in native byte order specifying message byte length:

```
+-----------------------------------+-------------------------------------------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Length Bytes (UTF-8 Encoded JSON String)  |
+-----------------------------------+-------------------------------------------+
| <------ 4-byte Native uint ------>| <------------ JSON Payload -------------> |
```

#### Binary Pack / Unpack Invariant (`folder_dispatcher.py`)
```python
# Windows stdio mode initialization:
if sys.platform == "win32":
    import msvcrt
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

# Exact-byte reading helper:
def read_exact(stream, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None  # Stream closed
        buf.extend(chunk)
    return bytes(buf)

# Reading from stdin:
raw_length = read_exact(sys.stdin.buffer, 4)
if raw_length is None:
    sys.exit(0)  # Clean stream termination
msg_len = struct.unpack('=I', raw_length)[0]
payload = read_exact(sys.stdin.buffer, msg_len).decode('utf-8')
data = json.loads(payload)

# Writing to stdout:
encoded = json.dumps(response).encode('utf-8')
sys.stdout.buffer.write(struct.pack('=I', len(encoded)))
sys.stdout.buffer.write(encoded)
sys.stdout.buffer.flush()
```

---

## 5. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **In-Page Capture & Scraper Latency**: The Shadow DOM capture overlay opens and displays extracted POI attributes within 200 milliseconds of triggering the shortcut on Google Maps, Roadtrippers, or TripAdvisor.
- **SC-002**: **Silent Token Refresh Reliability & Race Elimination**: 100% of pre-flight token checks identify tokens within 5 minutes of expiration and resolve concurrent requests through a single in-flight `refreshPromise` via Cognito `REFRESH_TOKEN_AUTH` without duplicate calls or user interruption.
- **SC-003**: **Zero CSS Style Bleed**: The capture overlay displays 0 CSS layout regressions across complex travel domains, guaranteed by open Shadow DOM encapsulation with `all: initial` reset.
- **SC-004**: **Native Folder Opener Launch Time**: The native host validates path security, normalizes URIs, and launches the native file manager window in under 150 milliseconds.
- **SC-005**: **Zero Command & UNC Injection Vulnerabilities**: 100% of malicious path injection test cases containing shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`) or external UNC hosts are rejected with `ILLEGAL_CHARACTERS` or `UNTRUSTED_NETWORK_HOST` without spawning shell processes.
- **SC-006**: **Strict Telemetry & Idempotency Compliance**: 100% of outbound mutation requests carry a valid UUIDv4 `Idempotency-Key` and W3C `traceparent` header, logging with directional tags (`MSG ->|  `, `MSG <-|  `, `MSG   |->`, `MSG   |<-`).
- **SC-007**: **Non-Admin Registration Success**: `register_native_host.py` successfully configures the host manifest and registry/config files on standard non-admin accounts across Windows, macOS, and Linux in under 3 seconds.
- **SC-008**: **SPA Bridge Graceful Degradation**: 100% of folder opener calls from the SPA web client either launch the local folder or surface an actionable setup toast banner without throwing unhandled exceptions.

---

## 6. Assumptions & Dependencies

- **Host Browser**: Google Chrome 116+ (or Chromium-based equivalents supporting Manifest V3 and Native Messaging).
- **Backend Services**: Vistarae backend services (`services/user`, `services/poi`, `services/local_gateway`) are running locally on port 8000 or accessible via CloudFront.
- **AWS Cognito**: Public App Client ID configured with `REFRESH_TOKEN_AUTH` enabled for silent token refresh.
- **Python Runtime**: Python 3.10+ installed on the host system and accessible for executing `native_host/folder_dispatcher.py`.
- **Supported Operating Systems**: Windows 10/11 (64-bit), macOS 12+ (Monterey or later), and modern Linux desktop environments with `xdg-open` (Ubuntu 22.04+, Fedora 38+).
