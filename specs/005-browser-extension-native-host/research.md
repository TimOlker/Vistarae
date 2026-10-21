# Architectural Research: Phase 5 — Manifest V3 Browser Extension & Native Messaging Host

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)

---

## 1. Executive Research Summary

Phase 5 introduces the desktop bridge and web capture tier of Vistarae. The primary architectural challenges span:

1. **Manifest V3 Ephemeral Service Worker Lifecycle & Concurrency**: Service workers in Chrome Manifest V3 do not run persistently; they are terminated when idle (~30 seconds) and awakened by events. Multiple asynchronous requests occurring concurrently during token expiration (`exp - 300s`) can trigger parallel refresh requests unless serialized by an in-flight promise mutex.
2. **In-Page Isolation via Open Shadow DOM**: Host websites possess wildly varied, aggressive global CSS styles (`* { color: red !important; }`, CSS resets, high z-indexes). True visual isolation demands an encapsulated Shadow DOM container (`<vistarae-capture-root>`) with scoped stylesheets and `all: initial` resets.
3. **OOP Scraper Registry**: Specialized parsers are required for high-value travel platforms (Google Maps, Roadtrippers, TripAdvisor) alongside a generic OpenGraph/DOM fallback.
4. **Binary Standard I/O Framing on Windows**: Chrome Native Messaging uses 4-byte native-endian binary integer length prefixes. On Windows, standard streams perform CRLF translation (`\r\n` vs `\n`) unless explicitly forced to `os.O_BINARY` via `msvcrt.setmode`. Furthermore, reading standard input must loop until the exact byte count is accumulated to prevent pipe fragmentation issues.
5. **UNC Network Share Security (NTLM Reflection Prevention)**: Windows file explorers can connect to UNC paths (`\\server\share`). Permitting arbitrary public internet hostnames allows NTLM hash capture attacks. The native host must enforce an allowlist restricting UNC paths to loopback, RFC 1918 private subnets, and `.local` domains, probed with a 1.0s timeout thread.
6. **Non-Admin Cross-Platform Registration**: Installing a native messaging host typically requires registry access on Windows or directory permissions on macOS/Linux. Using `HKCU` on Windows and user-level `~/Library/Application Support/...` or `~/.config/...` on macOS/Linux eliminates administrator/root permission requirements.

---

## 2. Research Decisions & Findings

### Decision 1: Manifest V3 Concurrency Mutex & Silent Token Refresh

- **Decision**: Implement an in-memory `refreshPromise: Promise<string> | null` singleton in the background service worker. When any capture or API request detects that the cached access token is expired or within 5 minutes of expiration (`Date.now() / 1000 >= exp - 300`), it initiates or awaits `refreshPromise`.
- **Rationale**:
  - AWS Cognito token refresh (`InitiateAuth` with `REFRESH_TOKEN_AUTH`) rotates or returns fresh token pairs. Simultaneous calls with the same refresh token can cause race condition errors (`InvalidParameterException` / `NotAuthorizedException`).
  - An in-memory promise deduplicates concurrent in-flight refresh requests from multiple browser tabs into exactly one network round-trip.
  - The promise resolves, updates `chrome.storage.local`, and clears itself in a `finally` block.
  - If the service worker is terminated while idle, memory is freed cleanly; the next wakeup reads the persistent tokens from `chrome.storage.local` and executes a fresh check.
  - Transient network failures retain the refresh token and emit an RFC 7807 error, while permanent 400/401 errors clear storage and present the in-page login form.
- **Alternatives Considered**:
  - _Queue-and-Drain Serialization_: Overly complex; introduces artificial delays for non-mutating calls.
  - _Periodic Chrome Alarms (e.g. every 45 min)_: Unreliable because alarms can be throttled when the browser is suspended or laptops enter sleep mode, leading to stale tokens during sudden user activity.

---

### Decision 2: In-Page Encapsulation & Dynamic Injection Architecture

- **Decision**: Construct an open Shadow DOM root on custom element `<vistarae-capture-root>` appended directly to `document.body` or `document.documentElement` with `position: fixed`, `top: 0`, `left: 0`, `width: 100vw`, `height: 100vh`, `z-index: 2147483647`, and CSS reset `all: initial`.
- **Rationale**:
  - Host website CSS cannot penetrate an open Shadow DOM root, shielding the Vistarae capture modal from aggressive global styling rules, CSS resets, or framework overrides.
  - `overlay.css` is injected directly into the shadow root via a `<style>` element or constructed stylesheet, keeping modal styles completely isolated.
  - The maximum 32-bit signed integer z-index (`2147483647`) guarantees that the capture overlay sits atop modals, sticky headers, or full-screen canvas elements on host sites.
  - Dynamic injection: If a user triggers capture on a tab loaded prior to extension install/reload, the background worker catches `"Receiving end does not exist"` and calls `chrome.scripting.executeScript({ target: { tabId }, files: ["content/content_script.js"] })` before re-dispatching the message.
- **Alternatives Considered**:
  - _`<iframe>` Injection_: Heavyweight; creates separate browsing contexts with cross-origin sandbox restrictions, blocking keyboard focus traps, selection access, and dark mode synchronization.
  - _Direct DOM Injection with Prefix Classes_: Susceptible to global CSS leakage (e.g., `* { box-sizing: border-box !important; color: red !important; }`), causing visual breakage.

---

### Decision 3: Object-Oriented Parser Registry (`BasePoiParser`)

- **Decision**: Structure DOM content extractors into an object-oriented hierarchy:
  - `BasePoiParser`: Abstract base class with contract methods `canParse(url, doc)` and `parse(doc, selection)`.
  - `GoogleMapsParser`: Parses `google.com/maps` targeting `h1.DUwDvf`, category button, address button, coordinates from URL (`/@(-?\d+\.\d+),(-?\d+\.\d+)` or `!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)`), and photos.
  - `RoadtrippersParser`: Parses `roadtrippers.com` targeting waypoint attributes, route cards, and coordinates.
  - `TripAdvisorParser`: Parses `tripadvisor.com` targeting `h1`, bubble ratings, and embedded `schema.org/Place` JSON-LD metadata.
  - `GenericSelectionParser`: Fallback extractor parsing `window.getSelection()`, `document.title`, OpenGraph tags (`og:title`, `og:description`), and geo tags (`place:location:latitude`).
- **Rationale**:
  - Encapsulates site-specific DOM query logic into isolated, testable modules.
  - Allows adding new platform scrapers (e.g. AllTrails, Atlas Obscura) in the future without modifying core capture orchestration.
  - Enables fallback to generic AI entity extraction when site-specific DOM selectors change or fail.
- **Alternatives Considered**:
  - _Monolithic procedural parser_: Hard to maintain; selector changes on one site risk breaking extraction on other sites.

---

### Decision 4: Windows Binary stdio Framing & Diagnostic Isolation

- **Decision**:
  - In `folder_dispatcher.py`, immediately check `if sys.platform == "win32":` and invoke:
    ```python
    import msvcrt, os
    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    ```
  - Launch Python with `-u` (unbuffered) in `run_dispatcher.bat`.
  - Implement an exact-byte accumulation read helper:
    ```python
    def read_exact(stream, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = stream.read(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)
    ```
  - Standard error isolation: Direct all diagnostic logs exclusively to `sys.stderr`. Never execute unformatted `print()` statements to `sys.stdout`.
- **Rationale**:
  - On Windows, standard C runtime stdio converts newline characters `0x0A` to `0x0D 0x0A` in text mode. In Chrome Native Messaging, binary integer length headers (e.g. length `10` = `0x0A 0x00 0x00 0x00`) or raw JSON strings containing `\n` become corrupted, causing Chrome to immediately kill the native host.
  - Pipe reads in Windows can deliver chunks smaller than the requested size. An accumulation loop guarantees exact frame boundary retrieval.
  - Google Chrome redirects anything written to `sys.stderr` to the browser's console/error log without disrupting the native messaging protocol on `sys.stdout`.
- **Alternatives Considered**:
  - _Direct `os.read(0, n)`_: Viable, but standard library `sys.stdin.buffer` with `msvcrt.setmode` is more idiomatic across Python platforms while retaining buffering control.

---

### Decision 5: UNC Network Share Allowlist & NTLM Reflection Prevention

- **Decision**: Restrict UNC paths (`\\server\share` or `//server/share`) to private network entities:
  - Normalize slashes (`//` to `\\` on Windows).
  - Extract the hostname/IP component.
  - Verify that the host is:
    - `localhost` or `127.0.0.1`
    - A valid private IPv4 address under RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) or loopback
    - A `.local` mDNS / intranet domain name
  - Reject any public internet domain name (e.g. `\\attacker.com\share`) with `UNTRUSTED_NETWORK_HOST`.
  - Non-blocking probe: Probe `os.path.exists()` in a worker thread with a 1.0-second timeout; if the SMB server is unresponsive, return `NETWORK_TIMEOUT` instead of hanging the process.
- **Rationale**:
  - In Windows, accessing an untrusted external UNC path automatically triggers SMB negotiation, transmitting the logged-in user's NetNTLMv2 challenge-response hash to the remote server (NTLM capture / reflection attack).
  - Slow or offline network shares can cause `os.path.exists()` to hang for 30–60 seconds, which would freeze the Chrome Native Messaging channel.
- **Alternatives Considered**:
  - _Disallow all UNC shares_: Breaks valid traveler workflows who store photo libraries on local NAS devices (`\\synology.local\photos`).
  - _Unrestricted UNC_: Severe security risk allowing NTLM credential harvesting from malicious websites.

---

### Decision 6: User-Level Cross-Platform Registration (`register_native_host.py`)

- **Decision**: Provide `scripts/register_native_host.py` that writes manifests directly into user-scoped locations:
  - **Windows**:
    - Generates `native_host/run_dispatcher.bat`:
      ```batch
      @echo off
      python -u "%~dp0folder_dispatcher.py" %*
      ```
    - Writes `native_host/com.vistarae.folder_opener.json` pointing to `run_dispatcher.bat`.
    - Writes Registry string value `(Default)` pointing to the JSON manifest in:
      `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`
  - **macOS**:
    - Applies `chmod +x native_host/folder_dispatcher.py`.
    - Copies manifest pointing directly to `folder_dispatcher.py` into:
      `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.vistarae.folder_opener.json`
  - **Linux**:
    - Applies `chmod +x native_host/folder_dispatcher.py`.
    - Copies manifest into:
      `~/.config/google-chrome/NativeMessagingHosts/com.vistarae.folder_opener.json`
- **Rationale**:
  - Writing to `HKCU` (HKEY_CURRENT_USER) on Windows and the user's home config directory on macOS/Linux requires zero administrator/root elevation (UAC prompt), enabling instant setup in developer environments and standard user profiles.
  - Manifest includes `"allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]` to prevent unauthorized extensions from accessing the local folder opener.
- **Alternatives Considered**:
  - _System-wide registration (`HKLM` / `/Library/...`)_: Requires administrator privileges and breaks on restricted enterprise machines.
