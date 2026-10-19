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
- *Ubiquitous*: The repository shall mandate a standardized copyright header banner on every `.py`, `.ts`, `.tsx`, and `.sql` source code file.
- *State-Driven*: While formatting comments in Python source files (`.py`), the author shall prefix each header line with `#`.
- *State-Driven*: While formatting comments in TypeScript and TSX files (`.ts`, `.tsx`), the author shall prefix each header line with `//`.
- *State-Driven*: While formatting comments in SQL migration and query files (`.sql`), the author shall prefix each header line with `--`.
- *Ubiquitous*: The author shall use the exact standard header banner:
  ```text
  Copyright (c) 2026 Vistarae. All rights reserved.
  SPDX-License-Identifier: Apache-2.0
  ```
- *Event-Driven*: When staging files for a git commit, the pre-commit hook runner shall execute `ruff check`, `ruff format`, `prettier`, and `check-copyright-header`.
- *Unwanted Behaviour*: If any staged file fails formatting, linting, or copyright header verification, then the pre-commit framework shall reject the commit.
- *Ubiquitous*: The author shall provide Google-style docstrings with explicit `Args:`, `Returns:`, and `Raises:` sections for every public module, class, function, and method.
- *Ubiquitous*: The developer shall structure code using early returns and guard clauses with a maximum nesting ceiling of 3 indentation levels.
- *Ubiquitous*: The static analysis linter shall enforce a Cognitive Complexity score less than or equal to 15 on all functions and methods.
- *Unwanted Behaviour*: If a function implements pure mathematical projections or coordinate transformation solvers, then the static analysis linter shall exempt that function from the Cognitive Complexity ceiling.

### 2. Monorepo & Ports/Adapters Architecture
- *Ubiquitous*: The monorepo shall isolate shared domain models, value objects, exceptions, and port interfaces inside the editable `packages/core` workspace package.
- *Event-Driven*: When initializing local development or CI test environments, the package manager shall install `packages/core` in editable mode (`pip install -e ./packages/core`).
- *Ubiquitous*: The monorepo root manifest shall resolve `packages/core` imports across `pytest`, `uvicorn`, and `alembic` without deploying AWS Lambda Layers.
- *Unwanted Behaviour*: If AWS Lambda deployment packages require pre-compiled binary C-extensions, then the build pipeline shall restrict AWS Lambda Layers exclusively to those binary C-extensions.
- *Ubiquitous*: The domain layer shall enforce strict Dependency Inversion by abstracting all external persistence, queueing, identity, geocoding, and AI infrastructure behind Python `typing.Protocol` interfaces.
- *Unwanted Behaviour*: If domain entities, services, or deduplication engines execute business logic, then domain modules shall not import `boto3`, inspect AWS Lambda `event`/`context` payloads, or execute direct HTTP or database operations.
- *Ubiquitous*: Every domain microservice shall expose an ASGI `app` instance for Uvicorn and a serverless entrypoint `lambda_handler = Mangum(app, lifespan="off")` for AWS Lambda.
- *State-Driven*: While running in the local development environment (`STAGE == "local"`), the Uvicorn gateway shall mount all domain services under a unified ASGI router (`services.local_gateway:app`).
- *Event-Driven*: When initializing AWS Lambda execution environments, the service runtime shall instantiate stateless SDK clients (such as `boto3` clients and Gemini configurations) outside the `lambda_handler` for warm-container reuse.
- *State-Driven*: While managing asynchronous transports (`httpx.AsyncClient`, SQLAlchemy `AsyncEngine` with `asyncpg`), the service runtime shall bind transports to a persistent module-level event loop or dispose them cleanly per invocation using FastAPI `@asynccontextmanager async def lifespan`.

### 3. Database, PgBouncer & Tenancy Invariants
- *Ubiquitous*: The database access layer shall execute all database operations exclusively via SQLAlchemy 2.0 Pure Async components (`create_async_engine`, `AsyncSession`, and `async_sessionmaker`).
- *Event-Driven*: When parsing the `DATABASE_URL`, the database connection factory shall normalize the URL scheme to `postgresql+asyncpg://` and convert `sslmode=require` to `ssl=require`.
- *State-Driven*: While executing in cloud or AWS Lambda environments (`STAGE != "local"`), the database connection factory shall configure `create_async_engine` with `poolclass=NullPool` targeting the Neon PgBouncer pooled endpoint (`-pooler`).
- *State-Driven*: While executing in the local development environment (`STAGE == "local"`), the database connection factory shall configure `create_async_engine` with `QueuePool` initialized to `pool_size=5` and `max_overflow=5`.
- *Ubiquitous*: The database connection factory shall supply `connect_args={"statement_cache_size": 0}` to `create_async_engine` to disable asyncpg prepared statement caching across Neon PgBouncer transaction-mode connections.
- *Event-Driven*: When initializing the database engine or executing the initial `SELECT 1` connection probe, the database factory shall execute a 3-attempt exponential backoff retry loop with intervals of 500ms, 1500ms, and 3000ms to absorb Neon compute cold starts.
- *Ubiquitous*: The repository access layer shall append `WHERE user_id = :current_user_id` to every database query, mutation, and foreign key lookup.
- *Unwanted Behaviour*: If application tables store tenant data in PostgreSQL, then the database schema shall not enable PostgreSQL Row-Level Security (RLS) to prevent session-variable state contamination across shared PgBouncer connection pools.

### 4. Alembic & Environment Isolation
- *Ubiquitous*: The engineering team shall maintain all database schema migration scripts exclusively inside the `db/migrations/` directory.
- *State-Driven*: While running schema migrations in CI/CD (GitHub Actions), the migration runner shall connect via the direct Neon PostgreSQL endpoint (non-pooled) appending `?sslmode=require`.
- *Ubiquitous*: Every Alembic migration script shall implement a fully reversible `downgrade()` function that cleanly drops or reverts all applied schema changes.
- *Unwanted Behaviour*: If an Alembic migration script defines an empty or no-op downgrade (`def downgrade(): pass`), then the code review and CI verification gates shall reject the migration.
- *Event-Driven*: When executing CI pull request validation, the test runner shall execute `alembic check` to verify that SQLAlchemy ORM metadata and Alembic migration revisions match exactly.
- *Ubiquitous*: The data models shall type all status, state, and category fields using Python `StrEnum` backed by PostgreSQL `VARCHAR(n)` columns.
- *Unwanted Behaviour*: If a schema migration introduces or modifies enumeration fields, then the migration script shall not create or alter native PostgreSQL database `ENUM` types.
- *State-Driven*: While running automated test suites in pytest, the test execution runner shall isolate database state using a local Docker PostGIS container (`postgis/postgis:16-3.4`).
- *State-Driven*: While operating in cloud environments, the infrastructure configuration shall maintain complete environment isolation across `main`, `staging`, and `preview/dev` using Neon Copy-on-Write Database Branches with dedicated `DATABASE_URL` credentials.

### 5. API Contract, Validation & Error Standard
- *Ubiquitous*: The backend service layer shall expose OpenAPI 3.1 specifications generated directly from FastAPI application models as the single authoritative API contract.
- *Event-Driven*: When exporting API contracts for frontend integration, the build pipeline shall execute `python -m scripts.export_openapi` to generate `./openapi.json`.
- *Event-Driven*: When `./openapi.json` is generated or updated, the build toolchain shall execute `npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts` to generate strict TypeScript definitions.
- *Event-Driven*: When running CI pull request validation, the workflow runner shall execute `git diff --exit-code ./frontend/src/types/api.ts` to assert that backend contract changes have synchronized TypeScript types.
- *Unwanted Behaviour*: If `./frontend/src/types/api.ts` diverges from backend OpenAPI models, then the CI pipeline shall terminate with a non-zero exit code.
- *Ubiquitous*: The application boundary layer shall validate all incoming external payloads using Pydantic v2 `StrictBaseModel` configured with `extra="forbid"`, `validate_assignment=True`, and `str_strip_whitespace=True`.
- *Unwanted Behaviour*: If an incoming payload contains unmapped or unexpected properties, then the boundary validator shall raise a validation error and reject the request.
- *Event-Driven*: When any microservice produces a non-2XX HTTP response, the service layer shall format the response body as RFC 7807 / RFC 9457 `ProblemDetails` JSON containing `type`, `title`, `status`, `detail`, `instance`, and `invalid_params`.
- *Event-Driven*: When the frontend single-page application receives an RFC 7807 / RFC 9457 `ProblemDetails` response, the UI error boundary shall render an actionable notification banner to the user.

### 6. Middleware Order & Security Guardrails
- *Event-Driven*: When configuring the FastAPI middleware stack, the application factory shall register `IdempotencyMiddleware` first and `RateLimitMiddleware` second to ensure Rate-Limiting executes as the outermost layer under Starlette's LIFO execution model.
- *Event-Driven*: When a client exceeds assigned request rate limits, the `RateLimitMiddleware` shall immediately return an RFC 7807 429 Too Many Requests response before `IdempotencyMiddleware` allocates database records.
- *State-Driven*: While executing in the local development environment (`STAGE == "local"`), the `CORSMiddleware` shall whitelist the SPA dev origin `http://localhost:5173`.
- *State-Driven*: While executing in production environments (`STAGE != "local"`), the `CORSMiddleware` shall whitelist only the Chrome Extension origin `chrome-extension://<EXTENSION_ID>` with explicit allowed headers (`Idempotency-Key`, `Content-Type`, `Authorization`, `traceparent`, `X-Amzn-Trace-Id`, `X-Vistarae-Trace-Id`).
- *Unwanted Behaviour*: If any service configures CORS origins, then the service shall not set `allow_origins=["*"]`.
- *Ubiquitous*: The system shall strictly prevent credential leakage by forbidding hardcoded tokens, excluding secrets from log outputs, and ignoring `.env*` files in git (except `.env.example`).
- *State-Driven*: While running database seeding or destructive scripts (`scripts/seed_local_db.py`), the script runner shall verify `STAGE == "local"` before executing `TRUNCATE` or batch deletions.
- *Event-Driven*: When executing operational maintenance tools (`scripts/redrive_dlq.py`) against non-local environments, the CLI runner shall require explicit `--env` flags and interactive user confirmation.

### 7. Observability, OpenTelemetry & X-Ray
- *State-Driven*: While executing in local development (`STAGE == "local"`), the logging subsystem shall output human-readable, formatted text logs.
- *State-Driven*: While executing in cloud environments (`STAGE != "local"`), the logging subsystem shall output structured JSON logs containing timestamp, level, trace context, and service identifiers.
- *State-Driven*: While operating in local testing mode (`STAGE == "local"`), cross-boundary message logs shall include the exact literal directional markers inside inline code blocks:
  - When a microservice receives a request: the service shall log `MSG: -->|`.
  - When a microservice returns a 2XX response: the service shall log `MSG: <--|`.
  - When a microservice returns a 4XX or 5XX error response: the service shall log `MSG: <~~|`.
  - When a client or service dispatches a request: the client shall log `MSG: |-->`.
  - When a client or service receives a 2XX response: the client shall log `MSG: |<--`.
  - When a client or service receives a 4XX or 5XX error response: the client shall log `MSG: |<~~`.
- *State-Driven*: While logging local directional messages, the logger shall include headers specifying sender service, receiver service, and authenticated user UUID.
- *State-Driven*: While executing in AWS production environments, the logger shall omit literal `MSG` prefixes and directional markers.
- *Event-Driven*: When enqueuing asynchronous background tasks to SQS, the dispatching service shall inject W3C `traceparent` and `X-Amzn-Trace-Id` into SQS `MessageAttributes` with `String` data types.
- *Event-Driven*: When an SQS background worker consumes a batch of messages, the worker shall extract trace attributes from `messageAttributes` and inject them into OpenTelemetry `TraceContext` and `AwsXRayPropagator`.
- *Ubiquitous*: The CloudFormation/SAM template shall enable AWS X-Ray tracing (`Tracing: Active`) on all application Lambdas with a custom `AWS::XRay::SamplingRule` configured to `ReservoirSize: 0` and `FixedRate: 0.01` (1% sampling) to ensure trace volume remains within the 100,000 free monthly trace tier.
- *Unwanted Behaviour*: If an incoming request includes client-forced sampling (`Sampled=1` via `X-Vistarae-Trace-Id` or `traceparent`), then the OpenTelemetry middleware shall honor client-forced sampling only if the caller provides a verified admin JWT claim or an active admin trace flag.

### 8. PyTest & SDD Governance
- *Event-Driven*: When running the test suite, pytest shall enforce a minimum 90% branch and line coverage threshold via `--cov=src --cov-fail-under=90`.
- *Unwanted Behaviour*: If total test coverage falls below 90%, then pytest shall fail the test run and CI shall reject the pull request.
- *Ubiquitous*: The test suite shall mirror the production source tree 1:1 within `tests/unit/` (e.g. `services/poi/geocoding.py` shall have unit tests located in `tests/unit/services/poi/test_geocoding.py`).
- *Ubiquitous*: The developer shall organize unit test scenarios within `Test<FeatureOrMethod>` classes inside the corresponding module test file.
- *Unwanted Behaviour*: If a unit test file exceeds approximately 500 lines or addresses distinct sub-domains, then the developer shall refactor the file into a cohesive test sub-package.
- *Unwanted Behaviour*: If a proposed code or infrastructure change lacks a ratified `spec.md` and dependency-ordered `tasks.md`, then developers and AI agents shall not write production code or tests.
- *Ubiquitous*: The specification (`spec.md`) shall govern as the absolute source of truth whenever code and specification diverge.
- *Unwanted Behaviour*: If a feature, endpoint, parameter, or abstraction is not explicitly mandated in the approved task checklist, then developers and AI agents shall not implement speculative code (strict YAGNI).
- *Ubiquitous*: Every git commit and pull request shall reference its corresponding spec-kit task ID (e.g., `T-001`).

## Operational & Infrastructure Invariants

### 1. Asynchronous SQS Ingestion & Queue Discipline
- *Unwanted Behaviour*: If an uploaded CSV file exceeds 2MB in payload size or contains more than 2,000 rows, then the ingestion gateway shall return an RFC 7807 413 or 422 error instructing the user to split the file.
- *Event-Driven*: When parsing CSV records during ingestion, the parser shall neutralize formula injection characters (`=`, `+`, `-`, `@`, `\t`, `\r`) prior to persistence.
- *Event-Driven*: When chunking validated records for asynchronous processing, the ingestion gateway shall partition records into batches of 10 messages (`BatchSize: 10`) for SQS dispatch.
- *Ubiquitous*: The primary SQS queue shall configure `ReceiveMessageWaitTimeSeconds: 20` (Long Polling) and `VisibilityTimeout: 180s` (at least 6 times the worker Lambda 30-second timeout).
- *Ubiquitous*: The dead-letter queue (DLQ) redrive policy shall configure `maxReceiveCount: 3` and `MessageRetentionPeriod: 1209600` (14 days).
- *Event-Driven*: When the dead-letter queue receives messages (`ApproximateNumberOfMessagesVisible >= 1`), a CloudWatch alarm shall trigger developer notification.
- *Ubiquitous*: SQS worker Lambda event source mappings shall enable `ReportBatchItemFailures: true` and return `{"batchItemFailures": [{"itemIdentifier": msg_id}]}` for any failed record in a batch.
- *Event-Driven*: When processing batch items in SQS workers, the worker shall insert a synthetic idempotency key `sha256(f"{user_id}:{csv_job_id}:{row_number}".encode()).hexdigest()` into `idempotency_keys` with `ON CONFLICT DO NOTHING` to guarantee record-level idempotency.

### 2. Geospatial Storage & Coordinate Transformations
- *Ubiquitous*: The database schema shall canonically store single point coordinates as `geography(Point, 4326)` for geodesic calculations and regional boundaries as `geometry(MultiPolygon, 4326)`.
- *Ubiquitous*: The repository query builder shall cast geography points to geometry `(geom::geometry) && ST_MakeEnvelope(minLng, minLat, maxLng, maxLat, 4326)` backed by composite functional GiST index `idx_pois_user_geom_geometry` on `(user_id, (geom::geometry))` for viewport bounding-box lookups.
- *Event-Driven*: When executing spatial radius queries with user-facing mile inputs, the repository shall convert miles to meters (`miles * 1609.344`) before calling `ST_DWithin`.
- *State-Driven*: While rendering coordinates on a shifted Chinese tile provider (GCJ-02 or BD-09), the frontend client shall execute coordinate transformations (`wgs84_to_gcj02`, `gcj02_to_wgs84`) purely on the client side if and only if coordinates fall inside the China bounding box (73.66°E to 135.05°E, 18.16°N to 53.55°N).
- *Ubiquitous*: The backend database shall retain all coordinates untransformed in canonical WGS-84 coordinate space.

### 3. Zero-Cost Architecture & AWS Free-Tier Guardrails
- *Ubiquitous*: The telemetry subsystem shall record user metrics, session counters, and token quotas strictly in Neon database tables (`user_metrics`, `user_quotas`) without invoking CloudWatch `PutMetricData` or DynamoDB.
- *Ubiquitous*: The CloudWatch monitoring configuration shall limit active alarms to within the 10-alarm AWS free tier allowance.
- *State-Driven*: While running the application in production, external monitoring services shall not issue recurring pings to `/health/ready` to permit Neon compute to scale to zero within the 190 free monthly compute hours.
- *Ubiquitous*: The frontend web hosting architecture shall host static single-page assets in a private Amazon S3 bucket fronted by AWS CloudFront using Origin Access Control (OAC).
- *Event-Driven*: When AWS Budgets emits a spending threshold alert ($1.00 or $5.00), the `SpendKillSwitch` Lambda shall throttle the API Gateway stage or set Lambda function `ReservedConcurrentExecutions: 0`.
- *Ubiquitous*: The Chrome native host bridge (`com.vistarae.folder_opener`) shall communicate over unbuffered standard I/O using 4-byte native endian integer framing (`struct.unpack('=I', ...)`, `struct.pack('=I', ...)`).
- *Unwanted Behaviour*: If an input path to the Chrome native host contains shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`), then the host dispatcher shall immediately reject the request.

## Development Workflow & CI/CD Quality Gates

### 1. Local Infrastructure First
- *Ubiquitous*: The development environment shall orchestrate all non-serverless dependencies locally via `docker compose up -d` using `docker-compose.yml` (`postgis/postgis:16-3.4` and `softwaremill/elasticmq-native:latest`).
- *Ubiquitous*: The engineering team shall verify every feature, API route, and extension interaction locally via `uvicorn`, local Vite proxy (`/api` -> `http://localhost:8000`), and ElasticMQ prior to cloud deployment.

### 2. Pre-Commit Verification Gate
- *Event-Driven*: When developers or AI agents commit code, the pre-commit framework shall execute Python linting and formatting via `ruff check` and `ruff format`.
- *Event-Driven*: When developers or AI agents commit code, the pre-commit framework shall execute frontend formatting via `prettier`.
- *Event-Driven*: When developers or AI agents commit code, the pre-commit framework shall verify mandatory file header banners across all `.py`, `.ts`, `.tsx`, and `.sql` files.

### 3. GitHub Actions Delivery Pipeline
- *Ubiquitous*: The CI/CD system shall utilize GitHub Actions running on the free runner tier as the sole continuous integration and deployment engine.
- *Ubiquitous*: The delivery pipeline shall authenticate to AWS using keyless OpenID Connect (OIDC) assuming temporary IAM roles (`GitHubActionsDeployerRole`).
- *Event-Driven*: When a pull request is submitted, GitHub Actions shall execute format checks, `pytest` with coverage enforcement, `alembic check`, and OpenAPI contract synchronization checks (`git diff --exit-code ./frontend/src/types/api.ts`).
- *Event-Driven*: When changes merge into release branches, GitHub Actions shall execute automated migrations on Neon branches and invalidate CloudFront edge caches (`/index.html`, `/`).

## Governance

### 1. Constitutional Supremacy
- *Ubiquitous*: The development team and AI agents shall treat this constitution as the supreme engineering law of the Vistarae project.
- *Ubiquitous*: All feature specifications (`spec.md`), task plans (`tasks.md`), code implementations, and pull requests shall strictly comply with the requirements in this document.
- *Unwanted Behaviour*: If an implementation contradicts any requirement in this constitution, then the implementation shall be deemed defective and rejected.

### 2. Amendment Procedure
- *Event-Driven*: When amending any constitutional rule, the author shall submit a formal pull request documenting technical justification, impact analysis, and an incremented semantic version.
- *State-Driven*: While amending governance policies, the author shall update the Sync Impact Report at the top of the file to document all modifications.

### 3. Versioning Policy
- *Ubiquitous*: The constitution shall adhere to Semantic Versioning (MAJOR.MINOR.PATCH).
- *State-Driven*: While proposing changes, the author shall increment the MAJOR version for incompatible governance or rule removals.
- *State-Driven*: While proposing changes, the author shall increment the MINOR version for additions of new rules, structural refactoring, or material expansions of technical guidance.
- *State-Driven*: While proposing changes, the author shall increment the PATCH version for non-semantic clarifications, wording corrections, or typo fixes.

### 4. Compliance Review
- *Event-Driven*: When reviewing pull requests, code reviewers and automated CI checks shall verify compliance against all constitutional requirements.
- *Unwanted Behaviour*: If a pull request introduces unjustified complexity, unratified architectural changes, or unapproved scope expansions, then the reviewer shall reject the pull request.

**Version**: 1.1.0 | **Ratified**: 2026-10-18 | **Last Amended**: 2026-10-18
