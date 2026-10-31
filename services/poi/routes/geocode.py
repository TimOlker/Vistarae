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

"""Cached reverse geocoding route handler (T-018).

Exposes GET /api/pois/geocode/reverse for the interactive Location Finder.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.repositories.geocache_repo import (
    SqlAlchemyGeocodingCacheRepository,
)
from vistarae_core.domain.entities import User
from vistarae_core.schemas.poi import ForwardGeocodeResponse, ReverseGeocodeResponse

from services.poi.dependencies import get_current_user
from services.poi.services.geocode_service import ReverseGeocodeService
from services.poi.services.geocoding_service import GeocodingService

router = APIRouter(tags=["geocoding"])


@router.get("/pois/geocode/reverse", response_model=ReverseGeocodeResponse)
async def reverse_geocode_endpoint(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in degrees (-90.0 to 90.0)"),
    lng: float = Query(
        ..., ge=-180.0, le=180.0, description="Longitude in degrees (-180.0 to 180.0)"
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReverseGeocodeResponse:
    """Reverse geocodes coordinates via internal PostGIS cache and rate-limited OSM Nominatim."""
    cache_repo = SqlAlchemyGeocodingCacheRepository(session)
    service = ReverseGeocodeService(cache_repo=cache_repo)
    return await service.reverse_geocode(lat=lat, lng=lng)


@router.get("/pois/geocode/forward", response_model=ForwardGeocodeResponse)
async def forward_geocode_endpoint(
    q: str = Query(..., min_length=1, max_length=500, description="Address or destination query"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ForwardGeocodeResponse:
    """Forward geocodes an address or query via internal PostGIS cache and rate-limited OSM Nominatim."""
    cache_repo = SqlAlchemyGeocodingCacheRepository(session)
    service = GeocodingService(cache_repo=cache_repo)
    lat, lon, addrs, cached = await service.geocode(q)
    street = addrs[0].street if addrs else None
    city = addrs[0].city if addrs else None
    state_prov = addrs[0].state_province if addrs else None
    country = addrs[0].country if addrs else None
    postal = addrs[0].postal_code if addrs else None
    return ForwardGeocodeResponse(
        latitude=lat,
        longitude=lon,
        street=street,
        city=city,
        state_province=state_prov,
        country=country,
        postal_code=postal,
        cached=cached,
    )
