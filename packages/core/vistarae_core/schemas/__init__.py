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

"""Pydantic v2 boundary schemas for requests, responses, and errors."""

from vistarae_core.schemas.admin import (
    AdminMessageRequest,
    AdminMetricsResponse,
    AdminUserDetailResponse,
    QuotaDefaultsRequest,
    QuotaDefaultsResponse,
)
from vistarae_core.schemas.auth import (
    ConfirmSignUpRequest,
    ConfirmSignUpResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.errors import InvalidParam, ProblemDetails
from vistarae_core.schemas.ingest import (
    DuplicateItemResponse,
    IngestJobProgressResponse,
    IngestUploadResponse,
    PhotoPOIInference,
    TriageDecisionItem,
    TriageRequest,
)
from vistarae_core.schemas.ingest_staging import (
    CandidateItemResponse,
    CandidateListResponse,
    CandidateUpdateRequest,
    CommitSummaryResponse,
    JobCancellationResponse,
    PhaseTransitionResponse,
)
from vistarae_core.schemas.itinerary import (
    CircuitBreakerWarning,
    ItineraryCreate,
    ItineraryDayBase,
    ItineraryDayCreate,
    ItineraryDayResponse,
    ItineraryGenerateRequest,
    ItineraryItemBase,
    ItineraryItemCreate,
    ItineraryItemReorderItem,
    ItineraryItemReorderRequest,
    ItineraryItemResponse,
    ItineraryItemSource,
    ItineraryResponse,
    ItineraryStatus,
    ItinerarySummary,
    ItineraryUpdate,
    MissingMealAdvisory,
)
from vistarae_core.schemas.poi import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    BulkListsRequest,
    BulkOperationResponse,
    BulkTagsRequest,
    DedupCheckResponse,
    ListCreateRequest,
    ListResponse,
    ListUpdateRequest,
    ParentPOICandidate,
    POICreateRequest,
    POIListResponse,
    POIReadResponse,
    POIResponse,
    POIUpdateRequest,
    PotentialDuplicateItem,
    ReverseGeocodeResponse,
    SharedListResponse,
)
from vistarae_core.schemas.poi_duplicate import (
    DuplicateCandidateItem,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from vistarae_core.schemas.poi_merge import (
    POIMergeRequest,
    POIMergeResponse,
)
from vistarae_core.schemas.preferences import (
    PlannerPreferencesResponse,
    POIPreferencesResponse,
    UIPreferencesResponse,
    UpdatePlannerPreferencesRequest,
    UpdatePOIPreferencesRequest,
    UpdateUIPreferencesRequest,
    UserPreferencesResponse,
)
from vistarae_core.schemas.scraping import (
    DeduplicationVerdictSchema,
    ExtractAndCheckRequest,
    ExtractAndCheckResponse,
    POICandidateSchema,
    ScrapingSourcesResponse,
    ScrapingSourcesUpdateRequest,
)
from vistarae_core.schemas.tag import (
    TagCreateRequest,
    TagInUseProblemDetails,
    TagResponse,
)
from vistarae_core.schemas.user import (
    UpdateUserQuotaRequest,
    UpdateUserRequest,
    UserMetricsResponse,
    UserProfileResponse,
    UserQuotaResponse,
    UserResponse,
)

from vistarae_core.schemas.poi_export import POIExportRecord

__all__ = [
    "POIExportRecord",
    "AdminMessageRequest",
    "AdminMetricsResponse",
    "AdminUserDetailResponse",
    "BulkDeleteRequest",
    "BulkDeleteResponse",
    "BulkListsRequest",
    "BulkOperationResponse",
    "BulkTagsRequest",
    "CandidateItemResponse",
    "CandidateListResponse",
    "CandidateUpdateRequest",
    "CircuitBreakerWarning",
    "CommitSummaryResponse",
    "ConfirmSignUpRequest",
    "ConfirmSignUpResponse",
    "DedupCheckResponse",
    "DeduplicationVerdictSchema",
    "DuplicateCandidateItem",
    "DuplicateCheckRequest",
    "DuplicateCheckResponse",
    "DuplicateItemResponse",
    "ExtractAndCheckRequest",
    "ExtractAndCheckResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "IngestJobProgressResponse",
    "IngestUploadResponse",
    "InvalidParam",
    "ItineraryCreate",
    "ItineraryDayBase",
    "ItineraryDayCreate",
    "ItineraryDayResponse",
    "ItineraryGenerateRequest",
    "ItineraryItemBase",
    "ItineraryItemCreate",
    "ItineraryItemReorderItem",
    "ItineraryItemReorderRequest",
    "ItineraryItemResponse",
    "ItineraryItemSource",
    "ItineraryResponse",
    "ItineraryStatus",
    "ItinerarySummary",
    "ItineraryUpdate",
    "JobCancellationResponse",
    "ListCreateRequest",
    "ListResponse",
    "ListUpdateRequest",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "LogoutResponse",
    "MissingMealAdvisory",
    "ParentPOICandidate",
    "PhaseTransitionResponse",
    "PhotoPOIInference",
    "PlannerPreferencesResponse",
    "POICandidateSchema",
    "POICreateRequest",
    "POIListResponse",
    "POIMergeRequest",
    "POIMergeResponse",
    "POIPreferencesResponse",
    "POIReadResponse",
    "POIResponse",
    "POIUpdateRequest",
    "PotentialDuplicateItem",
    "ProblemDetails",
    "QuotaDefaultsRequest",
    "QuotaDefaultsResponse",
    "RegisterRequest",
    "RegisterResponse",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "ReverseGeocodeResponse",
    "SharedListResponse",
    "StrictBaseModel",
    "ScrapingSourcesResponse",
    "ScrapingSourcesUpdateRequest",
    "TagCreateRequest",
    "TagInUseProblemDetails",
    "TagResponse",
    "TriageDecisionItem",
    "TriageRequest",
    "UIPreferencesResponse",
    "UpdatePlannerPreferencesRequest",
    "UpdatePOIPreferencesRequest",
    "UpdateUIPreferencesRequest",
    "UpdateUserQuotaRequest",
    "UpdateUserRequest",
    "UserMetricsResponse",
    "UserPreferencesResponse",
    "UserProfileResponse",
    "UserQuotaResponse",
    "UserResponse",
]
