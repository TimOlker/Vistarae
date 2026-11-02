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

"""Authoritative POI exchange data contract for dynamic export and flexible import."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel
from vistarae_core.domain.value_objects import IngestDisposition


class POIExchangeRecord(StrictBaseModel):
    """Authoritative data exchange schema for POI export, import, and backup."""

    poi_id: UUID | None = Field(
        default=None,
        description="Internal POI UUID; populated for committed POIs, empty for raw staged candidates.",
    )
    poi_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Primary display name of the Point of Interest.",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="WGS-84 decimal latitude coordinate.",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="WGS-84 decimal longitude coordinate.",
    )
    street_address: str | None = Field(
        default="",
        description="Street address line(s).",
    )
    city: str | None = Field(
        default="",
        description="Town, municipality, or city name.",
    )
    state_province: str | None = Field(
        default="",
        description="State, province, or primary administrative region.",
    )
    postal_code: str | None = Field(
        default="",
        description="ZIP or postal code.",
    )
    country: str | None = Field(
        default="",
        description="English country name or ISO code.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Approved taxonomy tags associated with the POI.",
    )
    dates_visited: list[str] = Field(
        default_factory=list,
        description="Chronological dates when the POI was visited (YYYY-MM-DD).",
    )
    photo_directory: str | None = Field(
        default="",
        description="Originating filesystem folder path of historical photos.",
    )
    location_confidence_percent: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Confidence score of location resolution (0-100).",
    )
    user_disposition: IngestDisposition | None = Field(
        default=IngestDisposition.ACCEPT,
        description="Triage disposition: accept, ignore, update_existing, sublocation.",
    )
    rejection_reason: str | None = Field(
        default="",
        description="Diagnostic explanation when geocoding or triage fails or ignores a record.",
    )
    ai_description: str | None = Field(
        default="",
        description="Synthesized descriptive overview of the POI.",
    )
    reason_to_visit: str | None = Field(
        default="",
        description="Personalized rationale aligned with traveler profile.",
    )
    recommended_duration_hours: float | None = Field(
        default=2.0,
        ge=0.0,
        description="Recommended dwell time in hours.",
    )
    itinerary_days: int | None = Field(
        default=1,
        ge=0,
        description="Allocated itinerary visit days.",
    )
    hero_image_url: str | None = Field(
        default="",
        description="Public image URL representing the POI.",
    )
    official_website: str | None = Field(
        default="",
        description="Official website or booking URL.",
    )
    wikipedia_url: str | None = Field(
        default="",
        description="Authoritative Wikipedia article URL.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the POI was added to Vistarae.",
    )

    @classmethod
    def get_export_field_names(cls) -> list[str]:
        """Dynamically introspects and returns all core field names for export serialization.

        Returns:
            list[str]: Ordered list of field names defined on POIExchangeRecord.
        """
        return list(cls.model_fields.keys())

    def to_export_dict(self) -> dict[str, str]:
        """Serializes the record into string representations suitable for RFC 4180 CSV export.

        Returns:
            dict[str, str]: Dictionary mapping each core field name to its string representation.
        """
        export_dict: dict[str, str] = {}
        for field_name in self.get_export_field_names():
            val = getattr(self, field_name)
            if val is None:
                export_dict[field_name] = ""
            elif isinstance(val, (list, set)):
                export_dict[field_name] = ";".join(str(item) for item in val if item)
            elif isinstance(val, datetime):
                export_dict[field_name] = val.isoformat()
            elif isinstance(val, IngestDisposition):
                export_dict[field_name] = val.value
            elif isinstance(val, UUID):
                export_dict[field_name] = str(val)
            else:
                export_dict[field_name] = str(val)
        return export_dict
