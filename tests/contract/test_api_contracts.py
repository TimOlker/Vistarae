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

"""Contract and boundary validation tests for Phase 9 API models (T-038).

Validates:
- All incoming Phase 9 models inherit StrictBaseModel with extra="forbid" (REQ-EXT-034)
- Invalid or unknown extra fields are strictly rejected with ValidationError
- FastAPI boundary handlers convert validation errors to RFC 7807 ProblemDetails
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient
from vistarae_core.domain.entities import User
from vistarae_core.schemas.scraping import (
    DeduplicationVerdictSchema,
    ExtractAndCheckRequest,
    POICandidateSchema,
    ScrapingSourcesUpdateRequest,
)
from vistarae_core.schemas.tag import (
    TagCreateRequest,
)

from services.poi.dependencies import get_current_user
from services.poi.main import app


class TestPydanticStrictBaseModelContracts:
    """Verifies that all Phase 9 models enforce strict schema boundaries (extra='forbid')."""

    def test_create_tag_request_extra_forbid(self) -> None:
        """TagCreateRequest rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            TagCreateRequest.model_validate(
                {"name": "Fortification", "unrecognized_field": "disallowed"}
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_scraping_sources_update_request_extra_forbid(self) -> None:
        """ScrapingSourcesUpdateRequest rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            ScrapingSourcesUpdateRequest.model_validate(
                {
                    "valid_scraping_domains": ["wikipedia.org"],
                    "unrecognized_field": "disallowed",
                }
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_scraping_sources_update_request_empty_domains_rejected(self) -> None:
        """ScrapingSourcesUpdateRequest rejects empty list (min_length=1)."""
        with pytest.raises(ValidationError):
            ScrapingSourcesUpdateRequest.model_validate({"valid_scraping_domains": []})

    def test_extract_and_check_request_extra_forbid(self) -> None:
        """ExtractAndCheckRequest rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractAndCheckRequest.model_validate(
                {
                    "source_url": "https://example.com",
                    "unrecognized_field": "disallowed",
                }
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_poi_candidate_schema_extra_forbid(self) -> None:
        """POICandidateSchema rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            POICandidateSchema.model_validate(
                {
                    "name": "Cloud Gate",
                    "description": "Sculpture",
                    "unrecognized_field": "disallowed",
                }
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_deduplication_verdict_schema_extra_forbid(self) -> None:
        """DeduplicationVerdictSchema rejects unknown attributes."""
        with pytest.raises(ValidationError) as exc_info:
            DeduplicationVerdictSchema.model_validate(
                {
                    "status": "UNIQUE_LOCATION",
                    "recommended_action": "proceed",
                    "unrecognized_field": "disallowed",
                }
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)


class TestRFC7807ProblemDetailsContract:
    """Verifies that FastAPI boundary converts validation failures to RFC 7807 ProblemDetails."""

    @pytest.fixture(autouse=True)
    def setup_auth(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub_contract_tester",
            email="contract_tester@vistarae.com",
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    def test_extra_field_returns_rfc7807_problem_details(self) -> None:
        """POST /api/pois/extract-and-check with extra field returns RFC 7807 422 ProblemDetails."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/pois/extract-and-check",
            json={
                "source_url": "https://example.com/bamburgh",
                "unexpected_field": "bad_input",
            },
        )
        assert response.status_code == 422
        assert response.headers.get("content-type") == "application/problem+json"
        body = response.json()
        assert "type" in body
        assert "title" in body
        assert body["status"] == 422
        assert "detail" in body or "errors" in body

    def test_missing_required_field_returns_rfc7807_problem_details(self) -> None:
        """POST /api/pois/extract-and-check without source_url returns RFC 7807 422 ProblemDetails."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/pois/extract-and-check",
            json={"page_title": "Missing Source URL"},
        )
        assert response.status_code == 422
        assert response.headers.get("content-type") == "application/problem+json"
        body = response.json()
        assert body["status"] == 422
