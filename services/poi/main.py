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

"""POIFunction FastAPI microservice application.

Exposes Point of Interest, planar viewport exploration, deduplication,
interactive merge, curated lists, taxonomy tag, and AI Trip Planner endpoints under /api.
Deployed as an AWS Lambda function via Mangum with lifespan='off' (Constitution Principle 2).

Serverless entry point:
    lambda_handler = Mangum(app, lifespan='off')
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from vistarae_core.adapters.db.session import (
    get_engine,
    get_session_factory,
    init_engine,
)
from vistarae_core.adapters.repositories.itinerary_repo import (
    SqlAlchemyItineraryRepository,
)
from vistarae_core.middleware.errors import add_problem_details_handlers

from services.poi.routes import bulk as bulk_routes
from services.poi.routes import dedup as dedup_routes
from services.poi.routes import itineraries as itinerary_routes
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
    description="Point of Interest Domain, Geospatial Engine, and AI Trip Planner microservice.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS Middleware (REQ-SAM-008a, Constitution Principle 6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.cloudfront\.net|chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_spend_killswitch(request: Request, call_next):
    """Halts execution with RFC 7807 503 Service Unavailable if SpendKillSwitch is active."""
    # Allow health checks even during emergency killswitch
    path = request.url.path
    if path in ("/health/ready", "/health/live", "/api/health/ready", "/api/health/live"):
        return await call_next(request)

    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = SqlAlchemyItineraryRepository(session)
            setting = await repo.get_system_setting("spend_killswitch")
            if setting and setting.get("killswitch_active"):
                return JSONResponse(
                    status_code=503,
                    content={
                        "type": "https://api.vistarae.com/errors/service-unavailable",
                        "title": "Service Unavailable",
                        "status": 503,
                        "detail": "Emergency spend killswitch is active. API compute is temporarily halted.",
                        "instance": request.url.path,
                    },
                    headers={"Content-Type": "application/problem+json"},
                )
    except Exception:
        # Fall through safely if db connection or session unavailable during bootstrap
        pass

    return await call_next(request)


# Register RFC 7807 problem details exception handlers
add_problem_details_handlers(app)

# Include routers without prefix for when mounted at /api in gateway
app.include_router(dedup_routes.router)
app.include_router(bulk_routes.router)
app.include_router(list_routes.router)
app.include_router(tag_routes.router)
app.include_router(poi_routes.router)
app.include_router(itinerary_routes.router)

# Also include with /api prefix for standalone execution or testing
app.include_router(dedup_routes.router, prefix="/api")
app.include_router(bulk_routes.router, prefix="/api")
app.include_router(list_routes.router, prefix="/api")
app.include_router(tag_routes.router, prefix="/api")
app.include_router(poi_routes.router, prefix="/api")
app.include_router(itinerary_routes.router, prefix="/api")


@app.get("/health/live")
@app.get("/api/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe returning 200 OK."""
    return {"status": "live"}


@app.get("/health/ready")
@app.get("/api/health/ready")
async def health_ready() -> dict[str, str]:
    """Readiness probe returning 200 OK."""
    return {"status": "ready"}


lambda_handler = Mangum(app, lifespan="off")

__all__ = [
    "app",
    "bulk_routes",
    "dedup_routes",
    "itinerary_routes",
    "lambda_handler",
    "list_routes",
    "poi_routes",
    "tag_routes",
]
