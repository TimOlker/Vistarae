<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Research & Architectural Decisions: Phase 8 — UI Main Page Enhancements

**Feature Identifier**: `008-ui-main-page-enhancements`  
**Date**: 2026-10-22  
**Status**: Completed  
**Spec Reference**: [spec.md](./spec.md)

---

## 1. Executive Research Summary

Phase 8 elevates the main Vistarae discovery canvas into a high-density, responsive travel operations workspace. This document captures the architectural decisions, trade-offs, and technical solutions addressing the four primary pillars of the feature:

1. **Adaptive Space Management**: Fluid layout transitions (`split`, `map_only`, `table_only`) with zero DOM unmounting and in-memory session preservation.
2. **Visual Query Builder & Filter Rules Persistence**: Dual-mode hybrid query execution (client in-memory for $<1,000$ POIs; backend PostGIS translation for $\ge 1,000$ POIs) and PostgreSQL JSONB rule persistence with strict tenant isolation.
3. **Multi-Select Mode & Atomic Bulk Operations Engine**: Synchronous batch operations capped at 500 records with single-transaction atomicity and safe primary-address updates.
4. **MapLibre GL Cluster Navigation & Rich Pin Popups**: Smooth bounding-box easing on cluster expansion, max-zoom ($z \ge 20$) co-location disambiguation, and interactive pin preview popups wired directly into the POI Edit Drawer.

---

## 2. Topic 1: Adaptive Space Management (Layout Toggles)

### Context & Challenge

The main Vistarae workspace presents two synchronized visualization components: MapLibre GL (`MapView`) and a tabular data grid (`POITable`). Travelers require the ability to collapse either component to maximize horizontal space:

- "Map Only": 100% width for geographic route exploration and visual clustering.
- "Table Only": 100% width for dense attribute comparison, sorting, and bulk management.
- "Split View": Side-by-side (approx. 58% map, 42% table) for coordinated spatial inspection.

When toggling layout modes, the application must:

- Avoid re-fetching data from the backend.
- Avoid unmounting the MapLibre GL canvas (which would drop WebGL context and trigger an expensive canvas re-initialization).
- Trigger `map.resize()` immediately after CSS layout transitions complete.
- Preserve active selection, filter state, and multi-select checkbox status.

### Alternatives Considered

1. **Conditional Mounting (`{mode !== 'table_only' && <MapView />}`)**:
   - _Rejected_: Unmounting the MapView destroys the MapLibre canvas instance, losing WebGL textures, active camera coordinates, and internal cluster caches. Re-mounting causes a visible flicker and 200–500ms delay.
2. **CSS Display / Visibility Toggling with `map.resize()`**:
   - _Selected_: Both components remain mounted in the DOM. In `map_only` mode, the table container is styled with `display: none` (or `width: 0`, `overflow: hidden`) and the map container expands to `flex: 1`. In `table_only` mode, the map container is hidden and the table expands to `flex: 1`. A `ResizeObserver` or explicit `useLayoutEffect` invokes `map.resize()` upon container dimension shifts, guaranteeing 60fps responsiveness under 100ms.

### Decision

Store layout mode (`split`, `map_only`, `table_only`) in React local state (`useState<LayoutMode>('split')`) inside `HomePage.tsx`. Do not persist layout preference to the database `user_preferences` table (per Clarification Q3), preserving lightweight session-only behavior.

---

## 3. Topic 2: Visual Query Builder & Hybrid Filter Evaluation Engine

### Context & Challenge

Travelers need to filter POIs using complex queries (e.g. `(Country = "Japan" AND Rating >= 4) OR (Tag = "bucket-list" AND already_visited = false)`).
The query structure must be:

- Easily serializable to JSON for database storage in `filter_rules.query_tree`.
- Evaluatable instantly ($<200$ms) in the browser for small-to-medium datasets ($<1,000$ POIs).
- Translatable into SQLAlchemy / PostgreSQL JSONB queries for large datasets ($\ge 1,000$ POIs) or when viewport pagination is active.

### Query Tree AST Design

We adopt a recursive Boolean Abstract Syntax Tree (AST):

```json
{
  "conjunction": "AND",
  "rules": [
    {
      "field": "country",
      "operator": "equals",
      "value": "Japan"
    },
    {
      "field": "rating",
      "operator": "greater_than_or_equal",
      "value": 4
    },
    {
      "conjunction": "OR",
      "rules": [
        { "field": "already_visited", "operator": "equals", "value": false },
        { "field": "want_to_visit_again", "operator": "equals", "value": true }
      ]
    }
  ]
}
```

### Hybrid Evaluation Architecture (Clarification Q1)

1. **Client-Side In-Memory Engine ($N < 1,000$ POIs)**:
   - Evaluates the AST using pure JavaScript predicate functions.
   - Operators supported: `equals`, `not_equals`, `contains`, `is_empty`, `is_not_empty`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `has_tag`, `lacks_tag`, `in_list`, `not_in_list`.
   - Executes in $<10$ms for 1,000 items in memory, driving instant marker visibility updates on the map and table row filtering.
2. **Server-Side SQLAlchemy AST Translator ($N \ge 1,000$ POIs)**:
   - When dataset exceeds 1,000 POIs or server viewport clustering is active, `POST /api/pois/query` or `GET /api/pois?filter_rule_id=...` submits the AST.
   - The backend `FilterQueryTranslator` compiles AST nodes into SQLAlchemy binary expressions:
     - `country` / `city` / `state`: PostgreSQL JSONB path queries on `pois.addresses` or scalar columns.
     - `rating`: Standard SQL `>=, <=, =`.
     - `tags`: SQL subquery or `EXISTS` on `poi_tags`.
     - `has_parent`: `parent_poi_id IS NOT NULL` / `IS NULL`.
     - `visit_state`: Standard enum filter.
   - Always combines filter predicates with `WHERE user_id = :current_user_id` and spatial bounding box `ST_MakeEnvelope`.

---

## 4. Topic 3: Filter Rule Persistence & Per-Tenant Isolation

### Database Schema

A new table `filter_rules` stores user search profiles:

- `id`: UUID PRIMARY KEY
- `user_id`: UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
- `name`: VARCHAR(100) NOT NULL
- `query_tree`: JSONB NOT NULL
- `table_config`: JSONB NOT NULL (visible columns, order sequence, sort spec)
- `pin_color_scheme`: JSONB NOT NULL (mode: `uniform` | `rating` | `visit_status` | `custom`, palette, mappings)
- `created_at`: TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at`: TIMESTAMPTZ NOT NULL DEFAULT now()
- **Constraint**: `UniqueConstraint("user_id", "name", name="uq_filter_rules_user_name")`

### Tenancy & Security (Constitution Principle 3)

- No PostgreSQL Row-Level Security (RLS) is used.
- All repository queries and mutations append `WHERE user_id = :current_user_id`.
- If a user attempts to update or delete a rule ID not owned by their `user_id`, the repository returns `None` and the API responds with RFC 7807 404 Not Found.

---

## 5. Topic 4: Multi-Select Mode & Atomic Bulk Operations

### Batch Ceiling & Performance (Clarification Q4)

- **Synchronous Batch Ceiling**: Maximum 500 POIs per bulk edit or delete request.
- Requests with $> 500$ `poi_ids` return RFC 7807 422 Unprocessable Entity with `code: "batch_limit_exceeded"`.
- 500 items execute within a single atomic SQLAlchemy transaction (`async with session.begin():`) in $<1.5$ seconds, well within the AWS Lambda 29-second API Gateway timeout limit.

### Non-Destructive Multi-Address Bulk Updates (Clarification Q2)

- Multi-address POIs (e.g., Iguazu Falls spanning Argentina and Brazil, Yellowstone spanning Wyoming, Montana, and Idaho) have an `addresses` JSONB array containing multiple `AddressRecord` items.
- When bulk updating City, State, or Country:
  - If `addresses` is non-empty, update the target field **exclusively on the primary record** (`addresses[0]`).
  - Preserve all other fields on `addresses[0]` (`street_address`, `postal_code`, `notes`).
  - Leave secondary address records (`addresses[1:]`) completely untouched.
  - If `addresses` is empty, instantiate a single new `AddressRecord` with the specified normalized value and default country.
  - If a null/clear action is requested, set the field to `null` on `addresses[0]`.
- All text inputs pass through `AddressNormalizer` before persistence to ensure canonical English spelling.

### Lifecycle Flag Recalculation

When bulk assigning visited dates or toggling `want_to_visit_again`:

- Appending a date automatically sets `already_visited = true`.
- If `already_visited == true` and `want_to_visit_again == false`: `visit_pending = false`.
- If `already_visited == true` and `want_to_visit_again == true`: `visit_pending = true`.
- If `already_visited == false`: `visit_pending = true`.

---

## 6. Topic 5: MapLibre GL Cluster Navigation & Popups

### Cluster Click & Zoom Easing

- MapLibre GL GeoJSON cluster sources provide `cluster_id`.
- On cluster click, call `mapSource.getClusterExpansionZoom(clusterId)` and calculate the geographic bounds of cluster leaves via `mapSource.getClusterLeaves(clusterId, 100, 0)`.
- Smoothly transition the viewport using `map.fitBounds(bounds, { padding: 60, maxZoom: 18, duration: 300 })`.
- Table synchronization: Viewport change fires `onViewportChange(bounds)`, restricting displayed table rows to POIs within the visible bounding box.

### Co-Located Pins at Max Zoom ($z \ge 20$)

- In high-density indoor venues (e.g. Louvre exhibits, shopping malls), multiple POIs share identical coordinates. At max zoom ($z=20$), expansion cannot separate them.
- Detect co-location ($N > 1$ at $z \ge 19.5$) and render an interactive disambiguation popup card listing co-located POI names, enabling direct selection.

### Unclustered Pin Popup Card

- Clicking an unclustered POI pin displays `POIPopupCard` anchored to the marker coordinates.
- Displays:
  - POI name
  - Star rating (gold stars or "Unrated")
  - Address: single address string OR "Multiple Locations ({N})" badge with count
  - Thumbnail photo (first URL from `image_urls` if present)
  - "Edit POI" primary action button: clicking opens `POIEditDrawer`, pre-populated with the full POI entity.

---

## 7. Architectural Decisions Matrix

| Capability              | Chosen Strategy                                                                                | Alternatives Evaluated                                          | Rationale                                                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Layout Switching**    | In-memory React state + CSS flex / display toggle + `map.resize()`                             | Persistent DB preferences; conditional DOM unmounting           | Sub-100ms latency, zero WebGL context loss, zero DB overhead.                                                             |
| **Filter Evaluation**   | Hybrid: In-memory client AST for $<1,000$ POIs; SQLAlchemy AST translator for $\ge 1,000$ POIs | Client-only filtering; Server-only querying for every keystroke | Instant client responsiveness for standard collections; scalable database push-down for massive collections.              |
| **Filter Rule Storage** | Dedicated `filter_rules` table with JSONB columns and `(user_id, name)` unique constraint      | Embedding in `user_preferences`; generic key-value store        | Clean relational modeling, CASCADE deletion with user, fast indexed lookups, isolated per-user naming.                    |
| **Bulk Updates**        | Primary-address targeting (`addresses[0]`), max 500 batch ceiling                              | Overwrite all addresses; Async background Celery queue          | Prevents catastrophic data loss on multi-state/country POIs; eliminates heavy worker infra for interactive UI operations. |
| **Pin Coloring**        | Dynamic SVG pin styling based on active rule `pin_color_scheme`                                | Fixed static pin assets; Client-side raster marker generation   | High-fidelity vector rendering on MapLibre GL with zero image network overhead.                                           |
| **Cluster Navigation**  | `fitBounds` on cluster leaf bounding box with 300ms easing                                     | Step-wise single zoom level increment                           | Provides immediate geographic context without requiring multiple repetitive user clicks.                                  |
