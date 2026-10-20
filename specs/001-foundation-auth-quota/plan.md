# Implementation Plan: Phase 1 — Foundation, Authentication, Quotas & Administration

**Branch**: `001-foundation-auth-quota` | **Date**: 2026-10-18 | **Spec**: [specs/001-foundation-auth-quota/spec.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/spec.md)  
**Input**: Feature specification from `specs/001-foundation-auth-quota/spec.md`  
**Constitution**: [.specify/memory/constitution.md](file:///d:/Coding/Vistarae/.specify/memory/constitution.md)

---

## Summary

Phase 1 (`001-foundation-auth-quota`) establishes the core infrastructure, identity, governance, and tenancy foundation for Vistarae. It implements a Python monorepo with an editable `packages/core` workspace package, pure async SQLAlchemy 2.0 database access with Neon cold-start retry loops, Alembic reversible migrations, AWS Cognito authentication with a stage-aware local mock bypass, rolling-window rate limiting with in-memory tier caching, database-backed idempotency protection, LLM token consumption budgeting, GDPR-compliant cascade deletion, and independent ASGI microservices (`services/user`, `services/admin`) unified locally via `services/local_gateway.py`.

---

## Technical Context

- **Language/Version**: Python 3.12+ (Ruff target `py312`)
- **Primary Dependencies**: FastAPI (>=0.115.0), Starlette, Uvicorn (>=0.30.0), Pydantic v2 (>=2.8.0), Pydantic-Settings (>=2.4.0), SQLAlchemy 2.0 (>=2.0.32, async), asyncpg (>=0.29.0), GeoAlchemy2 (>=0.15.0), Shapely (>=2.0.0), Alembic (>=1.13.0), Mangum (>=0.17.0), Boto3 / Botocore (>=1.34.0), PyJWT (>=2.8.0), OpenTelemetry SDK/API (>=1.26.0), HTTPX (>=0.27.0)
- **Storage**: PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4` in Docker; Neon PostgreSQL in cloud environments with `btree_gist` and `vector` extensions)
- **Messaging / Queues**: ElasticMQ Native (`softwaremill/elasticmq-native:latest`) simulating Amazon SQS locally (`vistarae-ingest-local` + DLQ)
- **Testing**: PyTest 8+, `pytest-asyncio`, `pytest-cov` (enforcing $\ge 90\%$ branch and line coverage), `httpx.AsyncClient` ASGI test client
- **Target Platform**: Local development on Windows/macOS/Linux via Docker Compose & Uvicorn; Cloud deployment on AWS Lambda (via Mangum) + Neon PostgreSQL
- **Project Type**: Python monorepo (Ports & Adapters architecture) with shared domain library (`packages/core`), standalone microservices (`services/user`, `services/admin`), and unified local ASGI gateway (`services/local_gateway.py`)
- **Performance Goals**: 
  - ASGI alive check (`/health/live`): $<2$ms (zero DB I/O)
  - Cached rate-limit check: $<1$ms via in-memory 60s TTL tier cache
  - Idempotent request replay: $<10$ms response latency (`X-Cache-Lookup: HIT`)
- **Constraints**: 
  - Zero DB queries on `/health/live` to protect Neon 190h/mo scale-to-zero compute quota
  - Zero CloudWatch `PutMetricData` or DynamoDB dependencies (Zero-Cost Architecture)
  - Strict RFC 7807 / RFC 9457 `application/problem+json` error envelopes
  - Strict cognitive complexity $\le 15$ and max nesting depth $\le 3$
- **Scale/Scope**: Multi-tenant database foundation supporting 50,000+ MAU, low tier (60 req/min) and high/admin tier (300 req/min), 50,000 monthly token quota default.

---

## Constitution Check

*GATE: Verified prior to research and design phases against `.specify/memory/constitution.md`.*

| Constitutional Invariant | Status | Compliance Detail |
| :--- | :---: | :--- |
| **1. File Header & Pre-Commit** | **PASS** | Mandatory copyright header `# Copyright (c) 2026 Vistarae. All rights reserved.` and `SPDX-License-Identifier: Apache-2.0` on every `.py` and `--` on `.sql` file. Google-style docstrings (`Args:`, `Returns:`, `Raises:`). Cognitive complexity $\le 15$. |
| **2. Monorepo & Ports/Adapters** | **PASS** | Shared domain, value objects, exceptions, and `typing.Protocol` ports placed in `packages/core` installed via `pip install -e ./packages/core`. Zero `boto3` or database driver imports in domain logic. Standalone ASGI apps with `Mangum(app, lifespan="off")`. |
| **3. Database & Tenancy** | **PASS** | SQLAlchemy 2.0 Async (`create_async_engine`, `AsyncSession`). URL normalized to `postgresql+asyncpg://`. Local uses `QueuePool(pool_size=5, max_overflow=5)`. Cloud uses `NullPool` with `connect_args={"statement_cache_size": 0}`. 3-attempt backoff retry loop (500ms, 1500ms, 3000ms). Explicit `WHERE user_id = :current_user_id` on all queries. No Postgres RLS. |
| **4. Alembic & Environment** | **PASS** | All migrations strictly inside `db/migrations/`. Reversible `downgrade()` implemented and tested. Enums modeled as Python `StrEnum` backed by `VARCHAR(n)` columns (no PostgreSQL native `ENUM`). `alembic check` enforced. |
| **5. API Contract & Validation** | **PASS** | Pydantic v2 `StrictBaseModel` (`extra="forbid"`, `validate_assignment=True`, `str_strip_whitespace=True`). OpenAPI 3.1 contracts exported. All errors formatted as RFC 7807 / RFC 9457 Problem Details. |
| **6. Middleware & Security** | **PASS** | Middleware order: `IdempotencyMiddleware` registered first, `RateLimitMiddleware` registered second (so Rate-Limiting executes outermost under Starlette LIFO). Rate limit 429 returns before idempotency allocation. CORS strictly configured (local `http://localhost:5173`, prod extension origin; never `*`). |
| **7. Observability & Tracing** | **PASS** | W3C `traceparent` propagation. Local mode emits literal directional markers (`MSG: -->|`, `MSG: <--|`, `MSG: <~~|`). Cloud mode emits structured JSON with X-Ray trace context. |
| **8. PyTest & SDD Governance** | **PASS** | $\ge 90\%$ branch and line coverage enforced (`--cov=packages/core --cov=services --cov-fail-under=90`). Tests mirror source tree 1:1 inside `tests/unit/`. Classes structured as `Test<FeatureOrMethod>`. |
| **Operational & Infrastructure** | **PASS** | Docker Compose runs `postgis/postgis:16-3.4` with volume `postgis_data` and ElasticMQ native mounting `docker/elasticmq.conf` with 180s visibility timeout. Neon scale-to-zero preserved via `/health/live`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation-auth-quota/
├── spec.md              # Requirements and architecture specification
├── plan.md              # This implementation plan
├── research.md          # Architectural research & decisions
├── data-model.md        # Relational schemas, ERD, and Pydantic models
├── quickstart.md        # Step-by-step local verification & test scenarios
└── contracts/
    └── api.openapi.yaml # Authoritative OpenAPI 3.1 contract specification
```

### Source Code Layout (Repository Root)

```text
d:\Coding\Vistarae\
├── .specify/
│   ├── memory/
│   │   └── constitution.md
│   └── feature.json
├── .pre-commit-config.yaml         # Pre-commit hook configuration (Principle 1)
├── alembic.ini                         # Root Alembic configuration pointing to db/migrations
├── docker/
│   └── elasticmq.conf                  # SQS emulation queue & DLQ definitions
├── docker-compose.yml                  # PostGIS 16-3.4 + ElasticMQ Native
├── pyproject.toml                      # Monorepo workspace configuration & pytest/ruff
├── packages/
│   └── core/                           # Shared domain library (editable install)
│       ├── pyproject.toml
│       └── vistarae_core/
│           ├── __init__.py
│           ├── domain/                 # Domain entities, value objects, exceptions
│           │   ├── __init__.py
│           │   ├── entities.py         # User, UserPreferences, UserQuota, etc.
│           │   ├── value_objects.py    # UserTier, ThemeMode, PacingMode, etc.
│           │   └── exceptions.py       # Domain-specific exceptions
│           ├── ports/                  # Abstract Protocol interfaces
│           │   ├── __init__.py
│           │   ├── repositories.py     # IUserRepository, IQuotaRepository, etc.
│           │   ├── identity.py         # IIdentityProvider (Cognito/Mock)
│           │   └── queue.py            # IMessageQueue (SQS/ElasticMQ)
│           ├── adapters/               # Concrete adapters
│           │   ├── __init__.py
│           │   ├── db/
│           │   │   ├── session.py      # AsyncEngine factory, pooling & retry
│           │   │   ├── base.py         # DeclarativeBase, mixins
│           │   │   └── tables.py       # SQLAlchemy 2.0 ORM Table definitions
│           │   ├── repositories/
│           │   │   ├── user_repo.py    # SQLAlchemy User & Preferences repository
│           │   │   ├── quota_repo.py   # Rolling window rate limiting & quotas
│           │   │   └── idempotency_repo.py # Idempotency persistence
│           │   ├── identity/
│           │   │   ├── cognito.py      # Boto3 Cognito & JWKS validation
│           │   │   └── mock.py         # Local X-Mock-User-Id bypass provider
│           │   └── queue/
│           │       └── sqs.py          # Boto3 SQS client adapter
│           ├── services/               # Domain application services
│           │   ├── __init__.py
│           │   └── token_budget.py     # TokenBudgetService (pre-flight check & atomic incr)
│           ├── middleware/             # Shared Starlette middleware
│           │   ├── __init__.py
│           │   ├── telemetry.py        # W3C trace & local MSG: -->| markers
│           │   ├── rate_limit.py       # 1-min rolling bucket & 60s tier cache
│           │   ├── idempotency.py      # Key locking, 409 conflict, replay
│           │   └── errors.py           # RFC 7807 ProblemDetails handler
│           └── schemas/                # StrictBaseModel Pydantic v2 schemas
│               ├── __init__.py
│               ├── base.py             # StrictBaseModel base definition
│               ├── user.py             # UserProfileResponse, UpdateUserRequest
│               ├── preferences.py      # UI, POI, Planner preference schemas
│               ├── admin.py            # Admin metrics, quota mutation schemas
│               └── errors.py           # RFC 7807 ProblemDetails schema
├── db/
│   └── migrations/                     # Schema migration scripts
│       ├── env.py                      # Pure Async Alembic runner
│       ├── script.py.mako              # Migration script template with header
│       └── versions/
│           └── 0001_foundation_auth_quota.py # Initial migration
├── services/
│   ├── local_gateway.py                # Unified ASGI dev router & CORS/lifespan
│   ├── user/                           # UserFunction microservice
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app & Mangum handler
│   │   ├── dependencies.py             # Auth dependency (Cognito / Local bypass)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── me.py                   # /api/users/me (profile & GDPR delete)
│   │       └── preferences.py          # /api/users/me/preferences/*
│   └── admin/                          # AdminFunction microservice
│       ├── __init__.py
│       ├── main.py                     # FastAPI app & Mangum handler
│       ├── dependencies.py             # Admin RBAC guard
│       └── routes/
│           ├── __init__.py
│           ├── metrics.py              # /api/admin/metrics
│           ├── users.py                # /api/admin/users/* (disable, quotas)
│           └── controls.py             # /api/admin/quotas/defaults, trace toggle
├── scripts/
│   ├── check_copyright_headers.py      # Enforces copyright header banner
│   ├── export_openapi.py               # Generates openapi.json from apps
│   ├── seed_local_db.py                # Seeds local test user and quotas
│   └── redrive_dlq.py                  # Operational redrive CLI
└── tests/
    ├── conftest.py                     # Async engine, mock auth, DB session fixtures
    └── unit/                           # 1:1 mirror of production code
        ├── packages/
        │   └── core/
        │       ├── test_entities.py
        │       ├── test_db_session.py
        │       ├── test_user_repo.py
        │       ├── test_quota_repo.py
        │       ├── test_idempotency_repo.py
        │       ├── test_token_budget_service.py
        │       ├── test_rate_limit_mw.py
        │       ├── test_idempotency_mw.py
        │       └── test_telemetry_mw.py
        └── services/
            ├── test_local_gateway.py
            ├── test_health_probes.py
            ├── user/
            │   ├── test_auth_dependency.py
            │   ├── test_routes_me.py
            │   └── test_routes_preferences.py
            └── admin/
                ├── test_admin_dependencies.py
                ├── test_routes_metrics.py
                └── test_routes_users.py
```

---

## Detailed Component Specifications

### 1. Root Workspace `pyproject.toml`
The root `pyproject.toml` manages monorepo dependencies, test execution, coverage enforcement, and linting standards:

```toml
# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

[project]
name = "vistarae-workspace"
version = "0.1.0"
description = "Vistarae Platform Root Workspace"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "sqlalchemy[asyncio]>=2.0.32",
    "asyncpg>=0.29.0",
    "geoalchemy2>=0.15.0",
    "shapely>=2.0.0",
    "alembic>=1.13.0",
    "boto3>=1.34.0",
    "mangum>=0.17.0",
    "pyjwt[crypto]>=2.8.0",
    "httpx>=0.27.0",
    "opentelemetry-api>=1.26.0",
    "opentelemetry-sdk>=1.26.0",
    "opentelemetry-instrumentation-fastapi>=0.47b0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "testcontainers[postgres]>=4.7.0",
    "ruff>=0.5.0",
    "mypy>=1.11.0",
    "pre-commit>=3.7.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = [".", "packages/core"]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--cov=packages/core --cov=services --cov-fail-under=90 --cov-report=term-missing"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "C901"]
ignore = ["B008", "E501", "UP042"]
mccabe = { max-complexity = 15 }

[tool.coverage.run]
source = ["packages/core", "services"]
omit = ["tests/*", "*/__pycache__/*"]
branch = true

[tool.coverage.report]
fail_under = 90
show_missing = true
```

---

### 2. `packages/core` Layout & Implementation

#### 2.1 Package Manifest (`packages/core/pyproject.toml`)
```toml
# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vistarae-core"
version = "0.1.0"
description = "Vistarae Core Domain, Ports, Adapters and Schemas"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.8.0",
    "sqlalchemy[asyncio]>=2.0.32",
    "asyncpg>=0.29.0",
    "starlette>=0.38.0",
    "httpx>=0.27.0",
    "pyjwt[crypto]>=2.8.0",
]
```

#### 2.2 Domain Entities & Value Objects (`vistarae_core/domain/`)
- `value_objects.py`: Defines `UserTier`, `ThemeMode`, `PacingMode`, `TransitSpeedMode`, and `IdempotencyStatus` using Python `StrEnum`.
- `entities.py`: Pure Python dataclasses representing business aggregates (`User`, `UserPreferences`, `UserQuota`, `UserMetric`, `IdempotencyRecord`) without SQLAlchemy or Pydantic runtime dependencies.
- `exceptions.py`: Pure domain exceptions (`AccountDisabledError`, `QuotaExceededError`, `IdempotencyConflictError`, `TenantNotFoundError`).

#### 2.3 Port Interfaces (`vistarae_core/ports/`)
Abstract interfaces using `typing.Protocol`:
- `IUserRepository`: `get_by_id(user_id)`, `get_by_cognito_sub(sub)`, `create(user, preferences, quotas, metrics)`, `update_profile(user_id, full_name)`, `delete(user_id)`.
- `IQuotaRepository`: `get_quota(user_id)`, `increment_request_count(user_id, tier, window_seconds=60) -> tuple[int, int, bool]`, `check_token_budget(user_id, required_tokens) -> bool`, `increment_tokens(user_id, tokens)`.
- `IIdempotencyRepository`: `get_or_create(user_id, key) -> tuple[IdempotencyStatus, int | None, dict | None]`, `complete(user_id, key, status_code, payload)`, `fail(user_id, key)`, `cleanup_older_than(hours=24)`.
- `IIdentityProvider`: `verify_token(token) -> dict`, `delete_user(cognito_sub)`.

#### 2.4 Database Adapter (`vistarae_core/adapters/db/`)
- `session.py`:
  - Normalizes `DATABASE_URL` from `postgres://` or `postgresql://` to `postgresql+asyncpg://` and replaces `sslmode=require` with `ssl=require`.
  - Configures `QueuePool` (pool_size=5, max_overflow=5) when `STAGE == 'local'`.
  - Configures `NullPool` with `connect_args={"statement_cache_size": 0}` when `STAGE != 'local'`.
  - Implements 3-attempt exponential backoff retry loop (500ms, 1500ms, 3000ms) for initial connection acquisition.
  - Exposes `get_db_session()` dependency yielding an `AsyncSession`.
- `tables.py`: Defines SQLAlchemy 2.0 ORM models mapping `users`, `user_preferences`, `user_metrics`, `user_quotas`, and `idempotency_keys` with `ON DELETE CASCADE`.

#### 2.5 Repositories Adapter (`vistarae_core/adapters/repositories/`)
- `user_repo.py`: Async SQLAlchemy implementation of `IUserRepository`.
- `quota_repo.py`: Atomic rolling window increment using PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` with timestamp checks.
- `idempotency_repo.py`: Atomic `INSERT ... ON CONFLICT (user_id, idempotency_key) DO NOTHING` returning record status.

#### 2.6 Middleware (`vistarae_core/middleware/`)
- `telemetry.py`:
  - Extracts W3C `traceparent` (`00-{trace_id}-{parent_span_id}-01`).
  - Generates new server `span_id`.
  - Attaches `X-Transaction-ID`, `X-Current-Span-ID`, `X-Parent-Transaction-ID` to outgoing response headers.
  - When `STAGE == "local"`, emits formatted logs:
    - Inbound: `MSG: -->| [{source} -> {destination}] [trace={trace_id}] {method} {path}`
    - Outbound 2XX: `MSG: <--| [{destination} -> {source}] [status={code}]`
    - Outbound 4XX/5XX: `MSG: <~~| [{destination} -> {source}] [status={code}]`
- `rate_limit.py`:
  - In-memory tier cache (`dict[UUID, tuple[UserTier, bool, float]]`) with 60-second TTL.
  - Checks if user is disabled -> returns RFC 7807 403 Forbidden.
  - Checks rolling 1-minute window -> increments in DB if cache valid.
  - If limit exceeded -> returns RFC 7807 429 Too Many Requests with `Retry-After: {seconds}` header.
- `idempotency.py`:
  - Inspects mutating methods (`POST`, `PUT`, `PATCH`, `DELETE`).
  - Reads `Idempotency-Key` header. If missing, passes through.
  - Calls `IIdempotencyRepository.get_or_create`.
  - If `PENDING`: Returns RFC 7807 409 Conflict.
  - If `COMPLETED`: Short-circuits and replays cached response with header `X-Cache-Lookup: HIT`.
  - If newly created: Intercepts response stream; upon successful completion (2XX/3XX), caches code & body as `COMPLETED`; on error, marks `FAILED`.

#### 2.7 Domain Application Services (`vistarae_core/services/`)
- `token_budget.py`:
  - `TokenBudgetService`: Encapsulates pre-flight token budget verification and atomic post-flight usage tracking.
  - Verifies `current_token_usage < monthly_token_quota`.
  - Rejects with RFC 7807 429 Too Many Requests (`https://errors.vistarae.com/token-quota-exceeded`) when budget is exhausted.
  - Executes atomic post-flight increment on both `user_quotas.current_token_usage` and `user_metrics.total_tokens_consumed`.

---

### 3. `db/migrations` (Alembic Setup & Initial Migration)

#### 3.1 Async Alembic Runner (`alembic.ini` & `db/migrations/env.py`)
- Standard root configuration file `alembic.ini` with `script_location = db/migrations`.
- Configured for SQLAlchemy 2.0 async engine via `asyncpg`.
- Sourced from `DATABASE_URL` environment variable.
- Sets `target_metadata = Base.metadata` from `vistarae_core.adapters.db.tables`.
- Replaces `%` in connection strings for safe URL parsing.

#### 3.2 Initial Migration Script (`0001_foundation_auth_quota.py`)
- Header standard:
  ```sql
  -- Copyright (c) 2026 Vistarae. All rights reserved.
  -- SPDX-License-Identifier: Apache-2.0
  ```
- `upgrade()`:
  1. Executes `CREATE EXTENSION IF NOT EXISTS` for `uuid-ossp`, `postgis`, `btree_gist`, `vector`.
  2. Creates tables: `users`, `user_preferences`, `user_metrics`, `user_quotas`, `idempotency_keys`.
  3. Creates indices:
     - `idx_users_cognito_sub` ON `users(cognito_sub)`
     - `idx_users_email` ON `users(email)`
     - `idx_user_quotas_tier` ON `user_quotas(tier)`
     - `idx_idempotency_keys_created_at` ON `idempotency_keys(created_at)`
  4. Enforces check constraints for enum string values.
- `downgrade()`:
  1. Drops tables in reverse dependency order: `idempotency_keys`, `user_quotas`, `user_metrics`, `user_preferences`, `users`.
  2. Drops indices.
  3. Fully reversible (no-op downgrade strictly forbidden).

---

### 4. `services/user` (UserFunction)

#### 4.1 FastAPI App (`services/user/main.py`)
- Independent ASGI application instance exposing routes under `/api/users`.
- Serverless entrypoint: `lambda_handler = Mangum(app, lifespan="off")`.
- Lifespan handler initializes connection pool and disposes cleanly.

#### 4.2 Authentication Dependency (`services/user/dependencies.py`)
- Resolves authenticated user context:
  - If `STAGE == "local"` and `X-Mock-User-Id` header is present: validates UUID format and retrieves/provisions mock user.
  - If `STAGE != "local"`: verifies Bearer JWT against AWS Cognito JWKS cache.
  - If JWT `sub` is not found in `users` table: returns RFC 7807 401 Unauthorized (`https://errors.vistarae.com/user-not-found`).
  - If `user_quotas.is_disabled` is `TRUE`: returns RFC 7807 403 Forbidden (`https://errors.vistarae.com/account-disabled`).

#### 4.3 Route Handlers
- `GET /api/users/me`: Returns `UserProfileResponse` combining user profile, sub-domain preferences, metrics, and quota status.
- `PATCH /api/users/me`: Updates `full_name` in `users`.
- `GET /api/users/me/preferences`: Returns `UserPreferencesResponse` (UI, POI, Planner).
- `PATCH /api/users/me/preferences/ui`: Updates Account/UI preferences.
- `PATCH /api/users/me/preferences/poi`: Updates POI Mode preferences.
- `PATCH /api/users/me/preferences/planner`: Updates Planner Mode preferences.
- `DELETE /api/users/me`: Invokes AWS Cognito `AdminDeleteUser(cognito_sub)` and then executes `DELETE FROM users WHERE id = :user_id` (triggering PostgreSQL foreign key cascade across all user data).

---

### 5. `services/admin` (AdminFunction)

#### 5.1 FastAPI App (`services/admin/main.py`)
- Independent ASGI application instance exposing routes under `/api/admin`.
- Serverless entrypoint: `lambda_handler = Mangum(app, lifespan="off")`.

#### 5.2 Admin RBAC Guard (`services/admin/dependencies.py`)
- Inspects authenticated caller's tier from `user_quotas` or Cognito admin group claims.
- If caller tier is not `'admin'`: raises RFC 7807 403 Forbidden (`https://errors.vistarae.com/admin-forbidden`).

#### 5.3 Route Handlers
- `GET /api/admin/metrics`: Aggregates platform telemetry (`total_users`, `active_users`, `disabled_users`, `total_pois`, `total_tokens_consumed`, `tier_distribution`).
- `GET /api/admin/users/{user_id}`: Inspects complete tenant account details (profile, quotas, preferences, metrics).
- `PATCH /api/admin/users/{user_id}/quota`: Updates `monthly_token_quota` or `tier` in `user_quotas` and invalidates the target user's in-memory tier cache entry.
- `POST /api/admin/users/{user_id}/disable`: Sets `is_disabled = TRUE` in `user_quotas` and invalidates tier cache.
- `POST /api/admin/users/{user_id}/enable`: Sets `is_disabled = FALSE` in `user_quotas` and invalidates tier cache.
- `PUT /api/admin/quotas/defaults`: Updates platform default provisioning quotas.
- `POST /api/admin/trace-injection/toggle`: Toggles global admin trace injection override.
- `POST /api/admin/users/{user_id}/messages`: Dispatches administrative notification.

---

### 6. `services/local_gateway.py` (Unified Local Gateway)

The local gateway is initialized in Phase 2 (`T-015`) to provide application lifespan connection management and standalone dual-probe health check endpoints (`/health/live`, `/health/ready`). In Phase 9 (`T-050`), once `services.user` and `services.admin` have been implemented, the microservice sub-applications and Starlette LIFO middleware stack are mounted:

```python
# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Unified Local Development ASGI Gateway.

Mounts standalone microservices (UserFunction, AdminFunction) and exposes
dual-probe health endpoints with unified middleware pipeline and CORS.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.session import get_db_session, get_engine
from vistarae_core.middleware.telemetry import TelemetryMiddleware
from vistarae_core.middleware.rate_limit import RateLimitMiddleware
from vistarae_core.middleware.idempotency import IdempotencyMiddleware
from vistarae_core.middleware.errors import add_problem_details_handlers
from services.user.main import app as user_app
from services.admin.main import app as admin_app

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and clean connection disposal."""
    engine = get_engine()
    yield
    await engine.dispose()

gateway = FastAPI(
    title="Vistarae Local Gateway",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. Error boundary handlers
add_problem_details_handlers(gateway)

# 2. Dual-probe health check endpoints
@gateway.get("/health/live", status_code=status.HTTP_200_OK)
async def health_live() -> dict[str, str]:
    """Zero-IO liveness probe for container alive checks."""
    return {"status": "alive"}

@gateway.get("/health/ready", status_code=status.HTTP_200_OK)
async def health_ready(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Database readiness probe executing SELECT 1."""
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}

# 3. Mount microservices
gateway.mount("/api/users", user_app)
gateway.mount("/api/admin", admin_app)

# 4. Middleware registration:
# Under Starlette's LIFO execution model:
# Outer: TelemetryMiddleware -> RateLimitMiddleware -> IdempotencyMiddleware : Inner
gateway.add_middleware(IdempotencyMiddleware)
gateway.add_middleware(RateLimitMiddleware)
gateway.add_middleware(TelemetryMiddleware)

# 5. Local CORS configuration
gateway.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Mock-User-Id",
        "X-Mock-User-Tier",
        "traceparent",
        "X-Source",
        "X-Destination",
    ],
)

app = gateway
```

---

### 7. Local Infrastructure (`docker-compose.yml` & `docker/elasticmq.conf`)

#### 7.1 ElasticMQ Configuration (`docker/elasticmq.conf`)
Pre-configures local SQS queue emulation with DLQ and 180-second visibility timeout:
```hocon
include classpath("application.conf")

node-address {
    protocol = http
    host = "*"
    port = 9324
    context = ""
}

rest-sqs {
    enabled = true
    bind-port = 9324
    bind-hostname = "0.0.0.0"
    sqs-limits = strict
}

rest-stats {
    enabled = true
    bind-port = 9325
    bind-hostname = "0.0.0.0"
}

queues {
    vistarae-ingest-dlq-local {
        defaultVisibilityTimeout = 180 seconds
        delay = 0 seconds
        receiveMessageWait = 0 seconds
    }
    vistarae-ingest-local {
        defaultVisibilityTimeout = 180 seconds
        delay = 0 seconds
        receiveMessageWait = 20 seconds
        deadLettersQueue {
            name = "vistarae-ingest-dlq-local"
            maxReceiveCount = 3
        }
    }
}
```

#### 7.2 Docker Compose Services (`docker-compose.yml`)
- `postgis`: Image `postgis/postgis:16-3.4`, port 5432, named volume `postgis_data:/var/lib/postgresql/data`.
- `elasticmq`: Image `softwaremill/elasticmq-native:latest`, ports 9324 (SQS) & 9325 (stats), mounts `docker/elasticmq.conf:/opt/elasticmq.conf`.

---

## Testing Strategy & Coverage Governance

1. **PyTest Invariant**: PyTest executes with `--cov=packages/core --cov=services --cov-fail-under=90`. CI rejects any PR with $<90\%$ branch or line coverage.
2. **Directory Mirroring**: `tests/unit/` mirrors the production source tree 1:1.
3. **Test Classes**: All test methods are contained within `Test<FeatureOrMethod>` classes.
4. **Fixtures**:
   - `async_db_session`: Yields a transactional session rolled back after every test case.
   - `mock_user`: Injects standard test user with tier `'low'` and tier `'admin'`.
   - `asgi_client`: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| *None* | *All requirements and patterns fully adhere to the Vistarae Constitution.* | *N/A* |
