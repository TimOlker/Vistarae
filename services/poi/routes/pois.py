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

"""Point of Interest CRUD, Planar Viewport Exploration, and Semantic Search endpoints (T-012, T-024, T-029).

Implements:
- GET /pois: Planar viewport bounding-box exploration, multi-facet filtering, semantic similarity search
- POST /pois: Geocoding enrichment, hierarchy validation, 30-tag ceiling, Gemini vector embedding
- GET /pois/{id}: Fetch POI with attached tags
- PATCH /pois/{id}: Partial updates, cycle-safe re-parenting, embedding re-computation
- DELETE /pois/{id}: Tenant-scoped deletion
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.domain.entities import POI, TagEntity, User
from vistarae_core.domain.exceptions import (
    CyclicHierarchyError,
    POINotFoundError,
    TagLimitExceededError,
)
from vistarae_core.domain.value_objects import (
    AddressRecord,
    BoundingBox,
    EnrichmentStatus,
    SourceType,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.geocoding import IGeocodingPort
from vistarae_core.ports.repositories import IPOIRepository, ITagRepository
from vistarae_core.schemas.poi import (
    POICreateRequest,
    POIListResponse,
    POIQueryRequest,
    POIResponse,
    POIUpdateRequest,
    TagResponse,
)
from vistarae_core.services.address_normalizer import AddressNormalizer
from vistarae_core.services.embedding_sanitizer import (
    build_composite_text,
    compute_embedding_md5,
)
from vistarae_core.services.hierarchy import HierarchyService

from services.poi.dependencies import (
    get_current_user,
    get_embedding_port,
    get_geocoding_port,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.services.filter_evaluator import FilterQueryTranslator

router = APIRouter(tags=["pois"])


def _poi_to_response(poi: POI, tags: list[TagEntity] | None = None) -> POIResponse:
    """Maps a pure domain POI entity and its tags to POIResponse schema."""
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
        image_urls=poi.image_urls,
        directory_paths=poi.directory_paths,
        creation_metadata=poi.creation_metadata,
        visit_state=poi.visit_state,
        visited_dates=poi.visited_dates,
        want_to_visit_again=poi.want_to_visit_again,
        already_visited=poi.already_visited,
        visit_pending=poi.visit_pending,
        source_type=poi.source_type,
        source_value=poi.source_value,
        rating=poi.rating,
        estimated_cost=poi.estimated_cost,
        pricing_unit=poi.pricing_unit,
        recommended_duration_hours=poi.recommended_duration_hours,
        recommended_visit_days=poi.recommended_visit_days,
        estimated_visit_time_notes=getattr(poi, "estimated_visit_time_notes", None),
        enrichment_status=poi.enrichment_status,
        lon=poi.geom.lon,
        lat=poi.geom.lat,
        similarity_score=getattr(poi, "similarity_score", None),
        tags=[TagResponse(id=t.id, name=t.name) for t in (tags or [])],
        created_at=poi.created_at or datetime.now(UTC),
        updated_at=poi.updated_at or datetime.now(UTC),
    )


def _parse_bbox(bbox_str: str | None) -> BoundingBox | None:
    """Parses minLng,minLat,maxLng,maxLat into a BoundingBox value object."""
    if not bbox_str:
        return None
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
        if len(parts) != 4:
            raise ValueError(
                "Bounding box must have 4 comma-separated values: minLng,minLat,maxLng,maxLat"
            )
        min_lon, min_lat, max_lon, max_lat = parts
        return BoundingBox(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid bounding box parameter: {exc}",
        ) from exc


@router.get("/pois", response_model=POIListResponse)
async def list_pois(
    bbox: str | None = Query(default=None, description="Planar bbox (minLng,minLat,maxLng,maxLat)"),
    list_id: UUID | None = Query(default=None),
    tag_ids: str | None = Query(default=None, description="Comma-separated tag UUIDs"),
    state: str | None = Query(default=None, description="State/province JSONB containment"),
    country: str | None = Query(default=None, description="Country JSONB containment"),
    visit_state: VisitState | None = Query(default=None),
    hierarchy: str = Query(default="all", enum=["all", "root_only", "children_only"]),
    parent_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Text filter for name/address"),
    semantic_q: str | None = Query(default=None, description="Natural language semantic search"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
    embedding_port: IEmbeddingPort = Depends(get_embedding_port),
) -> POIListResponse:
    """Queries POIs with planar viewport bounding box, taxonomic filters, and semantic search."""
    parsed_bbox = _parse_bbox(bbox)

    parsed_tag_ids: list[UUID] | None = None
    if tag_ids:
        try:
            parsed_tag_ids = [UUID(t.strip()) for t in tag_ids.split(",") if t.strip()]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid tag_ids UUID format: {exc}",
            ) from exc

    semantic_vector: list[float] | None = None
    if semantic_q and semantic_q.strip():
        semantic_vector = await embedding_port.generate_embedding(semantic_q.strip())

    pois, total = await poi_repo.list_pois(
        user_id=current_user.id,
        bbox=parsed_bbox,
        list_id=list_id,
        tag_ids=parsed_tag_ids,
        state=state,
        country=country,
        visit_state=visit_state,
        hierarchy=hierarchy,
        parent_id=parent_id,
        text_query=q,
        semantic_vector=semantic_vector,
        limit=limit,
        offset=offset,
    )

    tags_map = await tag_repo.get_tags_for_pois([p.id for p in pois])
    items = [_poi_to_response(p, tags_map.get(p.id, [])) for p in pois]

    return POIListResponse(items=items, total=total, limit=limit, offset=offset)


def _resolve_create_addresses(
    req: POICreateRequest,
    address: str | None,
    states: list[str],
    countries: list[str],
) -> tuple[list[AddressRecord], list[str], list[str], str | None]:
    """Resolves and normalizes addresses and falls back to geo-derived values."""
    addresses: list[AddressRecord] = []
    if req.addresses:
        addresses = AddressNormalizer.normalize_addresses(req.addresses)
    elif address or countries:
        addresses = [
            AddressNormalizer.normalize_address(
                AddressRecord(
                    street=address,
                    city=req.city,
                    state_province=states[0] if states else None,
                    country=countries[0] if countries else "Unknown",
                )
            )
        ]

    resolved_states = states or [a.state_province for a in addresses if a.state_province]
    resolved_countries = countries or [
        a.country for a in addresses if a.country and a.country != "Unknown"
    ]
    resolved_address = address or (
        addresses[0].street if addresses and addresses[0].street else None
    )

    return addresses, resolved_states, resolved_countries, resolved_address


@router.post("/pois", response_model=POIResponse, status_code=status.HTTP_201_CREATED)
async def create_poi(
    req: POICreateRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
    geocoding_port: IGeocodingPort = Depends(get_geocoding_port),
    embedding_port: IEmbeddingPort = Depends(get_embedding_port),
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    """Creates a new Point of Interest with geocoding and vector embedding."""
    # 1. Validate parent if provided
    if req.parent_poi_id is not None:
        parent = await poi_repo.get_by_id(req.parent_poi_id, current_user.id)
        if parent is None:
            raise POINotFoundError(f"Parent POI {req.parent_poi_id} not found")

    # 2. Geocoding enrichment
    address = req.address
    states = req.states or []
    countries = req.countries or []
    enrichment_status = EnrichmentStatus.PARTIAL

    try:
        if req.address:
            geo_res = await geocoding_port.forward_geocode(req.address)
        else:
            geo_res = await geocoding_port.reverse_geocode(req.lat, req.lon)

        enrichment_status = geo_res.status
        if not address and geo_res.formatted_address:
            address = geo_res.formatted_address
        if not states and geo_res.states:
            states = geo_res.states
        if not countries and geo_res.countries:
            countries = geo_res.countries
    except Exception:
        enrichment_status = EnrichmentStatus.PARTIAL

    # 3. Resolve tags (max 30 tags)
    resolved_tags: list[TagEntity] = []
    if req.tag_names:
        unique_names = sorted(
            list({name.strip().lower() for name in req.tag_names if name.strip()})
        )
        if len(unique_names) > 30:
            raise TagLimitExceededError(len(unique_names), 30)

        for name in unique_names:
            tag = await tag_repo.get_or_create(current_user.id, name)
            resolved_tags.append(tag)

    # 4. Generate Gemini embedding
    sorted_tag_names = sorted([t.name for t in resolved_tags])
    sanitized_text = build_composite_text(
        name=req.name,
        description=req.description,
        address=address,
        city=req.city,
        states=states,
        countries=countries,
        tags=sorted_tag_names,
    )
    embedding_vector = await embedding_port.generate_embedding(sanitized_text)
    md5_hash = compute_embedding_md5(sanitized_text)

    addresses, states, countries, address = _resolve_create_addresses(
        req, address, states, countries
    )
    source_type = req.source_type or SourceType.MANUAL
    source_value = req.source_value

    # 5. Persist POI aggregate
    poi_id = uuid4()
    poi = POI(
        id=poi_id,
        user_id=current_user.id,
        name=req.name,
        geom=WGS84Point(lon=req.lon, lat=req.lat),
        parent_poi_id=req.parent_poi_id,
        description=req.description,
        address=address,
        city=req.city,
        states=states,
        countries=countries,
        addresses=addresses,
        source_type=source_type,
        source_value=source_value,
        official_url=req.official_url,
        wiki_url=req.wiki_url,
        image_urls=req.image_urls,
        visit_state=req.visit_state,
        rating=req.rating,
        estimated_cost=req.estimated_cost,
        pricing_unit=req.pricing_unit,
        recommended_duration_hours=req.recommended_duration_hours,
        recommended_visit_days=req.recommended_visit_days,
        estimated_visit_time_notes=req.estimated_visit_time_notes,
        enrichment_status=enrichment_status,
        embedding=embedding_vector,
        embedding_md5=md5_hash,
    )

    created_poi = await poi_repo.create(poi)

    # 6. Attach tags
    if resolved_tags:
        await poi_repo.bulk_attach_tags(
            current_user.id, [created_poi.id], [t.id for t in resolved_tags]
        )

    return _poi_to_response(created_poi, resolved_tags)


@router.get("/pois/{poi_id}", response_model=POIResponse)
async def get_poi(
    poi_id: UUID,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
) -> POIResponse:
    """Retrieves a single POI by ID with its attached tags."""
    poi = await poi_repo.get_by_id(poi_id, current_user.id)
    if poi is None:
        raise POINotFoundError(str(poi_id))

    tags = await tag_repo.get_tags_for_poi(poi_id)
    return _poi_to_response(poi, tags)


def _apply_poi_updates(poi: POI, req: POIUpdateRequest) -> None:
    """Applies non-null scalar fields from update request to domain entity."""
    fields = (
        "name",
        "description",
        "address",
        "city",
        "states",
        "countries",
        "official_url",
        "wiki_url",
        "image_urls",
        "directory_paths",
        "visit_state",
        "visited_dates",
        "want_to_visit_again",
        "source_type",
        "source_value",
        "rating",
        "estimated_cost",
        "pricing_unit",
        "recommended_duration_hours",
        "recommended_visit_days",
        "estimated_visit_time_notes",
    )
    for field in fields:
        val = getattr(req, field, None)
        if val is not None:
            setattr(poi, field, val)

    # Coordinate update
    if req.latitude is not None and req.longitude is not None:
        poi.geom = WGS84Point(lat=req.latitude, lon=req.longitude)
    elif req.latitude is not None:
        poi.geom = WGS84Point(lat=req.latitude, lon=poi.geom.lon)
    elif req.longitude is not None:
        poi.geom = WGS84Point(lat=poi.geom.lat, lon=req.longitude)

    # Address normalization if addresses provided
    if req.addresses is not None:
        normalized = AddressNormalizer.normalize_addresses(req.addresses)
        poi.addresses = normalized
        if req.states is None:
            extracted_states = [a.state_province for a in normalized if a.state_province]
            if extracted_states:
                poi.states = list(dict.fromkeys(extracted_states))
        if req.countries is None:
            extracted_countries = [a.country for a in normalized if a.country]
            if extracted_countries:
                poi.countries = list(dict.fromkeys(extracted_countries))


@router.patch("/pois/{poi_id}", response_model=POIResponse)
async def update_poi(
    poi_id: UUID,
    req: POIUpdateRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
    embedding_port: IEmbeddingPort = Depends(get_embedding_port),
    session: AsyncSession = Depends(get_db_session),
) -> POIResponse:
    """Updates attributes of an existing POI with cycle prevention and embedding re-sync."""
    poi = await poi_repo.get_by_id(poi_id, current_user.id)
    if poi is None:
        raise POINotFoundError(str(poi_id))

    # Cycle detection and validation on parent change
    if "parent_poi_id" in req.model_fields_set:
        if req.parent_poi_id is not None:
            if req.parent_poi_id == poi_id:
                raise CyclicHierarchyError(
                    poi_id=str(poi_id), proposed_parent_id=str(req.parent_poi_id)
                )
            parent = await poi_repo.get_by_id(req.parent_poi_id, current_user.id)
            if parent is None:
                raise POINotFoundError(f"Parent POI {req.parent_poi_id} not found")
            hierarchy_service = HierarchyService(session)
            await hierarchy_service.validate_no_cycle(
                user_id=current_user.id,
                poi_id=poi_id,
                proposed_parent_id=req.parent_poi_id,
            )
            poi.parent_poi_id = req.parent_poi_id
        else:
            poi.parent_poi_id = None

    # Update simple scalar fields, coordinates, and addresses
    _apply_poi_updates(poi, req)

    # Tags reconciliation if tags provided
    current_tags = await tag_repo.get_tags_for_poi(poi_id)
    if req.tags is not None:
        unique_names = sorted(list({name.strip().lower() for name in req.tags if name.strip()}))
        if len(unique_names) > 30:
            raise TagLimitExceededError(len(unique_names), 30)

        resolved_tags: list[TagEntity] = []
        for name in unique_names:
            tag = await tag_repo.get_or_create(current_user.id, name)
            resolved_tags.append(tag)

        if current_tags:
            await poi_repo.bulk_detach_tags(current_user.id, [poi_id], [t.id for t in current_tags])
        if resolved_tags:
            await poi_repo.bulk_attach_tags(
                current_user.id, [poi_id], [t.id for t in resolved_tags]
            )
        current_tags = resolved_tags

    # Re-compute embedding if text changed
    sorted_tag_names = sorted([t.name for t in current_tags])
    sanitized_text = build_composite_text(
        name=poi.name,
        description=poi.description,
        address=poi.address,
        city=poi.city,
        states=poi.states,
        countries=poi.countries,
        tags=sorted_tag_names,
    )
    new_md5 = compute_embedding_md5(sanitized_text)

    # Short-circuit: only call Gemini when content checksum changes
    if new_md5 != poi.embedding_md5:
        poi.embedding = await embedding_port.generate_embedding(sanitized_text)
        poi.embedding_md5 = new_md5

    updated_poi = await poi_repo.update(poi)
    return _poi_to_response(updated_poi, current_tags)


@router.delete("/pois/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_poi(
    poi_id: UUID,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
) -> None:
    """Deletes a POI record scoped to current tenant."""
    deleted = await poi_repo.delete(poi_id, current_user.id)
    if not deleted:
        raise POINotFoundError(str(poi_id))


@router.post("/pois/query", response_model=POIListResponse)
async def query_pois(
    request: POIQueryRequest,
    current_user: User = Depends(get_current_user),
    poi_repo: IPOIRepository = Depends(get_poi_repo),
    tag_repo: ITagRepository = Depends(get_tag_repo),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> POIListResponse:
    """Evaluates a structured query tree AST against tenant POIs with optional bounding box."""
    predicate = FilterQueryTranslator.compile(
        query_tree=request.query_tree,
        user_id=current_user.id,
        bbox=request.bbox,
    )
    pois, total = await poi_repo.query_pois_by_predicate(
        predicate=predicate,
        limit=limit,
        offset=offset,
    )
    items: list[POIResponse] = []
    for p in pois:
        tags = await tag_repo.get_tags_for_poi(p.id)
        items.append(_poi_to_response(p, tags))

    return POIListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
