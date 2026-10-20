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

"""Curated Lists and Collaborative Public Sharing endpoints (T-034).

Implements:
- GET /lists: List user-owned collections
- POST /lists: Create new curated list
- GET /lists/{id}: Retrieve owned list
- PATCH /lists/{id}: Update title, description, or visibility
- DELETE /lists/{id}: Remove user list
- GET /lists/{id}/shared: Public access to shared curated list and member POIs
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from vistarae_core.domain.entities import ListEntity, User
from vistarae_core.ports.repositories import (
    IListRepository,
    IPOIRepository,
    ITagRepository,
)
from vistarae_core.schemas.poi import (
    ListCreateRequest,
    ListResponse,
    ListUpdateRequest,
    SharedListResponse,
)

from services.poi.dependencies import (
    get_current_user,
    get_list_repo,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.routes.pois import _poi_to_response

router = APIRouter(tags=["lists"])


def _list_to_response(list_entity: ListEntity) -> ListResponse:
    """Maps domain ListEntity to ListResponse schema."""
    return ListResponse(
        id=list_entity.id,
        user_id=list_entity.user_id,
        title=list_entity.title,
        description=list_entity.description,
        is_public=list_entity.is_public,
        created_at=list_entity.created_at or datetime.now(UTC),
        updated_at=list_entity.updated_at or datetime.now(UTC),
    )


@router.get("/lists", response_model=list[ListResponse])
async def list_user_lists(
    current_user: User = Depends(get_current_user),
    list_repo: IListRepository = Depends(get_list_repo),
) -> list[ListResponse]:
    """Retrieves all curated lists owned by the current tenant."""
    lists = await list_repo.list_by_user(current_user.id)
    return [_list_to_response(item) for item in lists]


@router.post("/lists", response_model=ListResponse, status_code=status.HTTP_201_CREATED)
async def create_list(
    req: ListCreateRequest,
    current_user: User = Depends(get_current_user),
    list_repo: IListRepository = Depends(get_list_repo),
) -> ListResponse:
    """Creates a new curated list owned by the current tenant."""
    entity = ListEntity(
        id=uuid4(),
        user_id=current_user.id,
        title=req.title,
        description=req.description,
        is_public=req.is_public,
    )
    created = await list_repo.create(entity)
    return _list_to_response(created)


@router.get("/lists/{list_id}/shared", response_model=SharedListResponse)
async def get_shared_list(
    list_id: UUID,
    list_repo: IListRepository = Depends(get_list_repo),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> SharedListResponse:
    """Public read-only endpoint for shared lists and member POIs (no authentication required)."""
    list_entity = await list_repo.get_by_id(list_id, user_id=None)
    if list_entity is None or not list_entity.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shared list {list_id} not found or is private.",
        )

    pois, _ = await poi_repo.list_pois(
        user_id=list_entity.user_id,
        list_id=list_id,
        limit=200,
    )
    tags_map = await tag_repo.get_tags_for_pois([p.id for p in pois])
    poi_responses = [_poi_to_response(p, tags_map.get(p.id, [])) for p in pois]

    return SharedListResponse(list=_list_to_response(list_entity), pois=poi_responses)


@router.get("/lists/{list_id}", response_model=ListResponse)
async def get_list(
    list_id: UUID,
    current_user: User = Depends(get_current_user),
    list_repo: IListRepository = Depends(get_list_repo),
) -> ListResponse:
    """Retrieves a single curated list by ID."""
    list_entity = await list_repo.get_by_id(list_id, user_id=current_user.id)
    if list_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"List {list_id} not found.",
        )
    return _list_to_response(list_entity)


@router.patch("/lists/{list_id}", response_model=ListResponse)
async def update_list(
    list_id: UUID,
    req: ListUpdateRequest,
    current_user: User = Depends(get_current_user),
    list_repo: IListRepository = Depends(get_list_repo),
) -> ListResponse:
    """Updates title, description, or visibility of an owned list."""
    existing = await list_repo.get_by_id(list_id, user_id=current_user.id)
    if existing is None or existing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"List {list_id} not found.",
        )

    if req.title is not None:
        existing.title = req.title
    if req.description is not None:
        existing.description = req.description
    if req.is_public is not None:
        existing.is_public = req.is_public

    updated = await list_repo.update(existing)
    return _list_to_response(updated)


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(
    list_id: UUID,
    current_user: User = Depends(get_current_user),
    list_repo: IListRepository = Depends(get_list_repo),
) -> None:
    """Deletes an owned curated list."""
    deleted = await list_repo.delete(list_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"List {list_id} not found.",
        )
