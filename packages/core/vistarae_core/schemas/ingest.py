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

"""Pydantic v2 boundary schemas for CSV ingestion, progress polling, and duplicate triage.

Enforces Constitution Principle 5 with strict validation (extra='forbid',
validate_assignment=True, str_strip_whitespace=True).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from vistarae_core.domain.value_objects import DuplicateTriageStatus, IngestJobStatus
from vistarae_core.schemas.base import StrictBaseModel


class IngestUploadResponse(StrictBaseModel):
    """Response returned upon accepting a bulk CSV upload."""

    job_id: UUID
    job_status: IngestJobStatus
    total_rows: int
    message: str


class DuplicateItemResponse(StrictBaseModel):
    """Suspected duplicate POI record presented for interactive triage."""

    row_number: int
    raw_name: str
    candidate_poi_id: UUID
    match_type: str
    similarity_score: float
    distance_meters: float
    triage_status: DuplicateTriageStatus
    staged_poi_data: dict[str, Any]


class IngestJobProgressResponse(StrictBaseModel):
    """Progress status, counts, and duplicate items for an ingestion job."""

    job_id: UUID
    job_status: IngestJobStatus
    total_rows: int
    processed_rows: int
    percent_complete: float
    duplicate_payloads: list[DuplicateItemResponse] = Field(default_factory=list)
    error_summary: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TriageDecisionItem(StrictBaseModel):
    """User triage decision for an individual suspected duplicate row."""

    row_number: int
    decision: DuplicateTriageStatus


class TriageRequest(StrictBaseModel):
    """Batch payload containing duplicate triage decisions."""

    decisions: list[TriageDecisionItem]


class PhotoPOIInference(StrictBaseModel):
    """Structured inference response from Google Gemini Flash-Lite."""

    name: str
    description: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_uncertain: bool = False
