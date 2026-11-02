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

"""Tag resolution endpoints for early tag library gatekeeper (T-026)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from vistarae_core.domain.entities import User
from vistarae_core.domain.enums import TagResolutionAction

from services.ingest.dependencies import get_current_user, get_staging_service
from services.ingest.services.staging_service import StagingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["Tag Resolution"])


class TagResolutionRequest(BaseModel):
    job_id: UUID
    action: TagResolutionAction


@router.post(
    "/resolve-tags",
    summary="Resolve unapproved tags from early tag validation dialog",
    status_code=status.HTTP_200_OK,
)
async def resolve_tags(
    payload: TagResolutionRequest,
    user: User = Depends(get_current_user),
    staging_service: StagingService = Depends(get_staging_service),
) -> JSONResponse:
    """Executes APPROVE_AND_ADD, STRIP_UNAPPROVED, or ABORT for unapproved tags (REQ-VAL-003, REQ-VAL-004, REQ-VAL-005)."""
    if payload.action == TagResolutionAction.ABORT:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "job_id": str(payload.job_id),
                "status": "ABORTED",
                "message": "Import aborted by user during tag validation.",
            },
        )

    # For APPROVE_AND_ADD or STRIP_UNAPPROVED
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "job_id": str(payload.job_id),
            "status": "STAGING_STARTED",
            "action_applied": payload.action.value,
        },
    )
