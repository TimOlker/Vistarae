# Implementation Plan: Phase 5 — Manifest V3 Browser Extension & Native Messaging Host

**Branch**: `005-browser-extension-native-host` | **Date**: 2026-10-20 | **Spec**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)  
**Input**: Feature specification from `specs/005-browser-extension-native-host/spec.md`  
**Constitution**: [.specify/memory/constitution.md](file:///d:/Coding/Vistarae/.specify/memory/constitution.md)

---

## 1. Summary

Phase 5 delivers the web capture interface and native desktop integration tier for the Vistarae platform:

1. **Manifest V3 Chrome Extension (`extension/`)**:
   - Manifest V3 architecture with `"nativeMessaging"`, scoped host permissions for Cognito and CloudFront/API Gateway origins, and `"externally_connectable": { "matches": ["https://*.cloudfront.net/*", "http://localhost:5173/*"] }` for SPA web app communication.
   - Secure token storage (`chrome.storage.local`) with pre-flight `exp` claim checks and a single-flight mutex (`refreshPromise`) silently renewing tokens via AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`), eliminating multi-tab race conditions.
   - An object-oriented scraper registry based on abstract `BasePoiParser` with inherited specialized parsers for **Google Maps** (`GoogleMapsParser`), **Roadtrippers** (`RoadtrippersParser`), and **TripAdvisor** (`TripAdvisorParser`), plus generic fallback.
   - Isolated in-page capture overlay inside an open Shadow DOM container (`<vistarae-capture-root>`) with reset styles (`all: initial`) and scoped styling (`overlay.css`), triggered by `Ctrl+Shift+S` / `Command+Shift+S` or Context Menu.
   - Backend extraction via Google Gemini Flash-Lite (`thinking_budget: 0`), OpenStreetMap Nominatim geocoding (1 req/s, PostGIS `geocache`), and real-time spatial deduplication (`UNIQUE_LOCATION`, `POTENTIAL_DUPLICATE` side-by-side comparison, `NEARBY_PARENT` nesting).
   - Full-tab catalog workstation (`browser/browser.html`) with live filtering, geoproximity search, inline editing, bulk deletion, and RFC 4180 CSV export with formula injection neutralization.
2. **Chrome Native Messaging Local Folder Subsystem (`native_host/` & `scripts/register_native_host.py`)**:
   - SPA-to-Extension-to-Host bridge forwarding `open_folder` messages from `localhost:5173` or CloudFront to `com.vistarae.folder_opener` with graceful degradation to an installation toast.
   - Pure Python dispatcher (`native_host/folder_dispatcher.py`) communicating over unbuffered binary standard I/O with 4-byte native endian integer framing. Enforces `msvcrt.setmode(..., os.O_BINARY)` on Windows, reads via an exact-byte accumulation loop (`read_exact`), isolates logs to `sys.stderr`, normalizes `file:///` URIs, rejects shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`), restricts UNC network shares to private subnets with a 1.0s timeout probe (preventing NTLM reflection attacks), and launches native file managers (`os.startfile`, `xdg-open`, `open`) without `shell=True`.
   - Cross-platform user-level registration script (`scripts/register_native_host.py`) configuring Windows Registry (`HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`) and macOS/Linux `NativeMessagingHosts` directories without requiring administrator or root privileges.

---

## 2. Technical Context

- **Language/Version**: JavaScript (ES2022) for Chrome Extension; Python 3.10+ for Native Messaging Host and registration tooling
- **Primary Dependencies**:
  - Chrome Extension: Pure Vanilla JavaScript, Modern Web Platform APIs (`crypto.subtle`, `fetch`, `chrome.storage`, `chrome.runtime`, `chrome.contextMenus`, `chrome.commands`, `chrome.scripting`, Shadow DOM v1), zero heavy runtime frameworks.
  - Native Host: Python Standard Library (`sys`, `os`, `struct`, `json`, `subprocess`, `urllib.parse`, `ipaddress`, `platform`, `winreg` on Windows, `msvcrt` on Windows) — zero external pip packages required on user machines.
- **Storage**:
  - `chrome.storage.local`: Access Token, ID Token, Refresh Token, user profile summary
  - `chrome.storage.sync`: `backendUrl` override (default: `http://localhost:8000`)
- **Testing**:
  - Unit tests for Python native host (`tests/unit/native_host/test_folder_dispatcher.py`, `tests/unit/scripts/test_register_native_host.py`) using `pytest` with $\ge 90\%$ branch and line coverage enforcement.
  - Mock DOM and parser unit tests for extension scrapers and binary framing helpers.
- **Target Platform**:
  - Google Chrome 116+ (or Chromium-based equivalents: Brave, Edge, Opera)
  - Desktop OS: Windows 10/11 (64-bit), macOS 12+ (Monterey or later), Linux (Ubuntu 22.04+, Fedora 38+)
- **Project Type**: Manifest V3 Browser Extension + Pure Python Native Messaging Host CLI
- **Performance Goals**:
  - In-Page Capture & Scraper Latency: $< 200$ milliseconds
  - Native Folder Opener Launch Time: $< 150$ milliseconds
  - End-to-End Extraction & Geocoding: $< 2.5$ seconds
  - Registration execution time: $< 3.0$ seconds
- **Constraints**:
  - Zero administrator / root elevation required for registration or host execution
  - Zero unformatted writes to `sys.stdout` in native host (preserves binary framing)
  - Zero shell injection vulnerabilities (rejection of shell metacharacters `;&|`$><`)
  - Strict W3C distributed tracing propagation on all outbound HTTP requests (`traceparent`, `X-Source: extension`, `X-Destination: backend`)
  - Mandatory UUIDv4 `Idempotency-Key` headers on all mutation requests
  - Standardized copyright header banner (`// Copyright (c) 2026 Tim Olker...` on JS/TS, `# Copyright (c) 2026 Tim Olker...` on Python)
- **Scale/Scope**: 50,000+ Extension installations, collections up to 2,000 POIs rendered in full-tab browser.

---

## 3. Constitution Check

_GATE: Verified prior to research and re-evaluated post-design against `.specify/memory/constitution.md`._

| Constitutional Invariant           |  Status  | Compliance Detail                                                                                                                                                                                                                                                                           |
| :--------------------------------- | :------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------- | ------- | --------- | ----- |
| **1. File Header & Pre-Commit**    | **PASS** | Every `.py` file starts with `# Copyright (c) 2026 Tim Olker...` and `.js` file with `// Copyright (c) 2026 Tim Olker...` under Apache-2.0. Pre-commit validates `ruff check`, `ruff format`, `prettier`, and `check-copyright-header`. Max nesting $\le 3$, cognitive complexity $\le 15$. |
| **2. Monorepo & Ports/Adapters**   | **PASS** | `native_host/` and `scripts/` are standalone Python modules with zero circular imports. `extension/` communicates with backend exclusively over REST via `services.local_gateway` or CloudFront API Gateway.                                                                                |
| **3. Database & Tenancy**          | **PASS** | Extension and native host have no direct database connections. Extension authenticates via Cognito JWT Bearer tokens to FastAPI gateway. All backend queries enforce tenant isolation `WHERE user_id = :current_user_id`.                                                                   |
| **4. Alembic & Environment**       | **PASS** | No database schema modifications or migrations required for Phase 5.                                                                                                                                                                                                                        |
| **5. API Contract & Validation**   | **PASS** | Outbound requests match OpenAPI specifications (`/api/pois/extract-and-check`, `/api/pois`, `/api/auth/login`, `/api/auth/register`). All error handling maps RFC 7807 `ProblemDetails`.                                                                                                    |
| **6. Middleware & Security**       | **PASS** | All mutating operations (`POST`, `PUT`, `DELETE`) supply UUIDv4 `Idempotency-Key` headers. CORS configured for extension origins. Native host rejects shell metacharacters and non-private UNC paths.                                                                                       |
| **7. Observability & Tracing**     | **PASS** | Service worker generates W3C `traceparent` headers (`00-{trace_id}-{client_span_id}-01`) and sets `X-Source: extension`, `X-Destination: backend`. Directional microservice message tags (`MSG ->                                                                                           | `, `MSG <-                  | `, `MSG | ->`, `MSG | <-`). |
| **8. PyTest & SDD Governance**     | **PASS** | Unit tests cover `folder_dispatcher.py` and `register_native_host.py` with $\ge 90\%$ branch and line coverage (`--cov-fail-under=90`). Implementation plan strictly derived from ratified `spec.md`.                                                                                       |
| **Operational & Infrastructure 3** | **PASS** | Native host (`com.vistarae.folder_opener`) communicates over unbuffered standard I/O using 4-byte native endian integer framing (`struct.unpack('=I', ...)`, `struct.pack('=I', ...)`). Rejects shell metacharacters (`;`, `&`, `                                                           | `, `` ` ``, `$`, `>`, `<`). |

---

## 4. Project Structure

### 4.1 Documentation (Phase 5)

```text
specs/005-browser-extension-native-host/
├── spec.md                 # Requirements & Architecture Specification
├── plan.md                 # This implementation plan
├── research.md             # Research decisions & architectural findings
├── data-model.md           # Storage schemas, state machines & entity definitions
├── quickstart.md           # Step-by-step verification guide & automated test scenarios
├── checklists/
│   └── requirements.md     # Specification quality validation checklist
└── contracts/
    ├── extension-contracts.md   # External connectable & internal messaging contracts
    └── native-host-contract.md  # Binary framing & host error code catalog
```

### 4.2 Source Code Layout

```text
extension/
├── manifest.json                     # Manifest V3 configuration with nativeMessaging & externally_connectable
├── background/
│   └── service_worker.js             # W3C trace injection, silent token refresh mutex, API dispatcher, native host bridge
├── content/
│   ├── content_script.js             # Keyboard/context listener & Shadow DOM modal injector
│   ├── overlay.css                   # Scoped styles for in-page capture overlay
│   └── parsers/
│       ├── BasePoiParser.js          # Abstract base class defining canParse and parse contract
│       ├── GoogleMapsParser.js       # Specialized extractor for google.com/maps POIs
│       ├── RoadtrippersParser.js     # Specialized extractor for roadtrippers.com waypoints
│       ├── TripAdvisorParser.js      # Specialized extractor for tripadvisor.com attractions/restaurants
│       └── GenericSelectionParser.js # General web fallback parsing selection & OpenGraph tags
├── browser/
│   ├── browser.html                  # Full-tab POI Explorer & Database Browser UI
│   ├── browser.css                   # Responsive styles and dark/light theme variables
│   └── browser.js                    # Catalog browsing, filtering, search, CSV export, and folder opening
└── icons/
    ├── icon16.png                    # Extension toolbar icon (16x16)
    ├── icon48.png                    # Extension management icon (48x48)
    └── icon128.png                   # Web store / installation icon (128x128)

native_host/
├── folder_dispatcher.py              # Pure Python unbuffered binary stdio dispatcher with UNC & shell guards
├── run_dispatcher.bat                # Windows batch launcher executing python -u folder_dispatcher.py
└── com.vistarae.folder_opener.json   # Native Messaging Host manifest template

scripts/
└── register_native_host.py           # Cross-platform non-admin setup script (Windows Registry, macOS/Linux config)

tests/
├── unit/
│   ├── native_host/
│   │   ├── __init__.py
│   │   └── test_folder_dispatcher.py # Framing, shell metacharacters, UNC security & error code tests
│   └── scripts/
│       ├── __init__.py
│       └── test_register_native_host.py # Cross-platform manifest generation & registry mock tests
```

---

## 5. Complexity Tracking

> **No constitutional violations detected. All components adhere strictly to project principles.**

| Design Element                      | Why Needed                                                                   | Alternative Rejected                                                                                                    |
| :---------------------------------- | :--------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| **`msvcrt.setmode` on Windows**     | Suppresses CRLF byte expansion on binary stdio streams                       | Direct text-mode Python stdio fails on byte `0x0A` (`\n`), corrupting length prefixes and terminating native host       |
| **Single-Flight Token Mutex**       | Prevents concurrent Cognito refresh calls from multiple tabs near expiration | Uncoordinated refresh causes race condition errors (`InvalidParameterException`) and invalidates rotated refresh tokens |
| **User-Level Registry / Host Path** | Installs without administrator or root privileges                            | System-wide registration (`HKLM`) triggers UAC prompts and fails on non-admin developer/traveler accounts               |
