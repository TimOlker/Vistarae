# API Contract: Full-Fidelity Candidate Export (017-export)

**Feature**: `017-export` | **Date**: 2026-11-11

---

## 1. Streaming Candidate Export Endpoint

### `GET /api/ingest/jobs/{job_id}/candidates/export`

Streams an RFC 4180 compliant CSV file representing all candidates staged in the specified job.

#### Path Parameters
- `job_id` (`UUID`, required): Unique identifier of the active ingestion job.

#### Query Parameters
- `candidate_ids` (`list[UUID]`, optional): Optional subset of candidate UUIDs to export. If omitted or empty, all candidates in the job are exported.
- `scope` (`string`, optional, default: `"all"`): Scope selector (`"all"`, `"selected"`, `"filtered"`).

#### Headers
- `Authorization: Bearer <token>` (required): Tenant authentication.
- Standard W3C Tracing Headers:
  - `traceparent: 00-{trace_id}-{client_span_id}-01`
  - `X-Source: webapp`
  - `X-Destination: ingest_service`

#### Response
- **Status**: `200 OK`
- **Headers**:
  - `Content-Type: text/csv; charset=utf-8`
  - `Content-Disposition: attachment; filename="vistarae_staging_{job_id}_{YYYY-MM-DD}.csv"`
  - `X-Transaction-ID: {trace_id}`
- **Body**: Chunked UTF-8 CSV stream starting with UTF-8 BOM (`\ufeff`) followed by the canonical header row and data rows.

#### Error Responses
- `400 Bad Request`: `{"detail": "No candidate records found for the requested job."}`
- `401 Unauthorized`: Tenant unauthenticated.
- `404 Not Found`: Ingestion job does not exist or does not belong to the tenant.

---

## 2. Client-Side Export Contract

### `exportWorkbenchCandidatesToCsv(candidates, selectedIds, options)`

Generates and initiates a direct browser download of the full-fidelity staging CSV.

#### Signature (TypeScript)
```typescript
export interface ExportWorkbenchOptions {
  jobId?: string;
  selectedCandidateIds?: Set<string>;
  activeEditorCandidate?: CandidateItem | null;
}

export function exportWorkbenchCandidatesToCsv(
  candidates: CandidateItem[],
  options?: ExportWorkbenchOptions
): { exportedCount: number; filename: string };
```

#### Behavior
1. If `options.activeEditorCandidate` is provided, merges uncommitted form changes into the corresponding item in `candidates`.
2. Evaluates export scope:
   - If `options.selectedCandidateIds` has size $> 0$, filters `candidates` to include only those whose `candidate_id` is in the set.
   - Otherwise, exports all items in `candidates`.
3. Serializes each candidate through `CANONICAL_EXPORT_FIELDS`, applying RFC 4180 escaping, UTF-8 BOM, and formula prefix neutralization.
4. Generates an in-memory `Blob` of type `text/csv;charset=utf-8;` and triggers browser file download.

