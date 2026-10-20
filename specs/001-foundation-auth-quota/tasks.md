# Tasks: Phase 1 — Foundation, Authentication, Quotas & Administration

**Feature**: `001-foundation-auth-quota` | **Status**: `READY` | **Date**: `2026-10-19`  
**Spec**: [specs/001-foundation-auth-quota/spec.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/spec.md)  
**Plan**: [specs/001-foundation-auth-quota/plan.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/plan.md)  
**Data Model**: [specs/001-foundation-auth-quota/data-model.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/data-model.md)  
**Contracts**: [specs/001-foundation-auth-quota/contracts/api.openapi.yaml](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/contracts/api.openapi.yaml)  
**Quickstart**: [specs/001-foundation-auth-quota/quickstart.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/quickstart.md)

---

## Phase 1: Setup (Workspace & Shared Infrastructure)

**Purpose**: Initialize monorepo workspace configuration, local container orchestration, and test environment prerequisites.

- [x] T-001 [REQ-FOUND-001] [REQ-FOUND-002] Create root workspace pyproject.toml with editable packages/core mapping, ruff lint config (target-version py312, line-length 100, cognitive complexity ceiling <= 15), and pytest coverage enforcement (>= 90% branch and line) in [pyproject.toml](file:///d:/Coding/Vistarae/pyproject.toml)
- [x] T-002 [P] [REQ-FOUND-003] [REQ-FOUND-004] [REQ-FOUND-005] Configure ElasticMQ native SQS queues (vistarae-ingest-local with visibility timeout 180s, receive message wait 20s, maxReceiveCount 3, and DLQ vistarae-ingest-dlq-local with visibility timeout 180s) in [docker/elasticmq.conf](file:///d:/Coding/Vistarae/docker/elasticmq.conf)
- [x] T-003 [P] [REQ-FOUND-001] [REQ-FOUND-002] [REQ-FOUND-003] Update local docker compose stack to orchestrate postgis/postgis:16-3.4 (with persistent volume postgis_data:/var/lib/postgresql/data) and softwaremill/elasticmq-native:latest (mounting docker/elasticmq.conf) in [docker-compose.yml](file:///d:/Coding/Vistarae/docker-compose.yml)
- [x] T-004 [P] Create editable domain package build definition and metadata in [packages/core/pyproject.toml](file:///d:/Coding/Vistarae/packages/core/pyproject.toml)
- [x] T-005 [P] Setup shared PyTest test fixtures (async database session with transaction rollback, mock user generators, HTTPX ASGI client) in [tests/conftest.py](file:///d:/Coding/Vistarae/tests/conftest.py)
- [x] T-005b [P] Configure .pre-commit-config.yaml and scripts/check_copyright_headers.py enforcing ruff, prettier, and mandatory copyright banner verification across all .py, .ts, .tsx, and .sql files per Constitution Principle 1 in [.pre-commit-config.yaml](file:///d:/Coding/Vistarae/.pre-commit-config.yaml) and [scripts/check_copyright_headers.py](file:///d:/Coding/Vistarae/scripts/check_copyright_headers.py)

---

## Phase 2: Foundational (Core Domain, Database Engine & Alembic Migrations)

**Purpose**: Establish core domain models, protocol interfaces, pure async SQLAlchemy 2.0 database engine with cold-start resilience, Alembic migrations, and dual-probe health checks.

**⚠️ CRITICAL**: Blocking prerequisite for all user stories. No user story work can begin until this phase is complete.

- [x] T-006 [P] [REQ-FOUND-008] [REQ-FOUND-010] [REQ-FOUND-011] Define pure domain StrEnum value objects (UserTier ['low', 'high', 'admin'], ThemeMode ['light', 'dark', 'system'], PacingMode ['relaxed', 'moderate', 'fast_paced'], TransitSpeedMode ['walking', 'bicycling', 'transit', 'driving'], IdempotencyStatus ['PENDING', 'COMPLETED', 'FAILED']) and aggregates in [packages/core/vistarae_core/domain/value_objects.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/domain/value_objects.py) and [packages/core/vistarae_core/domain/entities.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/domain/entities.py) with unit test in [tests/unit/packages/core/test_entities.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_entities.py)
- [x] T-007 [P] Define domain exceptions (AccountDisabledError, QuotaExceededError, IdempotencyConflictError, TenantNotFoundError) in [packages/core/vistarae_core/domain/exceptions.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/domain/exceptions.py)
- [x] T-008 [P] Define typing.Protocol port interfaces (IUserRepository, IQuotaRepository, IIdempotencyRepository, IIdentityProvider, IMessageQueue) isolating external dependencies in [packages/core/vistarae_core/ports/repositories.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/ports/repositories.py), [packages/core/vistarae_core/ports/identity.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/ports/identity.py), and [packages/core/vistarae_core/ports/queue.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/ports/queue.py)
- [x] T-009 [P] Implement SQLAlchemy 2.0 Pure Async connection factory (normalizing postgresql+asyncpg://, QueuePool [size=5, overflow=5] for local, NullPool with statement_cache_size=0 for cloud, 3-attempt exponential backoff retry at 500ms, 1500ms, 3000ms) in [packages/core/vistarae_core/adapters/db/session.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/db/session.py) with unit test in [tests/unit/packages/core/test_db_session.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_db_session.py)
- [x] T-010 [P] [REQ-FOUND-007] [REQ-FOUND-008] [REQ-FOUND-009] [REQ-FOUND-010] [REQ-FOUND-011] Implement SQLAlchemy 2.0 Declarative ORM tables for users, user_preferences, user_metrics, user_quotas, and idempotency_keys with mandatory ON DELETE CASCADE in [packages/core/vistarae_core/adapters/db/tables.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/db/tables.py) and [packages/core/vistarae_core/adapters/db/base.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/db/base.py) with unit test in [tests/unit/packages/core/test_tables.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_tables.py)
- [x] T-011 [P] Implement Pydantic v2 StrictBaseModel schemas (extra='forbid', validate_assignment=True, str_strip_whitespace=True) and RFC 7807 ProblemDetails error models in [packages/core/vistarae_core/schemas/base.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/schemas/base.py) and [packages/core/vistarae_core/schemas/errors.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/schemas/errors.py)
- [x] T-012 [P] Implement RFC 7807 FastAPI exception handlers formatting non-2XX responses as application/problem+json in [packages/core/vistarae_core/middleware/errors.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/middleware/errors.py)
- [x] T-013 [REQ-FOUND-006] [REQ-FOUND-007] [REQ-FOUND-008] [REQ-FOUND-009] [REQ-FOUND-010] [REQ-FOUND-011] Configure Alembic async runner and author initial migration script enabling extensions (uuid-ossp, postgis, btree_gist, vector), creating tenant tables with CASCADE foreign keys, check constraints, indices, and fully reversible downgrade in [alembic.ini](file:///d:/Coding/Vistarae/alembic.ini), [db/migrations/env.py](file:///d:/Coding/Vistarae/db/migrations/env.py), and [db/migrations/versions/0001_foundation_auth_quota.py](file:///d:/Coding/Vistarae/db/migrations/versions/0001_foundation_auth_quota.py)
- [x] T-014 [P] Implement W3C distributed tracing telemetry middleware extracting traceparent and emitting directional message logs (MSG: -->|, MSG: <--|, MSG: <~~|) when STAGE == 'local' in [packages/core/vistarae_core/middleware/telemetry.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/middleware/telemetry.py) with unit test in [tests/unit/packages/core/test_telemetry_mw.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_telemetry_mw.py)
- [x] T-015 [REQ-FOUND-012] [REQ-FOUND-013] [REQ-FOUND-014] [REQ-FOUND-015] Implement initial standalone gateway defining lifespan connection pool and dual-probe health endpoints (/health/live with zero DB I/O returning 200 OK, /health/ready executing SELECT 1 returning 200 or 503) without mounting unbuilt microservices in [services/local_gateway.py](file:///d:/Coding/Vistarae/services/local_gateway.py) with unit test in [tests/unit/services/test_health_probes.py](file:///d:/Coding/Vistarae/tests/unit/services/test_health_probes.py)

**Checkpoint**: Core foundation, async database engine, Alembic migrations, telemetry, and health probes ready. User story implementation can now proceed.

---

## Phase 3: User Story 1 — Authentication, Local Mock Bypass & GDPR Deletion (Priority: P1) 🎯 MVP

**Goal**: Establish tenant identity management via AWS Cognito, stage-aware local mock bypass (`X-Mock-User-Id`), disabled/orphaned account guards, and GDPR-compliant cascade deletion.

**Independent Test**: Verify user registration, mock bypass resolving user context when `STAGE == 'local'`, rejection of mock headers when `STAGE != 'local'`, immediate 401 for orphaned JWTs, 403 for disabled users, and cascade deletion via `DELETE /api/users/me`.

### Tests for User Story 1

- [x] T-016 [P] [US1] Write unit tests for AWS Cognito adapter and local mock provider in [tests/unit/packages/core/test_identity_adapters.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_identity_adapters.py)
- [x] T-017 [P] [US1] Write unit tests for authentication dependency (verifying JWKS validation, local X-Mock-User-Id bypass, 401 for orphaned JWTs, and 403 for disabled accounts) in [tests/unit/services/user/test_auth_dependency.py](file:///d:/Coding/Vistarae/tests/unit/services/user/test_auth_dependency.py)
- [x] T-018 [P] [US1] Write integration test verifying authentication lifecycle, local bypass, and GDPR cascade deletion in [tests/integration/test_auth_flow.py](file:///d:/Coding/Vistarae/tests/integration/test_auth_flow.py)

### Implementation for User Story 1

- [x] T-019 [P] [US1] [REQ-AUTH-001] [REQ-AUTH-003] [REQ-AUTH-004] [REQ-AUTH-005] [REQ-AUTH-006] Implement AWS Cognito adapter and local mock identity provider in [packages/core/vistarae_core/adapters/identity/cognito.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/identity/cognito.py) and [packages/core/vistarae_core/adapters/identity/mock.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/identity/mock.py)
- [x] T-020 [US1] [REQ-AUTH-002] [REQ-AUTH-010] Implement SQLAlchemy user repository managing users, preferences, metrics, and quotas insertion with tenant-scoped queries in [packages/core/vistarae_core/adapters/repositories/user_repo.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/repositories/user_repo.py) with unit test in [tests/unit/packages/core/test_user_repo.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_user_repo.py)
- [x] T-021 [US1] [REQ-AUTH-007] [REQ-AUTH-008] [REQ-AUTH-011] [REQ-AUTH-012] Implement stage-aware authentication dependency (supporting X-Mock-User-Id when STAGE == 'local', enforcing Cognito JWKS in cloud, checking orphaned JWTs [401], and checking is_disabled [403]) in [services/user/dependencies.py](file:///d:/Coding/Vistarae/services/user/dependencies.py)
- [x] T-022 [US1] [REQ-AUTH-009] [REQ-AUTH-010] Implement GDPR-compliant account deletion endpoint (DELETE /api/users/me calling Cognito AdminDeleteUser followed by PostgreSQL DELETE FROM users WHERE id = :user_id) in [services/user/routes/me.py](file:///d:/Coding/Vistarae/services/user/routes/me.py) with unit test in [tests/unit/services/user/test_routes_me.py](file:///d:/Coding/Vistarae/tests/unit/services/user/test_routes_me.py)

**Checkpoint**: Authentication, local stage bypass, and GDPR cascade deletion fully functional and independently verified.

---

## Phase 4: User Story 2 — User Profile & Sub-Domain Preferences (Priority: P1)

**Goal**: Deliver user profile management and partitioned sub-domain preferences (Account/UI, POI Mode, Planner Mode) with strict Pydantic v2 validation.

**Independent Test**: Fetch current user representation (`GET /api/users/me`), update profile name (`PATCH /api/users/me`), and independently fetch and mutate UI, POI, and Planner sub-domain preferences.

### Tests for User Story 2

- [x] T-023 [P] [US2] Write unit tests for UserProfileResponse and sub-domain preference schemas validation rules (clustering_radius_meters [10..500], meal_intervals_hours [1..8], daily_activity_hour_cap [1..18], preferred_currency [3 chars]) in [tests/unit/packages/core/test_schemas_preferences.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_schemas_preferences.py)
- [x] T-024 [P] [US2] Write unit tests for UserFunction profile and preferences routes in [tests/unit/services/user/test_routes_preferences.py](file:///d:/Coding/Vistarae/tests/unit/services/user/test_routes_preferences.py)

### Implementation for User Story 2

- [x] T-025 [P] [US2] [REQ-ADMIN-001] [REQ-ADMIN-002] [REQ-ADMIN-003] Define UserResponse, UpdateUserRequest, UserProfileResponse, UIPreferencesResponse, POIPreferencesResponse, PlannerPreferencesResponse, and UserPreferencesResponse schemas in [packages/core/vistarae_core/schemas/user.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/schemas/user.py) and [packages/core/vistarae_core/schemas/preferences.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/schemas/preferences.py)
- [x] T-026 [US2] [REQ-ADMIN-001] [REQ-ADMIN-002] Implement GET /api/users/me (combining profile, preferences, metrics, quotas) and PATCH /api/users/me (updating full_name) in [services/user/routes/me.py](file:///d:/Coding/Vistarae/services/user/routes/me.py)
- [x] T-027 [US2] [REQ-ADMIN-003] [REQ-ADMIN-004] [REQ-ADMIN-005] [REQ-ADMIN-006] Implement GET /api/users/me/preferences, PATCH /api/users/me/preferences/ui, PATCH /api/users/me/preferences/poi, and PATCH /api/users/me/preferences/planner in [services/user/routes/preferences.py](file:///d:/Coding/Vistarae/services/user/routes/preferences.py)
- [x] T-028 [US2] Assemble UserFunction FastAPI application instance with lifespan connection management and serverless lambda_handler = Mangum(app, lifespan="off") in [services/user/main.py](file:///d:/Coding/Vistarae/services/user/main.py)

**Checkpoint**: User profile and all sub-domain preference routes operational and testable.

---

## Phase 5: User Story 3 — Rolling Rate Limiting & Tier Caching (Priority: P2)

**Goal**: Enforce request rate limits via a 1-minute rolling window in PostgreSQL `user_quotas` (Low: 60 req/min, High/Admin: 300 req/min) optimized with a 60-second in-memory tier cache and RFC 7807 429 response.

**Independent Test**: Send 61 requests under tier `'low'`; assert requests 1–60 succeed (200 OK) and request 61 returns 429 with `Retry-After` header and RFC 7807 problem details JSON.

### Tests for User Story 3

- [x] T-029 [P] [US3] Write unit tests for Quota repository rolling window increments and tier limit queries in [tests/unit/packages/core/test_quota_repo.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_quota_repo.py)
- [x] T-030 [P] [US3] Write unit tests for RateLimitMiddleware (testing tier limits, in-memory cache hit/miss/expiry, window rollover, and RFC 7807 429 with Retry-After header) in [tests/unit/packages/core/test_rate_limit_mw.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_rate_limit_mw.py)

### Implementation for User Story 3

- [x] T-031 [US3] [REQ-QUOTA-001] [REQ-QUOTA-002] [REQ-QUOTA-003] [REQ-QUOTA-005] Implement atomic rolling window increment in quota repository (updating request_count and window_start_at with atomic rollover on window expiry) in [packages/core/vistarae_core/adapters/repositories/quota_repo.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/repositories/quota_repo.py)
- [x] T-032 [US3] [REQ-QUOTA-004] [REQ-QUOTA-006] Implement RateLimitMiddleware with thread-safe 60-second TTL in-memory tier and disablement cache, returning RFC 7807 429 Too Many Requests with Retry-After header upon limit exhaustion in [packages/core/vistarae_core/middleware/rate_limit.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/middleware/rate_limit.py)

**Checkpoint**: Rate limiting and tier caching operational; rate limit overages short-circuit before database allocations.

---

## Phase 6: User Story 4 — Database-Backed Idempotency Protection (Priority: P2)

**Goal**: Prevent duplicate mutations across `POST`, `PUT`, `PATCH`, `DELETE` using database-backed key locking in `idempotency_keys` with PENDING 409 conflict, COMPLETED replay (`X-Cache-Lookup: HIT`), and 24-hour cleanup.

**Independent Test**: Send concurrent mutating requests with the same `Idempotency-Key` asserting 409 Conflict; re-send completed request asserting exact cached body replay with header `X-Cache-Lookup: HIT`.

### Tests for User Story 4

- [x] T-033 [P] [US4] Write unit tests for Idempotency repository (get_or_create, complete, fail, cleanup_older_than) in [tests/unit/packages/core/test_idempotency_repo.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_idempotency_repo.py)
- [x] T-034 [P] [US4] Write unit tests for IdempotencyMiddleware (testing PENDING 409 conflict, COMPLETED replay with X-Cache-Lookup: HIT, and error FAILED transition) in [tests/unit/packages/core/test_idempotency_mw.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_idempotency_mw.py)
- [x] T-035 [P] [US4] Write integration test verifying rate limiting and idempotency middleware execution order under Starlette LIFO in [tests/integration/test_rate_limit_and_idempotency.py](file:///d:/Coding/Vistarae/tests/integration/test_rate_limit_and_idempotency.py)

### Implementation for User Story 4

- [x] T-036 [US4] [REQ-QUOTA-007] [REQ-QUOTA-008] [REQ-QUOTA-009] [REQ-QUOTA-010] [REQ-QUOTA-011] [REQ-QUOTA-012] Implement SQLAlchemy idempotency repository managing atomic key insertion, status updates (PENDING, COMPLETED, FAILED), cached payload storage, and 24-hour cleanup in [packages/core/vistarae_core/adapters/repositories/idempotency_repo.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/repositories/idempotency_repo.py)
- [x] T-037 [US4] [REQ-QUOTA-007] [REQ-QUOTA-008] [REQ-QUOTA-009] [REQ-QUOTA-010] [REQ-QUOTA-011] Implement IdempotencyMiddleware intercepting mutating requests with Idempotency-Key header, handling concurrent conflicts (409), caching successful responses, and replaying cached bodies with X-Cache-Lookup: HIT in [packages/core/vistarae_core/middleware/idempotency.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/middleware/idempotency.py)

**Checkpoint**: Idempotency protection fully active and verified against concurrent mutation conflicts and duplicate replays.

---

## Phase 7: User Story 5 — LLM Token Consumption Budgeting (Priority: P2)

**Goal**: Enforce Gemini Flash-Lite monthly token quota budgeting via pre-flight checks and atomic post-flight usage tracking.

**Independent Test**: Verify pre-flight token check rejects requests with RFC 7807 429 when `current_token_usage >= monthly_token_quota`; verify atomic increment adds tokens to `user_quotas.current_token_usage` and `user_metrics.total_tokens_consumed`.

### Tests for User Story 5

- [x] T-038 [P] [US5] Write unit tests for TokenBudgetService verifying pre-flight quota enforcement and atomic usage increments in [tests/unit/packages/core/test_token_budget_service.py](file:///d:/Coding/Vistarae/tests/unit/packages/core/test_token_budget_service.py)

### Implementation for User Story 5

- [x] T-039 [US5] [REQ-QUOTA-013] [REQ-QUOTA-014] Implement TokenBudgetService domain service executing pre-flight token budget verification (verifying current_token_usage < monthly_token_quota, rejecting with RFC 7807 429 Monthly Token Quota Exceeded) in [packages/core/vistarae_core/services/token_budget.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/services/token_budget.py)
- [x] T-040 [US5] [REQ-QUOTA-015] Implement atomic post-flight token increment in quota repository backing TokenBudgetService (incrementing user_quotas.current_token_usage and user_metrics.total_tokens_consumed by response.usage_metadata.total_token_count) in [packages/core/vistarae_core/adapters/repositories/quota_repo.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/adapters/repositories/quota_repo.py)

**Checkpoint**: Token budgeting pre-flight checks and atomic post-flight increments verified.

---

## Phase 8: User Story 6 — Administration Controls & Platform Telemetry (Priority: P3)

**Goal**: Deliver administrative governance endpoints under `/api/admin/*`, including platform telemetry metrics, tenant inspection, quota adjustment, user disablement/enablement, and RBAC enforcement.

**Independent Test**: Attempt administrative endpoint invocation with non-admin caller asserting RFC 7807 403 Forbidden; invoke with admin caller to read metrics, disable a target user, and assert that disabled user receives 403 on subsequent requests.

### Tests for User Story 6

- [x] T-041 [P] [US6] Write unit tests for Admin RBAC guard (verifying 403 Forbidden for non-admin callers) in [tests/unit/services/admin/test_admin_dependencies.py](file:///d:/Coding/Vistarae/tests/unit/services/admin/test_admin_dependencies.py)
- [x] T-042 [P] [US6] Write unit tests for AdminFunction telemetry, user management, and control routes in [tests/unit/services/admin/test_routes_metrics.py](file:///d:/Coding/Vistarae/tests/unit/services/admin/test_routes_metrics.py), [tests/unit/services/admin/test_routes_users.py](file:///d:/Coding/Vistarae/tests/unit/services/admin/test_routes_users.py), and [tests/unit/services/admin/test_routes_controls.py](file:///d:/Coding/Vistarae/tests/unit/services/admin/test_routes_controls.py)
- [x] T-043 [P] [US6] Write integration test for administrative governance and user disablement in [tests/integration/test_admin_governance.py](file:///d:/Coding/Vistarae/tests/integration/test_admin_governance.py)

### Implementation for User Story 6

- [x] T-044 [P] [US6] [REQ-ADMIN-007] [REQ-ADMIN-008] [REQ-ADMIN-009] [REQ-ADMIN-012] Define AdminMetricsResponse, AdminUserDetailResponse, UpdateUserQuotaRequest, QuotaDefaultsRequest, QuotaDefaultsResponse, and AdminMessageRequest schemas in [packages/core/vistarae_core/schemas/admin.py](file:///d:/Coding/Vistarae/packages/core/vistarae_core/schemas/admin.py)
- [x] T-045 [US6] [REQ-ADMIN-015] Implement Admin RBAC dependency checking caller tier == 'admin' and raising RFC 7807 403 Forbidden (https://errors.vistarae.com/admin-forbidden) in [services/admin/dependencies.py](file:///d:/Coding/Vistarae/services/admin/dependencies.py)
- [x] T-046 [US6] [REQ-ADMIN-007] Implement platform metrics aggregation route (GET /api/admin/metrics returning total_users, active_users, disabled_users, total_pois, total_tokens_consumed, tier_distribution) in [services/admin/routes/metrics.py](file:///d:/Coding/Vistarae/services/admin/routes/metrics.py)
- [x] T-047 [US6] [REQ-ADMIN-008] [REQ-ADMIN-009] [REQ-ADMIN-010] [REQ-ADMIN-011] Implement tenant inspection and governance routes (GET /api/admin/users/{user_id}, PATCH /api/admin/users/{user_id}/quota, POST /api/admin/users/{user_id}/disable, POST /api/admin/users/{user_id}/enable with in-memory tier cache invalidation) in [services/admin/routes/users.py](file:///d:/Coding/Vistarae/services/admin/routes/users.py)
- [x] T-048 [US6] [REQ-ADMIN-012] [REQ-ADMIN-013] [REQ-ADMIN-014] Implement admin control routes (PUT /api/admin/quotas/defaults, POST /api/admin/trace-injection/toggle, POST /api/admin/users/{user_id}/messages) in [services/admin/routes/controls.py](file:///d:/Coding/Vistarae/services/admin/routes/controls.py)
- [x] T-049 [US6] Assemble AdminFunction FastAPI application instance with lifespan connection management and serverless lambda_handler = Mangum(app, lifespan="off") in [services/admin/main.py](file:///d:/Coding/Vistarae/services/admin/main.py)

**Checkpoint**: Complete administrative suite, RBAC enforcement, and telemetry metrics operational.

---

## Phase 9: Polish, Gateway Assembly & Cross-Cutting Verification

**Purpose**: Assemble unified local development gateway, operational maintenance scripts, OpenAPI export, and execute quickstart validation suite.

- [x] T-050 [REQ-FOUND-012] [REQ-FOUND-013] Assemble and mount fully implemented services.user.app (/api/users) and services.admin.app (/api/admin) into unified local gateway, registering Starlette LIFO middleware stack (Idempotency registered first, RateLimit registered second, Telemetry outermost) and local CORS (http://localhost:5173) in [services/local_gateway.py](file:///d:/Coding/Vistarae/services/local_gateway.py) with unit test in [tests/unit/services/test_local_gateway.py](file:///d:/Coding/Vistarae/tests/unit/services/test_local_gateway.py)
- [x] T-051 [P] Implement OpenAPI contract export script generating openapi.json from UserFunction and AdminFunction apps in [scripts/export_openapi.py](file:///d:/Coding/Vistarae/scripts/export_openapi.py)
- [x] T-052 [P] Implement local database seeding script creating test users across low, high, and admin tiers (strictly checking STAGE == 'local') in [scripts/seed_local_db.py](file:///d:/Coding/Vistarae/scripts/seed_local_db.py)
- [x] T-053 [P] Implement DLQ redrive CLI script with required --env flag and interactive confirmation for non-local environments in [scripts/redrive_dlq.py](file:///d:/Coding/Vistarae/scripts/redrive_dlq.py)
- [x] T-054 Execute complete quickstart verification scenarios (dual-probe, local bypass, preference mutations, 61-request rate limit 429, idempotency 409 and replay, admin disablement, GDPR deletion) and assert 90% branch/line coverage via pytest --cov=packages/core --cov=services --cov-fail-under=90 per [specs/001-foundation-auth-quota/quickstart.md](file:///d:/Coding/Vistarae/specs/001-foundation-auth-quota/quickstart.md)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — starts immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **BLOCKS all user stories**.
- **Phase 3 (User Story 1 - Auth)**: Depends on Phase 2 completion — forms MVP foundation.
- **Phase 4 (User Story 2 - Preferences)**: Depends on Phase 3 (relies on authenticated user context).
- **Phase 5 (User Story 3 - Rate Limit)**: Depends on Phase 2 & Quota repository.
- **Phase 6 (User Story 4 - Idempotency)**: Depends on Phase 2 & Idempotency repository.
- **Phase 7 (User Story 5 - Token Budget)**: Depends on Phase 5 (extends Quota repository).
- **Phase 8 (User Story 6 - Admin)**: Depends on Phase 3 & Phase 5 (requires Admin tier check).
- **Phase 9 (Polish & Gateway)**: Depends on all user stories being complete.

### Parallel Execution Opportunities

- Tasks marked `[P]` within each phase can execute concurrently without file collisions.
- After Phase 2 completes, User Story 3 (Rate Limiting) and User Story 4 (Idempotency) can proceed in parallel with User Story 1 (Auth) if capacity permits.
- All unit test files mirror production modules 1:1 and can be authored in parallel with their corresponding implementation tasks.

---

## Implementation Strategy: MVP First

1. **Step 1: Setup & Foundation (Phases 1 & 2)**
   - Complete `docker-compose.yml`, `packages/core` layout, async database session, and Alembic migrations.
   - Run `alembic upgrade head` and verify health probes (`/health/live`, `/health/ready`).
2. **Step 2: MVP Delivery (Phase 3 — User Story 1)**
   - Implement stage-aware auth dependency and mock bypass (`X-Mock-User-Id`).
   - Validate unauthenticated rejection and GDPR cascade deletion.
3. **Step 3: User Preferences & Governance (Phases 4, 5, 6, 7)**
   - Implement sub-domain preferences (`/api/users/me/preferences/*`).
   - Mount rolling-window rate limiting, tier caching, idempotency, and token budgeting.
4. **Step 4: Administration & Gateway Unification (Phases 8 & 9)**
   - Implement AdminFunction routes and RBAC guards.
   - Mount all services in `services/local_gateway.py`.
   - Run end-to-end quickstart validation and coverage audit ($\ge 90\%$).

---

## Phase 10: Convergence

**Purpose**: Remediate gaps and inconsistencies identified during convergence assessment between spec, constitution, and codebase.

- [x] T-055 CRITICAL: Refactor /health/ready database failure response in services/local_gateway.py to return RFC 7807 ProblemDetails JSON with application/problem+json media type per REQ-FOUND-014 and Constitution Principle 5 (contradicts)
- [x] T-056 Implement Cognito auth lifecycle methods in CognitoIdentityProvider and expose /api/auth/\* routes for register, confirm-signup, login, forgot-password, reset-password, and logout per REQ-AUTH-001..006 (missing)
- [x] T-057 Implement 24-hour idempotency key retention cleanup CLI script in scripts/cleanup_idempotency.py per REQ-QUOTA-012 (partial)
