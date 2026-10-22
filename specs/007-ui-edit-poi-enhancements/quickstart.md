# Quickstart Validation Guide: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Feature Identifier**: `007-ui-edit-poi-enhancements`  
**Date**: 2026-10-21  
**Status**: Ready for Implementation  
**References**: [spec.md](./spec.md) | [research.md](./research.md) | [data-model.md](./data-model.md) | [contracts/poi-edit-api.yaml](./contracts/poi-edit-api.yaml)

---

## 1. Prerequisites & Environment Setup

Ensure the local development environment and PostGIS test container are running:

```bash
# 1. Start local PostGIS and ElasticMQ dependencies
docker compose up -d

# 2. Apply database migrations up to 0005_poi_edit_enhancements
uv run alembic upgrade head

# 3. Start local Uvicorn gateway service (port 8000)
uv run uvicorn services.local_gateway:app --reload --port 8000

# 4. In a separate terminal, start the Vite frontend development server (port 5173)
cd frontend && npm run dev
```

---

## 2. End-to-End Validation Scenarios

### Scenario 1: Multi-Address & Visit Lifecycle State Verification

**Goal**: Validate multi-address persistence, English name normalization, and deterministic visit lifecycle state calculation (`already_visited`, `visit_pending`).

1. **Step**: Open the POI Editor for an existing POI (e.g. `http://localhost:5173`).
2. **Action**:
   - Add Address 1: `street: "Ruta 101"`, `city: "Puerto Iguazú"`, `state: "misiones"`, `country: "argentina"`.
   - Add Address 2: `street: "BR-469"`, `city: "Foz do Iguaçu"`, `state: "parana"`, `country: "brasil"`.
   - Add Visited Date: `2024-05-15`.
   - Toggle "Want to visit again": Checked (`true`).
   - Click "Save Changes".
3. **Expected Outcome**:
   - State/province normalized to `"Misiones"` and `"Paraná"`.
   - Countries normalized to `"Argentina"` and `"Brazil"`.
   - POI JSON reflects `already_visited: true` and `visit_pending: true`.
   - Unchecking "Want to visit again" updates `visit_pending` to `false`.

---

### Scenario 2: Hierarchical POI Parenting & Cycle Rejection

**Goal**: Verify typeahead parent selection, parent display name resolution, and cycle prevention.

1. **Step**: In the POI Editor for "Old Faithful Geyser", navigate to the "Parent POI" field.
2. **Action**:
   - Type `"Yellowstone"` into the parent input.
   - Select `"Yellowstone National Park"` from the dropdown suggestions.
   - Click "Save Changes".
3. **Expected Outcome**:
   - `parent_poi_id` is persisted and `parent_poi_name` renders as `"Yellowstone National Park"`.
4. **Negative Test (Cycle Prevention)**:
   - Open "Yellowstone National Park" and attempt to assign `"Old Faithful Geyser"` as its parent.
   - Verify that "Old Faithful Geyser" is excluded from the dropdown, or that saving returns an RFC 7807 422 ProblemDetails response: `"Cannot assign descendant as parent POI (cyclical relationship)"`.

---

### Scenario 3: Location Finder Hybrid Routing & Reverse Geocoding

**Goal**: Validate interactive map pin selection, forward landmark search with zoom level adaptation, and backend reverse geocoding on "Apply".

1. **Step**: Click "Find on Map" in the POI Editor.
2. **Action**:
   - Search `"Mount Rushmore"` and hit Enter.
   - Verify the map centers on the monument at high zoom (zoom 16–18).
   - Click a point on the map to place a pin at `(43.8791, -103.4591)`.
   - Click "Apply".
3. **Expected Outcome**:
   - Location Finder closes without writing to the database.
   - POI draft updates coordinates to `43.8791, -103.4591`.
   - Backend reverse geocoding pre-fills city (`"Keystone"`), state (`"South Dakota"`), and country (`"United States"`).

---

### Scenario 4: Selective Field-by-Field POI Merge & Atomic Re-Parenting

**Goal**: Validate the dual-column merge comparison view, radio/checkbox synthesis, source deletion, and dependent reference re-parenting.

1. **Step**: Open the POI Edit page for POI A and click "Merge POI" with POI B.
2. **Action**:
   - Verify "Show all fields" toggle: disabled renders only diverging fields; enabled shows all fields.
   - For Name and Description, select POI B via radio buttons.
   - For Tags, Addresses, and Visited Dates, select all unique items from both POIs via checkboxes.
   - Click "Confirm Merge".
3. **Expected Outcome**:
   - Target POI is updated with combined unique sets and selected scalar values.
   - Source POI is deleted (`200 OK`).
   - Any itinerary items, list memberships, or child POIs that pointed to Source POI now reference Target POI.

---

### Scenario 5: Duplicate Collision Interception on Save

**Goal**: Test pre-save collision detection and in-memory draft preservation into the merge view.

1. **Step**: Create a new POI draft named `"Eiffel Tower"` with coordinates near Paris (`48.8584, 2.2945`).
2. **Action**: Click "Save Changes".
3. **Expected Outcome**:
   - Duplicate Interception dialog appears noting a matching POI within 200m and name similarity $\ge 0.60$.
   - Selecting "Merge" launches the Merge View with the current draft as source without losing uncommitted descriptions or addresses.
   - Selecting "Cancel" closes the modal and keeps the active draft intact in the editor.

---

## 3. Automated Verification Commands

Run the full automated test suite verifying 90% branch and line coverage per Constitution Principle 8:

```bash
# Backend unit & domain tests with 90% coverage threshold
uv run pytest tests/unit/services/poi/ --cov=services/poi --cov-fail-under=90

# Frontend unit tests
cd frontend && npm run test:unit
```
