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

"""Dual-probe health endpoints for container liveness and dependency readiness (T-017).

Provides:
- GET /health/live: Zero-IO container liveness probe (REQ-INGEST-012)
- GET /health/ready: Dependency readiness checking database and SQS (REQ-INGEST-011)
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.ports.queue import IQueuePort
from vistarae_core.schemas.errors import ProblemDetails

from services.ingest.dependencies import get_queue_port

router = APIRouter(tags=["health"])


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def health_live() -> dict[str, str]:
    """Zero-IO container liveness probe.

    Returns:
        Dict with status 'alive'.
    """
    return {"status": "alive"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def health_ready(
    session: AsyncSession = Depends(get_db_session),
    queue_port: IQueuePort = Depends(get_queue_port),
) -> JSONResponse:
    """Readiness probe checking database connectivity (SELECT 1) and SQS availability.

    Args:
        session: Active SQLAlchemy database session.
        queue_port: Active queue adapter port.

    Returns:
        200 OK if both database and queue are reachable; 503 ProblemDetails otherwise.
    """
    # 1. Database check
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        problem = ProblemDetails(
            type="https://errors.vistarae.com/database-unreachable",
            title="Database Unreachable",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity check failed: {exc}",
            instance="/health/ready",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    # 2. Queue check
    queue_name = os.getenv("INGEST_QUEUE_NAME", "vistarae-ingest-local")
    try:
        # Verify queue accessibility via receive_messages or queue resolve
        await queue_port.receive_messages(queue_name, max_messages=1, wait_time_seconds=0)
    except Exception as exc:
        problem = ProblemDetails(
            type="https://errors.vistarae.com/queue-unreachable",
            title="Queue Unreachable",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Queue connectivity check failed: {exc}",
            instance="/health/ready",
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready", "database": "healthy", "queue": "healthy"},
    )
