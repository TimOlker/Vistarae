"""Pydantic schemas for POI entities, deduplication responses, and lists."""

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.extraction import POIExtractionCandidate


class CollisionStatus(str, Enum):
    UNIQUE_LOCATION = "UNIQUE_LOCATION"
    POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"
    NEARBY_PARENT = "NEARBY_PARENT"


class POICollisionMatch(BaseModel):
    id: uuid.UUID
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    poi_type: str
    personal_rating: int | None = None
    distance_meters: float
    name_similarity: float
    description: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None


class ListSummary(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    is_trip: bool = False


class ExtractAndCheckResponse(BaseModel):
    candidate: POIExtractionCandidate
    latitude: float
    longitude: float
    display_name: str | None = None
    collision_status: CollisionStatus
    matched_poi: POICollisionMatch | None = None
    nearby_parent: POICollisionMatch | None = None
    available_lists: list[ListSummary] = Field(default_factory=list)
    source_url: str
    og_image_url: str | None = None


class POIAccessPointCreate(BaseModel):
    type: str = Field(..., description="e.g. parking lot, trail head, bus stop")
    description: str | None = None
    latitude: float
    longitude: float
    parking_logistics: str | None = Field(
        default=None, description="free parking, paid street parking, transit only"
    )


class POICreate(BaseModel):
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    poi_type: str = Field(..., description="photo location, site to see, experience, food/drink, lodging, transit")
    personal_rating: int | None = Field(default=3, ge=1, le=5)
    description: str | None = None
    category_tags: list[str] = Field(default_factory=list)
    visited: bool = False
    visit_date: date | None = None

    latitude: float
    longitude: float
    geofence_radius_ft: int = 500
    parent_poi_id: uuid.UUID | None = None

    physical_effort: str | None = None
    booking_lead_time: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    hours_seasonality: str | None = None
    best_time_to_visit: str | None = None
    website_official: str | None = None
    phone_number: str | None = None
    google_place_id: str | None = None

    primary_image_url: str | None = None
    alternate_image_urls: list[str] = Field(default_factory=list)
    source_url: str
    source_type: str | None = "Web Selection"
    raw_selected_text: str | None = None

    iptc_sublocation: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    iptc_world_region: str | None = None
    iptc_zip_code: str | None = None

    list_ids: list[uuid.UUID] = Field(default_factory=list)
    access_points: list[POIAccessPointCreate] = Field(default_factory=list)


class POIResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_aliases: list[str]
    poi_type: str
    personal_rating: int | None
    description: str | None
    category_tags: list[str]
    visited: bool
    visit_date: date | None
    latitude: float
    longitude: float
    geofence_radius_ft: int
    parent_poi_id: uuid.UUID | None
    physical_effort: str | None
    booking_lead_time: str | None
    indoor_outdoor: str | None
    estimated_duration: str | None
    cost_tier: str | None
    hours_seasonality: str | None
    best_time_to_visit: str | None
    website_official: str | None
    phone_number: str | None
    primary_image_url: str | None
    source_url: str
    iptc_city: str | None
    iptc_province_state: str | None
    iptc_country_code: str | None
    created_at: datetime
    list_ids: list[uuid.UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ListCreate(BaseModel):
    title: str
    description: str | None = None
    is_trip: bool = False
