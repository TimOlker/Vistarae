# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unified Local Development ASGI Gateway (T-015, T-050).

Mounts standalone microservices (UserFunction, AdminFunction) and exposes
dual-probe health endpoints with unified Starlette LIFO middleware pipeline and CORS.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session, get_engine, init_engine
from vistarae_core.middleware.errors import add_problem_details_handlers
from vistarae_core.middleware.idempotency import IdempotencyMiddleware
from vistarae_core.middleware.rate_limit import RateLimitMiddleware
from vistarae_core.middleware.telemetry import TelemetryMiddleware
from vistarae_core.schemas.errors import ProblemDetails

from services.admin.main import app as admin_app
from services.user.main import app as user_app
from services.user.routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and clean connection pool disposal.

    Args:
        app: FastAPI gateway application instance.

    Yields:
        None — yields control to request handling pipeline.
    """
    await init_engine()
    yield
    engine = get_engine()
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
    """Zero-IO liveness probe for container alive checks.

    Returns:
        Dict with status 'alive'.
    """
    return {"status": "alive"}


@gateway.get("/health/ready", status_code=status.HTTP_200_OK)
async def health_ready(
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """Database readiness probe executing SELECT 1.

    Args:
        session: Active database session.

    Returns:
        200 OK with status 'ready' or 503 Service Unavailable if database is unreachable.
    """
    try:
        await session.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready"},
        )
    except Exception as exc:
        problem = ProblemDetails(
            type="https://errors.vistarae.com/database-unreachable",
            title="Database Unreachable",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            instance="/health/ready",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )


# 3. Mount microservices
gateway.mount("/api/users", user_app)
gateway.mount("/api/admin", admin_app)
gateway.include_router(auth_router, prefix="/api/auth", tags=["auth"])

# 4. Middleware registration:
# Under Starlette's LIFO execution model:
# TelemetryMiddleware (outermost) -> RateLimitMiddleware -> IdempotencyMiddleware (innermost)
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
