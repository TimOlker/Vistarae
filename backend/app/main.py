"""FastAPI Ingestion Engine for Vistarae Travel Platform."""

import logging
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.middleware.telemetry import TelemetryMiddleware
from app.models import POI, ListModel, POIAccessPoint, POIListMembership, User
from app.schemas.auth import Token, UserLogin, UserRegister, UserResponse
from app.schemas.extraction import ExtractAndCheckRequest
from app.schemas.poi import (
    ExtractAndCheckResponse,
    ListCreate,
    ListSummary,
    POICreate,
    POIResponse,
)
from app.services.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.services.deduplication import check_spatial_collision
from app.services.extraction import extract_candidate_from_text
from app.services.geocoding import geocode_query

logger = logging.getLogger("vistarae.api")

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

    # 2. Geocoding
    search_query = candidate.search_address_query or candidate.name
    lat, lng, display_name, raw_geo = await geocode_query(search_query, db)

    # Enrich candidate IPTC fields from geocoding if empty
    if raw_geo and "address" in raw_geo:
        addr = raw_geo["address"]
        candidate.iptc_city = candidate.iptc_city or addr.get("city") or addr.get("town") or addr.get("village")
        candidate.iptc_province_state = candidate.iptc_province_state or addr.get("state")
        candidate.iptc_country_code = candidate.iptc_country_code or addr.get("country_code", "").upper()
        candidate.iptc_zip_code = candidate.iptc_zip_code or addr.get("postcode")

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

    return ExtractAndCheckResponse(
        candidate=candidate,
        latitude=lat,
        longitude=lng,
        display_name=display_name,
        collision_status=collision_status,
        matched_poi=duplicate_match,
        nearby_parent=nearby_parent,
        available_lists=available_lists,
        source_url=payload.page_url,
        og_image_url=payload.og_image_url,
    )


# ==========================================
# POI CRUD Routes
# ==========================================

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
    # Convert lat/lng into PostGIS Geography Point (SRID 4326)
    point_wkt = f"SRID=4326;POINT({payload.longitude} {payload.latitude})"

    new_poi = POI(
        user_id=current_user.id,
        name=payload.name,
        name_aliases=payload.name_aliases,
        poi_type=payload.poi_type,
        personal_rating=payload.personal_rating,
        description=payload.description,
        category_tags=payload.category_tags,
        visited=payload.visited,
        visit_date=payload.visit_date,
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
        source_type=payload.source_type,
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
        ap_point_wkt = f"SRID=4326;POINT({ap.longitude} {ap.latitude})"
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
        latitude=payload.latitude,
        longitude=payload.longitude,
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
        iptc_city=new_poi.iptc_city,
        iptc_province_state=new_poi.iptc_province_state,
        iptc_country_code=new_poi.iptc_country_code,
        created_at=new_poi.created_at,
        list_ids=payload.list_ids,
    )


@app.get("/api/v1/pois", response_model=list[POIResponse], tags=["POIs"])
async def list_pois(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists captured POIs belonging strictly to the authenticated user."""
    # Query with ST_Y (latitude) and ST_X (longitude) scoped to current_user.id
    query = text("""
        SELECT
            p.id, p.name, p.name_aliases, p.poi_type, p.personal_rating, p.description,
            p.category_tags, p.visited, p.visit_date, p.geofence_radius_ft, p.parent_poi_id,
            p.physical_effort, p.booking_lead_time, p.indoor_outdoor, p.estimated_duration,
            p.cost_tier, p.hours_seasonality, p.best_time_to_visit, p.website_official,
            p.phone_number, p.primary_image_url, p.source_url, p.iptc_city, p.iptc_province_state,
            p.iptc_country_code, p.created_at,
            ST_Y(p.location::geometry) AS latitude,
            ST_X(p.location::geometry) AS longitude
        FROM pois p
        WHERE p.user_id = :user_id
        ORDER BY p.created_at DESC
        LIMIT :limit;
    """)
    result = await db.execute(query, {"user_id": current_user.id, "limit": limit})
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
            latitude=float(r["latitude"]),
            longitude=float(r["longitude"]),
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
            iptc_city=r["iptc_city"],
            iptc_province_state=r["iptc_province_state"],
            iptc_country_code=r["iptc_country_code"],
            created_at=r["created_at"],
            list_ids=[],
        )
        for r in rows
    ]


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


@app.post("/api/v1/lists", response_model=ListSummary, status_code=status.HTTP_201_CREATED, tags=["Lists"])
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
