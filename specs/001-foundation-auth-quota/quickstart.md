# Quickstart & Verification Guide: 001-foundation-auth-quota

**Feature**: Foundation, Authentication, Quotas & Administration  
**Date**: 2026-10-18  
**Status**: APPROVED

This document describes the step-by-step verification workflow for validating Phase 1 locally.

---

## 1. Prerequisites & Environment Setup

### 1.1 Dependencies

- Docker & Docker Compose v2+
- Python 3.12+
- `curl` or `httpie` for API queries

### 1.2 Environment File (`.env.local`)

Create or verify `.env.local`:

```bash
STAGE=local
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/vistarae
AWS_DEFAULT_REGION=us-east-1
AWS_COGNITO_USER_POOL_ID=us-east-1_mockpool
AWS_COGNITO_APP_CLIENT_ID=mockclientid
ELASTICMQ_ENDPOINT=http://localhost:9324
```

### 1.3 Install & Sync Workspace Packages

Sync all dependencies and editable workspace packages (`vistarae-core`) in seconds using `uv`:

```bash
uv sync
```

_(Alternative without uv: `pip install -e . -e ./packages/core`)_

---

## 2. Infrastructure Provisioning

Start the local PostGIS and ElasticMQ SQS emulation containers:

```bash
docker compose up -d
```

Verify containers are running:

```bash
docker compose ps
```

- `vistarae-db` (Port 5432)
- `vistarae-elasticmq` (Ports 9324, 9325)

Verify ElasticMQ queues:

```bash
curl -s http://localhost:9325/
```

---

## 3. Database Schema Migrations

Run Alembic migrations to activate extensions and build relational tables:

```bash
uv run alembic upgrade head
```

_(Or if .venv is activated: `alembic upgrade head`)_

Verify migration reversibility:

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Verify schema consistency with models:

```bash
uv run alembic check
```

---

## 4. Run Local Development Gateway

Start the unified local development gateway:

```bash
uv run uvicorn services.local_gateway:app --host 0.0.0.0 --port 8030 --reload
```

---

## 5. End-to-End Validation Scenarios

### Scenario 1: Dual-Probe Health Checks

Test ASGI liveness (Zero DB I/O):

```bash
curl -i http://localhost:8000/health/live
```

**Expected Outcome**: `HTTP/1.1 200 OK` with body `{"status": "alive"}`.

Test Database readiness (`SELECT 1`):

```bash
curl -i http://localhost:8000/health/ready
```

**Expected Outcome**: `HTTP/1.1 200 OK` with body `{"status": "ready"}`.

---

### Scenario 2: Local Auth Bypass & User Profile

Query current user with mock tenant header:

```bash
curl -i -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     http://localhost:8000/api/users/me
```

**Expected Outcome**: `HTTP/1.1 200 OK` returning `UserProfileResponse` with initialized default preferences, metrics, and quotas.

---

### Scenario 3: Sub-Domain Preferences Mutation

Update POI Mode preferences:

```bash
curl -i -X PATCH \
     -H "Content-Type: application/json" \
     -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     -d '{"clustering_radius_meters": 75, "geoproximity_scope_km": 50.0}' \
     http://localhost:8000/api/users/me/preferences/poi
```

**Expected Outcome**: `HTTP/1.1 200 OK` with updated clustering radius and geoproximity scope.

---

### Scenario 4: Rate-Limiting Rolling Window & Tier Caching

Execute 61 rapid requests under tier `'low'`:

```bash
for i in {1..62}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
       -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
       http://localhost:8000/api/users/me
done
```

**Expected Outcome**:

- First 60 requests return `200`.
- Request 61+ returns `429 Too Many Requests` with:
  - Header: `Retry-After: <seconds>`
  - RFC 7807 problem details JSON:
    ```json
    {
      "type": "https://errors.vistarae.com/rate-limit-exceeded",
      "title": "Too Many Requests",
      "status": 429,
      "detail": "Rate limit of 60 requests per minute exceeded.",
      "instance": "/api/users/me"
    }
    ```

---

### Scenario 5: Idempotency Key Lock & Response Replay

Send mutating request with `Idempotency-Key`:

```bash
curl -i -X PATCH \
     -H "Content-Type: application/json" \
     -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     -H "Idempotency-Key: test-mutation-key-001" \
     -d '{"full_name": "Antigravity Voyager"}' \
     http://localhost:8000/api/users/me
```

**Expected Outcome**: `HTTP/1.1 200 OK`.

Repeat the exact same request with the same `Idempotency-Key`:

```bash
curl -i -X PATCH \
     -H "Content-Type: application/json" \
     -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     -H "Idempotency-Key: test-mutation-key-001" \
     -d '{"full_name": "Antigravity Voyager"}' \
     http://localhost:8000/api/users/me
```

**Expected Outcome**: `HTTP/1.1 200 OK` with header `X-Cache-Lookup: HIT` returning cached JSON response without executing downstream database writes.

---

### Scenario 6: Admin Governance & Disablement

Fetch system telemetry metrics:

```bash
curl -i -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000000" \
     -H "X-Mock-User-Tier: admin" \
     http://localhost:8000/api/admin/metrics
```

**Expected Outcome**: `HTTP/1.1 200 OK` with total users, active count, tokens consumed, and tier distribution.

Disable target user:

```bash
curl -i -X POST \
     -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000000" \
     -H "X-Mock-User-Tier: admin" \
     http://localhost:8000/api/admin/users/00000000-0000-0000-0000-000000000001/disable
```

**Expected Outcome**: `HTTP/1.1 200 OK` (`{"status": "disabled"}`).

Verify disabled user is immediately rejected:

```bash
curl -i -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     http://localhost:8000/api/users/me
```

**Expected Outcome**: `HTTP/1.1 403 Forbidden` (`https://errors.vistarae.com/account-disabled`).

---

### Scenario 7: GDPR Cascade Deletion

Delete tenant account:

```bash
curl -i -X DELETE \
     -H "X-Mock-User-Id: 00000000-0000-0000-0000-000000000001" \
     http://localhost:8000/api/users/me
```

**Expected Outcome**: `HTTP/1.1 204 No Content`.

Verify user and all child table rows (`user_preferences`, `user_metrics`, `user_quotas`, `idempotency_keys`) have been deleted via database cascade.

---

## 6. Automated PyTest Suite & Coverage Check

Execute complete unit and integration test suite with coverage enforcement:

```bash
uv run pytest --cov=packages/core --cov=services --cov-fail-under=90 --cov-report=term-missing
```

**Expected Outcome**: 100% passing tests and $\ge 90\%$ code coverage.
