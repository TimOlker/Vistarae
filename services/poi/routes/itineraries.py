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

"""FastAPI router for AI Trip Planner and Itinerary Management endpoints.

Implements Phase 6 Endpoints:
- POST /itineraries/generate: Natural language prompt + hybrid PostGIS + pgvector RAG
- GET /itineraries: List user itineraries
- POST /itineraries: Manually create itinerary
- GET /itineraries/{id}: Retrieve detailed itinerary with days, items, and warnings
- PUT /itineraries/{id}: Update itinerary metadata
- DELETE /itineraries/{id}: Delete itinerary
- PUT /itineraries/{id}/items/reorder: Batch item drag-and-drop reordering
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from vistarae_core.domain.entities import User
from vistarae_core.domain.itinerary import (
    Itinerary,
    ItineraryDay,
    ItineraryItem,
    ItineraryStatus,
)
from vistarae_core.ports.itinerary_repo import IItineraryRepository
from vistarae_core.schemas.itinerary import (
    ItineraryCreate,
    ItineraryDayResponse,
    ItineraryGenerateRequest,
    ItineraryItemReorderRequest,
    ItineraryItemResponse,
    ItineraryResponse,
    ItinerarySummary,
    ItineraryUpdate,
)

from services.poi.dependencies import (
    get_current_user,
    get_itinerary_repo,
    get_planner_service,
)
from services.poi.services.planner import PlannerService

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


def _to_itinerary_response(itinerary: Itinerary) -> ItineraryResponse:
    """Helper to convert domain Itinerary to ItineraryResponse schema."""
    return ItineraryResponse(
        id=itinerary.id,
        user_id=itinerary.user_id,  # type: ignore[arg-type]
        title=itinerary.title,
        destination=itinerary.destination,
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        budget_cents=itinerary.budget_cents,
        currency=itinerary.currency,
        status=itinerary.status,
        total_estimated_cost_cents=itinerary.total_estimated_cost_cents,
        days=[
            ItineraryDayResponse(
                id=day.id,
                itinerary_id=itinerary.id,
                day_number=day.day_number,
                calendar_date=day.calendar_date,
                notes=day.notes,
                target_budget_cents=day.target_budget_cents,
                total_cost_cents=day.total_cost_cents,
                items=[
                    ItineraryItemResponse(
                        id=item.id,
                        itinerary_day_id=day.id,
                        title=item.title,
                        category=item.category,
                        source_type=item.source_type,
                        latitude=item.latitude,
                        longitude=item.longitude,
                        order_index=item.order_index,
                        start_time=item.start_time,
                        end_time=item.end_time,
                        duration_hours=item.duration_hours,
                        cost_cents=item.cost_cents,
                        travel_time_prev_minutes=item.travel_time_prev_minutes,
                        travel_distance_prev_meters=item.travel_distance_prev_meters,
                        notes=item.notes,
                        poi_id=item.poi_id,
                        is_backup_for_id=item.is_backup_for_id,
                    )
                    for item in day.items
                ],
            )
            for day in itinerary.days
        ],
        advisories=[],
        circuit_breaker_warnings=[],
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
    )


@router.get("", response_model=list[ItinerarySummary])
async def list_itineraries(
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> list[ItinerarySummary]:
    """Lists all travel itineraries belonging to the authenticated user."""
    itineraries = await repo.list_itineraries_by_user(user.id)
    return [
        ItinerarySummary(
            id=it.id,
            user_id=it.user_id or user.id,
            title=it.title,
            destination=it.destination,
            start_date=it.start_date,
            end_date=it.end_date,
            budget_cents=it.budget_cents,
            currency=it.currency,
            status=it.status,
            total_estimated_cost_cents=it.total_estimated_cost_cents,
            total_days=len(it.days),
            total_activities=sum(len(d.items) for d in it.days),
            created_at=it.created_at,
            updated_at=it.updated_at,
        )
        for it in itineraries
    ]


@router.post("", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
async def create_itinerary(
    payload: ItineraryCreate,
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> ItineraryResponse:
    """Manually creates a new travel itinerary."""
    itinerary_id = uuid4()
    days: list[ItineraryDay] = []

    for d_create in payload.days:
        day_id = uuid4()
        items: list[ItineraryItem] = [
            ItineraryItem(
                id=uuid4(),
                itinerary_day_id=day_id,
                poi_id=i_create.poi_id,
                is_backup_for_id=i_create.is_backup_for_id,
                title=i_create.title,
                category=i_create.category,
                source_type=i_create.source_type,
                latitude=i_create.latitude,
                longitude=i_create.longitude,
                order_index=i_create.order_index,
                start_time=i_create.start_time,
                end_time=i_create.end_time,
                duration_hours=i_create.duration_hours,
                cost_cents=i_create.cost_cents,
                travel_time_prev_minutes=i_create.travel_time_prev_minutes,
                travel_distance_prev_meters=i_create.travel_distance_prev_meters,
                notes=i_create.notes,
            )
            for i_create in d_create.items
        ]
        days.append(
            ItineraryDay(
                id=day_id,
                itinerary_id=itinerary_id,
                day_number=d_create.day_number,
                calendar_date=d_create.calendar_date,
                notes=d_create.notes,
                target_budget_cents=d_create.target_budget_cents,
                total_cost_cents=sum(i.cost_cents for i in items),
                items=items,
            )
        )

    itinerary = Itinerary(
        id=itinerary_id,
        user_id=user.id,
        title=payload.title,
        destination=payload.destination,
        start_date=payload.start_date,
        end_date=payload.end_date,
        budget_cents=payload.budget_cents,
        currency=payload.currency,
        status=ItineraryStatus.DRAFT,
        days=days,
    )
    persisted = await repo.create_itinerary(itinerary)
    return _to_itinerary_response(persisted)


@router.post("/generate", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
async def generate_itinerary(
    payload: ItineraryGenerateRequest,
    user: User = Depends(get_current_user),
    planner_service: PlannerService = Depends(get_planner_service),
) -> ItineraryResponse:
    """Generates an AI-synthesized itinerary using hybrid PostGIS + pgvector RAG."""
    return await planner_service.generate_itinerary(user.id, payload)


@router.get("/{itinerary_id}", response_model=ItineraryResponse)
async def get_itinerary(
    itinerary_id: UUID,
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> ItineraryResponse:
    """Retrieves full details of a specific itinerary."""
    itinerary = await repo.get_itinerary_by_id(itinerary_id, user.id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Itinerary {itinerary_id} not found.",
        )
    return _to_itinerary_response(itinerary)


@router.put("/{itinerary_id}", response_model=ItineraryResponse)
async def update_itinerary(
    itinerary_id: UUID,
    payload: ItineraryUpdate,
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> ItineraryResponse:
    """Updates itinerary title, dates, budget, or status."""
    itinerary = await repo.get_itinerary_by_id(itinerary_id, user.id)
    if not itinerary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Itinerary {itinerary_id} not found.",
        )

    if payload.title is not None:
        itinerary.title = payload.title
    if payload.destination is not None:
        itinerary.destination = payload.destination
    if payload.start_date is not None:
        itinerary.start_date = payload.start_date
    if payload.end_date is not None:
        itinerary.end_date = payload.end_date
    if payload.budget_cents is not None:
        itinerary.budget_cents = payload.budget_cents
    if payload.currency is not None:
        itinerary.currency = payload.currency
    if payload.status is not None:
        itinerary.status = payload.status

    updated = await repo.update_itinerary(itinerary)
    return _to_itinerary_response(updated)


@router.delete("/{itinerary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_itinerary(
    itinerary_id: UUID,
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> None:
    """Deletes an itinerary and all its child days and items."""
    deleted = await repo.delete_itinerary(itinerary_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Itinerary {itinerary_id} not found.",
        )


@router.put("/{itinerary_id}/items/reorder", response_model=ItineraryResponse)
async def reorder_itinerary_items(
    itinerary_id: UUID,
    payload: ItineraryItemReorderRequest,
    user: User = Depends(get_current_user),
    repo: IItineraryRepository = Depends(get_itinerary_repo),
) -> ItineraryResponse:
    """Batch reorders scheduled items across days and time slots."""
    reorder_dicts = [
        {
            "item_id": item.item_id,
            "itinerary_day_id": item.itinerary_day_id,
            "order_index": item.order_index,
            "start_time": item.start_time,
            "end_time": item.end_time,
        }
        for item in payload.items
    ]
    try:
        updated = await repo.reorder_items(user.id, itinerary_id, reorder_dicts)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
    return _to_itinerary_response(updated)
