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

"""Endpoint for atomic POI field-by-field merge and referential re-parenting (T-024).

Implements REQ-MERGE-005 and REQ-MERGE-006 with tenant isolation and RFC 7807 errors.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import User
from vistarae_core.domain.exceptions import CyclicHierarchyError, POINotFoundError
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi_merge import POIMergeRequest, POIMergeResponse

from services.poi.dependencies import get_current_user, get_poi_repo, get_tag_repo
from services.poi.services.merge_service import MergeService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["merge"])


@router.post(
    "/pois/merge",
    response_model=POIMergeResponse,
    status_code=status.HTTP_200_OK,
    summary="Atomically merge source POI into target POI and delete source",
)
async def merge_pois_endpoint(
    req: POIMergeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> POIMergeResponse:
    """Executes atomic merge of source POI into target POI.

    Re-parents all dependent itinerary_items, poi_list_memberships,
    scanned_paths, and child POIs before deleting the source POI.
    """
    logger.info(
        "MSG   |-> Requesting POI merge: source=%s, target=%s for user=%s",
        req.source_poi_id,
        req.target_poi_id,
        current_user.id,
    )
    merge_service = MergeService(session, poi_repo, tag_repo)
    try:
        response = await merge_service.merge_pois(user_id=current_user.id, req=req)
        logger.info(
            "MSG   |<- POI merge completed: target=%s, deleted_source=%s, reparented_itin=%d, reparented_lists=%d, reparented_children=%d",
            response.target_poi.id,
            response.deleted_source_poi_id,
            response.reparented_itinerary_items_count,
            response.reparented_list_memberships_count,
            response.reparented_child_pois_count,
        )
        return response
    except POINotFoundError as exc:
        logger.warning("POI merge rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CyclicHierarchyError as exc:
        logger.warning("POI merge cyclic hierarchy rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        logger.warning("POI merge validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
