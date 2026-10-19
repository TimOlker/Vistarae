"""Pydantic schemas for Gemini Flash-Lite structured extraction."""

from typing import Literal

from pydantic import BaseModel, Field

POIType = Literal[
    "photo location",
    "site to see",
    "experience",
    "food/drink",
    "lodging",
    "transit",
]

IndoorOutdoor = Literal["Indoor", "Outdoor", "Mixed"]


class POIExtractionCandidate(BaseModel):
    """Structured extraction output returned by Gemini Flash-Lite."""

    name: str = Field(description="Primary official or common name of the Point of Interest")
    name_aliases: list[str] = Field(
        default_factory=list, description="Alternative names, local names, or abbreviations"
    )
    poi_type: POIType = Field(default="site to see", description="Type classification of this POI")
    personal_rating: int | None = Field(
        default=3,
        ge=1,
        le=5,
        description="Suggested quality rating 1-5 (5: world class, 4: worth drive, 3: nice if nearby, 2: maybe, 1: skip)",
    )
    description: str | None = Field(
        default=None,
        description="Concise, evocative summary highlighting why a traveler would visit",
    )
    category_tags: list[str] = Field(
        default_factory=list,
        description="Category keywords like 'waterfall', 'viewpoint', 'sunset', 'hiking'",
    )
    physical_effort: str | None = Field(
        default=None,
        description="Physical effort level required: drive-up, paved walk, moderate hike, strenuous, stairs",
    )
    booking_lead_time: str | None = Field(
        default=None,
        description="Booking lead time: walk-in ok, 1-3 days ahead, months ahead, permit lottery",
    )
    indoor_outdoor: IndoorOutdoor | None = Field(
        default=None, description="Setting environment: Indoor, Outdoor, or Mixed"
    )
    estimated_duration: str | None = Field(
        default=None, description="Typical visit duration: 30 mins, 1-2 hours, half day, full day"
    )
    cost_tier: str | None = Field(default=None, description="Cost estimate: Free, $, $$, $$$, $$$$")
    hours_seasonality: str | None = Field(
        default=None,
        description="Operating hours or seasonality advice, e.g. 'Open dawn to dusk, best May-Oct'",
    )
    best_time_to_visit: str | None = Field(
        default=None,
        description="Ideal timing, e.g. 'Sunrise', 'Golden Hour', 'Sunset', 'Low Tide'",
    )
    website_official: str | None = Field(
        default=None, description="Official website URL if mentioned or readily inferred"
    )
    phone_number: str | None = Field(default=None, description="Contact phone number if available")
    search_address_query: str = Field(
        description="Optimized geocoding search string for OpenStreetMap Nominatim (e.g. 'Glacier Point, Yosemite National Park, California, USA')"
    )
    iptc_sublocation: str | None = Field(default=None, description="Specific sublocation/landmark")
    iptc_city: str | None = Field(default=None, description="City or municipality")
    iptc_province_state: str | None = Field(default=None, description="Province or state")
    iptc_country_code: str | None = Field(
        default=None, description="2-letter ISO country code (e.g. US)"
    )
    iptc_world_region: str | None = Field(default=None, description="Continent / World region")
    iptc_zip_code: str | None = Field(default=None, description="Postal code")


class ExtractAndCheckRequest(BaseModel):
    """Payload sent from the Chrome Extension to initiate extraction and collision check."""

    selected_text: str = Field(
        default="", description="Highlighted text from user selection or generated summary"
    )
    page_title: str = Field(default="", description="Active web page document.title")
    page_url: str = Field(..., description="Active web page window.location.href")
    og_image_url: str | None = Field(default=None, description="OpenGraph preview image URL")
    latitude: float | None = Field(
        default=None, description="Direct latitude if known (e.g. from Google Maps pin)"
    )
    longitude: float | None = Field(
        default=None, description="Direct longitude if known (e.g. from Google Maps pin)"
    )
    place_name: str | None = Field(
        default=None, description="Direct place name if extracted from Google Maps URL/DOM"
    )
    category: str | None = Field(
        default=None, description="Direct category classification if extracted from Google Maps DOM"
    )
    website: str | None = Field(default=None, description="Direct official website URL if known")
    phone_number: str | None = Field(default=None, description="Direct phone number if known")
    city: str | None = Field(default=None, description="Direct city if known from source schema")
    state: str | None = Field(
        default=None, description="Direct state/province if known from source schema"
    )
    country: str | None = Field(
        default=None, description="Direct country code if known from source schema"
    )
    postal_code: str | None = Field(
        default=None, description="Direct postal code if known from source schema"
    )
    category_tags: list[str] | None = Field(
        default=None, description="Direct category tags if known from source schema"
    )
    physical_effort: str | None = Field(default=None, description="Direct physical effort if known")
    booking_lead_time: str | None = Field(
        default=None, description="Direct booking lead time if known"
    )
    indoor_outdoor: IndoorOutdoor | None = Field(
        default=None, description="Direct setting environment if known"
    )
    estimated_duration: str | None = Field(
        default=None, description="Direct estimated duration if known"
    )
    cost_tier: str | None = Field(default=None, description="Direct cost tier if known")
    best_time_to_visit: str | None = Field(
        default=None, description="Direct best time to visit if known"
    )
    source_type: str | None = Field(
        default=None,
        description="Source classification, e.g. Atlas Obscura, Google Maps, Web Selection",
    )
