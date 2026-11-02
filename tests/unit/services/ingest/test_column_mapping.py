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

"""Unit tests for flexible upload, column alignment detection, and pre-validation reporting (T-014)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from vistarae_core.domain.entities import User

from services.ingest.dependencies import (
    get_current_user,
    get_ingest_repo,
    get_staging_service,
)
from services.ingest.main import app


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid4(),
        cognito_sub="sub-test-flexible-upload",
        email="traveler@example.com",
    )


@pytest.fixture(autouse=True)
def override_auth(mock_user: User):
    mock_ingest_repo = MagicMock()
    mock_ingest_repo.create_job = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_ingest_repo] = lambda: mock_ingest_repo
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_flexible_returns_needs_column_mapping(mock_user: User):
    """Asserts that uploading a file with unmapped headers returns NEEDS_COLUMN_MAPPING status."""
    csv_content = b"Waypoint,CustomHeader,Lat,Lon\r\nPlace A,Sample 1,35.0,139.0\r\n"
    files = {"file": ("test.csv", csv_content, "text/csv")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/ingest/upload-flexible", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "NEEDS_COLUMN_MAPPING"
        assert "CustomHeader" in data["unmapped_columns"]
        assert len(data["sample_rows"]) > 0
        assert "target_fields" in data


@pytest.mark.asyncio
async def test_upload_flexible_validation_error_halts_with_422(mock_user: User):
    """Asserts that format or type failures return 422 with PreValidationReport detailing offending rows."""
    csv_content = b"name,latitude,longitude\r\nPlace A,true,139.0\r\n"
    files = {"file": ("test.csv", csv_content, "text/csv")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/ingest/upload-flexible", files=files)
        assert res.status_code == 422
        data = res.json()
        assert data["error_type"] == "VALIDATION_ERROR"
        assert data["invalid_row_count"] == 1
        assert data["can_skip_invalid"] is True
        assert len(data["issues"]) == 1
        assert data["issues"][0]["column"] == "latitude"
        assert data["issues"][0]["raw_value"] == "true"


@pytest.mark.asyncio
async def test_upload_flexible_skip_invalid_rows_stages_valid(mock_user: User):
    """Asserts that setting skip_invalid_rows=True bypasses invalid rows and stages valid ones."""
    csv_content = b"name,latitude,longitude\r\nValid Place,35.0,139.0\r\nBad Place,abc,139.0\r\n"
    files = {"file": ("test.csv", csv_content, "text/csv")}
    form_data = {"skip_invalid_rows": "true"}

    mock_staging_service = MagicMock()
    mock_staging_service.stage_exchange_records = AsyncMock(return_value=[])
    mock_staging_service.get_unapproved_tags = AsyncMock(return_value={})
    app.dependency_overrides[get_staging_service] = lambda: mock_staging_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/v1/ingest/upload-flexible",
                files=files,
                data=form_data,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "QUEUED"
            assert data["total_rows"] == 1
    finally:
        app.dependency_overrides.pop(get_staging_service, None)
