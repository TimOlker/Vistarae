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

"""User Privacy Exclusion Zone Route Handlers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.repositories.exclusion_zone_repo import (
    SqlAlchemyUserExclusionZoneRepository,
)
from vistarae_core.domain.entities import User, UserExclusionZone
from vistarae_core.schemas.exclusion_zone import (
    ExclusionCheckRequest,
    ExclusionCheckResponse,
    ExclusionZoneCreateRequest,
    ExclusionZoneListResponse,
    ExclusionZoneResponse,
    ExclusionZoneUpdateRequest,
)

from services.user.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/exclusion-zones",
    response_model=ExclusionZoneListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all privacy exclusion zones for the current user",
)
async def list_exclusion_zones(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExclusionZoneListResponse:
    """Returns all geographic exclusion zones configured by the user."""
    logger.info("MSG ->| GET /exclusion-zones for user=%s", current_user.id)
    repo = SqlAlchemyUserExclusionZoneRepository(session)
    zones = await repo.list_by_user(current_user.id)

    items = [
        ExclusionZoneResponse(
            id=z.id,
            name=z.name,
            latitude=z.latitude,
            longitude=z.longitude,
            radius_km=z.radius_km,
            created_at=z.created_at,
            updated_at=z.updated_at,
        )
        for z in zones
    ]
    logger.info("MSG <-| GET /exclusion-zones 200 OK: count=%d", len(items))
    return ExclusionZoneListResponse(items=items)


@router.post(
    "/exclusion-zones",
    response_model=ExclusionZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new privacy exclusion zone",
)
async def create_exclusion_zone(
    payload: ExclusionZoneCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExclusionZoneResponse:
    """Persists a new geographic privacy exclusion zone."""
    logger.info("MSG ->| POST /exclusion-zones: user=%s name='%s'", current_user.id, payload.name)
    repo = SqlAlchemyUserExclusionZoneRepository(session)
    now = datetime.now(UTC)

    zone = UserExclusionZone(
        id=uuid4(),
        user_id=current_user.id,
        name=payload.name.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
        created_at=now,
        updated_at=now,
    )
    created = await repo.create(zone)
    await session.commit()

    logger.info("MSG <-| POST /exclusion-zones 201 Created: id=%s", created.id)
    return ExclusionZoneResponse(
        id=created.id,
        name=created.name,
        latitude=created.latitude,
        longitude=created.longitude,
        radius_km=created.radius_km,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.put(
    "/exclusion-zones/{zone_id}",
    response_model=ExclusionZoneResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing privacy exclusion zone",
)
async def update_exclusion_zone(
    zone_id: UUID,
    payload: ExclusionZoneUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExclusionZoneResponse:
    """Modifies the name, center coordinates, or radius of an exclusion zone."""
    logger.info("MSG ->| PUT /exclusion-zones/%s for user=%s", zone_id, current_user.id)
    repo = SqlAlchemyUserExclusionZoneRepository(session)
    updated = await repo.update(
        zone_id=zone_id,
        user_id=current_user.id,
        name=payload.name.strip() if payload.name is not None else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exclusion zone not found")

    await session.commit()
    logger.info("MSG <-| PUT /exclusion-zones/%s 200 OK", zone_id)
    return ExclusionZoneResponse(
        id=updated.id,
        name=updated.name,
        latitude=updated.latitude,
        longitude=updated.longitude,
        radius_km=updated.radius_km,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete(
    "/exclusion-zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a privacy exclusion zone",
)
async def delete_exclusion_zone(
    zone_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Removes an exclusion zone."""
    logger.info("MSG ->| DELETE /exclusion-zones/%s for user=%s", zone_id, current_user.id)
    repo = SqlAlchemyUserExclusionZoneRepository(session)
    deleted = await repo.delete(zone_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exclusion zone not found")

    await session.commit()
    logger.info("MSG <-| DELETE /exclusion-zones/%s 204 No Content", zone_id)


@router.post(
    "/exclusion-zones/check",
    response_model=ExclusionCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check if a point falls within any user exclusion zones",
)
async def check_point_exclusion(
    payload: ExclusionCheckRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExclusionCheckResponse:
    """Evaluates whether the given (lat, lon) coordinates fall within any active exclusion zones."""
    repo = SqlAlchemyUserExclusionZoneRepository(session)
    matched = await repo.find_matching_zones(current_user.id, payload.latitude, payload.longitude)

    is_excluded = len(matched) > 0
    matched_responses = [
        ExclusionZoneResponse(
            id=z.id,
            name=z.name,
            latitude=z.latitude,
            longitude=z.longitude,
            radius_km=z.radius_km,
            created_at=z.created_at,
            updated_at=z.updated_at,
        )
        for z in matched
    ]

    return ExclusionCheckResponse(
        is_excluded=is_excluded,
        matched_zones=matched_responses,
        matched_zone_names=[z.name for z in matched],
    )

