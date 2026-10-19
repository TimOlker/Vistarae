# Vistarae Chrome Extension Installation & User Guide

This guide walks you through installing, configuring, and using the **Vistarae Manifest V3 Chrome Extension** in Developer Mode.

---

## 📋 Prerequisites

Before using the extension, ensure the Vistarae backend engine and database are running:

```bash
# Option A: Start via Docker Compose
make up

# Option B: Run locally with Python
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Verify the API is accessible by visiting the Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 📦 Step-by-Step Installation into Google Chrome

### Step 1: Open Chrome's Extension Manager
1. Open **Google Chrome**.
2. Type or paste the following into the URL address bar and press **Enter**:
   ```text
   chrome://extensions
   ```
   *(Alternatively, click Chrome's three-dots menu `⋮` $\rightarrow$ **Extensions** $\rightarrow$ **Manage Extensions**)*.

---

### Step 2: Enable Developer Mode
In the top-right corner of the `chrome://extensions` page, toggle the **Developer mode** switch to **ON**.

---

### Step 3: Load the Unpacked Extension
1. In the top-left toolbar that appears, click the **"Load unpacked"** button.
2. In the folder picker dialog, navigate to and select your project's `extension` directory:
   ```text
   D:\Coding\Vistarae\extension
   ```
3. Click **"Select Folder"**.

You will now see the **Vistarae - Travel POI Capture** card in your extensions list.

---

### Step 4: Pin the Extension (Recommended)
1. Click the **Puzzle Piece icon** (🧩) in Chrome's top toolbar.
2. Locate **Vistarae - Travel POI Capture**.
3. Click the **Pin icon** (📌) to pin Vistarae to your browser toolbar for easy access.

---

## 🚀 How to Capture Places & Travel Dreams

### 1. Highlight Text
Navigate to any travel website, blog, or article (e.g. [Wikipedia's Yosemite National Park](https://en.wikipedia.org/wiki/Yosemite_National_Park)). Highlight any text describing a place, overlook, trail, or landmark.

### 2. Trigger the Capture
Trigger Vistarae using either method:
* **Keyboard Shortcut**:
  * Windows / Linux: **`Ctrl+Shift+S`**
  * macOS: **`Command+Shift+S`**
* **Context Menu**:
  * Right-click the highlighted text $\rightarrow$ select **"Capture to Vistarae"**.

### 3. Sign In or Create an Account
On your first capture (or if your session expired), an isolated Shadow DOM dialog will appear:
* **Demo Account**:
  * **Email**: `demo@vistarae.com`
  * **Password**: `Traveler123!`
* **New Account**: Click the **"Create Account"** tab, enter your name, email, and password (min 6 characters), and click **Create Account**.

### 4. Review Extracted POI Details
Once authenticated, Vistarae automatically:
* Extracts structured POI attributes using **Google Gemini Flash-Lite** (zero thinking latency).
* Deterministically geocodes coordinates via **OpenStreetMap Nominatim** with local caching.
* Performs PostGIS spatial deduplication against **your personal collection**:
  * 🟢 **Unique Location**: No spatial conflict found within 500ft.
  * 🟡 **Potential Duplicate**: An existing record within 500ft shares $\ge 60\%$ name similarity (shows side-by-side comparison).
  * 🔵 **Nearby Macro-POI**: A nearby parent site (e.g. National Park or Historic District) was found and offers 1-click nesting.
* Allows adjusting personal star rating (1–5), physical effort, cost tier, best time to visit, and IPTC location metadata.
* Allows tagging to existing lists or creating a new list on the fly with the **`+ Create new list...`** input.

### 5. Save
Click **"Save to Vistarae"**. A confirmation toast will confirm that the record has been committed to your PostGIS database.

---

## 🛠️ Developer & Troubleshooting Tips

### Reloading After Code Changes
If you modify files inside `extension/`:
1. Return to `chrome://extensions`.
2. Find the **Vistarae** card.
3. Click the **Refresh icon** (🔄).
4. Reload any active webpage tabs to apply updated content scripts.

### Inspecting Extension Logs & Tracing
* **Background Service Worker Console**: On the `chrome://extensions` page, click the **"service worker"** link on the Vistarae card to open DevTools. You will see W3C `traceparent` headers and microservice tags:
  * `MSG ->|  `: Inbound messages from the active webpage.
  * `MSG <-|  `: Responses sent back to the tab.
  * `MSG   |->`: Outbound API calls with `TraceID` and `SpanID`.
  * `MSG   |<-`: Server responses with `ServerSpanID`.
* **In-Page Shadow DOM Inspection**: Open Chrome DevTools (`F12`) on any webpage where Vistarae is active. The modal is encapsulated inside `<vistarae-capture-root>` under an open `#shadow-root` to prevent host website CSS collisions.
