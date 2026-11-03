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

"""Domain enumerations and selective enrichment models.

Strictly modeled as Python StrEnum backed by VARCHAR columns per Constitution
Principle 4 (prohibiting PostgreSQL native ENUM types).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from vistarae_core.domain.base import StrictBaseModel
from vistarae_core.domain.value_objects import (
    ExportFormat,
    IngestCandidatePhaseState,
    IngestDisposition,
    TagResolutionAction,
)

__all__ = [
    "CandidateDisposition",
    "ExportFormat",
    "IngestCandidatePhaseState",
    "IngestDisposition",
    "SelectiveEnrichmentOverrides",
    "TagResolutionAction",
]


class CandidateDisposition(StrEnum):
    """Disposition classification for an ingest staging candidate."""

    ACCEPT = "accept"
    SUBLOCATION = "sublocation"
    IN_BATCH_MERGE = "in_batch_merge"
    UPDATE_EXISTING = "update_existing"
    EXCLUDE = "exclude"
    IGNORE = "ignore"


class SelectiveEnrichmentOverrides(StrictBaseModel):
    """Selective field re-calculation flags for POI import."""

    recalculate_description: bool = Field(
        default=False,
        description="Whether to regenerate the AI synthesized description.",
    )
    recalculate_reason_to_visit: bool = Field(
        default=False,
        description="Whether to regenerate the personalized reason to visit.",
    )
    recalculate_tags: bool = Field(
        default=False,
        description="Whether to regenerate taxonomy tags.",
    )
    recalculate_duration: bool = Field(
        default=False,
        description="Whether to recalculate recommended duration and itinerary days.",
    )
    recalculate_links: bool = Field(
        default=False,
        description="Whether to re-discover official website and Wikipedia links.",
    )
