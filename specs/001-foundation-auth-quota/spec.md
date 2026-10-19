# Specification: Phase 1 — Foundation, Authentication, Quotas & Administration
**Feature Identifier:** `001-foundation-auth-quota`  
**Status:** `DRAFT` | **Version:** `1.0.0` | **Date:** `2026-10-18`  
**Target Systems:** Vistarae Backend (FastAPI), Local Infrastructure (Docker Compose, ElasticMQ, PostGIS), Database (PostgreSQL 16 / Alembic), Identity (AWS Cognito)

---

## 1. Executive Summary & Context

Phase 1 (`001-foundation-auth-quota`) establishes the architectural and security backbone for the Vistarae platform. It provisions local infrastructure for offline-first development, creates core multi-tenant relational and spatial database schemas via Alembic, establishes identity management with AWS Cognito (supporting seamless local stage bypass), and introduces zero-overhead runtime governance via rolling-window rate limiting, token consumption budgeting, idempotency protection, and administrative controls.

### 1.1 Scope Boundaries
1. **Local Infrastructure (`docker-compose.yml`)**:
   - `postgis/postgis:16-3.4` container with persistent named volume `postgis_data:/var/lib/postgresql/data`.
   - `softwaremill/elasticmq-native:latest` container mounting `docker/elasticmq.conf` pre-configuring local SQS emulation for `vistarae-ingest-local` (with DLQ) and `vistarae-ingest-dlq-local`.
2. **Core Schemas & Alembic Migration**:
   - PostgreSQL extensions: `postgis`, `btree_gist`, and `vector`.
   - Tables: `users`, `user_preferences`, `user_metrics`, `user_quotas`, `idempotency_keys`.
   - Mandatory `ON DELETE CASCADE` on all tenant foreign keys referencing `users(id)`.
   - Preference sub-domains: Account/UI, POI Mode, and Planner Mode.
3. **Identity Hook & Auth Dependency**:
   - AWS Cognito User Pool integration: Sign-up (email code verification), sign-in, password reset, and logout.
   - Stage-aware local mocking via `X-Mock-User-Id` header when `APP_ENV == 'local'`.
   - GDPR-compliant account deletion: Cognito `AdminDeleteUser` followed by PostgreSQL cascade deletion.
   - Deletion/disablement guard: immediate RFC 7807 401/403 for orphaned or disabled JWTs.
4. **Middleware, Token Budgeting & Services**:
   - Rate-limiting middleware: 1-minute rolling bucket in `user_quotas` (Low: 60 req/min, High/Admin: 300 req/min) with 60-second in-memory tier cache and RFC 7807 429 response with `Retry-After`.
   - Idempotency middleware: Mutating operations protected by `(user_id, idempotency_key)`, handling `PENDING` (409 Conflict), `COMPLETED` (replay cached response with `X-Cache-Lookup: HIT`), and 24-hour cleanup.
   - Token budgeting: Pre-flight limit verification against Gemini Flash-Lite monthly quota and atomic post-flight usage tracking.
   - `UserFunction` (`/api/users/*`) and `AdminFunction` (`/api/admin/*`).
   - Dual-Probes: `/health/live` (zero DB I/O for ASGI alive checks) and `/health/ready` (`SELECT 1` for on-demand/CI checks to protect Neon's 190h/mo scale-to-zero quota).

---

## 2. Architecture & Service Topology

```mermaid
flowchart TD
    Client[Chrome Extension / Web Client] -->|W3C Trace & Bearer Token| Traefik[FastAPI Middleware Pipeline]
    
    subgraph Middleware Pipeline
        MW_Trace[Telemetry Middleware<br/>W3C Context & Msg Tags]
        MW_Auth[Auth Dependency<br/>Cognito JWKS / X-Mock-User-Id]
        MW_Rate[Rate-Limiting Middleware<br/>60s In-Memory Cache + DB Rolling Window]
        MW_Idemp[Idempotency Middleware<br/>(user_id, key) Cache & Conflict Check]
    end

    Traefik --> MW_Trace --> MW_Auth --> MW_Rate --> MW_Idemp

    subgraph Service Endpoints
        UserSvc[UserFunction<br/>/api/users/*]
        AdminSvc[AdminFunction<br/>/api/admin/*]
        HealthSvc[Dual-Probes<br/>/health/live & /health/ready]
        IngestSvc[Ingestion / POI Routes<br/>TokenBudget Check]
    end

    MW_Idemp --> UserSvc
    MW_Idemp --> AdminSvc
    MW_Idemp --> IngestSvc
    Traefik -.-> HealthSvc

    subgraph Infrastructure
        PG[(PostgreSQL 16 + PostGIS<br/>btree_gist, vector)]
        Cognito[AWS Cognito User Pool]
        EMQ[ElasticMQ Native<br/>SQS Emulation]
    end

    UserSvc -->|AdminDeleteUser| Cognito
    UserSvc -->|CASCADE Delete| PG
    AdminSvc -->|Metrics & Quotas| PG
    IngestSvc -->|Atomic Token Incr| PG
    IngestSvc -->|Dispatch Message| EMQ
    HealthSvc -->|SELECT 1 on ready only| PG
```

---

## 3. Data Dictionary & Schemas

### 3.1 Database Extensions
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "vector";
```

### 3.2 Relational DDL Specifications

```sql
-- 1. Users Table (Core tenant anchor)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cognito_sub VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL
);
CREATE INDEX idx_users_cognito_sub ON users(cognito_sub);
CREATE INDEX idx_users_email ON users(email);

-- 2. User Preferences Table (Partitioned into sub-domains)
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    -- Account / UI Preferences
    theme VARCHAR(16) DEFAULT 'system' NOT NULL, -- 'light', 'dark', 'system'
    email_notifications_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    push_notifications_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    marketing_emails_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- POI Mode Preferences
    clustering_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    clustering_radius_meters INT DEFAULT 50 NOT NULL,
    default_map_layer VARCHAR(32) DEFAULT 'standard' NOT NULL,
    geoproximity_scope_km FLOAT DEFAULT 25.0 NOT NULL,
    pin_color_presets JSONB DEFAULT '{"favorite": "#E11D48", "dream": "#8B5CF6", "visited": "#10B981", "default": "#3B82F6"}'::jsonb NOT NULL,
    
    -- Planner Mode Preferences
    pacing VARCHAR(16) DEFAULT 'moderate' NOT NULL, -- 'relaxed', 'moderate', 'fast_paced'
    meal_intervals_hours FLOAT DEFAULT 4.0 NOT NULL,
    lunch_packing_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    transit_speed_mode VARCHAR(16) DEFAULT 'walking' NOT NULL, -- 'walking', 'bicycling', 'transit', 'driving'
    daily_activity_hour_cap FLOAT DEFAULT 8.0 NOT NULL,
    preferred_currency VARCHAR(3) DEFAULT 'USD' NOT NULL,
    
    created_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL
);

-- 3. User Metrics Table (Aggregate reporting)
CREATE TABLE user_metrics (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    poi_count INT DEFAULT 0 NOT NULL,
    total_tokens_consumed INT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL
);

-- 4. User Quotas Table (Governance & rolling rate limiting)
CREATE TABLE user_quotas (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    monthly_token_quota INT DEFAULT 50000 NOT NULL,
    current_token_usage INT DEFAULT 0 NOT NULL,
    tier VARCHAR(16) DEFAULT 'low' NOT NULL, -- 'low', 'high', 'admin'
    request_count INT DEFAULT 0 NOT NULL,
    window_start_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL,
    is_disabled BOOLEAN DEFAULT FALSE NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL
);
CREATE INDEX idx_user_quotas_tier ON user_quotas(tier);

-- 5. Idempotency Keys Table (Safe mutations & deduplication)
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL, -- 'PENDING', 'COMPLETED', 'FAILED'
    response_code INT,
    response_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp() NOT NULL,
    CONSTRAINT uq_user_idempotency_key UNIQUE (user_id, idempotency_key)
);
CREATE INDEX idx_idempotency_keys_created_at ON idempotency_keys(created_at);
```

### 3.3 ElasticMQ Configuration (`docker/elasticmq.conf`)
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

---

## 4. Strict EARS Requirements Specification

### 4.1 REQ-FOUND-xxx: Local Infrastructure & Foundation

- **REQ-FOUND-001 (Ubiquitous):** The Vistarae Local Runtime shall run PostgreSQL 16 with PostGIS 3.4 using the Docker image `postgis/postgis:16-3.4`.
- **REQ-FOUND-002 (Ubiquitous):** The Vistarae Local Runtime shall persist database state to the named Docker volume `postgis_data:/var/lib/postgresql/data`.
- **REQ-FOUND-003 (Ubiquitous):** The Vistarae Local Runtime shall run ElasticMQ using the Docker image `softwaremill/elasticmq-native:latest` with the configuration mounted from `docker/elasticmq.conf`.
- **REQ-FOUND-004 (Event-driven):** WHEN the ElasticMQ container starts, the Vistarae Local Runtime shall pre-create the `vistarae-ingest-local` queue with a visibility timeout of 180 seconds, a receive message wait time of 20 seconds, and a dead letters queue pointing to `vistarae-ingest-dlq-local` with `maxReceiveCount = 3`.
- **REQ-FOUND-005 (Event-driven):** WHEN the ElasticMQ container starts, the Vistarae Local Runtime shall pre-create the dead letter queue `vistarae-ingest-dlq-local` with a visibility timeout of 180 seconds.
- **REQ-FOUND-006 (Ubiquitous):** The Vistarae Database Engine shall activate the `postgis`, `btree_gist`, and `vector` extensions via Alembic migration scripts.
- **REQ-FOUND-007 (Ubiquitous):** The Vistarae Database Engine shall enforce `ON DELETE CASCADE` on all foreign key constraints referencing `users(id)` across all tenant tables (`user_preferences`, `user_metrics`, `user_quotas`, `idempotency_keys`, `pois`, `lists`, `user_tags`, `scanned_paths`).
- **REQ-FOUND-008 (Ubiquitous):** The Vistarae Database Engine shall structure `user_preferences` into Account/UI (`theme`, notification flags), POI Mode (`clustering_enabled`, `clustering_radius_meters`, `default_map_layer`, `geoproximity_scope_km`, `pin_color_presets`), and Planner Mode (`pacing`, `meal_intervals_hours`, `lunch_packing_enabled`, `transit_speed_mode`, `daily_activity_hour_cap`, `preferred_currency`).
- **REQ-FOUND-009 (Ubiquitous):** The Vistarae Database Engine shall record aggregate user metrics in `user_metrics` (`user_id`, `poi_count`, `total_tokens_consumed`, `updated_at`).
- **REQ-FOUND-010 (Ubiquitous):** The Vistarae Database Engine shall maintain quota allocations in `user_quotas` (`user_id`, `monthly_token_quota` default 50000, `current_token_usage` default 0, `tier` default 'low', `request_count` default 0, `window_start_at` default `NOW()`, `is_disabled` default `FALSE`, `updated_at` default `NOW()`).
- **REQ-FOUND-011 (Ubiquitous):** The Vistarae Database Engine shall record idempotency records in `idempotency_keys` with a unique constraint on `(user_id, idempotency_key)` and status tracking (`PENDING`, `COMPLETED`, `FAILED`).
- **REQ-FOUND-012 (Event-driven):** WHEN an incoming HTTP GET request targets `/health/live`, the Vistarae Health Probe Router shall return HTTP 200 OK (`{"status": "alive"}`) without initiating any database operations or connection pool checks.
- **REQ-FOUND-013 (Event-driven):** WHEN an incoming HTTP GET request targets `/health/ready`, the Vistarae Health Probe Router shall execute `SELECT 1` on the active database session and return HTTP 200 OK (`{"status": "ready"}`) if the query completes successfully.
- **REQ-FOUND-014 (Exception):** IF the database connection fails or times out during a `/health/ready` check, THEN the Vistarae Health Probe Router shall return an RFC 7807 HTTP 503 Service Unavailable response (`{"type": "https://errors.vistarae.com/database-unreachable", "title": "Database Unreachable", "status": 503}`).
- **REQ-FOUND-015 (Ubiquitous):** The Vistarae Health Probe Router shall restrict `/health/ready` execution exclusively to CI/CD workflows and explicit manual readiness inspections to preserve serverless database scale-to-zero operational budgets.

---

### 4.2 REQ-AUTH-xxx: Identity Hook & Authentication Dependency

- **REQ-AUTH-001 (Event-driven):** WHEN an unauthenticated user submits registration details to `/api/auth/register`, the Vistarae Identity Service shall register the user in AWS Cognito and trigger the dispatch of an email verification code.
- **REQ-AUTH-002 (Event-driven):** WHEN a user submits a valid email verification code to `/api/auth/confirm-signup`, the Vistarae Identity Service shall confirm the account in AWS Cognito, insert a corresponding record into the local `users` table, and initialize default rows in `user_preferences`, `user_metrics`, and `user_quotas`.
- **REQ-AUTH-003 (Event-driven):** WHEN a user submits valid credentials to `/api/auth/login`, the Vistarae Identity Service shall authenticate against AWS Cognito and return standard JWT bearer tokens (`access_token`, `id_token`, `refresh_token`).
- **REQ-AUTH-004 (Event-driven):** WHEN a user submits an email to `/api/auth/forgot-password`, the Vistarae Identity Service shall initiate an AWS Cognito password reset flow and dispatch a confirmation code.
- **REQ-AUTH-005 (Event-driven):** WHEN a user submits a valid reset code and new password to `/api/auth/reset-password`, the Vistarae Identity Service shall confirm the password reset in AWS Cognito.
- **REQ-AUTH-006 (Event-driven):** WHEN an authenticated user submits a logout request to `/api/auth/logout`, the Vistarae Identity Service shall invalidate user tokens via AWS Cognito `GlobalSignOut`.
- **REQ-AUTH-007 (Optional Feature / Event-driven):** WHERE `APP_ENV == 'local'`, WHEN an incoming request contains the `X-Mock-User-Id` header with a valid UUID format, the Vistarae Auth Dependency shall bypass Cognito JWKS verification and resolve the mock user context directly.
- **REQ-AUTH-008 (Exception):** WHERE `APP_ENV != 'local'`, IF an incoming request contains the `X-Mock-User-Id` header, THEN the Vistarae Auth Dependency shall ignore the header and enforce standard Cognito JWT validation.
- **REQ-AUTH-009 (Event-driven):** WHEN an authenticated user submits a deletion request to `DELETE /api/users/me`, the Vistarae Identity Service shall call AWS Cognito `AdminDeleteUser` without prior call to `AdminUserGlobalSignOut`.
- **REQ-AUTH-010 (Event-driven):** WHEN AWS Cognito `AdminDeleteUser` succeeds, the Vistarae User Service shall execute `DELETE FROM users WHERE id = :user_id`.
- **REQ-AUTH-011 (Exception):** IF an incoming JWT contains a `sub` claim that does not exist in the `users` table, THEN the Vistarae Auth Dependency shall reject the request with an RFC 7807 HTTP 401 Unauthorized response (`{"type": "https://errors.vistarae.com/user-not-found", "title": "Account Not Found", "status": 401}`).
- **REQ-AUTH-012 (State-driven):** WHILE `is_disabled` is `TRUE` in `user_quotas`, the Vistarae Auth Dependency shall reject all authenticated requests from that user with an RFC 7807 HTTP 403 Forbidden response (`{"type": "https://errors.vistarae.com/account-disabled", "title": "Account Disabled", "status": 403}`).

---

### 4.3 REQ-QUOTA-xxx: Rate-Limiting, Idempotency & Token Budgeting

- **REQ-QUOTA-001 (Ubiquitous):** The Vistarae Rate-Limiting Middleware shall track request rates using a 1-minute rolling bucket stored in `user_quotas` (`request_count`, `window_start_at`).
- **REQ-QUOTA-002 (State-driven):** WHILE a user belongs to tier `'low'`, the Vistarae Rate-Limiting Middleware shall enforce a maximum limit of 60 requests per 1-minute rolling window.
- **REQ-QUOTA-003 (State-driven):** WHILE a user belongs to tier `'high'` or `'admin'`, the Vistarae Rate-Limiting Middleware shall enforce a maximum limit of 300 requests per 1-minute rolling window.
- **REQ-QUOTA-004 (Ubiquitous):** The Vistarae Rate-Limiting Middleware shall maintain an in-memory cache of user tiers and disabled flags with a 60-second time-to-live (TTL) to avoid redundant database reads.
- **REQ-QUOTA-005 (Event-driven):** WHEN the current timestamp exceeds `window_start_at + 60 seconds`, the Vistarae Rate-Limiting Middleware shall reset `request_count` to 1 and update `window_start_at` to the current timestamp.
- **REQ-QUOTA-006 (Exception):** IF a user exceeds their tier request limit within the active 1-minute window, THEN the Vistarae Rate-Limiting Middleware shall return an RFC 7807 HTTP 429 Too Many Requests response with a `Retry-After` header set to the remaining seconds of the current window.
- **REQ-QUOTA-007 (Optional Feature / Exception):** WHERE an incoming mutating request (`POST`, `PUT`, `PATCH`, `DELETE`) includes an `Idempotency-Key` header, IF a record matching `(user_id, idempotency_key)` exists with status `'PENDING'`, THEN the Vistarae Idempotency Middleware shall return an RFC 7807 HTTP 409 Conflict response (`{"type": "https://errors.vistarae.com/concurrent-mutation", "title": "Concurrent Request In Progress", "status": 409}`).
- **REQ-QUOTA-008 (Optional Feature / Event-driven):** WHERE an incoming mutating request includes an `Idempotency-Key` header, IF a record matching `(user_id, idempotency_key)` exists with status `'COMPLETED'`, THEN the Vistarae Idempotency Middleware shall short-circuit request execution and return the cached `response_payload` and `response_code` accompanied by header `X-Cache-Lookup: HIT`.
- **REQ-QUOTA-009 (Optional Feature / Event-driven):** WHERE an incoming mutating request includes an `Idempotency-Key` header, IF no matching record exists in `idempotency_keys`, THEN the Vistarae Idempotency Middleware shall insert a record with status `'PENDING'` prior to routing to downstream handlers.
- **REQ-QUOTA-010 (Optional Feature / Event-driven):** WHEN downstream execution completes successfully for a request tracked by `Idempotency-Key`, the Vistarae Idempotency Middleware shall update the record status to `'COMPLETED'`, recording the HTTP status code and JSON response body.
- **REQ-QUOTA-011 (Optional Feature / Exception):** IF downstream execution raises an unhandled exception for a request tracked by `Idempotency-Key`, THEN the Vistarae Idempotency Middleware shall update the record status to `'FAILED'` to permit subsequent client retries.
- **REQ-QUOTA-012 (Ubiquitous):** The Vistarae Idempotency Service shall execute scheduled retention cleanup jobs to delete all rows from `idempotency_keys` where `created_at < NOW() - INTERVAL '24 hours'`.
- **REQ-QUOTA-013 (Event-driven):** WHEN an LLM extraction request is initiated, the Vistarae Token Budgeting Service shall verify that `current_token_usage < monthly_token_quota` in `user_quotas`.
- **REQ-QUOTA-014 (Exception):** IF `current_token_usage >= monthly_token_quota` prior to an LLM extraction request, THEN the Vistarae Token Budgeting Service shall reject the request with an RFC 7807 HTTP 429 Too Many Requests response (`{"type": "https://errors.vistarae.com/token-quota-exceeded", "title": "Monthly Token Quota Exceeded", "status": 429}`).
- **REQ-QUOTA-015 (Event-driven):** WHEN an LLM extraction completes successfully, the Vistarae Token Budgeting Service shall atomically increment `user_quotas.current_token_usage` and `user_metrics.total_tokens_consumed` by the returned `response.usage_metadata.total_token_count`.

---

### 4.4 REQ-ADMIN-xxx: Administrative Controls & User Operations

- **REQ-ADMIN-001 (Event-driven):** WHEN an authenticated user requests `GET /api/users/me`, the Vistarae User Service shall return the user's profile, combined preferences, metrics, and quota utilization.
- **REQ-ADMIN-002 (Event-driven):** WHEN an authenticated user requests `PATCH /api/users/me`, the Vistarae User Service shall update the user's profile details (`full_name`) and return the updated user representation.
- **REQ-ADMIN-003 (Event-driven):** WHEN an authenticated user requests `GET /api/users/me/preferences`, the Vistarae User Service shall return all sub-domain preferences (Account/UI, POI Mode, Planner Mode).
- **REQ-ADMIN-004 (Event-driven):** WHEN an authenticated user requests `PATCH /api/users/me/preferences/ui`, the Vistarae User Service shall validate and update Account/UI preferences (`theme`, `email_notifications_enabled`, `push_notifications_enabled`, `marketing_emails_enabled`).
- **REQ-ADMIN-005 (Event-driven):** WHEN an authenticated user requests `PATCH /api/users/me/preferences/poi`, the Vistarae User Service shall validate and update POI Mode preferences (`clustering_enabled`, `clustering_radius_meters`, `default_map_layer`, `geoproximity_scope_km`, `pin_color_presets`).
- **REQ-ADMIN-006 (Event-driven):** WHEN an authenticated user requests `PATCH /api/users/me/preferences/planner`, the Vistarae User Service shall validate and update Planner Mode preferences (`pacing`, `meal_intervals_hours`, `lunch_packing_enabled`, `transit_speed_mode`, `daily_activity_hour_cap`, `preferred_currency`).
- **REQ-ADMIN-007 (Event-driven):** WHEN an administrator requests `GET /api/admin/metrics`, the Vistarae Admin Service shall aggregate and return platform telemetry insights (`total_users`, `active_users`, `disabled_users`, `total_pois`, `total_tokens_consumed`, `tier_distribution`).
- **REQ-ADMIN-008 (Event-driven):** WHEN an administrator requests `GET /api/admin/users/{user_id}`, the Vistarae Admin Service shall return the targeted user's complete operational status, quotas, preferences, and consumption metrics.
- **REQ-ADMIN-009 (Event-driven):** WHEN an administrator requests `PATCH /api/admin/users/{user_id}/quota`, the Vistarae Admin Service shall update `monthly_token_quota` or `tier` in `user_quotas` and invalidate the targeted user's in-memory tier cache entry.
- **REQ-ADMIN-010 (Event-driven):** WHEN an administrator requests `POST /api/admin/users/{user_id}/disable`, the Vistarae Admin Service shall set `is_disabled = TRUE` in `user_quotas` and invalidate the user's in-memory tier cache entry.
- **REQ-ADMIN-011 (Event-driven):** WHEN an administrator requests `POST /api/admin/users/{user_id}/enable`, the Vistarae Admin Service shall set `is_disabled = FALSE` in `user_quotas` and invalidate the user's in-memory tier cache entry.
- **REQ-ADMIN-012 (Event-driven):** WHEN an administrator requests `PUT /api/admin/quotas/defaults`, the Vistarae Admin Service shall update the platform default quota settings applied during user provisioning.
- **REQ-ADMIN-013 (Event-driven):** WHEN an administrator requests `POST /api/admin/trace-injection/toggle`, the Vistarae Admin Service shall toggle the global admin client W3C trace injection override flag.
- **REQ-ADMIN-014 (Event-driven):** WHEN an administrator requests `POST /api/admin/users/{user_id}/messages`, the Vistarae Admin Service shall record and queue an administrative dispatch message targeting the specified user.
- **REQ-ADMIN-015 (Exception):** IF a user whose tier is not `'admin'` attempts to invoke any endpoint under `/api/admin/*`, THEN the Vistarae Auth Dependency shall reject the request with an RFC 7807 HTTP 403 Forbidden response (`{"type": "https://errors.vistarae.com/admin-forbidden", "title": "Administrative Access Required", "status": 403}`).

---

## 5. API Contracts & Endpoint Specifications

### 5.1 RFC 7807 Standard Error Envelope
All error responses from middleware, dependencies, and route handlers shall strictly adhere to RFC 7807 (`application/problem+json`):
```json
{
  "type": "https://errors.vistarae.com/rate-limit-exceeded",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit of 60 requests per minute exceeded. Try again in 24 seconds.",
  "instance": "/api/users/me/preferences/poi"
}
```

### 5.2 UserFunction Routes (`/api/users/*`)

| Method | Endpoint | Description | Request Body | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/users/me` | Fetch active user profile, quotas & metrics | None | `200 OK` (`UserProfileResponse`) |
| `PATCH` | `/api/users/me` | Update full name | `{"full_name": "string"}` | `200 OK` (`UserResponse`) |
| `GET` | `/api/users/me/preferences` | Fetch all user preferences | None | `200 OK` (`UserPreferencesResponse`) |
| `PATCH` | `/api/users/me/preferences/ui` | Update Account/UI preferences | `UpdateUIPreferencesRequest` | `200 OK` (`UIPreferencesResponse`) |
| `PATCH` | `/api/users/me/preferences/poi` | Update POI Mode preferences | `UpdatePOIPreferencesRequest` | `200 OK` (`POIPreferencesResponse`) |
| `PATCH` | `/api/users/me/preferences/planner` | Update Planner Mode preferences | `UpdatePlannerPreferencesRequest` | `200 OK` (`PlannerPreferencesResponse`) |
| `DELETE` | `/api/users/me` | Permanent account deletion | None | `204 No Content` |

### 5.3 AdminFunction Routes (`/api/admin/*`)

| Method | Endpoint | Description | Request Body | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/metrics` | Platform telemetry and usage insights | None | `200 OK` (`AdminMetricsResponse`) |
| `GET` | `/api/admin/users/{user_id}` | Detailed tenant inspection | None | `200 OK` (`AdminUserDetailResponse`) |
| `PATCH` | `/api/admin/users/{user_id}/quota` | Adjust user quota or tier | `{"monthly_token_quota": 100000, "tier": "high"}` | `200 OK` (`UserQuotaResponse`) |
| `POST` | `/api/admin/users/{user_id}/disable` | Administratively disable user | None | `200 OK` (`{"status": "disabled"}`) |
| `POST` | `/api/admin/users/{user_id}/enable` | Re-enable disabled user | None | `200 OK` (`{"status": "enabled"}`) |
| `PUT` | `/api/admin/quotas/defaults` | Update global default quotas | `{"default_token_quota": 50000, "default_tier": "low"}` | `200 OK` (`QuotaDefaultsResponse`) |
| `POST` | `/api/admin/trace-injection/toggle` | Toggle trace injection debug flag | None | `200 OK` (`{"trace_injection_enabled": bool}`) |
| `POST` | `/api/admin/users/{user_id}/messages` | Send administrative alert | `{"title": "string", "message": "string"}` | `202 Accepted` |

### 5.4 Dual-Probe Routes (`/health/*`)

| Method | Endpoint | Scope | Database I/O | Success Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health/live` | Container / ASGI liveness | Zero DB I/O | `200 OK` (`{"status": "alive"}`) |
| `GET` | `/health/ready` | CI / Pre-deploy / Manual check | `SELECT 1` | `200 OK` (`{"status": "ready"}`) |

---

## 6. Telemetry & Messaging Tags Protocol

In accordance with project-wide telemetry standards, all messages sent or received across microservices, external LLM APIs, and the extension must emit structured logs with strict tag prefixes:

- Inbound message received: `MSG ->|  `
- Outbound response returned: `MSG <-|  `
- Outbound external request sent: `MSG   |->`
- Outbound external response received: `MSG   |<-`

### 6.1 W3C Distributed Tracing Invariants
1. Incoming requests from clients must carry standard W3C headers:
   - `traceparent: 00-{trace_id}-{client_span_id}-01`
   - `X-Source: extension` (or `web`)
   - `X-Destination: backend`
2. Backend responses must attach trace correlation headers:
   - `X-Transaction-ID: {trace_id}`
   - `X-Current-Span-ID: {server_span_id}`
   - `X-Parent-Transaction-ID: {client_span_id}`

---

## 7. Acceptance Criteria & Test Matrix

| Req ID | Target Component | Test Description | Verification Condition |
| :--- | :--- | :--- | :--- |
| `REQ-FOUND-001..005` | Docker Compose / ElasticMQ | Local compose startup & queue configuration | `docker compose up -d` boots postgis and elasticmq; SQS queues `vistarae-ingest-local` & DLQ exist with 180s visibility timeout. |
| `REQ-FOUND-006..011` | Alembic Migration | Schema migration execution | `alembic upgrade head` succeeds; `postgis`, `btree_gist`, `vector` enabled; foreign keys cascade. |
| `REQ-FOUND-012..015` | Health Probes | ASGI liveness vs DB readiness | `/health/live` returns 200 without DB connection; `/health/ready` executes `SELECT 1` and returns 503 when DB is stopped. |
| `REQ-AUTH-001..006` | Identity Service | Cognito Auth Lifecycle | Signup, verification, login, forgot-password, reset-password, and logout succeed. |
| `REQ-AUTH-007..008` | Auth Dependency | Local stage bypass | When `APP_ENV=local`, `X-Mock-User-Id` resolves user; in non-local environments, header is rejected. |
| `REQ-AUTH-009..010` | User Service | Cascade account deletion | Calling `DELETE /api/users/me` invokes Cognito `AdminDeleteUser` and cascades Postgres deletion for all user records. |
| `REQ-AUTH-011..012` | Auth Dependency | Orphaned & disabled JWT handling | Orphaned JWTs return 401; users with `is_disabled=TRUE` return 403. |
| `REQ-QUOTA-001..006` | Rate Limiter | Rolling window & tier caching | Low tier allows 60 req/min, 61st request returns RFC 7807 429 with `Retry-After`; High tier allows 300 req/min. |
| `REQ-QUOTA-007..012` | Idempotency Middleware | Key locking & cached responses | Simultaneous duplicate `Idempotency-Key` returns 409; completed key returns cached body with `X-Cache-Lookup: HIT`. |
| `REQ-QUOTA-013..015` | Token Budgeting | Pre-flight check & atomic increment | Rejects LLM call with 429 if `current_token_usage >= monthly_token_quota`; increments usage atomically on success. |
| `REQ-ADMIN-001..015` | Admin & User Services | User/Admin CRUD & Permissions | User can update sub-domain preferences; Admin can alter quotas, toggle traces, disable accounts, and read platform metrics. |

---

## 8. Security & Operational Considerations

1. **Neon Scale-to-Zero Preservation**: `/health/ready` MUST NOT be polled by automatic container health checks (e.g. AWS ECS liveness checks). Container liveness checks MUST solely query `/health/live` to allow Neon PostgreSQL compute to scale to 0 when inactive.
2. **Cognito Token Validation**: In production environments, Cognito JWTs are verified using a cached JWKS client verifying token signature, issuer (`https://cognito-idp.{region}.amazonaws.com/{user_pool_id}`), audience (`client_id`), and expiration timestamp.
3. **GDPR / Privacy Compliance**: Account deletion permanently purges all user data across all tables via database foreign key cascading (`ON DELETE CASCADE`), ensuring no orphaned personal identification records remain.
