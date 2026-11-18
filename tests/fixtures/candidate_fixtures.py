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

"""Test fixtures and mock factories for POI and candidate missing data exemptions."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from vistarae_core.domain.entities import IngestCandidate, PointOfInterest


def create_mock_candidate(
    poi_name: str = "Mount Rainier Peak",
    latitude: float | None = 46.8523,
    longitude: float | None = -121.7603,
    street_address: str | None = None,
    official_url: str | None = None,
    hero_image_url: str | None = "https://example.com/rainier.jpg",
    no_address: bool = False,
    no_websites: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generates candidate dictionary fixture with exemption fields."""
    cand_id = kwargs.get("id", uuid.uuid4())
    job_id = kwargs.get("job_id", uuid.uuid4())
    user_id = kwargs.get("user_id", uuid.uuid4())
    return {
        "id": cand_id,
        "job_id": job_id,
        "user_id": user_id,
        "row_index": kwargs.get("row_index", 1),
        "poi_name": poi_name,
        "latitude": Decimal(str(latitude)) if latitude is not None else None,
        "longitude": Decimal(str(longitude)) if longitude is not None else None,
        "street_address": street_address,
        "official_url": official_url,
        "hero_image_url": hero_image_url,
        "photo_directory": kwargs.get("photo_directory", "/photos"),
        "related_websites": kwargs.get("related_websites", []),
        "no_address": no_address,
        "no_websites": no_websites,
        "recommended_disposition": "accept",
        "user_disposition": None,
        "confidence_score": 90,
        "tags": ["mountain", "scenic"],
    }


def create_mock_poi(
    name: str = "Mount Rainier Peak",
    address: str | None = None,
    official_url: str | None = None,
    no_address: bool = False,
    no_websites: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generates POI dictionary fixture with exemption fields."""
    poi_id = kwargs.get("id", uuid.uuid4())
    user_id = kwargs.get("user_id", uuid.uuid4())
    return {
        "id": poi_id,
        "user_id": user_id,
        "name": name,
        "address": address,
        "official_url": official_url,
        "no_address": no_address,
        "no_websites": no_websites,
        "country_code": "US",
        "admin_level_1": "Washington",
        "locality": "Pierce County",
        "latitude": kwargs.get("latitude", 46.8523),
        "longitude": kwargs.get("longitude", -121.7603),
    }
