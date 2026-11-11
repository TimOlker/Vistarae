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
from vistarae_core.schemas.poi import (
    ExtractUrlCoordinatesResponse,
    ForwardGeocodeResponse,
    ReverseGeocodeResponse,
)

from services.poi.dependencies import get_current_user
from services.poi.services.geocode_service import ReverseGeocodeService
from services.poi.services.geocoding_service import GeocodingService
from services.poi.services.url_extractor import UrlCoordinateExtractor

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
    country: str | None = Query(default=None, description="Optional country hint"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ForwardGeocodeResponse:
    """Forward geocodes an address or query via internal PostGIS cache and rate-limited OSM Nominatim."""
    cache_repo = SqlAlchemyGeocodingCacheRepository(session)
    service = GeocodingService(cache_repo=cache_repo)
    lat, lon, addrs, cached = await service.geocode(q, country_hint=country)
    street = addrs[0].street if addrs else None
    city = addrs[0].city if addrs else None
    state_prov = addrs[0].state_province if addrs else None
    resolved_country = addrs[0].country if (addrs and addrs[0].country) else country
    postal = addrs[0].postal_code if addrs else None
    derived_cc = (
        addrs[0].country_code
        if addrs and addrs[0].country_code and addrs[0].country_code != "XX"
        else None
    )
    if not derived_cc and resolved_country:
        from vistarae_core.services.address_normalizer import AddressNormalizer

        mapped = AddressNormalizer.country_to_iso_code(resolved_country)
        if mapped != "XX":
            derived_cc = mapped
    country_code = derived_cc or ("US" if not resolved_country or resolved_country.strip().lower() in ("united states", "usa", "us") else None)
    admin_1 = addrs[0].admin_level_1 if addrs else None
    admin_2 = addrs[0].admin_level_2 if addrs else None
    locality = addrs[0].locality if addrs else None
    resolved_name = (
        addrs[0].raw_geocoding.get("resolved_name")
        if addrs and addrs[0].raw_geocoding and isinstance(addrs[0].raw_geocoding, dict)
        else None
    )
    return ForwardGeocodeResponse(
        latitude=lat,
        longitude=lon,
        resolved_name=resolved_name,
        street=street,
        city=city,
        locality=locality,
        state_province=state_prov,
        admin_level_1=admin_1,
        admin_level_2=admin_2,
        country=resolved_country,
        country_code=country_code,
        postal_code=postal,
        cached=cached,
    )


@router.get("/pois/geocode/extract-url", response_model=ExtractUrlCoordinatesResponse)
@router.post("/pois/geocode/extract-url", response_model=ExtractUrlCoordinatesResponse)
async def extract_url_coordinates_endpoint(
    url: str = Query(..., min_length=4, max_length=2000, description="Webpage or map URL to inspect"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExtractUrlCoordinatesResponse:
    """Extracts coordinates and enriched address from a webpage or map/geohack URL."""
    cache_repo = SqlAlchemyGeocodingCacheRepository(session)
    reverse_service = ReverseGeocodeService(cache_repo=cache_repo)
    geocoding_service = GeocodingService(cache_repo=cache_repo)
    extractor = UrlCoordinateExtractor(
        reverse_geocode_service=reverse_service,
        geocoding_service=geocoding_service,
    )
    return await extractor.extract_coordinates_from_url(url)

