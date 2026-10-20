# Quickstart & Verification Guide: Phase 5 — Browser Extension & Native Host

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Status**: Ready for Implementation  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)

---

## 1. Prerequisites

Before verifying Phase 5, ensure your local development stack is running:

```powershell
# 1. Start local PostGIS and ElasticMQ
docker compose up -d

# 2. Run database migrations
uv run alembic upgrade head

# 3. Start the FastAPI local gateway
uv run uvicorn services.local_gateway:app --reload --port 8000
```

Verify the API is accessible at [http://localhost:8000/health/ready](http://localhost:8000/health/ready).

---

## 2. Register the Native Messaging Host

Run the cross-platform non-admin setup script to register `com.vistarae.folder_opener`:

```powershell
# On Windows (PowerShell):
python scripts/register_native_host.py --extension-id <YOUR_EXTENSION_ID>
```

On Windows, the script will:
1. Generate `native_host/run_dispatcher.bat` invoking `python -u native_host/folder_dispatcher.py`.
2. Generate `native_host/com.vistarae.folder_opener.json` with the absolute path to the `.bat` launcher.
3. Register the manifest path in the Windows Registry under `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vistarae.folder_opener`.

To verify host registration without Chrome:
```powershell
python tests/unit/native_host/test_folder_dispatcher.py
```

---

## 3. Load the Extension into Google Chrome

1. Open **Google Chrome** and navigate to `chrome://extensions/`.
2. Toggle on **Developer mode** in the upper-right corner.
3. Click **Load unpacked** in the top-left toolbar.
4. Select the `extension/` directory from this repository:
   ```text
   D:\Coding\Vistarae\extension
   ```
5. Copy the generated **Extension ID** (a 32-character string like `abcdefghijklmnop...`).
6. Re-run the registration script with your actual ID if needed:
   ```powershell
   python scripts/register_native_host.py --extension-id <COPIED_EXTENSION_ID>
   ```
7. Click the Chrome Extensions puzzle icon (🧩) and pin **Vistarae - Travel POI Capture** to your toolbar.

---

## 4. End-to-End Verification Scenarios

### Scenario 1: Google Maps POI Capture (`GoogleMapsParser`)

1. Open Google Chrome and navigate to any place on Google Maps, e.g. [Yosemite National Park on Google Maps](https://www.google.com/maps/place/Yosemite+National+Park).
2. Press **`Ctrl+Shift+S`** (Windows) or **`Command+Shift+S`** (macOS).
3. **Verify**:
   - The `<vistarae-capture-root>` modal overlay opens smoothly in the center of the viewport within 200ms.
   - Form fields for Name, Category, Address, and Coordinates are automatically pre-populated without manual text selection.
   - The modal styling is completely unaffected by Google Maps CSS.
4. Adjust the star rating and click **Save to Vistarae**.
5. **Verify**: A success toast appears, the overlay dismisses, and the record is stored in PostGIS.

---

### Scenario 2: Roadtrippers & TripAdvisor OOP Parsing

1. Navigate to a waypoint page on `roadtrippers.com` or an attraction page on `tripadvisor.com`.
2. Press **`Ctrl+Shift+S`**.
3. **Verify**:
   - On Roadtrippers: `RoadtrippersParser` extracts waypoint title, description, and coordinates.
   - On TripAdvisor: `TripAdvisorParser` extracts business name, bubble rating, and address from JSON-LD.

---

### Scenario 3: Silent Token Refresh & Race Elimination

1. In Chrome DevTools for the service worker (`chrome://extensions` $\rightarrow$ click "service worker" link), inspect network activity.
2. Manually set a mock token in `chrome.storage.local` with an `exp` timestamp 2 minutes in the future.
3. Trigger two capture requests simultaneously across two tabs.
4. **Verify**:
   - DevTools network logs show exactly **one** call to AWS Cognito `InitiateAuth` (`REFRESH_TOKEN_AUTH`).
   - Both capture requests await the single in-flight promise and succeed with fresh tokens.
   - Both requests attach unique UUIDv4 `Idempotency-Key` headers and W3C `traceparent` headers.

---

### Scenario 4: SPA-to-Extension Native Folder Opening

1. Open the Vistarae SPA at [http://localhost:5173](http://localhost:5173).
2. On any POI card with a local folder path, click **Open Photo Directory**.
3. **Verify**:
   - The Windows File Explorer (or Finder / xdg-open) opens immediately highlighting the local folder.
   - In an incognito window without the extension, clicking the button displays the setup banner toast.

---

### Scenario 5: Security Guardrails Verification (Shell Metacharacters & UNC)

1. Run the automated test suite targeting the native messaging host:
   ```powershell
   uv run pytest tests/unit/native_host/test_folder_dispatcher.py -v
   ```
2. **Verify**:
   - Input paths containing `;`, `&`, `|`, `$`, `>`, `<` are rejected with `ILLEGAL_CHARACTERS`.
   - External UNC paths (`\\attacker.com\share`) are rejected with `UNTRUSTED_NETWORK_HOST`.
   - Private UNC paths (`\\192.168.1.100\photos`) succeed or time out within 1.0s.

---

## 5. Automated Test Execution

Run the complete Python test suite with branch and line coverage enforcement ($\ge 90\%$):

```powershell
uv run pytest --cov=native_host --cov=scripts --cov-fail-under=90 tests/unit/native_host/ tests/unit/scripts/
```
