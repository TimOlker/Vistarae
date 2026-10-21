# Quickstart & Validation Guide: Phase 6 — AI Trip Planner, AWS SAM Serverless Infrastructure & GitHub Actions OIDC CI/CD

**Feature Identifier**: `006-trip-planner-aws-cicd`  
**Date**: 2026-10-20  
**Target Environments**: Local Development (`STAGE=local`), AWS Production (`STAGE=prod` in `us-east-2`)

---

## 1. Prerequisites

- Python 3.12+ with `uv` or `pip`
- Node.js 20+ with `npm`
- Docker & Docker Compose (for local PostGIS `16-3.4` and ElasticMQ)
- AWS CLI v2 and AWS SAM CLI (`sam --version >= 1.100.0`)

---

## 2. Local Development Setup

### 2.1 Start Local Infrastructure

```bash
# Start Docker PostGIS and ElasticMQ
docker compose up -d

# Verify PostGIS is ready
docker compose exec db pg_isready -U postgres
```

### 2.2 Run Database Migrations

```bash
# Apply revision 0004 (itineraries, days, items, system_settings)
alembic upgrade head

# Verify migration parity
alembic check
```

### 2.3 Start Backend Gateway & Frontend Dev Server

```bash
# Terminal 1: Backend Gateway
python -m uvicorn services.local_gateway:app --reload --port 8000

# Terminal 2: Frontend Vite
cd frontend
npm run dev
```

---

## 3. Automated Test Suite & Coverage Verification

### 3.1 Run Backend Unit & Integration Tests (90% Coverage Gate)

```bash
# Enforce minimum 90% branch and line coverage
pytest --cov=src --cov=services --cov=packages/core --cov-fail-under=90 -v
```

### 3.2 Run Frontend Unit & Component Tests

```bash
cd frontend
npm test -- --run
```

### 3.3 Validate OpenAPI TypeScript Contract Parity

```bash
# Export schema and regenerate TypeScript bindings
python -m scripts.export_openapi
npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts

# Assert zero drift
git diff --exit-code ./frontend/src/types/api.ts
```

---

## 4. End-to-End Validation Scenarios

### Scenario 1: Natural Language Trip Generation (Hybrid PostGIS + pgvector RAG)

1. Navigate to `http://localhost:5173/planner`.
2. Enter destination "Olympic National Park & Seattle", dates: 4 days, prompt: "Coastal hikes and fresh local seafood".
3. Click "Generate Itinerary".
4. **Expected Outcome**:
   - Backend queries `WHERE user_id = :user_id AND ST_DWithin(...)` ordered by `embedding <=> :query_vec`.
   - UI populates 4-day columns with time-slotted POIs, transit times, and estimated costs.
   - Any missing meal periods flag an advisory card with nearby restaurant suggestions.

### Scenario 2: Multi-Day Attraction Day Shortage Circuit Breaker

1. In the itinerary board, select an attraction with `recommended_visit_days: 3` (e.g. Yellowstone or Multi-Day Park).
2. Attempt to add it to a 2-day trip.
3. **Expected Outcome**:
   - Scheduler blocks placement and displays modal prompt: _"Not enough days available for full visit (requires 3 days). Please extend the trip duration or remove scheduled events to make room."_

### Scenario 3: SAM Template Validation & Local API Simulation

```bash
# Validate SAM template syntax and least-privilege policies
sam validate --lint

# Run local API gateway emulator
sam local start-api --port 3001
```

### Scenario 4: SpendKillSwitch Fallback Verification

```bash
# Test SpendKillSwitch handler locally with mock SNS payload
python -m pytest tests/unit/services/admin/test_spend_killswitch.py -v
```

**Expected Outcome**:

- API Gateway stage throttle set to 0 rate/burst.
- SQS EventSourceMapping disabled.
- Neon DB `system_settings.killswitch_active` set to `true`.
- Any `ValidationException` during `PutFunctionConcurrency(0)` is caught and handled safely.

### Scenario 5: Print & PDF Export

1. Open an existing 3-day itinerary in the UI.
2. Click "Export to PDF".
3. **Expected Outcome**:
   - The browser opens native print preview with `@media print` layout.
   - Non-printable UI chrome (header, sidebar, drag handles) is hidden.
   - All itinerary days, time slots, transit durations, and notes are formatted across clean multi-page document blocks.
