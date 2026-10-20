# Chrome Extension (Manifest V3) & Native Messaging Host Setup

**Feature**: `005-browser-extension-native-host`  
**License**: Apache-2.0  
**Copyright**: (c) 2026 Tim Olker

---

## 1. Overview

Phase 5 of Vistarae equips travelers with:

1. **Manifest V3 Chrome Extension (`extension/`)**:
   - In-page web POI capture overlay (`Ctrl+Shift+S` / `Command+Shift+S` or right-click Context Menu) isolated via Shadow DOM (`<vistarae-capture-root>`).
   - Object-Oriented specialized scrapers for **Google Maps**, **Roadtrippers**, and **TripAdvisor**, with general web OpenGraph fallback.
   - Pre-flight silent JWT token refresh via AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`) with an in-memory single-flight promise mutex.
   - Full-tab POI Explorer (`browser/browser.html`) with real-time keyword search, category filters, geolocation proximity, and formula-injection-safe RFC 4180 CSV export.
2. **Chrome Native Messaging Host (`native_host/` & `scripts/register_native_host.py`)**:
   - Pure Python stdio dispatcher (`folder_dispatcher.py`) with 4-byte native-endian binary framing.
   - Strict Windows binary stream mode (`msvcrt.setmode` with `os.O_BINARY`) and launcher unbuffered flag (`python -u`).
   - Rejection of shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`, `\0`).
   - Private network allowlist and 1.0s timeout probe on UNC shares to eliminate NTLM reflection attacks.
   - User-level registration script without requiring administrator or root rights.

---

## 2. Installation & Quickstart

### Step 1: Register Native Messaging Host

From the repository root, run the user-level setup script:

```bash
python scripts/register_native_host.py
```

To register a custom or development Extension ID:

```bash
python scripts/register_native_host.py --extension-id <YOUR_CHROME_EXTENSION_ID>
```

To uninstall:

```bash
python scripts/register_native_host.py --uninstall
```

### Step 2: Load Unpacked Extension in Chrome

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** toggle in the top-right corner.
3. Click **Load unpacked** in the top-left toolbar.
4. Select the `extension/` folder in the Vistarae repository root (`D:\Coding\Vistarae\extension`).
5. Confirm the extension appears as **Vistarae — POI & Travel Capture Engine**.

### Step 3: Verify Capture & Scrapers

1. Open any travel page (e.g. Google Maps, Roadtrippers, TripAdvisor, or Wikipedia).
2. Press `Ctrl+Shift+S` (or `Command+Shift+S` on macOS).
3. The isolated Shadow DOM capture overlay opens automatically with pre-extracted POI fields.
4. Press `Ctrl+Enter` or click **Save to Vistarae** to commit to your travel collection.

### Step 4: Open POI Explorer Workstation

1. Click the Vistarae toolbar icon or right-click anywhere and select **Browse Saved POIs**.
2. Filter by category, search by destination name, or sort by proximity.
3. Click **Reveal Folder** on any POI with a local photo directory to launch the native operating system file manager window.
4. Click **Export to CSV** to download a sanitized RFC 4180 spreadsheet.

---

## 3. Automated Testing

Run the full Python native host test suite with coverage:

```bash
.venv\Scripts\python -m pytest tests/unit/native_host/test_folder_dispatcher.py tests/unit/scripts/test_register_native_host.py -v
```

Run the extension Vitest unit test suite:

```bash
cd frontend && npm run test:unit -- src/tests/extension/
```
