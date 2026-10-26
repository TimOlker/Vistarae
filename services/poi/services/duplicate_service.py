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

"""Scale-aware early duplicate and parent-child nesting triage engine (T-035).

Implements the dual-threshold heuristic distinguishing:
- POTENTIAL_DUPLICATE: Distance <= scale-adjusted radius AND trigram similarity >= 0.60 (recommends 'abort' or 'proceed')
- NEARBY_PARENT: Distance <= scale-adjusted radius AND trigram similarity < 0.60 with existing POI at larger scale (recommends 'make_child')
- UNIQUE_LOCATION: No proximate matches within scale radius (recommends 'proceed')

Includes circular parenting prevention to verify candidate parent is not an existing descendant POI.
Enforces REQ-EXT-030, REQ-EXT-031, and REQ-EXT-032.
"""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import UUID

from geoalchemy2.types import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.tables import POITable
from vistarae_core.domain.exceptions import CyclicHierarchyError
from vistarae_core.schemas.scraping import DeduplicationVerdictSchema
from vistarae_core.services.hierarchy import HierarchyService

from services.poi.scraping.scale_classifier import ScaleClassifier

logger = logging.getLogger(__name__)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two coordinates in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def trigram_similarity(s1: str, s2: str) -> float:
    """Computes character trigram similarity score (0.0 to 1.0) matching pg_trgm behavior."""
    s1_clean = "  " + s1.strip().lower() + " "
    s2_clean = "  " + s2.strip().lower() + " "
    if len(s1_clean) < 3 or len(s2_clean) < 3:
        return 1.0 if s1_clean.strip() == s2_clean.strip() else 0.0
    t1 = {s1_clean[i : i + 3] for i in range(len(s1_clean) - 2)}
    t2 = {s2_clean[i : i + 3] for i in range(len(s2_clean) - 2)}
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return round(intersection / union, 4) if union > 0 else 0.0


class DuplicateTriageService:
    """Evaluates early duplicate collision and parent-child nesting opportunities."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        hierarchy_service: HierarchyService | None = None,
    ) -> None:
        self._session = session
        self._hierarchy_service = hierarchy_service or (
            HierarchyService(session) if session is not None else None
        )

    async def _check_circular_parenting(
        self,
        user_id: UUID,
        current_poi_id: UUID | None,
        candidate_parent_id: UUID,
    ) -> bool:
        """Verifies candidate parent is not the POI itself or an existing descendant."""
        if current_poi_id is None:
            return False
        if current_poi_id == candidate_parent_id:
            return True
        if self._hierarchy_service is not None:
            try:
                await self._hierarchy_service.validate_no_cycle(
                    user_id=user_id,
                    poi_id=current_poi_id,
                    proposed_parent_id=candidate_parent_id,
                )
                return False
            except CyclicHierarchyError:
                logger.warning(
                    "MSG   |<- Circular parenting rejected: %s is a descendant of %s",
                    candidate_parent_id,
                    current_poi_id,
                )
                return True
        return False

    async def _fetch_proximate_records(
        self,
        user_id: UUID,
        name: str,
        latitude: float,
        longitude: float,
        in_memory_candidates: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        proximate_records: list[dict[str, Any]] = []

        # 1. If in-memory candidate list provided (unit testing)
        if in_memory_candidates is not None:
            for item in in_memory_candidates:
                poi_lat = item.get("latitude")
                poi_lon = item.get("longitude")
                if poi_lat is None or poi_lon is None:
                    continue
                dist = haversine_distance_meters(latitude, longitude, poi_lat, poi_lon)
                sim = trigram_similarity(name, item.get("name", ""))
                proximate_records.append(
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "description": item.get("description", ""),
                        "tags": item.get("tags", []),
                        "distance": dist,
                        "similarity": sim,
                    }
                )
            # Sort by distance asc, similarity desc
            proximate_records.sort(key=lambda r: (r["distance"], -r["similarity"]))

        # 2. Query PostGIS database via SQLAlchemy
        elif self._session is not None:
            candidate_point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
            candidate_geog = cast(candidate_point, Geography(geometry_type="POINT", srid=4326))
            max_search_radius = 5000.0  # Macro scale ceiling

            stmt = (
                select(
                    POITable.id,
                    POITable.name,
                    POITable.description,
                    func.ST_Distance(POITable.geom, candidate_geog).label("distance_meters"),
                    func.similarity(POITable.name, name).label("name_similarity"),
                )
                .where(
                    POITable.user_id == user_id,
                    POITable.geom.is_not(None),
                    func.ST_DWithin(POITable.geom, candidate_geog, max_search_radius),
                )
                .order_by(
                    func.ST_Distance(POITable.geom, candidate_geog).asc(),
                )
                .limit(20)
            )
            result = await self._session.execute(stmt)
            for row in result.all():
                proximate_records.append(
                    {
                        "id": row.id,
                        "name": str(row.name),
                        "description": str(row.description or ""),
                        "tags": [],
                        "distance": float(row.distance_meters),
                        "similarity": float(row.name_similarity),
                    }
                )
        return proximate_records

    async def evaluate_candidate(
        self,
        user_id: UUID,
        name: str,
        latitude: float | None,
        longitude: float | None,
        description: str = "",
        tags: list[str] | None = None,
        current_poi_id: UUID | None = None,
        in_memory_candidates: list[dict[str, Any]] | None = None,
    ) -> DeduplicationVerdictSchema:
        """Executes scale-aware dual-threshold triage against existing user POIs within 500ms.

        Args:
            user_id: Tenant UUID.
            name: Destination candidate name.
            latitude: Geographic latitude in decimal degrees.
            longitude: Geographic longitude in decimal degrees.
            description: Optional text summary of destination.
            tags: Optional associated tag slugs.
            current_poi_id: UUID of POI being updated, if applicable.
            in_memory_candidates: Optional list of dicts for testing without live database.

        Returns:
            DeduplicationVerdictSchema with status, scores, candidate info, and recommendation.
        """
        candidate_scale = ScaleClassifier.classify(name, description, tags)

        if latitude is None or longitude is None:
            return DeduplicationVerdictSchema(
                status="UNIQUE_LOCATION",
                scale_classification=candidate_scale,
                recommended_action="proceed",
            )

        proximate_records = await self._fetch_proximate_records(
            user_id=user_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            in_memory_candidates=in_memory_candidates,
        )

        # 3. Evaluate proximate records using dual-threshold heuristic
        best_duplicate: dict[str, Any] | None = None
        best_parent: dict[str, Any] | None = None

        for rec in proximate_records:
            if current_poi_id is not None and rec["id"] == current_poi_id:
                continue

            poi_scale = ScaleClassifier.classify(
                rec["name"],
                rec.get("description", ""),
                rec.get("tags", []),
            )
            dist = rec["distance"]
            sim = rec["similarity"]

            # Scale-adjusted radius for existing POI
            scale_radius = ScaleClassifier.get_radius(poi_scale)

            # Rule 1: POTENTIAL_DUPLICATE
            # Distance <= scale-adjusted radius AND similarity >= 0.60
            if dist <= scale_radius and sim >= 0.60:
                if best_duplicate is None or dist < best_duplicate["distance"]:
                    best_duplicate = {**rec, "poi_scale": poi_scale}
                continue

            # Rule 2: NEARBY_PARENT
            # Distance <= scale-adjusted radius AND similarity < 0.60 AND existing is larger scale
            if (
                dist <= scale_radius
                and sim < 0.60
                and ScaleClassifier.is_larger_scale(poi_scale, candidate_scale)
            ):
                # Verify circular parenting
                is_circular = await self._check_circular_parenting(
                    user_id=user_id,
                    current_poi_id=current_poi_id,
                    candidate_parent_id=rec["id"],
                )
                if not is_circular and (best_parent is None or dist < best_parent["distance"]):
                    best_parent = {**rec, "poi_scale": poi_scale}

        # Prioritize duplicate warning over parent-child suggestion
        if best_duplicate is not None:
            logger.info(
                "MSG   |<- Triage: POTENTIAL_DUPLICATE detected '%s' (dist=%.1fm, sim=%.2f)",
                best_duplicate["name"],
                best_duplicate["distance"],
                best_duplicate["similarity"],
            )
            return DeduplicationVerdictSchema(
                status="POTENTIAL_DUPLICATE",
                distance_meters=round(best_duplicate["distance"], 2),
                similarity_score=round(best_duplicate["similarity"], 4),
                existing_poi_id=best_duplicate["id"],
                existing_poi_name=best_duplicate["name"],
                scale_classification=candidate_scale,
                recommended_action="abort",
            )

        if best_parent is not None:
            logger.info(
                "MSG   |<- Triage: NEARBY_PARENT detected '%s' (scale=%s > %s, dist=%.1fm, sim=%.2f)",
                best_parent["name"],
                best_parent["poi_scale"],
                candidate_scale,
                best_parent["distance"],
                best_parent["similarity"],
            )
            return DeduplicationVerdictSchema(
                status="NEARBY_PARENT",
                distance_meters=round(best_parent["distance"], 2),
                similarity_score=round(best_parent["similarity"], 4),
                existing_poi_id=best_parent["id"],
                existing_poi_name=best_parent["name"],
                scale_classification=candidate_scale,
                recommended_action="make_child",
            )

        # Rule 3: UNIQUE_LOCATION
        return DeduplicationVerdictSchema(
            status="UNIQUE_LOCATION",
            scale_classification=candidate_scale,
            recommended_action="proceed",
        )
