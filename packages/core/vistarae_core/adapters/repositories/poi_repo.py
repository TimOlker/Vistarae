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

import contextlib
import json
import re
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

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
    ListTable,
    POIListTable,
    POITable,
    POITagTable,
    TagTable,
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
    AddressRecord,
    BoundingBox,
    EnrichmentStatus,
    MergeResolutionRule,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import IPOIRepository
from vistarae_core.services.address_normalizer import AddressNormalizer
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


def _row_to_poi(row: POITable, parent_name: str | None = None) -> POI:
    """Maps a POITable ORM row to pure POI domain entity."""
    addresses: list[AddressRecord] = []
    raw_addrs = getattr(row, "addresses", None)
    if raw_addrs:
        for addr in raw_addrs:
            if isinstance(addr, dict):
                with contextlib.suppress(Exception):
                    addresses.append(AddressRecord(**addr))
            elif isinstance(addr, AddressRecord):
                addresses.append(addr)

    city = row.city
    if not city and addresses:
        for addr in addresses:
            if addr.city:
                city = addr.city
                break

    states = list(row.states) if row.states else []
    if addresses:
        extracted = [a.state_province for a in addresses if a.state_province]
        states = list(dict.fromkeys(extracted))

    countries = list(row.countries) if row.countries else []
    if not countries and addresses:
        extracted = [a.country for a in addresses if a.country and a.country != "Unknown"]
        if extracted:
            countries = list(dict.fromkeys(extracted))

    address = row.address
    if not address and addresses:
        for addr in addresses:
            if addr.street:
                address = addr.street
                break

    return POI(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        geom=_extract_wgs84_point(row.geom),
        parent_poi_id=row.parent_poi_id,
        parent_poi_name=parent_name,
        description=row.description,
        reason_to_visit=getattr(row, "reason_to_visit", None),
        address=address,
        city=city,
        states=states,
        countries=countries,
        addresses=addresses,
        official_url=row.official_url,
        wiki_url=row.wiki_url,
        image_urls=list(row.image_urls) if row.image_urls else [],
        directory_paths=list(row.directory_paths) if row.directory_paths else [],
        creation_metadata=dict(row.creation_metadata) if row.creation_metadata else {},
        visit_state=VisitState(row.visit_state),
        visited_dates=list(row.visited_dates) if row.visited_dates else [],
        want_to_visit_again=getattr(row, "want_to_visit_again", False),
        already_visited=getattr(row, "already_visited", False),
        visit_pending=getattr(row, "visit_pending", True),
        source_type=getattr(row, "source_type", "Manual"),
        source_value=getattr(row, "source_value", None),
        rating=row.rating,
        estimated_cost=row.estimated_cost,
        pricing_unit=row.pricing_unit,
        recommended_duration_hours=row.recommended_duration_hours,
        recommended_visit_days=row.recommended_visit_days,
        estimated_visit_time_notes=row.estimated_visit_time_notes,
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
        serialized_addresses = (
            [
                addr.model_dump() if hasattr(addr, "model_dump") else dict(addr)
                for addr in poi.addresses
            ]
            if poi.addresses
            else []
        )

        resolved_city = poi.city
        if not resolved_city and poi.addresses:
            for addr in poi.addresses:
                if addr.city:
                    resolved_city = addr.city
                    break
        resolved_address = poi.address
        if not resolved_address and poi.addresses:
            for addr in poi.addresses:
                if addr.street:
                    resolved_address = addr.street
                    break

        row = POITable(
            id=poi.id,
            user_id=poi.user_id,
            parent_poi_id=poi.parent_poi_id,
            name=poi.name,
            description=poi.description,
            reason_to_visit=poi.reason_to_visit,
            address=resolved_address,
            city=resolved_city,
            states=poi.states,
            countries=poi.countries,
            addresses=serialized_addresses,
            source_type=poi.source_type.value
            if hasattr(poi.source_type, "value")
            else str(poi.source_type),
            source_value=poi.source_value,
            official_url=poi.official_url,
            wiki_url=poi.wiki_url,
            image_urls=poi.image_urls,
            directory_paths=poi.directory_paths,
            creation_metadata=poi.creation_metadata,
            visit_state=poi.visit_state.value
            if hasattr(poi.visit_state, "value")
            else str(poi.visit_state),
            visited_dates=poi.visited_dates,
            want_to_visit_again=poi.want_to_visit_again,
            already_visited=poi.already_visited,
            visit_pending=poi.visit_pending,
            rating=poi.rating,
            estimated_cost=poi.estimated_cost,
            pricing_unit=poi.pricing_unit,
            recommended_duration_hours=poi.recommended_duration_hours,
            recommended_visit_days=poi.recommended_visit_days,
            estimated_visit_time_notes=poi.estimated_visit_time_notes,
            enrichment_status=poi.enrichment_status.value
            if hasattr(poi.enrichment_status, "value")
            else str(poi.enrichment_status),
            geom=geom_wkt,
            region_geom=poi.region_geom,
            embedding=poi.embedding,
            embedding_md5=poi.embedding_md5,
        )
        self._session.add(row)
        await self._session.flush()
        return _row_to_poi(row, parent_name=poi.parent_poi_name)

    async def get_by_id(self, poi_id: UUID, user_id: UUID) -> POI | None:
        """Retrieves a POI by ID scoped to tenant with resolved parent name."""
        stmt = select(POITable).where(
            POITable.id == poi_id,
            POITable.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        parent_name: str | None = None
        if row.parent_poi_id is not None:
            p_stmt = select(POITable.name).where(
                POITable.id == row.parent_poi_id,
                POITable.user_id == user_id,
            )
            p_res = await self._session.execute(p_stmt)
            parent_name = p_res.scalar_one_or_none()

        return _row_to_poi(row, parent_name=parent_name)

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
        serialized_addresses = (
            [
                addr.model_dump() if hasattr(addr, "model_dump") else dict(addr)
                for addr in poi.addresses
            ]
            if poi.addresses
            else []
        )

        resolved_city = poi.city
        if not resolved_city and poi.addresses:
            for addr in poi.addresses:
                if addr.city:
                    resolved_city = addr.city
                    break
        resolved_address = poi.address
        if not resolved_address and poi.addresses:
            for addr in poi.addresses:
                if addr.street:
                    resolved_address = addr.street
                    break

        row.name = poi.name
        row.parent_poi_id = poi.parent_poi_id
        row.description = poi.description
        row.reason_to_visit = poi.reason_to_visit
        row.address = resolved_address
        row.city = resolved_city
        row.states = poi.states
        row.countries = poi.countries
        row.addresses = serialized_addresses
        row.source_type = (
            poi.source_type.value if hasattr(poi.source_type, "value") else str(poi.source_type)
        )
        row.source_value = poi.source_value
        row.official_url = poi.official_url
        row.wiki_url = poi.wiki_url
        row.image_urls = poi.image_urls
        row.directory_paths = poi.directory_paths
        row.creation_metadata = poi.creation_metadata
        row.visit_state = (
            poi.visit_state.value if hasattr(poi.visit_state, "value") else str(poi.visit_state)
        )
        row.visited_dates = poi.visited_dates
        row.want_to_visit_again = poi.want_to_visit_again
        row.already_visited = poi.already_visited
        row.visit_pending = poi.visit_pending
        row.rating = poi.rating
        row.estimated_cost = poi.estimated_cost
        row.pricing_unit = poi.pricing_unit
        row.recommended_duration_hours = poi.recommended_duration_hours
        row.recommended_visit_days = poi.recommended_visit_days
        row.estimated_visit_time_notes = poi.estimated_visit_time_notes
        row.enrichment_status = (
            poi.enrichment_status.value
            if hasattr(poi.enrichment_status, "value")
            else str(poi.enrichment_status)
        )
        row.geom = geom_wkt
        row.region_geom = poi.region_geom
        row.embedding = poi.embedding
        row.embedding_md5 = poi.embedding_md5

        await self._session.flush()
        return _row_to_poi(row, parent_name=poi.parent_poi_name)

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

    async def bulk_edit(  # noqa: C901
        self,
        user_id: UUID,
        poi_ids: list[UUID],
        action: str,
        payload: dict[str, Any],
    ) -> int:
        """Applies batch mutations across selected POIs atomically in a single transaction (T-027 / REQ-MAIN-027 to REQ-MAIN-035).

        Supports:
        - set_rating (REQ-MAIN-027)
        - add_visit_date with lifecycle calculation (REQ-MAIN-028)
        - set_visit_again with lifecycle calculation (REQ-MAIN-029)
        - add_tag and remove_tag (REQ-MAIN-030, REQ-MAIN-031)
        - add_to_list and remove_from_list (REQ-MAIN-032)
        - update_address strictly modifying addresses[0] and preserving secondary addresses (REQ-MAIN-033)
        """
        if not poi_ids:
            return 0

        # Query all target POIs owned by user
        stmt = select(POITable).where(
            POITable.id.in_(poi_ids),
            POITable.user_id == user_id,
        )
        res = await self._session.execute(stmt)
        pois = list(res.scalars().all())
        if not pois:
            return 0

        now = datetime.now(UTC)

        # 1. Rating
        if action == "set_rating":
            rating_val = payload.get("rating")
            for poi in pois:
                poi.rating = rating_val
                poi.updated_at = now
            await self._session.flush()
            return len(pois)

        # 2. Add Visit Date
        elif action == "add_visit_date":
            visit_date_raw = payload.get("visit_date")
            if not visit_date_raw:
                return 0
            vdate_str = str(visit_date_raw)
            for poi in pois:
                existing_dates = list(poi.visited_dates or [])
                if vdate_str not in existing_dates:
                    existing_dates.append(vdate_str)
                    existing_dates.sort()
                    poi.visited_dates = existing_dates
                poi.already_visited = True
                if poi.want_to_visit_again is True:
                    poi.visit_state = VisitState.VISITED_RETURN.value
                    poi.visit_pending = True
                else:
                    poi.visit_state = VisitState.VISITED_DO_NOT_RETURN.value
                    poi.visit_pending = False
                poi.updated_at = now
            await self._session.flush()
            return len(pois)

        # 3. Set Visit Again
        elif action == "set_visit_again":
            want_again = payload.get("want_to_visit_again")
            for poi in pois:
                poi.want_to_visit_again = want_again
                if poi.already_visited:
                    if want_again is True:
                        poi.visit_state = VisitState.VISITED_RETURN.value
                        poi.visit_pending = True
                    else:
                        poi.visit_state = VisitState.VISITED_DO_NOT_RETURN.value
                        poi.visit_pending = False
                else:
                    poi.visit_state = VisitState.NOT_VISITED.value
                    poi.visit_pending = True
                poi.updated_at = now
            await self._session.flush()
            return len(pois)

        # 4. Add Tag
        elif action == "add_tag":
            tag_name = (payload.get("tag_name") or "").strip()
            if not tag_name:
                return 0
            # Resolve or create tag
            tag_stmt = select(TagTable).where(
                TagTable.user_id == user_id,
                func.lower(TagTable.name) == tag_name.lower(),
            )
            tag = (await self._session.execute(tag_stmt)).scalar_one_or_none()
            if not tag:
                tag = TagTable(id=uuid4(), user_id=user_id, name=tag_name)
                self._session.add(tag)
                await self._session.flush()

            modified = 0
            for poi in pois:
                count_stmt = select(func.count(POITagTable.tag_id)).where(
                    POITagTable.poi_id == poi.id
                )
                cur_count = (await self._session.execute(count_stmt)).scalar() or 0
                exists_stmt = select(POITagTable).where(
                    POITagTable.poi_id == poi.id,
                    POITagTable.tag_id == tag.id,
                )
                if not (await self._session.execute(exists_stmt)).scalar_one_or_none():
                    if cur_count >= 30:
                        raise TagLimitExceededError(cur_count + 1, 30)
                    self._session.add(POITagTable(poi_id=poi.id, tag_id=tag.id))
                    poi.updated_at = now
                    modified += 1
            await self._session.flush()
            return modified

        # 5. Remove Tag
        elif action == "remove_tag":
            tag_name = (payload.get("tag_name") or "").strip()
            if not tag_name:
                return 0
            tag_stmt = select(TagTable).where(
                TagTable.user_id == user_id,
                func.lower(TagTable.name) == tag_name.lower(),
            )
            tag = (await self._session.execute(tag_stmt)).scalar_one_or_none()
            if not tag:
                return 0
            del_stmt = delete(POITagTable).where(
                POITagTable.poi_id.in_([p.id for p in pois]),
                POITagTable.tag_id == tag.id,
            )
            del_res = await self._session.execute(del_stmt)
            for poi in pois:
                poi.updated_at = now
            await self._session.flush()
            return del_res.rowcount or 0

        # 6. Add to List
        elif action == "add_to_list":
            list_id_raw = payload.get("list_id")
            if not list_id_raw:
                return 0
            list_uuid = UUID(str(list_id_raw)) if not isinstance(list_id_raw, UUID) else list_id_raw
            list_stmt = select(ListTable).where(
                ListTable.id == list_uuid,
                ListTable.user_id == user_id,
            )
            target_list = (await self._session.execute(list_stmt)).scalar_one_or_none()
            if not target_list:
                return 0

            modified = 0
            for poi in pois:
                exists_stmt = select(POIListTable).where(
                    POIListTable.poi_id == poi.id,
                    POIListTable.list_id == list_uuid,
                )
                if not (await self._session.execute(exists_stmt)).scalar_one_or_none():
                    self._session.add(POIListTable(poi_id=poi.id, list_id=list_uuid))
                    poi.updated_at = now
                    modified += 1
            await self._session.flush()
            return modified

        # 7. Remove from List
        elif action == "remove_from_list":
            list_id_raw = payload.get("list_id")
            if not list_id_raw:
                return 0
            list_uuid = UUID(str(list_id_raw)) if not isinstance(list_id_raw, UUID) else list_id_raw
            del_stmt = delete(POIListTable).where(
                POIListTable.poi_id.in_([p.id for p in pois]),
                POIListTable.list_id == list_uuid,
            )
            del_res = await self._session.execute(del_stmt)
            for poi in pois:
                poi.updated_at = now
            await self._session.flush()
            return del_res.rowcount or 0

        # 8. Update Address
        elif action == "update_address":
            addr_data = payload.get("address") or {}
            if hasattr(addr_data, "model_dump"):
                addr_data = addr_data.model_dump()

            city = addr_data.get("city")
            state_prov = addr_data.get("state_province")
            country = addr_data.get("country")
            clear_fields = set(addr_data.get("clear_fields") or [])

            norm_country = AddressNormalizer.normalize_country(country) if country else None
            norm_state = (
                AddressNormalizer.normalize_state_province(
                    state_prov, country=norm_country or "Unknown"
                )
                if state_prov
                else None
            )
            norm_city = city.strip() if city else None

            for poi in pois:
                addresses = list(poi.addresses or [])
                if not addresses:
                    primary = {
                        "city": None if "city" in clear_fields else norm_city,
                        "state_province": None if "state_province" in clear_fields else norm_state,
                        "country": None
                        if "country" in clear_fields
                        else (norm_country or "Unknown"),
                    }
                    addresses = [primary]
                else:
                    primary = dict(addresses[0])
                    if "city" in clear_fields:
                        primary["city"] = None
                    elif norm_city is not None:
                        primary["city"] = norm_city

                    if "state_province" in clear_fields:
                        primary["state_province"] = None
                    elif norm_state is not None:
                        primary["state_province"] = norm_state

                    if "country" in clear_fields:
                        primary["country"] = None
                    elif norm_country is not None:
                        primary["country"] = norm_country

                    addresses[0] = primary

                poi.addresses = addresses
                new_states = [a.get("state_province") for a in addresses if a.get("state_province")]
                new_countries = [a.get("country") for a in addresses if a.get("country")]
                poi.states = list(dict.fromkeys(new_states))
                poi.countries = list(dict.fromkeys(new_countries))
                poi.updated_at = now

            await self._session.flush()
            return len(pois)

        return 0

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

        # Fuzzy text search on name, address, city, description, or reason_to_visit
        if text_query:
            pattern = f"%{text_query}%"
            cond = or_(
                POITable.name.ilike(pattern),
                POITable.address.ilike(pattern),
                POITable.city.ilike(pattern),
                POITable.description.ilike(pattern),
                POITable.reason_to_visit.ilike(pattern),
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
            "estimated_visit_time_notes",
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

    async def query_pois_by_predicate(
        self,
        predicate: Any,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[POI], int]:
        """Queries POIs matching an arbitrary compiled AST predicate with pagination."""
        count_stmt = select(func.count()).select_from(POITable).where(predicate)
        total = (await self._session.execute(count_stmt)).scalar_one() or 0

        stmt = (
            select(POITable)
            .where(predicate)
            .order_by(POITable.name.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self._session.execute(stmt)
        pois = [_row_to_poi(r) for r in res.scalars().all()]
        return pois, total
