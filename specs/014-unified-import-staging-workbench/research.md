# Research & Architecture Decisions: Unified POI Import Staging Workbench

**Feature**: `014-unified-import-staging-workbench`  
**Date**: 2026-11-02  
**Status**: Completed  

---

## 1. Single-Stage Import Workbench vs Multi-Phase Modals

### Decision
Deprecate the two-phase modal wizard (`CSVTriageModal` $\rightarrow$ `CSVPhase2ReviewModal`) in favor of a single unified component: `CSVImportWorkbenchModal.tsx`.

### Rationale
- **Zero Backtracking**: Triage (geocoding, exclusion checks, duplicate resolution, parent assignment) and enrichment (photos, descriptions, durations, websites, tags) operate on the same `IngestCandidate` entity. A single-screen master-detail layout allows users to inspect and edit any attribute at any time.
- **Mental Model Alignment**: Travelers perceive their CSV rows as candidate places to verify. Forcing a linear sequence where geocoding must be completed before reviewing photos causes frustration when an enriched photo or description reveals that a coordinate or address was inaccurate.
- **Simpler State Management**: Eliminates synchronization bugs and race conditions between Phase 1 and Phase 2 transition state.

### Alternatives Considered
- *Retaining Two Phases with Bi-Directional State*: Adding a "Back" button that re-opens Phase 1 with preserved state. Rejected because it retains modal transition delays, cognitive friction, and duplicate UI logic.
- *Tabbed View Inside One Modal*: Creating a "Triage" tab and an "Enrichment" tab. Rejected because users still have to switch tabs to see complete information for a single POI.

---

## 2. Targeted Single-POI Enrichment Endpoint Architecture

### Decision
Expose an on-demand single candidate enrichment endpoint:
`POST /api/ingest/jobs/{job_id}/candidates/{candidate_id}/enrich`

### Rationale
- **Low Latency & Immediate Feedback**: When inspecting a specific candidate (e.g. *Caerleon Roman Legion Museum*), the traveler can trigger targeted enrichment and receive updated photos, websites, and descriptions within 1.5–3.0 seconds directly in the active editor.
- **Selective Recalculation**: Only blank/missing fields are populated; existing user inputs are never overwritten.
- **No Queue Contention**: Directly queries the enricher pipeline without waiting behind a 250-item background queue.

### Alternatives Considered
- *Triggering Batch Enrichment for 1 Record via SQS*: Re-enqueuing a batch job of size 1. Rejected due to SQS dispatch overhead and polling latency.
- *Client-Side Scraping*: Scraping directly from the browser. Rejected due to CORS restrictions and security principles in the constitution.

---

## 3. "No Websites" Idempotency & State Tracking Engine

### Decision
Add `no_websites: bool = False` to `IngestCandidate` domain model, database table `ingest_candidates`, and API schemas.

### Rationale
- **Rate Limit & Quota Preservation**: When AI enrichment and Wikidata search confirm that an obscure landmark has no web presence, setting `no_websites = True` prevents redundant external Nominatim/Wikidata/search engine queries on subsequent batch or single enrichment runs.
- **Clear UI State Machine**:
  - `related_websites.length > 0`: Checkbox is unchecked and disabled.
  - `related_websites.length == 0`: Checkbox is enabled for manual toggling.
  - Enrichment yields 0 sites: Checkbox is automatically set to `True`.
  - Adding a URL while checked: Checkbox immediately reverts to `False` and becomes disabled.

### Alternatives Considered
- *Inference Based on Empty String Array*: Assuming empty `related_websites == []` means no websites exist. Rejected because it cannot differentiate between "not yet searched" and "searched, confirmed none exist".

---

## 4. In-Batch Merge & Attribute Aggregation Strategy

### Decision
When Candidate B is marked `In-Batch Merge` with Candidate A as target:
1. Candidate A remains the primary candidate with authoritative name, coordinates, address, and primary description.
2. Upon saving or committing to PostGIS:
   - Unique URLs from Candidate B's `related_websites` are appended to Candidate A's `related_websites`.
   - Distinct tags from Candidate B are merged into Candidate A's `tags`.
   - Candidate B's visit notes and reason to visit are appended to Candidate A's notes (separated by newlines with candidate source attribution).
3. Candidate B is marked `merged` and pruned upon final commit.

### Rationale
- Prevents accidental loss of unique metadata that may have been spread across duplicate CSV entries (e.g. one row had the phone number or custom note, while the other had coordinates).

### Alternatives Considered
- *Total Overwrite / Discard*: Completely discarding Candidate B's attributes upon merge. Rejected because it discards valuable user data from multi-source spreadsheets.
- *Interactive Diff Wizard*: Requiring the user to manually select each attribute to keep. Rejected as overly complex for standard travel imports; automated non-conflicting union is faster and non-destructive.

---

## 5. Multi-Level Sublocation Hierarchy with Acyclic Cycle Detection

### Decision
Support arbitrary parent-child hierarchy depth (e.g. *Region $\rightarrow$ Park $\rightarrow$ District $\rightarrow$ Trailhead*) using a recursive ancestor check during parent assignment.

### Rationale
- Real-world attractions have nested sub-locations. Restricting hierarchies to 1 level forces unnatural grouping.
- **Cycle Prevention Algorithm**:
  When setting `candidate.parent_poi_id = P`:
  1. Traverse the parent chain of `P` up to the root.
  2. If `candidate.id` is encountered anywhere in `P`'s ancestor path, raise an HTTP 422 `ValidationException`: *"Circular hierarchy detected: Candidate cannot be a sublocation of its own descendant"*.

### Alternatives Considered
- *Fixed 1-Level Parent-Child*: Sublocations can only link to top-level root POIs. Rejected because it fails to represent natural travel structures (e.g. exhibits inside museums inside historic districts).

---

## 6. Active Staging Session Guard

### Decision
When `POST /api/ingest/upload` receives a new CSV upload, check if the authenticated user has an active uncommitted `IngestStagingJob` with status `staged` or `enriching`.
If found, reject with HTTP 409 Conflict / RFC 7807 `ProblemDetails`:
`"Active import session in progress. Please commit or discard job {active_job_id} before uploading a new CSV."`

### Rationale
- Protects travelers from accidentally losing hours of triage/enrichment work by dropping a second file onto the dropzone.
- Follows the user's explicit preference for Option B (Strict Guard).

---

## 7. Background Batch Enrichment with Non-Blocking UI

### Decision
Use Server-Sent Events (SSE) or lightweight HTTP polling (`GET /api/ingest/jobs/{job_id}/candidates?phase=staging&updated_since=...`) where the background worker processes candidates with a 1.0s token-bucket rate limiter for external calls, while the frontend dynamically updates candidate rows in-place.

### Rationale
- The user can continue inspecting, editing coordinates, or fixing notes on Candidate #10 while Candidates #1 through #9 are being enriched in the background.
- Eliminates blocking modal overlays.

