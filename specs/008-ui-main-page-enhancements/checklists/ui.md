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

# UI Requirements Quality Checklist: Phase 8 — UI Main Page Enhancements

**Purpose**: Validate the quality, completeness, clarity, and consistency of user interface and interaction specifications for Space Management, Visual POI Filter Rules, Multi-Select Bulk Actions, and Map Cluster Navigation & Pin Popups  
**Created**: 2026-10-22  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)

**Review Ownership**: This checklist is a reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when the reviewer determines the requirements-quality criterion is satisfied.  
**Marker Semantics**: `[x]` means the criterion has been reviewed and satisfied for requirements quality. It does not mean implementation work is complete.

---

## 1. Space Management & Viewport Focus Modes Requirements Quality

- [x] CHK001 - Are layout toggle interaction controls, segmented button styling, and keyboard access patterns explicitly defined for switching between `split`, `map_only`, and `table_only` modes? [Completeness, Spec §3 REQ-MAIN-001]
- [x] CHK002 - Is the layout persistence lifecycle explicitly clarified as in-memory session-only rather than database-backed user preferences? [Clarity, Spec §Clarifications Q3, REQ-MAIN-001]
- [x] CHK003 - Are horizontal width allocation proportions and CSS flex behaviors specified for both Map and Table in `split`, `map_only`, and `table_only` states? [Clarity, Spec §3 REQ-MAIN-002, REQ-MAIN-003, REQ-MAIN-004]
- [x] CHK004 - Are state preservation requirements documented for active POI selection, scroll position, and multi-select checkbox status during layout transitions? [Consistency, Spec §3 REQ-MAIN-005]
- [x] CHK005 - Can the sub-100 millisecond transition and viewport re-rendering threshold without page refresh be objectively measured? [Measurability, Spec §4 SC-001]
- [x] CHK006 - Are visual transitions or animation smoothing requirements specified for container collapsing and expanding? [Coverage, Spec §1 Pillar 1]

---

## 2. Visual POI Query Builder Requirements Quality

- [x] CHK007 - Are expand and collapse triggers, transition states, and container positioning above the map and table explicitly specified for the filter panel? [Completeness, Spec §3 REQ-MAIN-006, REQ-MAIN-007]
- [x] CHK008 - Are visual builder UI component patterns (dropdowns, tag chips, conjunction toggles) defined for constructing nested `AND`/`OR` boolean logic trees? [Completeness, Spec §3 REQ-MAIN-008]
- [x] CHK009 - Are input controls, allowed operators, and value constraints explicitly defined for each of the 10 supported filter dimensions (city, state, country, has_parent, visit_pending, already_visited, rating, list_id, visit_state, tag)? [Clarity, Spec §3 REQ-MAIN-009]
- [x] CHK010 - Is the hybrid filter evaluation threshold (<1,000 client in-memory vs. >=1,000 backend PostGIS AST) clearly specified with boundary handling? [Consistency, Spec §Clarifications Q1, REQ-MAIN-010]
- [x] CHK011 - Are UI empty states, reset triggers, and zero-match user feedback requirements defined when filters produce no matching POIs? [Coverage, Spec §2 Edge Cases, REQ-MAIN-011]
- [x] CHK012 - Can the sub-200 millisecond query execution latency for multi-clause filters across 5,000 POIs be objectively measured? [Measurability, Spec §4 SC-002]

---

## 3. Filter Rule Persistence & Color Schemes Requirements Quality

- [x] CHK013 - Are modal workflows and input validation rules defined for naming and saving a new Filter Rule (`name` 1–100 chars)? [Completeness, Spec §3 REQ-MAIN-012]
- [x] CHK014 - Are confirmation dialog patterns and overwrite behavior explicitly specified when saving a rule with an existing name owned by the user? [Clarity, Spec §3 REQ-MAIN-015, Spec §2 Edge Cases]
- [x] CHK015 - Are independent duplication and branching requirements clearly defined for the "Save As" action? [Consistency, Spec §3 REQ-MAIN-016]
- [x] CHK016 - Are destructive confirmation prompts and UI reset states specified when deleting an existing Filter Rule? [Coverage, Spec §3 REQ-MAIN-018]
- [x] CHK017 - Are UI interactions specified for column visibility selection, drag-and-drop reordering, and three-state sort toggling (asc, desc, unsorted) within table configuration? [Completeness, Spec §3 REQ-MAIN-019]
- [x] CHK018 - Are color palette pickers and value mapping controls documented for all four pin coloring modes (`uniform`, `rating`, `visit_status`, `custom`)? [Clarity, Spec §3 REQ-MAIN-020]
- [x] CHK019 - Are tenant isolation boundaries in the UI verified so that User A cannot view, load, or overwrite Filter Rules owned by User B? [Consistency, Spec §3 REQ-MAIN-014, SC-007]

---

## 4. POI Table Multi-Select Mode & Bulk Operations Requirements Quality

- [x] CHK020 - Are UI toggle placement, visual state styling, and row checkbox column rendering rules defined for transitioning between single-select and multi-select modes? [Completeness, Spec §3 REQ-MAIN-022, REQ-MAIN-023, REQ-MAIN-024]
- [x] CHK021 - Are selection behavior requirements specified for the header master checkbox across filtered subsets versus full dataset? [Clarity, Spec §3 REQ-MAIN-025]
- [x] CHK022 - Is the 500-record synchronous batch ceiling clearly enforced with UI counters and disabled trigger states when >500 items are selected? [Clarity, Spec §Clarifications Q4, REQ-MAIN-026, REQ-MAIN-035]
- [x] CHK023 - Are modal dialogs and form controls defined for bulk setting star ratings (0–5) with single-transaction atomicity? [Completeness, Spec §3 REQ-MAIN-027]
- [x] CHK024 - Are date picker controls and automatic lifecycle flag recalculation rules (`already_visited = true`, `visit_pending` update) specified for bulk visit date assignment? [Consistency, Spec §3 REQ-MAIN-028]
- [x] CHK025 - Are boolean toggle controls and lifecycle update rules defined for bulk "Visit Again" operations? [Completeness, Spec §3 REQ-MAIN-029]
- [x] CHK026 - Are idempotent tag search/creation and removal controls specified for bulk tagging without raising errors on non-tagged records? [Coverage, Spec §3 REQ-MAIN-030, REQ-MAIN-031]
- [x] CHK027 - Are curated list selection dropdowns and idempotent membership insertion/removal rules defined for bulk list operations? [Completeness, Spec §3 REQ-MAIN-032]
- [x] CHK028 - Is non-destructive primary address targeting (`addresses[0]` update, preserving secondary records) explicitly specified for bulk city, state, and country changes? [Consistency, Spec §Clarifications Q2, REQ-MAIN-033]
- [x] CHK029 - Are address normalization feedback and English standardization requirements defined for bulk location updates? [Clarity, Spec §3 REQ-MAIN-033, Assumptions]
- [x] CHK030 - Are destructive deletion confirmation dialogs, cascade warnings, and affected count summaries specified for bulk deletion? [Coverage, Spec §3 REQ-MAIN-034]
- [x] CHK031 - Can the 2.0-second transaction execution threshold for bulk mutations across up to 500 POIs be objectively measured? [Measurability, Spec §4 SC-004]

---

## 5. Map Canvas, Cluster Navigation & Rich Pin Popups Requirements Quality

- [x] CHK032 - Are cluster click camera easing parameters (bounding box computation, padding, and 300ms transition duration) explicitly specified? [Clarity, Spec §3 REQ-MAIN-036, SC-005]
- [x] CHK033 - Are spiderfied layout or co-located POI list disambiguation requirements defined for co-located pins at maximum zoom ($z \ge 20$)? [Edge Case, Spec §3 REQ-MAIN-037]
- [x] CHK034 - Are visual elements, typography, and card dimensions specified for the unclustered POI pin popup card (`POIPopupCard`)? [Completeness, Spec §3 REQ-MAIN-038]
- [x] CHK035 - Is the visual badge format and count display explicitly specified for multi-address POIs ("Multiple Locations ({N})") in pin popups? [Clarity, Spec §3 REQ-MAIN-038]
- [x] CHK036 - Are image thumbnail dimensions, aspect ratio constraints, and fallback placeholder rules defined when POIs have image URLs? [Coverage, Spec §3 REQ-MAIN-038]
- [x] CHK037 - Does the spec define transition requirements for closing the popup and opening `POIEditDrawer` pre-populated with the target POI on "Edit POI" click? [Consistency, Spec §3 REQ-MAIN-039]
- [x] CHK038 - Are continuous bidirectional synchronization requirements between visible map bounding box and POI table rows clearly documented? [Consistency, Spec §3 REQ-MAIN-040]

---

## Notes

- Mark items `[x]` only after review confirms the requirement-quality criterion is satisfied.
- Leave items unchecked (`[ ]`) when they still require clarification, correction, or reviewer evaluation.
- `/speckit-implement` reads checklist checkbox state as a quality gate and must not modify markers.
- Built-in specification quality checklist `checklists/requirements.md` is maintained separately by `/speckit-specify` and `/speckit-clarify`.
- Items are numbered sequentially (`CHK001` through `CHK038`) for precise cross-referencing in pull request discussions and code reviews.
