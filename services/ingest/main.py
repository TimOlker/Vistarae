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

"""IngestFunction FastAPI microservice application (T-018).

Provides bulk CSV upload, asynchronous job progress tracking, duplicate triage,
and dual-probe health endpoints.
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

from services.ingest.routes import health as health_routes
from services.ingest.routes import jobs as jobs_routes
from services.ingest.routes import triage as triage_routes
from services.ingest.routes import upload as upload_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages connection pool lifecycle for IngestFunction."""
    await init_engine()
    yield
    engine = get_engine()
    await engine.dispose()


app = FastAPI(
    title="Vistarae IngestFunction",
    description="Asynchronous Ingestion Pipeline and Batch Processing Gateway.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register RFC 7807 problem details exception handlers
add_problem_details_handlers(app)

# Include routers
app.include_router(health_routes.router)
app.include_router(upload_routes.router)
app.include_router(jobs_routes.router)
app.include_router(triage_routes.router)


# Serverless entrypoint
lambda_handler = Mangum(app, lifespan="off")
