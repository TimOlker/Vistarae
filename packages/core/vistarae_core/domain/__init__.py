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

"""Core domain models, value objects, and domain exceptions."""

from vistarae_core.domain.entities import (
    POI,
    DuplicatePayloadItem,
    GeocodingCacheEntry,
    IdempotencyRecord,
    IngestJob,
    IngestRowMessage,
    ListEntity,
    PotentialDuplicateMatch,
    TagEntity,
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.exceptions import (
    AccountDisabledError,
    CyclicHierarchyError,
    DomainError,
    FileTooLargeError,
    GeocodingTimeoutError,
    IdempotencyConflictError,
    IngestJobNotFoundError,
    InvalidCoordinateError,
    InvalidCSVHeaderError,
    InvalidMimeTypeError,
    POINotFoundError,
    QuotaExceededError,
    RowLimitExceededError,
    TagLimitExceededError,
    TenantNotFoundError,
)
from vistarae_core.domain.value_objects import (
    BoundingBox,
    DeduplicationPreset,
    DuplicateTriageStatus,
    EnrichmentStatus,
    IdempotencyStatus,
    IngestJobStatus,
    MergeResolutionRule,
    PacingMode,
    ThemeMode,
    TransitSpeedMode,
    UserTier,
    VisitState,
    WGS84Point,
)

__all__ = [
    "AccountDisabledError",
    "BoundingBox",
    "CyclicHierarchyError",
    "DeduplicationPreset",
    "DomainError",
    "DuplicatePayloadItem",
    "DuplicateTriageStatus",
    "EnrichmentStatus",
    "FileTooLargeError",
    "GeocodingCacheEntry",
    "GeocodingTimeoutError",
    "IdempotencyConflictError",
    "IdempotencyRecord",
    "IdempotencyStatus",
    "IngestJob",
    "IngestJobNotFoundError",
    "IngestJobStatus",
    "IngestRowMessage",
    "InvalidCSVHeaderError",
    "InvalidCoordinateError",
    "InvalidMimeTypeError",
    "ListEntity",
    "MergeResolutionRule",
    "POI",
    "POINotFoundError",
    "PacingMode",
    "PotentialDuplicateMatch",
    "QuotaExceededError",
    "RowLimitExceededError",
    "TagEntity",
    "TagLimitExceededError",
    "TenantNotFoundError",
    "ThemeMode",
    "TransitSpeedMode",
    "User",
    "UserMetric",
    "UserPreferences",
    "UserQuota",
    "UserTier",
    "VisitState",
    "WGS84Point",
]
