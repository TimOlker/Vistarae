# Quickstart & Validation Guide: Asynchronous Ingestion & Batch Processing

**Feature Identifier**: `003-async-ingestion-cli`  
**Date**: 2026-10-19  
**Status**: Completed  
**Spec**: [spec.md](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/spec.md) | **Contracts**: [ingest-api.yaml](file:///d:/Coding/Vistarae/specs/003-async-ingestion-cli/contracts/ingest-api.yaml)  

---

## 1. Prerequisites & Environment Setup

Ensure local Docker Compose infrastructure is active:

```bash
# 1. Start local PostGIS, ElasticMQ (SQS), and Jaeger
docker compose up -d db elasticmq jaeger

# 2. Verify ElasticMQ SQS queues are healthy
curl http://localhost:9324

# 3. Apply Alembic migrations to create ingest_jobs table
alembic upgrade head
```

---

## 2. Validation Scenario 1: Upload Guardrails & Enqueuing

### 2.1 Valid Upload (HTTP 202 Accepted)

Create a sample valid CSV (`sample_valid.csv`):
```csv
name,description,address,city,state,country,latitude,longitude,visited_date,tags
"Multnomah Falls","Iconic 620-foot cascade in the Columbia River Gorge.","50000 E Historic Columbia River Hwy","Bridal Veil","Oregon","United States",45.5762,-122.1158,2024-06-20,"waterfall,hiking"
"Cannon Beach","Scenic coastal beach featuring Haystack Rock.","Hemlock St","Cannon Beach","Oregon","United States",45.8918,-123.9615,2024-06-21,"beach,coast"
```

Submit via `curl` with a mock auth header:

```bash
curl -i -X POST http://localhost:8030/api/ingest/csv \
  -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
  -F "file=@sample_valid.csv;type=text/csv"
```

**Expected Response**:
- HTTP Status: `202 Accepted`
- Body:
  ```json
  {
    "job_id": "<UUID>",
    "job_status": "PENDING",
    "total_rows": 2,
    "message": "CSV upload accepted for asynchronous batch processing."
  }
  ```

### 2.2 Guardrail Verifications

1. **Size Exceeded (>2MB)**:
   ```bash
   # Generate a 2.5MB dummy CSV and submit
   # Expected: HTTP 413 Payload Too Large (RFC 7807)
   ```
2. **Row Limit Exceeded (>2,000 rows)**:
   ```bash
   # Submit a CSV containing 2,050 rows
   # Expected: HTTP 422 Unprocessable Content (RFC 7807)
   ```
3. **Formula Injection Neutralization**:
   ```csv
   name,address
   "=SUM(A1:A10)", "123 Main St"
   ```
   Verify that after parsing, the name cell starts with `'=SUM(A1:A10)`.

---

## 3. Validation Scenario 2: Batch Worker Processing & Idempotency

### 3.1 Run Local Worker

Execute the worker consumer locally:

```bash
python -m services.worker.main --env local
```

**Expected Worker Log Flow**:
1. Ingests SQS message from `vistarae-ingest-local`.
2. Extracts W3C `traceparent` and opens OpenTelemetry span.
3. Computes `sha256(f"{user_id}:{job_id}:{absolute_row_number}")` and inserts into `idempotency_keys`.
4. Checks `geocoding_cache`:
   - If hit: returns coordinates with zero delay.
   - If miss: enforces in-memory 1 req/sec interval, queries Nominatim, and caches response with 90-day TTL.
5. Performs spatial dedup check:
   - If unique: persists to `pois` table, generates 768-dim vector embedding via Gemini (`thinking_budget=0`).
   - If candidate duplicate: stages to `duplicate_payloads` in `ingest_jobs`.
6. Increments `processed_rows` in `ingest_jobs`.

### 3.2 Verify Idempotency

Re-send the same SQS message with the same `(user_id, job_id, absolute_row_number)`.
- Worker detects conflict on `idempotency_keys` (`ON CONFLICT DO NOTHING`).
- Worker logs `Idempotency hit, skipping duplicate processing` and deletes message.
- Zero duplicate rows are inserted into `pois`.

---

## 4. Validation Scenario 3: Polling Progress & Duplicate Triage

### 4.1 Poll Progress

```bash
curl -X GET http://localhost:8030/api/ingest/jobs/<job_id> \
  -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001"
```

**Expected Response**:
```json
{
  "id": "<job_id>",
  "job_status": "PARTIAL_SUCCESS",
  "total_rows": 2,
  "processed_rows": 2,
  "percent_complete": 100.0,
  "duplicates_pending_count": 1,
  "duplicate_items": [
    {
      "row_number": 2,
      "raw_name": "Cannon Beach",
      "candidate_poi_id": "<existing_poi_uuid>",
      "match_type": "POTENTIAL_DUPLICATE",
      "similarity_score": 0.95,
      "distance_meters": 50.0,
      "triage_status": "PENDING_REVIEW",
      "staged_poi_data": { ... }
    }
  ]
}
```

### 4.2 Submit Triage Decision

```bash
curl -X POST http://localhost:8030/api/ingest/jobs/<job_id>/triage \
  -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
  -H "Content-Type: application/json" \
  -d '{
    "decisions": [
      {
        "row_number": 2,
        "decision": "COMMITTED"
      }
    ]
  }'
```

**Expected Result**:
- POI is inserted into `pois` table.
- Item status updates to `COMMITTED`.
- Job status updates to `COMPLETED`.

---

## 5. Validation Scenario 4: Operational DLQ Redrive

```bash
# 1. Inspect visible messages in local DLQ
python scripts/redrive_dlq.py --env local --dry-run

# 2. Redrive messages back to main queue
python scripts/redrive_dlq.py --env local --max-messages 10

# 3. Test safety gate on production simulation
python scripts/redrive_dlq.py --env prod
# Expected: Prompt: "WARNING: You are about to redrive DLQ messages in 'prod'. Type 'yes' to confirm: "
```

---

## 6. Validation Scenario 5: AI Photo Scanner CLI

```bash
# Run unattended scan on photo directory
python -m photo_scraper.main --dir ./tests/fixtures/sample_photos --out ./output/vacation_ingest.csv --non-interactive

# Verify output CSV format
head -n 5 ./output/vacation_ingest.csv
```

**Expected CSV Output**:
- Valid CSV header: `name,description,address,city,state,country,latitude,longitude,visited_date,tags,triage_status`
- Ambiguous photos flagged with `triage_status: NEEDS_REVIEW`
- High-confidence photos marked `triage_status: APPROVED`
- All formula prefixes neutralized
