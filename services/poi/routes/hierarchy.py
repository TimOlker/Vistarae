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

"""Candidate parent POI search endpoint for hierarchical selection (T-011).

Provides typeahead parent candidate lookup with recursive CTE descendant
exclusion to prevent cyclic hierarchy graphs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import User
from vistarae_core.schemas.poi import ParentPOICandidate
from vistarae_core.services.hierarchy import HierarchyService

from services.poi.dependencies import get_current_user

router = APIRouter(tags=["hierarchy"])


@router.get("/pois/parents", response_model=list[ParentPOICandidate])
async def get_parent_poi_candidates(
    query: str | None = Query(
        default=None, description="Prefix or substring query to filter candidate names"
    ),
    exclude_poi_id: UUID | None = Query(
        default=None, description="Active POI to exclude with its descendants"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum candidate records"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ParentPOICandidate]:
    """Retrieves candidate parent POIs excluding the active POI and all its descendants."""
    hierarchy_service = HierarchyService(session)
    candidates = await hierarchy_service.get_candidate_parents(
        user_id=current_user.id,
        exclude_poi_id=exclude_poi_id,
        query=query,
        limit=limit,
    )
    return [ParentPOICandidate(**c) for c in candidates]
