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

# Extension Requirements Quality Checklist: Phase 9 — Extension Enhancements

**Purpose**: Validate the quality, completeness, clarity, and consistency of requirements for Chrome Extension enhancements, authentication gate, schema parity, multi-source scraping, intelligent geocoding, and scale-aware duplicate triage.  
**Created**: 2026-10-22  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)  

**Review Ownership**: This checklist is a reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when the reviewer determines the requirements-quality criterion is satisfied.  
**Marker Semantics**: `[x]` means the criterion has been reviewed and satisfied for requirements quality. It does not mean implementation work is complete.

---

## 1. Extension Streamlining & Informational Hub Requirements Quality

- [ ] CHK001 - Are the specific UI components slated for removal (CSV export button, tabular POI table, search box, category select) explicitly enumerated? [Completeness, Spec §1 Pillar 2, §4 REQ-EXT-011]
- [ ] CHK002 - Is the replacement educational overview content (Vistarae mission, keystroke instructions, server health, web app link) explicitly defined with layout requirements? [Clarity, Spec §4 REQ-EXT-013]
- [ ] CHK003 - Is the prohibition against displaying demo or mock records (`Glacier Point Overlook`, `Mist Trail`) unambiguous across all empty and offline states? [Consistency, Spec §4 REQ-EXT-012, §5 SC-006]
- [ ] CHK004 - Are visual branding, typography, and styling tokens for the extension companion dashboard aligned with the Web App design language? [Consistency, Spec §1 Pillar 2]
- [ ] CHK005 - Does the specification define what happens when the extension fails to connect to the backend gateway on initial load? [Coverage, Edge Case, Spec §4 REQ-EXT-012]

---

## 2. Authentication Gate & Identity Context Requirements Quality

- [ ] CHK006 - Is the pre-capture authentication check explicitly required to execute before any DOM overlay injection or scraping logic occurs? [Completeness, Spec §3 Story 2, §4 REQ-EXT-008]
- [ ] CHK007 - Is the unauthenticated redirect flow (opening Web App login with return parameter) clearly specified for keystroke and context menu triggers? [Clarity, Spec §4 REQ-EXT-009]
- [ ] CHK008 - Are requirements defined for displaying the authenticated user's email address and badge consistently in both the companion dashboard and the Shadow DOM overlay? [Consistency, Spec §4 REQ-EXT-010]
- [ ] CHK009 - Are session expiration handling and token refresh workflows explicitly documented when tokens expire during active browsing? [Coverage, Edge Case, Spec §3 Edge Cases]
- [ ] CHK010 - Can the pre-capture authentication gate and redirect behavior be objectively tested in isolation? [Measurability, Spec §3 Story 2 Acceptance 1]

---

## 3. Capture Overlay & 1:1 Schema Parity Requirements Quality

- [ ] CHK011 - Are all 13 core POI fields verified for 1:1 schema parity between the capture overlay form and the Web App POI Editor? [Completeness, Spec §4 REQ-EXT-014]
- [ ] CHK012 - Is the exclusion of the local photo folder field (`photo_folders`) during web scraping explicitly mandated? [Consistency, Spec §4 REQ-EXT-015]
- [ ] CHK013 - Is the star rating input explicitly specified to remain unassigned/blank by default, requiring manual traveler evaluation? [Clarity, Spec §4 REQ-EXT-016]
- [ ] CHK014 - Are Shadow DOM style encapsulation requirements specified to prevent host website CSS collisions? [Completeness, Spec §6 A-002, GEMINI.md §5]
- [ ] CHK015 - Are keyboard navigation patterns (Escape to close, Tab traversal, Enter to submit) documented for the capture overlay modal? [Coverage, Spec §3 Story 3]
- [ ] CHK016 - Can the sub-400 millisecond keystroke-to-overlay rendering ceiling be objectively measured across diverse websites? [Measurability, Spec §5 SC-003]

---

## 4. Multi-Source Scraping & Augmentation Pipeline Requirements Quality

- [ ] CHK017 - Is the order of operations explicitly specified: primary page extraction $\rightarrow$ English name determination $\rightarrow$ secondary augmentation? [Clarity, Spec §4 REQ-EXT-017, REQ-EXT-018]
- [ ] CHK018 - Are the user-configurable scraping domains (`valid_scraping_domains`) explicitly constrained to authorized preferences? [Consistency, Spec §2 Q1, §4 REQ-EXT-019]
- [ ] CHK019 - Is the 3.0-second timeout ceiling and graceful partial fallback behavior clearly defined when secondary sources stall or return 429/403? [Completeness, Spec §2 Q3, §4 REQ-EXT-020, §5 SC-004]
- [ ] CHK020 - Are requirements defined for tracking and recording all queried domains in the POI's `extraction_sources` array? [Completeness, Spec §4 REQ-EXT-021]
- [ ] CHK021 - Is the Gemini Flash-Lite summary synthesis explicitly constrained to `thinking_budget = 0` and structured Pydantic output? [Clarity, Spec §4 REQ-EXT-028, GEMINI.md §2]
- [ ] CHK022 - Are fallback requirements specified when the host website is a paywalled, obfuscated SPA, or canvas-based page? [Coverage, Edge Case, Spec §3 Edge Cases]

---

## 5. Intelligent Geocoding & Addressing Requirements Quality

- [ ] CHK023 - Is the internal PostGIS `geocoding_cache` query hash (SHA-256) check explicitly required prior to dispatching any external HTTP request? [Completeness, Spec §4 REQ-EXT-022, GEMINI.md §3]
- [ ] CHK024 - Is the OpenStreetMap Nominatim rate-limiting policy (maximum 1 req/sec with custom `User-Agent: VistaraeTravelEngine/1.0`) unambiguously specified? [Clarity, Spec §4 REQ-EXT-023, GEMINI.md §3]
- [ ] CHK025 - Are reverse geocoding requirements defined when coordinates are present but street or administrative data are missing? [Completeness, Spec §4 REQ-EXT-024]
- [ ] CHK026 - Are multi-address generation requirements explicitly documented for natural landmarks spanning multiple administrative regions (states or countries)? [Coverage, Spec §4 REQ-EXT-026]
- [ ] CHK027 - Is the standardization of country names to English ISO 3166-1 alpha-3 common names explicitly required? [Consistency, Spec §4 REQ-EXT-025]
- [ ] CHK028 - Can the 80% cache-hit efficiency target for repeat geocoding queries be objectively measured? [Measurability, Spec §5 SC-005]

---

## 6. Scale-Aware Duplicate & Nesting Triage Requirements Quality

- [ ] CHK029 - Is the early triage execution window (initial 500ms of analysis) explicitly specified? [Clarity, Spec §4 REQ-EXT-030]
- [ ] CHK030 - Are spatial footprint scale categories (Macro: 5,000m; Medium: 500m; Micro: 50m) quantified with specific distance radii? [Clarity, Spec §2 Q2, §4 REQ-EXT-031]
- [ ] CHK031 - Is the dual-threshold heuristic distinguishing `POTENTIAL_DUPLICATE` ($\ge 0.60$ similarity) from `NEARBY_PARENT` ($< 0.60$ similarity with larger scale) unambiguously defined? [Consistency, Spec §2 Q5, §4 REQ-EXT-031]
- [ ] CHK032 - Are user interaction requirements and button states explicitly defined for all three triage actions: "Proceed", "Make Child", and "Abort"? [Completeness, Spec §4 REQ-EXT-032]
- [ ] CHK033 - Are data persistence requirements specified for storing `parent_poi_id` and `parent_poi_name` when "Make Child" is selected? [Completeness, Spec §4 REQ-EXT-032]
- [ ] CHK034 - Are circular parenting prevention safeguards specified to disallow selecting a descendant POI as a parent? [Coverage, Edge Case, Spec §3 Edge Cases]
- [ ] CHK035 - Can the 5-second triage task completion threshold be objectively measured? [Measurability, Spec §5 SC-007]

---

## 7. Tag Matching & Recommendation Requirements Quality

- [ ] CHK036 - Are tag recommendation requirements clear when scraped text matches an alias shared across multiple tags (recommending all matching tags)? [Clarity, Spec §2 Q2, §4 REQ-EXT-029]
- [ ] CHK037 - Is the restriction that travelers may only assign tags belonging to their vetted user tag library strictly enforced? [Consistency, Spec §4 REQ-EXT-029, §5 SC-001]
- [ ] CHK038 - Are UI controls defined in the capture overlay for travelers to easily toggle, add, or deselect recommended tags? [Completeness, Spec §3 Story 3 Acceptance 4]

---

## 8. Observability, Telemetry & Boundary Validation Quality

- [ ] CHK039 - Are standard W3C tracing headers (`traceparent`, `X-Source: extension`, `X-Destination: backend`) explicitly mandated for every extension API call? [Completeness, Spec §4 REQ-EXT-033, GEMINI.md §1]
- [ ] CHK040 - Are directional logging tags (`MSG ->|`, `MSG <-|`, `MSG |->`, `MSG |<-`) mandated for all cross-boundary extension interactions in local development? [Consistency, Spec §4 REQ-EXT-033, Constitution Core Principle 7]
- [ ] CHK041 - Are boundary payloads validated using Pydantic v2 `StrictBaseModel` with `extra="forbid"`, returning RFC 7807 `ProblemDetails` on validation failure? [Consistency, Spec §4 REQ-EXT-034, Constitution Core Principle 5]

---

## Notes

- Mark items `[x]` only after review confirms the requirement-quality criterion is satisfied
- Leave items unchecked when they still require clarification, correction, or reviewer evaluation
- `/speckit-implement` reads checklist checkbox state as a gate and must not modify markers
- Items are numbered sequentially (CHK001–CHK041) for traceability across reviews
