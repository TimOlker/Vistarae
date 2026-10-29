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

"""Pydantic v2 boundary schemas for staged candidate ingestion and review (T-025, T-029).

Enforces strict boundary contracts for Phase 1 triage and Phase 2 review per OpenAPI specification.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.value_objects import (
    IngestCandidatePhaseState,
    IngestDisposition,
)
from vistarae_core.schemas.base import StrictBaseModel

__all__ = [
    "CandidateItemResponse",
    "CandidateListResponse",
    "CandidateUpdateRequest",
    "CommitSummaryResponse",
    "JobCancellationResponse",
    "PhaseTransitionResponse",
]


class CandidateItemResponse(StrictBaseModel):
    """Staged candidate POI record presented for Phase 1 triage and Phase 2 review."""

    id: UUID
    job_id: UUID
    row_index: int
    poi_name: str
    recommended_disposition: IngestDisposition
    user_disposition: IngestDisposition | None = None
    matched_existing_poi_id: UUID | None = None
    matched_existing_poi_name: str | None = None
    parent_poi_id: UUID | None = None
    parent_poi_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    street_address: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    dates_visited: list[str] = Field(default_factory=list)
    photo_directory: str
    confidence_score: int = Field(default=0, ge=0, le=100)
    tags: list[str] = Field(default_factory=list)
    description: str | None = None
    reason_to_visit: str | None = None
    update_coordinates: bool = False
    is_skipped: bool = False
    phase_state: IngestCandidatePhaseState
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(StrictBaseModel):
    """Collection response containing staged candidate items for an ingest job."""

    job_id: UUID
    total_candidates: int
    candidates: list[CandidateItemResponse] = Field(default_factory=list)


class CandidateUpdateRequest(StrictBaseModel):
    """Client payload for modifying an individual candidate's attributes or disposition."""

    poi_name: str | None = None
    user_disposition: IngestDisposition | None = None
    matched_existing_poi_id: UUID | None = None
    parent_poi_id: UUID | None = None
    latitude: float | None = None
    longitude: float | None = None
    street_address: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    dates_visited: list[str] | None = None
    photo_directory: str | None = None
    tags: list[str] | None = None
    description: str | None = None
    reason_to_visit: str | None = None
    update_coordinates: bool | None = None
    is_skipped: bool | None = None


class PhaseTransitionResponse(StrictBaseModel):
    """Acknowledgment payload upon advancing candidates from Phase 1 to Phase 2."""

    job_id: UUID
    message: str
    advanced_count: int
    ignored_count: int


class CommitSummaryResponse(StrictBaseModel):
    """Summary of committed POIs and database modifications upon completing Phase 2."""

    job_id: UUID
    committed_count: int
    created_pois: list[UUID] = Field(default_factory=list)
    merged_pois: list[UUID] = Field(default_factory=list)
    message: str


class JobCancellationResponse(StrictBaseModel):
    """Acknowledgment payload upon aborting triage/review and purging staging records."""

    job_id: UUID
    purged_count: int
    message: str

