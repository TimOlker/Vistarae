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

"""Standardized POI extractor record schema and formula neutralization (016-cli-extractors).

Defines the core data transfer objects for external scraping tools and enforces
formula injection security prior to CSV serialization.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel

FORMULA_PREFIXES: Final[tuple[str, ...]] = ("=", "+", "-", "@", "\t", "\r")

CSV_HEADERS: Final[list[str]] = [
    "POI Name",
    "Street Address",
    "Town/City",
    "State/Province",
    "Zip Code",
    "Country",
    "Country Code",
    "latitude",
    "longitude",
    "Tags",
    "Hero Image URL",
    "Websites",
    "Additional Address",
    "Estimated Visit Hours",
    "Itinerary Days",
    "Description",
    "Reason to Visit",
    "Photo Directory",
    "Dates Visited",
]


def neutralize_formula_injection(value: str | None) -> str:
    """Neutralizes spreadsheet formula injection by prepending a single quote.

    Prefixes '=', '+', '-', '@', '\\t', and '\\r' trigger dynamic formula evaluation
    in Microsoft Excel, LibreOffice Calc, and Google Sheets. Prepending a single
    quote forces spreadsheet applications to treat the cell contents as plain text.

    Args:
        value: Raw text string to sanitize.

    Returns:
        Sanitized text string with prepended single quote if matching injection prefixes.
    """
    if not value:
        return ""
    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


class WebsiteRecord(StrictBaseModel):
    """External website reference for a point of interest."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Descriptive label for the website, e.g. Official Website, Wikipedia",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Fully-qualified HTTP or HTTPS URL",
    )


class AdditionalAddressRecord(StrictBaseModel):
    """Secondary, satellite, or alternative physical location for multi-facility POIs."""

    street_address: str | None = Field(
        default=None,
        max_length=255,
        description="Secondary street address line",
    )
    town_city: str | None = Field(
        default=None,
        max_length=150,
        description="Locality, municipality, town, or city",
    )
    state_province: str | None = Field(
        default=None,
        max_length=100,
        description="State, province, or region",
    )
    zip_code: str | None = Field(
        default=None,
        max_length=20,
        description="Postal or zip code",
    )
    country: str | None = Field(
        default=None,
        max_length=100,
        description="Recognized country name",
    )
    country_code: str | None = Field(
        default=None,
        max_length=2,
        description="ISO 3166-1 alpha-2 uppercase country code",
    )
    latitude: Decimal | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="WGS-84 decimal latitude",
    )
    longitude: Decimal | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="WGS-84 decimal longitude",
    )
    facility_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional label identifying the satellite facility or entrance",
    )


class ExtractorRecord(StrictBaseModel):
    """Authoritative in-memory point of interest record produced by CLI extractors."""

    poi_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Standardized attraction or point of interest name",
    )
    street_address: str | None = Field(
        default=None,
        max_length=255,
        description="Primary street address line",
    )
    town_city: str | None = Field(
        default=None,
        max_length=150,
        description="Primary city, town, or locality",
    )
    state_province: str | None = Field(
        default=None,
        max_length=100,
        description="Primary state, province, or administrative region",
    )
    zip_code: str | None = Field(
        default=None,
        max_length=20,
        description="Postal or zip code",
    )
    country: str | None = Field(
        default=None,
        max_length=100,
        description="Recognized country name in English",
    )
    country_code: str | None = Field(
        default=None,
        max_length=2,
        description="ISO 3166-1 alpha-2 uppercase country code",
    )
    latitude: Decimal | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="WGS-84 decimal latitude",
    )
    longitude: Decimal | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="WGS-84 decimal longitude",
    )
    additional_addresses: list[AdditionalAddressRecord] = Field(
        default_factory=list,
        description="Collection of satellite or secondary physical locations",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Contextual and category tags associated with the POI",
    )
    websites: list[WebsiteRecord] = Field(
        default_factory=list,
        description="Collection of external web references",
    )
    hero_image_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Primary external exterior hero photo link",
    )
    description: str | None = Field(
        default=None,
        max_length=4000,
        description="Historical or geographic overview text",
    )
    reason_to_visit: str | None = Field(
        default=None,
        max_length=4000,
        description="Experiential highlights and visitation rationale",
    )
    photo_directory: str | None = Field(
        default=None,
        max_length=500,
        description="Local filesystem directory path containing photographs",
    )
    dates_visited: list[str] = Field(
        default_factory=list,
        description="ISO-8601 formatted visit dates (YYYY-MM-DD)",
    )
    estimated_visit_hours: Decimal | None = Field(
        default=None,
        ge=0,
        le=24,
        description="Estimated duration of visit in hours",
    )
    itinerary_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Estimated itinerary days recommended for destination",
    )
