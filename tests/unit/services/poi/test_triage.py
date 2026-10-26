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

"""Unit tests for spatial scale classification and duplicate/nesting triage (T-033).

Validates:
- Spatial scale classification (Macro, Medium, Micro) and radius assignment (REQ-EXT-031)
- Dual-threshold duplicate collision detection (distance <= radius AND similarity >= 0.60) (REQ-EXT-030, REQ-EXT-031)
- Parent-child nesting triage (distance <= radius AND similarity < 0.60 AND existing is larger scale) (REQ-EXT-031, REQ-EXT-032)
- Circular parenting prevention (rejecting candidate parent if descendant) (T-035)
- Fast execution under the 500ms analysis window (REQ-EXT-030)
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock

import pytest
from vistarae_core.domain.exceptions import CyclicHierarchyError
from vistarae_core.services.hierarchy import HierarchyService

from services.poi.scraping.scale_classifier import ScaleClassifier
from services.poi.services.duplicate_service import (
    DuplicateTriageService,
)


class TestScaleClassifier:
    """Test suite for spatial scale heuristic classifier."""

    def test_macro_scale_classification(self) -> None:
        """Verifies Macro classification for parks, ranges, forests, and geographic bodies."""
        macro_names = [
            "Yellowstone National Park",
            "Millennium Park",
            "Rocky Mountain Range",
            "Black Forest",
            "Grand Canyon",
            "Lake Tahoe",
        ]
        for name in macro_names:
            scale = ScaleClassifier.classify(name)
            assert scale == "macro", f"Expected 'macro' for {name}, got {scale}"
            assert ScaleClassifier.get_radius(scale) == 5000.0

    def test_medium_scale_classification(self) -> None:
        """Verifies Medium classification for museums, zoos, campuses, and castles."""
        medium_names = [
            "The Art Institute of Chicago",
            "Lincoln Park Zoo",
            "Edinburgh Castle",
            "Louvre Museum",
            "Harvard University Campus",
            "St. Patrick's Cathedral",
        ]
        for name in medium_names:
            scale = ScaleClassifier.classify(name)
            assert scale == "medium", f"Expected 'medium' for {name}, got {scale}"
            assert ScaleClassifier.get_radius(scale) == 500.0

    def test_micro_scale_classification(self) -> None:
        """Verifies Micro classification for sculptures, monuments, viewpoints, and exhibits."""
        micro_names = [
            "Cloud Gate",
            "Statue of Lincoln",
            "Glacier Point Overlook",
            "Commemorative Plaque",
            "Fountain of Time",
            "Eiffel Tower",
        ]
        for name in micro_names:
            scale = ScaleClassifier.classify(name)
            assert scale == "micro", f"Expected 'micro' for {name}, got {scale}"
            assert ScaleClassifier.get_radius(scale) == 50.0

    def test_scale_hierarchy_comparison(self) -> None:
        """Verifies relative spatial scale rank comparisons."""
        assert ScaleClassifier.is_larger_scale("macro", "medium") is True
        assert ScaleClassifier.is_larger_scale("macro", "micro") is True
        assert ScaleClassifier.is_larger_scale("medium", "micro") is True
        assert ScaleClassifier.is_larger_scale("micro", "macro") is False
        assert ScaleClassifier.is_larger_scale("medium", "macro") is False
        assert ScaleClassifier.is_larger_scale("micro", "micro") is False


class TestDuplicateTriageService:
    """Test suite for dual-threshold duplicate detection and parenting triage."""

    @pytest.mark.asyncio
    async def test_potential_duplicate_detected(self) -> None:
        """Verifies candidate with proximity <= radius and similarity >= 0.60 is classified as POTENTIAL_DUPLICATE."""
        user_id = uuid.uuid4()
        existing_id = uuid.uuid4()

        # Cloud Gate at 41.8827, -87.6233
        existing_poi = {
            "id": existing_id,
            "name": "Cloud Gate",
            "latitude": 41.8827,
            "longitude": -87.6233,
            "description": "Outdoor bean sculpture",
        }

        triage_service = DuplicateTriageService(session=None)
        start = time.perf_counter()
        verdict = await triage_service.evaluate_candidate(
            user_id=user_id,
            name="The Cloud Gate",  # High similarity (0.625 >= 0.60)
            latitude=41.88271,  # 5 meters away
            longitude=-87.62331,
            description="Famous mirrored bean sculpture",
            in_memory_candidates=[existing_poi],
        )
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 500.0, f"Triage took {duration_ms:.2f}ms, expected < 500ms"
        assert verdict.status == "POTENTIAL_DUPLICATE"
        assert verdict.recommended_action == "abort"
        assert verdict.existing_poi_id == existing_id
        assert verdict.existing_poi_name == "Cloud Gate"
        assert verdict.similarity_score is not None and verdict.similarity_score >= 0.60
        assert verdict.distance_meters is not None and verdict.distance_meters <= 50.0

    @pytest.mark.asyncio
    async def test_nearby_parent_detected(self) -> None:
        """Verifies candidate with proximity <= radius, similarity < 0.60, and larger scale existing POI is NEARBY_PARENT."""
        user_id = uuid.uuid4()
        park_id = uuid.uuid4()

        # Millennium Park (Macro) at 41.8826, -87.6226
        existing_park = {
            "id": park_id,
            "name": "Millennium Park",
            "latitude": 41.8826,
            "longitude": -87.6226,
            "description": "Public park located in the Loop community area of Chicago",
        }

        triage_service = DuplicateTriageService(session=None)
        start = time.perf_counter()
        verdict = await triage_service.evaluate_candidate(
            user_id=user_id,
            name="Cloud Gate",  # Micro scale
            latitude=41.8827,  # ~25 meters from Millennium Park center
            longitude=-87.6233,
            description="Outdoor sculpture in downtown Chicago",
            in_memory_candidates=[existing_park],
        )
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < 500.0, f"Triage took {duration_ms:.2f}ms, expected < 500ms"
        assert verdict.status == "NEARBY_PARENT"
        assert verdict.recommended_action == "make_child"
        assert verdict.existing_poi_id == park_id
        assert verdict.existing_poi_name == "Millennium Park"
        assert verdict.scale_classification == "micro"
        assert verdict.similarity_score is not None and verdict.similarity_score < 0.60
        assert verdict.distance_meters is not None and verdict.distance_meters <= 5000.0

    @pytest.mark.asyncio
    async def test_unique_location_when_no_nearby_pois(self) -> None:
        """Verifies candidate far from any existing POI returns UNIQUE_LOCATION and 'proceed'."""
        user_id = uuid.uuid4()
        existing_poi = {
            "id": uuid.uuid4(),
            "name": "Eiffel Tower",
            "latitude": 48.8584,
            "longitude": 2.2945,
        }

        triage_service = DuplicateTriageService(session=None)
        verdict = await triage_service.evaluate_candidate(
            user_id=user_id,
            name="Statue of Liberty",
            latitude=40.6892,
            longitude=-74.0445,
            in_memory_candidates=[existing_poi],
        )

        assert verdict.status == "UNIQUE_LOCATION"
        assert verdict.recommended_action == "proceed"
        assert verdict.existing_poi_id is None

    @pytest.mark.asyncio
    async def test_circular_parenting_prevention(self) -> None:
        """Verifies candidate parent is rejected if assigning it would create a circular hierarchy."""
        user_id = uuid.uuid4()
        current_poi_id = uuid.uuid4()
        descendant_poi_id = uuid.uuid4()

        # Mock HierarchyService to raise CyclicHierarchyError when descendant is proposed as parent
        mock_hierarchy = AsyncMock(spec=HierarchyService)
        mock_hierarchy.validate_no_cycle.side_effect = CyclicHierarchyError(
            str(current_poi_id), str(descendant_poi_id)
        )

        triage_service = DuplicateTriageService(
            session=None,
            hierarchy_service=mock_hierarchy,
        )

        # Existing candidate is a descendant with Macro scale
        descendant_candidate = {
            "id": descendant_poi_id,
            "name": "Sub-Park District",
            "latitude": 41.8826,
            "longitude": -87.6226,
        }

        verdict = await triage_service.evaluate_candidate(
            user_id=user_id,
            name="Sculpture Zone",
            latitude=41.8827,
            longitude=-87.6227,
            current_poi_id=current_poi_id,
            in_memory_candidates=[descendant_candidate],
        )

        # Because circular check failed, the descendant was NOT accepted as parent
        assert verdict.status == "UNIQUE_LOCATION"
        assert verdict.recommended_action == "proceed"
