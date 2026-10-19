# Research & Architectural Decisions: 001-foundation-auth-quota

**Feature**: Foundation, Authentication, Quotas & Administration  
**Date**: 2026-10-18  
**Status**: APPROVED  

---

## 1. Monorepo Architecture & Workspace Package Management

### Decision
Structure the Vistarae repository as a Python monorepo using a root workspace `pyproject.toml` and an editable domain package `packages/core`. All shared business logic, domain entities, value objects, domain exceptions, repository interfaces (`typing.Protocol`), SQLAlchemy ORM models, and middleware are isolated inside `packages/core`. Individual microservices (`services/user`, `services/admin`) depend on `packages/core` installed in editable mode (`pip install -e ./packages/core`).

### Rationale
- **Constitution Principle 2 Compliance**: Isolates shared domain models and port interfaces from transport layers.
- **Dependency Inversion**: Domain logic does not depend on cloud providers, AWS Lambda runtimes, or database drivers.
- **Fast Developer Ergonomics**: Changes in `packages/core` are immediately reflected across `services/user`, `services/admin`, and tests without packaging or layer rebuilds.

### Alternatives Considered
- *Single monolithic package*: Rejected because it entangles routes and prevents granular serverless packaging for AWS Lambda.
- *Separate repositories*: Rejected due to high synchronization overhead, versioning friction, and complex local testing workflows.

---

## 2. Database Engine & Connection Pooling (Neon PgBouncer vs. Local)

### Decision
Use SQLAlchemy 2.0 Pure Async with `asyncpg`. Dynamically configure the connection pool based on environment:
- **Local (`STAGE == "local"`)**: `create_async_engine` configured with `QueuePool(pool_size=5, max_overflow=5)`.
- **Cloud / Serverless (`STAGE != "local"`)**: `create_async_engine` configured with `NullPool` targeting Neon's pooled endpoint (`-pooler`) with `connect_args={"statement_cache_size": 0}` to disable prepared statement caching.
- **Cold-Start Resilience**: Implement a 3-attempt exponential backoff retry loop (500ms, 1500ms, 3000ms) on database engine initialization to absorb Neon compute scale-to-zero wakeups.

### Rationale
- **Constitution Principle 3 Compliance**: Prevents asyncpg prepared statement collisions across transaction-mode PgBouncer connections.
- **Scale-to-Zero Preservation**: `NullPool` prevents serverless Lambdas from leaking persistent connections to Neon.
- **Resilience**: Neon serverless database cold starts can take 1–2 seconds when resuming from suspended state; the retry loop prevents 500 errors during wakeups.

### Alternatives Considered
- *Prepared statement caching enabled*: Rejected because PgBouncer in transaction pooling mode routes consecutive queries to different backend connections, causing `prepared statement does not exist` errors.
- *Persistent connection pool in Lambda*: Rejected because idle connections keep Neon compute awake, violating the 190h/mo free tier limit.

---

## 3. Database Schema Migrations with Alembic

### Decision
Maintain all schema migrations exclusively inside `db/migrations/` managed by Alembic. The migration environment (`env.py`) executes using an async engine connection. All migration scripts must implement a fully reversible `downgrade()` function and use check constraints or Python `StrEnum` backed by PostgreSQL `VARCHAR(n)` columns rather than native PostgreSQL `ENUM` types.

### Rationale
- **Constitution Principle 4 Compliance**: Guarantees zero-risk rollbacks and database portability.
- **Non-blocking Schema Evolution**: PostgreSQL native `ENUM` types require exclusive table locks during modifications and create rollback complexities. `VARCHAR` with check constraints allows non-blocking schema updates.

### Alternatives Considered
- *Supabase CLI migrations*: Rejected because the project architecture transitioned from Supabase-specific tooling to pure PostgreSQL 16 + PostGIS on Neon/Docker.
- *Manual SQL migration scripts*: Rejected because it lacks schema version tracking, automated downgrade capabilities, and automated CI drift checks (`alembic check`).

---

## 4. Identity Management: AWS Cognito with Stage-Aware Local Bypass

### Decision
Integrate AWS Cognito User Pool for user registration, email verification, authentication, and password management.
- In production (`STAGE != "local"`), the authentication dependency validates incoming Bearer tokens against the Cognito JWKS endpoint, checking signature, issuer, audience, and expiration.
- In local development (`STAGE == "local"`), the authentication dependency permits local stage bypass via the `X-Mock-User-Id` header (accepting a valid UUID) to populate the `CurrentUser` context without external network calls.
- In non-local environments, the `X-Mock-User-Id` header is strictly ignored and rejected if unauthenticated.
- Account deletion executes GDPR-compliant cascading: AWS Cognito `AdminDeleteUser` is called first, followed by PostgreSQL `DELETE FROM users WHERE id = :user_id` (triggering `ON DELETE CASCADE` across all tenant child tables).

### Rationale
- **Constitution Principle 1 & Section 4.2 Compliance**: Ensures seamless, offline-first local development while maintaining zero trust in production.
- **GDPR Compliance**: Guarantees that deleting an account completely purges user identity from Cognito and all relational/spatial data from PostgreSQL.

### Alternatives Considered
- *Local Cognito Docker emulator (e.g., LocalStack Cognito)*: Rejected due to significant memory overhead, slow boot times, and maintenance complexity.
- *Custom JWT auth system*: Rejected because it introduces unnecessary security maintenance overhead; Cognito free tier provides 50,000 monthly active users at zero cost.

---

## 5. Rate Limiting & Tier Caching Strategy

### Decision
Implement rate limiting via Starlette middleware operating on a 1-minute rolling bucket stored in `user_quotas` (`request_count`, `window_start_at`).
- **Low Tier**: 60 requests per 1-minute window.
- **High / Admin Tier**: 300 requests per 1-minute window.
- **In-Memory Cache**: Maintain a thread-safe, 60-second TTL in-memory dictionary caching `(tier, is_disabled)` keyed by `user_id`.
- **429 Response**: When the limit is exceeded, immediately return RFC 7807 `429 Too Many Requests` with a `Retry-After` header indicating remaining window seconds.

### Rationale
- **Constitution Principle 6 Compliance**: Middleware order ensures `RateLimitMiddleware` executes before `IdempotencyMiddleware`, preventing rate-limited requests from allocating idempotency database records.
- **Low DB Overhead**: In-memory caching eliminates redundant database queries for user tier and status on every request.
- **Zero Cost**: Storing window state in PostgreSQL eliminates the need for an external Redis cluster.

### Alternatives Considered
- *Redis Token Bucket*: Rejected because maintaining a Redis instance incurs cloud infrastructure costs, violating the Zero-Cost Architecture principle.
- *Pure in-memory rate limiting*: Rejected because serverless AWS Lambda containers do not share memory; state must persist in the database.

---

## 6. Idempotency Protection Protocol

### Decision
Protect all mutating operations (`POST`, `PUT`, `PATCH`, `DELETE`) carrying an `Idempotency-Key` header via database-backed tracking in `idempotency_keys` with a unique constraint on `(user_id, idempotency_key)`.
- **Lifecycle**:
  - `PENDING`: Request received and processing begins. Concurrent requests with the same key receive RFC 7807 `409 Conflict`.
  - `COMPLETED`: Downstream execution finishes successfully. Stores HTTP status code and JSON response body. Subsequent identical requests replay this cached response with header `X-Cache-Lookup: HIT`.
  - `FAILED`: Unhandled exceptions mark the record as failed, permitting client retries.
- **Retention**: Periodic retention cleanup purges records older than 24 hours (`created_at < NOW() - INTERVAL '24 hours'`).

### Rationale
- **Constitution Principle 6 & REQ-QUOTA-007..012 Compliance**: Prevents duplicate resource creation caused by extension network retries, unstable mobile connections, or duplicate clicks.
- **RFC Compliance**: Cleanly separates conflicting in-flight operations (409) from completed idempotent replays (cached status + payload).

### Alternatives Considered
- *Cache-only idempotency (Memcached/Redis)*: Rejected to avoid external infrastructure costs and potential eviction before request completion.
- *Client-side debounce only*: Rejected because network partitions and browser retries bypass client-side guards.

---

## 7. Telemetry & Message Logging Protocol

### Decision
Implement a custom `TelemetryMiddleware` extracting W3C `traceparent` and proprietary correlation headers (`X-Source`, `X-Destination`).
- When `STAGE == "local"`, cross-boundary logs emit directional message tags:
  - Inbound request received: `MSG: -->|`
  - Outbound 2XX response: `MSG: <--|`
  - Outbound 4XX/5XX error response: `MSG: <~~|`
  - External outbound dispatch: `MSG: |-->`
  - External outbound response: `MSG: |<--`
- In production (`STAGE != "local"`), logs are emitted as structured JSON without directional tags, forwarding trace context to AWS X-Ray and OpenTelemetry.

### Rationale
- **Constitution Principle 7 Compliance**: Provides instant visual clarity during local terminal debugging while delivering machine-parseable structured logs in cloud environments.

### Alternatives Considered
- *Standard Uvicorn access logger*: Rejected because it lacks W3C transaction correlation, tenant context, and required directional tags.
