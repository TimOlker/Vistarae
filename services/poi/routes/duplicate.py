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

"""Endpoint for pre-save duplicate collision probing (T-028).

Evaluates candidate collisions using PostGIS geodesic distance (<= 200m)
and trigram name similarity (>= 0.60) under strict tenant isolation.
Implements REQ-SAVE-002 and REQ-SAVE-004.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from vistarae_core.domain.entities import POI, TagEntity, User
from vistarae_core.domain.value_objects import WGS84Point
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi import POIResponse, TagResponse
from vistarae_core.schemas.poi_duplicate import (
    DuplicateCandidateItem,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)

from services.poi.dependencies import get_current_user, get_poi_repo, get_tag_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["duplicate"])


def _poi_to_response(poi: POI, tags: list[TagEntity] | None = None) -> POIResponse:
    """Helper to convert domain POI to POIResponse."""
    lat = poi.geom.lat if poi.geom else None
    lon = poi.geom.lon if poi.geom else None
    return POIResponse(
        id=poi.id,
        user_id=poi.user_id,
        parent_poi_id=poi.parent_poi_id,
        parent_poi_name=getattr(poi, "parent_poi_name", None),
        name=poi.name,
        description=poi.description,
        addresses=poi.addresses or [],
        address=poi.address,
        city=poi.city,
        states=poi.states,
        countries=poi.countries,
        official_url=poi.official_url,
        wiki_url=poi.wiki_url,
        image_urls=poi.image_urls or [],
        directory_paths=poi.directory_paths or [],
        creation_metadata=poi.creation_metadata,
        visit_state=poi.visit_state,
        visited_dates=poi.visited_dates or [],
        already_visited=poi.already_visited,
        visit_pending=poi.visit_pending,
        want_to_visit_again=poi.want_to_visit_again,
        rating=poi.rating,
        tags=[TagResponse(id=t.id, name=t.name) for t in (tags or [])],
        estimated_cost=poi.estimated_cost,
        pricing_unit=poi.pricing_unit,
        recommended_duration_hours=poi.recommended_duration_hours,
        recommended_visit_days=poi.recommended_visit_days,
        source_type=getattr(poi, "source_type", None),
        source_value=getattr(poi, "source_value", None),
        enrichment_status=poi.enrichment_status,
        lat=lat,
        lon=lon,
        created_at=poi.created_at or datetime.now(UTC),
        updated_at=poi.updated_at or datetime.now(UTC),
    )


@router.post(
    "/pois/check-duplicate",
    response_model=DuplicateCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Probe duplicate collision before saving POI draft",
)
async def check_duplicate_poi(
    req: DuplicateCheckRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> DuplicateCheckResponse:
    """Evaluates whether draft name and coordinates collide with an existing POI.

    Proximity threshold: geodesic distance <= 200m.
    Similarity threshold: trigram similarity >= 0.60.
    """
    logger.info(
        "MSG   |-> Checking duplicate for name='%s' at (%f, %f) user=%s",
        req.name,
        req.latitude,
        req.longitude,
        current_user.id,
    )
    point = WGS84Point(lat=req.latitude, lon=req.longitude)
    matches = await poi_repo.find_potential_duplicates(
        user_id=current_user.id,
        name=req.name.strip(),
        point=point,
        radius_meters=200.0,
        similarity_threshold=0.60,
    )

    # Filter out active POI to prevent self-collision
    filtered_matches = [
        m for m in matches if req.exclude_poi_id is None or m.existing_poi.id != req.exclude_poi_id
    ]

    if not filtered_matches:
        logger.info("MSG   |<- Duplicate check: no collisions detected.")
        return DuplicateCheckResponse(is_duplicate=False, candidate=None)

    best_match = filtered_matches[0]
    candidate_poi = best_match.existing_poi
    tags = await tag_repo.get_tags_for_poi(candidate_poi.id)
    poi_read_resp = _poi_to_response(candidate_poi, tags)

    logger.info(
        "MSG   |<- Duplicate collision detected with POI id=%s name='%s' distance=%.1fm similarity=%.2f",
        candidate_poi.id,
        candidate_poi.name,
        best_match.distance_meters,
        best_match.name_similarity,
    )

    return DuplicateCheckResponse(
        is_duplicate=True,
        candidate=DuplicateCandidateItem(
            poi_id=candidate_poi.id,
            name=candidate_poi.name,
            distance_meters=best_match.distance_meters,
            name_similarity=best_match.name_similarity,
            poi=poi_read_resp,
        ),
    )
