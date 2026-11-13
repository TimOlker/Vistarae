# Feature Specification: AI Bulk Enrichment (018-bulk-ai-enrich)

**Feature Branch**: `018-bulk-ai-enrich`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "When running a 'AI Enrich All' currently the user had no visibility to what was going on, no status bar was displayed. POIs were failing since gemini resources had run out and processing kept proceeding, wasting resources and time. A fail fast style logic is needed. In the POI Import Staging Workbench when clicking 'AI Enrich All': When clicked this should continue the existing logic to loop through the POIs in the POI Import Staging Workbench and look for the fields previously targeted to be populated by webscraping and AI. The AI enrichment should only be available to users on a premium subscription level. The editing of the list of POIs should be disabled during this processing to avoid a race condition like the user deleting an existing POI or adding a new one. When processing completes, either successfully or unsuccessfully, re-enable. All of the selected POIs on the 'POI Import Staging Workbench' should be added to a queue. If no POIs are selected, prompt the user if all POIs should be processed, if the user says 'yes', all POIs should be added to the queue, if the user says 'No' abort processing. This should continue to send a fixed number POIs from the queue at a time to an independent processing logic worker that can be scaled horizontally (like an AWS lambda). This number should be configurable in an environment variable. When processing the first record, treat it like a canary - do not submit multiple records in parallel, make sure the first canary POI record is processed to avoid consuming multiple records resources. Each processing logic worker should return details on processing results. It should return a result code that indicates if the worker was successful, if it encountered an internal error, if it encountered a blocking external error (like resources exhausted or a quota limit reached that will likely mean future POIs being processed will fail) and temporary external error (like a record was not found). A detailed error text message describing the error should be returned as well. The time taken to process the POI should be returned as well as a count of resources used. When the producer that sent the request receives a blocking external error (like resources exhausted or a quota limit reached that will likely mean future POIs being processed will fail), do not submit additional POIs in the queue to the worker to be processed. Allow any previously submitted POIs to complete processing. When all workers have completed, then end the processing. While processing there should be a progress bar displayed to the user showing the total number of POIs in the queue, the number of POIs that successfully processed, the number of POIs that encountered an issue, and the number of POIs remaining, along with the percentage of processing. The number of POIs currently being processed should be displayed. The total time taken so far should be displayed. Average time to process a POI if possible would be useful. The bar should also have a 'Cancel' button that allows processing to gracefully to be ended. This will work similar to when an error is detected - stop submitting additional POIs to the worker and wait for the consumer workers to finish. When processing completes (success or unsuccessfully) - display an information window with stats (count of POIs processed successfully, count of unsuccessfully (by error status), count of unprocessed POIs, total duration, average time to process a POI, a total count of resources used across all POIs. Also include the reason for ending processing - all records processed, an error, user cancel, etc. In the log have a unique UUID that can be used to associate a request sent from the producer and then consumed by the worker. A unique number of the queue position for each item should also be recorded. Processing does not need to be sequential, but it should allow a user looking at the log in the consumer and the producer to have an idea of how much processing has completed. In the worker logs include the POI name being processed with the queue position and total queue like [X of Y]. Please flag any contradictions with previous logic or missing logic or features to include that might be useful."

## Architecture Alignment & Contradictions with Previous Logic

The following contradictions, superseded behaviors, and architectural refinements have been identified between this specification and legacy/previous implementations:

1. **Subscription Level Gate**:
   - _Previous Logic_: In earlier iterations of the workbench, "AI Enrich All" was accessible to all authenticated users regardless of tier.
   - _New Specification_: Bulk AI enrichment is restricted exclusively to travelers possessing an active `PREMIUM` subscription. Non-premium users see a locked state with an upgrade prompt in the UI and receive an explicit HTTP 403 Forbidden on the API.
2. **Execution Model & Queue Topology**:
   - _Previous Logic_: Background enrichment executed as an untracked in-memory `asyncio.create_task` looping sequentially through candidates within the FastAPI gateway process, providing no visibility and ignoring server restarts.
   - _New Specification_: Producer-worker architecture. A dedicated producer enqueues target candidates, coordinates a horizontal worker pool governed by a configurable concurrency ceiling (`BULK_ENRICHMENT_CONCURRENCY`), dispatches a canary record first, and streams real-time status.
3. **Selection-Aware Scope**:
   - _Previous Logic_: Clicking "AI Enrich All" previously evaluated all non-ignored candidates across the entire import job, ignoring candidate checkboxes.
   - _New Specification_: Selected table rows explicitly determine the enrichment queue. If no rows are selected, an interactive confirmation dialog prompts the user to either enrich all eligible candidates or cancel.
4. **Fail-Fast Error Classification vs. Silent Fallback**:
   - _Previous Logic_: When external services failed (such as Gemini HTTP 402 `RESOURCE_EXHAUSTED` or 429 quota exhaustion), errors were logged as warnings while execution silently fell back to local heuristics and continued burning resources across the rest of the queue.
   - _New Specification_: Fail-fast circuit breaking. If any worker reports a `BLOCKING_EXTERNAL_ERROR`, the producer immediately stops dispatching new items from the queue, allows in-flight workers to drain, halts the session, and surfaces a detailed post-run audit to the traveler.
5. **UI Interactivity & Mutual Exclusion**:
   - _Previous Logic_: The workbench table and candidate detail editor remained active and mutable while background tasks were running, leading to race conditions where user edits and background writes collided.
   - _New Specification_: The entire workbench enters a modal/locked read-only state during processing. Candidate editing, additions, deletions, triage overrides, and commits are disabled until the session finishes or is cancelled.

---

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Canary-Gated Fail-Fast Bulk Enrichment Dispatch (Priority: P1)

As a premium traveler managing a large batch of imported points of interest in the Import Staging Workbench, I want to run bulk AI enrichment with automated canary validation and fail-fast circuit breaking, so that I do not waste time, API quotas, or billable credits when external LLM or scraping services are unavailable or exhausted.

**Why this priority**: Without canary gating and fail-fast stopping, exhausting LLM prepaid credits or hitting API rate limits causes dozens or hundreds of candidates to silently fail or produce degraded fallback records, wasting money and confusing the traveler.

**Independent Test**: Can be tested by initiating bulk enrichment on a staging job containing 10 candidates with mock Gemini credentials set to return 402 `RESOURCE_EXHAUSTED`. Verify that candidate #1 is dispatched as a solitary canary, triggers the blocking error detection, halts further queue processing, and leaves candidates #2–#10 intact without consuming downstream resources.

**Acceptance Scenarios**:

1. **Given** a premium traveler with 5 selected candidates in the staging workbench, **When** the traveler clicks "AI Enrich All", **Then** the system shall enqueue exactly those 5 selected candidates for processing.
2. **Given** a staging workbench where 0 candidates are selected, **When** the traveler clicks "AI Enrich All", **Then** the system shall display a confirmation prompt asking whether all eligible candidates should be processed.
3. **Given** the confirmation prompt for 0 selected candidates, **When** the traveler selects "No", **Then** the system shall abort processing without modifying any candidate states or dispatching worker tasks.
4. **Given** the confirmation prompt for 0 selected candidates, **When** the traveler selects "Yes", **Then** the system shall enqueue all eligible non-ignored candidates in the active job into the enrichment queue.
5. **Given** a populated enrichment queue of $N$ candidates ($N \ge 2$), **When** processing begins, **Then** the system shall dispatch candidate #1 as an isolated canary record with concurrency 1, holding candidates #2 through #N in the queue until the canary completes.
6. **Given** the canary record completes with `SUCCESS` or `TEMPORARY_EXTERNAL_ERROR`, **When** the canary finishes, **Then** the system shall scale worker dispatch up to the configured concurrency limit ($C$) to process remaining queued items in parallel.
7. **Given** any worker (canary or subsequent) returns a `BLOCKING_EXTERNAL_ERROR` (such as HTTP 402 credits depleted or HTTP 429 quota exhausted), **When** the producer receives the error, **Then** the system shall immediately stop submitting additional queued candidates, wait for all currently in-flight workers to complete, and terminate processing.

---

### User Story 2 - Real-Time Enrichment Progress & Interactive Graceful Cancellation (Priority: P1)

As a traveler running a bulk enrichment job, I want a live progress modal showing exact queue counts, current in-flight workers, elapsed time, and dynamic completion estimates, along with a "Cancel" button, so that I have complete visibility and control over long-running operations.

**Why this priority**: Travelers need real-time feedback to know the system is actively working, how long it will take, and the ability to gracefully stop processing at any time without corrupting partial progress.

**Independent Test**: Can be tested by starting bulk enrichment on 20 candidates, verifying that the progress dialog displays total, completed, failed, in-flight, and remaining counts with updated percentages and elapsed time, clicking "Cancel" halfway through, and verifying that in-flight workers finish cleanly while remaining queued items are marked cancelled.

**Acceptance Scenarios**:

1. **Given** bulk enrichment is actively running, **When** the progress modal renders, **Then** the system shall display the total queue count, completed count, issue count, remaining count, in-flight count, percentage complete, elapsed duration, and calculated average processing time per POI.
2. **Given** bulk enrichment is in progress, **When** the traveler clicks the "Cancel" button on the progress modal, **Then** the system shall immediately transition the session to a draining state, cease submitting new candidates from the queue, and display a "Cancelling... waiting for active workers" status.
3. **Given** active workers are draining following a cancellation request, **When** all in-flight workers finish, **Then** the system shall terminate the session and present the completion summary report.

---

### User Story 3 - Post-Processing Summary Window & Telemetry Audit (Priority: P2)

As a traveler or administrative user, I want a comprehensive summary report displayed immediately after bulk enrichment finishes, detailing success counts, failure reasons, durations, and resource usage, so that I understand exactly what was enriched and why processing ended.

**Why this priority**: Travelers need unambiguous closure after bulk runs, distinguishing between successfully enriched POIs, temporary item-specific failures, and system-level blocking stops.

**Independent Test**: Can be tested by completing a bulk run where 3 POIs succeed, 1 encounters a temporary error (e.g. website 404), and 6 are cancelled due to a user stop. Verify that the modal clearly enumerates counts by category, average duration, total resources used, and termination reason.

**Acceptance Scenarios**:

1. **Given** bulk enrichment completes (via normal completion, error circuit-break, or cancellation), **When** processing terminates, **Then** the system shall present an informational summary modal containing:
   - Total POIs in queue
   - Count of POIs successfully enriched
   - Count of POIs with issues, itemized by error category (`INTERNAL_ERROR`, `BLOCKING_EXTERNAL_ERROR`, `TEMPORARY_EXTERNAL_ERROR`)
   - Count of unprocessed/skipped POIs
   - Total elapsed execution time
   - Average processing time per POI
   - Total resources consumed across all workers (LLM tokens and web queries)
   - Specific termination reason (e.g., "All records processed", "Blocked by external quota limit", "Cancelled by user")
2. **Given** the summary modal is displayed, **When** the traveler closes the modal, **Then** the system shall refresh the workbench table, displaying updated candidate fields and badges for all enriched items.

---

### User Story 4 - Mutual Exclusion & Subscription Entitlement Gating (Priority: P2)

As the Vistarae platform, I want to lock the workbench during active bulk enrichment and enforce premium subscription levels, so that race conditions are prevented and premium computational resources are protected.

**Why this priority**: Allowing travelers to edit, delete, or commit candidate rows while worker processes are concurrently updating those exact rows causes database conflicts and data loss. Restricting bulk AI to premium tiers protects operational budgets.

**Independent Test**: Can be tested by verifying that free-tier users cannot trigger bulk enrichment, and that while bulk enrichment is active for a premium user, all table row actions, batch edit buttons, discard buttons, and detail editor form inputs are disabled.

**Acceptance Scenarios**:

1. **Given** a user with a non-premium subscription tier, **When** viewing the staging workbench, **Then** the "AI Enrich All" control shall be disabled with a visible badge or tooltip indicating premium entitlement is required.
2. **Given** a non-premium user submits a request to the bulk enrichment API endpoint, **When** the backend evaluates the request, **Then** the system shall reject the request with HTTP 403 Forbidden.
3. **Given** bulk enrichment is initiated, **When** the session starts, **Then** the system shall disable candidate editing, deletion, row selection modifications, and session discard in the workbench UI until processing ends.
4. **Given** bulk enrichment terminates (successfully or unsuccessfully), **When** the session concludes, **Then** the system shall restore full editing capabilities to the workbench UI.

---

## Edge Cases

- **What happens if the canary record encounters a `TEMPORARY_EXTERNAL_ERROR` (e.g., specific website 404 or missing coordinates)?**
  The canary check differentiates between service-level exhaustion and single-item data defects. If the canary fails due to an item-specific issue (e.g., website not found), the system shall record the issue for that candidate and proceed to process the remaining queue at the configured concurrency limit. It only halts if the canary returns a `BLOCKING_EXTERNAL_ERROR` (e.g., HTTP 402/429/auth failure).
- **What happens if a worker crashes or times out while processing a candidate?**
  The worker pool shall enforce a per-item timeout. If a worker fails to report back within the timeout window, the item is marked with `INTERNAL_ERROR` ("Worker execution timed out"), allowing in-flight tracking to decrement cleanly and prevent hanging sessions.
- **What happens if the traveler closes or refreshes the browser during bulk enrichment?**
  The backend enrichment session maintains its queue state and progress in the database/session cache. When the traveler reopens the workbench for that job, the system detects the active session, restores the locked state and progress modal, and continues tracking until completion.
- **What happens if a user clicks "AI Enrich All" when all candidates in the job are already fully enriched?**
  The system shall inspect candidate completeness. If all selected or available candidates already possess required AI fields, the system shall prompt the traveler asking if they wish to force-recalculate all records or cancel.
- **What happens if multiple browser tabs attempt to start bulk enrichment on the same job simultaneously?**
  The backend enforces an atomic session lock per `job_id`. If a second request arrives while a session is active, the system rejects the duplicate with HTTP 409 Conflict ("Enrichment already in progress for this job").

---

## Requirements _(mandatory)_

### Functional Requirements

#### Entitlement & Pre-Flight Gating
- **REQ-ENR-001**: _Ubiquitous_: The system shall restrict execution of bulk AI enrichment exclusively to users with an active `PREMIUM` subscription tier.
- **REQ-ENR-002**: _Event-Driven_: When a non-premium user attempts to trigger bulk enrichment via the API, the system shall reject the request with HTTP 403 Forbidden and Problem Details explaining the subscription requirement.
- **REQ-ENR-003**: _State-Driven_: While a non-premium user views the staging workbench, the user interface shall render the "AI Enrich All" action in a disabled state accompanied by an entitlement badge and upgrade prompt.

#### Queue Initialization & Scoping
- **REQ-ENR-004**: _Event-Driven_: When a traveler clicks "AI Enrich All" with one or more candidate rows selected in the workbench table, the system shall initialize the enrichment queue containing exclusively the selected candidate records.
- **REQ-ENR-005**: _Event-Driven_: When a traveler clicks "AI Enrich All" with zero candidate rows selected, the system shall display an interactive confirmation prompt asking: `"Enrich all eligible candidates in this batch?"`.
- **REQ-ENR-006**: _Event-Driven_: When the traveler responds "No" to the zero-selection prompt, the system shall abort initiation without mutating candidate data or contacting external services.
- **REQ-ENR-007**: _Event-Driven_: When the traveler responds "Yes" to the zero-selection prompt, the system shall populate the enrichment queue with all candidates in the job whose disposition is not `IGNORE`, `EXCLUDE`, or `EXISTING`.
- **REQ-ENR-008**: _Ubiquitous_: The system shall assign each queued candidate a unique, 1-based sequential position index from `1` to `N` (where $N$ is the total queue size) to establish a deterministic execution order.

#### Mutual Exclusion & Workbench Locking
- **REQ-ENR-009**: _State-Driven_: While bulk enrichment is active for a staging job, the system shall disable candidate editing, manual field saves, candidate deletion, row status toggling, batch updates, and session discarding across the staging workbench UI.
- **REQ-ENR-010**: _Event-Driven_: When bulk enrichment terminates (whether by successful completion, circuit-break, or user cancellation), the system shall immediately re-enable all workbench editing controls and reload candidate data.

#### Horizontal Worker Dispatch & Canary Validation
- **REQ-ENR-011**: _Ubiquitous_: The system shall read the maximum worker concurrency ceiling from the environment variable `BULK_ENRICHMENT_CONCURRENCY` (defaulting to `3` if unspecified).
- **REQ-ENR-012**: _State-Driven_: While initiating execution for queue position `1` (the canary item), the system shall dispatch exactly one solitary worker task and withhold all subsequent queue items until the canary worker returns.
- **REQ-ENR-013**: _Event-Driven_: When the canary worker completes with `SUCCESS` or `TEMPORARY_EXTERNAL_ERROR`, the system shall transition to parallel dispatch, maintaining up to the configured concurrency ceiling ($C$) of simultaneously active workers for remaining queued candidates.
- **REQ-ENR-014**: _Event-Driven_: When the canary worker completes with a `BLOCKING_EXTERNAL_ERROR`, the system shall abort all remaining queue items immediately without dispatching any further workers.

#### Worker Execution, Telemetry & Standardized Result Codes
- **REQ-ENR-015**: _Ubiquitous_: Every worker invocation shall execute as a decoupled, stateless processing unit that enriches a single candidate's web data, photos, duration estimates, and AI visit notes.
- **REQ-ENR-016**: _Ubiquitous_: The system shall require every worker to return a standardized result structure comprising:
  - `result_code`: One of `SUCCESS`, `INTERNAL_ERROR`, `BLOCKING_EXTERNAL_ERROR`, or `TEMPORARY_EXTERNAL_ERROR`.
  - `error_message`: Detailed descriptive explanation if any issue was encountered.
  - `duration_ms`: Total execution time in milliseconds.
  - `resources_used`: Quantitative count of external resources consumed (including LLM token counts and external web requests).
  - `enriched_candidate`: The updated candidate payload if enrichment succeeded.
- **REQ-ENR-017**: _Ubiquitous_: The system shall classify external HTTP 402 (payment required/credits depleted), HTTP 429 (rate/quota limit exhausted), and service authentication failures as `BLOCKING_EXTERNAL_ERROR`.
- **REQ-ENR-018**: _Ubiquitous_: The system shall classify missing target websites, unresolvable domain queries, and empty scrape results as `TEMPORARY_EXTERNAL_ERROR`.
- **REQ-ENR-019**: _Ubiquitous_: The system shall classify unhandled exceptions, serialization failures, and worker timeouts as `INTERNAL_ERROR`.

#### Fail-Fast Circuit Breaking & Cancellation
- **REQ-ENR-020**: _Event-Driven_: When the producer receives a `BLOCKING_EXTERNAL_ERROR` from any active worker, the system shall trigger fail-fast circuit breaking:
  1. Immediately mark the remaining unprocessed queue as halted.
  2. Prevent any new candidate dispatches to workers.
  3. Await completion of all currently in-flight worker tasks.
  4. Terminate the enrichment session.
- **REQ-ENR-021**: _Event-Driven_: When the traveler clicks the "Cancel" button on the progress modal, the system shall:
  1. Transition session state to `CANCELLING`.
  2. Cease dispatching any new items from the queue.
  3. Allow all in-flight workers to complete processing.
  4. Mark all un-dispatched items as `CANCELLED`.
  5. Terminate the enrichment session.

#### User Visibility & Real-Time Progress Modal
- **REQ-ENR-022**: _State-Driven_: While bulk enrichment is active, the system shall render a modal dialog displaying:
  - Total candidates in queue ($N$).
  - Number of successfully processed candidates.
  - Number of candidates with issues (itemized by failure type).
  - Number of candidates remaining in queue.
  - Number of candidates currently in-flight.
  - Percentage of completion ($0\%$ to $100\%$).
  - Elapsed wall-clock time formatted as `MM:SS`.
  - Dynamically calculated average processing time per POI.
  - A prominent "Cancel" button.
- **REQ-ENR-023**: _Ubiquitous_: The progress calculation shall update in real-time as each worker completes.

#### Post-Processing Summary Window
- **REQ-ENR-024**: _Event-Driven_: When bulk enrichment terminates, the system shall replace the active progress view with a completion summary report detailing:
  - Termination status (`COMPLETED`, `BLOCKED`, `CANCELLED`, or `FAILED`).
  - Specific reason for termination (e.g., `"All candidates successfully processed"`, `"Halted: Gemini prepaid credits depleted (HTTP 402)"`, `"Cancelled by traveler"`).
  - Count of successfully enriched POIs.
  - Count of POIs that encountered issues, grouped by result code.
  - Count of unprocessed POIs.
  - Total elapsed session duration.
  - Average processing duration per candidate.
  - Aggregate count of external resources used across all processed POIs.
- **REQ-ENR-025**: _Event-Driven_: When the traveler dismisses the completion summary report, the system shall close the modal and refresh the staging workbench table to reflect all enriched candidate records.

#### Distributed Tracing & Correlated Logging Protocol
- **REQ-ENR-026**: _Ubiquitous_: The system shall generate a unique `EnrichmentSessionId` (UUIDv4) upon session creation and attach it to all producer requests, queue messages, worker execution contexts, and backend responses.
- **REQ-ENR-027**: _Ubiquitous_: Producer and worker logs shall adhere to the Vistarae Messaging Protocol tags:
  - Inbound message received: `MSG ->|  `
  - Response to outbound message received: `MSG <-|  `
  - Outbound message sent: `MSG   |->`
  - Response to outbound message sent: `MSG   |<-`
- **REQ-ENR-028**: _Ubiquitous_: Every worker log entry shall record the candidate POI name, queue position index, total queue size in the format `[X of Y]`, and the `EnrichmentSessionId`. Example:
  `MSG ->| [EnrichWorker] Processing POI 'Mount Fuji' [1 of 15] | SessionID={uuid}`.

---

### Key Entities

- **EnrichmentSession**: Represents the lifecycle of a bulk enrichment operation.
  - `session_id`: Unique UUIDv4 identifier.
  - `job_id`: Associated staging import job UUID.
  - `user_id`: Owning traveler UUID.
  - `status`: Current state (`INITIALIZING`, `CANARY_DISPATCH`, `ACTIVE`, `DRAINING`, `COMPLETED`, `BLOCKED`, `CANCELLED`, `FAILED`).
  - `total_count`: Total number of candidates in the queue ($N$).
  - `concurrency_limit`: Maximum parallel workers ($C$).
  - `canary_candidate_id`: ID of the candidate designated as canary.
  - `started_at`: Timestamp when canary dispatched.
  - `ended_at`: Timestamp when last worker drained.
  - `termination_reason`: Plain-text explanation of how/why the session concluded.

- **EnrichmentQueueItem**: Represents an individual candidate's place in the enrichment workflow.
  - `queue_item_id`: Unique UUIDv4 identifier.
  - `session_id`: Parent `EnrichmentSession` foreign key.
  - `candidate_id`: Target candidate UUID.
  - `queue_position`: 1-based sequential integer ($1 \le X \le N$).
  - `status`: State (`QUEUED`, `IN_FLIGHT`, `SUCCEEDED`, `FAILED`, `CANCELLED`).
  - `is_canary`: Boolean flag indicating if item is position 1.
  - `worker_id`: Identifier of the worker instance that processed the item.
  - `result_code`: `SUCCESS`, `INTERNAL_ERROR`, `BLOCKING_EXTERNAL_ERROR`, `TEMPORARY_EXTERNAL_ERROR`, or `null`.
  - `error_message`: Text of error if result is not `SUCCESS`.
  - `duration_ms`: Duration of worker execution.
  - `resources_used`: Integer count of external units (tokens/requests) consumed.

- **EnrichmentSummaryReport**: The immutable audit report generated upon session completion.
  - `session_id`: Associated session UUID.
  - `total_candidates`: Total items queued.
  - `succeeded_count`: Number of successfully enriched candidates.
  - `temporary_error_count`: Number of candidates with non-fatal external issues.
  - `blocking_error_count`: Number of blocking errors encountered.
  - `internal_error_count`: Number of unexpected system errors.
  - `unprocessed_count`: Number of items that remained in queue upon halt/cancel.
  - `total_duration_ms`: Total wall-clock time from start to drain.
  - `average_duration_ms`: Mean processing time across completed candidates.
  - `total_resources_used`: Sum of all external units consumed.
  - `termination_reason`: Human-readable summary description.

---

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: _Zero Downstream Resource Waste on External Failure_: When a worker encounters a blocking external failure (such as quota depletion or HTTP 402/429), $0$ additional candidates from the queue shall be dispatched to external APIs.
- **SC-002**: _Sub-Second Fail-Fast Triggering_: Upon receipt of a `BLOCKING_EXTERNAL_ERROR`, the producer shall transition the queue to halted and cease dispatch within $500\text{ ms}$.
- **SC-003**: _Real-Time Progress Responsiveness_: The progress bar, percentage, and candidate counts displayed to the traveler shall update within $1\text{ second}$ of any worker task completing.
- **SC-004**: _Zero Concurrent Mutation Race Conditions_: $100\%$ of candidate edits, deletions, and commits shall be blocked while bulk enrichment is active, resulting in $0$ race condition write conflicts.
- **SC-005**: _Complete Operational Accounting_: The post-processing summary window shall account for $100\%$ of queued candidates across succeeded, failed, and unprocessed categories without omission.
- **SC-006**: _Immediate Graceful Cancellation_: When the traveler clicks "Cancel", active dispatches shall stop within $500\text{ ms}$, and in-flight workers shall be drained cleanly without data corruption.

---

## Assumptions

- **Configurable Concurrency**: The default concurrency limit of `3` is optimal for typical API rate limits (e.g., Nominatim 1 req/sec policy and LLM quota tiers), but operators can configure higher concurrency via `BULK_ENRICHMENT_CONCURRENCY` when running dedicated infrastructure or higher quota tiers.
- **Worker Scalability**: The worker logic can execute as an asynchronous worker pool within FastAPI, an external Celery/Arq background worker, or serverless AWS Lambda functions invoked via event payload.
- **Resource Metric Granularity**: "Resources used" tracks the sum of external calls (LLM generation requests and Nominatim/web scraping requests) and estimated token counts where provided by the provider SDK.
- **Target Fields**: Bulk enrichment populates existing targeted candidate fields (`description`, `reason_to_visit`, `recommended_duration_hours`, `recommended_visit_days`, `estimated_visit_time_notes`, `hero_image_url`, `related_websites`, `tags`) preserving manual user overrides marked `is_user_overridden`.

