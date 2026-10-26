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

"""Taxonomy Tags endpoints (REQ-EXT-001 to REQ-EXT-007, T-013).

Implements:
- GET /api/pois/tags: List user-scoped tags in alphabetical order with slugs, aliases & reference counts
- POST /api/pois/tags: Create tag with slug & aliases (409 on duplicate slug)
- DELETE /api/pois/tags/{tag_id}: Delete tag (409 Conflict with remediation link if in use)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from vistarae_core.domain.entities import TagEntity, User
from vistarae_core.ports.repositories import ITagRepository
from vistarae_core.schemas.errors import ProblemDetails
from vistarae_core.schemas.tag import (
    TagCreateRequest,
    TagInUseProblemDetails,
    TagResponse,
    slugify_tag_name,
)

from services.poi.dependencies import get_current_user, get_tag_repo

router = APIRouter(tags=["tags"])


@router.get("/pois/tags", response_model=list[TagResponse])
@router.get("/tags", response_model=list[TagResponse], include_in_schema=False)
async def list_tags(
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> list[TagResponse]:
    """Retrieves all taxonomy tags for tenant in strict alphabetical order."""
    tags = await tag_repo.list_by_user(current_user.id)
    return [
        TagResponse(
            id=t.id,
            slug=t.slug,
            name=t.name,
            aliases=t.aliases,
            poi_count=t.poi_count,
            created_at=t.created_at,
        )
        for t in tags
    ]


@router.post(
    "/pois/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ProblemDetails, "description": "Tag slug already exists in user library"},
    },
)
@router.post(
    "/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_tag(
    req: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> TagResponse | JSONResponse:
    """Creates a new taxonomy tag with unique slug and search aliases."""
    slug = req.slug or slugify_tag_name(req.name)
    existing = await tag_repo.get_by_slug(current_user.id, slug)
    if existing and isinstance(existing, TagEntity):
        problem = ProblemDetails(
            type="urn:vistarae:error:tag-slug-exists",
            title="Tag slug already exists",
            status=409,
            detail=f"A tag with slug '{slug}' already exists in your library.",
            instance="/api/pois/tags",
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    tag = await tag_repo.create(
        user_id=current_user.id,
        name=req.name.strip(),
        slug=slug,
        aliases=req.aliases or [],
    )
    if not isinstance(tag, TagEntity) and hasattr(tag_repo, "get_or_create"):
        alt_tag = await tag_repo.get_or_create(current_user.id, req.name.strip())
        if isinstance(alt_tag, TagEntity):
            tag = alt_tag

    return TagResponse(
        id=tag.id,
        slug=getattr(tag, "slug", slug),
        name=tag.name,
        aliases=getattr(tag, "aliases", []) or [],
        poi_count=0,
        created_at=getattr(tag, "created_at", None) or datetime.now(UTC),
    )


@router.delete(
    "/pois/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        409: {
            "model": TagInUseProblemDetails,
            "description": "Tag is currently referenced by one or more POIs",
        },
        404: {"model": ProblemDetails, "description": "Tag not found"},
    },
)
@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    include_in_schema=False,
)
async def delete_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> Response:
    """Deletes a taxonomy tag if not referenced by any POIs.

    Enforces referential integrity check: returns RFC 7807 409 Conflict with
    remediation link if referenced by one or more POIs.
    """
    ref_count = await tag_repo.count_referencing_pois(current_user.id, tag_id)
    if isinstance(ref_count, int) and ref_count > 0:
        tag = await tag_repo.get_by_id(current_user.id, tag_id)
        tag_slug = tag.slug if tag else str(tag_id)
        problem = TagInUseProblemDetails(
            detail=f"Cannot delete tag: currently used by {ref_count} POIs.",
            referencing_poi_count=ref_count,
            remediation_filter_url=f"/?filter_tag={tag_slug}",
            instance=f"/api/pois/tags/{tag_id}",
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    deleted = await tag_repo.delete(tag_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag {tag_id} not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
