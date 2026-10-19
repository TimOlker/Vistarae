# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""POIFunction FastAPI microservice application.

Exposes Point of Interest, planar viewport exploration, deduplication,
interactive merge, curated lists, and taxonomy tag endpoints under /api.
Deployed as an AWS Lambda function via Mangum with lifespan='off' (Constitution Principle 2).

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

from services.poi.routes import bulk as bulk_routes
from services.poi.routes import dedup as dedup_routes
from services.poi.routes import lists as list_routes
from services.poi.routes import pois as poi_routes
from services.poi.routes import tags as tag_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages connection pool lifecycle for POIFunction."""
    await init_engine()
    yield
    engine = get_engine()
    await engine.dispose()


app = FastAPI(
    title="Vistarae POIFunction",
    description="Point of Interest Domain and Geospatial Engine microservice.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register RFC 7807 problem details exception handlers
add_problem_details_handlers(app)

# Include routers without prefix for when mounted at /api in gateway
app.include_router(dedup_routes.router)
app.include_router(bulk_routes.router)
app.include_router(list_routes.router)
app.include_router(tag_routes.router)
app.include_router(poi_routes.router)

# Also include with /api prefix for standalone execution or testing
app.include_router(dedup_routes.router, prefix="/api")
app.include_router(bulk_routes.router, prefix="/api")
app.include_router(list_routes.router, prefix="/api")
app.include_router(tag_routes.router, prefix="/api")
app.include_router(poi_routes.router, prefix="/api")

lambda_handler = Mangum(app, lifespan="off")

__all__ = [
    "app",
    "bulk_routes",
    "dedup_routes",
    "lambda_handler",
    "list_routes",
    "poi_routes",
    "tag_routes",
]
