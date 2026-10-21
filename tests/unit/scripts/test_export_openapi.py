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

"""Unit test for OpenAPI export script (T044, REQ-CICD-009, REQ-CICD-010).

Verifies that scripts/export_openapi.py correctly exports complete OpenAPI 3.1
specifications including Phase 6 AI Trip Planner routes and Pydantic schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_openapi import export_openapi


def test_export_openapi_generates_valid_spec(tmp_path: Path):
    """Verifies that export_openapi writes a valid OpenAPI 3.1 spec containing itinerary endpoints."""
    out_file = tmp_path / "openapi_test.json"
    result_path = export_openapi(out_file)

    assert result_path == out_file
    assert out_file.exists()

    with open(out_file, encoding="utf-8") as f:
        spec = json.load(f)

    # OpenAPI structure
    assert spec.get("openapi") == "3.1.0"
    assert "paths" in spec
    assert "components" in spec
    assert "schemas" in spec["components"]

    # Phase 6 Itinerary Paths (REQ-PLAN-001, REQ-PLAN-002)
    paths = spec["paths"]
    assert "/api/itineraries" in paths
    assert "/api/itineraries/generate" in paths
    assert "/api/itineraries/{itinerary_id}" in paths
    assert "/api/itineraries/{itinerary_id}/items/reorder" in paths

    # Phase 6 Schemas (REQ-PLAN-005, REQ-CICD-009)
    schemas = spec["components"]["schemas"]
    assert "ItineraryResponse" in schemas
    assert "ItinerarySummary" in schemas
    assert "ItineraryDayResponse" in schemas
    assert "ItineraryItemResponse" in schemas
    assert "ItineraryGenerateRequest" in schemas
    assert "ItineraryItemReorderRequest" in schemas
