# Quickstart & Verification Guide: Extension Capture Bug Fixes

**Feature**: `010-extension-capture-bug-fix`  
**Date**: 2026-10-26  
**Status**: Ready for Validation

---

## Prerequisites

1. **Local Infrastructure Running**:
   ```powershell
   .\vistarae.ps1 dev
   ```
   - PostgreSQL/PostGIS running on port 5432.
   - FastAPI backend running on `http://localhost:8000`.
   - React SPA running on `http://localhost:5173`.
2. **Chrome Extension Loaded**:
   - Open `chrome://extensions/`.
   - Enable "Developer mode".
   - Click "Load unpacked" and select `d:\Coding\Vistarae\extension`.
   - Ensure the extension is reloaded (click 🔄).
3. **Authenticated Session**:
   - Log into `http://localhost:5173` with user `tim@olker.us`.
   - Refresh the page to synchronize credentials into the extension.

---

## Validation Scenarios

### Scenario 1: Clean Destination Name Sanitization (Bug Fix 1)

1. Navigate to Google Maps place page:
   `https://www.google.com/maps/place/Eltz+Castle/@50.2052269,7.3365473,233m/...`
2. Press `Ctrl+Shift+S`.
3. **Verify**:
   - The **Destination / POI Name** field displays cleanly as **"Eltz Castle"**.
   - It does **NOT** contain `" - Google Maps"` or any source platform suffix.

---

### Scenario 2: Knowledge Enrichment & Wikipedia Link (Bug Fix 2 & 4)

1. In the open capture modal for Eltz Castle:
2. **Verify**:
   - **Summary Description**: Displays a 2-3 sentence informative overview of the medieval castle (not `"Captured from Google Maps: Eltz Castle"`).
   - **Wikipedia Article**: Populated with `https://en.wikipedia.org/wiki/Eltz_Castle` (or canonical English Wikipedia URL).

---

### Scenario 3: Link Verification "View" Buttons (Bug Fix 5)

1. Next to the **Official Website** and **Wikipedia Article** inputs:
2. **Verify**:
   - Both inputs have a visible **"View ↗"** button.
   - Clicking **"View"** next to Wikipedia opens `https://en.wikipedia.org/wiki/Eltz_Castle` in a new browser tab (`target="_blank"`, `rel="noopener noreferrer"`).
   - When an input field is cleared/empty, its corresponding "View" button becomes disabled.

---

### Scenario 4: Hero Image Preview & Live Reload (Bug Fix 6)

1. In the open capture modal:
2. **Verify**:
   - **Hero Image Preview**: The visual thumbnail card renders an image of Eltz Castle.
   - **Custom URL & Reload**: Paste a new image URL into the Hero Image field and click the **"Preview" / "Reload"** button.
   - The thumbnail updates immediately upon successful image preflight.
   - Paste an invalid URL: An inline warning ("Image preview unavailable") appears without disrupting form submission.

---

### Scenario 5: Address Cleansing & Country Accuracy (Bug Fix 7)

1. In the open capture modal:
2. **Verify**:
   - The resolved address displays: `"Burg Eltz, 56294 Wierschem, Germany"`.
   - There is **NO** leading pushpin glyph (`🖈` or `📍`).
   - The country displays **only Germany** — it does **NOT** list `"Germany, United States"`.

---

### Scenario 6: Interactive Mini-Map Verification & Reselection (Bug Fix 3)

1. Under the **Latitude** and **Longitude** inputs:
2. **Verify**:
   - An interactive Leaflet mini-map displays with an OpenStreetMap tile background.
   - A pin is plotted at `50.2052269, 7.3365473`.
3. Click the **"Reselect Location"** button.
4. Click a different spot on the map or drag the pin.
5. **Verify**:
   - The marker repositions immediately.
   - Latitude and Longitude fields update instantly.
   - The resolved address automatically re-queries reverse-geocoding and updates the address display for the new position.

---

### Scenario 7: Vetted Tag Recommendations (Bug Fix 8)

1. In the open capture modal under **Vetted Tags**:
2. **Verify**:
   - Relevant tag pills appear (e.g. `Castle`, `Historic Site`, `Landmark`).
   - Clicking a tag toggles its active/inactive state.

---

### Scenario 8: Estimated Visit Duration (Bug Fix 9)

1. In the open capture modal:
2. **Verify**:
   - **Duration (hours)**: Pre-fills with an appropriate estimate (e.g., `2.5` hours).
   - **Duration (days)**: Pre-fills with `0` days.
   - Both fields remain fully editable by the traveler.

---

### Scenario 9: Full Persistence & Database Parity

1. Click **"Save to Vistarae"**.
2. **Verify**:
   - Modal shows saving state, then displays confirmation and closes.
   - Open Web App at `http://localhost:5173`.
   - "Eltz Castle" appears in your POI list with clean name, enriched description, verified coordinates, and valid tags.
