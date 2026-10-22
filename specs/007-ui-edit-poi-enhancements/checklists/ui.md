# UI Requirements Quality Checklist: Phase 7 — UI POI Editor Enhancements, Location Finder & Merge Workflow

**Purpose**: Validate the quality, completeness, clarity, and consistency of user interface requirements and interaction specifications for the POI Editor, Location Finder, Merge View, and Duplicate Collision workflows  
**Created**: 2026-10-21  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)

**Review Ownership**: This checklist is a reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when the reviewer determines the requirements-quality criterion is satisfied.  
**Marker Semantics**: `[x]` means the criterion has been reviewed and satisfied for requirements quality. It does not mean implementation work is complete.

---

## 1. POI Editor Form Controls & Data Entry Quality

- [x] CHK001 - Are multiline description formatting, maximum character constraints, and real-time character count display requirements explicitly specified? [Clarity, Spec §4.1 REQ-EDIT-001]
- [x] CHK002 - Are input constraints and unit formatting defined for estimated visit duration in both decimal hours and integer days? [Clarity, Spec §4.1 REQ-EDIT-006]
- [x] CHK003 - Are dynamic UI state transition rules defined for `source_type` selection and its conditional `source_value` input (URL vs directory vs upload vs disabled)? [Completeness, Spec §4.1 REQ-EDIT-007]
- [x] CHK004 - Are URL format validation and inline error messaging requirements documented for Official Website and Wikipedia link inputs? [Clarity, Spec §4.1 REQ-EDIT-008]
- [x] CHK005 - Are ascending chronological ordering, date addition via date picker, and individual date deletion controls clearly specified for visited dates? [Completeness, Spec §4.1 REQ-EDIT-010]
- [x] CHK006 - Are visual status indicators or badge representations defined for derived visit lifecycle flags (`already_visited`, `visit_pending`)? [Completeness, Spec §4.1 REQ-EDIT-011]
- [x] CHK007 - Are photo directory path input requirements defined for both manual text entry and the File System Access API (`showDirectoryPicker`) fallback? [Completeness, Spec §4.1 REQ-EDIT-005]

---

## 2. Parent POI Typeahead & Hierarchy Requirements Quality

- [x] CHK008 - Are typeahead input debouncing thresholds, minimum query character triggers, and matching highlight styles explicitly quantified? [Clarity, Spec §4.1 REQ-EDIT-012]
- [x] CHK009 - Are requirements specified for displaying the resolved parent POI name versus storing the underlying `parent_poi_id`? [Consistency, Spec §4.1 REQ-EDIT-013]
- [x] CHK010 - Are UI filtering requirements documented to exclude the active POI and its existing descendants from parent dropdown options? [Coverage, Spec §4.1 REQ-EDIT-014]
- [x] CHK011 - Does the spec define clear user interaction requirements for clearing or disassociating an assigned parent POI back to top-level status? [Completeness, Spec §2 User Story 1]
- [x] CHK012 - Can the 100 millisecond response time for typeahead dropdown filtering over 1,000 POIs be objectively measured? [Measurability, Spec §6 SC-007]

---

## 3. Multi-Address Editor & Normalization Requirements Quality

- [x] CHK013 - Are visual card or block layout requirements defined for adding, reordering, and deleting multiple address records on a single POI? [Completeness, Spec §4.1 REQ-EDIT-002]
- [x] CHK014 - Is the required visual distinction between mandatory fields (Country) and optional fields (Street, City, State, Zip) clearly specified? [Clarity, Spec §4.1 REQ-EDIT-004]
- [x] CHK015 - Are UI feedback mechanisms specified when state/province or country names are normalized to English standard nomenclature upon save? [Coverage, Spec §4.1 REQ-EDIT-003]
- [x] CHK016 - Does the spec document layout and truncation requirements for trans-boundary multi-address sites in table and list summaries? [Edge Case, Spec §3 Edge Cases]

---

## 4. Location Finder Map Workspace Requirements Quality

- [x] CHK017 - Are modal layout dimensions, responsive viewport breakpoints, and layer switcher controls (satellite, terrain, street) fully specified? [Completeness, Spec §4.2 REQ-LOC-001]
- [x] CHK018 - Are default centering rules and initial zoom levels unambiguous for POIs with existing coordinates versus POIs without coordinates? [Consistency, Spec §4.2 REQ-LOC-002]
- [x] CHK019 - Are adaptive zoom levels quantified with explicit numeric map zoom integers for broad cities (zoom 10–12) versus specific monuments (zoom 16–18)? [Clarity, Spec §4.2 REQ-LOC-003]
- [x] CHK020 - Is the candidate match pin limit $X$ specified with a concrete default value and configuration mechanism? [Clarity, Spec §4.2 REQ-LOC-004]
- [x] CHK021 - Are banner placement, styling, and action prompt requirements documented for high-cardinality search refinement warnings? [Completeness, Spec §4.2 REQ-LOC-005]
- [x] CHK022 - Are notification requirements specified for empty queries or searches yielding zero candidate matches? [Coverage, Spec §4.2 REQ-LOC-006]
- [x] CHK023 - Are active marker styling, drag/drop interactions, and live decimal coordinate readout formats explicitly defined? [Clarity, Spec §4.2 REQ-LOC-007]
- [x] CHK024 - Is non-destructive draft coordinate application on "Apply" clearly distinguished from database persistence on "Save"? [Consistency, Spec §4.2 REQ-LOC-009]

---

## 5. POI Merge Comparison & Synthesis Requirements Quality

- [x] CHK025 - Are dual-column comparison layout specifications defined for distinguishing Source POI from Target POI? [Completeness, Spec §4.3 REQ-MERGE-001]
- [x] CHK026 - Are visual diffing criteria and default state requirements specified for the "Show all fields" toggle? [Clarity, Spec §4.3 REQ-MERGE-002]
- [x] CHK027 - Are radio button interaction rules and default pre-selections defined for all scalar attribute rows? [Consistency, Spec §4.3 REQ-MERGE-003]
- [x] CHK028 - Are checkbox selection states, select-all controls, and union de-duplication rules defined for multi-value set attributes? [Completeness, Spec §4.3 REQ-MERGE-004]
- [x] CHK029 - Does the spec define confirmation dialog warning prompts before permanently deleting the source POI and re-parenting child records? [Coverage, Spec §4.3 REQ-MERGE-005]

---

## 6. Duplicate Collision Dialog & Save Workflow Quality

- [x] CHK030 - Are dialog layout, conflicting POI summary cards, and the three actionable buttons (Create New, Merge, Cancel) explicitly specified? [Completeness, Spec §4.4 REQ-SAVE-003]
- [x] CHK031 - Is in-memory draft preservation into the POI Merge workspace documented with zero data loss on collision triage? [Clarity, Spec §4.4 REQ-SAVE-003]
- [x] CHK032 - Are visual save-in-progress loading spinners and button disablement states specified to prevent duplicate double-submit requests? [Coverage, Spec §4.4 REQ-SAVE-001]

---

## 7. Interaction States, Feedback & Accessibility Quality

- [x] CHK033 - Are focus trapping, keyboard navigation (`Escape` to close, `Tab` cycling), and ARIA attributes defined for all modal dialogs? [Accessibility, Spec §2 User Scenarios]
- [x] CHK034 - Are loading skeletons or asynchronous spinners defined for reverse geocoding, typeahead lookups, and duplicate collision checks? [Completeness, Spec §5 Data Models]
- [x] CHK035 - Are RFC 7807 ProblemDetails error notification toast/banner requirements specified for network failures and validation rejections? [Consistency, Spec §4.1 REQ-EDIT-004]
- [x] CHK036 - Can the 15-second landmark search and coordinate pin application target be objectively measured during UX evaluations? [Measurability, Spec §6 SC-001]

---

## Notes

- Mark items `[x]` only after review confirms the requirement-quality criterion is satisfied
- Leave items unchecked when they still require clarification, correction, or reviewer evaluation
- `/speckit-implement` reads checklist checkbox state as a gate and must not modify markers
- Items are numbered sequentially (CHK001–CHK036) for easy reference and audit tracking
