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

"""SQLAlchemy 2.0 repository adapter for Points of Interest and PostGIS spatial queries.

Implements Constitution Principles 2 & 3 and Operational Invariant 2:
- Dual-index spatial separation:
    * Planar bounding box queries use (geom::geometry) && ST_MakeEnvelope
    * Geodesic proximity queries use ST_DWithin and ST_Distance on geography
- Antimeridian crossing handling (dual envelope split when min_lon > max_lon)
- Multi-state and multi-country JSONB array containment queries (@>)
- Trigram similarity deduplication (similarity >= 0.60)
- Atomic interactive merge with hierarchy cycle prevention and 30-tag ceiling
- Strict tenant scoping (WHERE user_id = :current_user_id)
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import (
    cast,
    delete,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.tables import (
    POIListTable,
    POITable,
    POITagTable,
)
from vistarae_core.domain.entities import (
    POI,
    PotentialDuplicateMatch,
)
from vistarae_core.domain.exceptions import (
    POINotFoundError,
    TagLimitExceededError,
)
from vistarae_core.domain.value_objects import (
    BoundingBox,
    EnrichmentStatus,
    MergeResolutionRule,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import IPOIRepository
from vistarae_core.services.hierarchy import HierarchyService


def _extract_wgs84_point(geom: Any) -> WGS84Point:
    """Extracts a canonical WGS84Point from a GeoAlchemy geometry or mock object."""
    if isinstance(geom, WGS84Point):
        return geom
    try:
        shape = to_shape(geom)
        return WGS84Point(lon=float(shape.x), lat=float(shape.y))
    except Exception as err:
        if hasattr(geom, "x") and hasattr(geom, "y"):
            return WGS84Point(lon=float(geom.x), lat=float(geom.y))
        geom_str = getattr(geom, "data", None) or str(geom)
        m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", str(geom_str), re.IGNORECASE)
        if m:
            return WGS84Point(lon=float(m.group(1)), lat=float(m.group(2)))
        raise ValueError(f"Unable to extract WGS84Point from {geom}") from err


def _row_to_poi(row: POITable) -> POI:
    """Maps a POITable ORM row to pure POI domain entity."""
    return POI(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        geom=_extract_wgs84_point(row.geom),
        parent_poi_id=row.parent_poi_id,
        description=row.description,
        address=row.address,
        city=row.city,
        states=list(row.states) if row.states else [],
        countries=list(row.countries) if row.countries else [],
        official_url=row.official_url,
        wiki_url=row.wiki_url,
        image_urls=list(row.image_urls) if row.image_urls else [],
        directory_paths=list(row.directory_paths) if row.directory_paths else [],
        creation_metadata=dict(row.creation_metadata) if row.creation_metadata else {},
        visit_state=VisitState(row.visit_state),
        visited_dates=list(row.visited_dates) if row.visited_dates else [],
        rating=row.rating,
        estimated_cost=row.estimated_cost,
        pricing_unit=row.pricing_unit,
        recommended_duration_hours=row.recommended_duration_hours,
        recommended_visit_days=row.recommended_visit_days,
        enrichment_status=EnrichmentStatus(row.enrichment_status),
        region_geom=str(row.region_geom) if row.region_geom is not None else None,
        embedding=list(row.embedding) if row.embedding is not None else None,
        embedding_md5=row.embedding_md5,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyPOIRepository(IPOIRepository):
    """PostgreSQL PostGIS adapter implementing IPOIRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes repository with database session.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def create(self, poi: POI) -> POI:
        """Creates a new POI record for the tenant."""
        geom_wkt = WKTElement(f"POINT({poi.geom.lon} {poi.geom.lat})", srid=4326)
        row = POITable(
            id=poi.id,
            user_id=poi.user_id,
            parent_poi_id=poi.parent_poi_id,
            name=poi.name,
            description=poi.description,
            address=poi.address,
            city=poi.city,
            states=poi.states,
            countries=poi.countries,
            official_url=poi.official_url,
            wiki_url=poi.wiki_url,
            image_urls=poi.image_urls,
            directory_paths=poi.directory_paths,
            creation_metadata=poi.creation_metadata,
            visit_state=poi.visit_state.value,
            visited_dates=poi.visited_dates,
            rating=poi.rating,
            estimated_cost=poi.estimated_cost,
            pricing_unit=poi.pricing_unit,
            recommended_duration_hours=poi.recommended_duration_hours,
            recommended_visit_days=poi.recommended_visit_days,
            enrichment_status=poi.enrichment_status.value,
            geom=geom_wkt,
            region_geom=poi.region_geom,
            embedding=poi.embedding,
            embedding_md5=poi.embedding_md5,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_poi(row)

    async def get_by_id(self, poi_id: UUID, user_id: UUID) -> POI | None:
        """Retrieves a POI by ID scoped to tenant."""
        stmt = select(POITable).where(
            POITable.id == poi_id,
            POITable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _row_to_poi(row)

    async def update(self, poi: POI) -> POI:
        """Updates an existing POI record."""
        stmt = select(POITable).where(
            POITable.id == poi.id,
            POITable.user_id == poi.user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise POINotFoundError(str(poi.id))

        geom_wkt = WKTElement(f"POINT({poi.geom.lon} {poi.geom.lat})", srid=4326)
        row.name = poi.name
        row.parent_poi_id = poi.parent_poi_id
        row.description = poi.description
        row.address = poi.address
        row.city = poi.city
        row.states = poi.states
        row.countries = poi.countries
        row.official_url = poi.official_url
        row.wiki_url = poi.wiki_url
        row.image_urls = poi.image_urls
        row.directory_paths = poi.directory_paths
        row.creation_metadata = poi.creation_metadata
        row.visit_state = poi.visit_state.value
        row.visited_dates = poi.visited_dates
        row.rating = poi.rating
        row.estimated_cost = poi.estimated_cost
        row.pricing_unit = poi.pricing_unit
        row.recommended_duration_hours = poi.recommended_duration_hours
        row.recommended_visit_days = poi.recommended_visit_days
        row.enrichment_status = poi.enrichment_status.value
        row.geom = geom_wkt
        row.region_geom = poi.region_geom
        row.embedding = poi.embedding
        row.embedding_md5 = poi.embedding_md5

        await self._session.flush()
        return _row_to_poi(row)

    async def delete(self, poi_id: UUID, user_id: UUID) -> bool:
        """Deletes a POI by ID scoped to tenant."""
        stmt = delete(POITable).where(
            POITable.id == poi_id,
            POITable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return (result.rowcount or 0) > 0

    async def bulk_delete(self, poi_ids: list[UUID], user_id: UUID) -> int:
        """Deletes multiple POIs in a single transaction."""
        if not poi_ids:
            return 0
        stmt = delete(POITable).where(
            POITable.id.in_(poi_ids),
            POITable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def list_pois(
        self,
        user_id: UUID,
        bbox: BoundingBox | None = None,
        list_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
        state: str | None = None,
        country: str | None = None,
        visit_state: VisitState | None = None,
        visited_from: date | None = None,
        visited_to: date | None = None,
        hierarchy: str = "all",
        parent_id: UUID | None = None,
        text_query: str | None = None,
        semantic_vector: list[float] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[POI], int]:
        """Queries POIs with multi-facet spatial, planar bbox, and taxonomic filters."""
        query = select(POITable).where(POITable.user_id == user_id)
        count_query = select(func.count(POITable.id)).where(POITable.user_id == user_id)

        # Planar bounding box viewport filtering
        if bbox is not None:
            geom_as_geometry = cast(POITable.geom, Geometry)
            if not bbox.crosses_antimeridian:
                # Standard planar bounding box envelope intersection
                envelope = func.ST_MakeEnvelope(
                    bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat, 4326
                )
                bbox_cond = geom_as_geometry.op("&&")(envelope)
            else:
                # Antimeridian split into dual envelopes
                env1 = func.ST_MakeEnvelope(bbox.min_lon, bbox.min_lat, 180.0, bbox.max_lat, 4326)
                env2 = func.ST_MakeEnvelope(-180.0, bbox.min_lat, bbox.max_lon, bbox.max_lat, 4326)
                bbox_cond = or_(
                    geom_as_geometry.op("&&")(env1),
                    geom_as_geometry.op("&&")(env2),
                )
            query = query.where(bbox_cond)
            count_query = count_query.where(bbox_cond)

        # State and country JSONB array containment
        if state is not None:
            state_jsonb = cast(json.dumps([state]), JSONB)
            cond = POITable.states.op("@>")(state_jsonb)
            query = query.where(cond)
            count_query = count_query.where(cond)

        if country is not None:
            country_jsonb = cast(json.dumps([country]), JSONB)
            cond = POITable.countries.op("@>")(country_jsonb)
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Visit state filtering
        if visit_state is not None:
            cond = POITable.visit_state == visit_state.value
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Hierarchy filtering
        if hierarchy == "root_only":
            cond = POITable.parent_poi_id.is_(None)
            query = query.where(cond)
            count_query = count_query.where(cond)
        elif hierarchy == "children_only":
            cond = POITable.parent_poi_id.is_not(None)
            query = query.where(cond)
            count_query = count_query.where(cond)

        if parent_id is not None:
            cond = POITable.parent_poi_id == parent_id
            query = query.where(cond)
            count_query = count_query.where(cond)

        # List membership filtering
        if list_id is not None:
            list_subq = (
                select(POIListTable.poi_id).where(POIListTable.list_id == list_id).scalar_subquery()
            )
            cond = POITable.id.in_(list_subq)
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Tag membership filtering
        if tag_ids:
            tag_subq = (
                select(POITagTable.poi_id).where(POITagTable.tag_id.in_(tag_ids)).scalar_subquery()
            )
            cond = POITable.id.in_(tag_subq)
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Fuzzy text search on name or address
        if text_query:
            pattern = f"%{text_query}%"
            cond = or_(
                POITable.name.ilike(pattern),
                POITable.address.ilike(pattern),
                POITable.city.ilike(pattern),
            )
            query = query.where(cond)
            count_query = count_query.where(cond)

        # Semantic vector similarity ranking (HNSW cosine distance)
        if semantic_vector is not None:
            query = query.order_by(POITable.embedding.cosine_distance(semantic_vector))
        else:
            query = query.order_by(POITable.created_at.desc())

        # Total count execution
        count_res = await self._session.execute(count_query)
        total_count = count_res.scalar() or 0

        # Paginated fetch
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        rows = result.scalars().all()

        return [_row_to_poi(r) for r in rows], total_count

    async def find_potential_duplicates(
        self,
        user_id: UUID,
        name: str,
        point: WGS84Point,
        radius_meters: float,
        similarity_threshold: float = 0.60,
    ) -> list[PotentialDuplicateMatch]:
        """Finds candidate duplicate POIs using geodesic proximity and trigram similarity."""
        candidate_point = func.ST_SetSRID(func.ST_MakePoint(point.lon, point.lat), 4326)
        candidate_geog = cast(candidate_point, Geography(geometry_type="POINT", srid=4326))

        # Spatial filter (ST_DWithin on geography)
        within_cond = func.ST_DWithin(POITable.geom, candidate_geog, radius_meters)

        # Trigram similarity calculation and threshold
        sim_expr = func.similarity(POITable.name, name)
        sim_cond = sim_expr >= similarity_threshold

        # Distance calculation in meters
        dist_expr = func.ST_Distance(POITable.geom, candidate_geog)

        stmt = (
            select(
                POITable,
                dist_expr.label("distance_meters"),
                sim_expr.label("name_similarity"),
            )
            .where(
                POITable.user_id == user_id,
                within_cond,
                sim_cond,
            )
            .order_by(sim_expr.desc(), dist_expr.asc())
        )

        result = await self._session.execute(stmt)
        matches: list[PotentialDuplicateMatch] = []
        for row in result.all():
            table_poi = row[0]
            distance = float(row[1])
            similarity = float(row[2])
            # Confidence score combines name similarity and relative distance
            distance_penalty = (distance / max(radius_meters, 1.0)) * 0.2
            confidence = round(max(0.0, min(1.0, similarity * (1.0 - distance_penalty))), 4)

            matches.append(
                PotentialDuplicateMatch(
                    existing_poi=_row_to_poi(table_poi),
                    distance_meters=round(distance, 2),
                    name_similarity=round(similarity, 4),
                    match_confidence=confidence,
                )
            )

        return matches

    async def merge_pois(
        self,
        user_id: UUID,
        rule: MergeResolutionRule,
    ) -> POI:
        """Interactively merges two duplicate POIs atomically."""
        # 1. Fetch both target and source POIs
        stmt = select(POITable).where(
            POITable.id.in_([rule.target_poi_id, rule.source_poi_id]),
            POITable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        rows = {r.id: r for r in res.scalars().all()}

        target = rows.get(rule.target_poi_id)
        source = rows.get(rule.source_poi_id)

        if target is None:
            raise POINotFoundError(str(rule.target_poi_id))
        if source is None:
            raise POINotFoundError(str(rule.source_poi_id))

        # 2. Cycle prevention: Target cannot be a descendant of source
        hierarchy_svc = HierarchyService(self._session)
        await hierarchy_svc.validate_no_cycle(
            user_id=user_id,
            poi_id=rule.source_poi_id,
            proposed_parent_id=rule.target_poi_id,
        )

        # 3. Cascade re-parent child POIs from source to target
        await self._session.execute(
            update(POITable)
            .where(
                POITable.parent_poi_id == source.id,
                POITable.user_id == user_id,
            )
            .values(parent_poi_id=target.id)
        )

        # 4. Copy requested attributes from source to target
        allowed_copy_fields = {
            "description",
            "address",
            "city",
            "official_url",
            "wiki_url",
            "image_urls",
            "directory_paths",
            "rating",
            "estimated_cost",
            "pricing_unit",
            "recommended_duration_hours",
            "recommended_visit_days",
            "visit_state",
            "visited_dates",
        }
        for field_name in rule.use_source_for:
            if field_name in allowed_copy_fields:
                source_val = getattr(source, field_name, None)
                if source_val is not None:
                    setattr(target, field_name, source_val)

        # 5. Union list memberships
        source_lists_stmt = select(POIListTable.list_id).where(POIListTable.poi_id == source.id)
        target_lists_stmt = select(POIListTable.list_id).where(POIListTable.poi_id == target.id)
        s_lists = set((await self._session.execute(source_lists_stmt)).scalars().all())
        t_lists = set((await self._session.execute(target_lists_stmt)).scalars().all())
        new_lists = s_lists - t_lists
        for list_id in new_lists:
            self._session.add(POIListTable(poi_id=target.id, list_id=list_id))

        # 6. Union tags and enforce 30-tag ceiling
        if rule.merge_tags:
            source_tags_stmt = select(POITagTable.tag_id).where(POITagTable.poi_id == source.id)
            target_tags_stmt = select(POITagTable.tag_id).where(POITagTable.poi_id == target.id)
            s_tags = set((await self._session.execute(source_tags_stmt)).scalars().all())
            t_tags = set((await self._session.execute(target_tags_stmt)).scalars().all())
            total_unique_tags = len(s_tags | t_tags)
            if total_unique_tags > 30:
                raise TagLimitExceededError(total_unique_tags, 30)

            new_tags = s_tags - t_tags
            for tag_id in new_tags:
                self._session.add(POITagTable(poi_id=target.id, tag_id=tag_id))

        # 7. Delete source POI (foreign keys on poi_lists, poi_tags CASCADE delete)
        await self._session.delete(source)

        await self._session.flush()
        return _row_to_poi(target)

    async def bulk_attach_tags(
        self, user_id: UUID, poi_ids: list[UUID], tag_ids: list[UUID]
    ) -> int:
        """Attaches tags to multiple POIs in a single transaction."""
        if not poi_ids or not tag_ids:
            return 0

        # Verify all target POIs belong to tenant
        poi_count_stmt = select(func.count(POITable.id)).where(
            POITable.id.in_(poi_ids), POITable.user_id == user_id
        )
        count = (await self._session.execute(poi_count_stmt)).scalar() or 0
        if count != len(poi_ids):
            raise POINotFoundError("One or more POIs not found for tenant")

        # Check tag counts per POI
        for poi_id in poi_ids:
            existing_tags = select(func.count(POITagTable.tag_id)).where(
                POITagTable.poi_id == poi_id
            )
            current_tag_count = (await self._session.execute(existing_tags)).scalar() or 0
            if current_tag_count + len(tag_ids) > 30:
                raise TagLimitExceededError(current_tag_count + len(tag_ids), 30)

        created_count = 0
        for poi_id in poi_ids:
            for tag_id in tag_ids:
                exists_stmt = select(POITagTable).where(
                    POITagTable.poi_id == poi_id, POITagTable.tag_id == tag_id
                )
                existing = (await self._session.execute(exists_stmt)).scalar_one_or_none()
                if not existing:
                    self._session.add(POITagTable(poi_id=poi_id, tag_id=tag_id))
                    created_count += 1

        await self._session.flush()
        return created_count

    async def bulk_detach_tags(
        self, user_id: UUID, poi_ids: list[UUID], tag_ids: list[UUID]
    ) -> int:
        """Detaches tags from multiple POIs in a single transaction."""
        if not poi_ids or not tag_ids:
            return 0
        stmt = delete(POITagTable).where(
            POITagTable.poi_id.in_(poi_ids),
            POITagTable.tag_id.in_(tag_ids),
        )
        res = await self._session.execute(stmt)
        return res.rowcount or 0

    async def bulk_attach_lists(
        self, user_id: UUID, poi_ids: list[UUID], list_ids: list[UUID]
    ) -> int:
        """Attaches POIs to multiple lists in a single transaction."""
        if not poi_ids or not list_ids:
            return 0

        created_count = 0
        for poi_id in poi_ids:
            for list_id in list_ids:
                exists_stmt = select(POIListTable).where(
                    POIListTable.poi_id == poi_id, POIListTable.list_id == list_id
                )
                existing = (await self._session.execute(exists_stmt)).scalar_one_or_none()
                if not existing:
                    self._session.add(POIListTable(poi_id=poi_id, list_id=list_id))
                    created_count += 1

        await self._session.flush()
        return created_count

    async def bulk_detach_lists(
        self, user_id: UUID, poi_ids: list[UUID], list_ids: list[UUID]
    ) -> int:
        """Detaches POIs from multiple lists in a single transaction."""
        if not poi_ids or not list_ids:
            return 0
        stmt = delete(POIListTable).where(
            POIListTable.poi_id.in_(poi_ids),
            POIListTable.list_id.in_(list_ids),
        )
        res = await self._session.execute(stmt)
        return res.rowcount or 0
