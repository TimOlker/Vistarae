# Data Model: AI Bulk Enrichment (018-bulk-ai-enrich)

**Date**: 2026-11-13  
**Status**: Completed  
**Feature Spec**: [spec.md](./spec.md)

---

## 1. Domain Entities & Value Objects

### 1.1 Enumerations

All enumerations are implemented as Python `StrEnum` backed by PostgreSQL `VARCHAR(n)` columns in compliance with Constitution Principle 4 (no native DB enum types).

```python
from enum import StrEnum

class BulkEnrichmentStatus(StrEnum):
    """Lifecycle states of a bulk enrichment session and audit record."""
    INITIALIZING = "INITIALIZING"
    CANARY_DISPATCH = "CANARY_DISPATCH"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class EnrichmentResultCode(StrEnum):
    """Execution outcome classified by candidate worker."""
    SUCCESS = "SUCCESS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BLOCKING_EXTERNAL_ERROR = "BLOCKING_EXTERNAL_ERROR"
    TEMPORARY_EXTERNAL_ERROR = "TEMPORARY_EXTERNAL_ERROR"

class RecoveryPromptAction(StrEnum):
    """Traveler choices in response to the login unacknowledged failure prompt."""
    RESUME = "resume"
    DISMISS = "dismiss"
    CANCEL = "cancel"
```

---

### 1.2 Persistent Entity: `BulkEnrichmentResult`

Represents an immutable historical audit record of each bulk enrichment operation run by a traveler.

- **Table**: `bulk_enrichment_results`
- **Ownership**: Strict tenant isolation via `user_id`.

| Field Name | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `user_id` | `UUID` | No | - | Foreign key to `users.id` with `ON DELETE CASCADE`. |
| `job_id` | `UUID` | No | - | Foreign key to `ingest_jobs.id` with `ON DELETE CASCADE`. |
| `session_id` | `UUID` | No | - | Unique UUID of the in-memory or orchestrated enrichment session. |
| `status` | `VARCHAR(32)` | No | - | Final terminal status (`COMPLETED`, `BLOCKED`, `CANCELLED`, `FAILED`). |
| `processed_count` | `INTEGER` | No | `0` | Number of candidates that completed worker execution. |
| `unprocessed_count` | `INTEGER` | No | `0` | Number of queued candidates not dispatched before termination. |
| `failure_count` | `INTEGER` | No | `0` | Sum of internal, blocking, and temporary worker failures. |
| `success_count` | `INTEGER` | No | `0` | Number of candidates successfully enriched. |
| `total_resources_used` | `INTEGER` | No | `0` | Total external calls and token units consumed across all workers. |
| `total_duration_ms` | `INTEGER` | No | `0` | Total wall-clock time from canary dispatch to session termination. |
| `average_duration_ms` | `INTEGER` | No | `0` | Mean runtime per candidate in milliseconds. |
| `termination_reason` | `TEXT` | No | - | Descriptive explanation of session termination. |
| `acknowledged_at` | `TIMESTAMP WITH TIME ZONE` | Yes | `NULL` | When the user responded to the recovery dialog; `NULL` while unacknowledged. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | No | `NOW()` | Timestamp when the audit record was persisted. |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | No | `NOW()` | Timestamp when the audit record was last updated. |

#### Database Indexes:
1. `idx_bulk_enrichment_user_recovery`:
   - Composite B-Tree index on `(user_id, acknowledged_at, created_at DESC)`
   - Accelerates the login recovery query (`REQ-ENR-034`) to `< 5ms`.
2. `idx_bulk_enrichment_job_id`:
   - Index on `(job_id)` for quick lookup by active workbench session.
3. `idx_bulk_enrichment_session_id`:
   - Unique index on `(session_id)` ensuring exactly one audit record per session.

---

### 1.3 In-Memory Session Entities

Used by `BulkEnrichmentSessionManager` during runtime execution.

#### `EnrichmentSession`
```python
@dataclass
class EnrichmentSession:
    session_id: UUID
    job_id: UUID
    user_id: UUID
    status: BulkEnrichmentStatus
    total_count: int
    concurrency_limit: int
    canary_candidate_id: UUID
    started_at: datetime
    ended_at: datetime | None = None
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stop_requested: bool = False
    termination_reason: str = ""
    processed_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    unprocessed_count: int = 0
    total_resources_used: int = 0
    total_duration_ms: int = 0
```

#### `EnrichmentQueueItem`
```python
@dataclass
class EnrichmentQueueItem:
    queue_item_id: UUID
    session_id: UUID
    candidate_id: UUID
    candidate_name: str
    queue_position: int  # 1-based index (1 <= X <= N)
    is_canary: bool
    status: str  # QUEUED, IN_FLIGHT, SUCCEEDED, FAILED, CANCELLED
    worker_id: str | None = None
    result_code: EnrichmentResultCode | None = None
    error_message: str | None = None
    duration_ms: int = 0
    resources_used: int = 0
```

---

## 2. Pydantic Boundary Schemas

All request/response schemas inherit from `StrictBaseModel` with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True` (Constitution Principle 5).

### 2.1 Enqueue & Lifecycle

```python
from pydantic import Field
from uuid import UUID
from vistarae_core.schemas.base import StrictBaseModel

class BulkEnrichmentInitiateRequest(StrictBaseModel):
    candidate_ids: list[UUID] | None = Field(
        default=None,
        description="Explicit candidate IDs to enrich. If empty or None, all eligible candidates are targeted.",
    )
    force_refresh: bool = Field(
        default=False,
        description="If True, recomputes all target fields regardless of pre-existing data, preserving user overrides.",
    )
    all_eligible: bool = Field(
        default=False,
        description="Explicit confirmation flag when candidate_ids is empty, confirming all eligible POIs should be enqueued.",
    )

class BulkEnrichmentInitiateResponse(StrictBaseModel):
    session_id: UUID
    job_id: UUID
    total_enqueued: int
    status: BulkEnrichmentStatus
    message: str

class BulkEnrichmentProgressResponse(StrictBaseModel):
    session_id: UUID
    job_id: UUID
    status: BulkEnrichmentStatus
    total_count: int
    completed_count: int
    success_count: int
    issue_count: int
    remaining_count: int
    in_flight_count: int
    percent_complete: int
    elapsed_seconds: int
    average_duration_ms: int | None
    can_cancel: bool
    status_message: str

class BulkEnrichmentCancelResponse(StrictBaseModel):
    session_id: UUID
    status: BulkEnrichmentStatus
    message: str

class BulkEnrichmentHeartbeatResponse(StrictBaseModel):
    session_id: UUID
    acknowledged: bool
    is_active: bool
```

### 2.2 Summary & Audit

```python
class BulkEnrichmentSummaryResponse(StrictBaseModel):
    session_id: UUID
    job_id: UUID
    status: BulkEnrichmentStatus
    total_candidates: int
    succeeded_count: int
    temporary_error_count: int
    blocking_error_count: int
    internal_error_count: int
    unprocessed_count: int
    total_duration_ms: int
    average_duration_ms: int
    total_resources_used: int
    termination_reason: str
    created_at: datetime

class BulkEnrichmentRecoveryResponse(StrictBaseModel):
    result_id: UUID
    job_id: UUID
    session_id: UUID
    status: BulkEnrichmentStatus
    failed_at: datetime
    unprocessed_count: int
    failure_count: int
    total_candidates: int
    termination_reason: str

class BulkEnrichmentRecoveryActionRequest(StrictBaseModel):
    result_id: UUID
    action: RecoveryPromptAction
```

---

## 3. State Transitions

```
[IDLE / READY]
       │
       ▼ (Traveler clicks "AI Enrich All" + selection validated)
[INITIALIZING]
       │
       ▼ (Canary record #1 dispatched alone)
[CANARY_DISPATCH] ────(Blocking external error: 402/429)────► [BLOCKED]
       │                                                         │
       ▼ (Canary SUCCESS or TEMPORARY_ERROR)                     │
[ACTIVE] ◄─── Concurrency scales to BULK_ENRICHMENT_CONCURRENCY  │
  │   │                                                          │
  │   ├───(Blocking external error detected on any worker)───────┤
  │   │                                                          │
  │   ├───(User clicks "Cancel" OR heartbeat lost >15s)──────────┤
  │   │                                                          │
  │   ▼                                                          │
  └───► [DRAINING] (Wait up to 30s grace period for in-flight)───┘
               │
               ├──► [COMPLETED] (All queued candidates succeeded or handled)
               ├──► [BLOCKED]   (Halted due to quota/resource exhaustion)
               ├──► [CANCELLED] (Halted due to traveler request or disconnect)
               └──► [FAILED]    (Halted due to critical unhandled system errors)
```

