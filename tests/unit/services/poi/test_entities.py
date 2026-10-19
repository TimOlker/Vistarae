# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for POI domain entities, value objects, and spatial boundaries (T-008).

Verifies:
- WGS84Point coordinate boundaries [-180, 180] and [-90, 90]
- China territory bounding box (73.66°E <= lon <= 135.05°E, 18.16°N <= lat <= 53.55°N)
- BoundingBox coordinate validation and antimeridian crossing detection
- DeduplicationPreset radius conversions (urban 805m, macro 80467m)
- Domain entities: POI, ListEntity, TagEntity, GeocodingCacheEntry, PotentialDuplicateMatch
- Domain exceptions: CyclicHierarchyError, TagLimitExceededError, GeocodingTimeoutError, InvalidCoordinateError, POINotFoundError
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from vistarae_core.domain.entities import (
    POI,
    GeocodingCacheEntry,
    ListEntity,
    PotentialDuplicateMatch,
    TagEntity,
)
from vistarae_core.domain.exceptions import (
    CyclicHierarchyError,
    GeocodingTimeoutError,
    InvalidCoordinateError,
    POINotFoundError,
    TagLimitExceededError,
)
from vistarae_core.domain.value_objects import (
    BoundingBox,
    DeduplicationPreset,
    EnrichmentStatus,
    MergeResolutionRule,
    VisitState,
    WGS84Point,
)


class TestWGS84Point:
    """Tests for canonical WGS-84 coordinate validation and geographic flags."""

    def test_valid_point_instantiation(self) -> None:
        """Asserts point with valid coordinates initializes properly."""
        pt = WGS84Point(lon=-122.4194, lat=37.7749)
        assert pt.lon == -122.4194
        assert pt.lat == 37.7749

    def test_invalid_longitude_raises_value_error(self) -> None:
        """Asserts longitude beyond [-180, 180] raises ValueError."""
        with pytest.raises(ValueError, match="Longitude.*out of range"):
            WGS84Point(lon=180.1, lat=0.0)

        with pytest.raises(ValueError, match="Longitude.*out of range"):
            WGS84Point(lon=-180.1, lat=0.0)

    def test_invalid_latitude_raises_value_error(self) -> None:
        """Asserts latitude beyond [-90, 90] raises ValueError."""
        with pytest.raises(ValueError, match="Latitude.*out of range"):
            WGS84Point(lon=0.0, lat=90.1)

        with pytest.raises(ValueError, match="Latitude.*out of range"):
            WGS84Point(lon=0.0, lat=-90.1)

    def test_china_bbox_detection(self) -> None:
        """Asserts coordinates in China return True and others return False."""
        beijing = WGS84Point(lon=116.4074, lat=39.9042)
        assert beijing.is_in_china_bbox is True

        shanghai = WGS84Point(lon=121.4737, lat=31.2304)
        assert shanghai.is_in_china_bbox is True

        # Exact boundary points
        sw_corner = WGS84Point(lon=73.66, lat=18.16)
        assert sw_corner.is_in_china_bbox is True

        ne_corner = WGS84Point(lon=135.05, lat=53.55)
        assert ne_corner.is_in_china_bbox is True

        # Outside points
        sf = WGS84Point(lon=-122.4194, lat=37.7749)
        assert sf.is_in_china_bbox is False

        tokyo = WGS84Point(lon=139.6917, lat=35.6895)
        assert tokyo.is_in_china_bbox is False


class TestBoundingBox:
    """Tests for 2D map viewport envelopes and antimeridian split detection."""

    def test_valid_bounding_box(self) -> None:
        """Asserts standard bounding box instantiates and detects non-crossing."""
        bbox = BoundingBox(min_lon=-122.5, min_lat=37.7, max_lon=-122.3, max_lat=37.9)
        assert bbox.crosses_antimeridian is False

    def test_antimeridian_crossing_detection(self) -> None:
        """Asserts crossing when min_lon > max_lon (e.g. Fiji, Aleutians)."""
        bbox = BoundingBox(min_lon=175.0, min_lat=-20.0, max_lon=-175.0, max_lat=-15.0)
        assert bbox.crosses_antimeridian is True

    def test_invalid_coordinates_raise_value_error(self) -> None:
        """Asserts out-of-range bbox coordinates raise ValueError."""
        with pytest.raises(ValueError, match="Longitude must be within"):
            BoundingBox(min_lon=-181.0, min_lat=10.0, max_lon=10.0, max_lat=20.0)

        with pytest.raises(ValueError, match="Latitude must be within"):
            BoundingBox(min_lon=-10.0, min_lat=-95.0, max_lon=10.0, max_lat=20.0)

        with pytest.raises(ValueError, match="min_lat.*cannot exceed max_lat"):
            BoundingBox(min_lon=-10.0, min_lat=30.0, max_lon=10.0, max_lat=20.0)


class TestDeduplicationPresetAndRules:
    """Tests for deduplication presets and merge resolution rule."""

    def test_presets_radius_meters(self) -> None:
        """Asserts urban is 805m and macro is 80467m."""
        assert DeduplicationPreset.URBAN.radius_meters == 805.0
        assert DeduplicationPreset.MACRO.radius_meters == 80467.0

    def test_merge_resolution_rule(self) -> None:
        """Asserts MergeResolutionRule stores target, source, and field list."""
        target_id = uuid4()
        source_id = uuid4()
        rule = MergeResolutionRule(
            target_poi_id=target_id,
            source_poi_id=source_id,
            use_source_for=["description", "official_url"],
            merge_tags=True,
        )
        assert rule.target_poi_id == target_id
        assert rule.source_poi_id == source_id
        assert rule.use_source_for == ["description", "official_url"]
        assert rule.merge_tags is True


class TestPOIDomainEntities:
    """Tests for pure POI, ListEntity, TagEntity, GeocodingCacheEntry."""

    def test_poi_instantiation_defaults(self) -> None:
        """Asserts default values on POI aggregate."""
        poi_id = uuid4()
        user_id = uuid4()
        pt = WGS84Point(lon=-119.5383, lat=37.8651)
        poi = POI(
            id=poi_id,
            user_id=user_id,
            name="Yosemite National Park",
            geom=pt,
            states=["California"],
            countries=["United States"],
        )
        assert poi.id == poi_id
        assert poi.user_id == user_id
        assert poi.name == "Yosemite National Park"
        assert poi.geom == pt
        assert poi.parent_poi_id is None
        assert poi.visit_state == VisitState.NOT_VISITED
        assert poi.enrichment_status == EnrichmentStatus.SUCCESS
        assert poi.states == ["California"]
        assert poi.countries == ["United States"]
        assert poi.recommended_visit_days == 1
        assert isinstance(poi.created_at, datetime)
        assert isinstance(poi.updated_at, datetime)

    def test_list_and_tag_entities(self) -> None:
        """Asserts list and tag entity creation."""
        user_id = uuid4()
        list_entity = ListEntity(
            id=uuid4(),
            user_id=user_id,
            title="Summer Vacation 2026",
            is_public=True,
        )
        assert list_entity.title == "Summer Vacation 2026"
        assert list_entity.is_public is True

        tag = TagEntity(id=uuid4(), user_id=user_id, name="scenic-overlook")
        assert tag.name == "scenic-overlook"

    def test_geocoding_cache_entry(self) -> None:
        """Asserts cache entry expiration calculation."""
        entry = GeocodingCacheEntry(
            query_hash="a" * 64,
            lat=37.7749,
            lon=-122.4194,
            formatted_address="San Francisco, CA, USA",
            status="SUCCESS",
        )
        assert entry.query_hash == "a" * 64
        assert entry.expires_at > datetime.now(UTC) + timedelta(days=89)

    def test_potential_duplicate_match(self) -> None:
        """Asserts duplicate match object construction."""
        poi = POI(
            id=uuid4(),
            user_id=uuid4(),
            name="Glacier Point",
            geom=WGS84Point(lon=-119.5732, lat=37.7304),
        )
        match = PotentialDuplicateMatch(
            existing_poi=poi,
            distance_meters=412.5,
            name_similarity=0.85,
            match_confidence=0.92,
        )
        assert match.existing_poi.name == "Glacier Point"
        assert match.distance_meters == 412.5
        assert match.name_similarity == 0.85
        assert match.match_confidence == 0.92


class TestDomainExceptions:
    """Tests for domain exception message formatting and properties."""

    def test_cyclic_hierarchy_error(self) -> None:
        """Asserts CyclicHierarchyError has poi and parent properties."""
        err = CyclicHierarchyError("poi-123", "poi-456")
        assert err.poi_id == "poi-123"
        assert err.proposed_parent_id == "poi-456"
        assert "circular hierarchy" in str(err)

    def test_tag_limit_exceeded_error(self) -> None:
        """Asserts TagLimitExceededError tracks count and limit."""
        err = TagLimitExceededError(35, 30)
        assert err.count == 35
        assert err.limit == 30
        assert "35 tags" in str(err)

    def test_geocoding_timeout_error(self) -> None:
        """Asserts GeocodingTimeoutError tracks query and timeout."""
        err = GeocodingTimeoutError("Mount Whitney", 3.0)
        assert err.query == "Mount Whitney"
        assert err.timeout_seconds == 3.0
        assert "timeout ceiling" in str(err)

    def test_invalid_coordinate_error(self) -> None:
        """Asserts InvalidCoordinateError tracks lat and lon."""
        err = InvalidCoordinateError(95.0, 200.0)
        assert err.lat == 95.0
        assert err.lon == 200.0
        assert "Invalid WGS-84" in str(err)

    def test_poi_not_found_error(self) -> None:
        """Asserts POINotFoundError tracks poi_id."""
        err = POINotFoundError("poi-999")
        assert err.poi_id == "poi-999"
        assert "not found" in str(err)
