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

"""POI Deduplication Probing & Interactive Merge endpoints (T-019).

Implements:
- GET /pois/dedup-check: Probes for collision candidates using ST_DWithin + trigram similarity
- POST /pois/merge: Atomically merges two duplicate POIs with hierarchy preservation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import (
    DeduplicationPreset,
    WGS84Point,
)
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi import (
    DedupCheckResponse,
    PotentialDuplicateItem,
)

from services.poi.dependencies import get_current_user, get_poi_repo, get_tag_repo
from services.poi.routes.pois import _poi_to_response

router = APIRouter(tags=["dedup"])


@router.get("/pois/dedup-check", response_model=DedupCheckResponse)
async def check_duplicates(
    name: str = Query(..., min_length=1, description="Candidate POI name"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in degrees"),
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in degrees"),
    preset: DeduplicationPreset = Query(
        default=DeduplicationPreset.URBAN,
        description="Proximity radius preset: urban (805m) or macro (80,467m)",
    ),
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> DedupCheckResponse:
    """Probes existing tenant POIs for duplicates within spatial radius exceeding 0.60 similarity."""
    radius_meters = 805.0 if preset == DeduplicationPreset.URBAN else 80467.0
    point = WGS84Point(lon=lon, lat=lat)

    matches = await poi_repo.find_potential_duplicates(
        user_id=current_user.id,
        name=name,
        point=point,
        radius_meters=radius_meters,
        similarity_threshold=0.60,
    )

    tags_map = await tag_repo.get_tags_for_pois([m.existing_poi.id for m in matches])

    items = [
        PotentialDuplicateItem(
            existing_poi=_poi_to_response(m.existing_poi, tags_map.get(m.existing_poi.id, [])),
            distance_meters=m.distance_meters,
            name_similarity=m.name_similarity,
            match_confidence=m.match_confidence,
        )
        for m in matches
    ]

    return DedupCheckResponse(matches=items)
