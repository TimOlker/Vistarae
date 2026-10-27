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

"""Atomic POI merge service executing referential re-parenting and field synthesis (T-023)."""

import contextlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.domain.entities import POI, TagEntity
from vistarae_core.domain.exceptions import CyclicHierarchyError, POINotFoundError
from vistarae_core.domain.value_objects import AddressRecord, VisitState, WGS84Point
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi import POIResponse, TagResponse
from vistarae_core.schemas.poi_merge import POIMergeRequest, POIMergeResponse
from vistarae_core.services.address_normalizer import AddressNormalizer
from vistarae_core.services.hierarchy import HierarchyService


def _entity_to_poi_response(poi: POI, tags: list[TagEntity] | None = None) -> POIResponse:
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
        estimated_visit_time_notes=getattr(poi, "estimated_visit_time_notes", None),
        source_type=getattr(poi, "source_type", None),
        source_value=getattr(poi, "source_value", None),
        enrichment_status=poi.enrichment_status,
        lat=lat,
        lon=lon,
        created_at=poi.created_at or datetime.now(UTC),
        updated_at=poi.updated_at or datetime.now(UTC),
    )


class MergeService:
    """Orchestrates atomic synthesis of POI attributes and dependent foreign re-parenting."""

    def __init__(
        self,
        session: AsyncSession,
        poi_repo: IPOIRepository,
        tag_repo: ITagRepository,
    ) -> None:
        self._session = session
        self._poi_repo = poi_repo
        self._tag_repo = tag_repo

    async def merge_pois(self, user_id: UUID, req: POIMergeRequest) -> POIMergeResponse:  # noqa: C901
        """Executes atomic merge of source into target POI under tenant isolation."""
        if req.use_source_for and req.source_poi_id is not None:
            from vistarae_core.ports.repositories import MergeResolutionRule

            rule = MergeResolutionRule(
                target_poi_id=req.target_poi_id,
                source_poi_id=req.source_poi_id,
                use_source_for=req.use_source_for,
                merge_tags=req.merge_tags,
            )
            merged = await self._poi_repo.merge_pois(user_id=user_id, rule=rule)
            tags = await self._tag_repo.get_tags_for_poi(merged.id)
            return POIMergeResponse(
                id=merged.id,
                target_poi=_entity_to_poi_response(merged, tags),
                deleted_source_poi_id=req.source_poi_id,
            )

        # 1. Target verification
        target = await self._poi_repo.get_by_id(req.target_poi_id, user_id)
        if target is None:
            raise POINotFoundError(str(req.target_poi_id))

        # 2. Source verification (if source_poi_id provided)
        source: POI | None = None
        if req.source_poi_id is not None:
            if req.source_poi_id == req.target_poi_id:
                raise ValueError("Source POI and Target POI cannot be the same")
            source = await self._poi_repo.get_by_id(req.source_poi_id, user_id)
            if source is None:
                raise POINotFoundError(str(req.source_poi_id))

        # 3. Apply scalar values
        scalars = req.selected_scalars or {}
        if req.use_source_for and source is not None:
            for field_name in req.use_source_for:
                if hasattr(source, field_name):
                    setattr(target, field_name, getattr(source, field_name))

        if "name" in scalars and scalars["name"]:
            target.name = str(scalars["name"]).strip()
        if "description" in scalars:
            target.description = scalars["description"]
        if "recommended_duration_hours" in scalars:
            val = scalars["recommended_duration_hours"]
            target.recommended_duration_hours = float(val) if val is not None else None
        if "recommended_visit_days" in scalars:
            val = scalars["recommended_visit_days"]
            target.recommended_visit_days = int(val) if val is not None else 1
        if "estimated_visit_time_notes" in scalars:
            target.estimated_visit_time_notes = scalars["estimated_visit_time_notes"]
        if "source_type" in scalars:
            target.source_type = scalars["source_type"]
        if "source_value" in scalars:
            target.source_value = scalars["source_value"]
        if "official_url" in scalars:
            target.official_url = scalars["official_url"]
        if "wiki_url" in scalars:
            target.wiki_url = scalars["wiki_url"]
        if "want_to_visit_again" in scalars:
            target.want_to_visit_again = bool(scalars["want_to_visit_again"])
        if "rating" in scalars:
            val = scalars["rating"]
            target.rating = int(val) if val is not None else None
        if "visit_state" in scalars and scalars["visit_state"]:
            target.visit_state = scalars["visit_state"]

        # Coordinates
        lat_val = scalars.get("latitude") if "latitude" in scalars else scalars.get("lat")
        lng_val = (
            scalars.get("longitude")
            if "longitude" in scalars
            else (scalars.get("lon") if "lon" in scalars else scalars.get("lng"))
        )
        if lat_val is not None and lng_val is not None:
            target.geom = WGS84Point(lat=float(lat_val), lon=float(lng_val))
        elif lat_val is not None and target.geom:
            target.geom = WGS84Point(lat=float(lat_val), lon=target.geom.lon)
        elif lng_val is not None and target.geom:
            target.geom = WGS84Point(lat=target.geom.lat, lon=float(lng_val))

        # Parent POI validation and assignment
        if "parent_poi_id" in scalars:
            raw_parent = scalars["parent_poi_id"]
            if raw_parent:
                parent_id = UUID(str(raw_parent))
                if parent_id == target.id or (req.source_poi_id and parent_id == req.source_poi_id):
                    raise CyclicHierarchyError(str(target.id), str(parent_id))
                hierarchy_service = HierarchyService(self._session)
                await hierarchy_service.validate_no_cycle(user_id, target.id, parent_id)
                target.parent_poi_id = parent_id
            else:
                target.parent_poi_id = None

        # 4. Apply set values
        sets = dict(req.selected_sets or {})
        if req.merge_tags and source is not None and "tags" not in sets:
            source_tags = await self._tag_repo.get_tags_for_poi(source.id)
            if source_tags:
                target_tags = await self._tag_repo.get_tags_for_poi(target.id)
                combined = list({t.name for t in (target_tags + source_tags)})
                sets["tags"] = combined

        # Addresses
        if "addresses" in sets and sets["addresses"] is not None:
            raw_records: list[AddressRecord] = []
            for item in sets["addresses"]:
                if isinstance(item, dict):
                    raw_records.append(
                        AddressRecord(
                            street=item.get("street"),
                            city=item.get("city"),
                            state_province=item.get("state_province"),
                            country=item.get("country") or "",
                            postal_code=item.get("postal_code"),
                        )
                    )
                elif isinstance(item, AddressRecord):
                    raw_records.append(item)
            norm_records = AddressNormalizer.normalize_addresses(raw_records)
            # De-duplicate addresses
            unique_addrs: list[AddressRecord] = []
            seen = set()
            for a in norm_records:
                k = (a.street, a.city, a.state_province, a.country, a.postal_code)
                if k not in seen:
                    seen.add(k)
                    unique_addrs.append(a)
            target.addresses = unique_addrs
            if unique_addrs:
                first = unique_addrs[0]
                target.address = first.street
                target.city = first.city
                target.states = [first.state_province] if first.state_province else []
                target.countries = [first.country]

        # Directory paths
        if "directory_paths" in sets and sets["directory_paths"] is not None:
            target.directory_paths = list(
                dict.fromkeys([p.strip() for p in sets["directory_paths"] if p and str(p).strip()])
            )

        # Image URLs
        if "image_urls" in sets and sets["image_urls"] is not None:
            target.image_urls = list(
                dict.fromkeys([u.strip() for u in sets["image_urls"] if u and str(u).strip()])
            )

        # Visited dates
        if "visited_dates" in sets and sets["visited_dates"] is not None:
            dates = [str(d).strip() for d in sets["visited_dates"] if d and str(d).strip()]
            target.visited_dates = sorted(list(set(dates)))

        # Update visit lifecycle flags
        target.already_visited = bool(target.visited_dates and len(target.visited_dates) > 0)
        target.visit_pending = bool(not target.visited_dates or target.want_to_visit_again)
        if target.already_visited:
            if target.want_to_visit_again:
                target.visit_state = VisitState.VISITED_RETURN
            else:
                target.visit_state = VisitState.VISITED_DO_NOT_RETURN
        else:
            target.visit_state = VisitState.NOT_VISITED

        # Update target in repository
        updated_target = await self._poi_repo.update(target)

        # Tags reconciliation
        if "tags" in sets and sets["tags"] is not None:
            tag_names = sorted(
                list({str(t).strip().lower() for t in sets["tags"] if t and str(t).strip()})
            )
            current_tags = await self._tag_repo.get_tags_for_poi(target.id)
            resolved_tags: list[TagEntity] = []
            for name in tag_names:
                resolved_tags.append(await self._tag_repo.get_or_create(user_id, name))
            if current_tags:
                await self._poi_repo.bulk_detach_tags(
                    user_id, [target.id], [t.id for t in current_tags]
                )
            if resolved_tags:
                await self._poi_repo.bulk_attach_tags(
                    user_id, [target.id], [t.id for t in resolved_tags]
                )

        # 5. Referential Re-parenting & Source Deletion
        reparented_itineraries = 0
        reparented_lists = 0
        reparented_children = 0

        if req.source_poi_id is not None:
            source_id = req.source_poi_id

            # a. Itinerary items:
            res_itin = await self._session.execute(
                text("UPDATE itinerary_items SET poi_id = :target_id WHERE poi_id = :source_id"),
                {"target_id": target.id, "source_id": source_id},
            )
            reparented_itineraries = res_itin.rowcount or 0

            # b. Curated list memberships (poi_lists):
            await self._session.execute(
                text("""
                    DELETE FROM poi_lists
                    WHERE poi_id = :source_id
                      AND list_id IN (SELECT list_id FROM poi_lists WHERE poi_id = :target_id)
                """),
                {"target_id": target.id, "source_id": source_id},
            )
            res_lists = await self._session.execute(
                text("UPDATE poi_lists SET poi_id = :target_id WHERE poi_id = :source_id"),
                {"target_id": target.id, "source_id": source_id},
            )
            reparented_lists = res_lists.rowcount or 0

            # c. Scanned paths (photo scraper):
            with contextlib.suppress(Exception):
                await self._session.execute(
                    text("UPDATE scanned_paths SET poi_id = :target_id WHERE poi_id = :source_id"),
                    {"target_id": target.id, "source_id": source_id},
                )

            # d. Child POIs in hierarchy:
            res_child = await self._session.execute(
                text("""
                    UPDATE pois
                    SET parent_poi_id = :target_id
                    WHERE parent_poi_id = :source_id AND user_id = :user_id
                """),
                {"target_id": target.id, "source_id": source_id, "user_id": user_id},
            )
            reparented_children = res_child.rowcount or 0

            # e. Detach all tags from source_poi before delete:
            await self._session.execute(
                text("DELETE FROM poi_tags WHERE poi_id = :source_id"),
                {"source_id": source_id},
            )

            # f. Delete source POI from DB:
            await self._poi_repo.delete(source_id, user_id)

        # 6. Build response
        final_tags = await self._tag_repo.get_tags_for_poi(target.id)
        refreshed_target = await self._poi_repo.get_by_id(target.id, user_id)
        target_entity = refreshed_target if refreshed_target is not None else updated_target

        return POIMergeResponse(
            id=target.id,
            target_poi=_entity_to_poi_response(target_entity, final_tags),
            deleted_source_poi_id=req.source_poi_id,
            reparented_itinerary_items_count=reparented_itineraries,
            reparented_list_memberships_count=reparented_lists,
            reparented_child_pois_count=reparented_children,
        )
