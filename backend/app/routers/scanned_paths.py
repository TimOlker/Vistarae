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

"""Endpoints for scanned photo file path management, geocoding previews, and POI association."""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import asc, delete, desc, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import POI, POIAccessPoint, POIListMembership, ScannedPath, User
from app.schemas.scanned_path import (
    AddPhotoFolderRequest,
    AddPhotoFolderResponse,
    BatchGeocodeConfirmRequest,
    BatchGeocodeConfirmResponse,
    BatchGeocodePreviewResponse,
    ConflictingPOIInfo,
    DisassociateAndSplitResponse,
    DisassociateFolderRequest,
    GeocodeCandidateItem,
    InspectLocalPhotoRequest,
    InspectPhotoResponse,
    POIDetailsLookupRequest,
    POIDetailsLookupResponse,
    POIMergeRequest,
    POIMergeResponse,
    ScannedPathBatchGeocodeRequest,
    ScannedPathBatchUpdate,
    ScannedPathEnrichmentResponse,
    ScannedPathListResponse,
    ScannedPathResponse,
    ScannedPathUpdate,
)
from app.services.auth import get_current_user
from app.services.enrichment import lookup_and_enrich_place, resolve_folder_photo_date
from app.services.extraction import sanitize_official_website
from app.services.geocoding import extract_address_components, geocode_query
from app.services.photo_metadata import (
    SUPPORTED_IMAGE_EXTENSIONS,
    extract_photo_metadata_from_bytes,
    extract_photo_metadata_from_path,
)

logger = logging.getLogger("vistarae.api.scanned_paths")

router = APIRouter(prefix="/api/v1", tags=["Scanned Paths"])


@router.get("/scanned-paths", response_model=ScannedPathListResponse)
async def list_scanned_paths(
    status_filter: str | None = Query(None, alias="status"),
    include_hidden: bool = Query(False),
    poi_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("folder_path"),
    sort_order: str = Query("asc"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List scanned file paths with filtering, searching, sorting, and pagination."""
    query = (
        select(ScannedPath, POI.name.label("poi_name"))
        .outerjoin(POI, ScannedPath.poi_id == POI.id)
        .where(ScannedPath.user_id == current_user.id)
    )

    if status_filter and status_filter.strip() and status_filter.lower() != "all":
        query = query.where(func.lower(ScannedPath.status) == status_filter.strip().lower())
    elif not include_hidden and not poi_id:
        query = query.where(func.lower(ScannedPath.status) != "hidden")

    if poi_id:
        poi_record = await db.scalar(
            select(POI).where(POI.id == poi_id, POI.user_id == current_user.id)
        )
        source_url_conditions = []
        if poi_record and poi_record.source_url:
            norm_source = poi_record.source_url.strip().rstrip("\\/")
            if norm_source:
                source_url_conditions.append(
                    func.lower(ScannedPath.folder_path) == norm_source.lower()
                )

        query = query.where(
            or_(
                ScannedPath.poi_id == poi_id,
                ScannedPath.conflict_poi_ids.any(poi_id),
                *source_url_conditions,
            )
        )

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(ScannedPath.folder_path).like(term),
                func.lower(ScannedPath.folder_name).like(term),
                func.lower(ScannedPath.site_name).like(term),
                func.lower(ScannedPath.city).like(term),
                func.lower(ScannedPath.state).like(term),
                func.lower(ScannedPath.country).like(term),
                func.lower(ScannedPath.reasoning).like(term),
                func.lower(POI.name).like(term),
            )
        )

    # Count total matching
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Sorting
    valid_sort_fields = {
        "folder_path": ScannedPath.folder_path,
        "folder_name": ScannedPath.folder_name,
        "status": ScannedPath.status,
        "site_name": ScannedPath.site_name,
        "city": ScannedPath.city,
        "state": ScannedPath.state,
        "country": ScannedPath.country,
        "photo_count": ScannedPath.photo_count,
        "earliest_date": ScannedPath.earliest_date,
        "latest_date": ScannedPath.latest_date,
        "created_at": ScannedPath.created_at,
        "reasoning": ScannedPath.reasoning,
    }
    col = valid_sort_fields.get(sort_by, ScannedPath.folder_path)
    direction = desc(col) if sort_order.lower() == "desc" else asc(col)
    query = query.order_by(direction).offset(offset).limit(limit)

    results = (await db.execute(query)).all()

    # Batch lookup all POI names for conflict IDs and secondary POIs
    all_conflict_ids = set()
    for sp, _ in results:
        if sp.conflict_poi_ids:
            all_conflict_ids.update(sp.conflict_poi_ids)
        if sp.poi_id:
            all_conflict_ids.add(sp.poi_id)

    poi_names_map = {}
    if all_conflict_ids:
        name_rows = (
            await db.execute(select(POI.id, POI.name).where(POI.id.in_(all_conflict_ids)))
        ).all()
        poi_names_map = {row[0]: row[1] for row in name_rows}

    items = []
    for sp, p_name in results:
        conflict_names = []
        if sp.conflict_poi_ids:
            for cid in sp.conflict_poi_ids:
                if cid in poi_names_map:
                    conflict_names.append(poi_names_map[cid])
        # If this folder is queried for a specific poi_id and sp.poi_id != poi_id, include the primary poi name as conflict
        if (
            poi_id
            and sp.poi_id
            and sp.poi_id != poi_id
            and sp.poi_id in poi_names_map
            and poi_names_map[sp.poi_id] not in conflict_names
        ):
            conflict_names.append(poi_names_map[sp.poi_id])

        resp = ScannedPathResponse(
            id=sp.id,
            user_id=sp.user_id,
            poi_id=sp.poi_id,
            poi_name=p_name or (poi_names_map.get(sp.poi_id) if sp.poi_id else None),
            folder_path=sp.folder_path,
            folder_name=sp.folder_name,
            parent_folder=sp.parent_folder,
            status=sp.status,
            site_name=sp.site_name,
            city=sp.city,
            state=sp.state,
            country=sp.country,
            country_code=sp.country_code,
            latitude=sp.latitude,
            longitude=sp.longitude,
            confidence=sp.confidence or "medium",
            reasoning=sp.reasoning,
            photo_count=sp.photo_count or 0,
            earliest_date=sp.earliest_date,
            latest_date=sp.latest_date,
            has_conflict=bool(sp.has_conflict),
            conflict_poi_ids=list(sp.conflict_poi_ids or []),
            conflict_poi_names=conflict_names,
            conflict_note=sp.conflict_note,
            created_at=sp.created_at,
            updated_at=sp.updated_at,
        )
        items.append(resp)

    return ScannedPathListResponse(
        items=items,
        total_count=total_count,
        offset=offset,
        limit=limit,
    )


@router.patch("/scanned-paths/{path_id}", response_model=ScannedPathResponse)
async def update_scanned_path(
    path_id: uuid.UUID,
    payload: ScannedPathUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates fields on an individual scanned path."""
    sp = await db.scalar(
        select(ScannedPath).where(ScannedPath.id == path_id, ScannedPath.user_id == current_user.id)
    )
    if not sp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanned path not found")

    if payload.status is not None:
        sp.status = payload.status
    if payload.site_name is not None:
        sp.site_name = payload.site_name
    if payload.city is not None:
        sp.city = payload.city
    if payload.state is not None:
        sp.state = payload.state
    if payload.country is not None:
        sp.country = payload.country
    if payload.country_code is not None:
        sp.country_code = payload.country_code
    if payload.latitude is not None:
        sp.latitude = payload.latitude
    if payload.longitude is not None:
        sp.longitude = payload.longitude
    if payload.reasoning is not None:
        sp.reasoning = payload.reasoning
    if payload.poi_id is not None:
        sp.poi_id = payload.poi_id

    # If coordinates are present and status is identified, ensure a linked POI exists with matching coordinates
    has_coords = sp.latitude is not None and sp.longitude is not None
    if has_coords and not sp.poi_id and sp.status == "identified":
        new_poi = POI(
            id=uuid.uuid4(),
            user_id=current_user.id,
            created_at=datetime.now(),
            name=payload.site_name or sp.site_name or sp.folder_name,
            name_aliases=[],
            poi_type="site to see",
            visited=True,
            visit_date=sp.earliest_date,
            visit_dates=[sp.earliest_date] if sp.earliest_date else [],
            location=f"SRID=4326;POINT({sp.longitude} {sp.latitude})",
            source_url=sp.folder_path,
            source_type="photo",
            iptc_city=sp.city,
            iptc_province_state=sp.state,
            iptc_country_code=sp.country_code,
        )
        db.add(new_poi)
        await db.flush()
        sp.poi_id = new_poi.id
        sp.status = "identified"
    elif has_coords and sp.poi_id:
        linked_poi = await db.scalar(
            select(POI).where(POI.id == sp.poi_id, POI.user_id == current_user.id)
        )
        if linked_poi and not linked_poi.location:
            linked_poi.location = f"SRID=4326;POINT({sp.longitude} {sp.latitude})"

    await db.commit()
    await db.refresh(sp)

    poi_name = None
    if sp.poi_id:
        poi_name = await db.scalar(select(POI.name).where(POI.id == sp.poi_id))

    return ScannedPathResponse(
        id=sp.id,
        user_id=sp.user_id,
        poi_id=sp.poi_id,
        poi_name=poi_name,
        folder_path=sp.folder_path,
        folder_name=sp.folder_name,
        parent_folder=sp.parent_folder,
        status=sp.status,
        site_name=sp.site_name,
        city=sp.city,
        state=sp.state,
        country=sp.country,
        country_code=sp.country_code,
        latitude=sp.latitude,
        longitude=sp.longitude,
        confidence=sp.confidence or "medium",
        reasoning=sp.reasoning,
        photo_count=sp.photo_count or 0,
        earliest_date=sp.earliest_date,
        latest_date=sp.latest_date,
        created_at=sp.created_at,
        updated_at=sp.updated_at,
    )


@router.post("/scanned-paths/batch-update")
async def batch_update_scanned_paths(
    payload: ScannedPathBatchUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch updates status and/or location (city/state/country) across multiple paths."""
    stmt = select(ScannedPath).where(
        ScannedPath.id.in_(payload.path_ids),
        ScannedPath.user_id == current_user.id,
    )
    records = (await db.scalars(stmt)).all()
    if not records:
        return {"updated_count": 0}

    for sp in records:
        if payload.status:
            if payload.status == "identified" and not sp.poi_id:
                pass  # Cannot mark as identified without a linked POI
            else:
                sp.status = payload.status
        if payload.city is not None:
            sp.city = payload.city
        if payload.state is not None:
            sp.state = payload.state
        if payload.country is not None:
            sp.country = payload.country

    await db.commit()
    return {"updated_count": len(records)}


@router.post("/scanned-paths/batch-geocode", response_model=BatchGeocodePreviewResponse)
async def preview_batch_geocode(
    payload: ScannedPathBatchGeocodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pre-runs Nominatim geocoding on selected paths and checks for collisions before saving."""
    stmt = select(ScannedPath).where(
        ScannedPath.id.in_(payload.path_ids),
        ScannedPath.user_id == current_user.id,
    )
    paths = (await db.scalars(stmt)).all()
    candidates: list[GeocodeCandidateItem] = []

    for sp in paths:
        # Build query string
        parts = [sp.site_name or sp.folder_name]
        if sp.city:
            parts.append(sp.city)
        if sp.state:
            parts.append(sp.state)
        if sp.country:
            parts.append(sp.country)
        query_str = ", ".join([p.strip() for p in parts if p and p.strip()])

        lat, lon, display_name, raw_json = await geocode_query(query_str, db)
        found = lat != 0.0 or lon != 0.0

        _, city_ext, state_ext, country_ext, country_code_ext, _ = (
            extract_address_components(raw_json)
            if raw_json
            else (None, None, None, None, None, None)
        )

        matched_poi_id = None
        matched_poi_name = None
        action_proposed = "create_poi"

        if found:
            # Check PostGIS collision with existing POIs within 500 meters
            collision_query = text("""
                SELECT id, name,
                       ST_Distance(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS dist
                FROM pois
                WHERE location IS NOT NULL
                  AND (user_id = :uid)
                  AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 500)
                ORDER BY dist ASC
                LIMIT 1;
            """)
            match_row = (
                await db.execute(collision_query, {"lng": lon, "lat": lat, "uid": current_user.id})
            ).first()
            if match_row:
                matched_poi_id = match_row[0]
                matched_poi_name = match_row[1]
                action_proposed = "link_poi"
        else:
            action_proposed = "unresolved"

        candidate = GeocodeCandidateItem(
            path_id=sp.id,
            folder_path=sp.folder_path,
            folder_name=sp.folder_name,
            current_site_name=sp.site_name,
            query_used=query_str,
            found=found,
            display_name=display_name,
            latitude=lat if found else None,
            longitude=lon if found else None,
            city=city_ext or sp.city,
            state=state_ext or sp.state,
            country=country_ext or sp.country,
            country_code=country_code_ext or sp.country_code,
            matched_existing_poi_id=matched_poi_id,
            matched_existing_poi_name=matched_poi_name,
            action_proposed=action_proposed,
        )
        candidates.append(candidate)

    return BatchGeocodePreviewResponse(candidates=candidates)


@router.post("/scanned-paths/batch-confirm-geocode", response_model=BatchGeocodeConfirmResponse)
async def confirm_batch_geocode(
    payload: BatchGeocodeConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Applies user-confirmed geocodes, creating or linking POIs and updating path records."""
    updated_count = 0
    created_poi_count = 0
    linked_poi_count = 0

    for item in payload.items:
        if not item.apply:
            continue

        sp = await db.scalar(
            select(ScannedPath).where(
                ScannedPath.id == item.path_id, ScannedPath.user_id == current_user.id
            )
        )
        if not sp:
            continue

        has_coords = item.latitude is not None and item.longitude is not None
        target_poi_id = item.existing_poi_id

        if item.create_new_poi:
            # Create a new POI
            new_poi = POI(
                id=uuid.uuid4(),
                user_id=current_user.id,
                created_at=datetime.now(),
                name=item.site_name or sp.site_name or sp.folder_name,
                name_aliases=[],
                poi_type="site to see",
                visited=True,
                visit_date=sp.earliest_date,
                visit_dates=[sp.earliest_date] if sp.earliest_date else [],
                location=f"SRID=4326;POINT({item.longitude} {item.latitude})"
                if has_coords
                else None,
                source_url=sp.folder_path,
                source_type="photo",
                iptc_city=item.city or sp.city,
                iptc_province_state=item.state or sp.state,
                iptc_country_code=item.country_code or sp.country_code,
            )
            db.add(new_poi)
            await db.flush()
            target_poi_id = new_poi.id
            created_poi_count += 1
        elif target_poi_id:
            linked_poi_count += 1

        # Update scanned_path record
        sp.poi_id = target_poi_id
        sp.status = "identified" if has_coords or target_poi_id else "location unknown"
        if item.site_name:
            sp.site_name = item.site_name
        if has_coords:
            sp.latitude = item.latitude
            sp.longitude = item.longitude
        if item.city:
            sp.city = item.city
        if item.state:
            sp.state = item.state
        if item.country:
            sp.country = item.country
        if item.country_code:
            sp.country_code = item.country_code
        sp.reasoning = "Resolved via interactive Nominatim geocode review"

        updated_count += 1

    await db.commit()
    return BatchGeocodeConfirmResponse(
        updated_count=updated_count,
        created_poi_count=created_poi_count,
        linked_poi_count=linked_poi_count,
    )


@router.post(
    "/scanned-paths/{path_id}/disassociate-and-split", response_model=DisassociateAndSplitResponse
)
async def disassociate_and_split(
    path_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlinks a path from its current POI and creates a new unlocated POI record."""
    sp = await db.scalar(
        select(ScannedPath).where(ScannedPath.id == path_id, ScannedPath.user_id == current_user.id)
    )
    if not sp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanned path not found")

    old_poi_id = sp.poi_id
    new_poi_name = sp.site_name or sp.folder_name or "Unlocated Place"

    # Create new unlocated POI
    new_poi = POI(
        id=uuid.uuid4(),
        user_id=current_user.id,
        created_at=datetime.now(),
        name=new_poi_name,
        name_aliases=[],
        poi_type="site to see",
        visited=True,
        visit_date=sp.earliest_date,
        visit_dates=[sp.earliest_date] if sp.earliest_date else [],
        location=None,  # Intentionally unlocated to enter the pool of POIs needing location
        source_url=sp.folder_path,
        source_type="photo",
        iptc_city=sp.city,
        iptc_province_state=sp.state,
        iptc_country_code=sp.country_code,
    )
    db.add(new_poi)
    await db.flush()

    # Re-link the scanned path to the new unlocated POI
    sp.poi_id = new_poi.id
    sp.status = "location unknown"
    sp.latitude = None
    sp.longitude = None
    sp.reasoning = f"Disassociated from POI {old_poi_id} and split into new unlocated POI"

    await db.commit()

    return DisassociateAndSplitResponse(
        success=True,
        path_id=sp.id,
        old_poi_id=old_poi_id,
        new_poi_id=new_poi.id,
        new_poi_name=new_poi.name,
    )


@router.post("/pois/merge", response_model=POIMergeResponse)
async def merge_pois(
    payload: POIMergeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merges source/deleted POI into target/kept POI, applying granular field choices,
    updating list memberships and scanned path associations, and deleting the source POI."""
    target_id = payload.kept_poi_id or payload.target_poi_id
    source_id = payload.deleted_poi_id or payload.source_poi_id

    if not target_id or not source_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both target (kept) and source (deleted) POI IDs must be provided",
        )

    if source_id == target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a POI into itself"
        )

    source_poi = await db.scalar(
        select(POI).where(POI.id == source_id, POI.user_id == current_user.id)
    )
    target_poi = await db.scalar(
        select(POI).where(POI.id == target_id, POI.user_id == current_user.id)
    )

    if not source_poi or not target_poi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source or target POI not found"
        )

    # 1. Update single-value fields on target POI if specified in payload
    if payload.name is not None:
        target_poi.name = payload.name
    if payload.poi_type is not None:
        target_poi.poi_type = payload.poi_type
    if payload.personal_rating is not None:
        target_poi.personal_rating = payload.personal_rating
    if payload.description is not None:
        target_poi.description = payload.description

    # Parent / Macro site
    if payload.clear_parent_poi:
        target_poi.parent_poi_id = None
    elif payload.parent_poi_id is not None:
        if payload.parent_poi_id != source_poi.id and payload.parent_poi_id != target_poi.id:
            target_poi.parent_poi_id = payload.parent_poi_id
        else:
            target_poi.parent_poi_id = None

    # Location
    if payload.clear_location:
        target_poi.location = None
    elif payload.latitude is not None and payload.longitude is not None:
        if payload.latitude == 0.0 and payload.longitude == 0.0:
            target_poi.location = None
        else:
            target_poi.location = f"SRID=4326;POINT({payload.longitude} {payload.latitude})"

    # IPTC location metadata
    if payload.iptc_sublocation is not None:
        target_poi.iptc_sublocation = payload.iptc_sublocation
    if payload.iptc_zip_code is not None:
        target_poi.iptc_zip_code = payload.iptc_zip_code
    if payload.iptc_city is not None:
        target_poi.iptc_city = payload.iptc_city
    if payload.iptc_province_state is not None:
        target_poi.iptc_province_state = payload.iptc_province_state
    if payload.iptc_country_code is not None:
        target_poi.iptc_country_code = payload.iptc_country_code

    # Visit & contact logistics
    if payload.physical_effort is not None:
        target_poi.physical_effort = payload.physical_effort
    if payload.indoor_outdoor is not None:
        target_poi.indoor_outdoor = payload.indoor_outdoor
    if payload.estimated_duration is not None:
        target_poi.estimated_duration = payload.estimated_duration
    if payload.cost_tier is not None:
        target_poi.cost_tier = payload.cost_tier
    if payload.booking_lead_time is not None:
        target_poi.booking_lead_time = payload.booking_lead_time
    if payload.visit_again is not None:
        target_poi.visit_again = payload.visit_again
    if payload.phone_number is not None:
        target_poi.phone_number = payload.phone_number
    if payload.website_official is not None:
        target_poi.website_official = sanitize_official_website(payload.website_official)
    if payload.source_type is not None:
        target_poi.source_type = payload.source_type
    if payload.source_url is not None:
        target_poi.source_url = payload.source_url

    # 2. Multi-value: Visit dates
    if payload.visit_dates is not None:
        sorted_dates = sorted(list(set(payload.visit_dates)))
        target_poi.visit_dates = sorted_dates
        target_poi.visited = len(sorted_dates) > 0
        target_poi.visit_date = sorted_dates[0] if sorted_dates else None
    else:
        existing_dates = set(target_poi.visit_dates or [])
        if target_poi.visit_date:
            existing_dates.add(target_poi.visit_date)
        if source_poi.visit_dates:
            existing_dates.update(source_poi.visit_dates)
        if source_poi.visit_date:
            existing_dates.add(source_poi.visit_date)
        sorted_dates = sorted(list(existing_dates))
        target_poi.visit_dates = sorted_dates
        target_poi.visited = len(sorted_dates) > 0
        if sorted_dates:
            target_poi.visit_date = sorted_dates[0]

    # 3. Multi-value: Category tags
    if payload.category_tags is not None:
        target_poi.category_tags = list(dict.fromkeys(payload.category_tags))
    else:
        existing_tags = set(target_poi.category_tags or [])
        if source_poi.category_tags:
            existing_tags.update(source_poi.category_tags)
        target_poi.category_tags = list(existing_tags)

    # 4. Multi-value: List memberships
    if payload.list_ids is not None:
        await db.execute(delete(POIListMembership).where(POIListMembership.poi_id == target_poi.id))
        for lid in set(payload.list_ids):
            db.add(POIListMembership(poi_id=target_poi.id, list_id=lid))

    # 5. Multi-value: Scanned paths
    reassigned_count = 0
    if payload.selected_scanned_path_ids is not None:
        if payload.selected_scanned_path_ids:
            res = await db.execute(
                update(ScannedPath)
                .where(
                    ScannedPath.id.in_(payload.selected_scanned_path_ids),
                    ScannedPath.user_id == current_user.id,
                )
                .values(poi_id=target_poi.id)
            )
            reassigned_count = res.rowcount
        # Disassociate unselected paths from source_poi so they are not tied to the deleted record
        await db.execute(
            update(ScannedPath)
            .where(
                ScannedPath.poi_id == source_poi.id,
                ~ScannedPath.id.in_(payload.selected_scanned_path_ids or []),
            )
            .values(poi_id=None)
        )
    else:
        reassign_stmt = (
            update(ScannedPath)
            .where(ScannedPath.poi_id == source_poi.id)
            .values(poi_id=target_poi.id)
        )
        res = await db.execute(reassign_stmt)
        reassigned_count = res.rowcount

    # 6. Re-parent any child POIs of source_poi to target_poi
    await db.execute(
        update(POI).where(POI.parent_poi_id == source_poi.id).values(parent_poi_id=target_poi.id)
    )

    # 7. Reassign any access points from source_poi to target_poi
    await db.execute(
        update(POIAccessPoint)
        .where(POIAccessPoint.poi_id == source_poi.id)
        .values(poi_id=target_poi.id)
    )

    # 8. Delete source POI
    await db.delete(source_poi)
    await db.commit()

    return POIMergeResponse(
        success=True,
        target_poi_id=target_poi.id,
        target_poi_name=target_poi.name,
        paths_reassigned_count=reassigned_count,
        kept_poi_id=target_poi.id,
        deleted_poi_id=source_poi.id,
    )


@router.get("/scanned-paths/{path_id}/lookup-details", response_model=ScannedPathEnrichmentResponse)
async def lookup_scanned_path_details(
    path_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enriches a scanned folder's place details:
    1. Resolves photo date from DB or disk EXIF/mtime or path.
    2. Looks up official website, phone number, category tags, description, and logistics via OSM + Gemini.
    3. Caches resolved date back to scanned_paths if newly discovered.
    """
    sp = await db.scalar(
        select(ScannedPath).where(ScannedPath.id == path_id, ScannedPath.user_id == current_user.id)
    )
    if not sp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanned path not found")

    # 1. Resolve photo date
    resolved_date = sp.earliest_date or sp.latest_date
    if not resolved_date:
        resolved_date = resolve_folder_photo_date(sp.folder_path)
        if resolved_date:
            sp.earliest_date = resolved_date
            await db.commit()
            await db.refresh(sp)

    # 2. Enrich details
    place_name = sp.site_name or sp.folder_name
    enriched = await lookup_and_enrich_place(
        place_name=place_name,
        city=sp.city,
        state=sp.state,
        country=sp.country,
        latitude=sp.latitude,
        longitude=sp.longitude,
        db=db,
        folder_context=sp.folder_path,
    )

    return ScannedPathEnrichmentResponse(
        path_id=sp.id,
        folder_path=sp.folder_path,
        folder_name=sp.folder_name,
        site_name=sp.site_name,
        earliest_date=resolved_date,
        latest_date=sp.latest_date,
        visit_date_formatted=resolved_date.isoformat() if resolved_date else None,
        category_tags=enriched.get("category_tags") or [],
        website_official=enriched.get("website_official"),
        phone_number=enriched.get("phone_number"),
        description=enriched.get("description") or sp.reasoning,
        poi_type=enriched.get("poi_type") or "site to see",
        physical_effort=enriched.get("physical_effort"),
        indoor_outdoor=enriched.get("indoor_outdoor"),
        estimated_duration=enriched.get("estimated_duration"),
        cost_tier=enriched.get("cost_tier"),
        best_time_to_visit=enriched.get("best_time_to_visit"),
        hours_seasonality=enriched.get("hours_seasonality"),
        city=enriched.get("city") or sp.city,
        state=enriched.get("state") or sp.state,
        country=enriched.get("country") or sp.country,
        country_code=enriched.get("country_code") or sp.country_code,
        latitude=enriched.get("latitude") if enriched.get("latitude") is not None else sp.latitude,
        longitude=enriched.get("longitude")
        if enriched.get("longitude") is not None
        else sp.longitude,
    )


@router.post("/pois/lookup-details", response_model=POIDetailsLookupResponse)
async def lookup_generic_poi_details(
    payload: POIDetailsLookupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enriches generic place details (website, phone, category tags, logistics) via OSM and Gemini."""
    enriched = await lookup_and_enrich_place(
        place_name=payload.place_name,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        latitude=payload.latitude,
        longitude=payload.longitude,
        db=db,
        folder_context=payload.folder_context,
    )
    return POIDetailsLookupResponse(
        place_name=payload.place_name,
        category_tags=enriched.get("category_tags") or [],
        website_official=enriched.get("website_official"),
        phone_number=enriched.get("phone_number"),
        description=enriched.get("description"),
        poi_type=enriched.get("poi_type") or "site to see",
        physical_effort=enriched.get("physical_effort"),
        indoor_outdoor=enriched.get("indoor_outdoor"),
        estimated_duration=enriched.get("estimated_duration"),
        cost_tier=enriched.get("cost_tier"),
        best_time_to_visit=enriched.get("best_time_to_visit"),
        hours_seasonality=enriched.get("hours_seasonality"),
        city=enriched.get("city") or payload.city,
        state=enriched.get("state") or payload.state,
        country=enriched.get("country") or payload.country,
        country_code=enriched.get("country_code"),
        latitude=enriched.get("latitude")
        if enriched.get("latitude") is not None
        else payload.latitude,
        longitude=enriched.get("longitude")
        if enriched.get("longitude") is not None
        else payload.longitude,
    )


@router.post("/pois/{poi_id}/photo-folder", response_model=AddPhotoFolderResponse)
async def add_photo_folder_to_poi(
    poi_id: uuid.UUID,
    payload: AddPhotoFolderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Associates a photo folder with a POI.
    If the same folder is already in use with another POI, flags the issue
    so the POIs can be properly refactored manually.
    """
    poi = await db.scalar(select(POI).where(POI.id == poi_id, POI.user_id == current_user.id))
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found")

    raw_path = payload.folder_path.strip()
    if not raw_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Folder path cannot be empty"
        )

    norm_path = raw_path.rstrip("\\/")
    if not norm_path:
        norm_path = raw_path

    # Normalize file path to parent folder if an image file was supplied
    p = Path(norm_path)
    if p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
        norm_path = str(p.parent).rstrip("\\/") or str(p.parent)

    folder_name = os.path.basename(norm_path.rstrip("\\/")) or norm_path

    # Check if a ScannedPath already exists for this user
    sp = await db.scalar(
        select(ScannedPath).where(
            ScannedPath.user_id == current_user.id,
            func.lower(ScannedPath.folder_path) == norm_path.lower(),
        )
    )

    # Detect any conflicting POIs using this folder:
    conflicting_poi_ids = set()
    if sp:
        if sp.poi_id and sp.poi_id != poi_id:
            conflicting_poi_ids.add(sp.poi_id)
        if sp.conflict_poi_ids:
            for cid in sp.conflict_poi_ids:
                if cid != poi_id:
                    conflicting_poi_ids.add(cid)

    # Also check if another POI has source_url equal to this folder path
    other_pois_with_url = (
        (
            await db.execute(
                select(POI).where(
                    POI.user_id == current_user.id,
                    POI.id != poi_id,
                    func.lower(POI.source_url) == norm_path.lower(),
                )
            )
        )
        .scalars()
        .all()
    )
    for op in other_pois_with_url:
        conflicting_poi_ids.add(op.id)

    # Load details of conflicting POIs
    conflicting_pois_info = []
    if conflicting_poi_ids:
        c_pois = (
            (
                await db.execute(
                    select(POI).where(
                        POI.id.in_(conflicting_poi_ids), POI.user_id == current_user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for cp in c_pois:
            conflicting_pois_info.append(
                ConflictingPOIInfo(
                    id=cp.id,
                    name=cp.name,
                    poi_type=cp.poi_type,
                    iptc_city=cp.iptc_city,
                    iptc_province_state=cp.iptc_province_state,
                    iptc_country_code=cp.iptc_country_code,
                    source_url=cp.source_url,
                )
            )

    has_conflict = len(conflicting_pois_info) > 0

    # If conflict detected and action is "check": return conflict warning
    if has_conflict and payload.action == "check":
        other_names = ", ".join([cp.name for cp in conflicting_pois_info])
        return AddPhotoFolderResponse(
            success=False,
            conflict=True,
            conflicting_pois=conflicting_pois_info,
            message=f"Folder is already associated with place '{other_names}'. Please review to refactor or share.",
            path_id=sp.id if sp else None,
            folder_path=norm_path,
            folder_name=folder_name,
        )

    # If action is "share_and_flag" (associate and flag conflict on both):
    if has_conflict and payload.action == "share_and_flag":
        other_names = ", ".join([cp.name for cp in conflicting_pois_info])
        if not sp:
            sp = ScannedPath(
                id=uuid.uuid4(),
                user_id=current_user.id,
                poi_id=conflicting_pois_info[0].id if conflicting_pois_info else poi_id,
                folder_path=norm_path,
                folder_name=folder_name,
                status="identified",
                conflict_poi_ids=[poi_id],
                has_conflict=True,
                conflict_note=f"Shared folder conflict between '{poi.name}' and '{other_names}'.",
            )
            db.add(sp)
        else:
            curr_conflicts = list(sp.conflict_poi_ids or [])
            if poi_id not in curr_conflicts and sp.poi_id != poi_id:
                curr_conflicts.append(poi_id)
            sp.conflict_poi_ids = curr_conflicts
            sp.has_conflict = True
            sp.conflict_note = f"Shared folder conflict between '{poi.name}' and '{other_names}'."
            sp.status = "identified"

        if not poi.source_url:
            poi.source_url = norm_path
            poi.source_type = "photo"

        await db.commit()
        await db.refresh(sp)
        return AddPhotoFolderResponse(
            success=True,
            conflict=True,
            conflicting_pois=conflicting_pois_info,
            message=f"Folder attached and conflict flagged between '{poi.name}' and '{other_names}' for manual refactoring.",
            path_id=sp.id,
            folder_path=norm_path,
            folder_name=sp.folder_name,
        )

    # If action is "reassign" (exclusively assign to this POI, resolving previous conflict):
    if payload.action == "reassign":
        if not sp:
            sp = ScannedPath(
                id=uuid.uuid4(),
                user_id=current_user.id,
                poi_id=poi_id,
                folder_path=norm_path,
                folder_name=folder_name,
                status="identified",
                has_conflict=False,
                conflict_poi_ids=[],
                conflict_note=None,
            )
            db.add(sp)
        else:
            sp.poi_id = poi_id
            curr_conflicts = [cid for cid in (sp.conflict_poi_ids or []) if cid != poi_id]
            sp.conflict_poi_ids = curr_conflicts
            sp.has_conflict = len(curr_conflicts) > 0
            sp.conflict_note = None if not sp.has_conflict else sp.conflict_note
            sp.status = "identified"

        poi.source_url = norm_path
        poi.source_type = "photo"
        await db.commit()
        await db.refresh(sp)
        return AddPhotoFolderResponse(
            success=True,
            conflict=False,
            conflicting_pois=[],
            message=f"Folder successfully reassigned to '{poi.name}'.",
            path_id=sp.id,
            folder_path=norm_path,
            folder_name=sp.folder_name,
        )

    # Standard case: No conflict
    if not sp:
        sp = ScannedPath(
            id=uuid.uuid4(),
            user_id=current_user.id,
            poi_id=poi_id,
            folder_path=norm_path,
            folder_name=folder_name,
            status="identified",
            has_conflict=False,
            conflict_poi_ids=[],
        )
        db.add(sp)
    else:
        if sp.poi_id == poi_id:
            return AddPhotoFolderResponse(
                success=True,
                conflict=False,
                message="Folder is already attached to this place.",
                path_id=sp.id,
                folder_path=norm_path,
                folder_name=sp.folder_name,
            )
        sp.poi_id = poi_id
        sp.status = "identified"

    if not poi.source_url:
        poi.source_url = norm_path
        poi.source_type = "photo"

    await db.commit()
    await db.refresh(sp)
    return AddPhotoFolderResponse(
        success=True,
        conflict=False,
        conflicting_pois=[],
        message=f"Folder '{folder_name}' successfully attached to '{poi.name}'.",
        path_id=sp.id,
        folder_path=norm_path,
        folder_name=sp.folder_name,
    )


@router.post("/scanned-paths/{path_id}/disassociate")
async def disassociate_scanned_path(
    path_id: uuid.UUID,
    payload: DisassociateFolderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disassociates a folder from a specific POI (clearing or resolving multi-POI conflicts)."""
    sp = await db.scalar(
        select(ScannedPath).where(ScannedPath.id == path_id, ScannedPath.user_id == current_user.id)
    )
    if not sp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanned path not found")

    target_poi_id = payload.poi_id
    if sp.poi_id == target_poi_id:
        remaining_conflicts = list(sp.conflict_poi_ids or [])
        if remaining_conflicts:
            sp.poi_id = remaining_conflicts.pop(0)
            sp.conflict_poi_ids = remaining_conflicts
            sp.has_conflict = len(remaining_conflicts) > 0
            if not sp.has_conflict:
                sp.conflict_note = None
        else:
            sp.poi_id = None
            sp.status = "skipped"
            sp.has_conflict = False
            sp.conflict_note = None
    elif target_poi_id in (sp.conflict_poi_ids or []):
        curr_conflicts = [cid for cid in sp.conflict_poi_ids if cid != target_poi_id]
        sp.conflict_poi_ids = curr_conflicts
        sp.has_conflict = len(curr_conflicts) > 0
        if not sp.has_conflict:
            sp.conflict_note = None

    await db.commit()
    return {"success": True, "message": "Folder disassociated from place."}


@router.post("/pois/{poi_id}/inspect-photo-path", response_model=InspectPhotoResponse)
async def inspect_photo_path(
    poi_id: uuid.UUID,
    payload: InspectLocalPhotoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Inspects a local file or folder path.
    1. Determines folder path.
    2. Checks if folder is already in use by another POI (aborts if duplicate).
    3. If not in use, extracts EXIF date, lat/long, and IPTC/XMP tags from the image file.
    """
    raw_path_str = (payload.file_path or "").strip()
    if not raw_path_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File path must not be empty"
        )

    norm_path = raw_path_str.rstrip("\\/")
    if not norm_path:
        norm_path = raw_path_str
    p = Path(norm_path)

    # 1. Determine if it's a file or folder
    is_image_file = p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    if is_image_file or (p.exists() and p.is_file()):
        target_file = p
        target_folder = p.parent
    else:
        target_folder = p
        target_file = None
        # Try to find the first image in target_folder if it exists on disk
        if target_folder.exists() and target_folder.is_dir():
            try:
                for entry in target_folder.iterdir():
                    if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                        target_file = entry
                        break
            except Exception:
                pass

    folder_path_str = str(target_folder).rstrip("\\/")
    if not folder_path_str:
        folder_path_str = str(target_folder)

    # 2. Duplicate folder check: is this folder already associated with another POI?
    conflicting_poi_ids = set()

    # Check scanned_paths
    existing_sps = (
        (
            await db.execute(
                select(ScannedPath).where(
                    ScannedPath.user_id == current_user.id,
                    func.lower(ScannedPath.folder_path) == folder_path_str.lower(),
                )
            )
        )
        .scalars()
        .all()
    )

    already_linked = False
    for sp in existing_sps:
        if sp.poi_id == poi_id:
            already_linked = True
        elif sp.poi_id:
            conflicting_poi_ids.add(sp.poi_id)
        if sp.conflict_poi_ids:
            for cid in sp.conflict_poi_ids:
                if cid == poi_id:
                    already_linked = True
                else:
                    conflicting_poi_ids.add(cid)

    # Check pois.source_url
    other_pois_source = (
        (
            await db.execute(
                select(POI).where(
                    POI.user_id == current_user.id,
                    POI.id != poi_id,
                    func.lower(POI.source_url) == folder_path_str.lower(),
                )
            )
        )
        .scalars()
        .all()
    )

    for op in other_pois_source:
        conflicting_poi_ids.add(op.id)

    try:
        curr_poi = await db.get(POI, poi_id)
        if (
            curr_poi
            and curr_poi.source_url
            and curr_poi.source_url.strip().rstrip("\\/").lower() == folder_path_str.lower()
        ):
            already_linked = True
    except Exception:
        pass

    # If folder is in use by another POI: ABORT!
    if conflicting_poi_ids:
        conflicting_pois = []
        c_pois = (
            (
                await db.execute(
                    select(POI).where(
                        POI.id.in_(conflicting_poi_ids), POI.user_id == current_user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for cp in c_pois:
            conflicting_pois.append(
                ConflictingPOIInfo(
                    id=cp.id,
                    name=cp.name,
                    poi_type=cp.poi_type,
                    iptc_city=cp.iptc_city,
                    iptc_province_state=cp.iptc_province_state,
                    iptc_country_code=cp.iptc_country_code,
                    source_url=cp.source_url,
                )
            )

        names_str = ", ".join(f"'{cp.name}'" for cp in conflicting_pois)
        return InspectPhotoResponse(
            success=False,
            status="duplicate_aborted",
            message=f"Folder '{folder_path_str}' is already in use by place: {names_str}. Association aborted.",
            folder_path=folder_path_str,
            file_name=target_file.name if target_file else None,
            conflicting_pois=conflicting_pois,
            already_linked=already_linked,
        )

    # 3. If not duplicate, read EXIF metadata from target_file if available
    if target_file and target_file.exists():
        meta = extract_photo_metadata_from_path(target_file)
        has_meta = bool(meta.date_taken or meta.latitude is not None or meta.tags)
        return InspectPhotoResponse(
            success=True,
            status="metadata_found" if has_meta else "no_metadata",
            message=f"Metadata inspected successfully from '{target_file.name}'."
            if has_meta
            else f"No EXIF GPS/date metadata found in '{target_file.name}'.",
            folder_path=folder_path_str,
            file_name=target_file.name,
            date_taken=meta.date_taken,
            latitude=meta.latitude,
            longitude=meta.longitude,
            tags=meta.tags,
            conflicting_pois=[],
            already_linked=already_linked,
        )

    # If target_file doesn't exist on local disk or no image found
    return InspectPhotoResponse(
        success=True,
        status="no_metadata",
        message="Folder is valid and not in use, but no readable image file with EXIF was found on disk.",
        folder_path=folder_path_str,
        file_name=target_file.name if target_file else None,
        conflicting_pois=[],
        already_linked=already_linked,
    )


@router.post("/pois/{poi_id}/inspect-photo-upload", response_model=InspectPhotoResponse)
async def inspect_photo_upload(
    poi_id: uuid.UUID,
    file: UploadFile = File(...),
    folder_path: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Inspects an uploaded photo file for EXIF date, lat/long, and tags.
    If folder_path is supplied, verifies it is not in use by another POI.
    """
    contents = await file.read()
    meta = extract_photo_metadata_from_bytes(contents, file.filename)

    conflicting_poi_ids = set()
    norm_folder = None
    if folder_path and folder_path.strip():
        norm_folder = folder_path.strip().rstrip("\\/")

    # If folder was not explicitly provided, attempt to locate the folder on disk among the user's scanned paths
    if not norm_folder and file.filename:
        target_name = file.filename
        poi_paths = []
        try:
            poi_record = await db.get(POI, poi_id)
            if poi_record and poi_record.source_url:
                poi_paths.append(poi_record.source_url.strip())
            res_poi_sps = await db.execute(
                select(ScannedPath.folder_path).where(
                    ScannedPath.user_id == current_user.id,
                    ScannedPath.poi_id == poi_id,
                )
            )
            if hasattr(res_poi_sps, "scalars"):
                poi_paths.extend(res_poi_sps.scalars().all())
            elif hasattr(res_poi_sps, "all"):
                poi_paths.extend(
                    [r[0] if isinstance(r, (list, tuple)) else r for r in res_poi_sps.all()]
                )
        except Exception:
            pass

        # 0. Check current POI paths (direct and recursive)
        for p_str in poi_paths:
            try:
                p = Path(p_str)
                if (p / target_name).is_file():
                    norm_folder = str(p).rstrip("\\/")
                    break
                if p.is_dir():
                    for root, _dirs, files in os.walk(p):
                        if target_name in files:
                            norm_folder = str(root).rstrip("\\/")
                            break
                    if norm_folder:
                        break
            except Exception:
                pass

        # 1. Check candidate paths matching photo year
        candidate_paths = []
        if not norm_folder:
            year_str = None
            if meta.date_taken:
                year_str = (
                    str(meta.date_taken.year)
                    if hasattr(meta.date_taken, "year")
                    else str(meta.date_taken)[:4]
                )
            if year_str:
                try:
                    res_year = await db.execute(
                        select(ScannedPath.folder_path).where(
                            ScannedPath.user_id == current_user.id,
                            ScannedPath.folder_path.contains(year_str),
                        )
                    )
                    if hasattr(res_year, "scalars"):
                        candidate_paths = list(res_year.scalars().all())
                    elif hasattr(res_year, "all"):
                        candidate_paths = [
                            r[0] if isinstance(r, (list, tuple)) else r for r in res_year.all()
                        ]
                except Exception:
                    candidate_paths = []

                # Fast direct check
                for cp_str in candidate_paths:
                    try:
                        if (Path(cp_str) / target_name).is_file():
                            norm_folder = str(cp_str).rstrip("\\/")
                            break
                    except Exception:
                        pass

                # Recursive check within candidate directories
                if not norm_folder:
                    for cp_str in candidate_paths:
                        try:
                            cand_dir = Path(cp_str)
                            if cand_dir.is_dir():
                                for root, _dirs, files in os.walk(cand_dir):
                                    if target_name in files:
                                        norm_folder = str(root).rstrip("\\/")
                                        break
                                if norm_folder:
                                    break
                        except Exception:
                            pass

        # 2. Check all remaining user scanned paths
        if not norm_folder:
            try:
                res_all = await db.execute(
                    select(ScannedPath.folder_path).where(ScannedPath.user_id == current_user.id)
                )
                if hasattr(res_all, "scalars"):
                    all_paths = [
                        p
                        for p in res_all.scalars().all()
                        if p not in candidate_paths and p not in poi_paths
                    ]
                elif hasattr(res_all, "all"):
                    all_paths = [
                        r[0] if isinstance(r, (list, tuple)) else r
                        for r in res_all.all()
                        if (r[0] if isinstance(r, (list, tuple)) else r) not in candidate_paths
                        and (r[0] if isinstance(r, (list, tuple)) else r) not in poi_paths
                    ]
                else:
                    all_paths = []
            except Exception:
                all_paths = []

            for cp_str in all_paths:
                try:
                    if (Path(cp_str) / target_name).is_file():
                        norm_folder = str(cp_str).rstrip("\\/")
                        break
                except Exception:
                    pass

            if not norm_folder:
                for cp_str in all_paths:
                    try:
                        cand_dir = Path(cp_str)
                        if cand_dir.is_dir():
                            for root, _dirs, files in os.walk(cand_dir):
                                if target_name in files:
                                    norm_folder = str(root).rstrip("\\/")
                                    break
                            if norm_folder:
                                break
                    except Exception:
                        pass

    already_linked = False
    if norm_folder:
        existing_sps = (
            (
                await db.execute(
                    select(ScannedPath).where(
                        ScannedPath.user_id == current_user.id,
                        func.lower(ScannedPath.folder_path) == norm_folder.lower(),
                    )
                )
            )
            .scalars()
            .all()
        )

        for sp in existing_sps:
            if not hasattr(sp, "poi_id"):
                continue
            if sp.poi_id == poi_id:
                already_linked = True
            elif sp.poi_id:
                conflicting_poi_ids.add(sp.poi_id)
            if hasattr(sp, "conflict_poi_ids") and sp.conflict_poi_ids:
                for cid in sp.conflict_poi_ids:
                    if cid == poi_id:
                        already_linked = True
                    else:
                        conflicting_poi_ids.add(cid)

        other_pois_source = (
            (
                await db.execute(
                    select(POI).where(
                        POI.user_id == current_user.id,
                        POI.id != poi_id,
                        func.lower(POI.source_url) == norm_folder.lower(),
                    )
                )
            )
            .scalars()
            .all()
        )
        for op in other_pois_source:
            conflicting_poi_ids.add(op.id)

        try:
            curr_poi = await db.get(POI, poi_id)
            if (
                curr_poi
                and curr_poi.source_url
                and curr_poi.source_url.strip().rstrip("\\/").lower() == norm_folder.lower()
            ):
                already_linked = True
        except Exception:
            pass

        if conflicting_poi_ids:
            conflicting_pois = []
            c_pois = (
                (
                    await db.execute(
                        select(POI).where(
                            POI.id.in_(conflicting_poi_ids), POI.user_id == current_user.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            for cp in c_pois:
                conflicting_pois.append(
                    ConflictingPOIInfo(
                        id=cp.id,
                        name=cp.name,
                        poi_type=cp.poi_type,
                        iptc_city=cp.iptc_city,
                        iptc_province_state=cp.iptc_province_state,
                        iptc_country_code=cp.iptc_country_code,
                        source_url=cp.source_url,
                    )
                )

            names_str = ", ".join(f"'{cp.name}'" for cp in conflicting_pois)
            return InspectPhotoResponse(
                success=False,
                status="duplicate_aborted",
                message=f"Folder '{norm_folder}' is already in use by place: {names_str}. Association aborted.",
                folder_path=norm_folder,
                file_name=file.filename,
                conflicting_pois=conflicting_pois,
                already_linked=already_linked,
            )

    has_meta = bool(meta.date_taken or meta.latitude is not None or meta.tags or norm_folder)
    return InspectPhotoResponse(
        success=True,
        status="metadata_found" if has_meta else "no_metadata",
        message=f"Metadata inspected successfully from '{file.filename}'."
        if has_meta
        else f"No EXIF GPS/date metadata found in '{file.filename}'.",
        folder_path=norm_folder,
        file_name=file.filename,
        date_taken=meta.date_taken,
        latitude=meta.latitude,
        longitude=meta.longitude,
        tags=meta.tags,
        conflicting_pois=[],
        already_linked=already_linked,
    )
