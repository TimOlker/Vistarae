# Travel Style Personalization & Unique User Context

## Overview

Vistarae empowers travelers to customize how destinations and points of interest (POIs) are extracted, enriched, and presented across the platform. By articulating your natural travel style (interests, pacing, culinary passions, architectural preferences), Vistarae uses Google Gemini Flash-Lite to decompose your preferences into modular prompt directives that shape future captures.

Additionally, every captured POI features both an objective factual summary (`Description`) and a tailored experiential rationale (`Reason to Visit`) explaining *why* a tourist with your travel interests should visit the location.

---

## 1. Setting Up Your Travel Style

1. Navigate to your **Profile** (`/profile`) on the Vistarae Web App.
2. Locate the **Travel Style & AI Context** card (`#travel-style`).
3. In the freeform text area (up to 2,000 characters), describe what you look for when exploring:
   - *Interests*: Artisan food, local markets, gothic architecture, scenic trails, modern art.
   - *Pacing*: Leisurely with long café breaks vs. fast-paced bucket-list sightseeing.
   - *Atmosphere*: Quiet hidden alleys vs. bustling landmarks.
4. Click **Save Travel Style**.

### AI Prompt Decomposition

Upon saving, Gemini Flash-Lite decomposes your narrative into three distinct prompt directives:
- **`Description Directive`**: Controls which physical landmarks, architectural styles, and neighborhood features are highlighted in factual POI summaries.
- **`Reason to Visit Directive`**: Dictates the experiential rationale explaining why a visitor would find the attraction compelling.
- **`Pacing & Duration Directive`**: Guides recommended duration calculations (e.g. factoring in leisurely stops or rapid visits).

Active directives appear in read-only preview cards immediately below the narrative editor.

---

## 2. "Reason to Visit" Field

Across all Vistarae interfaces, POIs feature two complementary fields arranged in strict visual order:
1. **Description**: Factual summary describing *what* the destination is.
2. **Reason to Visit**: Experiential tourist rationale describing *why* someone should visit.

### Interface Parity

- **Chrome Extension Capture Overlay**: The `Reason to Visit` multiline textarea appears immediately below `Description`.
- **Web App POI Edit Drawer**: Full editing parity for `reason_to_visit` directly below `description`.
- **Web App POI Detail Drawer**: Displays an informative "Why Visit" card directly beneath the summary description.
- **Web App POI Table**: Optional column toggle for `Reason to Visit`, full sorting, and text filter evaluation matching both fields.
- **Manual Add Modal**: Captures both `description` and `reason_to_visit` when manually creating POIs.

---

## 3. Unified Search

Vistarae leverages PostgreSQL trigram similarity indices (`gin_trgm_ops`) and client-side filter evaluators to provide unified text search across both `description` and `reason_to_visit`.

Searching for specialized keywords present exclusively in a POI's `reason_to_visit` (e.g., *"artisan sourdough"*, *"panoramic sunset"*, *"tranquil courtyard"*) returns 100% of matching locations with zero false exclusions.

---

## 4. Batch CSV Ingestion & Imports

When importing POIs in bulk via `/import`:
- CSV files may include optional column headers: `reason_to_visit` or `why_visit`.
- When web addresses are provided without pre-filled text, the background ingestion processor retrieves your active prompt directives from the in-memory cache and generates personalized descriptions and reasons to visit automatically.

---

## 5. In-Memory Caching & Performance

- **Sub-2ms Resolution**: Active prompt directives are cached in-process with a 300-second TTL, resolving directives in $< 0.001$ms on cache hits without external cache dependencies.
- **Proactive Eviction**: Updating your travel narrative, clearing preferences, or deleting your account immediately evicts cached entries for your tenant.
- **Database Fallback**: In the event of cache errors, the system transparently falls back to PostgreSQL without interrupting capture or enrichment operations.

---

## 6. API Reference

### `GET /api/user/profile/travel-style`
Retrieves the authenticated traveler's stored narrative and active prompt directives.

**Response**:
```json
{
  "travel_style_description": "I love relaxing vacations exploring local bakeries...",
  "prompts": [
    {
      "prompt_type": "description",
      "prompt_text": "Emphasize culinary culture, neighborhood character, and artisan food.",
      "updated_at": "2026-10-27T16:00:00Z"
    },
    {
      "prompt_type": "reason_to_visit",
      "prompt_text": "Highlight local food tastings and sensory atmosphere.",
      "updated_at": "2026-10-27T16:00:00Z"
    },
    {
      "prompt_type": "time_spent",
      "prompt_text": "Allow extra time for relaxed pacing and lingering.",
      "updated_at": "2026-10-27T16:00:00Z"
    }
  ]
}
```

### `PUT /api/user/profile/travel-style`
Updates freeform travel style narrative and synthesizes modular prompt directives.

**Request Body**:
```json
{
  "travel_style_description": "Passionate about gothic cathedrals, quiet cobblestone streets, and classical history."
}
```

### `DELETE /api/user/profile/travel-style`
Clears stored narrative and deletes all synthesized prompt directives for the tenant.

### `POST /api/pois/extract-and-check`
Extracts and check triage candidate from web page URL and snippet, applying personalized directives.

**Response**:
```json
{
  "candidate": {
    "name": "Pike Place Market",
    "description": "Historic public market in Seattle overlooking Elliott Bay...",
    "reason_to_visit": "Wander bustling market alleys to sample artisan cheeses and ciders...",
    "latitude": 47.6087,
    "longitude": -122.3400
  },
  "verdict": {
    "match_type": "UNIQUE_LOCATION"
  }
}
```
