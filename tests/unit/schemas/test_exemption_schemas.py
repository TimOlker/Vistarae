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

"""Unit tests for Pydantic schema validation of missing data exemption attributes."""

import uuid

from vistarae_core.schemas.ingest_staging import (
    BatchEditCandidatesRequest,
    CandidateItemResponse,
    CandidateUpdateRequest,
)
from vistarae_core.schemas.poi import POICreateRequest, POIResponse, POIUpdateRequest


def test_poi_response_schema_defaults():
    """Verify POIResponse schema defaults no_address and no_websites to False."""
    poi = POIResponse(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Mt Rainier",
        lon=-121.76,
        lat=46.85,
        created_at="2026-11-18T12:00:00Z",
        updated_at="2026-11-18T12:00:00Z",
    )
    assert poi.no_address is False
    assert poi.no_websites is False


def test_poi_create_request_schema():
    """Verify POICreateRequest schema accepts no_address and no_websites."""
    req = POICreateRequest(
        name="Crater Lake",
        lon=-122.1,
        lat=42.9,
        no_address=True,
        no_websites=True,
    )
    assert req.no_address is True
    assert req.no_websites is True


def test_poi_update_request_schema():
    """Verify POIUpdateRequest schema allows optional no_address and no_websites."""
    req = POIUpdateRequest(no_address=True)
    assert req.no_address is True
    assert req.no_websites is None


def test_candidate_item_response_schema():
    """Verify CandidateItemResponse schema exposes no_address and no_websites."""
    cand = CandidateItemResponse(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        row_index=1,
        poi_name="Glacier Peak",
        recommended_disposition="accept",
        photo_directory="/photos",
        phase_state="phase_1_triage",
        created_at="2026-11-18T12:00:00Z",
        updated_at="2026-11-18T12:00:00Z",
    )
    assert cand.no_address is False
    assert cand.no_websites is False


def test_candidate_update_request_schema():
    """Verify CandidateUpdateRequest schema accepts exemption toggles."""
    req = CandidateUpdateRequest(no_address=True, no_websites=False)
    assert req.no_address is True
    assert req.no_websites is False


def test_batch_edit_candidates_request_schema():
    """Verify BatchEditCandidatesRequest schema accepts exemption flags."""
    req = BatchEditCandidatesRequest(
        candidate_ids=[uuid.uuid4(), uuid.uuid4()],
        no_address=True,
        no_websites=False,
    )
    assert req.no_address is True
    assert req.no_websites is False
