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

"""FastAPI Ingestion Engine for Vistarae Travel Platform."""

import inspect
import logging
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.middleware.telemetry import TelemetryMiddleware
from app.models import POI, ListModel, POIAccessPoint, POIListMembership, ScannedPath, User, UserTag
from app.routers.poi_ingestion import router as poi_ingestion_router
from app.routers.scanned_paths import router as scanned_paths_router
from app.schemas.auth import Token, UserLogin, UserRegister, UserResponse
from app.schemas.extraction import ExtractAndCheckRequest
from app.schemas.poi import (
    CheckDuplicateRequest,
    CheckDuplicateResponse,
    ExtractAndCheckResponse,
    GeocodeQueryResponse,
    ListCreate,
    ListSummary,
    ParentPOISummary,
    POIBulkActionResponse,
    POIBulkDeleteRequest,
    POIBulkUpdateRequest,
    POICreate,
    POIResponse,
    POIUpdate,
    ReverseGeocodeResponse,
    TagCreate,
    TagResponse,
)
from app.services.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.services.countries import map_country_to_code
from app.services.deduplication import check_spatial_collision
from app.services.extraction import (
    extract_candidate_from_text,
    sanitize_image_url,
    sanitize_official_website,
)
from app.services.geocoding import (
    enrich_candidate_from_address,
    extract_address_components,
    geocode_query,
    reverse_geocode,
)

logger = logging.getLogger("vistarae.api")
# Reload trigger for ingestion optimizations

app = FastAPI(
    title="Vistarae Ingestion Engine",
    description="Captures travel dreams, extracts POIs via Gemini Flash-Lite, geocodes with Nominatim, and deduplicates in PostGIS.",
    version="0.1.0",
)

# OpenTelemetry W3C distributed tracing middleware
app.add_middleware(TelemetryMiddleware)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scanned_paths_router)
app.include_router(poi_ingestion_router)


# ==========================================
# System / Health Routes
# ==========================================


@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Healthcheck confirming database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        logger.error(f"Healthcheck database error: {exc}")
        db_status = f"unhealthy: {exc}"

    return {
        "status": "online",
        "service": "vistarae-backend",
        "environment": settings.APP_ENV,
        "database": db_status,
    }


# ==========================================
# Authentication & User Management Routes
# ==========================================


@app.post(
    "/api/v1/auth/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)
async def register_user(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Registers a new user account, creates credentials, and returns an access token."""
    existing_user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    new_user = User(
        id=uuid.uuid4(),
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(user_id=new_user.id, email=new_user.email)
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@app.post(
    "/api/v1/auth/login",
    response_model=Token,
    tags=["Authentication"],
)
async def login_user(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates user credentials and issues a JWT access token."""
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    token = create_access_token(user_id=user.id, email=user.email)
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@app.get(
    "/api/v1/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Returns profile information for the authenticated user."""
    return UserResponse.model_validate(current_user)


# ==========================================
# Extraction & Deduplication Routes
# ==========================================

STANDARD_TAGS = [
    "NPS",
    "scenic",
    "viewpoint",
    "hiking",
    "waterfall",
    "sunset",
    "sunrise",
    "wildlife",
    "photography",
    "historic",
    "nature",
    "beach",
    "museum",
    "ship",
    "military",
    "airplane",
    "aviation",
    "space",
    "island",
    "monument",
    "memorial",
    "lighthouse",
    "castle",
    "bridge",
    "mountain",
    "canyon",
    "cave",
    "park",
    "food",
    "overlook",
    "trail",
    "lodging",
]


async def get_user_all_tags(user_id: uuid.UUID, db: AsyncSession) -> list[str]:
    """Retrieves standard common tags merged with user's custom tags and tags in existing POIs."""
    user_tags_res = await db.scalars(select(UserTag.name).where(UserTag.user_id == user_id))
    user_custom = set(user_tags_res.all())

    poi_tags_res = await db.scalars(
        select(func.unnest(POI.category_tags)).where(POI.user_id == user_id).distinct()
    )
    poi_tags = set(poi_tags_res.all() or [])

    merged = set(STANDARD_TAGS) | user_custom | poi_tags
    return sorted(list(merged), key=lambda x: (x != "NPS", x.lower()))


@app.post(
    "/api/v1/extract-and-check",
    response_model=ExtractAndCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Extraction & Deduplication"],
)
async def extract_and_check(
    payload: ExtractAndCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Primary pipeline called by Chrome Extension:
    1. Extracts structured entities using Google Gemini Flash-Lite.
    2. Deterministically geocodes location via Nominatim (cached).
    3. Performs spatial radius & trigram similarity deduplication in PostGIS (scoped to user).
    4. Returns candidate draft, collision status, and user's available lists.
    """
    # 1. LLM Extraction
    candidate = await extract_candidate_from_text(payload)
    if payload.place_name:
        candidate.name = payload.place_name
    if payload.city:
        if payload.state and payload.city.strip().lower() == payload.state.strip().lower():
            if (
                payload.place_name
                and payload.place_name.strip().lower() != payload.state.strip().lower()
            ):
                candidate.iptc_city = payload.place_name
            else:
                candidate.iptc_city = None
        else:
            candidate.iptc_city = payload.city
    if payload.state:
        candidate.iptc_province_state = payload.state

    if payload.country:
        candidate.iptc_country_code = payload.country
    if payload.postal_code:
        candidate.iptc_zip_code = payload.postal_code
    if payload.website and not candidate.website_official:
        candidate.website_official = payload.website

    # 2. Geocoding (use direct coordinates if provided from Google Maps pin or Atlas Obscura)
    if payload.latitude is not None and payload.longitude is not None:
        lat = payload.latitude
        lng = payload.longitude
        display_name = payload.place_name or candidate.name
        raw_geo = None
    else:
        search_query = candidate.search_address_query or candidate.name
        lat, lng, display_name, raw_geo = await geocode_query(search_query, db)

    # Enrich candidate IPTC fields from forward geocoding if available
    if raw_geo:
        enrich_candidate_from_address(candidate, raw_geo)

    # 2b. Reverse geocoding lookup:
    # If address fields are not found but coordinates are present, resolve address using lat/long lookup
    has_valid_coords = lat != 0.0 or lng != 0.0
    address_missing = (
        not candidate.iptc_city
        or candidate.iptc_city.lower() in ("unknown", "unknown city")
        or not candidate.iptc_province_state
        or candidate.iptc_province_state.lower() in ("unknown", "unknown state")
        or not candidate.iptc_country_code
    )
    if has_valid_coords and address_missing:
        logger.info(
            f"Address fields incomplete for '{candidate.name}'. Attempting reverse geocoding lookup for ({lat}, {lng})."
        )
        rev_display_name, rev_geo = await reverse_geocode(lat, lng, db)
        if rev_geo:
            enrich_candidate_from_address(candidate, rev_geo)
            if not display_name or display_name == candidate.name:
                display_name = rev_display_name or display_name

    # 3. Spatial Deduplication & Nesting Check (isolated to current user's POIs)
    collision_status, duplicate_match, nearby_parent = await check_spatial_collision(
        cand_name=candidate.name,
        cand_lat=lat,
        cand_lng=lng,
        radius_ft=500,
        db=db,
        user_id=current_user.id,
    )

    # 4. Fetch available lists for current user
    lists_result = await db.scalars(
        select(ListModel).where(ListModel.user_id == current_user.id).order_by(ListModel.title)
    )
    available_lists = [
        ListSummary(id=lst.id, title=lst.title, description=lst.description, is_trip=lst.is_trip)
        for lst in lists_result.all()
    ]

    # 5. Fetch available parent POIs for current user
    parents_result = await db.scalars(
        select(POI).where(POI.user_id == current_user.id).order_by(POI.name)
    )
    available_parents = [
        ParentPOISummary(id=p.id, name=p.name, poi_type=p.poi_type) for p in parents_result.all()
    ]

    # 6. Fetch available tags for current user
    available_tags = await get_user_all_tags(current_user.id, db)

    return ExtractAndCheckResponse(
        candidate=candidate,
        latitude=lat if (lat != 0.0 or lng != 0.0) else None,
        longitude=lng if (lat != 0.0 or lng != 0.0) else None,
        display_name=display_name,
        collision_status=collision_status,
        matched_poi=duplicate_match,
        nearby_parent=nearby_parent,
        available_lists=available_lists,
        available_parents=available_parents,
        available_tags=available_tags,
        source_url=payload.page_url,
        og_image_url=payload.og_image_url,
        location_detected=(lat is not None and lng is not None and (lat != 0.0 or lng != 0.0))
        and bool(
            candidate.name
            and candidate.name.lower() not in ("scenic point of interest", "unknown", "untitled")
        ),
    )


# ==========================================
# Geocoding Routes
# ==========================================


@app.get(
    "/api/v1/reverse-geocode",
    response_model=ReverseGeocodeResponse,
    status_code=status.HTTP_200_OK,
    tags=["Geocoding"],
)
@app.get(
    "/api/v1/pois/reverse-geocode",
    response_model=ReverseGeocodeResponse,
    status_code=status.HTTP_200_OK,
    tags=["Geocoding"],
)
async def api_reverse_geocode(
    latitude: float = Query(..., description="Latitude to reverse geocode"),
    longitude: float = Query(..., description="Longitude to reverse geocode"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reverse geocodes coordinates to resolve address details (city, state, country, etc.)."""
    display_name, raw_json = await reverse_geocode(latitude, longitude, db)
    comps = extract_address_components(raw_json)
    return ReverseGeocodeResponse(
        display_name=display_name,
        city=comps.get("city"),
        state=comps.get("state"),
        country_code=comps.get("country_code"),
        country_name=comps.get("country_name"),
        sublocation=comps.get("sublocation"),
        postcode=comps.get("postcode"),
        raw_address=raw_json.get("address", {}) if raw_json else {},
    )


@app.get(
    "/api/v1/geocode",
    response_model=GeocodeQueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Geocoding"],
)
@app.get(
    "/api/v1/pois/geocode",
    response_model=GeocodeQueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Geocoding"],
)
async def api_geocode(
    query: str | None = Query(None, description="Place name or address query to forward geocode"),
    q: str | None = Query(None, description="Alias for query"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forward geocodes a place name or address to coordinates and address details."""
    search_term = (query or q or "").strip()
    if not search_term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="query parameter is required"
        )
    lat, lng, display_name, raw_json = await geocode_query(search_term, db)
    comps = extract_address_components(raw_json)
    return GeocodeQueryResponse(
        latitude=lat if (lat != 0.0 or lng != 0.0) else None,
        longitude=lng if (lat != 0.0 or lng != 0.0) else None,
        display_name=display_name,
        city=comps.get("city"),
        state=comps.get("state"),
        country_code=comps.get("country_code"),
        country_name=comps.get("country_name"),
        sublocation=comps.get("sublocation"),
        postcode=comps.get("postcode"),
        raw_address=raw_json.get("address", {}) if raw_json else {},
    )


# ==========================================
# POI CRUD Routes
# ==========================================


@app.post(
    "/api/v1/pois/check-duplicate",
    response_model=CheckDuplicateResponse,
    status_code=status.HTTP_200_OK,
    tags=["POIs", "Deduplication"],
)
async def api_check_duplicate_poi(
    payload: CheckDuplicateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluates an in-progress or cloned POI for duplicate entry and spatial collisions against the user's collection."""
    collision_status, duplicate_match, nearby_parent = await check_spatial_collision(
        cand_name=payload.name,
        cand_lat=payload.latitude,
        cand_lng=payload.longitude,
        radius_ft=payload.radius_ft,
        db=db,
        user_id=current_user.id,
    )
    return CheckDuplicateResponse(
        collision_status=collision_status,
        matched_poi=duplicate_match,
        nearby_parent=nearby_parent,
    )


@app.post(
    "/api/v1/pois",
    response_model=POIResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["POIs"],
)
async def create_poi(
    payload: POICreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Commits verified POI into PostgreSQL/PostGIS owned by the authenticated user."""
    has_coords = (
        payload.latitude is not None
        and payload.longitude is not None
        and (payload.latitude != 0.0 or payload.longitude != 0.0)
    )

    # If address fields are empty on create, attempt reverse geocode lookup
    if has_coords and not (
        payload.iptc_city and payload.iptc_province_state and payload.iptc_country_code
    ):
        _, rev_geo = await reverse_geocode(payload.latitude, payload.longitude, db)
        if rev_geo:
            enrich_candidate_from_address(payload, rev_geo)

    # Convert lat/lng into PostGIS Geography Point (SRID 4326) if present
    point_wkt = f"SRID=4326;POINT({payload.longitude} {payload.latitude})" if has_coords else None

    payload.website_official = sanitize_official_website(payload.website_official)
    payload.primary_image_url = sanitize_image_url(payload.primary_image_url)

    new_poi = POI(
        id=uuid.uuid4(),
        user_id=current_user.id,
        created_at=datetime.now(),
        name=payload.name,
        name_aliases=payload.name_aliases,
        poi_type=payload.poi_type,
        personal_rating=payload.personal_rating,
        description=payload.description,
        category_tags=payload.category_tags,
        visited=payload.visited,
        visit_date=payload.visit_date,
        visit_dates=payload.visit_dates
        if payload.visit_dates
        else ([payload.visit_date] if payload.visit_date else []),
        visit_again=payload.visit_again,
        location=point_wkt,
        geofence_radius_ft=payload.geofence_radius_ft,
        parent_poi_id=payload.parent_poi_id,
        physical_effort=payload.physical_effort,
        booking_lead_time=payload.booking_lead_time,
        indoor_outdoor=payload.indoor_outdoor,
        estimated_duration=payload.estimated_duration,
        cost_tier=payload.cost_tier,
        hours_seasonality=payload.hours_seasonality,
        best_time_to_visit=payload.best_time_to_visit,
        website_official=payload.website_official,
        phone_number=payload.phone_number,
        google_place_id=payload.google_place_id,
        primary_image_url=payload.primary_image_url,
        alternate_image_urls=payload.alternate_image_urls,
        source_url=payload.source_url,
        source_type=payload.source_type or "web",
        raw_selected_text=payload.raw_selected_text,
        iptc_sublocation=payload.iptc_sublocation,
        iptc_city=payload.iptc_city,
        iptc_province_state=payload.iptc_province_state,
        iptc_country_code=payload.iptc_country_code,
        iptc_world_region=payload.iptc_world_region,
        iptc_zip_code=payload.iptc_zip_code,
    )
    db.add(new_poi)
    await db.flush()

    # Add access points
    for ap in payload.access_points:
        ap_has_coords = (
            ap.latitude is not None
            and ap.longitude is not None
            and (ap.latitude != 0.0 or ap.longitude != 0.0)
        )
        ap_point_wkt = f"SRID=4326;POINT({ap.longitude} {ap.latitude})" if ap_has_coords else None
        access_point = POIAccessPoint(
            poi_id=new_poi.id,
            type=ap.type,
            description=ap.description,
            location=ap_point_wkt,
            parking_logistics=ap.parking_logistics,
        )
        db.add(access_point)

    # Add list memberships
    for lid in payload.list_ids:
        membership = POIListMembership(poi_id=new_poi.id, list_id=lid)
        db.add(membership)

    await db.commit()
    await db.refresh(new_poi)

    return POIResponse(
        id=new_poi.id,
        name=new_poi.name,
        name_aliases=new_poi.name_aliases or [],
        poi_type=new_poi.poi_type,
        personal_rating=new_poi.personal_rating,
        description=new_poi.description,
        category_tags=new_poi.category_tags or [],
        visited=new_poi.visited,
        visit_date=new_poi.visit_date,
        visit_dates=new_poi.visit_dates
        if new_poi.visit_dates
        else ([new_poi.visit_date] if new_poi.visit_date else []),
        visit_again=new_poi.visit_again if new_poi.visit_again is not None else False,
        latitude=payload.latitude if has_coords else None,
        longitude=payload.longitude if has_coords else None,
        geofence_radius_ft=new_poi.geofence_radius_ft,
        parent_poi_id=new_poi.parent_poi_id,
        physical_effort=new_poi.physical_effort,
        booking_lead_time=new_poi.booking_lead_time,
        indoor_outdoor=new_poi.indoor_outdoor,
        estimated_duration=new_poi.estimated_duration,
        cost_tier=new_poi.cost_tier,
        hours_seasonality=new_poi.hours_seasonality,
        best_time_to_visit=new_poi.best_time_to_visit,
        website_official=new_poi.website_official,
        phone_number=new_poi.phone_number,
        primary_image_url=new_poi.primary_image_url,
        source_url=new_poi.source_url,
        source_type=new_poi.source_type,
        iptc_city=new_poi.iptc_city,
        iptc_province_state=new_poi.iptc_province_state,
        iptc_country_code=new_poi.iptc_country_code,
        created_at=new_poi.created_at,
        list_ids=payload.list_ids,
    )


@app.get("/api/v1/pois", response_model=list[POIResponse], tags=["POIs"])
async def list_pois(
    search: str | None = None,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_miles: float | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lng: float | None = None,
    max_lng: float | None = None,
    list_id: uuid.UUID | None = None,
    tag: str | None = None,
    has_location: bool | None = None,
    visit_again: bool | None = None,
    visited_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists and filters captured POIs belonging strictly to the authenticated user.
    Supports filtering by search query, country, state, city, lat/lng + radius, map bounding box, list_id, tag, location presence, visit_again, and visited_status.
    """
    conditions = ["p.user_id = :user_id"]
    params: dict = {"user_id": current_user.id, "limit": limit, "offset": offset}

    if has_location is True:
        conditions.append("p.location IS NOT NULL")
    elif has_location is False:
        conditions.append("p.location IS NULL")

    if visit_again is not None:
        conditions.append("p.visit_again = :visit_again")
        params["visit_again"] = visit_again

    if visited_status:
        v_status = visited_status.strip().lower().replace(" ", "_")
        if v_status == "visited":
            conditions.append(
                "(p.visit_date IS NOT NULL OR (p.visit_dates IS NOT NULL AND cardinality(p.visit_dates) > 0))"
            )
        elif v_status in ("not_visited", "unvisited"):
            conditions.append(
                "(p.visit_date IS NULL AND (p.visit_dates IS NULL OR cardinality(p.visit_dates) = 0))"
            )
        elif v_status in ("to_see", "tosee"):
            conditions.append(
                "((p.visit_date IS NULL AND (p.visit_dates IS NULL OR cardinality(p.visit_dates) = 0)) OR p.visit_again IS TRUE)"
            )

    if search and search.strip():
        conditions.append(
            "(p.name ILIKE :search_like OR p.description ILIKE :search_like OR p.iptc_city ILIKE :search_like)"
        )
        params["search_like"] = f"%{search.strip()}%"

    if country and country.strip():
        c_val = country.strip()
        mapped_code = map_country_to_code(c_val)
        if mapped_code:
            conditions.append(
                "(p.iptc_country_code = :country_exact OR p.iptc_country_code ILIKE :country_val)"
            )
            params["country_exact"] = mapped_code
            params["country_val"] = f"%{mapped_code}%"
        else:
            conditions.append(
                "(p.iptc_country_code ILIKE :country_val OR p.iptc_country_code = :country_exact)"
            )
            params["country_val"] = f"%{c_val}%"
            params["country_exact"] = c_val.upper()

    if state and state.strip():
        conditions.append("p.iptc_province_state ILIKE :state_like")
        params["state_like"] = f"%{state.strip()}%"

    if city and city.strip():
        conditions.append("p.iptc_city ILIKE :city_like")
        params["city_like"] = f"%{city.strip()}%"

    if lat is not None and lng is not None:
        radius_meters = (radius_miles or 25.0) * 1609.34
        conditions.append(
            "ST_DWithin(p.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_meters)"
        )
        params["lat"] = lat
        params["lng"] = lng
        params["radius_meters"] = radius_meters

    if min_lat is not None and max_lat is not None and min_lng is not None and max_lng is not None:
        if min_lng <= max_lng:
            conditions.append(
                "ST_Intersects(p.location::geometry, ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326))"
            )
            params.update(
                {"min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat}
            )
        else:
            conditions.append(
                "(ST_Intersects(p.location::geometry, ST_MakeEnvelope(:min_lng, :min_lat, 180.0, :max_lat, 4326)) OR "
                "ST_Intersects(p.location::geometry, ST_MakeEnvelope(-180.0, :min_lat, :max_lng, :max_lat, 4326)))"
            )
            params.update(
                {"min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat}
            )

    if list_id is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM poi_list_memberships plm WHERE plm.poi_id = p.id AND plm.list_id = :filter_list_id)"
        )
        params["filter_list_id"] = list_id

    if tag and tag.strip():
        t_clean = tag.strip().lower()
        conditions.append(
            "(:tag_exact = ANY(p.category_tags) OR p.category_tags::text ILIKE :tag_like)"
        )
        params["tag_exact"] = t_clean
        params["tag_like"] = f"%{t_clean}%"

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT
            p.id, p.name, p.name_aliases, p.poi_type, p.personal_rating, p.description,
            p.category_tags, p.visited, p.visit_date, p.visit_dates, p.visit_again, p.geofence_radius_ft, p.parent_poi_id,
            p.physical_effort, p.booking_lead_time, p.indoor_outdoor, p.estimated_duration,
            p.cost_tier, p.hours_seasonality, p.best_time_to_visit, p.website_official,
            p.phone_number, p.primary_image_url, p.source_url, p.source_type, p.iptc_city, p.iptc_province_state,
            p.iptc_country_code, p.created_at,
            ST_Y(p.location::geometry) AS latitude,
            ST_X(p.location::geometry) AS longitude,
            EXISTS(
                SELECT 1 FROM scanned_paths sp
                WHERE sp.user_id = p.user_id AND sp.has_conflict = TRUE AND (sp.poi_id = p.id OR p.id = ANY(sp.conflict_poi_ids))
            ) AS has_folder_conflict,
            COALESCE((
                SELECT array_agg(plm.list_id)
                FROM poi_list_memberships plm
                WHERE plm.poi_id = p.id
            ), ARRAY[]::uuid[]) AS list_ids
        FROM pois p
        WHERE {where_clause}
        ORDER BY p.created_at DESC
        LIMIT :limit OFFSET :offset;
    """)
    result = await db.execute(query, params)
    rows = result.mappings().all()

    return [
        POIResponse(
            id=r["id"],
            name=r["name"],
            name_aliases=r["name_aliases"] or [],
            poi_type=r["poi_type"],
            personal_rating=r["personal_rating"],
            description=r["description"],
            category_tags=r["category_tags"] or [],
            visited=r["visited"],
            visit_date=r["visit_date"],
            visit_dates=list(r["visit_dates"]) if r.get("visit_dates") is not None else [],
            visit_again=bool(r["visit_again"]) if r.get("visit_again") is not None else False,
            latitude=float(r["latitude"]) if r["latitude"] is not None else None,
            longitude=float(r["longitude"]) if r["longitude"] is not None else None,
            geofence_radius_ft=r["geofence_radius_ft"],
            parent_poi_id=r["parent_poi_id"],
            physical_effort=r["physical_effort"],
            booking_lead_time=r["booking_lead_time"],
            indoor_outdoor=r["indoor_outdoor"],
            estimated_duration=r["estimated_duration"],
            cost_tier=r["cost_tier"],
            hours_seasonality=r["hours_seasonality"],
            best_time_to_visit=r["best_time_to_visit"],
            website_official=r["website_official"],
            phone_number=r["phone_number"],
            primary_image_url=r["primary_image_url"],
            source_url=r["source_url"],
            source_type=r.get("source_type"),
            iptc_city=r["iptc_city"],
            iptc_province_state=r["iptc_province_state"],
            iptc_country_code=r["iptc_country_code"],
            created_at=r["created_at"],
            list_ids=list(r["list_ids"]) if r["list_ids"] is not None else [],
            has_folder_conflict=bool(r.get("has_folder_conflict", False)),
        )
        for r in rows
    ]


@app.get("/api/v1/pois/{poi_id}", response_model=POIResponse, tags=["POIs"])
async def get_poi(
    poi_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves a single POI by ID belonging strictly to the authenticated user."""
    query = text("""
        SELECT
            p.id, p.name, p.name_aliases, p.poi_type, p.personal_rating, p.description,
            p.category_tags, p.visited, p.visit_date, p.visit_dates, p.visit_again, p.geofence_radius_ft, p.parent_poi_id,
            p.physical_effort, p.booking_lead_time, p.indoor_outdoor, p.estimated_duration,
            p.cost_tier, p.hours_seasonality, p.best_time_to_visit, p.website_official,
            p.phone_number, p.primary_image_url, p.source_url, p.source_type, p.iptc_city, p.iptc_province_state,
            p.iptc_country_code, p.created_at,
            ST_Y(p.location::geometry) AS latitude,
            ST_X(p.location::geometry) AS longitude,
            EXISTS(
                SELECT 1 FROM scanned_paths sp
                WHERE sp.user_id = p.user_id AND sp.has_conflict = TRUE AND (sp.poi_id = p.id OR p.id = ANY(sp.conflict_poi_ids))
            ) AS has_folder_conflict,
            COALESCE((
                SELECT array_agg(plm.list_id)
                FROM poi_list_memberships plm
                WHERE plm.poi_id = p.id
            ), ARRAY[]::uuid[]) AS list_ids
        FROM pois p
        WHERE p.id = :poi_id AND p.user_id = :user_id;
    """)
    result = await db.execute(query, {"poi_id": poi_id, "user_id": current_user.id})
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found")

    return POIResponse(
        id=row["id"],
        name=row["name"],
        name_aliases=row["name_aliases"] or [],
        poi_type=row["poi_type"],
        personal_rating=row["personal_rating"],
        description=row["description"],
        category_tags=row["category_tags"] or [],
        visited=row["visited"],
        visit_date=row["visit_date"],
        visit_dates=list(row["visit_dates"]) if row.get("visit_dates") is not None else [],
        visit_again=bool(row["visit_again"]) if row.get("visit_again") is not None else False,
        latitude=float(row["latitude"]) if row["latitude"] is not None else None,
        longitude=float(row["longitude"]) if row["longitude"] is not None else None,
        geofence_radius_ft=row["geofence_radius_ft"],
        parent_poi_id=row["parent_poi_id"],
        physical_effort=row["physical_effort"],
        booking_lead_time=row["booking_lead_time"],
        indoor_outdoor=row["indoor_outdoor"],
        estimated_duration=row["estimated_duration"],
        cost_tier=row["cost_tier"],
        hours_seasonality=row["hours_seasonality"],
        best_time_to_visit=row["best_time_to_visit"],
        website_official=row["website_official"],
        phone_number=row["phone_number"],
        primary_image_url=row["primary_image_url"],
        source_url=row["source_url"],
        source_type=row.get("source_type"),
        iptc_city=row["iptc_city"],
        iptc_province_state=row["iptc_province_state"],
        iptc_country_code=row["iptc_country_code"],
        created_at=row["created_at"],
        list_ids=list(row["list_ids"]) if row["list_ids"] is not None else [],
        has_folder_conflict=bool(row.get("has_folder_conflict", False)),
    )


@app.put("/api/v1/pois/{poi_id}", response_model=POIResponse, tags=["POIs"])
async def update_poi(
    poi_id: uuid.UUID,
    payload: POIUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates an existing POI record belonging to the authenticated user."""
    poi = await db.scalar(select(POI).where(POI.id == poi_id, POI.user_id == current_user.id))
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found")

    if payload.name is not None:
        poi.name = payload.name
    if payload.name_aliases is not None:
        poi.name_aliases = payload.name_aliases
    if payload.poi_type is not None:
        poi.poi_type = payload.poi_type
    if payload.personal_rating is not None:
        poi.personal_rating = payload.personal_rating
    if payload.description is not None:
        poi.description = payload.description
    if payload.category_tags is not None:
        poi.category_tags = payload.category_tags
    if payload.visited is not None:
        poi.visited = payload.visited
    if payload.visit_date is not None:
        poi.visit_date = payload.visit_date
    if payload.visit_dates is not None:
        poi.visit_dates = payload.visit_dates
    if payload.visit_again is not None:
        poi.visit_again = payload.visit_again
    if payload.clear_location:
        poi.location = None
    elif payload.latitude is not None and payload.longitude is not None:
        if payload.latitude == 0.0 and payload.longitude == 0.0:
            poi.location = None
        else:
            poi.location = f"SRID=4326;POINT({payload.longitude} {payload.latitude})"
    if payload.geofence_radius_ft is not None:
        poi.geofence_radius_ft = payload.geofence_radius_ft
    if "parent_poi_id" in payload.model_fields_set:
        if payload.parent_poi_id and payload.parent_poi_id == poi.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="A place cannot be its own parent"
            )
        poi.parent_poi_id = payload.parent_poi_id
    if payload.physical_effort is not None:
        poi.physical_effort = payload.physical_effort
    if payload.booking_lead_time is not None:
        poi.booking_lead_time = payload.booking_lead_time
    if payload.indoor_outdoor is not None:
        poi.indoor_outdoor = payload.indoor_outdoor
    if payload.estimated_duration is not None:
        poi.estimated_duration = payload.estimated_duration
    if payload.cost_tier is not None:
        poi.cost_tier = payload.cost_tier
    if payload.hours_seasonality is not None:
        poi.hours_seasonality = payload.hours_seasonality
    if payload.best_time_to_visit is not None:
        poi.best_time_to_visit = payload.best_time_to_visit
    if payload.website_official is not None:
        poi.website_official = sanitize_official_website(payload.website_official)
    if payload.phone_number is not None:
        poi.phone_number = payload.phone_number
    if payload.primary_image_url is not None:
        poi.primary_image_url = sanitize_image_url(payload.primary_image_url)
    if payload.source_url is not None:
        poi.source_url = payload.source_url
    if payload.source_type is not None:
        poi.source_type = payload.source_type
    if payload.iptc_sublocation is not None:
        poi.iptc_sublocation = payload.iptc_sublocation
    if payload.iptc_city is not None:
        poi.iptc_city = payload.iptc_city
    if payload.iptc_province_state is not None:
        poi.iptc_province_state = payload.iptc_province_state
    if payload.iptc_country_code is not None:
        poi.iptc_country_code = payload.iptc_country_code
    if payload.iptc_zip_code is not None:
        poi.iptc_zip_code = payload.iptc_zip_code

    # Update list memberships if list_ids explicitly passed
    if payload.list_ids is not None:
        await db.execute(
            text("DELETE FROM poi_list_memberships WHERE poi_id = :poi_id"),
            {"poi_id": poi_id},
        )
        for lid in payload.list_ids:
            db.add(POIListMembership(poi_id=poi_id, list_id=lid))

    await db.commit()
    return await get_poi(poi_id, current_user, db)


@app.delete("/api/v1/pois/{poi_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["POIs"])
async def delete_poi(
    poi_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a POI record belonging strictly to the authenticated user."""
    poi = await db.scalar(select(POI).where(POI.id == poi_id, POI.user_id == current_user.id))
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found")

    # Disassociate all scanned paths pointing to this POI and set their status to location unknown
    sp_res = await db.scalars(
        select(ScannedPath).where(
            ScannedPath.poi_id == poi.id,
            ScannedPath.user_id == current_user.id,
        )
    )
    scanned_paths = sp_res.all() if hasattr(sp_res, "all") else []
    if inspect.isawaitable(scanned_paths):
        scanned_paths = []
    for sp in scanned_paths:
        sp.poi_id = None
        sp.status = "location unknown"
        sp.latitude = None
        sp.longitude = None
        sp.reasoning = f"Associated POI '{poi.name}' was deleted"

    await db.delete(poi)
    await db.commit()


@app.post("/api/v1/pois/bulk-delete", response_model=POIBulkActionResponse, tags=["POIs"])
async def bulk_delete_pois(
    payload: POIBulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk deletes selected POIs belonging strictly to the authenticated user."""
    pois_res = await db.scalars(
        select(POI).where(POI.id.in_(payload.poi_ids), POI.user_id == current_user.id)
    )
    pois = pois_res.all() if hasattr(pois_res, "all") else []
    if inspect.isawaitable(pois):
        pois = []

    count = len(pois)
    if pois:
        poi_map = {p.id: p.name for p in pois}
        sp_res = await db.scalars(
            select(ScannedPath).where(
                ScannedPath.poi_id.in_(list(poi_map.keys())),
                ScannedPath.user_id == current_user.id,
            )
        )
        scanned_paths = sp_res.all() if hasattr(sp_res, "all") else []
        if inspect.isawaitable(scanned_paths):
            scanned_paths = []
        for sp in scanned_paths:
            pname = poi_map.get(sp.poi_id, "Unknown")
            sp.poi_id = None
            sp.status = "location unknown"
            sp.latitude = None
            sp.longitude = None
            sp.reasoning = f"Associated POI '{pname}' was deleted"

        for poi in pois:
            await db.delete(poi)
    await db.commit()
    return POIBulkActionResponse(success=True, affected_count=count)


@app.post("/api/v1/pois/bulk-update", response_model=POIBulkActionResponse, tags=["POIs"])
async def bulk_update_pois(
    payload: POIBulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk updates tags and/or location for selected POIs belonging to the authenticated user."""
    pois = (
        await db.scalars(
            select(POI).where(POI.id.in_(payload.poi_ids), POI.user_id == current_user.id)
        )
    ).all()

    clean_add_tags = [t.strip() for t in payload.add_tags if t.strip()]
    clean_remove_tags = [t.strip().lower() for t in payload.remove_tags if t.strip()]

    for poi in pois:
        # 1. Update tags if specified
        if clean_add_tags or clean_remove_tags:
            current_tags = list(poi.category_tags or [])
            if clean_remove_tags:
                current_tags = [t for t in current_tags if t.lower() not in clean_remove_tags]
            for add_t in clean_add_tags:
                if not any(t.lower() == add_t.lower() for t in current_tags):
                    current_tags.append(add_t)
            poi.category_tags = current_tags

        # 2. Update coordinates / clear location
        if payload.clear_location:
            poi.location = None
        elif payload.latitude is not None and payload.longitude is not None:
            if payload.latitude == 0.0 and payload.longitude == 0.0:
                poi.location = None
            else:
                poi.location = f"SRID=4326;POINT({payload.longitude} {payload.latitude})"

        # 3. Update location fields if specified
        if payload.iptc_city is not None:
            poi.iptc_city = payload.iptc_city.strip() or None
        if payload.iptc_province_state is not None:
            poi.iptc_province_state = payload.iptc_province_state.strip() or None
        if payload.iptc_country_code is not None:
            poi.iptc_country_code = payload.iptc_country_code.strip().upper() or None

    await db.commit()
    return POIBulkActionResponse(success=True, affected_count=len(pois))


# ==========================================
# List Management Routes
# ==========================================


@app.get("/api/v1/lists", response_model=list[ListSummary], tags=["Lists"])
async def list_user_lists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves all lists belonging to the authenticated user."""
    result = await db.scalars(
        select(ListModel).where(ListModel.user_id == current_user.id).order_by(ListModel.title)
    )
    return [
        ListSummary(id=lst.id, title=lst.title, description=lst.description, is_trip=lst.is_trip)
        for lst in result.all()
    ]


@app.post(
    "/api/v1/lists", response_model=ListSummary, status_code=status.HTTP_201_CREATED, tags=["Lists"]
)
async def create_user_list(
    payload: ListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new list owned by the authenticated user."""
    new_list = ListModel(
        id=uuid.uuid4(),
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        is_trip=payload.is_trip,
    )
    db.add(new_list)
    await db.commit()
    await db.refresh(new_list)
    return ListSummary(
        id=new_list.id,
        title=new_list.title,
        description=new_list.description,
        is_trip=new_list.is_trip,
    )


@app.delete("/api/v1/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Lists"])
async def delete_user_list(
    list_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a list owned by the authenticated user."""
    target_list = await db.scalar(
        select(ListModel).where(ListModel.id == list_id, ListModel.user_id == current_user.id)
    )
    if not target_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")
    await db.delete(target_list)
    await db.commit()
    return None


# ==========================================
# Category Tag Management Routes
# ==========================================


@app.get("/api/v1/tags", response_model=list[str], tags=["Tags"])
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves all standard and user-defined tags."""
    return await get_user_all_tags(current_user.id, db)


@app.post(
    "/api/v1/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED, tags=["Tags"]
)
async def create_custom_tag(
    payload: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new custom tag for the authenticated user."""
    tag_clean = payload.name.strip()
    if not tag_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag cannot be empty"
        )

    existing = await db.scalar(
        select(UserTag).where(
            UserTag.user_id == current_user.id, func.lower(UserTag.name) == tag_clean.lower()
        )
    )
    if not existing:
        new_tag = UserTag(user_id=current_user.id, name=tag_clean)
        db.add(new_tag)
        await db.commit()

    return TagResponse(name=tag_clean, is_custom=True)


@app.delete("/api/v1/tags/{tag_name}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tags"])
async def delete_custom_tag(
    tag_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Removes a custom tag for the authenticated user."""
    tag_clean = tag_name.strip()
    target = await db.scalar(
        select(UserTag).where(
            UserTag.user_id == current_user.id, func.lower(UserTag.name) == tag_clean.lower()
        )
    )
    if target:
        await db.delete(target)
        await db.commit()
    return None
