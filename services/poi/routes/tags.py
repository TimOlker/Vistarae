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

"""Taxonomy Tags endpoints (T-034).

Implements:
- GET /tags: List user-scoped tags
- POST /tags: Create or fetch existing tag
- DELETE /tags/{id}: Delete user tag
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from vistarae_core.domain.entities import User
from vistarae_core.ports.repositories import ITagRepository
from vistarae_core.schemas.poi import TagCreateRequest, TagResponse

from services.poi.dependencies import get_current_user, get_tag_repo

router = APIRouter(tags=["tags"])


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> list[TagResponse]:
    """Retrieves all taxonomy tags created by the current tenant."""
    tags = await tag_repo.list_by_user(current_user.id)
    return [TagResponse(id=t.id, name=t.name) for t in tags]


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    req: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> TagResponse:
    """Creates a new taxonomy tag or returns existing tag with same name."""
    tag = await tag_repo.get_or_create(current_user.id, req.name)
    return TagResponse(id=tag.id, name=tag.name)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> None:
    """Deletes a taxonomy tag owned by the current tenant."""
    deleted = await tag_repo.delete(tag_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag {tag_id} not found.",
        )
