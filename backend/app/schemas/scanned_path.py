"""Pydantic schemas for scanned photo file paths and batch operations."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ScannedPathResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    poi_id: uuid.UUID | None = None
    poi_name: str | None = None
    folder_path: str
    folder_name: str
    parent_folder: str | None = None
    status: str  # 'pending', 'identified', 'location unknown', 'skipped'
    site_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    confidence: str = "medium"
    reasoning: str | None = None
    photo_count: int = 0
    earliest_date: date | None = None
    latest_date: date | None = None

    # Multi-POI conflict tracking
    has_conflict: bool = False
    conflict_poi_ids: list[uuid.UUID] = []
    conflict_poi_names: list[str] = []
    conflict_note: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConflictingPOIInfo(BaseModel):
    id: uuid.UUID
    name: str
    poi_type: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    source_url: str | None = None


class AddPhotoFolderRequest(BaseModel):
    folder_path: str
    action: str = "check"  # "check", "share_and_flag", "reassign"


class AddPhotoFolderResponse(BaseModel):
    success: bool
    conflict: bool
    conflicting_pois: list[ConflictingPOIInfo] = []
    message: str
    path_id: uuid.UUID | None = None
    folder_path: str
    folder_name: str | None = None


class DisassociateFolderRequest(BaseModel):
    poi_id: uuid.UUID


class InspectLocalPhotoRequest(BaseModel):
    file_path: str  # File path or folder path on local disk


class InspectPhotoResponse(BaseModel):
    success: bool
    status: str  # "metadata_found", "duplicate_aborted", "no_metadata", "file_not_found"
    message: str
    folder_path: str | None = None
    file_name: str | None = None
    date_taken: date | None = None
    latitude: float | None = None
    longitude: float | None = None
    tags: list[str] = []
    conflicting_pois: list[ConflictingPOIInfo] = []
    already_linked: bool = False


class ScannedPathListResponse(BaseModel):
    items: list[ScannedPathResponse]
    total_count: int
    offset: int
    limit: int


class ScannedPathUpdate(BaseModel):
    status: str | None = None
    site_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    reasoning: str | None = None
    poi_id: uuid.UUID | None = None


class ScannedPathBatchUpdate(BaseModel):
    path_ids: list[uuid.UUID] = Field(..., min_length=1)
    status: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class ScannedPathBatchGeocodeRequest(BaseModel):
    path_ids: list[uuid.UUID] = Field(..., min_length=1)


class GeocodeCandidateItem(BaseModel):
    path_id: uuid.UUID
    folder_path: str
    folder_name: str
    current_site_name: str | None = None
    query_used: str
    found: bool
    display_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    matched_existing_poi_id: uuid.UUID | None = None
    matched_existing_poi_name: str | None = None
    action_proposed: str = "create_poi"  # "create_poi", "link_poi", "unresolved"


class BatchGeocodePreviewResponse(BaseModel):
    candidates: list[GeocodeCandidateItem]


class BatchGeocodeConfirmItem(BaseModel):
    path_id: uuid.UUID
    apply: bool = True
    create_new_poi: bool = True
    existing_poi_id: uuid.UUID | None = None
    site_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None


class BatchGeocodeConfirmRequest(BaseModel):
    items: list[BatchGeocodeConfirmItem] = Field(..., min_length=1)


class BatchGeocodeConfirmResponse(BaseModel):
    updated_count: int
    created_poi_count: int
    linked_poi_count: int


class DisassociateAndSplitResponse(BaseModel):
    success: bool
    path_id: uuid.UUID
    old_poi_id: uuid.UUID | None = None
    new_poi_id: uuid.UUID
    new_poi_name: str


class POIMergeRequest(BaseModel):
    source_poi_id: uuid.UUID | None = None
    target_poi_id: uuid.UUID | None = None
    kept_poi_id: uuid.UUID | None = None
    deleted_poi_id: uuid.UUID | None = None

    # Granular single-value overrides for the kept POI
    name: str | None = None
    poi_type: str | None = None
    personal_rating: int | None = None
    parent_poi_id: uuid.UUID | None = None
    clear_parent_poi: bool = False
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    clear_location: bool = False
    iptc_sublocation: str | None = None
    iptc_zip_code: str | None = None
    iptc_city: str | None = None
    iptc_province_state: str | None = None
    iptc_country_code: str | None = None
    physical_effort: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    booking_lead_time: str | None = None
    visit_again: bool | None = None
    phone_number: str | None = None
    website_official: str | None = None
    source_type: str | None = None
    source_url: str | None = None

    # Multi-value selections
    visit_dates: list[date] | None = None
    category_tags: list[str] | None = None
    list_ids: list[uuid.UUID] | None = None
    selected_scanned_path_ids: list[uuid.UUID] | None = None


class POIMergeResponse(BaseModel):
    success: bool
    target_poi_id: uuid.UUID
    target_poi_name: str
    paths_reassigned_count: int
    kept_poi_id: uuid.UUID | None = None
    deleted_poi_id: uuid.UUID | None = None


class ScannedPathEnrichmentResponse(BaseModel):
    path_id: uuid.UUID
    folder_path: str
    folder_name: str
    site_name: str | None = None
    earliest_date: date | None = None
    latest_date: date | None = None
    visit_date_formatted: str | None = None
    category_tags: list[str] = Field(default_factory=list)
    website_official: str | None = None
    phone_number: str | None = None
    description: str | None = None
    poi_type: str = "site to see"
    physical_effort: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    best_time_to_visit: str | None = None
    hours_seasonality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class POIDetailsLookupRequest(BaseModel):
    place_name: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    folder_context: str | None = None


class POIDetailsLookupResponse(BaseModel):
    place_name: str
    category_tags: list[str] = Field(default_factory=list)
    website_official: str | None = None
    phone_number: str | None = None
    description: str | None = None
    poi_type: str = "site to see"
    physical_effort: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    best_time_to_visit: str | None = None
    hours_seasonality: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
