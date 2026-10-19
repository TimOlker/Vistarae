# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""UserFunction FastAPI microservice application.

Standalone ASGI application exposing user profile, preference, and GDPR
deletion routes under /api/users. Deployed as an AWS Lambda function via
Mangum with lifespan='off' (Constitution Principle 2).

Serverless entry point:
    lambda_handler = Mangum(app, lifespan='off')
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mangum import Mangum
from vistarae_core.adapters.db.session import get_engine, init_engine
from vistarae_core.middleware.errors import add_problem_details_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages connection pool lifecycle for UserFunction.

    Initializes the engine with 3-attempt backoff on startup and disposes
    the connection pool cleanly on shutdown.

    Args:
        app: FastAPI application instance (unused but required by protocol).

    Yields:
        None — yields control to request handlers.
    """
    await init_engine()
    yield
    engine = get_engine()
    await engine.dispose()


app = FastAPI(
    title="Vistarae UserFunction",
    description="Tenant profile, preferences, and GDPR deletion microservice.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register RFC 7807 problem details exception handlers.
add_problem_details_handlers(app)

# ── Route registration ────────────────────────────────────────────────────
# Routes are imported lazily to prevent import-time DB connections.
from services.user.routes import auth as auth_routes  # noqa: E402
from services.user.routes import me as me_routes  # noqa: E402
from services.user.routes import preferences as preferences_routes  # noqa: E402

app.include_router(me_routes.router, prefix="/api/users", tags=["user-profile"])
app.include_router(
    preferences_routes.router, prefix="/api/users", tags=["user-preferences"]
)
app.include_router(me_routes.router, tags=["user-profile"])
app.include_router(preferences_routes.router, tags=["user-preferences"])
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])

# ── AWS Lambda serverless entry point ────────────────────────────────────
# lifespan="off" is required because Lambda invocations do not support the
# ASGI lifespan protocol; connection management is handled by the lifespan
# context manager above for local and container deployments.
lambda_handler = Mangum(app, lifespan="off")
