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

"""AdminFunction FastAPI microservice application.

Standalone ASGI application exposing administrative governance routes under
/api/admin. Deployed as an AWS Lambda function via Mangum (Constitution
Principle 2). Serverless entry point: lambda_handler = Mangum(app, lifespan='off').
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
    """Manages connection pool lifecycle for AdminFunction.

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
    title="Vistarae AdminFunction",
    description="Administrative governance, telemetry metrics, and tenant control microservice.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register RFC 7807 problem details exception handlers.
add_problem_details_handlers(app)

# ── Route registration ────────────────────────────────────────────────────
from services.admin.routes import controls, metrics, users  # noqa: E402

app.include_router(metrics.router, prefix="/api/admin", tags=["admin-metrics"])
app.include_router(users.router, prefix="/api/admin", tags=["admin-users"])
app.include_router(controls.router, prefix="/api/admin", tags=["admin-controls"])
app.include_router(metrics.router, tags=["admin-metrics"])
app.include_router(users.router, tags=["admin-users"])
app.include_router(controls.router, tags=["admin-controls"])

# ── AWS Lambda serverless entry point ────────────────────────────────────
lambda_handler = Mangum(app, lifespan="off")
