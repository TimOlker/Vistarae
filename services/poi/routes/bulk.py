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

"""Bulk POI mutations: Editing, Tagging, List curation, and Deletion endpoints (T-028 / REQ-MAIN-026 to REQ-MAIN-035).

Implements:
- POST /pois/bulk-edit: Atomic bulk mutation of up to 500 POIs
- POST /pois/bulk-tags: Bulk attach or detach tags
- POST /pois/bulk-lists: Bulk attach or detach lists
- POST /pois/bulk-delete: Atomic bulk deletion of up to 500 POIs
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import IPOIRepository
from vistarae_core.schemas.poi import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    BulkEditRequest,
    BulkListsRequest,
    BulkOperationResponse,
    BulkTagsRequest,
)

from services.poi.dependencies import get_current_user, get_poi_repo

router = APIRouter(tags=["bulk"])


@router.post("/pois/bulk-edit", response_model=BulkOperationResponse)
async def bulk_edit(
    req: BulkEditRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> BulkOperationResponse:
    """Applies bulk mutations across up to 500 POIs atomically in a single transaction (REQ-MAIN-026 to REQ-MAIN-035)."""
    action_str = req.action.value if hasattr(req.action, "value") else str(req.action)
    count = await poi_repo.bulk_edit(
        user_id=current_user.id,
        poi_ids=req.poi_ids,
        action=action_str,
        payload=req.payload.model_dump(),
    )
    return BulkOperationResponse(modified_count=count)


@router.post("/pois/bulk-tags", response_model=BulkOperationResponse)
async def bulk_tags(
    req: BulkTagsRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> BulkOperationResponse:
    """Attaches or detaches multiple tags across target POIs in a single transaction."""
    if req.action == "attach":
        count = await poi_repo.bulk_attach_tags(
            user_id=current_user.id,
            poi_ids=req.poi_ids,
            tag_ids=req.tag_ids,
        )
    else:
        count = await poi_repo.bulk_detach_tags(
            user_id=current_user.id,
            poi_ids=req.poi_ids,
            tag_ids=req.tag_ids,
        )
    return BulkOperationResponse(modified_count=count)


@router.post("/pois/bulk-lists", response_model=BulkOperationResponse)
async def bulk_lists(
    req: BulkListsRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> BulkOperationResponse:
    """Attaches or detaches multiple curated list memberships in a single transaction."""
    if req.action == "attach":
        count = await poi_repo.bulk_attach_lists(
            user_id=current_user.id,
            poi_ids=req.poi_ids,
            list_ids=req.list_ids,
        )
    else:
        count = await poi_repo.bulk_detach_lists(
            user_id=current_user.id,
            poi_ids=req.poi_ids,
            list_ids=req.list_ids,
        )
    return BulkOperationResponse(modified_count=count)


@router.post("/pois/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete(
    req: BulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> BulkDeleteResponse:
    """Deletes multiple POIs in a single atomic transaction (REQ-MAIN-034, REQ-MAIN-035)."""
    count = await poi_repo.bulk_delete(
        poi_ids=req.poi_ids,
        user_id=current_user.id,
    )
    return BulkDeleteResponse(deleted_count=count)
