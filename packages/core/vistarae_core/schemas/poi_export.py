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

"""Standardized POI export record schema for RFC 4180 CSV export and import.

Adheres to:
- REQ-SCR-029: Standardized output schema
- REQ-SCR-034: 12 standardized CSV columns
- StrictBaseModel immutability and validation
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel


class POIExportRecord(StrictBaseModel):
    """Standardized representation of a POI row for RFC 4180 CSV export and import."""

    poi_name: str = Field(
        ...,
        max_length=255,
        description="Standardized name of the attraction",
    )
    street_address: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned street addresses",
    )
    town_city: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned city or locality names",
    )
    state_province: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned state or province names",
    )
    zip_code: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned postal or zip codes",
    )
    country: list[str] = Field(
        default_factory=list,
        description="Semicolon-aligned English country names",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Thematic or contextual tags (empty for photo scraper)",
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
    dates_visited: list[str] = Field(
        default_factory=list,
        description="ISO-8601 visit dates (YYYY-MM-DD)",
    )
    photo_directory: str = Field(
        ...,
        description="Original filesystem directory path of the POI",
    )
    location_confidence_percent: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Location certainty score (0-100)",
    )
    confidence_source: str | None = Field(
        default=None,
        description="Signals and sources contributing to location confidence",
    )
