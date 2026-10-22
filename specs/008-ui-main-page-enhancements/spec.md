# Feature Specification: Phase 8 — UI Main Page Enhancements (Space Management, Visual POI Filter Rules, Multi-Select Bulk Actions & Map Popups)

**Feature Identifier**: `008-ui-main-page-enhancements`  
**Feature Branch**: `008-ui-main-page-enhancements`  
**Created**: 2026-10-22  
**Status**: Draft  
**Target Systems**:

- **Main Viewport Frontend**: `frontend/src/pages/HomePage.tsx`, `frontend/src/components/poi/POITable.tsx`, `frontend/src/components/map/MapView.tsx`, `frontend/src/components/filter/` (Query builder, Saved rule manager, Column selector, Pin color scheme editor), `frontend/src/components/bulk/` (Bulk operations modal/toolbar).
- **Filter & Bulk Operations Backend**: `services/poi/` (`/api/pois/filter-rules/*`, `/api/pois/bulk-edit`, `/api/pois/bulk-delete`), `packages/core/vistarae_core/` (Filter rule entity, query builder AST, bulk action schemas, address normalization integration).
- **Database & Persistence**: PostgreSQL 16+ / PostGIS / Alembic migration `0006_filter_rules_and_bulk.py` creating tenant-isolated `filter_rules` table with unique constraint on `(user_id, name)`.

**Input**: User description:

> "/speckit.specify Create the specification for Phase 7 (008-ui-main-page-enhancements) using strict EARS syntax.
>
> Scope to cover Main page enhancements:
>
> 1. Space management:
>    - On the main Vistarae page, please add the ability to hide either the Map or the POI Table view. If the MAP is hidden, give all horizontal space to the POI Table. If the POI Table is hidden, then give all horizontal space to the Map view. If neither the Map or POI Table are hidden, allow the horizontal space to be shared by both.
> 2. POI Filtering - allow the user to refine what POIs are displayed to make a large dataset more manageable & easier to interact with.
>    - Add a filtering section. By default this is hidden, but when expanded provides the user the ability to intelligently filter what POIs are displayed. This should allow the user build and/or statements into a text field, but a UI builder. Things a user can can build a query with include (but are not limited to):
>      - city/town equal/not equal to a value
>      - state/province equal/not equal to a value
>      - country equal/not equal to a value
>      - to only allow POIs that do have a Parent POI, POIs that do have a Parent POI
>      - "visit pending" flag is True or False
>      - "already visited" flag is True or False
>      - star rating equal/less/greater/less-than-or-equal/greater-than-or-equal
>      - included in/not included in a specified travel list
>      - if the POI equals/not equals a different the enumerated visited status
>      - matches a tag / does not match a tag
>      - When 'Apply' button is clicked, apply the rule to control which POIs are displayed on the map and in the POI Table.
>    - The filter section above the Map and POI Table should give the user the ability to save the currently selected filters to a 'Filter Rule'. A previously saved 'Filter Rule' should be able to be loaded. The 'Filter Rule' saved by a user should only be able to be loaded /edited by a user. Saving a 'Filter Rule' to an existing Filter Name should overwrite the existing 'Filter Rule'. A user should also be able to delete an existing 'Filter Rule'. The filter section should also allow the columns displayed in the POI table to be saved. There should also be a "Save As" capability to allow an existing 'Filter Rule' be used as the basis to start a new, independent 'Filter Rule'.
>    - The user should be given the ability to select which columns to include and what order they are displayed in. Additionally a column can be unsorted, ascending or descending.
>    - The user should also specify how to color the POI pins displayed on the map. The color scheme should be included into the 'Filter Rule'. A color scheme could be all pins have the same color, or one color for each different star rating, or one color if a poi has be visited or not visited. The user should be able to define custom color schemes.
>    - Each 'Filter Rule' is saved to the DB to persist the information and is associated with a user's profile. So 'User A' and 'User B' can both have an independent 'Filter Rule' named 'Demo' and not impact each other. 'User A' should never be able to see any 'Filter Rule' owned by 'User B'.
> 3. POI select mode and bulk edit / delete capability
>    - POI Table by default is a single select mode.
>    - A toggle should enable a multi-select mode, where a checkbox appears to the left of each POI displayed in the POI Table. If disabled, hide the checkbox and apply options. The option to perform a bulk option should be allowed when multiple records are selected.
>    - In multi-select mode, There should be button to toggle all POIs / non POIs being selected (based on the currently selected values).
>    - In multi-select mode, An ability should be provided to allow operations to be applied to all selected records. This could be to assign values to records including (but not limited to)
>      - set the star rating (to one of the enumerated values for the field).
>      - set a visited date (and then set the already visited, visit pending flags)
>      - visit again (and then set the already visited, visit pending flags)
>      - apply a specific tag (if it doesn't already exist)
>      - remove a specific tag (if it exists - do nothing if it does not exist)
>      - add to a list (if it doesn't already exist in the list)
>      - remove from a list (if it already exists in the list)
>      - update the town/city (if multiple town/city are defined for record remove all records and replace with just new value). This should also allow the town/city to be set to a Null / not set value. Make sure to set to use what ever normalization rules are used elsewhere before applying a new value.
>      - update the state/province (if multiple state/province are defined for record remove all records and replace with just new value). This should also allow the state/province to be set to a Null / not set value. Make sure to set to use what ever normalization rules are used elsewhere before applying a new value.
>      - update the country (if multiple country are defined for record remove all records and replace with just new value). This should also allow the country to be set to a Null / not set value. Make sure to set to use what ever normalization rules are used elsewhere before applying a new value.
>      - bulk delete selected records (with confirmation)
> 4. POI Map Pin popup
>    - when clicking on a pin on a map representing a POI that is a cluster, zoom in on the area covered by the pins of the cluster. If too many POIs are within the cluster and exceed the default display rule, then cluster items together as needed. As usual, make sure the POI table is only listing the items currently displayed on the map (whether as a single POI or as part of a cluster).
>    - when clicking on a pin on a map representing a POI that is not a cluster, display a popup on the map. Display the POI name, include a button that can be clicked that will bring up the POI editor. Display the address information if there is a single address. If multiple address indicate multiple locations. If there is an image URL associated with the POI display the image here."

---

## 1. Executive Summary & Context

Phase 8 (`008-ui-main-page-enhancements`) expands the main Vistarae discovery canvas into a high-density, interactive travel operations workspace. As travelers accumulate thousands of points of interest across the globe, interacting with large geographic datasets requires adaptive space management, visual query filtering, reusable view profiles, bulk data remediation, and context-preserving map interaction.

The feature delivers four cohesive capability pillars:

1. **Adaptive Space Management (Layout Toggle)**:

   - Provides instant controls allowing travelers to switch between three display modes: **Split View** (Map and Table share horizontal space), **Map Only** (POI Table is hidden, granting 100% horizontal width to the map canvas), and **Table Only** (Map is hidden, granting 100% horizontal width to tabular analysis).
   - Preserves active selection, filter state, and viewport synchronization across layout transitions without reloading data.

2. **Visual Query Builder & Persisted Filter Rules**:

   - Introduces an expandable filter workspace above the main layout with a visual query builder supporting conjunctions (`AND`, `OR`) across core POI metadata: City/Town, State/Province, Country, Parent POI presence (`has_parent`, `no_parent`), Visit Lifecycle (`visit_pending`, `already_visited`, `want_to_visit_again`), Star Rating (`=`, `<`, `>`, `<=`, `>=`), Curated List membership, Visited Status enumeration, and Tag matching.
   - Enables travelers to save complete **Filter Rules** into PostgreSQL (`filter_rules` table), capturing the active query tree, customized table column visibility, column order, column sorting states, and dynamic map pin coloring rules.
   - Provides rule lifecycle actions: **Load Rule**, **Save (Overwrite)**, **Save As (Fork/Duplicate)**, and **Delete**.
   - Strict tenant isolation ensures each user independently owns and names their rules without cross-tenant visibility or naming conflicts.
   - Implements dynamic map pin coloring schemes tied to the active rule: uniform color, color-by-rating (1–5 scale), color-by-visit-status, and customizable rule-based palettes.

3. **Multi-Select Mode & Atomic Bulk Operations**:

   - Extends the POI Table with a dedicated multi-select mode toggle.
   - In multi-select mode, individual row checkboxes and a master "Select All / Deselect All" toggle allow flexible batch selection across the currently filtered record set.
   - Provides an atomic bulk operation dialog supporting:
     - Assigning star ratings (0–5).
     - Recording visited dates with automatic lifecycle flag recalculation (`already_visited = true`, `visit_pending` update).
     - Toggling future return intent (`want_to_visit_again`) with automatic `visit_pending` recalculation.
     - Adding or removing tags idempotently.
     - Adding or removing curated list memberships idempotently.
     - Replacing or clearing City/Town, State/Province, and Country across all address records per POI using standardized English normalization.
     - Bulk deletion with explicit confirmation dialog and cascade safety.

4. **Map Pin Popups & Cluster Navigation**:
   - Enhances map cluster interaction: clicking a cluster dynamically eases the camera into the exact bounding box enclosing all clustered POIs, expanding them into individual pins or sub-clusters.
   - Guarantees strict bidirectional synchronization: the POI table exclusively displays POIs present within the current map viewport.
   - Clicking an unclustered POI pin displays an anchored interactive popup preview containing the POI name, hero photo thumbnail (if present), formatted address (or "Multiple Locations (N)" badge for multi-address POIs), star rating, and a direct "Edit POI" button that opens the edit drawer.

---

## Clarifications

### Session 2026-10-22

- Q: How should POI filter rules be evaluated between the browser client and the backend database? → A: Hybrid filtering: Evaluate filter rules in-memory for datasets under 1,000 POIs for instant reactivity, and push filter criteria to backend `/api/pois` with PostGIS bounding-box integration when datasets exceed 1,000 POIs or viewport clustering is active.
- Q: When performing a bulk update of City, State, or Country on POIs that possess multiple existing addresses, how should the address records be modified? → A: Update only primary address: Update the target field only on the first address record in the array, leaving secondary address records unmodified. If no address exists, instantiate a single address record with the provided value.
- Q: How should the traveler's preferred layout mode (`split`, `map_only`, or `table_only`) be persisted? → A: Session-only in-memory state: Default to `split` view on every fresh login or page load without persisting changes across browser sessions or altering `user_preferences` schema.
- Q: What should be the maximum number of POIs allowed in a single synchronous bulk operation? → A: 500 records maximum: Enforce a synchronous batch ceiling of up to 500 POIs per bulk edit/delete operation, returning an RFC 7807 422 validation error if exceeded with a prompt to narrow the active filter.

---

## 2. User Scenarios & Testing _(mandatory)_

### User Story 1 - Adaptive Space Management & Focus Modes (Priority: P1) 🎯 MVP

A traveler wants to focus exclusively on geographical route planning. On the main page, they click "Map Only". The POI Table smoothly collapses, and the interactive map expands to fill 100% of the horizontal viewport, providing maximum geographical context for clustering and spatial navigation. Later, when reviewing tabular data for data cleanup, they click "Table Only", expanding the POI table to full width to inspect all columns without horizontal scrolling truncation. Finally, they click "Split View" to return to the balanced side-by-side workspace.

**Why this priority**: Essential UX foundation for managing dense information. Travelers must be able to maximize either spatial or tabular screen real estate on demand.

**Independent Test**: Load the main page, click "Map Only" (verify map expands to 100% width and table is removed from DOM/hidden), click "Table Only" (verify table expands to 100% width and map is unmounted/hidden), and click "Split View" (verify both components render side-by-side).

**Acceptance Scenarios**:

1. **Given** the user is viewing the main page in default Split View, **When** the user clicks "Map Only", **Then** the map container expands to 100% horizontal width and the POI table is hidden.
2. **Given** the user is in "Map Only" mode, **When** the user clicks "Table Only", **Then** the POI table expands to 100% horizontal width and the map is hidden.
3. **Given** the user is in "Table Only" mode, **When** the user clicks "Split View", **Then** the map and POI table share the horizontal space according to standard layout proportions.
4. **Given** a POI is selected in Split View, **When** the user switches layout modes, **Then** the active POI selection is preserved across view transitions.

---

### User Story 2 - Visual POI Filtering & Persisted Filter Rules (Priority: P1)

A traveler with over 3,000 saved POIs wants to plan a trip to Japan. They expand the Filter section and use the visual query builder to add criteria: `Country equals "Japan"` AND `already_visited equals false` AND `rating >= 4`. They customize the POI table to show columns `[Name, City, Rating, Tags]` sorted by `Rating descending`. They select a pin coloring scheme where pins are colored by star rating (5-star gold, 4-star blue). They click "Apply", and both the map pins and POI table immediately update to reflect only the matching POIs. The traveler clicks "Save Rule", names it "Japan Unvisited Top Picks", and saves it. Later, they tweak the criteria and use "Save As" to create "Japan Visited Gems".

**Why this priority**: Core value proposition for high-volume travel curation. Without structured filtering, large datasets become unmanageable.

**Independent Test**: Open filter bar, construct multi-predicate query with AND/OR logic, click "Apply", verify map and table display only matching records, save as named rule, reload page, select rule from dropdown, and assert filters, table columns, and pin colors restore accurately.

**Acceptance Scenarios**:

1. **Given** the filter section is collapsed, **When** the user clicks the filter toggle, **Then** the visual filter builder expands above the map and table.
2. **Given** the filter builder is open, **When** the user defines criteria (`Country = "France"`, `Rating >= 4`) and clicks "Apply", **Then** only POIs matching all conjunction conditions appear on the map and table.
3. **Given** active filter criteria, table column order, and a star-rating pin coloring scheme, **When** the user enters a rule name and clicks "Save Rule", **Then** the rule is persisted to the database under the user's profile.
4. **Given** a user has saved rules, **When** the user selects "Japan Unvisited" from the saved rule dropdown, **Then** the query criteria, table columns, sort order, and pin coloring scheme are loaded and applied synchronously.
5. **Given** an existing loaded rule, **When** the user modifies criteria and clicks "Save As" with a new name, **Then** a new independent filter rule is created in the database without altering the original rule.
6. **Given** an existing filter rule, **When** the user clicks "Delete Rule" and confirms, **Then** the rule is removed from the database and the filter selection resets.

---

### User Story 3 - Multi-Select Mode & Batch POI Operations (Priority: P2)

A traveler returns from a trip to Kyoto where they visited 25 temples and scenic spots. In the POI Table, they enable "Multi-Select Mode". Row checkboxes appear next to every POI. They filter by `City = "Kyoto"`, click the master checkbox to select all 25 filtered POIs, and click "Bulk Edit". In the bulk operations dialog, they set a visited date (`2026-10-15`), add the tag `kyoto-autumn-2026`, and add all 25 to the list "Japan 2026 Trip". Upon confirming, the backend atomically updates all 25 records, automatically sets `already_visited = true`, and refreshes the view without full page reload.

**Why this priority**: Eliminates repetitive manual editing when curating groups of POIs after a trip or bulk CSV import.

**Independent Test**: Enable multi-select toggle, select multiple POIs via individual checkboxes and master toggle, launch Bulk Edit modal, update rating to 5 and add tag "favorite", confirm, and verify all selected records in the database reflect the changes and computed lifecycle flags.

**Acceptance Scenarios**:

1. **Given** the POI Table in default single-select mode, **When** the user toggles "Multi-Select Mode", **Then** checkboxes appear on the left of every row and a bulk actions toolbar displays above the table.
2. **Given** multi-select mode is active, **When** the user clicks the master checkbox, **Then** all currently filtered and visible POIs in the table are toggled between selected and unselected.
3. **Given** 10 POIs are selected, **When** the user clicks "Bulk Edit" and applies a star rating of 4, **Then** all 10 records update their rating to 4 in a single request.
4. **Given** selected POIs, **When** the user adds a visited date via bulk edit, **Then** the date is appended to each record's `visited_dates` array and `already_visited` is updated to `true`.
5. **Given** selected POIs, **When** the user updates the country to "United States", **Then** all existing addresses on each selected POI have their country updated to the standardized English value.
6. **Given** selected POIs, **When** the user clicks "Bulk Delete" and confirms the modal warning, **Then** the selected records are deleted from the database and removed from the active view.

---

### User Story 4 - Rich Map Pin Popup & Cluster Exploration (Priority: P2)

A traveler browses their European travel map. They see a cluster pin labeled "18" over Paris. They click the cluster pin; the map smoothly zooms and centers on the exact bounding box of those 18 pins, revealing individual monuments. They click the unclustered pin for "Musée d'Orsay". An anchored map popup appears showing the museum's name, a thumbnail image of the Beaux-Arts railway clock, its rating (5 stars), its formatted address, and an "Edit POI" button. Clicking "Edit POI" opens the full edit drawer to inspect notes and photos.

**Why this priority**: Delivers intuitive spatial discovery. Users need quick previews without being forced into full-drawer edit mode on every click.

**Independent Test**: Click a map cluster pin, assert map animates zoom to fit all cluster members, click an individual pin, assert popup displays name, thumbnail image, rating, address, and click "Edit POI" to open the drawer.

**Acceptance Scenarios**:

1. **Given** a map cluster pin representing multiple POIs, **When** the user clicks the cluster, **Then** the map animates zoom and pan to the bounding box enclosing all child POIs.
2. **Given** an unclustered POI pin on the map, **When** the user clicks the pin, **Then** an anchored popup opens displaying the POI name, star rating, address, and thumbnail image.
3. **Given** a POI with multiple addresses, **When** its pin popup renders, **Then** the popup displays "Multiple Locations ({N})" with an address count indicator.
4. **Given** an active pin popup, **When** the user clicks "Edit POI", **Then** the popup closes and the `POIEditDrawer` opens populated with the POI's details.
5. **Given** any map pan or zoom change, **When** the viewport finishes settling, **Then** the POI Table updates to list strictly the POIs located within the visible map boundaries.

---

### Edge Cases

- **Empty Filter Match**: When a visual filter produces zero matching POIs, both the map and table render an informative empty state ("No POIs match your filter criteria. [Reset Filters]") without crashing or leaving phantom markers.
- **Extreme Clustering at Max Zoom**: When multiple POIs share identical or near-identical coordinates (e.g. multiple exhibits inside the Louvre) at maximum map zoom ($z \ge 20$), clicking the cluster expands a spiderfied pin spread or displays a list popup allowing selection among co-located POIs.
- **Bulk Edit Partial Address Replacement**: When bulk-updating city or state on POIs where some records have zero existing addresses, the system creates a default address record containing the newly assigned components and required country placeholder ("Unknown" or user-provided country).
- **Rule Name Collisions Across Users**: User A and User B both save a rule named "Vacation 2026". The unique constraint `(user_id, name)` ensures neither user collides with or sees the other user's rule.
- **Rule Overwrite Confirmation**: When a user saves a rule with a name that already exists in their own profile, the UI prompts: "A filter rule named '[Name]' already exists. Overwrite?" with "Overwrite" and "Cancel" actions.
- **Multi-Select Viewport Interaction**: If a user selects 5 POIs, pans the map, and then filters to a new subset, selected items remain in memory until explicitly deselected or a bulk action executes.

---

## 3. Requirements _(mandatory)_

### Functional Requirements

#### Space Management & Layout Modes

- **REQ-MAIN-001**: **Ubiquitous**: The main application layout shall provide a segmented view control supporting three layout states (`split`, `map_only`, and `table_only`), defaulting to in-memory `split` view on initial page load and login without requiring database persistence.
- **REQ-MAIN-002**: **State-Driven**: While the layout state is set to `map_only`, the application shall hide the POI Table and allocate 100% of the horizontal content area to the Map canvas.
- **REQ-MAIN-003**: **State-Driven**: While the layout state is set to `table_only`, the application shall hide the Map canvas and allocate 100% of the horizontal content area to the POI Table.
- **REQ-MAIN-004**: **State-Driven**: While the layout state is set to `split`, the application shall display both the Map canvas and POI Table sharing horizontal space side-by-side.
- **REQ-MAIN-005**: **Event-Driven**: When switching between layout states, the application shall preserve all active POI selections, filter criteria, and multi-select checkbox states.

#### Visual POI Filter Builder

- **REQ-MAIN-006**: **Ubiquitous**: The main page shall incorporate a collapsible filter panel positioned above the map and table views, defaulting to a collapsed state.
- **REQ-MAIN-007**: **Event-Driven**: When the filter toggle is clicked, the application shall expand or collapse the visual query builder panel.
- **REQ-MAIN-008**: **Ubiquitous**: The visual query builder shall enable travelers to compose multi-clause filter statements joined by conjunctions (`AND`, `OR`).
- **REQ-MAIN-009**: **Ubiquitous**: The query builder shall support the following filter dimensions and operators:
  1. `city`: `equals`, `not_equals`, `contains`, `is_empty`, `is_not_empty`
  2. `state_province`: `equals`, `not_equals`, `contains`, `is_empty`, `is_not_empty`
  3. `country`: `equals`, `not_equals`
  4. `has_parent`: boolean (`true` for POIs with a `parent_poi_id`, `false` for root POIs)
  5. `visit_pending`: boolean (`true`, `false`)
  6. `already_visited`: boolean (`true`, `false`)
  7. `rating`: numeric operators (`=`, `<`, `>`, `<=`, `>=`) on values 0 to 5
  8. `list_id`: `in_list`, `not_in_list` referencing tenant curated lists
  9. `visit_state`: `equals`, `not_equals` on `not_visited`, `visited_return`, `visited_do_not_return`
  10. `tag`: `has_tag`, `lacks_tag` matching tag strings
- **REQ-MAIN-010**: **Event-Driven**: When the traveler clicks "Apply", the application shall evaluate the filter criteria using hybrid execution: evaluating the criteria in-memory for datasets under 1,000 POIs for instant reactivity, and pushing filter AST criteria to the backend `/api/pois` endpoint with PostGIS bounding-box integration when datasets exceed 1,000 POIs or server viewport clustering is active, restricting both rendered map pins and displayed table rows to matching records.
- **REQ-MAIN-011**: **Event-Driven**: When the traveler clicks "Clear Filter", the application shall reset all query clauses and display all tenant POIs within the current viewport.

#### Filter Rule Persistence & Color Schemes

- **REQ-MAIN-012**: **Ubiquitous**: The database schema shall persist filter profiles in a dedicated `filter_rules` table containing `id` (UUID PK), `user_id` (UUID FK to `users.id` ON DELETE CASCADE), `name` (VARCHAR(100)), `query_tree` (JSONB), `table_config` (JSONB), `pin_color_scheme` (JSONB), `created_at` (TIMESTAMPTZ), and `updated_at` (TIMESTAMPTZ).
- **REQ-MAIN-013**: **Ubiquitous**: The database schema shall enforce a unique constraint `uq_filter_rules_user_name` on `(user_id, name)` to guarantee per-tenant namespace isolation.
- **REQ-MAIN-014**: **State-Driven**: While executing any query or mutation on `filter_rules`, the backend repository shall enforce `WHERE user_id = :current_user_id` to strictly prevent cross-tenant data leakage.
- **REQ-MAIN-015**: **Event-Driven**: When the traveler clicks "Save Rule" with an existing rule name, the application shall prompt for overwrite confirmation and update the existing record upon confirmation.
- **REQ-MAIN-016**: **Event-Driven**: When the traveler clicks "Save As" and provides a unique rule name, the application shall insert a new independent `filter_rules` record.
- **REQ-MAIN-017**: **Event-Driven**: When the traveler selects a saved rule from the rule selector dropdown, the application shall load and apply its query tree, table column configuration, and map pin coloring scheme.
- **REQ-MAIN-018**: **Event-Driven**: When the traveler clicks "Delete Rule" and confirms, the backend shall delete the corresponding `filter_rules` record under tenant verification.
- **REQ-MAIN-019**: **Ubiquitous**: The table configuration (`table_config`) within a filter rule shall persist the visible column list, column order sequence, and sort specification (column identifier and sort direction: `asc`, `desc`, `unsorted`).
- **REQ-MAIN-020**: **Ubiquitous**: The map pin coloring configuration (`pin_color_scheme`) shall support four distinct coloring modes:
  1. `uniform`: A single specified hex color applied to all pins.
  2. `rating`: Discrete color mapping for star ratings 1 through 5.
  3. `visit_status`: Distinct colors for `not_visited`, `visited_return`, and `visited_do_not_return`.
  4. `custom`: A user-defined mapping of tag or status strings to hex colors.
- **REQ-MAIN-021**: **Event-Driven**: When a pin coloring scheme is active, the map rendering engine shall display pins matching the designated scheme colors.

#### POI Table Configuration & Multi-Select Mode

- **REQ-MAIN-022**: **Ubiquitous**: The POI Table shall default to single-select row interaction mode.
- **REQ-MAIN-023**: **State-Driven**: While multi-select mode is enabled via the UI toggle, the POI Table shall render a checkbox column as the first column of every row and display a bulk actions toolbar.
- **REQ-MAIN-024**: **State-Driven**: While multi-select mode is disabled, the POI Table shall hide all row checkboxes and the bulk actions toolbar.
- **REQ-MAIN-025**: **Event-Driven**: When the traveler clicks the header master checkbox in multi-select mode, the application shall toggle selection for all currently filtered POIs in the table.
- **REQ-MAIN-026**: **Ubiquitous**: The bulk actions toolbar shall display the count of currently selected POIs (enforcing a maximum selection ceiling of 500 POIs) and enable the "Bulk Actions" menu only when between 1 and 500 POIs are selected.

#### Bulk Operations Engine

- **REQ-MAIN-027**: **Event-Driven**: When the traveler triggers a bulk rating assignment, the backend shall update `rating = :new_rating` for all selected POI IDs owned by the authenticated user in a single database transaction.
- **REQ-MAIN-028**: **Event-Driven**: When the traveler triggers a bulk visit date assignment, the backend shall append the specified ISO-8601 date to `visited_dates`, update `already_visited = true`, and recompute `visit_pending` for each selected POI.
- **REQ-MAIN-029**: **Event-Driven**: When the traveler triggers a bulk "Visit Again" toggle, the backend shall update `want_to_visit_again = :value` and recompute `visit_pending` across all selected POIs.
- **REQ-MAIN-030**: **Event-Driven**: When the traveler triggers a bulk tag addition, the backend shall associate the specified tag with all selected POIs, skipping records where the tag already exists.
- **REQ-MAIN-031**: **Event-Driven**: When the traveler triggers a bulk tag removal, the backend shall remove the specified tag association from all selected POIs without raising errors on non-tagged records.
- **REQ-MAIN-032**: **Event-Driven**: When the traveler triggers a bulk list addition or removal, the backend shall insert or delete memberships in `poi_lists` idempotently for all selected POIs.
- **REQ-MAIN-033**: **Event-Driven**: When the traveler triggers a bulk update of City/Town, State/Province, or Country:
  1. The backend shall normalize the input values using the standard `address_normalizer` engine.
  2. If a selected POI possesses existing addresses in its `addresses` JSONB array, the backend shall update the specified field strictly on the primary (first) address entry in that array, leaving secondary address records unmodified.
  3. If a selected POI possesses an empty `addresses` array, the backend shall create a single new address record containing the updated fields and required country placeholder.
  4. If the traveler specifies a null/clear action, the backend shall set the specified field to `null` on the primary address entry without removing the address object itself.
- **REQ-MAIN-034**: **Event-Driven**: When the traveler triggers a bulk deletion, the backend shall verify tenant ownership, atomically delete all selected POIs, re-parent or cascade dependent references, and return the count of deleted records.
- **REQ-MAIN-035**: **Unwanted Behaviour**: If a bulk mutation payload contains more than 500 `poi_ids`, then the backend shall reject the operation returning an RFC 7807 422 Unprocessable Entity error detailing the batch limit violation; and if an unauthorized or cross-tenant POI ID is included in a bulk mutation payload, then the backend shall reject the operation or restrict mutation strictly to records owned by the authenticated user.

#### Map Pin Popup & Cluster Navigation

- **REQ-MAIN-036**: **Event-Driven**: When the traveler clicks a map cluster pin, the map engine shall compute the geographical bounding box of all clustered member POIs and smoothly zoom and pan to fit the bounding box within the viewport.
- **REQ-MAIN-037**: **State-Driven**: While the map zoom reaches maximum level ($z \ge 20$) and multiple POIs remain co-located, the map engine shall display an interactive spiderfied layout or co-located POI list.
- **REQ-MAIN-038**: **Event-Driven**: When the traveler clicks an unclustered POI pin on the map, the map engine shall open an anchored popup displaying:
  1. The POI canonical name.
  2. Star rating visual indicator (or "Unrated").
  3. Formatted address summary for single-address POIs, or a "Multiple Locations ({N})" badge for multi-address POIs.
  4. Thumbnail image preview if `image_urls` contains at least one valid image URL.
  5. An "Edit POI" action button.
- **REQ-MAIN-039**: **Event-Driven**: When the traveler clicks "Edit POI" inside a map pin popup, the application shall close the popup and open the `POIEditDrawer` pre-populated with that POI's aggregate record.
- **REQ-MAIN-040**: **Ubiquitous**: The POI Table shall continuously synchronize with the map viewport, displaying strictly the POIs located within the current map bounding box regardless of cluster state.

---

### Key Entities

- **FilterRule**: Represents a traveler's saved search, display, and coloring preference profile.
  - `id`: Unique UUID identifier.
  - `user_id`: Tenant owner UUID referencing `users.id`.
  - `name`: User-facing rule name (e.g., "High Priority Unvisited", "France Castles").
  - `query_tree`: Structured JSONB AST representing boolean condition clauses (`conjunction`, `rules`: `[{field, operator, value}]`).
  - `table_config`: Structured JSONB representing visible column IDs, column sequence array, and primary sort specification (`{column, direction}`).
  - `pin_color_scheme`: Structured JSONB representing the map coloring strategy (`mode`, `palette`, `default_color`, `rule_mappings`).
  - `created_at` / `updated_at`: Standard UTC timestamps.
- **BulkOperationRequest**: Pydantic schema representing batch mutations on an explicit array of POI UUIDs.
  - `poi_ids`: List of target POI UUIDs (min 1, max 500).
  - `action`: StrEnum (`set_rating`, `add_visit_date`, `set_visit_again`, `add_tag`, `remove_tag`, `add_to_list`, `remove_from_list`, `update_address_fields`, `delete`).
  - `payload`: Context-specific parameters (e.g., `{rating: 4}`, `{tag: "unesco"}`, `{city: "Kyoto", state_province: "Kyoto Prefecture", country: "Japan"}`).

---

## 4. Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: **Space Management Responsiveness**: Switching between `split`, `map_only`, and `table_only` modes completes and re-renders the viewport in under 100 milliseconds without page refresh or data re-fetching.
- **SC-002**: **Filter Query Execution Latency**: Applying a multi-clause visual filter against a dataset of up to 5,000 POIs evaluates and renders matching records in under 200 milliseconds.
- **SC-003**: **Rule Persistence Round-Trip**: Saving, loading, or updating a Filter Rule via the backend API completes in under 300 milliseconds.
- **SC-004**: **Bulk Operation Throughput**: Executing a bulk mutation on up to 500 selected POIs (tagging, rating, or address update) completes in a single database transaction in under 2.0 seconds.
- **SC-005**: **Map Cluster Zoom Responsiveness**: Clicking a cluster pin computes bounds and transitions the camera to the enclosing boundary in under 300 milliseconds.
- **SC-006**: **Zero Data Loss on Multi-Address Bulk Update**: When bulk-updating city, state, or country, 100% of existing street and postal code data on target address records is preserved without destructive truncation.
- **SC-007**: **Tenant Isolation Guarantee**: 100% of filter rules and bulk operations are strictly scoped to the authenticated user; cross-tenant query attempts return zero records or RFC 7807 404/403 responses.

---

## 5. Assumptions

- **MapLibre GL Compatibility**: The MapView component uses MapLibre GL 4+ with GeoJSON cluster sources; camera fitting is handled via standard `map.fitBounds()` calculations on cluster expansion.
- **Client vs. Server Filtering Scale**: Datasets with fewer than 1,000 POIs evaluate filter rules directly on the client using in-memory AST filtering for zero-latency UI response; datasets exceeding 1,000 POIs push filter parameters to the backend `/api/pois` endpoint with PostGIS bounding-box integration.
- **Address Normalization Consistency**: Bulk address field updates utilize the exact same standard English normalization dictionary implemented in `packages/core/vistarae_core/services/address_normalizer.py`.
- **Single-Page Context**: The layout state (`split`, `map_only`, `table_only`) is preserved in component state / local session storage during the active browser session, defaulting to `split` on initial login.
- **Transaction Safety**: Bulk operations execute within a single atomic SQLAlchemy async session (`async with session.begin():`) ensuring all-or-nothing execution.
