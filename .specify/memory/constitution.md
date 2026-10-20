<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 -> 1.1.0 (EARS Requirement Syntax Refactoring)
Modified Principles:
  - 1. File Header & Pre-Commit Standard (refactored to strict EARS syntax)
  - 2. Monorepo & Ports/Adapters Architecture (refactored to strict EARS syntax)
  - 3. Database, PgBouncer & Tenancy Invariants (refactored to strict EARS syntax)
  - 4. Alembic & Environment Isolation (refactored to strict EARS syntax)
  - 5. API Contract, Validation & Error Standard (refactored to strict EARS syntax)
  - 6. Middleware Order & Security Guardrails (refactored to strict EARS syntax)
  - 7. Observability, OpenTelemetry & X-Ray (refactored to strict EARS syntax)
  - 8. PyTest & SDD Governance (refactored to strict EARS syntax)
Added Sections:
  - Operational & Infrastructure Invariants (refactored to strict EARS syntax)
  - Governance Framework (refactored to strict EARS syntax)
Removed Sections: None.
Follow-up TODOs: None (all template placeholders fully resolved).
-->

# Vistarae Constitution

## Core Principles

### 1. File Header & Pre-Commit Standard

- _Ubiquitous_: The repository shall mandate a standardized copyright header banner on every `.py`, `.ts`, `.tsx`, and `.sql` source code file.
- _State-Driven_: While formatting comments in Python source files (`.py`), the author shall prefix each header line with `#`.
- _State-Driven_: While formatting comments in TypeScript and TSX files (`.ts`, `.tsx`), the author shall prefix each header line with `//`.
- _State-Driven_: While formatting comments in SQL migration and query files (`.sql`), the author shall prefix each header line with `--`.
- _Ubiquitous_: The author shall use the exact standard header banner:

  ```text
  Copyright (c) 2026 Tim Olker

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  SPDX-License-Identifier: Apache-2.0
  ```

- _Event-Driven_: When staging files for a git commit, the pre-commit hook runner shall execute `ruff check`, `ruff format`, `prettier`, and `check-copyright-header`.
- _Unwanted Behaviour_: If any staged file fails formatting, linting, or copyright header verification, then the pre-commit framework shall reject the commit.
- _Ubiquitous_: The author shall provide Google-style docstrings with explicit `Args:`, `Returns:`, and `Raises:` sections for every public module, class, function, and method.
- _Ubiquitous_: The developer shall structure code using early returns and guard clauses with a maximum nesting ceiling of 3 indentation levels.
- _Ubiquitous_: The static analysis linter shall enforce a Cognitive Complexity score less than or equal to 15 on all functions and methods.
- _Unwanted Behaviour_: If a function implements pure mathematical projections or coordinate transformation solvers, then the static analysis linter shall exempt that function from the Cognitive Complexity ceiling.

### 2. Monorepo & Ports/Adapters Architecture

- _Ubiquitous_: The monorepo shall isolate shared domain models, value objects, exceptions, and port interfaces inside the editable `packages/core` workspace package.
- _Event-Driven_: When initializing local development or CI test environments, the package manager shall install `packages/core` in editable mode (`pip install -e ./packages/core`).
- _Ubiquitous_: The monorepo root manifest shall resolve `packages/core` imports across `pytest`, `uvicorn`, and `alembic` without deploying AWS Lambda Layers.
- _Unwanted Behaviour_: If AWS Lambda deployment packages require pre-compiled binary C-extensions, then the build pipeline shall restrict AWS Lambda Layers exclusively to those binary C-extensions.
- _Ubiquitous_: The domain layer shall enforce strict Dependency Inversion by abstracting all external persistence, queueing, identity, geocoding, and AI infrastructure behind Python `typing.Protocol` interfaces.
- _Unwanted Behaviour_: If domain entities, services, or deduplication engines execute business logic, then domain modules shall not import `boto3`, inspect AWS Lambda `event`/`context` payloads, or execute direct HTTP or database operations.
- _Ubiquitous_: Every domain microservice shall expose an ASGI `app` instance for Uvicorn and a serverless entrypoint `lambda_handler = Mangum(app, lifespan="off")` for AWS Lambda.
- _State-Driven_: While running in the local development environment (`STAGE == "local"`), the Uvicorn gateway shall mount all domain services under a unified ASGI router (`services.local_gateway:app`).
- _Event-Driven_: When initializing AWS Lambda execution environments, the service runtime shall instantiate stateless SDK clients (such as `boto3` clients and Gemini configurations) outside the `lambda_handler` for warm-container reuse.
- _State-Driven_: While managing asynchronous transports (`httpx.AsyncClient`, SQLAlchemy `AsyncEngine` with `asyncpg`), the service runtime shall bind transports to a persistent module-level event loop or dispose them cleanly per invocation using FastAPI `@asynccontextmanager async def lifespan`.

### 3. Database, PgBouncer & Tenancy Invariants

- _Ubiquitous_: The database access layer shall execute all database operations exclusively via SQLAlchemy 2.0 Pure Async components (`create_async_engine`, `AsyncSession`, and `async_sessionmaker`).
- _Event-Driven_: When parsing the `DATABASE_URL`, the database connection factory shall normalize the URL scheme to `postgresql+asyncpg://` and convert `sslmode=require` to `ssl=require`.
- _State-Driven_: While executing in cloud or AWS Lambda environments (`STAGE != "local"`), the database connection factory shall configure `create_async_engine` with `poolclass=NullPool` targeting the Neon PgBouncer pooled endpoint (`-pooler`).
- _State-Driven_: While executing in the local development environment (`STAGE == "local"`), the database connection factory shall configure `create_async_engine` with `QueuePool` initialized to `pool_size=5` and `max_overflow=5`.
- _Ubiquitous_: The database connection factory shall supply `connect_args={"statement_cache_size": 0}` to `create_async_engine` to disable asyncpg prepared statement caching across Neon PgBouncer transaction-mode connections.
- _Event-Driven_: When initializing the database engine or executing the initial `SELECT 1` connection probe, the database factory shall execute a 3-attempt exponential backoff retry loop with intervals of 500ms, 1500ms, and 3000ms to absorb Neon compute cold starts.
- _Ubiquitous_: The repository access layer shall append `WHERE user_id = :current_user_id` to every database query, mutation, and foreign key lookup.
- _Unwanted Behaviour_: If application tables store tenant data in PostgreSQL, then the database schema shall not enable PostgreSQL Row-Level Security (RLS) to prevent session-variable state contamination across shared PgBouncer connection pools.

### 4. Alembic & Environment Isolation

- _Ubiquitous_: The engineering team shall maintain all database schema migration scripts exclusively inside the `db/migrations/` directory.
- _State-Driven_: While running schema migrations in CI/CD (GitHub Actions), the migration runner shall connect via the direct Neon PostgreSQL endpoint (non-pooled) appending `?sslmode=require`.
- _Ubiquitous_: Every Alembic migration script shall implement a fully reversible `downgrade()` function that cleanly drops or reverts all applied schema changes.
- _Unwanted Behaviour_: If an Alembic migration script defines an empty or no-op downgrade (`def downgrade(): pass`), then the code review and CI verification gates shall reject the migration.
- _Event-Driven_: When executing CI pull request validation, the test runner shall execute `alembic check` to verify that SQLAlchemy ORM metadata and Alembic migration revisions match exactly.
- _Ubiquitous_: The data models shall type all status, state, and category fields using Python `StrEnum` backed by PostgreSQL `VARCHAR(n)` columns.
- _Unwanted Behaviour_: If a schema migration introduces or modifies enumeration fields, then the migration script shall not create or alter native PostgreSQL database `ENUM` types.
- _State-Driven_: While running automated test suites in pytest, the test execution runner shall isolate database state using a local Docker PostGIS container (`postgis/postgis:16-3.4`).
- _State-Driven_: While operating in cloud environments, the infrastructure configuration shall maintain complete environment isolation across `main`, `staging`, and `preview/dev` using Neon Copy-on-Write Database Branches with dedicated `DATABASE_URL` credentials.

### 5. API Contract, Validation & Error Standard

- _Ubiquitous_: The backend service layer shall expose OpenAPI 3.1 specifications generated directly from FastAPI application models as the single authoritative API contract.
- _Event-Driven_: When exporting API contracts for frontend integration, the build pipeline shall execute `python -m scripts.export_openapi` to generate `./openapi.json`.
- _Event-Driven_: When `./openapi.json` is generated or updated, the build toolchain shall execute `npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts` to generate strict TypeScript definitions.
- _Event-Driven_: When running CI pull request validation, the workflow runner shall execute `git diff --exit-code ./frontend/src/types/api.ts` to assert that backend contract changes have synchronized TypeScript types.
- _Unwanted Behaviour_: If `./frontend/src/types/api.ts` diverges from backend OpenAPI models, then the CI pipeline shall terminate with a non-zero exit code.
- _Ubiquitous_: The application boundary layer shall validate all incoming external payloads using Pydantic v2 `StrictBaseModel` configured with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True`.
- _Unwanted Behaviour_: If an incoming payload contains unmapped or unexpected properties, then the boundary validator shall raise a validation error and reject the request.
- _Event-Driven_: When any microservice produces a non-2XX HTTP response, the service layer shall format the response body as RFC 7807 / RFC 9457 `ProblemDetails` JSON containing `type`, `title`, `status`, `detail`, `instance`, and `invalid_params`.
- _Event-Driven_: When the frontend single-page application receives an RFC 7807 / RFC 9457 `ProblemDetails` response, the UI error boundary shall render an actionable notification banner to the user.

### 6. Middleware Order & Security Guardrails

- _Event-Driven_: When configuring the FastAPI middleware stack, the application factory shall register `IdempotencyMiddleware` first and `RateLimitMiddleware` second to ensure Rate-Limiting executes as the outermost layer under Starlette's LIFO execution model.
- _Event-Driven_: When a client exceeds assigned request rate limits, the `RateLimitMiddleware` shall immediately return an RFC 7807 429 Too Many Requests response before `IdempotencyMiddleware` allocates database records.
- _State-Driven_: While executing in the local development environment (`STAGE == "local"`), the `CORSMiddleware` shall whitelist the SPA dev origin `http://localhost:5173`.
- _State-Driven_: While executing in production environments (`STAGE != "local"`), the `CORSMiddleware` shall whitelist only the Chrome Extension origin `chrome-extension://<EXTENSION_ID>` with explicit allowed headers (`Idempotency-Key`, `Content-Type`, `Authorization`, `traceparent`, `X-Amzn-Trace-Id`, `X-Vistarae-Trace-Id`).
- _Unwanted Behaviour_: If any service configures CORS origins, then the service shall not set `allow_origins=["*"]`.
- _Ubiquitous_: The system shall strictly prevent credential leakage by forbidding hardcoded tokens, excluding secrets from log outputs, and ignoring `.env*` files in git (except `.env.example`).
- _State-Driven_: While running database seeding or destructive scripts (`scripts/seed_local_db.py`), the script runner shall verify `STAGE == "local"` before executing `TRUNCATE` or batch deletions.
- _Event-Driven_: When executing operational maintenance tools (`scripts/redrive_dlq.py`) against non-local environments, the CLI runner shall require explicit `--env` flags and interactive user confirmation.

### 7. Observability, OpenTelemetry & X-Ray

- _State-Driven_: While executing in local development (`STAGE == "local"`), the logging subsystem shall output human-readable, formatted text logs.
- _State-Driven_: While executing in cloud environments (`STAGE != "local"`), the logging subsystem shall output structured JSON logs containing timestamp, level, trace context, and service identifiers.
- _State-Driven_: While operating in local testing mode (`STAGE == "local"`), cross-boundary message logs shall include the exact literal directional markers inside inline code blocks:
  - When a microservice receives a request: the service shall log `MSG: -->|`.
  - When a microservice returns a 2XX response: the service shall log `MSG: <--|`.
  - When a microservice returns a 4XX or 5XX error response: the service shall log `MSG: <~~|`.
  - When a client or service dispatches a request: the client shall log `MSG: |-->`.
  - When a client or service receives a 2XX response: the client shall log `MSG: |<--`.
  - When a client or service receives a 4XX or 5XX error response: the client shall log `MSG: |<~~`.
- _State-Driven_: While logging local directional messages, the logger shall include headers specifying sender service, receiver service, and authenticated user UUID.
- _State-Driven_: While executing in AWS production environments, the logger shall omit literal `MSG` prefixes and directional markers.
- _Event-Driven_: When enqueuing asynchronous background tasks to SQS, the dispatching service shall inject W3C `traceparent` and `X-Amzn-Trace-Id` into SQS `MessageAttributes` with `String` data types.
- _Event-Driven_: When an SQS background worker consumes a batch of messages, the worker shall extract trace attributes from `messageAttributes` and inject them into OpenTelemetry `TraceContext` and `AwsXRayPropagator`.
- _Ubiquitous_: The CloudFormation/SAM template shall enable AWS X-Ray tracing (`Tracing: Active`) on all application Lambdas with a custom `AWS::XRay::SamplingRule` configured to `ReservoirSize: 0` and `FixedRate: 0.01` (1% sampling) to ensure trace volume remains within the 100,000 free monthly trace tier.
- _Unwanted Behaviour_: If an incoming request includes client-forced sampling (`Sampled=1` via `X-Vistarae-Trace-Id` or `traceparent`), then the OpenTelemetry middleware shall honor client-forced sampling only if the caller provides a verified admin JWT claim or an active admin trace flag.

### 8. PyTest & SDD Governance

- _Event-Driven_: When running the test suite, pytest shall enforce a minimum 90% branch and line coverage threshold via `--cov=src --cov-fail-under=90`.
- _Unwanted Behaviour_: If total test coverage falls below 90%, then pytest shall fail the test run and CI shall reject the pull request.
- _Ubiquitous_: The test suite shall mirror the production source tree 1:1 within `tests/unit/` (e.g. `services/poi/geocoding.py` shall have unit tests located in `tests/unit/services/poi/test_geocoding.py`).
- _Ubiquitous_: The developer shall organize unit test scenarios within `Test<FeatureOrMethod>` classes inside the corresponding module test file.
- _Unwanted Behaviour_: If a unit test file exceeds approximately 500 lines or addresses distinct sub-domains, then the developer shall refactor the file into a cohesive test sub-package.
- _Unwanted Behaviour_: If a proposed code or infrastructure change lacks a ratified `spec.md` and dependency-ordered `tasks.md`, then developers and AI agents shall not write production code or tests.
- _Ubiquitous_: The specification (`spec.md`) shall govern as the absolute source of truth whenever code and specification diverge.
- _Unwanted Behaviour_: If a feature, endpoint, parameter, or abstraction is not explicitly mandated in the approved task checklist, then developers and AI agents shall not implement speculative code (strict YAGNI).
- _Ubiquitous_: Every git commit and pull request shall reference its corresponding spec-kit task ID (e.g., `T-001`).

## Operational & Infrastructure Invariants

### 1. Asynchronous SQS Ingestion & Queue Discipline

- _Unwanted Behaviour_: If an uploaded CSV file exceeds 2MB in payload size or contains more than 2,000 rows, then the ingestion gateway shall return an RFC 7807 413 or 422 error instructing the user to split the file.
- _Event-Driven_: When parsing CSV records during ingestion, the parser shall neutralize formula injection characters (`=`, `+`, `-`, `@`, `\t`, `\r`) prior to persistence.
- _Event-Driven_: When chunking validated records for asynchronous processing, the ingestion gateway shall partition records into batches of 10 messages (`BatchSize: 10`) for SQS dispatch.
- _Ubiquitous_: The primary SQS queue shall configure `ReceiveMessageWaitTimeSeconds: 20` (Long Polling) and `VisibilityTimeout: 180s` (at least 6 times the worker Lambda 30-second timeout).
- _Ubiquitous_: The dead-letter queue (DLQ) redrive policy shall configure `maxReceiveCount: 3` and `MessageRetentionPeriod: 1209600` (14 days).
- _Event-Driven_: When the dead-letter queue receives messages (`ApproximateNumberOfMessagesVisible >= 1`), a CloudWatch alarm shall trigger developer notification.
- _Ubiquitous_: SQS worker Lambda event source mappings shall enable `ReportBatchItemFailures: true` and return `{"batchItemFailures": [{"itemIdentifier": msg_id}]}` for any failed record in a batch.
- _Event-Driven_: When processing batch items in SQS workers, the worker shall insert a synthetic idempotency key `sha256(f"{user_id}:{csv_job_id}:{row_number}".encode()).hexdigest()` into `idempotency_keys` with `ON CONFLICT DO NOTHING` to guarantee record-level idempotency.

### 2. Geospatial Storage & Coordinate Transformations

- _Ubiquitous_: The database schema shall canonically store single point coordinates as `geography(Point, 4326)` for geodesic calculations and regional boundaries as `geometry(MultiPolygon, 4326)`.
- _Ubiquitous_: The repository query builder shall cast geography points to geometry `(geom::geometry) && ST_MakeEnvelope(minLng, minLat, maxLng, maxLat, 4326)` backed by composite functional GiST index `idx_pois_user_geom_geometry` on `(user_id, (geom::geometry))` for viewport bounding-box lookups.
- _Event-Driven_: When executing spatial radius queries with user-facing mile inputs, the repository shall convert miles to meters (`miles * 1609.344`) before calling `ST_DWithin`.
- _State-Driven_: While rendering coordinates on a shifted Chinese tile provider (GCJ-02 or BD-09), the frontend client shall execute coordinate transformations (`wgs84_to_gcj02`, `gcj02_to_wgs84`) purely on the client side if and only if coordinates fall inside the China bounding box (73.66°E to 135.05°E, 18.16°N to 53.55°N).
- _Ubiquitous_: The backend database shall retain all coordinates untransformed in canonical WGS-84 coordinate space.

### 3. Zero-Cost Architecture & AWS Free-Tier Guardrails

- _Ubiquitous_: The telemetry subsystem shall record user metrics, session counters, and token quotas strictly in Neon database tables (`user_metrics`, `user_quotas`) without invoking CloudWatch `PutMetricData` or DynamoDB.
- _Ubiquitous_: The CloudWatch monitoring configuration shall limit active alarms to within the 10-alarm AWS free tier allowance.
- _State-Driven_: While running the application in production, external monitoring services shall not issue recurring pings to `/health/ready` to permit Neon compute to scale to zero within the 190 free monthly compute hours.
- _Ubiquitous_: The frontend web hosting architecture shall host static single-page assets in a private Amazon S3 bucket fronted by AWS CloudFront using Origin Access Control (OAC).
- _Event-Driven_: When AWS Budgets emits a spending threshold alert ($1.00 or $5.00), the `SpendKillSwitch` Lambda shall throttle the API Gateway stage or set Lambda function `ReservedConcurrentExecutions: 0`.
- _Ubiquitous_: The Chrome native host bridge (`com.vistarae.folder_opener`) shall communicate over unbuffered standard I/O using 4-byte native endian integer framing (`struct.unpack('=I', ...)`, `struct.pack('=I', ...)`).
- _Unwanted Behaviour_: If an input path to the Chrome native host contains shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`), then the host dispatcher shall immediately reject the request.

## Development Workflow & CI/CD Quality Gates

### 1. Local Infrastructure First

- _Ubiquitous_: The development environment shall orchestrate all non-serverless dependencies locally via `docker compose up -d` using `docker-compose.yml` (`postgis/postgis:16-3.4` and `softwaremill/elasticmq-native:latest`).
- _Ubiquitous_: The engineering team shall verify every feature, API route, and extension interaction locally via `uvicorn`, local Vite proxy (`/api` -> `http://localhost:8000`), and ElasticMQ prior to cloud deployment.

### 2. Pre-Commit Verification Gate

- _Event-Driven_: When developers or AI agents commit code, the pre-commit framework shall execute Python linting and formatting via `ruff check` and `ruff format`.
- _Event-Driven_: When developers or AI agents commit code, the pre-commit framework shall execute frontend formatting via `prettier`.
- _Event-Driven_: When developers or AI agents commit code, the pre-commit framework shall verify mandatory file header banners across all `.py`, `.ts`, `.tsx`, and `.sql` files.

### 3. GitHub Actions Delivery Pipeline

- _Ubiquitous_: The CI/CD system shall utilize GitHub Actions running on the free runner tier as the sole continuous integration and deployment engine.
- _Ubiquitous_: The delivery pipeline shall authenticate to AWS using keyless OpenID Connect (OIDC) assuming temporary IAM roles (`GitHubActionsDeployerRole`).
- _Event-Driven_: When a pull request is submitted, GitHub Actions shall execute format checks, `pytest` with coverage enforcement, `alembic check`, and OpenAPI contract synchronization checks (`git diff --exit-code ./frontend/src/types/api.ts`).
- _Event-Driven_: When changes merge into release branches, GitHub Actions shall execute automated migrations on Neon branches and invalidate CloudFront edge caches (`/index.html`, `/`).

## Governance

### 1. Constitutional Supremacy

- _Ubiquitous_: The development team and AI agents shall treat this constitution as the supreme engineering law of the Vistarae project.
- _Ubiquitous_: All feature specifications (`spec.md`), task plans (`tasks.md`), code implementations, and pull requests shall strictly comply with the requirements in this document.
- _Unwanted Behaviour_: If an implementation contradicts any requirement in this constitution, then the implementation shall be deemed defective and rejected.

### 2. Amendment Procedure

- _Event-Driven_: When amending any constitutional rule, the author shall submit a formal pull request documenting technical justification, impact analysis, and an incremented semantic version.
- _State-Driven_: While amending governance policies, the author shall update the Sync Impact Report at the top of the file to document all modifications.

### 3. Versioning Policy

- _Ubiquitous_: The constitution shall adhere to Semantic Versioning (MAJOR.MINOR.PATCH).
- _State-Driven_: While proposing changes, the author shall increment the MAJOR version for incompatible governance or rule removals.
- _State-Driven_: While proposing changes, the author shall increment the MINOR version for additions of new rules, structural refactoring, or material expansions of technical guidance.
- _State-Driven_: While proposing changes, the author shall increment the PATCH version for non-semantic clarifications, wording corrections, or typo fixes.

### 4. Compliance Review

- _Event-Driven_: When reviewing pull requests, code reviewers and automated CI checks shall verify compliance against all constitutional requirements.
- _Unwanted Behaviour_: If a pull request introduces unjustified complexity, unratified architectural changes, or unapproved scope expansions, then the reviewer shall reject the pull request.

**Version**: 1.1.0 | **Ratified**: 2026-10-18 | **Last Amended**: 2026-10-18
